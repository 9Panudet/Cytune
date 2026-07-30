"""Gate I-1 evaluation (Step 0.5.3, roadmap §0.3 / PREREG_I1.md).

Known-good must beat known-bad on the real hot-loop workload by:
  - raw-pointer path (csr_scale): speedup >= 1.15x
  - numeric-loop path (pava):     speedup >= 1.50x
where speedup = median(known-bad samples_ns) / median(known-good samples_ns)
(median over the K_final reps; median-of-medians degenerates to the single-instance
median, §0.3). Pure functions — the orchestrator computes the 0.5.3 decision with
these; stats-auditor recomputes independently from the raw at preflight (zero diff).
"""
import statistics

THRESHOLDS = {"raw-pointer": 1.15, "numeric-loop": 1.50}


def speedup(good_samples_ns, bad_samples_ns):
    """median(bad)/median(good) — >1 means known-good is faster (the desired sign)."""
    g = statistics.median(good_samples_ns)
    b = statistics.median(bad_samples_ns)
    if g <= 0:
        raise ValueError(f"median(good) must be > 0, got {g}")
    return b / g


def gate_pass(ratio, threshold):
    return ratio >= threshold


def evaluate(kernel_records):
    """kernel_records: {kernel: {path_class, good: [ns...], bad: [ns...]}}.
    Returns per-kernel ratios/verdicts and the overall I-1 pass (all kernels)."""
    per_kernel, overall = {}, True
    for kernel, rec in kernel_records.items():
        threshold = THRESHOLDS[rec["path_class"]]
        ratio = speedup(rec["good"], rec["bad"])
        passed = gate_pass(ratio, threshold)
        overall = overall and passed
        per_kernel[kernel] = {
            "path_class": rec["path_class"],
            "median_good_ns": statistics.median(rec["good"]),
            "median_bad_ns": statistics.median(rec["bad"]),
            "speedup": ratio, "threshold": threshold, "pass": passed,
        }
    return {"per_kernel": per_kernel, "i1_pass": overall}
