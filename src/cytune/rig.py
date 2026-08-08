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

PKG_DIR = os.path.dirname(os.path.abspath(__file__))            # .../src/cytune
REPO = os.path.abspath(os.path.join(PKG_DIR, "..", ".."))
IMAGE = "localhost/motifbo-env:phase1"

# THE PINNED TOOLCHAIN, BY CONTENT. Every number under results/ was measured in this image.
#
# The NAME is not the pin and never was: `podman tag anything localhost/motifbo-env:phase1` makes a
# name match in one command, which is how the adversarial campaign turned a stub into a clean
# sanitizer verdict (H6). The digest is the identity. It is resolved at run time and recorded on
# every artifact and every gate verdict (I4.3).
PINNED_IMAGE_DIGEST = ("sha256:d45e33b08bad0020bcf0d04eefe50c04e7e1f36e3ccb4d55daf655e9900295d2")


_DIGEST_CACHE = {}


def image_ref(image=None):
    """What to actually hand `podman run` — the resolved image ID, not the tag.

    THE DEFECT THIS CLOSES (Attack A, found by the focused adversarial re-run, and it was mine).
    `image_digest` memoises per name, and the cache is filled by the FIRST container spawn of a run.
    The sanitizer gate then compared that digest against the pinned one minutes later, while
    `podman run <name>` resolved the tag LIVE. One `podman tag stub localhost/motifbo-env:phase1`
    between those two moments made `is_pinned_image()` return True from a stale, honest digest while
    the stub actually ran — which is H6 rebuilt on top of its own fix, by a cache added for speed.

    Comparing the digest was the right idea and checking it at the right MOMENT is the rest of it:
    resolve once, then run THAT, so the image whose digest was compared is by construction the image
    that executed. A tag moved afterwards points somewhere cytune is no longer looking.

    Falls back to the name only when the image cannot be resolved at all, in which case the run
    fails loudly and no verdict is produced.
    """
    return image_digest(image) or (image or IMAGE)


