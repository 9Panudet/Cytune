"""TDD — v1.4 per-rep input refresh (Step 1.2.4, Decision A).

In-place kernels mutate their timed inputs, so args-built-once times a DEGENERATE path on
reps 2..K. v1.4: when the driver declares mutated_arg_indices, the child REGENERATES the
input from the committed recipe before EACH rep (warmup + timed), UNTIMED. These tests lock
(a) regen ON -> every rep sees a fresh input, (b) regen OFF (pure kernel default) -> args
reused, (c) the regen does NOT enter the timed region (timing-region law preserved). Run in
the pinned container (needs numpy + the real _child subprocess).
"""
import pathlib
import tempfile

from motifbo.timing.runtime_ns import measure

FIXTURE = str(pathlib.Path(__file__).parent / "fixtures" / "inplace_marker_kernel.py")


def _setup(trace_path):
    return (f"import numpy as np\n"
            f"arr = np.zeros(1, dtype=np.int64)\n"
            f"args = (arr, {trace_path!r})\n")


def _run(mutated_arg_indices=None, per_rep_regen=None, reps=3, warmup=1):
    with tempfile.NamedTemporaryFile(mode="r", suffix=".trace", delete=False) as tf:
        trace = tf.name
    res = measure(FIXTURE, "kernel", _setup(trace), reps=reps, warmup=warmup,
                  mutated_arg_indices=mutated_arg_indices, per_rep_regen=per_rep_regen)
    observed = [int(x) for x in pathlib.Path(trace).read_text().split()]
    pathlib.Path(trace).unlink()
    return res, observed


def test_regen_on_every_rep_sees_a_fresh_input():
    # mutated_arg_indices declared -> regen before each call -> the kernel always observes
    # arr[0]==0 (fresh). Without regen it would observe 0,1,2,... (the degenerate path).
    res, observed = _run(mutated_arg_indices=[0], reps=3, warmup=1)
    assert observed == [0, 0, 0, 0]          # 1 warmup + 3 timed, ALL fresh
    assert res["per_rep_regen"] is True
    assert res["mutated_arg_indices"] == [0]
    assert len(res["samples_ns"]) == 3


def test_regen_off_by_default_reuses_args_degenerate_path():
    # no mutated args declared -> args-once (the pure-kernel default). The fixture mutates,
    # so the trace COUNTS UP — this is exactly the degeneracy v1.4 fixes for real in-place kernels.
    res, observed = _run(mutated_arg_indices=None, reps=3, warmup=1)
    assert observed == [0, 1, 2, 3]          # accumulated state across calls
    assert res["per_rep_regen"] is False


def test_per_rep_regen_override_forces_regen_without_declaring_mutation():
    res, observed = _run(per_rep_regen=True, reps=4, warmup=0)
    assert observed == [0, 0, 0, 0]
    assert res["per_rep_regen"] is True


def test_regen_is_untimed_timing_region_is_only_the_kernel():
    # The regen (np.zeros alloc + exec) must NOT inflate the samples: a 1-element kernel that
    # only appends a line is sub-millisecond; if the regen leaked into the timed region the
    # samples would carry the exec/alloc cost. Assert all samples are tiny (< 5 ms).
    res, _ = _run(mutated_arg_indices=[0], reps=5, warmup=1)
    assert all(s < 5_000_000 for s in res["samples_ns"]), res["samples_ns"]
