"""Cycle/wall-clock divergence report + deterministic subsample selector (Step 0.2.3).

§5.1: perf cycle counts are collected alongside wall-clock on a 10% subsample as a
cross-check; measurement-auditor reviews divergences. With frequency held (Step
0.2.1), user-space cycles ~ wall time x frequency: per-rep effective GHz =
cycles / wall_ns. The report compares the median effective frequency against the
held frequency (caller supplies it, e.g. from /logs/governor/invocations.log).
"""
import statistics

SCHEMA = "motifbo-divergence-v1"
# Recorded constant. Revision (e.g. after the 0.2.4 pilot) is a pinned-constant
# change: pre-registered, never silent.
DEFAULT_REL_THRESHOLD = 0.05
SUBSAMPLE_EVERY = 10                  # 10% subsample (§5.1)


def should_sample_cycles(eval_index, every=SUBSAMPLE_EVERY):
    """Deterministic 10% selector: evaluation indices 0, every, 2*every, ..."""
    return eval_index % every == 0


def build_divergence_report(samples_ns, cycles, expected_ghz,
                            rel_threshold=DEFAULT_REL_THRESHOLD):
    """Per-measurement cross-check record (schema motifbo-divergence-v1)."""
    if not samples_ns or not cycles:
        raise ValueError("empty samples/cycles")
    if len(samples_ns) != len(cycles):
        raise ValueError(f"length mismatch: {len(samples_ns)} wall vs {len(cycles)} cycles")
    if any(w <= 0 for w in samples_ns):
        raise ValueError("non-positive wall sample")
    if any(c < 0 for c in cycles):
        raise ValueError("negative cycle count")
    if expected_ghz <= 0:
        raise ValueError(f"expected_ghz must be > 0, got {expected_ghz}")

    per_rep = [{"rep": i, "wall_ns": w, "cycles": c, "eff_ghz": c / w}
               for i, (w, c) in enumerate(zip(samples_ns, cycles))]
    median_eff = statistics.median(r["eff_ghz"] for r in per_rep)
    rel_dev = abs(median_eff - expected_ghz) / expected_ghz
    return {
        "schema": SCHEMA,
        "expected_ghz": expected_ghz,
        "rel_threshold": rel_threshold,
        "n_reps": len(per_rep),
        "per_rep": per_rep,
        "median_eff_ghz": median_eff,
        "rel_dev": rel_dev,
        "divergent": rel_dev > rel_threshold,
    }
