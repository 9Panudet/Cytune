"""Rig modes (PREREG §12 A-4; directive item 5) — quiesced vs portable.

Product reality: the study's rig requires a human with root to have run `host_prep.sh` (no_turbo,
performance governor, isolated cores, THP=madvise). A user tuning their own module has none of
that. cytune therefore measures in one of two modes and SAYS WHICH ONE on the certificate:

  quiesced  measure_wrap.sh verifies the full host assert set and refuses otherwise; every row
            carries the verified RIG_FINGERPRINT. This is measurement of record.
  portable  no measure_wrap (or its asserts fail): a plain pinned container, still one fresh
            subprocess per config and still median-of-K, but WITHOUT host quiescing. Rows carry
            rig="UNGATED". Speedups are indicative, not decision-grade.

The mode NEVER affects correctness. The oracle, the tolerance and the "never emit an oracle-failing
config" guarantee are identical in both. Degrading the rig degrades the SPEED claim only — that
separation is the whole point of having two modes rather than refusing to run.
"""
from __future__ import annotations
import os
import subprocess

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
IMAGE = "localhost/motifbo-env:phase1"
MEASURE_WRAP = os.path.join(REPO, "scripts", "measure_wrap.sh")
WORKER = "/probe/phasep/cytune_phase.py"

QUIESCED = "quiesced"
PORTABLE = "portable"


def probe_rig():
    """Return (mode, detail). Never raises — an unavailable rig degrades, it does not fail."""
    if not os.path.exists(MEASURE_WRAP):
        return PORTABLE, "measure_wrap.sh not present"
    try:
        r = subprocess.run(["bash", MEASURE_WRAP, "--verify-only"],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return PORTABLE, f"measure_wrap could not be executed: {e}"
    if r.returncode == 0:
        return QUIESCED, r.stdout.strip() or "verify-only PASS"
    # exit 78 is measure_wrap's structured refusal; anything else is unexpected but still a refusal
    return PORTABLE, (r.stderr.strip() or r.stdout.strip() or f"verify-only exit {r.returncode}")


def _mounts(workspace):
    return ["--security-opt", "label=disable",
            "-e", "PYTHONPATH=/src",
            "-v", f"{REPO}/scripts:/probe:ro",
            "-v", f"{REPO}/src:/src:ro",
            "-v", f"{REPO}/results:/results:ro",
            "-v", f"{workspace}:/work"]


def _inner(name, sub, args):
    return [IMAGE, "python3", "-m", "cytune.worker", sub,
            f"/work/_kernels/{name}", f"/work/{name}"] + [str(a) for a in args]


def build_cmd(workspace, name, ids_arg):
    """BUILD phase — a PLAIN container. Never measure_wrap: compiling on the isolated measurement
    core would be pointless, and CF-1 wants build and measure in separate contexts anyway."""
    return (["podman", "run", "--rm", "--network=none"] + _mounts(workspace) +
            _inner(name, "build", [ids_arg]))


def measure_cmd(workspace, name, mode, sub, args):
    """MEASURE phase — through measure_wrap when quiesced, plain container when portable."""
    inner = _inner(name, sub, args)
    if mode == QUIESCED:
        return ["bash", MEASURE_WRAP] + _mounts(workspace) + inner
    return ["podman", "run", "--rm", "--network=none"] + _mounts(workspace) + inner


def compute_cmd(workspace, name, sub, args):
    """Pure-compute steps (probe features, DOE planning). No timing happens, so these never need
    the quiesced rig — running them under measure_wrap would only add noise to its invocation log."""
    return (["podman", "run", "--rm", "--network=none"] + _mounts(workspace) +
            _inner(name, sub, args))


def certificate_line(mode, detail):
    if mode == QUIESCED:
        return f"quiesced — host asserts verified by measure_wrap ({detail})"
    return ("portable measurement — INDICATIVE, not decision-grade. The host was not quiesced "
            f"({detail}). Correctness guarantees are unaffected; timing may drift with system load.")
