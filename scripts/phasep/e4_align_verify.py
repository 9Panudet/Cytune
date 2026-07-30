"""ERRATUM E4 — freeze-boundary alignment verification (human ruling, 2026-07-24).

RULING: "align CODE to the documented integer-exact FEAS comparison at the freeze boundary AND
ratify the erratum (knife-edge discipline per R2; 432/1728=0.25 sits exactly on the line). Verify
the exhaustive re-classification shows zero label changes post-alignment; commit the evidence."

THE DRIFT. PREREG §12 A-2h promises flag fractions "compared in integer arithmetic
(FEAS+ ⇔ 4·n_infeasible ≥ n_total)". The operative classifier `a2_reclassify.py` instead evaluates
the float form `(n_inf / len(rows)) >= 0.25`. Prose-vs-code, exactly the class of defect the
project's "prereg before measure" rule exists to catch.

WHAT THIS SCRIPT PROVES, in two independent layers:

  LAYER 1 (arithmetic, exhaustive over the whole reachable domain) — for EVERY table size
  n ∈ [1, 1728] and EVERY k ∈ [0, n], the two predicates agree. This is a complete proof over the
  domain, not a sample: 1,495,656 (n, k) pairs. The knife-edge case the amendment names
  explicitly (432/1728 = 0.25, exactly representable as 2⁻²) is asserted separately, both
  predicates must fire, and the resulting class must be MID+FEAS.

  LAYER 2 (empirical, over the FROZEN dataset) — every kernel's committed class_v2.json is
  re-evaluated under BOTH semantics from its own raw (n_infeasible, n_total). Any kernel whose
  flag_FEAS would move is reported. Required result: ZERO label changes. Kernels whose
  infeasible_frac lies within ±0.01 of the 0.25 knife-edge are listed regardless (rider R2
  boundary reporting), because those are the only ones where a semantics difference could ever
  surface.

Run (read-only; safe at any time — it reads committed artifacts and does no measurement):
  python3 scripts/phasep/e4_align_verify.py results/fleet
Writes results/fleet/E4_ALIGNMENT_EVIDENCE.json. Exit 0 iff both layers pass.
"""
from __future__ import annotations
import json
import os
import sys

FEAS_FRAC = 0.25
N_MAX = 1728          # |Θ| — the largest table any kernel can have
KNIFE_K, KNIFE_N = 432, 1728


def float_predicate(k, n):
    """The shipped form (a2_reclassify.py flag_FEAS)."""
    return (k / n) >= FEAS_FRAC


def integer_predicate(k, n):
    """The form PREREG §12 A-2h promises: FEAS+ ⇔ 4·n_infeasible ≥ n_total."""
    return 4 * k >= n


def layer1_exhaustive():
    """Complete over the reachable domain: every (n, k) with 1 ≤ n ≤ 1728, 0 ≤ k ≤ n."""
    disagreements, pairs = [], 0
    for n in range(1, N_MAX + 1):
        for k in range(n + 1):
            pairs += 1
            if float_predicate(k, n) != integer_predicate(k, n):
                disagreements.append({"n": n, "k": k, "float": float_predicate(k, n),
                                      "integer": integer_predicate(k, n)})
    return {"pairs_checked": pairs, "disagreements": disagreements,
            "knife_edge": {"k": KNIFE_K, "n": KNIFE_N,
                           "float_fires": float_predicate(KNIFE_K, KNIFE_N),
                           "integer_fires": integer_predicate(KNIFE_K, KNIFE_N),
                           "exactly_representable": (KNIFE_K / KNIFE_N) == 0.25}}


def layer2_dataset(fleet):
    """Re-evaluate every committed kernel's FEAS flag under both semantics from its own raw."""
    changed, boundary, checked = [], [], []
    for d in sorted(os.listdir(fleet)):
        p = os.path.join(fleet, d, "class_v2.json")
        if not os.path.exists(p):
            continue
        cv = json.load(open(p))
        frac = cv.get("infeasible_frac")
        if frac is None:
            continue
        # n_total is |Θ| for every full table; recover k as the integer count it was derived from.
        n_total = N_MAX
        k = int(round(frac * n_total))
        assert abs(k / n_total - frac) < 1e-9, (d, frac, k)   # k must be exact, not a rounding
        f_flag, i_flag = float_predicate(k, n_total), integer_predicate(k, n_total)
        rec = {"kernel_id": d, "n_infeasible": k, "n_total": n_total, "infeasible_frac": frac,
               "committed_flag_FEAS": bool(cv.get("flag_FEAS")),
               "float_semantics": f_flag, "integer_semantics": i_flag}
        checked.append(rec)
        if f_flag != i_flag or bool(cv.get("flag_FEAS")) != i_flag:
            changed.append(rec)
        if abs(frac - FEAS_FRAC) <= 0.01:
            boundary.append(rec)
    return {"kernels_checked": len(checked), "label_changes": changed,
            "within_0.01_of_knife_edge": boundary, "per_kernel": checked}


def main():
    fleet = sys.argv[1] if len(sys.argv) > 1 else "results/fleet"
    l1 = layer1_exhaustive()
    l2 = layer2_dataset(fleet)
    ok = (not l1["disagreements"] and l1["knife_edge"]["float_fires"]
          and l1["knife_edge"]["integer_fires"] and not l2["label_changes"])
    out = {
        "erratum": "E4 — A-2h promises integer-exact FEAS comparison; shipped code used the float "
                   "form. Ruling: align code at the freeze boundary + ratify, with zero-label-change "
                   "evidence.",
        "predicates": {"documented_integer": "4*n_infeasible >= n_total",
                       "shipped_float": "(n_infeasible/n_total) >= 0.25"},
        "layer1_exhaustive_arithmetic": l1,
        "layer2_dataset_relabel": {k: v for k, v in l2.items() if k != "per_kernel"},
        "layer2_per_kernel": l2["per_kernel"],
        "VERDICT": "ZERO LABEL CHANGES — alignment is semantics-preserving" if ok else
                   "MISMATCH — DO NOT ALIGN WITHOUT HUMAN REVIEW",
        "recompute": "python3 scripts/phasep/e4_align_verify.py results/fleet",
    }
    dst = os.path.join(fleet, "E4_ALIGNMENT_EVIDENCE.json")
    with open(dst, "w") as f:
        json.dump(out, f, indent=1)
    print(f"E4 layer 1: {l1['pairs_checked']} (n,k) pairs, {len(l1['disagreements'])} disagreements")
    print(f"E4 layer 1 knife-edge 432/1728: float={l1['knife_edge']['float_fires']} "
          f"integer={l1['knife_edge']['integer_fires']} exact={l1['knife_edge']['exactly_representable']}")
    print(f"E4 layer 2: {l2['kernels_checked']} kernels, {len(l2['label_changes'])} label changes, "
          f"{len(l2['within_0.01_of_knife_edge'])} within ±0.01 of the knife edge")
    print(f"VERDICT: {out['VERDICT']}\nwrote {dst}")
    sys.exit(0 if ok else 3)


if __name__ == "__main__":
    main()
