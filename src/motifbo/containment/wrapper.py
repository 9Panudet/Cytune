"""Per-candidate containment wrapper (Step 0.4.3, roadmap §3.4 + §3.5).

HOST-SIDE: the orchestrator launches each candidate compile/run as its own podman
container with the §3.4 limits, and classifies the outcome per §3.5 so the
orchestrator NEVER crashes on a misbehaving candidate.

§3.4 limits: `--network=none`; `--memory=4g` with swap disabled (cgroup); `/sandbox`
= a fresh 2 GB tmpfs (a new container per candidate ⇒ the tmpfs is wiped automatically);
wall-clock timeout = 120 s for compiles, max(10× golden median, 5 s) for runs.

§3.5 PROCESS-level labels produced here:
  ok | timeout | memory_cap_kill | crash (segfault/abort/bus/fpe/ill) | nonzero_exit
The remaining §3.5 verdicts (sanitizer report ≠ 0, oracle mismatch) come from the
sanitizer/oracle layers; feasibility is composed from all of them downstream (1.4.3).

CARRIED NOTE F9 (0.4.1 auditor): a GATE-mode sanitizer run uses detect_leaks=0, so a
nonzero exit is a real report; LEAK-AUDIT mode must NOT feed exit code into
feasibility (a by-design CPython residual leak exits 1). This wrapper only reports
process labels and asserts no feasibility itself, so that contract is preserved here.
"""
import signal
import subprocess
import time
import uuid
from dataclasses import dataclass

# §3.4 constants.
COMPILE_TIMEOUT_S = 120.0
RUN_TIMEOUT_FLOOR_S = 5.0
RUN_TIMEOUT_FACTOR = 10.0
DEFAULT_MEMORY_MB = 4096          # 4 GB cgroup cap
DEFAULT_SANDBOX_MB = 2048         # 2 GB tmpfs /sandbox

_CRASH_SIGNALS = {int(s) for s in (signal.SIGSEGV, signal.SIGABRT, signal.SIGBUS,
                                   signal.SIGFPE, signal.SIGILL)}
_SIGKILL = int(signal.SIGKILL)


def run_timeout_s(golden_median_s):
    """§3.4 run-timeout rule: max(10× golden median, 5 s)."""
    return max(RUN_TIMEOUT_FACTOR * golden_median_s, RUN_TIMEOUT_FLOOR_S)


@dataclass
class ContainmentResult:
    label: str
    returncode: "int | None"
    timed_out: bool
    oom_killed: bool
    duration_s: float
    stdout: str
    stderr: str


def classify(returncode, timed_out, oom_killed):
    """Map a finished candidate process to a §3.5 process-level label."""
    if timed_out:
        return "timeout"
    if oom_killed:
        return "memory_cap_kill"
    if returncode == 0:
        return "ok"
    sig = None
    if returncode is not None and returncode < 0:
        sig = -returncode                       # Popen convention: killed by -N
    elif returncode is not None and returncode > 128:
        sig = returncode - 128                  # shell/podman convention: 128+N
    if sig == _SIGKILL:
        return "memory_cap_kill"                # SIGKILL w/o our timeout ⇒ OOM under --memory
    if sig in _CRASH_SIGNALS:
        return "crash"
    return "nonzero_exit"


def run_contained(argv, *, image, timeout_s, memory_mb=DEFAULT_MEMORY_MB,
                  sandbox_mb=DEFAULT_SANDBOX_MB, mounts=(), env=None,
                  cpuset=None, workdir=None, podman="podman"):
    """Run `argv` in a contained podman container; return a ContainmentResult.

    Never raises on candidate misbehaviour — timeouts, OOM kills, segfaults, and
    aborts all come back as labels. A harness-level failure (e.g. podman missing)
    is itself caught and surfaced as label 'harness_error'.
    """
    name = f"motifbo-cand-{uuid.uuid4().hex[:12]}"
    cmd = [podman, "run", "--name", name, "--network=none",
           f"--memory={memory_mb}m", f"--memory-swap={memory_mb}m",
           "--tmpfs", f"/sandbox:size={sandbox_mb}m"]
    if cpuset is not None:
        cmd.append(f"--cpuset-cpus={cpuset}")
    if workdir is not None:
        cmd += ["-w", workdir]
    for m in mounts:
        cmd += ["-v", m]
    for k, v in (env or {}).items():
        cmd += ["-e", f"{k}={v}"]
    cmd.append(image)
    cmd += list(argv)

    t0 = time.monotonic()
    timed_out = False
    rc, out, err, oom = None, "", "", False
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        try:
            out, err = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            subprocess.run([podman, "kill", name], capture_output=True)
            out, err = proc.communicate()
        rc = proc.returncode
        oom = _oom_killed(podman, name)
        return ContainmentResult(classify(rc, timed_out, oom), rc, timed_out, oom,
                                 time.monotonic() - t0, out or "", err or "")
    except Exception as e:                      # harness failure, not candidate fault
        return ContainmentResult("harness_error", rc, timed_out, oom,
                                 time.monotonic() - t0, out or "", f"{err}\n{e!r}")
    finally:
        subprocess.run([podman, "rm", "-f", name], capture_output=True)


def _oom_killed(podman, name):
    p = subprocess.run([podman, "inspect", "--format", "{{.State.OOMKilled}}", name],
                       capture_output=True, text=True)
    return p.returncode == 0 and p.stdout.strip() == "true"
