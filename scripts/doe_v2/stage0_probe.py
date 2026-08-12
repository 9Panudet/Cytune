"""STAGE 0.1 — is the design/candidate mismatch a DEFECT, or a deliberate bet that pays?

The mismatch is a structural fact: the frozen designs are D-optimal over 1,728 candidates with 13
parameters, while a default (FP-strict) run may only EMIT 576 of them and only 11 of those
parameters are non-constant. `plan.py`'s docstring defends measuring the un-emittable rows anyway:
"measuring is not emitting, and it is what makes the fast-math signal reportable at all."

That defence rests on an ASSUMPTION, not on a preference: that the main-effects model is additive
across the fmffp factor — i.e. that the effect of `-O3` measured under `-ffast-math` is the same
effect `-O3` will have under strict FP. If additivity holds, the fast-math rows are free
information and the design is fine. If it fails, those rows actively BIAS the strict-space effect
estimates the walk then ranks on, and the budget spent on them is worse than wasted.

This project has already MEASURED that assumption's plausibility and named the failure: kernels
classified INT are interaction-dominated by definition. So the assumption is not uniformly safe,
and the question is quantitative.

THIS SCRIPT IS DESCRIPTIVE, NOT A VARIANT COMPARISON. It reads the frozen tables and compares two
FITS on the same data; it runs no search, spends no budget, and produces no regret number. It is
the cheapest probe that discriminates "deliberate bet that pays" from "defect", and it is run
BEFORE the pre-registration so the pre-registration can be written knowing which one it is.
"""
from __future__ import annotations

import json
import os
import statistics
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))

import fleet                                               # noqa: E402
from cytune.plan import STRICT                             # noqa: E402
from cytune._vendor import theta                           # noqa: E402

# The 10 design columns that are NOT fmffp — the ones both fits share and the walk ranks on.
SHARED = [k for k, (fi, _lv) in enumerate(theta.DESIGN_COLUMNS, start=1) if fi != 8]
FMFFP = [k for k, (fi, _lv) in enumerate(theta.DESIGN_COLUMNS, start=1) if fi == 8]
NAMES = [f"{theta.FACTOR_NAMES[fi]}={lv}" for fi, lv in theta.DESIGN_COLUMNS]


def _ols(ids, y):
    """Unregularised least squares on non-constant columns. Returns full-width beta."""
    X = theta.design_matrix(ids)
    keep = [0] + [k for k in range(1, X.shape[1]) if 0 < X[:, k].sum() < X.shape[0]]
    b, *_ = np.linalg.lstsq(X[:, keep], np.asarray(y, float), rcond=1e-12)
    beta = np.zeros(X.shape[1])
    for pos, k in enumerate(keep):
        beta[k] = b[pos]
    return beta


