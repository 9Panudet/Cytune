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
from .sanitize_gate import BUILD_COMMAND, CONTAINERFILE, EXPECTED_IMAGE_ID, IMAGE

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
        have_cf = os.path.exists(CONTAINERFILE)
        fix = f"BUILD IT: {BUILD_COMMAND}"
        fix += (f" (run from the repository root; it takes a few minutes and needs network access)"
                if have_cf else
                f" — but {CONTAINERFILE} is missing, so run this from a complete checkout")
        fix += (f". The expected image ID starts {EXPECTED_IMAGE_ID}; a different ID means your "
                f"toolchain differs from the one every published number was measured on. The "
                f"whole toolchain is pinned in that image, and an unpinned toolchain makes "
                f"results incomparable between runs.")
        return BLOCKING, False, f"pinned image {IMAGE} is absent", fix
    rc, out, _e = _run(["podman", "image", "inspect", IMAGE, "--format", "{{.Id}}"])
    if rc != 0:
        return BLOCKING, True, IMAGE, ""
    match = "" if out.startswith(EXPECTED_IMAGE_ID) else f" != expected {EXPECTED_IMAGE_ID}…"
    return BLOCKING, True, f"{IMAGE} ({out[:12]}…{match})", ""


def _check_entry_point():
    """Is `cytune` actually on PATH, or is the user stuck typing the module form?

    Cold-user finding F1: the README's first command was `cytune doctor` and there was no
    packaging, so a stranger hit `command not found` and had four guesses to make. Now there is a
    console script — and if it is missing, this line says exactly how to get it.
    """
    on_path = shutil.which("cytune")
    if on_path:
        return INFO, True, f"`cytune` is on PATH ({on_path})", ""
    # Being invoked BY the console script (e.g. `.venv/bin/cytune`) without the venv activated is
    # not a problem to report as if it were one.
    if os.path.basename(sys.argv[0] or "") == "cytune":
        return INFO, True, f"running the console script ({sys.argv[0]}); not on PATH — " \
                           f"activate the venv to type `cytune` directly", ""
    return INFO, False, "`cytune` is not on PATH (you are running the module form)", \
        "install the console script with `pip install -e .` from the repository root. " \
        "`python3 -m cytune ...` keeps working either way."


def _check_sanitizer_gate():  # noqa: C901
    """The §1.4 gate needs the same image; if it is missing the gate cannot run and cytune's
    memory-safety guarantee degrades to 'not checked'. Reported separately from the image check
    because the CONSEQUENCE is different and specific."""
    from . import sanitize_gate
    # By DIGEST, not by name: an image tagged with the pinned name is still not the pinned image,
    # and this line is where a user finds that out before spending an hour measuring (H6).
    unpinned = not sanitize_gate.is_pinned_image()
    over = f" [CYTUNE_SANITIZER_IMAGE={IMAGE}]" if IMAGE != sanitize_gate.DEFAULT_IMAGE else ""
    rc, _o, _e = _run(["podman", "image", "exists", IMAGE])
    if rc != 0:
        return DEGRADED, False, f"the §1.4 sanitizer gate CANNOT RUN (image absent){over}", \
            "cytune will still tune, but the emitted config is NOT checked for memory errors. " \
            "The certificate records this as not-run — which is NOT a pass. See D23." \
            + (f" Note that CYTUNE_SANITIZER_IMAGE is set to {IMAGE}; unset it to use the "
               f"pinned image." if over else "")
    if unpinned:
        return DEGRADED, False, \
            f"the §1.4 gate would run in an image that is NOT the pinned toolchain{over}", \
            f"the image resolves to digest {(rig.image_digest(IMAGE) or 'unknown')[:19]}, not the " \
            f"pinned {EXPECTED_IMAGE_ID}…. A clean gate from it is NOT treated as a pass: the " \
            f"'safe' wording is withheld and --apply refuses. Rebuild with `{BUILD_COMMAND}`."
    return DEGRADED, True, f"ASan+UBSan gate available for the emitted config{over}", ""


def _flatten(text, limit=160):
    """Collapse a subprocess's multi-line stderr onto one line.

    F10: doctor spliced raw multi-line output into the middle of a formatted field and destroyed
    the column layout. The detail is still worth showing — it is often the actual reason — so it
    is flattened rather than dropped."""
    one = " ".join((text or "").split())
    return one if len(one) <= limit else one[:limit - 1] + "…"


def _check_rig():
    mode, detail = rig.probe_rig()
    if mode == rig.QUIESCED:
        return DEGRADED, True, f"quiesced rig ({_flatten(detail)})", ""
    return DEGRADED, False, f"portable mode — {_flatten(detail)}", \
        "measurements are best-effort: turbo, frequency scaling and other processes are not " \
        "controlled. Speedups smaller than a few percent are not distinguishable from noise. " \
        "Run scripts/host_prep.sh (needs sudo) for the quiesced rig, or pass --rig portable to " \
        "accept indicative timings."


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
          ("python", _check_python), ("entry point", _check_entry_point),
          ("workspace", _check_workspace)]


