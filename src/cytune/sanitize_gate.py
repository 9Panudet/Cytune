"""§1.4 SANITIZER GATE for the emitted config — the product half of D23.

WHY THIS EXISTS. D23 found that the Phase-P fleet harness never invoked roadmap §1.4's
ASan+UBSan feasibility gate: ~149 kernels x 1,728 configs were gated on the ORACLE alone. The
oracle is an OUTPUT check, and an output check cannot see a read that produced a correct answer.
On three min/max-reduction kernels it passed 432 configs each that read out of bounds — the whole
13x "speedup" was the removed bounds check on a kernel that then read memory it did not own.

The validation-auditor then found the more serious half (F2): **the same gate was missing from the
product.** `cytune` measures live into its own workspace table and gates feasibility on the oracle
alone, exactly as the fleet harness did. So on a user's kernel with a latent out-of-bounds read
inside a reduction, cytune would reproduce D23 exactly — recommend checks-off, watch the oracle
pass, and emit it. The overlay that fixed the study is structurally incapable of covering this:
it is a correction to frozen tables, and cytune never reads those tables.

WHAT THIS GATE DOES. Before a winner is certified, its ACTUAL config is rebuilt under
ASan+UBSan and the driver is run on it. This is PREREG §301 verbatim — "every reported endpoint
winner additionally gets a full-config sanitizer run" — and it is the emitted config specifically,
not a nearby corner, because the emitted config is the one the user will ship.

A report makes the config INFEASIBLE (§1.4), so it is never emitted; the certificate records the
rejection and cytune falls back exactly as it does for an oracle failure. *Correctness absolute*
is the rule and it does not have an exception for "the output happened to be right".

HONEST LIMIT, stated here so it cannot be overread: ASan detects the memory-safety errors it
detects. A clean gate is evidence that this config does not commit one on THIS input, not a proof
of memory safety. It is strictly more than the oracle alone could tell you, and strictly less than
a proof.
"""
from __future__ import annotations
import json
import os
import subprocess

# Reuses the audited Phase-P rig rather than a second implementation: the same builder, the same
# child, the same token list. A separate copy would be a second thing to keep correct, and D11/D22
# were both caused by a rule existing in more than one place. That rig now lives in
# `cytune/_vendor/` as a byte-pinned copy rather than behind a mount of the study tree, so the
# "same builder, same child, same tokens" property is enforced by test_cytune_vendor.py instead of
# by a path that happens to exist on this machine.
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IMAGE = "localhost/motifbo-env:phase1"
# Overridable so the gate can be pointed at a differently-named build of the same image, and so
# the NOT-RUN path can be exercised end-to-end without deleting anything (T4.19). This CANNOT
# produce a false pass: an unreachable image yields verdict IMAGE_UNAVAILABLE with clean=None,
# `rejects()` is unaffected, and the certificate prints "NOT RUN IS NOT A PASS". The only thing
# it can do is make the guarantee weaker AND SAY SO, which is the whole design.
IMAGE = os.environ.get("CYTUNE_SANITIZER_IMAGE", DEFAULT_IMAGE)


def _resolved_digest():
    from . import rig
    return rig.image_digest(IMAGE)


def is_pinned_image():
    """Is the image this gate will run in the PINNED one — by content, not by name?

    The first fix for H6 compared `IMAGE != DEFAULT_IMAGE`, i.e. the NAME the user asked for. That
    is defeated by `podman tag stub localhost/motifbo-env:phase1`, which costs one command and
    makes the name check pass while the gate runs in the stub. Comparing the digest cannot be
    defeated that way: re-tagging does not change what the image contains.
    """
    from . import rig
    digest = _resolved_digest()
    if digest is None:
        return False
    return digest == rig.PINNED_IMAGE_DIGEST

# How a stranger OBTAINS the image. Cold-user finding F3: the image is a BLOCKING prerequisite,
# `doctor` said "build or load it", and nothing anywhere named the command or the Containerfile.
# That is the second of the two obstacles that made the acceptance verdict "no".
CONTAINERFILE = os.path.abspath(os.path.join(_PKG_DIR, "..", "..", "Containerfile"))
BUILD_COMMAND = f"podman build -f Containerfile -t {IMAGE} ."

