"""Top-main-effect helper for the planted control gate (PREREG §9.1).

The planted-lever control must measure boundscheck as the LARGEST main effect. From a kernel's
table.jsonl, fit the §0.1 main-effects OLS on log(feasible median) and report whether the
boundscheck factor's effect (max |coef| among its dummies) is the largest across the 9 factors.
"""
from __future__ import annotations
import json
import numpy as np
import theta


def factor_effects(table_path):
    feas = {r["config_id"]: r["screen"]["median_ns"]
            for r in map(json.loads, open(table_path)) if r.get("feasible") and r.get("screen")}
    if len(feas) < 20:
        return None
    ids = sorted(feas)
    X = theta.design_matrix(ids)
    y = np.log(np.array([feas[c] for c in ids], float))
    keep = [0] + [k for k in range(1, X.shape[1]) if 0 < X[:, k].sum() < X.shape[0]]
    beta, *_ = np.linalg.lstsq(X[:, keep], y, rcond=1e-12)
    eff = {}
    for pos, kc in enumerate(keep):
        if kc == 0:
            continue
        fidx, _lev = theta.DESIGN_COLUMNS[kc - 1]
        eff[fidx] = max(eff.get(fidx, 0.0), abs(float(beta[pos])))
    return {theta.FACTOR_NAMES[fi]: v for fi, v in eff.items()}


def top_effect_is_boundscheck(table_path):
    eff = factor_effects(table_path)
    if not eff:
        return None
    return max(eff, key=eff.get) == "boundscheck"
