"""Step 1.2.2 TDD — median-over-N-subprocess endpoint + re-measure/discard rule.

Two layers of test:
  - PURE / FAKE-subprocess: the re-measure decision logic (robust scale, outlier
    detection, the hard re-roll cap, the `flagged` marker) is exercised deterministically
    by injecting a fake single-subprocess primitive that returns scripted per-subprocess
    medians. This is the p-hack-sensitive surface, so it gets exhaustive unit coverage.
  - INTEGRATION: measure_endpoint actually spawns N FRESH subprocesses through the real
    runtime_ns rig on the sleep_kernel fixture, proving the endpoint inherits the
    perf_counter region placement and the fresh-process discipline.

Run inside the pinned container (same invocation as test_runtime_ns.py).
"""
import statistics
from pathlib import Path

import pytest

from motifbo.timing.endpoint import (
    RemeasurePolicy, measure_endpoint, outlier_indices, robust_scale,
)

FIXTURES = Path(__file__).parent / "fixtures"
SLEEP_KERNEL = str(FIXTURES / "sleep_kernel.py")

KERNEL_S = 0.050
TOL_S = 0.025
LO_NS = int(KERNEL_S * 1e9)
HI_NS = int((KERNEL_S + TOL_S) * 1e9)
SETUP = f"import time\nargs = ({KERNEL_S},)\nkwargs = {{}}\n"


def fake_measure(median_sequence):
    """A fake runtime_ns.measure: pops the next scripted median and returns a child
    result whose samples_ns have exactly that median (constant samples -> median == value)."""
    seq = list(median_sequence)
    calls = {"n": 0}

    def _fake(*, module_path, kernel, setup_code, reps, warmup, timeout_s, cycles,
              mutated_arg_indices=None, per_rep_regen=None, preimport=None):
        if not seq:
            raise AssertionError("fake_measure called more times than scripted "
                                 "(infinite re-roll? cap not enforced)")
        v = seq.pop(0)
        calls["n"] += 1
        return {"samples_ns": [v] * reps, "reps": reps, "warmup": warmup,
                "import_ns": 0, "setup_ns": 0, "cycles": None,
                "child_pid": 100000 + calls["n"]}

    _fake.calls = calls
    return _fake


# A representative pre-registered-shaped policy for the logic tests (the ACTUAL values
# are fixed at Step 1.5.1; these only exercise the mechanism).
POL = RemeasurePolicy(threshold_x=5.0, max_remeasures=1, min_scale_rel=0.003)


# ---------- pure: robust scale + outlier detection ----------

def test_policy_has_no_defaults_so_an_unregistered_threshold_cannot_be_used():
    with pytest.raises(TypeError):
        RemeasurePolicy()                       # must force explicit pre-registered values


def test_robust_scale_floor_prevents_degenerate_mad():
    # two coincident medians -> MAD == 0; the relative floor must take over (not 0).
    s = robust_scale([100.0, 100.0, 100.3], min_scale_rel=0.003)
    assert s == pytest.approx(0.003 * 100.0)    # floor = min_scale_rel * |center|


def test_robust_scale_uses_mad_when_above_floor():
    # wide, symmetric spread -> MAD dominates the (tiny) floor.
    s = robust_scale([10.0, 20.0, 30.0], min_scale_rel=0.003)
    assert s == pytest.approx(10.0)             # median(|dev|) of {10,0,10} = 10


def test_robust_scale_not_inflated_by_a_lone_extreme():
    # The defining property of MAD (vs SD): a single far value must NOT inflate the scale.
    # center=median([100,100,100,9000])=100; median(|dev|)=median({0,0,0,8900})=0.
    s = robust_scale([100.0, 100.0, 100.0, 9000.0], min_scale_rel=0.0)
    assert s == 0.0                             # an SD impl would be ~3850 here


def test_outlier_indices_flags_one_far_subprocess():
    assert outlier_indices([100.0, 100.0, 130.0], POL) == [2]


def test_outlier_indices_quiet_on_normal_jitter():
    # ~0.2% spread, below the floored threshold -> no false flag.
    assert outlier_indices([100.0, 100.1, 100.2], POL) == []