def analyse(tbl):
    """Compare strict-only vs all-rows main effects on ONE kernel's exhaustive table."""
    feas = {c: m for c, (f, m, _r) in tbl.items() if f and m is not None}
    strict = {c: m for c, m in feas.items() if STRICT.allows(c)}
    if len(strict) < 40 or len(feas) < 40:
        return None

    s_ids = sorted(strict)
    a_ids = sorted(feas)
    b_strict = _ols(s_ids, [np.log(strict[c]) for c in s_ids])
    b_all = _ols(a_ids, [np.log(feas[c]) for c in a_ids])

    # (1) Do the SHARED effects agree? Reported in percent-per-level, the unit that matters:
    #     exp(beta) - 1 is the multiplicative effect of turning that level on.
    eff_s = np.exp(b_strict[SHARED]) - 1.0
    eff_a = np.exp(b_all[SHARED]) - 1.0
    max_abs = float(np.max(np.abs(eff_s - eff_a)))
    worst = NAMES[SHARED[int(np.argmax(np.abs(eff_s - eff_a)))] - 1]

    # (2) The CONSEQUENCE the walk actually feels: how differently do the two fits RANK the
    #     emittable space? A biased effect only matters if it reorders candidates.
    cand = sorted(c for c in range(theta.N_CONFIGS) if STRICT.allows(c))
    Xc = theta.design_matrix(cand)
    p_s, p_a = Xc @ b_strict, Xc @ b_all
    order_s = np.argsort(p_s, kind="stable")
    order_a = np.argsort(p_a, kind="stable")

    # top-1 agreement and where the all-rows fit's pick lands in the strict fit's truth
    truth = {c: strict[c] for c in cand if c in strict}
    best_true = min(truth.values())
    pick_s = next(cand[i] for i in order_s if cand[i] in truth)
    pick_a = next(cand[i] for i in order_a if cand[i] in truth)

    return {
        "n_feasible": len(feas), "n_strict": len(strict),
        "max_shared_effect_gap": max_abs, "worst_factor": worst,
        "effects_strict": {NAMES[k - 1]: float(e) for k, e in zip(SHARED, eff_s)},
        "effects_all": {NAMES[k - 1]: float(e) for k, e in zip(SHARED, eff_a)},
        "spearman_rank": float(np.corrcoef(np.argsort(order_s), np.argsort(order_a))[0, 1]),
        "top1_same": bool(pick_s == pick_a),
        # regret of ACTING on each fit's top pick, against the strict-space truth
        "regret_if_fit_on_strict": truth[pick_s] / best_true - 1.0,
        "regret_if_fit_on_all": truth[pick_a] / best_true - 1.0,
    }


def main():
    man, ov = fleet.manifest(), fleet.overlay()
    roster = fleet.roster(man)
    out, by_role = {}, {}
    for role, entries in roster.items():
        rows = []
        for kid, cell in entries:
            a = analyse(fleet.load_table(kid, man, ov))
            if a is None:
                continue
            a["cell"] = cell
            out[kid] = a
            rows.append(a)
        by_role[role] = rows

    print("STAGE 0.1 — does the additivity bet behind the 1,728-candidate design pay?")
    print("(comparing main effects fit on STRICT-only rows vs ALL rows, per kernel, "
          "on the exhaustive frozen tables)\n")
    print(f"{'role':12s} {'n':>4s} {'top-1 same':>11s} {'median |effect gap|':>20s} "
          f"{'max |effect gap|':>17s} {'median regret cost':>19s}")
    for role in ("training", "holdout-H", "R-anchor"):
        rows = by_role.get(role) or []
        if not rows:
            continue
        gaps = [r["max_shared_effect_gap"] for r in rows]
        cost = [r["regret_if_fit_on_all"] - r["regret_if_fit_on_strict"] for r in rows]
        print(f"{role:12s} {len(rows):4d} {sum(r['top1_same'] for r in rows):>6d}/{len(rows):<4d} "
              f"{statistics.median(gaps):>19.1%} {max(gaps):>17.1%} "
              f"{statistics.median(cost):>+19.2%}")

    print("\nPer-cell, all roles pooled (the additivity assumption is a property of the LANDSCAPE):")
    cells = {}
    for a in out.values():
        cells.setdefault(a["cell"], []).append(a)
    print(f"{'cell':12s} {'n':>4s} {'top-1 same':>11s} {'median |effect gap|':>20s} "
          f"{'median regret cost':>19s}")
    for cell in sorted(cells):
        rows = cells[cell]
        gaps = [r["max_shared_effect_gap"] for r in rows]
        cost = [r["regret_if_fit_on_all"] - r["regret_if_fit_on_strict"] for r in rows]
        print(f"{cell:12s} {len(rows):4d} {sum(r['top1_same'] for r in rows):>6d}/{len(rows):<4d} "
              f"{statistics.median(gaps):>19.1%} {statistics.median(cost):>+19.2%}")

    p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                     "results", "doe_v2", "stage0_additivity_probe.json")
    json.dump(out, open(p, "w"), indent=1)
    print(f"\nraw -> {p}   (n={len(out)} kernels)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
