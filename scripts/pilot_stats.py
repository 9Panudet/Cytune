"""Step 0.2.4 pilot statistics (runs IN the pinned container; deterministic).

Reads the committed raw pilot files + the pilot thermal CSV; produces
results/pilot/PILOT_REPORT.md + data/env/MEASUREMENT_CONSTANTS.json.
Every number in the report carries its raw-file pointer; stats-auditor recomputes
independently at preflight (required diff: zero).

Bootstrap: B=10,000 resamples (Tier 3 default, §5.2), numpy default_rng(0xC0FFEE).
For each candidate K: resample K samples with replacement from the 30 pilot samples,
take the median, repeat B times; CI = [2.5, 97.5] percentiles; half-width = (hi-lo)/2.
Validation target (§5.1): half-width <= 1% of the full-sample median at K_final=30.

Usage: pilot_stats.py <raw_dir> <thermal_csv> <report_out> <constants_out>
"""
import json
import sys
from pathlib import Path

import numpy as np

B = 10_000
BOOT_SEED = 0xC0FFEE
K_GRID = [5, 10, 15, 20, 25, 30]
K_FINAL = 30                       # §5.1: fixed, never adaptive — validated here
EXPECTED_GHZ = 3.6                 # held base clock (Step 0.2.1; nominal)
THERMAL_MARGIN_C = 10              # threshold = pilot max + margin (rationale: report)


def bootstrap_halfwidth(samples, k, rng):
    res = rng.choice(samples, size=(B, k), replace=True)
    med = np.median(res, axis=1)
    lo, hi = np.percentile(med, [2.5, 97.5])
    return (hi - lo) / 2.0