def _expected_image_id():
    """The short id `doctor` shows, derived from the one full digest rather than repeated.

    It used to be a second literal. Two spellings of the same pin is how a pin stops being one —
    the same defect as F7's three version strings, on the value that decides whether a sanitizer
    verdict counts.
    """
    from . import rig
    return rig.PINNED_IMAGE_DIGEST.split(":", 1)[-1][:12]


EXPECTED_IMAGE_ID = _expected_image_id()   # the image every number in results/ was measured on

_SNIPPET = """
import json, os, subprocess, sys, tempfile
from cytune._vendor import sanitizer_build as S, theta   # the import also puts _vendor on sys.path
from cytune import binding
from profiles import sanitizer_runtime_env
asan = subprocess.run(['gcc', '-print-file-name=libasan.so'],
                      capture_output=True, text=True).stdout.strip()
env = {**os.environ, **sanitizer_runtime_env(asan)}
env['PYTHONDONTWRITEBYTECODE'] = '1'
kdir = sys.argv[1]
cid = int(sys.argv[2])
# I4.3 — WHAT THIS GATE BUILT FROM, hashed here rather than asserted by the host. A clean verdict
# about a different source tree is not a verdict about the configuration being emitted.
src_sha = binding.tree_sha256(kdir)
work = tempfile.mkdtemp()
b = S._sanitizer_build(kdir, theta.config_of(cid), os.path.join(work, 'c'),
                       os.path.join(work, 'so'), 'kernel')
if not b['ok']:
    print(json.dumps({'ran': True, 'clean': None, 'verdict': 'BUILD_FAIL',
                      'source_tree_sha256': src_sha,
                      'reason': b['reason'], 'log': b.get('log', '')[-400:]}))
    raise SystemExit(0)
san_artifact = binding.sha256_file(b['so_path'])
p = subprocess.run([sys.executable, os.path.join(os.path.dirname(S.__file__), 'san_child.py'),
                    kdir, b['so_path'], '3', '20260730', '--module', b['module']],
                   capture_output=True, text=True, env=env, timeout=900)
blob = p.stdout + p.stderr
tokens = sorted({t for t in S.SAN_TOKENS if t in blob})
if tokens:
    v, clean = 'SANITIZER_REPORT', False
elif p.returncode != 0 or 'SAN_CHILD_OK' not in p.stdout:
    v, clean = 'RUN_FAIL_NO_TOKEN', None
else:
    v, clean = 'CLEAN', True
# The ACTIONABLE half of an ASan report is its HEAD: `ERROR: AddressSanitizer: ...`, the
# `READ of size N at 0x... thread T0`, the stack trace, and `is located N bytes before a
# ... region`. The tail is the shadow-byte map and the legend, which tell a user nothing
# about which line of their kernel is wrong. Taking a fixed slice off the END handed them
# the legend, cut off mid-token. Anchor on the first error marker and take forward.
_MARKS = ('ERROR: AddressSanitizer', 'ERROR: LeakSanitizer', 'ERROR: ThreadSanitizer',
          'runtime error:', 'WARNING: MemorySanitizer')
_at = min([i for i in (blob.find(m) for m in _MARKS) if i >= 0], default=-1)
_head = blob[_at:_at + 6000] if _at >= 0 else blob[:6000]
print(json.dumps({'ran': True, 'clean': clean, 'verdict': v, 'tokens': tokens,
                  'returncode': p.returncode,
                  'source_tree_sha256': src_sha,
                  'sanitizer_artifact_sha256': san_artifact,
                  'stderr_excerpt': '' if clean else _head,
                  'full_output': '' if clean else blob[:60000]}))
"""


def available():
    """Is the pinned image present? A gate that cannot run must say so, never pass by default."""
    r = subprocess.run(["podman", "image", "exists", IMAGE], capture_output=True)
    return r.returncode == 0


