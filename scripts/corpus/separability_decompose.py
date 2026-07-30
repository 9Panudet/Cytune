"""Step-1.3 A3 — decompose the separability factorial into main effects + interactions.

Reads the committed separability_factorial raw (<unit>__separability.json: a 2(boundscheck)×3(opt_level)
×2(march) full factorial of endpoint_ns) and computes the ANOVA-style variance decomposition of the
LOG-runtime response (log because directive/flag effects are multiplicative → additive in log; exp(effect)
= the speed ratio). A SATURATED model on the 12 cells (no replication; each cell is a median-of-3-subprocess
point estimate): SS_total = Σ main-effect SS (bc, opt, march) + Σ interaction SS (bc×opt, bc×march,
opt×march, bc×opt×march). The INTERACTION VARIANCE FRACTION = interaction SS / total SS quantifies how much
of the response a categorical BO surrogate could exploit BEYOND additive main effects: small fraction ⇒
separable ⇒ no RF-surrogate advantage over RS (this is the MEASURED basis for the INFERRED BO≤RS).

Worst-case + raw pointers: every number recomputed from the raw here; nothing hand-entered.
Usage: separability_decompose.py <unit>__separability.json [...]
"""
import json
import math
import sys

OPT = ["-O1", "-O2", "-O3"]
MARCH = ["x86-64", "native"]
BC = ["True", "False"]


def decompose(path):
    j = json.load(open(path))
    cells = {(r["bc"], r["opt_level"], r["march"]): r["endpoint_ns"]
             for r in j["configs"] if r.get("endpoint_ns")}
    # y[i,j,k] = log(ns); i=bc(2), j=opt(3), k=march(2)
    y = [[[math.log(cells[(BC[i], OPT[jj], MARCH[k])]) for k in range(2)] for jj in range(3)]
         for i in range(2)]
    n_missing = 2 * 3 * 2 - len(cells)

    def mean(vals):
        return sum(vals) / len(vals)
    flat = [y[i][jj][k] for i in range(2) for jj in range(3) for k in range(2)]
    grand = mean(flat)
    # marginal means
    mA = [mean([y[i][jj][k] for jj in range(3) for k in range(2)]) for i in range(2)]          # bc
    mB = [mean([y[i][jj][k] for i in range(2) for k in range(2)]) for jj in range(3)]          # opt
    mC = [mean([y[i][jj][k] for i in range(2) for jj in range(3)]) for k in range(2)]          # march
    mAB = [[mean([y[i][jj][k] for k in range(2)]) for jj in range(3)] for i in range(2)]
    mAC = [[mean([y[i][jj][k] for jj in range(3)]) for k in range(2)] for i in range(2)]
    mBC = [[mean([y[i][jj][k] for i in range(2)]) for k in range(2)] for jj in range(3)]

    SS_A = 6 * sum((mA[i] - grand) ** 2 for i in range(2))
    SS_B = 4 * sum((mB[jj] - grand) ** 2 for jj in range(3))
    SS_C = 6 * sum((mC[k] - grand) ** 2 for k in range(2))
    SS_AB = 2 * sum((mAB[i][jj] - mA[i] - mB[jj] + grand) ** 2 for i in range(2) for jj in range(3))
    SS_AC = 3 * sum((mAC[i][k] - mA[i] - mC[k] + grand) ** 2 for i in range(2) for k in range(2))
    SS_BC = 2 * sum((mBC[jj][k] - mB[jj] - mC[k] + grand) ** 2 for jj in range(3) for k in range(2))
    SS_tot = sum((v - grand) ** 2 for v in flat)
    # 3-way = residual of the saturated model
    SS_ABC = SS_tot - (SS_A + SS_B + SS_C + SS_AB + SS_AC + SS_BC)

    main = SS_A + SS_B + SS_C
    inter = SS_AB + SS_AC + SS_BC + SS_ABC
    ns_min = min(cells.values()); ns_max = max(cells.values())
    return {
        "unit": j["unit"], "module": j.get("module"), "n_cells": len(cells), "n_missing": n_missing,
        "SS_total": SS_tot,
        "main_effect_fraction": main / SS_tot, "interaction_fraction": inter / SS_tot,
        "ss_fraction": {"boundscheck": SS_A / SS_tot, "opt_level": SS_B / SS_tot, "march": SS_C / SS_tot,
                        "bc:opt": SS_AB / SS_tot, "bc:march": SS_AC / SS_tot,
                        "opt:march": SS_BC / SS_tot, "bc:opt:march": SS_ABC / SS_tot},
        "main_effect_ratio": {  # exp(level spread) = multiplicative speed effect of each factor
            "boundscheck": math.exp(max(mA) - min(mA)),
            "opt_level": math.exp(max(mB) - min(mB)),
            "march": math.exp(max(mC) - min(mC))},
        "delta_observed": ns_max / ns_min, "t_best_ns": ns_min, "t_worst_ns": ns_max}


def main():
    out = [decompose(p) for p in sys.argv[1:]]
    for d in out:
        print(f"\n=== {d['module']} ({d['unit']})  [{d['n_cells']}/12 cells, Δ_observed={d['delta_observed']:.2f}] ===")
        print(f"  MAIN-EFFECT variance fraction = {d['main_effect_fraction']:.1%}"
              f"   INTERACTION fraction = {d['interaction_fraction']:.1%}")
        print("  per-term SS fraction:")
        for k, v in d["ss_fraction"].items():
            print(f"    {k:14} {v:7.1%}")
        print("  main-effect multiplicative size (speed ratio across the factor's levels):")
        for k, v in d["main_effect_ratio"].items():
            print(f"    {k:12} {v:.2f}x")
    print("\n" + json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
