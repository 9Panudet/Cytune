"""B3 — a machine-level measurement lock.

THE FAILURE MODE THIS CLOSES, and why it deserves a mechanism rather than a warning.

CF-1 says compile and measure never overlap. The product enforces that *within one process*:
one container per phase, builds pinned off the isolated cores, and `cli.tune` running the stages in
order. Across processes it enforces nothing at all. Two `cytune tune` runs in two terminals — the
ordinary shape of multi-project work — interleave freely, and `cli.tune` alternates build and
measure four times, so each run's parallel build phase lands inside the other's timed phase.

The result is not a crash. It is **wrong numbers with no warning**: a contended machine measures
slower, the slowdown correlates with time, and config id order correlates with `-O1`/`-O3`, so a
time-correlated slowdown can alias onto a factor. This project has already discarded 626 measured
rows to exactly that mechanism (2026-07-24), and `campaign_busy.sh` argues the policy on that
evidence: report BUSY for the WHOLE cycle, build included, because the cheap false positive is
worth avoiding the expensive false negative.

DESIGN NOTES, each one load-bearing:

  * `flock`, not a PID file. The kernel releases a `flock` when the holder dies, so `kill -9`
    leaves no stale lock — a property no PID file has. The heartbeat below therefore only has to
    cover the wedged-but-alive holder, which is a much smaller problem.
  * Machine-global path, not per user and not per workspace. The contended resource is the
    physical machine — LLC and DRAM bandwidth are shared even when cpusets are not — so a
    per-user lock under $XDG_RUNTIME_DIR would miss the rootless-podman-different-UID case that
    is the realistic one, and a per-workspace lock would miss every case this exists for.
  * The holder is identified by `pid` PLUS its `/proc/<pid>` start time, never by matching a
    command line. `pgrep -f` matching its own caller is defect D19, and it is not repeated here.
  * The whole run holds it, not each phase. A per-phase lock would still let a competing run's
    BUILD land inside this run's MEASURE, which is the contamination mode.
  * Never acquired by a read-only rig verification. `rig.probe_rig()` and `doctor` both shell out
    to `measure_wrap.sh --verify-only` on every invocation; acquiring there would deadlock doctor
    against any running tune, and tune against itself.
"""
from __future__ import annotations

import errno
import fcntl
import json
import os
import time

DEFAULT_DIRS = ("/var/lock/cytune", "/tmp")
LOCK_NAME = "cytune-measure.lock"

# A holder whose heartbeat is older than this is reported as possibly wedged. It is NOT stolen:
# the message tells the user how old it is and lets them decide. Silent stealing is how two runs
# end up measuring at once, which is the thing this file exists to prevent.
STALE_S = 1800.0


class Busy(Exception):
    """Another measurement holds the machine. Carries the holder's payload for the message."""

    def __init__(self, holder, path):
        self.holder = holder or {}
        self.path = path
        super().__init__("another cytune measurement holds this machine")


def lock_path():
    """First writable candidate wins. Recorded on the certificate so the choice is not invisible."""
    for d in DEFAULT_DIRS:
        try:
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, LOCK_NAME)
            fd = os.open(p, os.O_RDWR | os.O_CREAT, 0o666)
            os.close(fd)
            try:
                os.chmod(p, 0o666)          # cross-user by design; fails harmlessly if not owner
            except OSError:
                pass
            return p
        except OSError:
            continue
    raise RuntimeError(f"no writable location for the measurement lock (tried {DEFAULT_DIRS})")


def _boot_id():
    try:
        with open("/proc/sys/kernel/random/boot_id") as f:
            return f.read().strip()
    except OSError:
        return None


def _starttime(pid):
    """Field 22 of /proc/<pid>/stat. Makes the (pid, starttime) pair PID-reuse-proof."""
    try:
        with open(f"/proc/{pid}/stat") as f:
            data = f.read()
        return data[data.rindex(")") + 2:].split()[19]
    except (OSError, ValueError, IndexError):
        return None


def _alive(pid, starttime):
    if not pid:
        return False
    st = _starttime(pid)
    return st is not None and (starttime is None or st == starttime)


def read_holder(path=None):
    """The current payload, or None. Never blocks and never acquires."""
    path = path or lock_path()
    try:
        with open(path) as f:
            txt = f.read().strip()
        return json.loads(txt) if txt else None
    except (OSError, ValueError):
        return None