def main(raw_dir, thermal_csv, report_out, constants_out):
    sys.path.insert(0, "/src")
    from motifbo.timing.divergence import build_divergence_report

    raws = {p.stem.rsplit("_K", 1)[0]: json.loads(p.read_text())
            for p in sorted(Path(raw_dir).glob("*_K30.json"))}
    rng = np.random.default_rng(BOOT_SEED)

    kstats = {}
    for name, rec in raws.items():
        s = np.asarray(rec["result"]["samples_ns"], dtype=float)
        med = float(np.median(s))
        q25, q75 = np.percentile(s, [25, 75])
        mad = float(np.median(np.abs(s - med)))
        boots = {k: float(bootstrap_halfwidth(s, k, rng)) for k in K_GRID}
        ks_ok = [k for k in K_GRID if boots[k] / med <= 0.01]
        div = build_divergence_report(rec["result"]["samples_ns"],
                                      rec["result"]["cycles"], EXPECTED_GHZ)
        kstats[name] = {
            "n": len(s), "median_ns": med, "iqr_ns": float(q75 - q25),
            "mad_ns": mad, "iqr_rel": float((q75 - q25) / med),
            "boot_halfwidth_ns": boots,
            "boot_halfwidth_rel": {k: boots[k] / med for k in K_GRID},
            "k30_target_met": boots[30] / med <= 0.01,
            "smallest_k_meeting_target": ks_ok[0] if ks_ok else None,
            "divergence": {kk: div[kk] for kk in
                           ("median_eff_ghz", "rel_dev", "divergent")},
            "raw_file": f"results/pilot/{Path(raw_dir).name}/{name}_K30.json",
        }

    # thermal: pilot window maxima + throttle delta (CSV columns per thermal_log.sh).
    # Basis = "Core 3" channel when present, else package temperature (D4: the
    # channel can be absent on boots where cpu7 was ever offlined; package temp is
    # the die-level signal containing core 3 — recorded deviation).
    rows = [ln.split(",") for ln in
            Path(thermal_csv).read_text().strip().splitlines()[1:]]
    pkg = [int(r[2]) for r in rows]
    core3 = [int(r[6]) for r in rows if r[6] != "NA"]
    throttle = [int(r[7]) for r in rows if r[7] != "NA"]
    basis = "core3" if core3 else "package"
    basis_vals = core3 if core3 else pkg
    thermal = {
        "samples": len(rows), "max_pkg_mC": max(pkg),
        "max_core3_mC": max(core3) if core3 else None,
        "basis": basis,
        "throttle_delta": throttle[-1] - throttle[0],
        "csv": str(thermal_csv),
        "discard_threshold_mC": (max(basis_vals) // 1000 + THERMAL_MARGIN_C) * 1000,
    }

    all_met = all(v["k30_target_met"] for v in kstats.values())
    constants = {
        "schema": "motifbo-measurement-constants-v1",
        "set_at_step": "0.2.4",
        "K_final": K_FINAL,
        "K_final_validated": all_met,
        "K_pilot": 30, "warmup": 5,
        "K_search_range": [5, 10],            # §1.5 item 4 (recorded for reference)
        "thermal_discard_mC": thermal["discard_threshold_mC"],
        "thermal_basis": thermal["basis"],
        "throttle_discard_rule": "any rep window with throttle_delta > 0 is discarded",
        "divergence_rel_threshold": 0.05,
        "expected_ghz": EXPECTED_GHZ,
        "bootstrap": {"B": B, "seed": BOOT_SEED, "ci": [2.5, 97.5]},
    }

    lines = ["# PILOT_REPORT — Step 0.2.4 (K_pilot=30, both reference kernels)", "",
             f"Recompute: `python scripts/pilot_stats.py "
             f"results/pilot/{Path(raw_dir).name} {thermal_csv} <report> "
             f"<constants>` (in-container; B={B}, seed={BOOT_SEED:#x}).", ""]
    for name, v in kstats.items():
        lines += [f"## {name}  (raw: {v['raw_file']})",
                  f"- n={v['n']}; median={v['median_ns']/1e6:.3f} ms; "
                  f"IQR={v['iqr_ns']/1e6:.3f} ms ({v['iqr_rel']*100:.2f}% of median); "
                  f"MAD={v['mad_ns']/1e6:.3f} ms",
                  f"- bootstrap 95% CI half-width of median, relative: " +
                  ", ".join(f"K={k}: {v['boot_halfwidth_rel'][k]*100:.3f}%"
                            for k in K_GRID),
                  f"- K_final=30 target (<=1%): "
                  f"{'MET' if v['k30_target_met'] else 'NOT MET'}; "
                  f"smallest K meeting target: {v['smallest_k_meeting_target']}",
                  f"- cycles cross-check: median_eff_ghz="
                  f"{v['divergence']['median_eff_ghz']:.4f}, "
                  f"rel_dev={v['divergence']['rel_dev']*100:.2f}%, "
                  f"divergent={v['divergence']['divergent']}", ""]
    core3_txt = (f"{thermal['max_core3_mC']/1000:.0f}C"
                 if thermal["max_core3_mC"] is not None else "NA (D4)")
    lines += ["## Thermal (pilot window)",
              f"- samples={thermal['samples']} (1 s cadence); basis={thermal['basis']}; "
              f"max core3={core3_txt}; "
              f"max pkg={thermal['max_pkg_mC']/1000:.0f}C; "
              f"throttle_delta={thermal['throttle_delta']} (csv: {thermal['csv']})",
              f"- discard threshold = max({thermal['basis']}) + {THERMAL_MARGIN_C}C = "
              f"{thermal['discard_threshold_mC']/1000:.0f}C (>=10C above pilot "
              f"steady-state indicates abnormal thermal contamination; far below "
              f"Tjmax=100C). Independent rule: throttle_delta > 0 -> discard.", "",
              f"## Constants -> data/env/MEASUREMENT_CONSTANTS.json",
              f"- K_final=30 {'VALIDATED' if all_met else 'NOT VALIDATED — RED GATE'}"]

    Path(report_out).write_text("\n".join(lines) + "\n")
    Path(constants_out).write_text(json.dumps(constants, indent=1) + "\n")
    print("\n".join(lines[-12:]))
    if not all_met:
        sys.exit(1)


if __name__ == "__main__":
    main(*sys.argv[1:5])
