"""Recompute the within-subprocess CI@30 (G4 / criterion-5, Step 1.2.4) from a committed
endpoint raw JSON. Pure arithmetic on the raw samples_ns — the auditable mechanism so the
gate number is never hand-entered (stats-auditor re-runs the equivalent at preflight).

CI@30 = relative 95% CI half-width of the per-subprocess mean:
    halfwidth = t(.975, df=29) * s / sqrt(n),  s = sample stddev (ddof=1), n = reps (=30)
    ci_rel_pct = 100 * halfwidth / median        (median as the location, per §5.1 endpoint)
t(.975, 29) = 2.045 (K_final=30 is fixed, so df is fixed; the constant is pinned, not fit).
The G4 gate is the WORST ci_rel_pct across the N subprocesses <= 1%.

Usage: ci_from_endpoint.py <endpoint_raw.json>
"""
import json
import math
import statistics
import sys

T_975_DF29 = 2.045


def main():
    with open(sys.argv[1]) as fh:
        raw = json.load(fh)
    rows = []
    for i, sub in enumerate(raw["subprocesses"]):
        s = [float(x) for x in sub["samples_ns"]]
        n = len(s)
        mean = statistics.fmean(s)
        sd = statistics.stdev(s)
        med = statistics.median(s)
        q = statistics.quantiles(s, n=4, method="inclusive")
        iqr = q[2] - q[0]
        mad = statistics.median([abs(x - med) for x in s])
        half = T_975_DF29 * sd / math.sqrt(n)
        rows.append({"subproc": i, "n": n, "mean_ns": mean, "median_ns": med,
                     "stddev_ns": sd, "iqr_ns": iqr, "mad_ns": mad,
                     "ci95_halfwidth_ns": half,
                     "ci_rel_pct": 100.0 * half / med})
    worst = max(r["ci_rel_pct"] for r in rows)
    meds = raw["subproc_medians_ns"]
    bc = statistics.median(meds)
    between_rstd_pct = 100.0 * statistics.pstdev(meds) / bc
    out = {"unit": raw.get("unit"), "scale": raw.get("scale"),
           "endpoint_ns": raw["endpoint_ns"],
           "per_subprocess": rows,
           "worst_ci_rel_pct": worst,
           "G4_pass_ci30_le_1pct": worst <= 1.0,
           "between_subproc_rstd_pct": between_rstd_pct,
           "subproc_medians_ns": meds,
           "t_975_df29": T_975_DF29}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