def run_checks():
    out = []
    for name, fn in CHECKS:
        tier, ok, detail, fix = fn()
        out.append({"check": name, "tier": tier, "ok": bool(ok), "detail": detail, "fix": fix})
    return out


# The checks `tune` runs for itself (C2). Deliberately a SUBSET: `measurement rig` is not here,
# because a non-quiesced rig is a degraded run and not a broken one, and `workspace` is not here
# because tune creates its own. These four are the ones whose absence makes a run impossible, and
# whose failure without this check surfaced as an internal error three stages later.
TUNE_PREFLIGHT = ("podman", "pinned image", "sanitizer gate", "python")


def blocking_preflight():
    """The BLOCKING checks `cytune tune` must pass before it builds anything.

    Why tune runs these itself rather than telling the user to run `doctor` first: a beginner does
    not know `doctor` exists. Before this, a machine with no podman produced a container spawn
    failure from inside the build stage -- accurate, and useless. Now the run stops before it
    creates a workspace and prints DOCTOR'S OWN fix line, which is the line that has been kept
    current because `doctor` is what people are told to run.

    Returns the failing rows, most important first. Empty means clear to proceed.
    """
    rows = [r for r in run_checks() if r["check"] in TUNE_PREFLIGHT]
    return [r for r in rows if r["tier"] == BLOCKING and not r["ok"]]


def build_image(args=None):
    """`cytune doctor --build-image` — run the pinned build, then VERIFY what came out.

    `doctor` has always named the command; a user still had to leave, read the Containerfile's
    directory, run it, and come back. That was the last manual step in getting from a clean machine
    to a working cytune, and cold-user finding F3 was that nothing anywhere named it at all.

    The verification is the part that matters. A build that succeeds and produces a DIFFERENT image
    from the one every number under results/ was measured on is not a success — it is an unpinned
    toolchain, silently. So the digest is compared and a mismatch is reported as a failure with the
    consequence spelled out, rather than a green checkmark on the wrong image.
    """
    if not os.path.exists(CONTAINERFILE):
        print(f"cytune: {CONTAINERFILE} is missing — run this from a complete checkout.\n"
              f"  The Containerfile pins the whole toolchain; without it there is nothing to "
              f"build.", file=sys.stderr)
        return 1
    root = os.path.dirname(CONTAINERFILE)
    cmd = ["podman", "build", "-f", CONTAINERFILE, "-t", IMAGE, root]
    print(f"cytune — building the pinned toolchain image\n  {' '.join(cmd)}\n"
          f"  This takes several minutes and needs network access. Output follows.\n")
    try:
        rc = subprocess.call(cmd)
    except FileNotFoundError:
        print("cytune: podman is not on PATH.", file=sys.stderr)
        return 1
    if rc != 0:
        print(f"\ncytune: the image build FAILED (podman exit {rc}). Nothing was verified.",
              file=sys.stderr)
        return 1

    got = rig.image_digest(IMAGE)
    print()
    if got == rig.PINNED_IMAGE_DIGEST:
        print(f"OK — {IMAGE} is the pinned toolchain ({got[:19]}…).")
        return 0
    print(f"cytune: the build SUCCEEDED but produced a different image.\n"
          f"  built    : {got or 'unresolved'}\n"
          f"  expected : {rig.PINNED_IMAGE_DIGEST}\n\n"
          f"  This is not a pass. Every published number was measured in the expected image,\n"
          f"  and the §1.4 sanitizer gate treats a clean verdict from any other image as NOT\n"
          f"  authoritative — the 'safe' wording is withheld and --apply refuses (H6).\n\n"
          f"  Usually this means an upstream package moved. cytune will still run; it will say on\n"
          f"  every certificate that its toolchain is not the pinned one.", file=sys.stderr)
    return 1


def doctor(args=None):
    if getattr(args, "build_image", False):
        return build_image(args)
    rows = run_checks()
    if getattr(args, "json", False):
        import json
        from . import SCHEMA_VERSION
        blocking = [r for r in rows if r["tier"] == BLOCKING and not r["ok"]]
        degraded = [r for r in rows if r["tier"] == DEGRADED and not r["ok"]]
        code = 1 if blocking else 0
        # `name` mirrors the other artifacts' key for the same idea; `check` is kept alongside it
        # because the compatibility promise says fields are added, never removed or renamed under
        # a consumer. It will go at 2.0, not before.
        checks = [{**r, "name": r["check"]} for r in rows]
        print(json.dumps({"schema": f"cytune-doctor/{SCHEMA_VERSION}",
                          "cytune_version": __version__, "checks": checks,
                          "blocking": len(blocking), "degraded": len(degraded),
                          "ready": not blocking, "ok": not blocking,
                          "exit_code": code}, indent=1))
        return code
    print(f"cytune {__version__} — environment check\n")
    width = max(len(r["check"]) for r in rows)
    for r in rows:
        mark = ("ok  " if r["ok"] else
                "FAIL" if r["tier"] == BLOCKING else
                "warn" if r["tier"] == DEGRADED else "info")
        print(f"  [{mark}] {r['check']:<{width}}  {_flatten(r['detail'], 200)}")
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
