"""Probe features (PREREG §9.2, applied verbatim) + the v0-interim derived signals.

§9.2 pins three features and one degeneracy rule. They are implemented here EXACTLY as written,
with no additions folded in, so that the day the real probe->class classifier is fit it consumes
the same feature definitions this CLI already emits.

The extra signals below (strict delta, fast-math, feasibility) are NOT §9.2 features. They are
labelled `interim: true` everywhere they surface, because v0 must decide about fast-math and §9.2's
three features cannot express that question.
"""
from __future__ import annotations
import math

from ._vendor import theta
import classify  # container-side only (imports numpy at module scope)

IF_NA = None  # §9.2: NA is its own feature value — never imputed, never silently treated as 0


def probe_config_ids():
    """The pre-registered 16-point D-optimal design + the reference config."""
    import json
    from ._vendor import designs_path
    d = json.load(open(designs_path()))
    return sorted(set(d["designs"]["probe_16"]["config_ids"] + [theta.REFERENCE_ID]))


def features(rows):
    """rows: {config_id: table row}. Returns the §9.2 features plus interim signals."""
    attempted = len(rows)
    feas = {cid: r["screen"]["median_ns"] for cid, r in rows.items()
            if r.get("feasible") and r.get("screen")}
    n_feas = len(feas)
    feas_frac = (n_feas / attempted) if attempted else 0.0

    # ---- §9.2 feature 1: Δ̂_probe = max/min over FEASIBLE probe medians
    delta_probe = (max(feas.values()) / min(feas.values())) if n_feas >= 2 else None

    # ---- §9.2 feature 2: ÎF_probe = 1 - R² of the §0.1 main-effects fit on feasible rows,
    #      subject to the degenerate-probe rule.
    if_probe, if_detail, degenerate = IF_NA, None, True
    if n_feas >= 2:
        ids = sorted(feas)
        rank = _model_rank(ids)
        degenerate = n_feas <= rank + 2
        if not degenerate:
            logy = [math.log(feas[c]) for c in ids]
            if_probe, if_detail = classify._interaction_fraction(ids, logy)

    return {
        # §9.2, verbatim
        "delta_probe": delta_probe,
        "if_probe": if_probe,
        "if_probe_na": if_probe is IF_NA,
        "feas_frac": feas_frac,
        "degenerate_probe": degenerate,
        "n_probe_attempted": attempted,
        "n_probe_feasible": n_feas,
        "if_detail": if_detail,
        "reference_feasible": theta.REFERENCE_ID in feas,
        # v0-interim derived signals — NOT §9.2 features
        "interim_signals": _interim_signals(feas),
    }


def _model_rank(feas_ids):
    """Rank of the main-effects design after dropping columns constant over the feasible rows."""
    import numpy as np
    X = theta.design_matrix(feas_ids)
    keep = [0] + [k for k in range(1, X.shape[1]) if 0 < X[:, k].sum() < X.shape[0]]
    return int(np.linalg.matrix_rank(X[:, keep]))


def _interim_signals(feas):
    """Strict/fast-math split. `strict` = fast_math off (the fmffp factor's first element)."""
    if not feas:
        return {"interim": True, "delta_probe_strict": None, "fm_signal": None,
                "best_all_ns": None, "best_strict_ns": None, "feas_signal": None}
    strict = {c: m for c, m in feas.items() if theta.config_of(c)[8][0] == "off"}
    best_all = min(feas.values())
    best_strict = min(strict.values()) if strict else None
    return {
        "interim": True,
        "delta_probe_strict": ((max(strict.values()) / min(strict.values()))
                               if len(strict) >= 2 else None),
        "best_all_ns": best_all,
        "best_strict_ns": best_strict,
        # > 1 means some fast-math config looked faster than anything strict. UNVERIFIED for
        # correctness at this point — the probe measures, the oracle judges, and a fast-math config
        # that wins on speed routinely loses on the oracle (measured: fm_sum, 576/1728 oracle-fail).
        "fm_signal": (best_strict / best_all) if (best_strict and best_all) else None,
        "n_strict_feasible": len(strict),
    }
