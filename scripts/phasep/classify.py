"""Measured class assignment A/B/C/boundary (PREREG §1).

Input: a kernel's frozen full table as {config_id: median_ns} over FEASIBLE configs only
(infeasible configs omitted). Output: the class record with every intermediate statistic, so the
assignment is fully reproducible and auditor-checkable. Class is MEASURED from the kernel's own
table against the pre-registered thresholds — never asserted by construction (roadmap §3.4).
"""
from __future__ import annotations
import math
import numpy as np
import theta

TAU = 0.02
IF_FLOOR = 1.10   # Amendment A-1b: IF evaluated only when Δ_all ≥ this (5× the 2% noise floor)


def _interaction_fraction(feas_ids, logy):
    """IF = 1 - R² of the main-effects OLS fit (min-norm lstsq; drop constant dummy columns;
    SS_tot=0 ⇒ IF=0). PREREG §1.1."""
    X = theta.design_matrix(feas_ids)                      # (m, 13), col 0 = intercept
    y = np.asarray(logy, float)
    ybar = y.mean()
    ss_tot = float(((y - ybar) ** 2).sum())
    if ss_tot == 0.0:
        return 0.0, {"ss_tot": 0.0, "dropped_cols": "all-equal"}
    # drop dummy columns constant over the feasible rows (keep intercept)
    keep = [0] + [k for k in range(1, X.shape[1]) if 0 < X[:, k].sum() < X.shape[0]]
    Xr = X[:, keep]
    beta, *_ = np.linalg.lstsq(Xr, y, rcond=1e-12)         # min-norm least squares
    resid = y - Xr @ beta
    ss_res = float((resid ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot
    return 1.0 - r2, {"ss_tot": ss_tot, "ss_res": ss_res, "r2": r2, "n_cols": len(keep)}


def _greedy_gap(feas, t_star):
    """Best-improvement 1-flip hill-climb from the reference config over feasible rows."""
    cur = theta.REFERENCE_ID
    while True:
        # strictly-improving feasible neighbors; tie-break lowest median then lowest config_id
        cand = [n for n in theta.neighbors(cur) if n in feas and feas[n] < feas[cur]]
        if not cand:
            break
        cur = min(cand, key=lambda n: (feas[n], n))
    return feas[cur] / t_star - 1.0, cur


def _tau_prominent_optima(feas):
    """Count feasible configs strictly better than ALL feasible neighbors by > τ (PREREG §1.1-4)."""
    optima = []
    for c, m in feas.items():
        nbrs = [feas[n] for n in theta.neighbors(c) if n in feas]
        if not nbrs:
            continue
        if all(m < (1.0 - TAU) * mn for mn in nbrs):
            optima.append(c)
    return optima


def classify(feasible_medians: dict):
    """feasible_medians: {config_id: median_ns} over feasible configs. Returns the class record."""
    feas = {int(k): float(v) for k, v in feasible_medians.items()}
    n_feas = len(feas)
    ref = theta.REFERENCE_ID
    if ref not in feas:
        return {"measured_class": None, "reason": "reference_infeasible", "n_feasible": n_feas}
    if n_feas < 32:
        return {"measured_class": None, "reason": "table_degenerate", "n_feasible": n_feas}

    t_star = min(feas.values())
    t_ref = feas[ref]
    # Δ_strict: best among fast_math=off feasible configs
    strict = [m for c, m in feas.items() if theta.config_of(c)[8][0] == "off"]
    t_strict = min(strict) if strict else t_star
    delta_all = t_ref / t_star
    delta_strict = t_ref / t_strict

    ids = sorted(feas)
    logy = [math.log(feas[c]) for c in ids]
    IF, if_detail = _interaction_fraction(ids, logy)

    gap, gap_end = _greedy_gap(feas, t_star)
    optima = _tau_prominent_optima(feas)
    deep_optima = [c for c in optima if feas[c] >= 1.15 * t_star]

    # Amendment A-1b: IF is only meaningful when Δ_all ≥ IF_FLOOR (5× the 2% noise floor); below it
    # a kernel is class A directly (flat-by-Δ) — at Δ→1, IF = 1−R² is noise/noise.
    if_gated = delta_all < IF_FLOOR
    is_A = if_gated or (IF < 0.10)
    is_B = (not if_gated) and (IF >= 0.25) and (delta_all >= 1.5)
    is_C = (gap >= 0.15) or (len(optima) >= 2 and len(deep_optima) >= 1)
    matches = [name for name, flag in (("A", is_A), ("B", is_B), ("C", is_C)) if flag]
    measured = matches[0] if len(matches) == 1 else "boundary"

    return {
        "measured_class": measured, "matches": matches,
        "n_feasible": n_feas,
        "interaction_fraction": IF, "if_detail": if_detail,
        "delta_all": delta_all, "delta_strict": delta_strict,
        "t_star_ns": t_star, "t_ref_ns": t_ref, "t_strict_ns": t_strict,
        "greedy_gap": gap, "greedy_end_id": gap_end,
        "n_tau_optima": len(optima), "tau_optima": optima,
        "n_deep_optima": len(deep_optima),
        "if_gated": if_gated, "if_floor": IF_FLOOR,   # A-1b: True ⇒ IF not evaluated (flat-by-Δ)
        "flags": {"is_A": is_A, "is_B": is_B, "is_C": is_C},
    }
