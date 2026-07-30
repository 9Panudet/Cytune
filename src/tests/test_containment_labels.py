"""Step 0.4.3 — containment label-classification tests (pure logic, §3.5).

The podman-backed OOM/timeout/segfault fixtures run on the host (no nested podman
in this test container); see scripts/containment_smoke.py + results/containment/.
These tests pin the pure §3.5 mapping that those fixtures depend on, so the mapping
cannot silently drift (e.g. a segfault being labeled ok).
"""
import signal

from motifbo.containment.wrapper import (
    COMPILE_TIMEOUT_S,
    DEFAULT_MEMORY_MB,
    DEFAULT_SANDBOX_MB,
    classify,
    run_timeout_s,
)


def test_clean_exit_is_ok():
    assert classify(0, False, False) == "ok"


def test_timeout_dominates_everything():
    assert classify(0, True, False) == "timeout"
    assert classify(137, True, True) == "timeout"
    assert classify(None, True, False) == "timeout"


def test_oom_flag_and_sigkill_fallback_both_map_to_memory_cap_kill():
    assert classify(137, False, True) == "memory_cap_kill"          # inspect flag
    assert classify(137, False, False) == "memory_cap_kill"         # 128+SIGKILL
    assert classify(-int(signal.SIGKILL), False, False) == "memory_cap_kill"  # Popen -9


def test_crash_signals_map_to_crash():
    for sig in (signal.SIGSEGV, signal.SIGABRT, signal.SIGBUS, signal.SIGFPE,
                signal.SIGILL):
        assert classify(128 + int(sig), False, False) == "crash", sig
        assert classify(-int(sig), False, False) == "crash", sig


def test_plain_nonzero_is_nonzero_exit_not_crash():
    # a compile error / sys.exit(3) must NOT be misread as a crash
    assert classify(1, False, False) == "nonzero_exit"
    assert classify(3, False, False) == "nonzero_exit"
    assert classify(127, False, False) == "nonzero_exit"


def test_run_timeout_rule_is_max_10x_or_5s():
    assert run_timeout_s(0.0) == 5.0
    assert run_timeout_s(0.1) == 5.0          # 10*0.1=1.0 < floor
    assert run_timeout_s(2.0) == 20.0         # 10*2.0 > floor
    assert run_timeout_s(0.5) == 5.0          # exactly at floor


def test_section_3_4_constants():
    assert COMPILE_TIMEOUT_S == 120.0
    assert DEFAULT_MEMORY_MB == 4096
    assert DEFAULT_SANDBOX_MB == 2048
