"""Replay algorithms RS + DOE (PREREG §8.1/§8.2). BO + Motif live in bo.py / motif.py.

Every algorithm sees ONLY the SealedTable (replay.py). It returns best-found-feasible ns within the
budget; the reference config is observation 0 (free, already-queried). Deterministic given (seed).
NO replay STUDY runs here and nothing touches a pilot table before the P-2 freeze.
"""
from __future__ import annotations
import json
import math
import os
import numpy as np
import theta

_DESIGNS = None


def _designs():
    global _DESIGNS
    if _DESIGNS is None:
        here = os.path.dirname(os.path.abspath(__file__))
        for p in (os.environ.get("PHASEP_DOE_DESIGNS"),
                  os.path.join(here, "..", "..", "results", "prereg", "doe_designs_theta.json"),
                  "/results/prereg/doe_designs_theta.json",
                  "/work/prereg/doe_designs_theta.json"):
            if p and os.path.exists(p):
                _DESIGNS = json.load(open(p))["designs"]
                break
        if _DESIGNS is None:
            raise FileNotFoundError("doe_designs_theta.json not found; set PHASEP_DOE_DESIGNS")
    return _DESIGNS


def _ref_best(sealed):
    _rid, rfeas, rm, _r = sealed.reference_obs
    return rm if rfeas else None


def _upd(best, m):
    return m if best is None else min(best, m)


# ------------------------------------------------------------------ RS (§8.1)
def rs(sealed, budget, seed):
    """Uniform without replacement over Θ per seed. Reference is obs 0 (free)."""
    rng = np.random.default_rng(seed)
    best = _ref_best(sealed)
    for cid in rng.permutation(sealed.n_configs):
        if sealed.budget_used >= budget:
            break
        cid = int(cid)
        if cid == sealed.reference_id:
            continue
        feas, m, _r = sealed.query(cid)
        if feas and m is not None:
            best = _upd(best, m)
    return best


# ------------------------------------------------------------------ DOE (§8.2)
def _ridge_fit(X, y, lam=1.0):
    """Ridge on z-scored nonzero-variance dummies (intercept unpenalized). Returns beta in X-space."""
    n, p = X.shape
    mu = X.mean(0); sd = X.std(0)
    scale = np.where(sd > 0, sd, 1.0)
    Z = (X - mu) / scale
    Z[:, 0] = 1.0                                   # keep intercept column as 1
    P = np.eye(p); P[0, 0] = 0.0                    # do not penalize intercept
    b = np.linalg.solve(Z.T @ Z + lam * P, Z.T @ y)
    # map z-space beta back to raw design space so predict uses theta.design_matrix directly
    beta = np.zeros(p)
    beta[1:] = b[1:] / scale[1:]
    beta[0] = b[0] - np.sum(b[1:] * mu[1:] / scale[1:])
    return beta


def _fit(obs_ids, obs_logm):
    X = theta.design_matrix(obs_ids)
    y = np.asarray(obs_logm, float)
    keep = [0] + [k for k in range(1, X.shape[1]) if 0 < X[:, k].sum() < X.shape[0]]
    Xr = X[:, keep]
    use_ols = len(obs_ids) >= 16 and np.linalg.matrix_rank(Xr) == Xr.shape[1]
    beta = np.zeros(X.shape[1])
    if use_ols:
        br, *_ = np.linalg.lstsq(Xr, y, rcond=1e-12)
    else:
        br = _ridge_fit(Xr, y, 1.0)
    for pos, kc in enumerate(keep):
        beta[kc] = br[pos]
    return beta, use_ols


def _pred_rank(beta):
    pred = theta.design_matrix(range(theta.N_CONFIGS)) @ beta
    return sorted(range(theta.N_CONFIGS), key=lambda c: (pred[c], c)), pred


def doe(sealed, budget, seed=None):
    """Pre-registered D-optimal screen -> fit -> predicted-best ranking walk (confirm + leftover).

    N_d = min(24, B-1); committed designs cover N_d ∈ {7,15,24} (B∈{8,16,32/64/128}). Deterministic.
    NOTE: the formal §8.2 fold-over escalation (interaction-augmentation D-optimal design of the top-3
    |effect| factors, triggered on ambiguity) is a P3.3-full refinement with its own TDD, to land
    before BO/DOE enter the replay STUDY (post P-2 freeze). This baseline spends leftover budget by
    walking the main-effects predicted ranking (best-first, skipping queried) — the honest current
    behavior; it is NOT yet the interaction fold-over.
    """
    Nd = min(24, budget - 1)
    key = f"doe_{Nd}" if f"doe_{Nd}" in _designs() else "doe_24"
    design = _designs()[key]["config_ids"]
    best = _ref_best(sealed)
    obs_ids, obs_logm = [], []
    rid, rfeas, rm, _r = sealed.reference_obs
    if rfeas:
        obs_ids.append(rid); obs_logm.append(math.log(rm))
    for cid in design:
        if sealed.budget_used >= budget:
            break
        if cid == rid:
            continue
        feas, m, _r = sealed.query(cid)
        if feas and m is not None:
            obs_ids.append(cid); obs_logm.append(math.log(m)); best = _upd(best, m)
    if obs_ids:
        beta, _ols = _fit(obs_ids, obs_logm)
        ranking, _pred = _pred_rank(beta)
    else:
        ranking = sorted(range(theta.N_CONFIGS))
    # confirm + leftover: walk predicted-best-first, skipping queried, until budget exhausted
    for cid in ranking:
        if sealed.budget_used >= budget:
            break
        if cid in sealed.queried_ids:
            continue
        feas, m, _r = sealed.query(cid)
        if feas and m is not None:
            best = _upd(best, m)
    return best
