"""A3 — FREEZE_MANIFEST v2: the same frozen set, plus the CONFORMANCE FLAGS that say what each
kernel may be used FOR.

v1 answered "is this kernel in the frozen set, and is its table the one we froze" (sha256, write-
once). It could not answer "may this kernel's rows enter per-class inference", and by P-2 that
question has four different answers for four different reasons. Downstream code was making the
call ad hoc, which is how a memo threshold ended up governing a floor verdict (D22).

FLAGS (a kernel carries all that apply; `conformant` means none of the restricting ones do):

  conformant          — usable for per-class inference. The default.
  descriptive-only    — PREREG §4: `agreement_binary_ok` is False. Excluded from per-class
                        inference, retained and reported. Unconditional, no threshold.
  sanitizer-corrected — D23/A-9: the §1.4 overlay changed this kernel's feasibility labels, and
                        its class. The CORRECTED class is authoritative; the ledger's
                        `measured_v2` is history.
  directive-partial   — DEV-3: in-source Cython directives are not stripped, so 3-4 search axes
                        are inert. Excluded from directive-effect inference and from
                        routing-acceptance rows; retained as a runtime/FEAS anchor.
  scale-band-deviation— DEV-4: reference time outside the pre-registered 50-80 ms golden band.
                        Rows stand (CI + determinism gates passed); cross-anchor comparisons carry
                        the caveat.

v2 does NOT re-freeze anything: it reads v1's sha256 set, VERIFIES it still matches the tables on
disk, and adds the flag layer. A hash mismatch is fatal — it would mean the raw moved under the
freeze, which is the one thing the write-once manifest exists to prevent.

  podman run --rm --security-opt label=disable -v "$PWD":/w -w /w -e PYTHONPATH=/w/src \\
      localhost/motifbo-env:phase1 python3 scripts/phasep/freeze_manifest_v2.py
"""
from __future__ import annotations
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import run_fleet as rf                                     # noqa: E402 — THE cell rule
import san_overlay                                         # noqa: E402

FLEET = os.path.join(REPO, "results", "fleet")
OUT = os.path.join(FLEET, "FREEZE_MANIFEST_V2.json")

# DEV-3 / DEV-4 — named here because they are per-anchor facts established by inspection, not
# derivable from any committed field. Each carries its register entry so the flag is traceable.
DIRECTIVE_PARTIAL = {"fleet_R_05_ppoly": "DEV-3", "fleet_R_06_floyd": "DEV-3"}
SCALE_BAND_DEVIATION = {"fleet_R_04_binning": "DEV-4"}


def _sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def build():
    v1 = json.load(open(os.path.join(FLEET, "FREEZE_MANIFEST.json")))
    hman_p = os.path.join(FLEET, "H_MANIFEST.json")
    hman = json.load(open(hman_p)) if os.path.exists(hman_p) else None
    overlay = san_overlay.load(FLEET)
    corrected = san_overlay.corrected_classes(FLEET)

    led = [json.loads(l) for l in open(os.path.join(FLEET, "fleet_ledger.jsonl"))]
    acc = {e["kernel_id"]: e for e in led if e.get("status") == "ACCEPTED"}

    kernels, drift, counts = {}, [], {}
    for kid, ent in sorted(acc.items()):
        t = os.path.join(FLEET, kid, "table.jsonl")
        if not os.path.exists(t):
            continue
        rec = (v1.get("kernels") or {}).get(kid) or {}
        want = rec.get("table_sha256")
        got = _sha256(t)
        if want and want != got:
            drift.append({"kernel_id": kid, "frozen": want, "on_disk": got})

        flags = []
        if ent.get("agreement_ok") is False:
            flags.append("descriptive-only")
        if kid in overlay:
            flags.append("sanitizer-corrected")
        if kid in DIRECTIVE_PARTIAL:
            flags.append("directive-partial")
        if kid in SCALE_BAND_DEVIATION:
            flags.append("scale-band-deviation")
        restricting = {"descriptive-only", "directive-partial"}
        if not (restricting & set(flags)):
            flags.insert(0, "conformant")

        role = ("R-anchor" if ent.get("dataset") == "R"
                else "holdout-H" if ent.get("holdout") else "training")
        kernels[kid] = {
            "role": role,
            "in_v1_freeze": kid in (v1.get("kernels") or {}),
            "table_sha256": got,
            "flags": flags,
            "cell": rf._cell_of(ent),
            "cell_uncorrected": ("FLAT+FM" if (ent.get("measured_v2") == "FLAT"
                                               and ent.get("flag_FM")) else ent.get("measured_v2")),
            "agreement_binary_ok": ent.get("agreement_ok"),
            "provenance": ent.get("provenance"),
            "wave": ent.get("wave"),
            "flag_FM": ent.get("flag_FM"), "flag_FEAS": ent.get("flag_FEAS"),
            "sanitizer_cells_overlaid": len(overlay.get(kid, ())) or None,
            "class_corrected_to": corrected.get(kid),
            "deviation_ref": DIRECTIVE_PARTIAL.get(kid) or SCALE_BAND_DEVIATION.get(kid),
        }
        for f in flags:
            counts[f] = counts.get(f, 0) + 1

    return {
        "schema": "phasep-freeze-manifest-v2",
        "supersedes": "FREEZE_MANIFEST.json (v1) — NOT replaced; v1 stays write-once and its "
                      "sha256 set is verified here, byte-for-byte",
        "adds": "conformance flags: what each kernel may be USED FOR, which v1 could not express",
        "classifier": v1.get("classifier") or v1.get("classifier_sha256"),
        "e4_alignment": "results/fleet/E4_ALIGNMENT_EVIDENCE.json (integer FEAS form, A-2h/E4)",
        "sanitizer_overlay": "results/fleet/SANITIZER_INFEASIBLE_OVERLAY.json (D23 / A-9)",
        "deviations": "results/fleet/DEVIATIONS_REGISTER.md",
        "flag_definitions": {
            "conformant": "usable for per-class inference",
            "descriptive-only": "PREREG §4 agreement_fail — excluded from per-class inference",
            "sanitizer-corrected": "D23/A-9 — §1.4 overlay changed feasibility labels and class",
            "directive-partial": "DEV-3 — in-source directives leave 3-4 axes inert; excluded from "
                                 "directive-effect inference and routing-acceptance rows",
            "scale-band-deviation": "DEV-4 — reference outside the 50-80 ms band; rows stand",
        },
        "n_v1_frozen": v1.get("n_kernels"),
        "n_h_manifest": (hman or {}).get("n_kernels"),
        "n_kernels": len(kernels),
        "flag_counts": counts,
        "hash_drift": drift,
        "hash_drift_is_fatal": True,
        "kernels": kernels,
        "recompute": ("podman run --rm --security-opt label=disable -v \"$PWD\":/w -w /w "
                      "-e PYTHONPATH=/w/src localhost/motifbo-env:phase1 python3 "
                      "scripts/phasep/freeze_manifest_v2.py"),
    }


def main():
    m = build()
    if m["hash_drift"]:
        for d in m["hash_drift"]:
            print(f"  HASH DRIFT {d['kernel_id']}: frozen {d['frozen'][:12]} != "
                  f"on-disk {d['on_disk'][:12]}")
        raise SystemExit("FATAL: the frozen raw moved under the manifest — refusing to write v2")
    with open(OUT, "w") as f:
        json.dump(m, f, indent=1)
    print(f"FREEZE_MANIFEST_V2: {m['n_kernels']} kernels, v1 hashes VERIFIED (0 drift)")
    for k, v in sorted(m["flag_counts"].items()):
        print(f"  {k:22s} {v}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
