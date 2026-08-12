"""RUNTIME_NS endpoint layer — median-over-N-subprocess timing endpoint (Step 1.2.2).

The single-subprocess primitive is runtime_ns.measure(): ONE fresh subprocess runs
K_final reps with perf_counter_ns immediately around the kernel call (validated at
Step 0.2.2; K_final=30 is the per-subprocess rep count — never a lever, §5.1). This
module sits ABOVE it and defines the RQ1 timing ENDPOINT for one (unit, config):
the median over N (=3) FRESH subprocesses, each running its own K_final reps.

Why median-of-N (results/characterization/CF4_BASELINE.md, decided at Step 1.2.0):
short branch/pointer-heavy units (PAVA class) showed a real ~3.6% slow-outlier
population in the per-subprocess median at ~74 ms that VANISHES at ~500 ms (0/20).
The PRIMARY control is the per-unit ~480-500 ms golden (set at 1.1.5); median-of-3 is
residual insurance — a single anomalous subprocess cannot move the median (median of
{ok, ok, bad} = ok), so it cannot corrupt a config's endpoint or break the paired RQ1
comparison. The structure is UNIFORM across all units (not conditional).

Re-measure/discard rule (anti-p-hacking; PRE-REGISTERED at Step 1.5.1, PREREG_RQ1):
ALL THREE knobs — threshold_x, max_remeasures, min_scale_rel — are fixed BEFORE any RQ1
data via a RemeasurePolicy passed in here. RemeasurePolicy has NO production defaults,
so an unregistered threshold can never silently shape an endpoint. With policy=None
(characterization, e.g. Step 1.2.4) the endpoint is the pure median over N — no
re-measure, raw between-subprocess spread preserved.

The outlier test uses a FROZEN reference (center + robust scale taken from the ORIGINAL
N medians only). It is deliberately NOT recomputed on the growing pool: a re-measure
that itself lands slow would otherwise inflate the scale and launder a real anomaly away
(silent, unflagged endpoint shift — caught in the Step-1.2.2 adversarial review). With a
frozen reference `flagged` is MONOTONIC: once an original-N subprocess deviates by more
than threshold_x * robust_scale it stays surfaced; a clean re-draw can supply recovery
data and pull the endpoint median back to consensus, but it does NOT clear the flag.

The re-measure count is HARD-CAPPED (max_remeasures) — no infinite re-roll (a p-hack
vector). Raw is NEVER silently discarded: every subprocess (original and re-measured) is
retained in the returned `subprocesses` for independent recompute (§6.1).

Estimator note: under an active policy a re-measure makes the retained pool even
(e.g. 4), so statistics.median returns the mean of the two central per-subprocess
medians — a defined, robust, recomputable estimator, but not an odd true-middle value.
The exact even-pool estimator is pinned at Step 1.5.1 in PREREG_RQ1. Precondition:
subprocess medians are strictly positive (perf_counter_ns deltas), so the relative
scale floor min_scale_rel*|center| is itself positive.

This endpoint binds Step 1.2.4 / §1.5.3 / §1.5.4 identically (one rig, every timed path).
"""
import statistics
from dataclasses import dataclass

from motifbo.timing.runtime_ns import measure

N_SUBPROC = 3        # CF-4 decision: median over 3 fresh subprocesses (uniform, all units)


@dataclass(frozen=True)
class RemeasurePolicy:
    """Pre-registered (Step 1.5.1) re-measure/discard parameters. Deliberately has NO
    defaults: a real RQ1 run MUST pass the pre-registered values, so an unregistered
    threshold can never silently shape an endpoint. For characterization, pass policy=None.

    threshold_x:    a subprocess median is an outlier iff |median - center| exceeds
                    threshold_x * robust_scale(reference), where center and robust_scale
                    are taken from the ORIGINAL N medians and then FROZEN.
    max_remeasures: HARD cap on extra fresh subprocesses spawned across the whole call
                    (anti-infinite-reroll). Once reached, the call stops re-rolling.
    min_scale_rel:  relative floor on the robust scale (fraction of |center|). MAD over
                    3 points is degenerate (one deviation is exactly 0; if two medians
                    coincide MAD -> 0 and ANY third value false-flags). The floor is set
                    at 1.5.1 from the CF-4 between-subprocess noise floor (rstd ~0.2-0.4%)
                    so that normal run-to-run jitter does not flag. This is the THIRD
                    pre-registered knob (alongside threshold_x and max_remeasures) — it
                    is fixed in PREREG_RQ1, not introduced post-hoc.
    """
    threshold_x: float
    max_remeasures: int
    min_scale_rel: float


def _median(samples_ns):
    return float(statistics.median(samples_ns))


def robust_scale(medians, min_scale_rel):
    """MAD of `medians`, floored at min_scale_rel * |center| (center = their median).

    Robust (MAD, not SD — an outlier does not inflate it) with a relative floor that
    prevents the degenerate n=3 MAD (=0 when two medians coincide) from false-flagging
    on normal jitter. Presumes center > 0 (perf_counter_ns deltas are strictly positive).
    """
    center = statistics.median(medians)
    mad = statistics.median([abs(m - center) for m in medians])
    return max(mad, min_scale_rel * abs(center))


