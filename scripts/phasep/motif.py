"""Motif+BO — cross-kernel warm-started BO (PREREG §8.4, roadmap §5.5).

SKELETON under the §0.6 HARD-FAIL CONTRACT (D1 guard): extraction failure raises
MotifExtractionError — the kernel is excluded from the Motif arm with a recorded reason, NEVER a
zero vector. `extract_features` currently emits the STRUCTURAL-COUNT baseline (§2.4: explicit
counts, the ProGraML caution against learned embeddings) directly from the .pyx token stream; the
full ORCA ≤5-node graphlet-orbit census on the Cython.Compiler parse-tree graph is the P3.2-full
build (marked TODO) and slots into `extract_features` behind the same contract.

Transfer = leave-one-kernel-out (§8.4): the target kernel's own table is never in its prior; H and R
are never in any prior. NO study runs here; nothing touches a pilot table before the P-2 freeze.
"""
from __future__ import annotations
import os
import re
import numpy as np
import theta
import bo as bomod


class MotifExtractionError(Exception):
    """Raised on any extraction failure (hard-fail contract, §0.6). Never return a zero vector."""


# Structural-count feature names (deterministic; the non-degenerate baseline).
_PATTERNS = {
    "n_for": r"\bfor\b",
    "n_while": r"\bwhile\b",
    "n_if": r"\bif\b",
    "n_index": r"\w+\s*\[",                 # array/memoryview indexing
    "n_call": r"\w+\s*\(",
    "n_cdef": r"\bcdef\b",
    "n_memoryview": r"\[::1\]|\[:\s*,\s*::1\]|\[:\]",
    "n_def": r"\bdef\b",
    "n_cimport": r"\bcimport\b",
    "n_float_decl": r"\b(double|float|floating)\b",
    "n_int_decl": r"\b(long|int|Py_ssize_t|int32_t|int64_t)\b",
    "n_add": r"[^+]\+[^+=]",
    "n_mul": r"\*",
    "n_div": r"[^/]/[^/=]",
    "n_mod": r"%",
}


def extract_features(pyx_path):
    """Return a named structural-count feature vector for a kernel .pyx. Hard-fail on any error."""
    try:
        src = open(pyx_path, encoding="utf-8").read()
    except Exception as e:
        raise MotifExtractionError(f"cannot read {pyx_path}: {e}")
    if not src.strip():
        raise MotifExtractionError(f"empty source: {pyx_path}")
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    feat = {name: float(len(re.findall(pat, code))) for name, pat in _PATTERNS.items()}
    feat["n_lines"] = float(len([l for l in code.splitlines() if l.strip()]))
    vec = np.array(list(feat.values()), float)
    if not np.any(vec > 0):                       # D1 non-degeneracy guard
        raise MotifExtractionError(f"degenerate (all-zero) feature vector: {pyx_path}")
    return feat


def feature_vector(feat):
    return np.array([feat[k] for k in sorted(feat)], float)


def _standardize_S(source_mat, target_vec):
    """§8.4 verbatim: z-score with ddof=0 FIT ON THE SOURCE SET S ONLY; zero-variance features
    (over S) dropped (the dropped set is the ~keep mask, recorded by the caller); the target is
    transformed with S's mu/sd — never included in the fit."""
    mu = source_mat.mean(0); sd = source_mat.std(0)       # ddof=0
    keep = sd > 0
    zs = (source_mat[:, keep] - mu[keep]) / sd[keep]
    zt = (target_vec[keep] - mu[keep]) / sd[keep]
    return zs, zt, keep


def motif_warmstart(target_feat, sources, k=8):
    """LOKO warm start (§8.4): sources = [(kernel_id, feat, best_feasible_config_ids_by_screen,
    gen_index), ...] (gen_index optional; defaults to kernel_id for the tie rule).

    §8.4 verbatim: process sources in DESCENDING cosine similarity (ties by ASCENDING source
    generation index); per source walk feasible configs in ascending screen-median order (the
    caller pre-sorts, ties lowest config_id) and take the first config not already in the init set
    INCLUDING THE REFERENCE; a config used once is not reused; up to k. The <k fill from the §8.3
    default init (its stated order incl. the 5 seed-randoms) is completed by motifbo(), which owns
    the rng. Deterministic.
    """
    if not sources:
        return None
    feats_S = np.vstack([feature_vector(s[1]) for s in sources])
    z_S, z_t, _keep = _standardize_S(feats_S, feature_vector(target_feat))

    def cos(a, b):
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        return float(a @ b / (na * nb)) if na > 0 and nb > 0 else 0.0

    def gen_idx(s):
        return s[3] if len(s) > 3 else s[0]

    order = sorted(range(len(sources)), key=lambda i: (-cos(z_S[i], z_t), gen_idx(sources[i])))
    init, seen = [], {theta.REFERENCE_ID}                  # §8.4: "including the reference"
    for i in order:
        for cid in sources[i][2]:                          # ascending screen-median (caller-sorted)
            if cid not in seen:
                init.append(cid); seen.add(cid)
                break
        if len(init) >= k:
            break
    # The <k fill from the §8.3 default init (ref, expert, known-bad, 5 seed-randoms, in stated
    # order) is completed by motifbo(), which owns the init/interleave rng (bo-math note (b)).
    return init[:k]


def motifbo(sealed, budget, seed, warmstart_configs=None, hash_k=None, seed_i=None, alg_id=4):
    """BO (§8.3) with the 8-config initial design replaced by the LOKO warm start (§8.4).

    warmstart_configs is computed by the study driver from OTHER kernels (LOKO); if None, falls back
    to the §8.3 default init (so the arm degrades gracefully to BO when no prior is available).
    Seed discipline = bo()'s two INDEPENDENT streams (init/interleave rng + pinned RF random_state)
    via bo._streams; alg_id=4 is Motif+BO's slot in the §3.3 fixed order RS<DOE<BO<Motif+BO (the
    study passes hash_k/seed_i explicitly; the default only serves unit tests)."""
    if not warmstart_configs:
        return bomod.bo(sealed, budget, seed, hash_k=hash_k, seed_i=seed_i, alg_id=alg_id)
    rng, rf_state = bomod._streams(seed, hash_k, seed_i, alg_id)
    ws = list(warmstart_configs)
    if len(ws) < 8:                     # §8.4 fill + bo-math note (b): complete to 8 from the
        for cid in bomod._init_design(sealed, rng):        # §8.3 default init in its stated order
            if cid not in ws:
                ws.append(cid)
            if len(ws) >= 8:
                break
    warmstart_configs = ws
    Xall = theta.design_matrix(range(theta.N_CONFIGS))
    queried, best = {}, None
    rid, rfeas, rm, _r = sealed.reference_obs
    queried[rid] = (rfeas, rm)
    if rfeas and rm is not None:
        best = rm

    def observe(cid):
        nonlocal best
        f, m, _r2 = sealed.query(cid)
        queried[cid] = (f, m)
        if f and m is not None:
            best = m if best is None else min(best, m)

    for cid in warmstart_configs:
        if sealed.budget_used >= budget:
            break
        if cid not in sealed.queried_ids:
            observe(cid)
    step = len(warmstart_configs)
    while sealed.budget_used < budget:
        if step % 4 == 3:
            unq = [c for c in range(theta.N_CONFIGS) if c not in queried]
            cand = int(rng.choice(unq)) if unq else None
        else:
            cand = bomod._propose(queried, Xall, best, rng, rf_state)
        if cand is None:
            break
        observe(cand)
        step += 1
    return best
