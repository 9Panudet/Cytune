"""Build the DOE-v2 candidate designs. Deterministic, committed as data, auditor-recomputable.

SAME MACHINERY AS scripts/phasep/build_doe_designs.py — Fedorov single-best-swap exchange on the
Cook & Nachtsheim (1980) rank-1 delta, 50 seeded restarts, keep max log-det, ties broken by the
lexicographically-lowest sorted config_id tuple. Three things are generalised, and only three:

  1. THE CANDIDATE SET is the policy's emittable set, not all of Θ (V1 — the Stage-0 fix).
  2. THE PRIOR TERM. The criterion becomes det(Xd'Xd + A) where A = X0'X0 + K:
       X0  rows already paid for and conditioned on (V2 — the probe augmentation)
       K   a prior precision matrix (V3 Bayesian-D; eps*I recovers the classical criterion)
     The delta formula holds for any invertible M by the matrix determinant lemma, which is why
     the study's own docstring states it that way rather than for the unregularised case.
  3. THE CODING may be drop-first dummy (default) or orthogonal-polynomial for the ordered
     factors (V4). Same parameter count either way.

WHY THE DESIGNS ARE FROZEN DATA AND NOT COMPUTED AT RUN TIME. A design computed in the product
would make what cytune measures depend on the numpy version and the RNG of the machine it runs on,
which is a different search per host and un-auditable after the fact. The study's designs are
committed for that reason and these follow the rule: this script writes a JSON, the product reads
it, and an auditor recomputes the JSON from this script plus theta.py.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))

from cytune.plan import EmissionPolicy                    # noqa: E402
from cytune._vendor import theta                          # noqa: E402
import seeds                                              # noqa: E402  (vendored, on sys.path)

EPS = 1e-6
TOL = 1e-10
RESTARTS = 50
MAX_ITER = 2000

# The emission policies cytune can run under, each with its own candidate set and parameter count.
POLICIES = {
    "strict":     EmissionPolicy(),
    "contract":   EmissionPolicy(allow_fp_contract=True),
    "fastmath":   EmissionPolicy(allow_fast_math=True, allow_fp_contract=True),
    "portable":   EmissionPolicy(portable_flags=True),
}

# Ordered factors get polynomial contrasts under the "ordinal" coding (V4). opt_level is ordered
# by optimisation level; funroll is NOT naturally ordered (omit/on/off are three regimes, not a
# scale) — it is included because the directive asks for it and because "omit < on" is at least
# arguable, and whether that helps or is noise is exactly what V4 measures.
ORDINAL_FACTORS = {5: ("-O1", "-O2", "-O3"), 7: ("omit", "on", "off")}


def candidates(policy):
    return [c for c in range(theta.N_CONFIGS) if policy.allows(c)]


# ------------------------------------------------------------------------------------- coding
def _poly_contrasts(k):
    """Orthonormal linear/quadratic contrasts for a k-level ordered factor (k-1 columns)."""
    x = np.arange(k, dtype=float)
    cols = []
    for deg in range(1, k):
        v = x ** deg
        for prev in cols:                      # Gram-Schmidt against lower degrees and the mean
            v = v - (v @ prev) / (prev @ prev) * prev
        v = v - v.mean()
        cols.append(v)
    return np.array([c / np.linalg.norm(c) for c in cols]).T      # (k, k-1)


def model_matrix(ids, coding="dummy"):
    """Full-width (13-column) model matrix under the requested coding.

    Column ORDER and MEANING are identical to theta.DESIGN_COLUMNS in both codings, so a beta
    vector is always interpretable against the same names and the two codings are comparable
    parameter-for-parameter.
    """
    if coding == "dummy":
        return theta.design_matrix(ids)
    if coding != "ordinal":
        raise ValueError(f"unknown coding {coding!r}")
    contrasts = {k: _poly_contrasts(len(lv)) for k, lv in ORDINAL_FACTORS.items()}
    rows = []
    for cid in ids:
        cfg = theta.config_of(cid)
        row = [1.0]
        for k, lv in theta.DESIGN_COLUMNS:
            if k in ORDINAL_FACTORS:
                levels = ORDINAL_FACTORS[k]
                deg = levels.index(lv) - 1          # drop-first: lv is levels[1] or levels[2]
                row.append(float(contrasts[k][levels.index(cfg[k]), deg]))
            else:
                row.append(1.0 if cfg[k] == lv else 0.0)
        rows.append(row)
    return np.array(rows, dtype=float)


def live_columns(cand_ids, coding="dummy"):
    """Column indices that are not constant over the candidate set — the estimable parameters.

    THIS IS THE STAGE-0 FIX IN ONE FUNCTION. Under FP-strict the two fmffp dummies are constant 0
    over all 576 candidates, so there are 11 parameters, not 13, and a design built for 13 is
    spending points to estimate two coefficients that do not exist in its own candidate set.
    """
    X = model_matrix(cand_ids, coding)
    return [0] + [k for k in range(1, X.shape[1])
                  if not np.allclose(X[:, k], X[0, k])]


# ------------------------------------------------------------------------------------ Fedorov
def _fedorov_once(XALL, A, Nd, rng):
    """One restart. A is the prior/augmentation term added to Xd'Xd (must make M invertible)."""
    n, p = XALL.shape
    D = rng.choice(n, size=Nd, replace=False)
    for _ in range(MAX_ITER):
        Xd = XALL[D]
        M = Xd.T @ Xd + A
        Minv = np.linalg.inv(M)
        d_all = np.einsum("ij,jk,ik->i", XALL, Minv, XALL)
        d_i = d_all[D]
        d_ij = (XALL[D] @ Minv) @ XALL.T
        ratio = 1.0 + (d_all[None, :] - d_i[:, None]) + (d_i[:, None] * d_all[None, :] - d_ij ** 2)
        ratio[:, D] = -np.inf
        flat = int(np.argmax(ratio))
        i_star, j_star = divmod(flat, n)
        if ratio[i_star, j_star] <= 1.0 + TOL:
            break
        D[i_star] = j_star
    _, logdet = np.linalg.slogdet(XALL[D].T @ XALL[D] + A)
    return sorted(int(i) for i in D), float(logdet)


