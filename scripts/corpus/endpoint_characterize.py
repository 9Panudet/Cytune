"""Characterize an M-subprocess endpoint raw (Step 1.2.4 criterion-5 + CF-4 re-check).

Computes, from the committed raw (M fresh subprocesses x K=30 reps each), the THREE numbers
the v1.4 criterion-5 framing distinguishes (Decision B), plus the CF-4 slow-outlier metrics:

  1. WITHIN-subprocess CI@30   : per-subprocess bootstrap-free t-CI half-width of the mean /
     median; report worst + median across the M subprocesses (the kernel-intrinsic precision).
  2. WORST-of-M-raw subprocess : max one-sided slow deviation of a subprocess median from the
     robust bulk center (the outlier the median-of-N / re-measure policy DISCARDS).
  3. ENDPOINT precision        : partition the M subprocesses into independent consecutive
     median-of-3 triples, compute each endpoint, report the rstd + relative 95% CI half-width
     of those endpoints. This is the v1.4 criterion-5 GATE number (what the RQ1 search sees).
     Conservative: pure median-of-3, no re-measure (the policy only improves it).

  CF-4 outlier metrics: robust-sigma (1.4826*MAD), slow-outlier rate (one-sided z>3), max dev%.

Usage: endpoint_characterize.py <endpoint_raw.json> [label]
"""
import json
import math
import statistics
import sys

T_975_DF29 = 2.045


def within_ci(samples):
    n = len(samples); med = statistics.median(samples)
    sd = statistics.stdev(samples)
    return 100.0 * (T_975_DF29 * sd / math.sqrt(n)) / med


def main():
    raw = json.load(open(sys.argv[1]))
    label = sys.argv[2] if len(sys.argv) > 2 else raw.get("unit", "")
    subs = raw["subprocesses"]
    meds = [statistics.median([float(x) for x in s["samples_ns"]]) for s in subs]
    M = len(meds)
    center = statistics.median(meds)
    mad = statistics.median([abs(m - center) for m in meds])
    rsigma = 1.4826 * mad if mad > 0 else 0.0

    # within-subprocess CI@30
    wcis = sorted(within_ci([float(x) for x in s["samples_ns"]]) for s in subs)
    # one-sided slow outliers (z>3 above the robust center)
    z = [((m - center) / rsigma if rsigma > 0 else 0.0) for m in meds]
    slow = [i for i, zi in enumerate(z) if zi > 3.0]
    max_dev_pct = 100.0 * (max(meds) - center) / center

    # endpoint precision: independent consecutive median-of-3 triples (pure, no re-measure)
    triples = [meds[i:i + 3] for i in range(0, M - M % 3, 3)]
    endpoints = [statistics.median(t) for t in triples]
    if len(endpoints) >= 2:
        ep_center = statistics.median(endpoints)
        ep_rstd = 100.0 * statistics.pstdev(endpoints) / ep_center
        ep_ci = 100.0 * (T_975_DF29 * statistics.stdev(endpoints) /
                         math.sqrt(len(endpoints))) / ep_center
        ep_range = 100.0 * (max(endpoints) - min(endpoints)) / ep_center
    else:
        ep_rstd = ep_ci = ep_range = float("nan")

    out = {
        "label": label, "M_subprocesses": M,
        "endpoint_ns_overall": raw.get("endpoint_ns"),
        "robust_center_ns": center, "robust_sigma_pct": 100.0 * rsigma / center,
        "within_ci30_pct": {"worst": wcis[-1], "median": statistics.median(wcis),
                            "best": wcis[0]},
        "slow_outlier_rate": {"count": len(slow), "of_M": M,
                              "pct": 100.0 * len(slow) / M, "indices": slow},
        "max_slow_dev_pct": max_dev_pct,
        "endpoint_precision": {"n_triples": len(endpoints),
                               "endpoints_ns": endpoints,
                               "rstd_pct": ep_rstd, "ci95_halfwidth_pct": ep_ci,
                               "range_pct": ep_range,
                               "GATE_endpoint_le_1pct": (ep_ci <= 1.0)},
        "subproc_medians_ns": meds,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