# ---------- endpoint robustness (the structural guarantee) ----------

def test_endpoint_median_robust_to_single_outlier_without_policy():
    res = measure_endpoint(SLEEP_KERNEL, "kernel", SETUP, reps=4, n_subproc=3,
                           policy=None, _measure=fake_measure([100.0, 100.0, 900.0]))
    assert res["endpoint_ns"] == 100.0          # median ignores the lone 900
    assert res["n_subproc_final"] == 3
    assert res["remeasures"] == [] and res["flagged"] is False


def test_no_policy_is_pure_median_of_n_no_remeasure():
    fake = fake_measure([10.0, 12.0, 11.0])
    res = measure_endpoint(SLEEP_KERNEL, "kernel", SETUP, reps=4, n_subproc=3,
                           policy=None, _measure=fake)
    assert res["endpoint_ns"] == 11.0
    assert fake.calls["n"] == 3                 # exactly N, never an extra
    assert res["policy"] is None


# ---------- re-measure / discard rule ----------

def test_clean_triple_under_policy_does_not_remeasure():
    fake = fake_measure([100.0, 100.0, 100.0])
    res = measure_endpoint(SLEEP_KERNEL, "kernel", SETUP, reps=4, n_subproc=3,
                           policy=POL, _measure=fake)
    assert fake.calls["n"] == 3
    assert res["remeasures"] == [] and res["flagged"] is False


def test_outlier_triggers_one_remeasure_then_flags_if_it_persists():
    # 3rd subprocess anomalous (300); the one allowed re-measure (4th=100) does NOT
    # remove the retained 300, so after the cap the config is flagged for audit, while
    # the endpoint stays robust (median of {100,100,300,100} = 100).
    fake = fake_measure([100.0, 100.0, 300.0, 100.0])
    res = measure_endpoint(SLEEP_KERNEL, "kernel", SETUP, reps=4, n_subproc=3,
                           policy=POL, _measure=fake)
    assert fake.calls["n"] == 4                 # 3 + exactly one re-measure
    assert len(res["remeasures"]) == 1
    assert res["flagged"] is True
    assert res["endpoint_ns"] == 100.0
    assert 100000 + 4 in [s["child_pid"] for s in res["subprocesses"]]   # 4th retained
    # provenance is load-bearing for the anti-p-hack audit trail: assert it, do not just
    # produce it. The re-measure was triggered by subprocess index 2 (the 300).
    assert res["remeasures"][0]["triggered_by"] == [2]
    assert res["remeasures"][0]["median_ns"] == 100.0
    assert res["reference"]["center_ns"] == 100.0      # frozen reference is the original-N median


def test_clean_redraw_supplies_recovery_but_does_not_launder_the_anomaly():
    # Behavioral lock on the RECOVERY-WITHOUT-LAUNDERING property (the DISCRIMINATING
    # regression guard for the review MAJOR is test_two_slow... below — this scenario
    # happens to pass on the old growing-pool code too, so it pins behaviour, not the bug).
    # Original {100,100,140}: the 140 is a real anomaly. A re-measure that lands clean (100)
    # must (a) let the endpoint median RECOVER to consensus 100, and (b) NOT clear the flag —
    # the anomaly happened and stays surfaced. With a FROZEN reference a clean re-draw cannot
    # un-flag a real outlier.
    fake = fake_measure([100.0, 100.0, 140.0, 100.0])
    res = measure_endpoint(SLEEP_KERNEL, "kernel", SETUP, reps=4, n_subproc=3,
                           policy=POL, _measure=fake)
    assert res["endpoint_ns"] == 100.0          # recovered to consensus
    assert res["flagged"] is True               # but the anomaly is NOT laundered away
    assert len(res["remeasures"]) == 1
    assert res["outlier_indices"] == [2]        # the 140 is still an outlier vs the frozen ref


