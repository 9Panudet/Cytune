"""`cytune doctor` — check the environment BEFORE a run, and print what to do about each failure.

Every check answers one question a user would otherwise discover as a confusing mid-run error, and
every failure line names the fix. Checks are grouped by what they cost you if they fail:

  BLOCKING   — cytune cannot run at all.
  DEGRADED   — cytune runs, but a guarantee is weaker, and the certificate will say so.
  INFO       — worth knowing, costs nothing.

The DEGRADED tier exists because of D23: the difference between "the sanitizer gate passed" and
"the sanitizer gate could not run" is the whole lesson of this phase, and a user should be able to
find out which state they are in BEFORE they spend an hour measuring, not by reading a field in a
certificate afterwards.
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys

from . import __version__, rig
from .sanitize_gate import IMAGE

BLOCKING, DEGRADED, INFO = "BLOCKING", "DEGRADED", "INFO"


def _run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", "not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"


def _check_podman():
    if not shutil.which("podman"):
        return BLOCKING, False, "podman not on PATH", \
            "install podman — every build and measurement runs inside the pinned image"
    rc, out, err = _run(["podman", "--version"])
    if rc != 0:
        return BLOCKING, False, f"podman present but not working: {err[:80]}", \
            "check that podman can run rootless: `podman info`"
    return BLOCKING, True, out, ""


def _check_image():
    rc, _o, _e = _run(["podman", "image", "exists", IMAGE])
    if rc != 0:
        return BLOCKING, False, f"pinned image {IMAGE} is absent", \
            f"build or load it: the whole toolchain is pinned there, and an unpinned " \
            f"toolchain makes results incomparable"
    rc, out, _e = _run(["podman", "image", "inspect", IMAGE, "--format", "{{.Id}}"])
    return BLOCKING, True, f"{IMAGE} ({out[:19]}…)" if rc == 0 else IMAGE, ""


def _check_sanitizer_gate():
    """The §1.4 gate needs the same image; if it is missing the gate cannot run and cytune's
    memory-safety guarantee degrades to 'not checked'. Reported separately from the image check
    because the CONSEQUENCE is different and specific."""
    rc, _o, _e = _run(["podman", "image", "exists", IMAGE])
    if rc != 0:
        return DEGRADED, False, "the §1.4 sanitizer gate CANNOT RUN (image absent)", \
            "cytune will still tune, but the emitted config is NOT checked for memory errors. " \
            "The certificate records this as not-run — which is NOT a pass. See D23."
    return DEGRADED, True, "ASan+UBSan gate available for the emitted config", ""


def _check_rig():
    mode, detail = rig.probe_rig()
    if mode == rig.QUIESCED:
        return DEGRADED, True, f"quiesced rig ({detail})", ""
    return DEGRADED, False, f"portable mode — {detail}", \
        "measurements are best-effort: turbo, frequency scaling and other processes are not " \
        "controlled. Speedups smaller than a few percent are not distinguishable from noise. " \
        "Run scripts/host_prep.sh (needs sudo) for the quiesced rig."


def _check_python():
    v = sys.version_info
    ok = v >= (3, 9)
    return BLOCKING if not ok else INFO, ok, \
        f"python {v.major}.{v.minor}.{v.micro}", "" if ok else "cytune needs python >= 3.9"


def _check_workspace(path=".cytune"):
    d = os.path.abspath(path)
    parent = os.path.dirname(d)
    if os.path.exists(d):
        ok = os.access(d, os.W_OK)
        return INFO, ok, f"workspace {d} exists", "" if ok else f"{d} is not writable"
    ok = os.access(parent, os.W_OK)
    return INFO, ok, f"workspace {d} will be created", \
        "" if ok else f"{parent} is not writable — pass --workspace elsewhere"


CHECKS = [("podman", _check_podman), ("pinned image", _check_image),
          ("sanitizer gate", _check_sanitizer_gate), ("measurement rig", _check_rig),
          ("python", _check_python), ("workspace", _check_workspace)]


def run_checks():
    out = []
    for name, fn in CHECKS:
        tier, ok, detail, fix = fn()
        out.append({"check": name, "tier": tier, "ok": bool(ok), "detail": detail, "fix": fix})
    return out


def doctor(args=None):
    rows = run_checks()
    print(f"cytune {__version__} — environment check\n")
    width = max(len(r["check"]) for r in rows)
    for r in rows:
        mark = "ok  " if r["ok"] else ("FAIL" if r["tier"] == BLOCKING else "warn")
        print(f"  [{mark}] {r['check']:<{width}}  {r['detail']}")
        if not r["ok"] and r["fix"]:
            for line in _wrap(r["fix"], width + 11):
                print(line)
    blocking = [r for r in rows if r["tier"] == BLOCKING and not r["ok"]]
    degraded = [r for r in rows if r["tier"] == DEGRADED and not r["ok"]]
    print()
    if blocking:
        print(f"BLOCKED: {len(blocking)} check(s) must pass before cytune can run.")
        return 1
    if degraded:
        print(f"READY, with {len(degraded)} degraded guarantee(s) — cytune will run and the "
              f"certificate will state each one. Nothing above is silently ignored.")
        return 0
    print("READY — all checks pass.")
    return 0


def _wrap(text, indent, width=96):
    words, line, out = text.split(), " " * indent, []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = " " * indent + w
        else:
            line = (line + " " + w) if line.strip() else line + w
    if line.strip():
        out.append(line)
    return out
