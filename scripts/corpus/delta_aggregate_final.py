"""Step-1.3 FINAL Δ aggregate — best-available rig per unit (the A/B/C decision artifact).

For each of the 9 surviving modules, uses the ENDPOINT measurement (<unit>__endpoint.json, the
v1.4 median-of-3-subprocess production rig) where it exists, else the SCREEN measurement
(<unit>.json, in-process median). Reports per-unit Δ WITH its rig provenance, then the §1.3.2
admission verdict on BOTH axes:
  - Δ_all     = t_worst/t_best over all 16 configs (includes the unsafe -ffast-math FP=A poles)
  - Δ_strict  = t_worst/t_best over the 8 FP=T bit-preserving configs (the verified-correctness axis)
Admission (frozen §1.3.2): NON-FLAT iff median Δ ≥ 1.5 AND ≥70% of units Δ ≥ 1.2.

Worst-case + raw pointers; recomputed from the committed raw JSONs (no hand-entered numbers).
Usage: delta_aggregate_final.py [dir=results/characterization/delta_probe]
"""
import glob
import json
import os
import statistics
import sys


def load_best(d):
    """Return {unit_key: (record, rig)} preferring endpoint over screen."""
    best = {}
    for path in sorted(glob.glob(os.path.join(d, "*.json"))):
        base = os.path.basename(path)
        endpoint = base.endswith("__endpoint.json")
        key = base[:-len("__endpoint.json")] if endpoint else base[:-len(".json")]
        with open(path) as fh:
            j = json.load(fh)
        if j.get("delta_all") is None:
            continue
        rig = "endpoint" if endpoint else "screen"
        # endpoint wins if present
        if key not in best or rig == "endpoint":
            best[key] = (j, rig)
    return best


def gate(ds):
    med = statistics.median(ds)
    frac12 = sum(x >= 1.2 for x in ds) / len(ds)
    return med, frac12, (med >= 1.5 and frac12 >= 0.70)


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "results/characterization/delta_probe"
    best = load_best(d)
    units = sorted(best.values(), key=lambda x: -x[0]["delta_all"])

    print(f"Step-1.3 FINAL Δ aggregate — {len(units)} surviving modules (best-available rig)\n")
    hdr = f"{'module':22} {'archetype':24} {'rig':9} {'Δ_all':>7} {'Δ_strict':>9} {'t_best_ms':>10}"
    print(hdr); print("-" * len(hdr))
    for j, rig in units:
        tb = (j["t_best_ns"] or 0) / 1e6
        dfs = j.get("delta_feasible_strict")
        print(f"{j['module']:22} {str(j.get('archetype')):24} {rig:9} {j['delta_all']:7.3f} "
              f"{(dfs if dfs is not None else float('nan')):9.3f} {tb:10.1f}")

    da = [j["delta_all"] for j, _ in units]
    ds = [j["delta_feasible_strict"] for j, _ in units if j.get("delta_feasible_strict") is not None]
    n_ep = sum(1 for _, rig in units if rig == "endpoint")
    med_a, f12_a, nf_a = gate(da)
    med_s, f12_s, nf_s = gate(ds)

    print(f"\n  rig provenance: {n_ep}/{len(units)} endpoint, {len(units)-n_ep}/{len(units)} screen")
    print("\n--- §1.3.2 admission verdict ---")
    print(f"  Δ_all  (incl. unsafe fast-math): median {med_a:.3f}  | ≥1.2: {f12_a:.0%}  "
          f"-> {'NON-FLAT (PASS)' if nf_a else 'FLAT (FAIL)'}")
    print(f"  Δ_strict (bit-preserving, FP=T): median {med_s:.3f}  | ≥1.2: {f12_s:.0%}  "
          f"-> {'NON-FLAT (PASS)' if nf_s else 'FLAT (FAIL)'}")
    print(f"\n  Δ_all sorted   : {sorted(round(x,3) for x in da)}  (worst {min(da):.3f})")
    print(f"  Δ_strict sorted: {sorted(round(x,3) for x in ds)}  (worst {min(ds):.3f})")
    hi = [j['module'] for j, _ in units if j['delta_feasible_strict'] is not None
          and j['delta_feasible_strict'] >= 1.5]
    print(f"\n  bit-preserving HIGH-Δ subclass (Δ_strict ≥ 1.5): {hi}  ({len(hi)}/{len(units)})")


if __name__ == "__main__":
    main()
