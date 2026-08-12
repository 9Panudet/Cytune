"""Aggregate the Step-1.3 Δ-probe per-unit raw JSONs into the §1.3.2 admission verdict.

Recomputes from raw (stats-from-raw discipline): reads results/characterization/delta_probe/*.json
(each the committed output of delta_probe.py), reports the per-unit Δ distribution, corpus median Δ,
and the fraction with Δ ≥ 1.2, then applies the frozen §1.3.2 gate:
    NON-FLAT  iff  median Δ ≥ 1.5  AND  ≥ 70% of units with Δ ≥ 1.2.
The §1.3.2 metric is Δ_all = t_worst/t_best over the 16-config probe; Δ_feasible_strict (the FP=T
bit-preserving subset) is reported alongside as the RQ1-honest lower view.

Usage: delta_aggregate.py [dir=results/characterization/delta_probe]
"""
import glob
import json
import os
import statistics
import sys


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "results/characterization/delta_probe"
    units = []
    for path in sorted(glob.glob(os.path.join(d, "*.json"))):
        if path.endswith("__endpoint.json"):
            continue                       # screen aggregate: endpoint files handled separately
        with open(path) as fh:
            j = json.load(fh)
        if j.get("delta_all") is None:
            continue
        units.append(j)

    if not units:
        print("no Δ-probe results found in", d)
        return

    def gate(metric):
        ds = [u[metric] for u in units if u.get(metric) is not None]
        med = statistics.median(ds)
        frac12 = sum(x >= 1.2 for x in ds) / len(ds)
        non_flat = (med >= 1.5) and (frac12 >= 0.70)
        return med, frac12, non_flat, ds

    print(f"Δ-probe aggregate  ({len(units)} units; {d})\n")
    hdr = f"{'module':22} {'archetype':22} {'Δ_all':>7} {'Δ_strict':>9} {'t_best_ms':>10} {'worst':>6} {'best':>6}"
    print(hdr); print("-" * len(hdr))
    for u in sorted(units, key=lambda x: -x["delta_all"]):
        tb = (u["t_best_ns"] or 0) / 1e6
        dfs = u.get("delta_feasible_strict")
        print(f"{u['module']:22} {str(u.get('archetype')):22} {u['delta_all']:7.3f} "
              f"{(dfs if dfs is not None else float('nan')):9.3f} {tb:10.1f} "
              f"{str(u.get('worst_label')):>6} {str(u.get('best_label')):>6}")

    med_a, f12_a, nf_a, ds_a = gate("delta_all")
    med_s, f12_s, nf_s, ds_s = gate("delta_feasible_strict")
    print("\n--- §1.3.2 admission (gate metric = Δ_all = t_worst/t_best over 16 configs) ---")
    print(f"  corpus median Δ_all        = {med_a:.3f}   (admission needs ≥ 1.5)")
    print(f"  fraction Δ_all ≥ 1.2       = {f12_a:.0%}     (admission needs ≥ 70%)")
    print(f"  VERDICT (Δ_all)            = {'NON-FLAT (PASS §1.3)' if nf_a else 'FLAT (FAIL §1.3)'}")
    print(f"\n  [reference] median Δ_strict = {med_s:.3f} ; fraction ≥1.2 = {f12_s:.0%} ; "
          f"{'NON-FLAT' if nf_s else 'FLAT'}")
    print(f"\n  per-unit Δ_all sorted: {sorted(round(x,3) for x in ds_a)}")
    print(f"  worst-case (min Δ_all): {min(ds_a):.3f}   best-case (max): {max(ds_a):.3f}")


if __name__ == "__main__":
    main()