def outlier_indices(medians, policy):
    """Indices of `medians` farther than policy.threshold_x * robust_scale from the center.

    Pure helper: center and scale are computed from the `medians` passed in. measure_endpoint
    does NOT call this on the growing pool — it FREEZES the reference to the original N (see
    the module docstring) — so use this only on a fixed reference set.
    """
    center = statistics.median(medians)
    thresh = policy.threshold_x * robust_scale(medians, policy.min_scale_rel)
    return [i for i, m in enumerate(medians) if abs(m - center) > thresh]


def measure_endpoint(module_path, kernel, setup_code, reps, *, n_subproc=N_SUBPROC,
                     warmup=5, timeout_s=300.0, cycles=False, policy=None,
                     mutated_arg_indices=None, per_rep_regen=None, preimport=None,
                     _measure=measure):
    """Median-over-`n_subproc`-fresh-subprocess timing endpoint for one (unit, config).

    Each subprocess runs `reps` (=K_final) reps via the validated runtime_ns rig (fresh
    process, perf_counter_ns around the kernel call only). Returns the endpoint (median of
    the per-subprocess medians) plus full provenance: every subprocess result, its median,
    the frozen outlier reference, the final outlier indices, re-measure events, the
    `flagged` marker, and the policy used. Raw is never discarded here (§6.1 recompute).

      policy=None -> pure median over n_subproc subprocesses (characterization; no re-measure).
      policy set  -> the pre-registered (Step 1.5.1) re-measure/discard rule is active.

    n_subproc defaults to the pinned N_SUBPROC=3 and is recorded in provenance; RQ1 callsites
    MUST pass the pinned constant and the seal (stats-auditor, 1.2.4) asserts it is 3 and
    uniform across all units — only the characterization path may sweep N.

    `_measure` is the single-subprocess primitive (injectable for tests).
    """
    def one():
        return _measure(module_path=module_path, kernel=kernel, setup_code=setup_code,
                        reps=reps, warmup=warmup, timeout_s=timeout_s, cycles=cycles,
                        mutated_arg_indices=mutated_arg_indices,
                        per_rep_regen=per_rep_regen, preimport=preimport)

    subs = [one() for _ in range(n_subproc)]
    medians = [_median(s["samples_ns"]) for s in subs]

    remeasures = []
    flagged = False
    reference = None
    final_outliers = []
    if policy is not None:
        # FROZEN reference = the original N medians only. The outlier test is taken against
        # this fixed (center, scale); a later (possibly slow) re-measure can therefore never
        # inflate the scale and launder a real anomaly away (Step-1.2.2 adversarial review).
        ref = medians[:n_subproc]
        ref_center = statistics.median(ref)
        ref_scale = robust_scale(ref, policy.min_scale_rel)
        ref_thresh = policy.threshold_x * ref_scale
        reference = {"center_ns": ref_center, "scale_ns": ref_scale,
                     "threshold_ns": ref_thresh, "min_scale_rel": policy.min_scale_rel}

        def anomalies(pool):
            return [i for i, m in enumerate(pool) if abs(m - ref_center) > ref_thresh]

        orig_outliers = anomalies(medians)
        if orig_outliers:
            flagged = True       # an original-N subprocess deviated > X*scale -> SURFACE it
            # Re-measure (capped) for recovery data + reproducibility evidence. `flagged` is
            # NOT cleared by a clean re-draw — an anomaly that happened stays surfaced.
            while anomalies(medians) and len(remeasures) < policy.max_remeasures:
                extra = one()
                subs.append(extra)
                medians.append(_median(extra["samples_ns"]))
                remeasures.append({"triggered_by": orig_outliers,
                                   "median_ns": medians[-1],
                                   "child_pid": extra.get("child_pid")})
        final_outliers = anomalies(medians)
        # Asymmetry, by design: `flagged` is driven by the ORIGINAL N (an anomaly that
        # happened, surfaced and monotonic); `outlier_indices` is the anomaly set across the
        # FINAL pool (the full audit set vs the frozen reference). A relative rig has no
        # absolute ground truth, so an ALL-N-consistently-slow config (no subprocess deviates
        # from the others) cannot be flagged here — that residual is covered by the per-unit
        # ~500 ms golden + the paired RQ1 diff + CF-1, NOT by this layer (CF4_BASELINE.md).

    return {
        "endpoint_ns": _median(medians),
        "n_subproc": n_subproc,
        "n_subproc_final": len(subs),
        "subproc_medians_ns": medians,
        "reference": reference,
        "outlier_indices": final_outliers,
        "remeasures": remeasures,
        "flagged": flagged,
        "policy": (None if policy is None else
                   {"threshold_x": policy.threshold_x,
                    "max_remeasures": policy.max_remeasures,
                    "min_scale_rel": policy.min_scale_rel}),
        "subprocesses": subs,
    }