def test_two_slow_subprocesses_shift_the_endpoint_but_it_is_flagged_not_silent():
    # REGRESSION for the Step-1.2.2 review MAJOR finding. If the original outlier (140)
    # REPRODUCES on the re-measure (a second 140), the growing pool would, under the buggy
    # design, recompute center=120/MAD=20 and SILENTLY absorb both -> endpoint 120, unflagged.
    # With the frozen original-N reference the 120 endpoint shift is FLAGGED, never silent.
    fake = fake_measure([100.0, 100.0, 140.0, 140.0])
    res = measure_endpoint(SLEEP_KERNEL, "kernel", SETUP, reps=4, n_subproc=3,
                           policy=POL, _measure=fake)
    assert res["endpoint_ns"] == 120.0          # median([100,100,140,140]) — a real shift...
    assert res["flagged"] is True               # ...that is SURFACED, not silently absorbed
    assert res["outlier_indices"] == [2, 3]     # both 140s are outliers vs the frozen ref (100)


def test_remeasure_cap_is_hard_no_infinite_reroll():
    # A SINGLE persistent extreme (9000) stays an outlier no matter how many tight 100s
    # join the pool, so the rule would re-roll forever without the cap. With cap=2 it must
    # stop after exactly N + 2 = 5 subprocesses: fake_measure is scripted with exactly 5
    # values and RAISES on a 6th call, so an uncapped loop fails this test loudly.
    pol = RemeasurePolicy(threshold_x=5.0, max_remeasures=2, min_scale_rel=0.003)
    fake = fake_measure([100.0, 100.0, 9000.0, 100.0, 100.0])   # 3 + 2 = 5, no more
    res = measure_endpoint(SLEEP_KERNEL, "kernel", SETUP, reps=4, n_subproc=3,
                           policy=pol, _measure=fake)
    assert fake.calls["n"] == 5                 # stopped exactly at N + max_remeasures
    assert len(res["remeasures"]) == 2
    assert res["flagged"] is True
    assert res["endpoint_ns"] == 100.0          # endpoint stays robust through it all


def test_cap_zero_flags_without_any_remeasure():
    fake = fake_measure([100.0, 100.0, 300.0])
    pol = RemeasurePolicy(threshold_x=5.0, max_remeasures=0, min_scale_rel=0.003)
    res = measure_endpoint(SLEEP_KERNEL, "kernel", SETUP, reps=4, n_subproc=3,
                           policy=pol, _measure=fake)
    assert fake.calls["n"] == 3                 # flag-only, no extra subprocess
    assert res["remeasures"] == [] and res["flagged"] is True


def test_policy_provenance_recorded():
    res = measure_endpoint(SLEEP_KERNEL, "kernel", SETUP, reps=4, n_subproc=3,
                           policy=POL, _measure=fake_measure([10.0, 10.0, 10.0]))
    assert res["policy"] == {"threshold_x": 5.0, "max_remeasures": 1,
                             "min_scale_rel": 0.003}


def test_all_raw_subprocesses_retained_for_recompute():
    res = measure_endpoint(SLEEP_KERNEL, "kernel", SETUP, reps=4, n_subproc=3,
                           policy=POL, _measure=fake_measure([100.0, 100.0, 300.0, 100.0]))
    # endpoint must be recomputable from the retained raw (empirical honesty §6.1).
    recomputed = statistics.median(
        [statistics.median(s["samples_ns"]) for s in res["subprocesses"]])
    assert recomputed == res["endpoint_ns"]
    assert len(res["subprocesses"]) == res["n_subproc_final"]


# ---------- integration: real fresh subprocesses through the runtime_ns rig ----------

def test_endpoint_over_real_fresh_subprocesses():
    res = measure_endpoint(SLEEP_KERNEL, "kernel", SETUP, reps=5, n_subproc=3,
                           warmup=2, policy=None)
    assert res["n_subproc_final"] == 3
    pids = [s["child_pid"] for s in res["subprocesses"]]
    assert len(set(pids)) == 3                  # three DISTINCT fresh subprocesses
    assert LO_NS <= res["endpoint_ns"] < HI_NS  # endpoint inherits the kernel-only region
    for m in res["subproc_medians_ns"]:
        assert LO_NS <= m < HI_NS
