"""Step 0.2.3 TDD — per-rep CPU-cycle cross-check + divergence report (§5.1).

Cycle tests REQUIRE perf access: run in the pinned container with the committed
profile data/env/seccomp-perf-events.json (see logs/env/STEP_0.2.3_perf_feasibility.log).
Counting events are user-space only (exclude_kernel=1 — mandatory at paranoid=2).
"""
import statistics
from pathlib import Path

import pytest

from motifbo.timing.divergence import (DEFAULT_REL_THRESHOLD, SCHEMA,
                                       build_divergence_report,
                                       should_sample_cycles)
from motifbo.timing.runtime_ns import measure

FIXTURES = Path(__file__).parent / "fixtures"
BUSY = str(FIXTURES / "busy_kernel.py")
SLEEP = str(FIXTURES / "sleep_kernel.py")
SETUP = "args = (0.050,)\nkwargs = {}\n"


def run(module, cycles, reps=3):
    return measure(module_path=module, kernel="kernel", setup_code=SETUP,
                   reps=reps, warmup=1, cycles=cycles)


# ---- cycles collection -------------------------------------------------------

def test_cycles_collected_when_requested():
    res = run(BUSY, cycles=True)
    assert isinstance(res["cycles"], list) and len(res["cycles"]) == 3
    assert all(c > 0 for c in res["cycles"])
    assert len(res["samples_ns"]) == 3          # wall-clock still produced


def test_cycles_absent_by_default():
    res = run(BUSY, cycles=False)
    assert res["cycles"] is None


def test_busy_effective_frequency_sane():
    res = run(BUSY, cycles=True)
    for c, w in zip(res["cycles"], res["samples_ns"]):
        assert 0.5 <= c / w <= 6.0, f"effective {c / w:.2f} GHz implausible"


def test_sleep_burns_far_fewer_cycles_than_busy():
    sleep_setup = "args = (0.050,)\nkwargs = {}\n"
    busy = statistics.median(run(BUSY, cycles=True)["cycles"])
    slp = statistics.median(measure(module_path=SLEEP, kernel="kernel",
                                    setup_code=sleep_setup, reps=3, warmup=1,
                                    cycles=True)["cycles"])
    assert slp < 0.2 * busy, f"sleep {slp} vs busy {busy}: counter not discriminating"


# ---- divergence report (pure logic) -----------------------------------------

def test_divergence_report_clean_case():
    rep = build_divergence_report(samples_ns=[1_000_000] * 5,
                                  cycles=[3_600_000] * 5, expected_ghz=3.6)
    assert rep["schema"] == SCHEMA
    assert rep["median_eff_ghz"] == pytest.approx(3.6)
    assert rep["rel_dev"] == pytest.approx(0.0)
    assert rep["divergent"] is False
    assert rep["rel_threshold"] == DEFAULT_REL_THRESHOLD
    assert len(rep["per_rep"]) == 5
    assert rep["per_rep"][0] == {"rep": 0, "wall_ns": 1_000_000,
                                 "cycles": 3_600_000,
                                 "eff_ghz": pytest.approx(3.6)}


def test_divergence_report_flags_deviation():
    rep = build_divergence_report(samples_ns=[1_000_000] * 5,
                                  cycles=[3_000_000] * 5, expected_ghz=3.6)
    assert rep["rel_dev"] == pytest.approx((3.6 - 3.0) / 3.6)
    assert rep["divergent"] is True


def test_divergence_report_rejects_bad_input():
    with pytest.raises(ValueError):
        build_divergence_report([], [], 3.6)                      # empty
    with pytest.raises(ValueError):
        build_divergence_report([1, 2], [1], 3.6)                 # length mismatch
    with pytest.raises(ValueError):
        build_divergence_report([0], [100], 3.6)                  # zero wall
    with pytest.raises(ValueError):
        build_divergence_report([1_000_000], [3_600_000], 0.0)    # bad expected


# ---- deterministic 10% subsample selector ------------------------------------

def test_subsample_selector_deterministic_ten_percent():
    chosen = [i for i in range(100) if should_sample_cycles(i)]
    assert chosen == list(range(0, 100, 10))      # exactly 10%, stable, index 0 in
    assert [i for i in range(100) if should_sample_cycles(i)] == chosen
