"""`--apply` — write the emitted directive header into the .pyx, instead of hand-transcribing it.

Hand-transcribing five booleans from a terminal into a source file is a place to make a silent
mistake, and the mistake that matters is transcribing `boundscheck=False` onto a kernel whose
faster config was refused for reading out of bounds. So this module has one job and one refusal:

  APPLIES only a certificate whose verdict is `improvement` and whose emitted config passed the
  §1.4 sanitizer gate CLEANLY. Not "did not report" — CLEAN. A gate that could not run leaves
  `clean = None`, and None is not a pass; applying on that basis would be D23 rebuilt at the last
  possible step, with the tool's own hand on the keyboard.

Never writes to the user's file unless they ask for it twice: `--apply` writes a sibling copy,
`--apply --in-place` edits the original.
"""
from __future__ import annotations
import difflib
import os
import re

HEADER_RE = re.compile(r"^\s*#\s*cython\s*:", re.IGNORECASE)


class ApplyRefused(RuntimeError):
    pass


def check_applicable(cert):
    """Raise ApplyRefused with a reason a user can act on, or return None."""
    v = cert.get("verdict")
    if v != "improvement":
        raise ApplyRefused(
            f"nothing to apply — the verdict is {v!r}, so the recommendation IS your existing "
            f"reference configuration. Applying it would change nothing."
            + ("\n  A faster configuration was found and refused; see the certificate."
               if cert.get("winner_rejection") else ""))
    if cert.get("winner_rejection"):
        raise ApplyRefused("refusing to apply: this run rejected a candidate at verify. "
                           "Read the certificate before changing your source.")
    gate = cert.get("sanitizer_gate") or {}
    if gate.get("image_overridden"):
        raise ApplyRefused(
            f"refusing to apply: the §1.4 gate ran against {gate.get('image')!r}, which is NOT the "
            f"pinned image (CYTUNE_SANITIZER_IMAGE is set).\n"
            f"  A clean result from an unpinned image is not a pass — cytune has no way to know "
            f"that image runs the same sanitizer rig.\n"
            f"  Unset CYTUNE_SANITIZER_IMAGE and re-run.")
    if gate.get("ran") is False and gate.get("clean") is True:
        raise ApplyRefused(
            f"refusing to apply: the §1.4 gate reports clean=True but says it did "
            f"NOT run (ran=False).\n"
            f"  A gate that did not run cannot be clean. That combination means the verdict "
            f"describes nothing,\n"
            f"  and none of the checks that tie a gate to a configuration are performed for it.\n"
            f"  This is a cytune defect if you see it — please report the certificate.")
    if gate.get("authoritative") is False:
        raise ApplyRefused(
            f"refusing to apply: the §1.4 gate did not attest which source tree it built, so "
            f"cytune cannot\n"
            f"  tie its CLEAN verdict to the code you are about to change.\n"
            f"  {gate.get('warning', '')}")
    if gate.get("clean") is not True:
        raise ApplyRefused(
            f"refusing to apply: the §1.4 sanitizer gate on the emitted config is "
            f"{gate.get('verdict')} (clean={gate.get('clean')!r}), not CLEAN.\n"
            f"  NOT RUN IS NOT A PASS. --apply writes checks-off directives into your source; "
            f"cytune will not do that on a config whose memory safety was never confirmed.\n"
            f"  Fix the environment (`cytune doctor`) and re-run, or apply the header by hand "
            f"having read the certificate.")
    return None


def rewrite_source(text, header):
    """Return (new_text, action). Replaces an existing `# cython:` line, else inserts one."""
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if HEADER_RE.match(line):
            lines[i] = header + "\n"
            return "".join(lines), "replaced"
    # Insert after a shebang and/or coding line, before anything else.
    at = 0
    if lines and lines[0].startswith("#!"):
        at = 1
    if len(lines) > at and "coding" in lines[at] and lines[at].lstrip().startswith("#"):
        at += 1
    lines.insert(at, header + "\n")
    return "".join(lines), "inserted"


def apply_to(pyx_path, cert, in_place=False):
    """Write the emitted directive header. Returns a record of what happened."""
    check_applicable(cert)
    header = cert["emitted_config"]["directive_header"]
    with open(pyx_path) as f:
        original = f.read()
    new, action = rewrite_source(original, header)
    if in_place:
        target = pyx_path
        backup = pyx_path + ".cytune-backup"
        if not os.path.exists(backup):
            with open(backup, "w") as f:
                f.write(original)
    else:
        root, ext = os.path.splitext(pyx_path)
        target = f"{root}.tuned{ext}"
        backup = None
    diff = unified_diff(original, new, pyx_path, target)
    with open(target, "w") as f:
        f.write(new)
    return {"applied": True, "target": target, "action": action, "header": header,
            "backup": backup, "in_place": bool(in_place), "diff": diff}


def unified_diff(original, new, from_path, to_path):
    """What `--apply` is about to change, in the form everyone already reads.

    `--apply` writes checks-off directives into source code. Reporting only "APPLIED: replaced the
    directive header" tells a user that something happened, not what — and the one edit that
    matters most (an existing `# cython:` line being REPLACED, silently discarding whatever the
    author had deliberately set there) is invisible in that wording.
    """
    return "".join(difflib.unified_diff(
        original.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile=from_path, tofile=to_path, n=2))


def build_snippet(cert):
    """A ready-to-paste setup.py fragment, so the GCC flags are not hand-transcribed either."""
    e = cert["emitted_config"]
    gcc = e["gcc_flags"].split()
    port = cert.get("portability") or {}
    warn = ("\n# WARNING: -march=native hard-codes THIS machine's ISA. See the certificate's\n"
            "# PORTABILITY WARNING before shipping a binary built with these flags.\n"
            if not port.get("portable", True) else "")
    return (
        f"# --- generated by cytune {cert.get('cytune_version', '')} for {cert['module']} ---\n"
        f"{warn}"
        f"from setuptools import setup, Extension\n"
        f"from Cython.Build import cythonize\n\n"
        f"CYTHON_DIRECTIVES = {_directives_dict(e['directive_header'])!r}\n"
        f"EXTRA_COMPILE_ARGS = {gcc!r}\n\n"
        f"setup(ext_modules=cythonize(\n"
        f"    [Extension('{cert['module']}', ['{cert['module']}.pyx'],\n"
        f"               extra_compile_args=EXTRA_COMPILE_ARGS)],\n"
        f"    compiler_directives=CYTHON_DIRECTIVES))\n")


def _directives_dict(header):
    body = header.split(":", 1)[1]
    out = {}
    for part in body.split(","):
        if "=" not in part:
            continue
        k, v = (x.strip() for x in part.split("=", 1))
        out[k] = (v == "True") if v in ("True", "False") else v
    return out