def describe(holder, path):
    """The refusal message. It names the holder, the age, the remedy, and the reason."""
    if not holder:
        return (f"another process holds the measurement lock at {path} (it wrote no details).\n"
                f"  Wait for it to finish, or re-run with --wait to queue.")
    pid = holder.get("pid")
    age = time.time() - float(holder.get("acquired_epoch") or time.time())
    hb = holder.get("heartbeat_epoch")
    hb_age = (time.time() - float(hb)) if hb else None
    lines = [
        f"another cytune measurement holds this machine (lock: {path})",
        f"    pid {pid}  started {age / 60:.1f} min ago  phase {holder.get('phase') or '?'}",
        f"    workspace {holder.get('workspace')}",
        f"    rig {holder.get('rig_mode')}  host {holder.get('nodename')}",
    ]
    if hb_age is not None and hb_age > STALE_S:
        lines.append(f"    WARNING: its heartbeat is {hb_age / 60:.0f} min old — it may be wedged. "
                     f"It still holds the lock, so it is still running; kill it deliberately if "
                     f"you believe otherwise.")
    lines += [
        "",
        "  Two runs measuring at once produce WRONG NUMBERS with no warning: a contended machine",
        "  measures slower, and because config id order correlates with the -O1/-O3 factor, a",
        "  time-correlated slowdown can alias onto a factor. This project discarded 626 measured",
        "  rows to exactly that on 2026-07-24.",
        "",
        "  Wait for it, or re-run with --wait to queue behind it.",
    ]
    return "\n".join(lines)


class MeasurementLock:
    """Exclusive, machine-wide, for the whole run. Use as a context manager."""

    def __init__(self, workspace=None, rig_mode=None, argv=None, path=None):
        self.path = path or lock_path()
        self.workspace = workspace
        self.rig_mode = rig_mode
        self.argv = argv
        self._fd = None
        self._payload = None

    # -------------------------------------------------------------------------------- acquisition
    def _payload_now(self, phase):
        return {
            "pid": os.getpid(),
            "starttime": _starttime(os.getpid()),
            "nodename": os.uname().nodename,
            "boot_id": _boot_id(),
            "rig_mode": self.rig_mode,
            "workspace": self.workspace,
            "argv": self.argv,
            "phase": phase,
            "acquired_epoch": getattr(self, "_acquired", time.time()),
            "acquired_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "heartbeat_epoch": time.time(),
        }

    def _write(self, phase):
        self._payload = self._payload_now(phase)
        os.ftruncate(self._fd, 0)
        os.lseek(self._fd, 0, os.SEEK_SET)
        os.write(self._fd, (json.dumps(self._payload) + "\n").encode())
        os.fsync(self._fd)

    def acquire(self, wait=False, on_wait=None, poll_s=2.0, timeout_s=None):
        self._fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o666)
        t0 = time.time()
        announced = False
        while True:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as e:
                if e.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                holder = read_holder(self.path)
                if not wait:
                    os.close(self._fd)
                    self._fd = None
                    raise Busy(holder, self.path)
                if on_wait and not announced:
                    on_wait(holder)                     # print WHO we are queued behind, once
                    announced = True
                if timeout_s is not None and time.time() - t0 > timeout_s:
                    os.close(self._fd)
                    self._fd = None
                    raise Busy(holder, self.path)
                time.sleep(poll_s)
        self._acquired = time.time()
        self._write("acquired")
        return self

    def heartbeat(self, phase):
        """Called at every phase transition, so a wedged holder is visible as a stale heartbeat."""
        if self._fd is not None:
            self._write(phase)

    def held(self):
        return self._fd is not None

    def release(self):
        if self._fd is None:
            return
        try:
            os.ftruncate(self._fd, 0)
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()
        return False


# ------------------------------------------------------------------------------- the process-wide
# handle, so `Session._run` can assert the lock is held without threading it through every call.
_CURRENT = None


def set_current(lk):
    global _CURRENT
    _CURRENT = lk


def current():
    return _CURRENT


def assert_held(phase):
    """Belt and braces: no code path may enter a TIMED phase without the lock.

    `MeasurementLock` is taken once in `cli.tune`, above every container spawn. This assert is what
    stops a future code path from timing something outside it, and it is deliberately shaped like
    the CF-4 asserts: cheap, at the boundary, and pointing at the rule it protects.

    Disabled by CYTUNE_NO_MEASUREMENT_LOCK=1 for the tests that exercise the machinery itself.
    """
    if os.environ.get("CYTUNE_NO_MEASUREMENT_LOCK") == "1":
        return
    lk = current()
    if lk is None or not lk.held():
        raise AssertionError(
            f"CF-1: entered timed phase {phase!r} without holding the machine-level measurement "
            f"lock. Two concurrent measurements produce wrong numbers with no warning; see "
            f"cytune/lock.py.")
