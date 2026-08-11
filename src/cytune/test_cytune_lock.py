"""B3 — the machine-level measurement lock.

The tests that matter here are the two-PROCESS ones. A lock that works within one process is not a
lock; the failure mode it exists to close is two `cytune tune` invocations in two terminals, which
is the ordinary shape of multi-project work and produces wrong numbers with no warning.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time

import pytest

from cytune import lock

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, ".."))


def _child(body, lock_file, timeout=30):
    """Run `body` in a fresh interpreter so the flock comes from a different process."""
    code = textwrap.dedent(f"""
        import json, sys, time
        sys.path.insert(0, {SRC!r})
        from cytune import lock
        LOCK = {lock_file!r}
        {textwrap.indent(textwrap.dedent(body), '        ').strip()}
    """)
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          timeout=timeout)


@pytest.fixture()
def lockfile(tmp_path):
    return str(tmp_path / "measure.lock")


# --------------------------------------------------------------------------------- the real thing
def test_a_second_process_cannot_measure_while_the_first_holds_the_lock(lockfile):
    """THE test. Two processes, one lock, and the second must not proceed."""
    holder = subprocess.Popen(
        [sys.executable, "-c", textwrap.dedent(f"""
            import sys, time
            sys.path.insert(0, {SRC!r})
            from cytune import lock
            lk = lock.MeasurementLock(workspace="/w/first", rig_mode="quiesced",
                                      path={lockfile!r})
            lk.acquire()
            print("HELD", flush=True)
            time.sleep(30)
        """)], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "HELD"
        r = _child("""
            lk = lock.MeasurementLock(workspace="/w/second", path=LOCK)
            try:
                lk.acquire()
                print("ACQUIRED")
            except lock.Busy as e:
                print("BUSY " + json.dumps(e.holder))
        """, lockfile)
        assert r.stdout.startswith("BUSY "), (
            f"the second process was allowed to measure: {r.stdout!r} {r.stderr[-500:]!r}")
        held = json.loads(r.stdout[len("BUSY "):])
        assert held["workspace"] == "/w/first"
        assert held["pid"] == holder.pid
        assert held["rig_mode"] == "quiesced"
    finally:
        holder.kill()
        holder.wait()


def test_the_lock_is_released_when_the_holder_is_killed(lockfile):
    """`flock` is kernel-held, so `kill -9` releases it. No PID file has this property, and it is
    why the staleness timeout only has to cover a wedged-but-ALIVE holder."""
    holder = subprocess.Popen(
        [sys.executable, "-c", textwrap.dedent(f"""
            import sys, time
            sys.path.insert(0, {SRC!r})
            from cytune import lock
            lock.MeasurementLock(path={lockfile!r}).acquire()
            print("HELD", flush=True)
            time.sleep(30)
        """)], stdout=subprocess.PIPE, text=True)
    assert holder.stdout.readline().strip() == "HELD"
    holder.kill()
    holder.wait()
    r = _child("""
        lk = lock.MeasurementLock(path=LOCK)
        lk.acquire()
        print("ACQUIRED")
    """, lockfile)
    assert "ACQUIRED" in r.stdout, r.stderr[-500:]


def test_wait_queues_instead_of_refusing(lockfile):
    """--wait must actually queue and then proceed, not spin forever or give up."""
    holder = subprocess.Popen(
        [sys.executable, "-c", textwrap.dedent(f"""
            import sys, time
            sys.path.insert(0, {SRC!r})
            from cytune import lock
            lk = lock.MeasurementLock(path={lockfile!r}).acquire()
            print("HELD", flush=True)
            time.sleep(2.0)
            lk.release()
            time.sleep(10)
        """)], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "HELD"
        t0 = time.time()
        r = _child("""
            lk = lock.MeasurementLock(path=LOCK)
            lk.acquire(wait=True, poll_s=0.2)
            print("ACQUIRED after wait")
        """, lockfile)
        assert "ACQUIRED after wait" in r.stdout, r.stderr[-500:]
        assert time.time() - t0 > 1.0, "it did not actually wait for the holder"
    finally:
        holder.kill()
        holder.wait()


def test_wait_gives_up_at_its_timeout_rather_than_hanging(lockfile):
    holder = subprocess.Popen(
        [sys.executable, "-c", textwrap.dedent(f"""
            import sys, time
            sys.path.insert(0, {SRC!r})
            from cytune import lock
            lock.MeasurementLock(path={lockfile!r}).acquire()
            print("HELD", flush=True)
            time.sleep(30)
        """)], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "HELD"
        r = _child("""
            lk = lock.MeasurementLock(path=LOCK)
            try:
                lk.acquire(wait=True, poll_s=0.1, timeout_s=1.0)
                print("ACQUIRED")
            except lock.Busy:
                print("GAVE UP")
        """, lockfile)
        assert "GAVE UP" in r.stdout, r.stderr[-500:]
    finally:
        holder.kill()
        holder.wait()


# ---------------------------------------------------------------------------------- the mechanism
def test_the_holder_is_identified_by_pid_and_start_time_not_by_command_line(lockfile):
    """D19 was a busy predicate that matched its own caller's command line. The payload carries
    (pid, /proc start time) instead, which is PID-reuse-proof and matches nothing by name."""
    lk = lock.MeasurementLock(workspace="/w", path=lockfile).acquire()
    try:
        h = lock.read_holder(lockfile)
        assert h["pid"] == os.getpid()
        assert h["starttime"] == lock._starttime(os.getpid())
        assert lock._alive(h["pid"], h["starttime"]) is True
        assert lock._alive(h["pid"], "999999999") is False, "a reused PID must not read as alive"
    finally:
        lk.release()


def test_the_refusal_message_names_the_holder_and_the_remedy(lockfile):
    lk = lock.MeasurementLock(workspace="/w/mine", rig_mode="quiesced", path=lockfile).acquire()
    try:
        msg = lock.describe(lock.read_holder(lockfile), lockfile)
        assert "/w/mine" in msg and str(os.getpid()) in msg
        assert "--wait" in msg
        assert "626" in msg, "the message must say WHY, with the evidence"
    finally:
        lk.release()


def test_a_stale_heartbeat_is_reported_but_never_silently_stolen(lockfile):
    lk = lock.MeasurementLock(workspace="/w", path=lockfile).acquire()
    try:
        h = dict(lock.read_holder(lockfile))
        h["heartbeat_epoch"] = time.time() - (lock.STALE_S + 60)
        with open(lockfile, "w") as f:
            f.write(json.dumps(h))
        msg = lock.describe(h, lockfile)
        assert "may be wedged" in msg
        assert "still holds the lock" in msg, "a stale heartbeat must not read as a free lock"
    finally:
        lk.release()


def test_the_heartbeat_advances_with_the_phase(lockfile):
    lk = lock.MeasurementLock(path=lockfile).acquire()
    try:
        first = lock.read_holder(lockfile)
        time.sleep(0.01)
        lk.heartbeat("endpoint")
        second = lock.read_holder(lockfile)
        assert second["phase"] == "endpoint"
        assert second["heartbeat_epoch"] > first["heartbeat_epoch"]
        assert second["acquired_epoch"] == first["acquired_epoch"], (
            "the heartbeat must not reset the acquisition time — the refusal message reports how "
            "long the holder has been running")
    finally:
        lk.release()


# ------------------------------------------------------------------- the assert in the timed path
def test_a_timed_phase_without_the_lock_is_an_assertion_failure(monkeypatch):
    monkeypatch.delenv("CYTUNE_NO_MEASUREMENT_LOCK", raising=False)
    lock.set_current(None)
    for phase in ("golden", "measure", "endpoint"):
        with pytest.raises(AssertionError, match="CF-1"):
            lock.assert_held(phase)


def test_the_assert_passes_while_the_lock_is_held(lockfile, monkeypatch):
    monkeypatch.delenv("CYTUNE_NO_MEASUREMENT_LOCK", raising=False)
    lk = lock.MeasurementLock(path=lockfile).acquire()
    lock.set_current(lk)
    try:
        lock.assert_held("measure")                       # must not raise
    finally:
        lock.set_current(None)
        lk.release()


def test_every_timed_phase_the_session_knows_about_is_covered():
    """Anti-vacuity: if a new timed phase is added to Session and not to TIMED_PHASES, the assert
    silently stops covering it. This pins the list against the phases Session actually runs."""
    from cytune import session
    assert set(session.Session.TIMED_PHASES) == {"golden", "measure", "endpoint"}, (
        "Session.TIMED_PHASES changed; confirm the new phase is timed and update this test "
        "deliberately, or the CF-1 assert now has a hole")


def test_the_escape_hatch_is_explicit_and_off_by_default(monkeypatch):
    """The suite disables the assert to exercise the machinery; a user must never inherit that."""
    monkeypatch.setenv("CYTUNE_NO_MEASUREMENT_LOCK", "1")
    lock.set_current(None)
    lock.assert_held("measure")                           # disabled: no raise
    monkeypatch.setenv("CYTUNE_NO_MEASUREMENT_LOCK", "0")
    with pytest.raises(AssertionError):
        lock.assert_held("measure")


def test_the_lock_path_is_machine_global_not_per_user_or_per_workspace():
    """The contended resource is the machine. A per-user path under $XDG_RUNTIME_DIR would miss
    the rootless-podman-different-UID case, which is the realistic one."""
    p = lock.lock_path()
    assert p.startswith("/var/lock/") or p.startswith("/tmp/"), p
    assert os.environ.get("XDG_RUNTIME_DIR", "\0") not in p
    assert os.getcwd() not in p
