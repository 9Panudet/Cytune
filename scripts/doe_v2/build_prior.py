"""V3's prior K, derived from the measured between-kernel variance of each factor's effect.

Bayesian D-optimality maximises det(X'X/σ² + Σ₀⁻¹), equivalently det(X'X + σ²Σ₀⁻¹). So the prior
term is K = σ² / var_between(β_j) — a factor whose effect is nearly the same on every kernel needs
few points to pin down, and a factor that swings wildly between kernels needs many. Both quantities
are MEASURED here, not chosen:

  var_between(β_j)  variance of the j-th strict-space main effect across TRAINING kernels
  σ²                median residual variance of that same main-effects fit — i.e. everything the
                    additive model does not explain (interactions + rig noise)

TRAINING FLEET ONLY. holdout-H and R-anchor are confirmatory (PREREG_DOE_V2 §4); deriving the prior
from them would be fitting the engine to its own test set, which is the mistake this project has a
name for. The roster split comes from FREEZE_MANIFEST_V2's `role` field, written at the P-2 freeze.

The intercept needs no special case: absolute kernel runtimes differ by orders of magnitude, so its
between-kernel variance is enormous and K₀ collapses to ~0 on its own. That is the unpenalised
intercept falling out of the measurement rather than being asserted.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))

import designs_v2 as D                                     # noqa: E402
import fleet                                               # noqa: E402
from cytune._vendor import theta                           # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "results", "doe_v2", "prior_K.json")


def effect_vector(tbl, policy, coding="dummy"):
    """Ground-truth strict-space main effects for one kernel, from its exhaustive table.

    Returns (beta over live columns, residual variance) or None if too few feasible rows.
    """
    feas = {c: m for c, (f, m, _r) in tbl.items()
            if f and m is not None and policy.allows(c)}
    if len(feas) < 60:
        return None
    ids = sorted(feas)
    keep = D.live_columns(D.candidates(policy), coding)
    X = D.model_matrix(ids, coding)[:, keep]
    y = np.log(np.array([feas[c] for c in ids], float))
    beta, *_ = np.linalg.lstsq(X, y, rcond=1e-12)
    resid = y - X @ beta
    dof = max(1, len(ids) - X.shape[1])
    return beta, float(resid @ resid / dof)


def main(policy_name="strict", coding="dummy"):
    policy = D.POLICIES[policy_name]
    man, ov = fleet.manifest(), fleet.overlay()
    train = [k for k, v in sorted(man["kernels"].items())
             if v["role"] == "training"
             and os.path.exists(os.path.join(fleet.FLEET, k, "table.jsonl"))]

    betas, sig2, used = [], [], []
    for kid in train:
        r = effect_vector(fleet.load_table(kid, man, ov), policy, coding)
        if r is None:
            continue
        betas.append(r[0])
        sig2.append(r[1])
        used.append(kid)
    B = np.array(betas)
    sigma2 = float(np.median(sig2))
    var_between = B.var(axis=0, ddof=1)
    K = sigma2 / np.maximum(var_between, 1e-12)

    keep = D.live_columns(D.candidates(policy), coding)
    names = ["intercept"] + [f"{theta.FACTOR_NAMES[fi]}={lv}" for fi, lv in theta.DESIGN_COLUMNS]
    live_names = [names[k] for k in keep]

    doc = {
        "policy": policy_name, "coding": coding,
        "n_training_kernels": len(used), "sigma2_median": sigma2,
        "param_names": live_names,
        "var_between": var_between.tolist(),
        "mean_effect": B.mean(axis=0).tolist(),
        "K": K.tolist(),
        "derivation": ("K_j = sigma2 / var_between(beta_j); beta from OLS main-effects on each "
                       "TRAINING kernel's policy-allowed exhaustive rows; sigma2 = median residual "
                       "variance of that fit. Training fleet only (PREREG_DOE_V2 §4)."),
        "kernels": used,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(doc, open(OUT, "w"), indent=1)

    print(f"prior K  ({policy_name}, {coding} coding, n={len(used)} TRAINING kernels)")
    print(f"  sigma2 (median residual var of the additive fit) = {sigma2:.5f}")
    print(f"  {'parameter':26s} {'mean effect':>12s} {'sd between':>11s} {'K':>10s}")
    for n, m, v, k in zip(live_names, B.mean(axis=0), var_between, K):
        eff = f"{np.exp(m) - 1:+.1%}" if n != "intercept" else "     —"
        print(f"  {n:26s} {eff:>12s} {np.sqrt(v):>11.4f} {k:>10.3f}")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
