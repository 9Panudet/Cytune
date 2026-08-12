"""Frozen-fleet loader for the DOE-v2 evaluation. Same two guards the study uses, same order.

FREEZE GUARD then OVERLAY, never one without the other. The hash proves the raw table has not
moved since the P-2 freeze; the §1.4 sanitizer overlay then corrects the feasibility LABEL on top
of it (D23 / amendment A-9). Loading a table without the overlay would let a variant "win" by
optimising into a config that reads out of bounds — the exact failure D23 already cost this project
once. `assert_overlay_present` refuses to run if the verdict file is missing, because "no overlay
file" must never quietly mean "nothing to correct".

The SPLIT comes from FREEZE_MANIFEST_V2's `role` field, which was written at the freeze:
  training (129)  — development data, already seen, tuned on
  holdout-H (11)  — confirmatory, synthetic
  R-anchor (9)    — confirmatory, REAL code, and what the product actually runs on
Reported separately, never pooled (PREREG_DOE_V2 §4).
"""
from __future__ import annotations

import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FLEET = os.path.join(ROOT, "results", "fleet")
MANIFEST = os.path.join(FLEET, "FREEZE_MANIFEST_V2.json")
OVERLAY = os.path.join(FLEET, "SANITIZER_INFEASIBLE_OVERLAY.json")


class FreezeViolation(Exception):
    pass


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest():
    if not os.path.exists(MANIFEST):
        raise FreezeViolation(f"FREEZE GUARD: no {MANIFEST}")
    return json.load(open(MANIFEST))


def overlay():
    if not os.path.exists(OVERLAY):
        raise FreezeViolation(
            "SANITIZER GUARD: no SANITIZER_INFEASIBLE_OVERLAY.json — roadmap §1.4's verdict has "
            "not been computed. (D23: the oracle passed 1,296 configs that read out of bounds.)")
    o = json.load(open(OVERLAY))
    return {k: set(v) for k, v in o["kernels"].items()}


def load_table(kid, man=None, ov=None):
    """Hash-verified, overlay-applied {config_id: (feasible, median_ns|None, reason)}."""
    man = man or manifest()
    ov = overlay() if ov is None else ov
    path = os.path.join(FLEET, kid, "table.jsonl")
    want = man["kernels"][kid]["table_sha256"]
    got = _sha(path)
    if got != want:
        raise FreezeViolation(f"FREEZE GUARD: {kid} table hash {got[:12]}… != frozen {want[:12]}…")
    forced = ov.get(kid, set())
    tbl = {}
    for line in open(path):
        r = json.loads(line)
        cid = r["config_id"]
        feas = bool(r.get("feasible")) and cid not in forced
        reason = ("sanitizer_oob" if (cid in forced and r.get("feasible"))
                  else r.get("reason", "ok"))
        med = r["screen"]["median_ns"] if (feas and r.get("screen")) else None
        tbl[cid] = (feas, med, reason)
    return tbl


ROLES = ("training", "holdout-H", "R-anchor")


def roster(man=None):
    """{role: [(kernel_id, cell)]} for every kernel with a table on disk."""
    man = man or manifest()
    out = {r: [] for r in ROLES}
    for kid, v in sorted(man["kernels"].items()):
        if not os.path.exists(os.path.join(FLEET, kid, "table.jsonl")):
            continue
        out.setdefault(v["role"], []).append((kid, v["cell"]))
    return out
