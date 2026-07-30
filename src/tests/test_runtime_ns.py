"""Step 0.2.2 TDD — timing-region placement tests for the RUNTIME_NS harness.

Calibration (fixtures): import sleeps 100 ms, input construction (setup) sleeps
200 ms, kernel sleeps KERNEL_S = 50 ms. A correctly-placed region measures the
kernel only: every sample in [KERNEL_S, KERNEL_S + TOL). TOL = 25 ms — generous for
scheduler noise, 4x below the smallest contamination (setup 200 ms).
Run inside the pinned container (see logs/env/STEP_0.2.2_runtime_ns.log).
"""
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

import pytest

from motifbo.timing.runtime_ns import measure

FIXTURES = Path(__file__).parent / "fixtures"
SLEEP_KERNEL = str(FIXTURES / "sleep_kernel.py")

KERNEL_S = 0.050
TOL_S = 0.025
LO_NS = int(KERNEL_S * 1e9)              # sleep() guarantees >= duration
HI_NS = int((KERNEL_S + TOL_S) * 1e9)

SETUP = (
    "import time\n"
    "time.sleep(0.200)\n"                # expensive input construction — never timed
    f"args = ({KERNEL_S},)\n"
    "kwargs = {}\n"
)


def run_measure(reps=5, warmup=2, setup=SETUP, kernel="kernel"):
    return measure(module_path=SLEEP_KERNEL, kernel=kernel, setup_code=setup,
                   reps=reps, warmup=warmup)


def test_measured_matches_slept_within_tolerance():
    res = run_measure()
    assert len(res["samples_ns"]) == 5
    for s in res["samples_ns"]:
        assert LO_NS <= s < HI_NS, f"sample {s}ns outside [{LO_NS},{HI_NS})"
    assert LO_NS <= statistics.median(res["samples_ns"]) < HI_NS


def test_import_and_setup_recorded_but_not_timed():
    res = run_measure()
    assert res["import_ns"] >= int(0.100 * 1e9)   # slow import happened...
    assert res["setup_ns"] >= int(0.200 * 1e9)    # ...and slow setup happened...
    for s in res["samples_ns"]:                   # ...neither leaked into samples
        assert s < HI_NS


def test_fresh_subprocess_per_measure():
    a, b = run_measure(reps=1, warmup=0), run_measure(reps=1, warmup=0)
    assert a["child_pid"] != b["child_pid"]
    assert a["child_pid"] != os.getpid() and b["child_pid"] != os.getpid()


def test_warmup_calls_executed_and_excluded(tmp_path):
    count_file = tmp_path / "calls.txt"
    setup = (
        "import time\n"
        f"args = ({KERNEL_S},)\n"
        f"kwargs = {{'count_file': {str(count_file)!r}}}\n"
    )
    res = run_measure(reps=3, warmup=4, setup=setup)
    assert len(res["samples_ns"]) == 3            # warmup reps not reported
    calls = count_file.read_text().count("x")
    assert calls == 7                             # ...but actually executed (4+3)


def test_misplaced_timing_region_is_detected(tmp_path):
    """The deliberately-bad child must VIOLATE the placement bound (§6.3 sensitivity)."""
    spec = {"module_path": SLEEP_KERNEL, "kernel": "kernel", "setup_code": SETUP,
            "reps": 3, "out": str(tmp_path / "out.json")}
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec))
    subprocess.run([sys.executable, str(FIXTURES / "bad_child_misplaced.py"),
                    str(spec_path)], check=True, timeout=120)
    bad = json.loads((tmp_path / "out.json").read_text())
    bad_median = statistics.median(bad["samples_ns"])
    assert bad_median >= HI_NS, (
        "placement bound failed to detect a mis-placed timing region — "
        "the placement tests are vacuous")


def test_child_failure_raises_not_silent():
    with pytest.raises(RuntimeError):
        run_measure(kernel="no_such_kernel")
