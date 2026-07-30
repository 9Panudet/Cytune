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
# were both caused by a rule existing in more than one place.
_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
_AUDIT = "/repo/scripts/phasep/sanitizer_spot_audit.py"
IMAGE = "localhost/motifbo-env:phase1"

_SNIPPET = """
import json, os, subprocess, sys, tempfile
sys.path.insert(0, '/repo/scripts/phasep')
sys.path.insert(0, '/repo/src')
import sanitizer_spot_audit as S, theta
from motifbo.build.profiles import sanitizer_runtime_env
asan = subprocess.run(['gcc', '-print-file-name=libasan.so'],
                      capture_output=True, text=True).stdout.strip()
env = {**os.environ, **sanitizer_runtime_env(asan)}
env['PYTHONDONTWRITEBYTECODE'] = '1'
kdir = sys.argv[1]
cid = int(sys.argv[2])
work = tempfile.mkdtemp()
b = S._sanitizer_build(kdir, theta.config_of(cid), os.path.join(work, 'c'),
                       os.path.join(work, 'so'), 'kernel')
if not b['ok']:
    print(json.dumps({'ran': True, 'clean': None, 'verdict': 'BUILD_FAIL',
                      'reason': b['reason'], 'log': b.get('log', '')[-400:]}))
    raise SystemExit(0)
p = subprocess.run([sys.executable, '/repo/scripts/phasep/san_child.py', kdir, b['so_path'],
                    '3', '20260730', '--module', b['module']],
                   capture_output=True, text=True, env=env, timeout=900)
blob = p.stdout + p.stderr
tokens = sorted({t for t in S.SAN_TOKENS if t in blob})
if tokens:
    v, clean = 'SANITIZER_REPORT', False
elif p.returncode != 0 or 'SAN_CHILD_OK' not in p.stdout:
    v, clean = 'RUN_FAIL_NO_TOKEN', None
else:
    v, clean = 'CLEAN', True
print(json.dumps({'ran': True, 'clean': clean, 'verdict': v, 'tokens': tokens,
                  'returncode': p.returncode,
                  'stderr_excerpt': '' if clean else blob[-1200:]}))
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
    if not available():
        return {"ran": False, "clean": None, "verdict": "IMAGE_UNAVAILABLE",
                "note": f"pinned image {IMAGE} not present; the §1.4 gate did NOT run. This is "
                        f"not a pass — the emit decision rests on the oracle alone."}
    cmd = ["podman", "run", "--rm", "--security-opt", "label=disable",
           "-v", f"{_REPO}:/repo:ro", "-v", f"{os.path.abspath(kernel_dir)}:/kdir:ro",
           "-e", "PYTHONPATH=/repo/src", IMAGE,
           "python3", "-c", _SNIPPET, "/kdir", str(config_id)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ran": False, "clean": None, "verdict": "TIMEOUT",
                "note": f"the §1.4 gate exceeded {timeout}s and did NOT complete. Not a pass."}
    for line in reversed((r.stdout or "").strip().splitlines()):
        if line.startswith("{"):
            try:
                out = json.loads(line)
                out["config_id"] = config_id
                out["rule"] = ("roadmap §1.4 / PREREG §301 — an ASan+UBSan report makes the "
                               "candidate infeasible regardless of whether its output was correct")
                return out
            except json.JSONDecodeError:
                continue
    return {"ran": False, "clean": None, "verdict": "HARNESS_ERROR",
            "note": (r.stderr or "")[-400:] or "no JSON on stdout", "config_id": config_id}


def rejects(result):
    """Does this gate result FORBID emitting the config? Only a positive sanitizer report does.

    A gate that did not run does not reject — it degrades the guarantee, and the certificate says
    so. Making a non-run into a rejection would make the product unusable wherever the pinned image
    is absent; making it into a pass would be the D23 lapse rebuilt on purpose. Neither: it is
    recorded as what it is."""
    return bool(result) and result.get("verdict") == "SANITIZER_REPORT"