def image_digest(image=None):
    """The content digest of what `image` resolves to right now, or None if it is not present.

    Never raises: an unresolvable image degrades the guarantee and says so, exactly as a missing
    measure_wrap does. Refusing here would make the failure mode of a missing image indistinguishable
    from a crash.
    """
    name = image or IMAGE
    if name in _DIGEST_CACHE:
        return _DIGEST_CACHE[name]
    try:
        r = subprocess.run(["podman", "image", "inspect", "--format", "{{.Id}}", name],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    out = (r.stdout or "").strip()
    if r.returncode != 0 or not out:
        return None
    digest = out if out.startswith("sha256:") else f"sha256:{out}"
    _DIGEST_CACHE[name] = digest
    return digest


def isolated_cpus():
    """The cores the kernel has been told to keep off the general scheduler, as a string.

    Read so the BUILD phase can be pinned away from them: compiling on the isolated measurement
    core is the one thing that could make a build and a measurement interfere, and CF-1 separates
    the phases in TIME while this separates them in SPACE.
    """
    try:
        with open("/sys/devices/system/cpu/isolated") as f:
            return f.read().strip()
    except OSError:
        return ""


def _build_cpus():
    """`--cpuset-cpus` for the build container: every online CPU that is not isolated."""
    iso = isolated_cpus()
    if not iso:
        return None
    bad = set()
    for part in iso.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            bad.update(range(int(a), int(b) + 1))
        else:
            bad.add(int(part))
    keep = [c for c in range(os.cpu_count() or 1) if c not in bad]
    return ",".join(str(c) for c in keep) if keep else None

# HOST infrastructure, deliberately NOT shipped inside the package.
#
# `measure_wrap.sh` verifies a quiesced host — no_turbo, performance governor, isolated core,
# THP — which only exists after a human has run `sudo scripts/host_prep.sh`. A pip-installed
# cytune cannot quiesce anything, so vendoring the script would buy nothing and would break it:
# it resolves `REPO_ROOT="$(dirname $0)/.."` and calls a sibling `scripts/thermal_log.sh`, so
# moving it into the package made it fail with rc=127 mid-run instead of degrading. (Caught by a
# live run during the v1.0.0 architecture pass; the graceful path below is the original design and
# is the correct one.)
#
# When the script is absent, `probe_rig()` returns PORTABLE with the reason, `doctor` reports
# DEGRADED, and the certificate says the timings are indicative. Nothing silently passes.
MEASURE_WRAP = os.path.join(REPO, "scripts", "measure_wrap.sh")

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
        # F12: a raw Python exception repr in a user-facing field.
        reason = (f"{MEASURE_WRAP} could not be executed"
                  + (" (bash was not found on PATH)" if "bash" in str(e) else f" ({e})"))
        return PORTABLE, reason
    if r.returncode == 0:
        return QUIESCED, r.stdout.strip() or "verify-only PASS"
    # exit 78 is measure_wrap's structured refusal; anything else is unexpected but still a refusal
    return PORTABLE, (r.stderr.strip() or r.stdout.strip() or f"verify-only exit {r.returncode}")


def _mounts(workspace):
    """Exactly two mounts: the package (read-only) and the user's workspace (read-write).

    This used to also mount the repo's `scripts/` at /probe and `results/` at /results, because the
    container-side worker imported the study's harness from one and the frozen DOE designs from the
    other. Both are now vendored into the package (see `cytune/_vendor/`), so a measurement
    container can no longer see the study tree at all — which is what makes "the product ships
    standalone" a checkable property rather than a claim.
    `test_cytune_architecture.py::test_container_mounts_expose_only_the_package_and_workspace`
    pins it.
    """
    return ["--security-opt", "label=disable",
            "-e", "PYTHONPATH=/opt/cytune",
            # I4 — the toolchain identity travels WITH the work, so the artifact record written
            # inside the container names the image that produced it rather than the host asserting
            # afterwards which image it thinks it used.
            "-e", f"CYTUNE_IMAGE_DIGEST={image_digest() or ''}",
            "-v", f"{PKG_DIR}:/opt/cytune/cytune:ro",
            "-v", f"{workspace}:/work"]


def _inner(name, sub, args):
    # By RESOLVED ID, not by tag — see image_ref(). Every phase of a run therefore executes the
    # same image the certificate names, and re-tagging mid-run cannot redirect it.
    return [image_ref(), "python3", "-m", "cytune.worker", sub,
            f"/work/_kernels/{name}", f"/work/{name}"] + [str(a) for a in args]


def build_cmd(workspace, name, ids_arg):
    """BUILD phase — a PLAIN container. Never measure_wrap: compiling on the isolated measurement
    core would be pointless, and CF-1 wants build and measure in separate contexts anyway.

    Pinned to the NON-isolated cores when the host has isolated any. The build is now parallel
    across every CPU it is given (worker._build_all), which makes "do not compile on the
    measurement core" something to enforce rather than assume — and it is what lets the container
    size its own worker pool from `sched_getaffinity` instead of being told twice.
    """
    cpus = _build_cpus()
    opts = ["--cpuset-cpus", cpus] if cpus else []
    return (["podman", "run", "--rm", "--network=none"] + opts + _mounts(workspace) +
            _inner(name, "build", [ids_arg]))


def _readonly_artifacts(workspace, name):
    """Re-mount the built `.so` tree READ-ONLY over the writable workspace, for measure phases.

    THE DEFECT THIS CLOSES (Attack B, focused adversarial re-run). I4.1 hashes the artifact in the
    PARENT before spawning the measurement child. `_vendor/measure_child.py` then loads the DRIVER
    first and the `.so` only afterwards — so the driver's import-time code runs between the hash and
    the load, inside a container where the whole workspace was mounted read-write. A driver that
    overwrote the winner's `.so` with a faster binary producing identical output got: the honest
    hash on both sides of I4.1, a real wall clock that corroborated under C1, and a forged speedup.

    Hashing again afterwards is not sufficient on its own — the swap can be undone before exit. The
    fix is to remove the capability: nothing in a measure phase writes to `_so/` (the build phase is
    a separate container, which is what CF-1 is for), so the directory is mounted read-only and the
    swap fails at the filesystem instead of being detected after the fact.

    This does NOT close the driver loading a different module by patching `importlib` in its own
    process. That is the stated trust boundary (GUARANTEES N8) and no mount can fix it.
    """
    so = os.path.join(workspace, name, "_so")
    return ["-v", f"{so}:/work/{name}/_so:ro"] if os.path.isdir(so) else []


def measure_cmd(workspace, name, mode, sub, args):
    """MEASURE phase — through measure_wrap when quiesced, plain container when portable."""
    inner = _inner(name, sub, args)
    mounts = _mounts(workspace) + _readonly_artifacts(workspace, name)
    if mode == QUIESCED:
        return ["bash", MEASURE_WRAP] + mounts + inner
    return ["podman", "run", "--rm", "--network=none"] + mounts + inner


def compute_cmd(workspace, name, sub, args):
    """Pure-compute steps (probe features, DOE planning). No timing happens, so these never need
    the quiesced rig — running them under measure_wrap would only add noise to its invocation log."""
    return (["podman", "run", "--rm", "--network=none"] + _mounts(workspace) +
            _inner(name, sub, args))


FORCED_PORTABLE = "forced by --rig portable"


def certificate_line(mode, detail):
    """One line, and it must not assert anything about the host that this run did not check.

    `--rig portable` on an ALREADY-QUIESCED host relabels the claim; it does not un-quiesce the
    machine. Saying "the host was not quiesced" there was a flat false statement of fact about
    the user's machine, in a tool whose whole pitch is not making unsupported claims."""
    if mode == QUIESCED:
        return f"quiesced — host asserts verified by measure_wrap ({detail})"
    if detail == FORCED_PORTABLE:
        return ("portable measurement — INDICATIVE, not decision-grade. Measurement was forced to "
                "portable by --rig portable, so the host's quiesced state (whatever it is) was "
                "not used or verified. Correctness guarantees are unaffected; timing may drift "
                "with system load.")
    return ("portable measurement — INDICATIVE, not decision-grade. The host could not be "
            f"verified as quiesced ({detail}). Correctness guarantees are unaffected; timing may "
            "drift with system load.")