def build(Nd, cand_ids, key, coding="dummy", prior_rows=None, K=None):
    """A D-optimal exact design of size Nd over `cand_ids`.

    prior_rows: config_ids already paid for, whose information is conditioned on (V2).
    K:          diagonal prior precision, length = number of live columns (V3). Defaults to eps*I.
    """
    keep = live_columns(cand_ids, coding)
    XALL = model_matrix(cand_ids, coding)[:, keep]
    p = XALL.shape[1]

    if K is None:
        A = EPS * np.eye(p)
    else:
        K = np.asarray(K, float)
        if K.shape != (p,):
            raise ValueError(f"K has length {K.shape} but this design has {p} live parameters")
        A = np.diag(K)
    n_prior = 0
    if prior_rows:
        X0 = model_matrix(sorted(prior_rows), coding)[:, keep]
        A = A + X0.T @ X0
        n_prior = len(prior_rows)

    master = seeds.seq(*key)
    best = None
    for child in master.spawn(RESTARTS):
        ids, logdet = _fedorov_once(XALL, A, Nd, np.random.default_rng(child))
        cand = (logdet, [cand_ids[i] for i in ids])
        if best is None or logdet > best[0] + 1e-9 or (
                abs(logdet - best[0]) <= 1e-9 and cand[1] < best[1]):
            best = cand
    logdet, ids = best
    Xd = model_matrix(ids, coding)[:, keep]
    rank = int(np.linalg.matrix_rank(Xd))
    return {"N_d": Nd, "key": list(key), "config_ids": sorted(ids), "logdet": logdet,
            "rank": rank, "n_params": p, "n_candidates": len(cand_ids),
            "coding": coding, "n_prior_rows": n_prior,
            "full_rank": rank == min(Nd, p)}