def gate(kernel_dir, config_id, timeout=1200):
    """Run the §1.4 gate on ONE config of ONE kernel. Returns a dict that is always safe to embed
    in a certificate.

    `clean` is TRUE / FALSE / None, and None is not a pass. A gate that could not run leaves the
    emit decision to the oracle alone and the certificate must say so — that is precisely the state
    the whole Phase-P campaign was silently in."""
    pinned = is_pinned_image()
    digest = _resolved_digest()
    if not available():
        return {"ran": False, "clean": None, "verdict": "IMAGE_UNAVAILABLE",
                "image": IMAGE, "image_digest": digest, "image_overridden": not pinned,
                "note": f"pinned image {IMAGE} not present; the §1.4 gate did NOT run. This is "
                        f"not a pass — the emit decision rests on the oracle alone."}
    # RUN THE IMAGE WHOSE DIGEST WAS JUST COMPARED, by id. Passing the NAME here left a window in
    # which a `podman tag` could redirect the run after `is_pinned_image()` had already answered —
    # Attack A, which turned the digest pin back into the name pin it replaced.
    from . import rig
    cmd = ["podman", "run", "--rm", "--security-opt", "label=disable",
           "-v", f"{_PKG_DIR}:/opt/cytune/cytune:ro",
           "-v", f"{os.path.abspath(kernel_dir)}:/kdir:ro",
           "-e", "PYTHONPATH=/opt/cytune", rig.image_ref(IMAGE),
           "python3", "-c", _SNIPPET, "/kdir", str(config_id)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ran": False, "clean": None, "verdict": "TIMEOUT",
                "image": IMAGE, "image_digest": digest, "image_overridden": not pinned,
                "note": f"the §1.4 gate exceeded {timeout}s and did NOT complete. Not a pass."}
    for line in reversed((r.stdout or "").strip().splitlines()):
        if line.startswith("{"):
            try:
                out = json.loads(line)
                out["config_id"] = config_id
                # Provenance on the verdict itself. Without it the certificate recorded a CLEAN
                # gate with no record of WHICH image produced it (H6). The DIGEST is the record —
                # the name can be reassigned with `podman tag` and the digest cannot.
                out["image"] = IMAGE
                out["image_digest"] = digest
                out["image_overridden"] = not pinned
                if not pinned and out.get("clean") is True:
                    out["authoritative"] = False
                    out["warning"] = (
                        f"the §1.4 gate ran in image {IMAGE!r} (digest "
                        f"{(digest or 'unresolved')[:19]}), which is NOT the pinned toolchain. A "
                        f"clean result from an unpinned image is NOT treated as a pass: cytune "
                        f"withholds the 'safe' wording and --apply refuses. Re-tagging an image "
                        f"with the pinned name does not change this.")
                out["rule"] = ("roadmap §1.4 / PREREG §301 — an ASan+UBSan report makes the "
                               "candidate infeasible regardless of whether its output was correct")
                return out
            except json.JSONDecodeError:
                continue
    return {"ran": False, "clean": None, "verdict": "HARNESS_ERROR",
            "image": IMAGE, "image_digest": digest, "image_overridden": not pinned,
            "note": (r.stderr or "")[-400:] or "no JSON on stdout", "config_id": config_id}


def is_authoritative(result):
    """Is this gate result a PASS cytune may act on?

    Only a CLEAN result from the PINNED image is. `CYTUNE_SANITIZER_IMAGE` exists so the not-run
    path can be exercised without deleting anything, and the docstring above claimed it "cannot
    produce a false pass". That was wrong, and the adversarial campaign demonstrated it: `gate()`
    parses whatever JSON the image prints on stdout, so a stub image whose `python3` echoes one
    line turns a kernel whose real gate REPORTS into `clean: true`.

    The claim is now true because a clean result from an unpinned image is not treated as a pass:
    the certificate records the image, the "safe" wording is withheld, and `--apply` refuses. The
    override can still make the guarantee weaker and say so; it can no longer manufacture one.
    """
    return bool(result) and result.get("clean") is True and not result.get("image_overridden")


def rejects(result):
    """Does this gate result FORBID emitting the config? Only a positive sanitizer report does.

    A gate that did not run does not reject — it degrades the guarantee, and the certificate says
    so. Making a non-run into a rejection would make the product unusable wherever the pinned image
    is absent; making it into a pass would be the D23 lapse rebuilt on purpose. Neither: it is
    recorded as what it is."""
    return bool(result) and result.get("verdict") == "SANITIZER_REPORT"
