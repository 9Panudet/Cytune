"""D23 remediation — the §1.4 sanitizer verdict, applied as an OVERLAY over the frozen tables.

WHAT HAPPENED. The `trap_wrap` feasibility variant plants an out-of-bounds read: the driver passes
`guard=1`, the kernel computes `j = i - off` with `off=1`, and reads `a[-1]`. Under a typed
memoryview with `wraparound=False` that index does NOT wrap — it reads before the buffer. Under
`boundscheck=True` Cython raises IndexError first, and under `wraparound=True` the index wraps
in-bounds and is well defined. So the UB-executing set is exactly

    {config : boundscheck=False AND wraparound=False}   -> 432 of the 1,728 configs

per armed trap kernel. That was the DESIGN: the trap is what makes the directive pair a
correctness lever. The oracle was expected to catch it, and for 76 of the 79 armed kernels it did
— all 432 UB configs are recorded infeasible.

For THREE kernels it did not. `int_min32` / `int_max32` are min/max reductions: reading one garbage
value before the buffer and dropping `a[n-1]` changes the answer only if the garbage is more
extreme than the true extremum or the dropped element WAS the extremum. Over 16k-49k random int32
samples that essentially never happens, so the output matched the golden and the oracle passed —
432/432 UB configs recorded FEASIBLE, in each of the three. ASan reports a heap-buffer-overflow on
every one of them. The oracle is an OUTPUT check; it cannot see a read that produced a correct
answer. That is precisely why roadmap §1.4 makes the sanitizer a SEPARATE gate — and that gate was
never invoked by the fleet harness.

WHY AN OVERLAY AND NOT AN EDIT. `FREEZE_MANIFEST.json` is write-once and carries a sha256 per
`table.jsonl`. The measurements in those rows are real and are not in question — the timing is what
the rig measured. What is wrong is the FEASIBILITY LABEL. So the raw stays byte-identical and this
file records the correction on top of it, with its reason. Every consumer (classification, replay,
routing, the CLI) applies the overlay; nothing rewrites history.

The overlay is derived MECHANICALLY from the committed specs + `theta`, never hand-listed: a cell
is overlaid iff its kernel is an armed `trap_wrap` kernel, its config is in the UB set, and the
table currently records it feasible. Run it twice and it produces the same file.

  podman run --rm --security-opt label=disable -v "$PWD":/w -w /w -e PYTHONPATH=/w/src \\
      localhost/motifbo-env:phase1 python3 scripts/phasep/san_overlay.py
"""
from __future__ import annotations
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import theta                                             # noqa: E402

FLEET = os.path.join(REPO, "results", "fleet")
KROOT = os.path.join(FLEET, "_kernels")
OUT = os.path.join(FLEET, "SANITIZER_INFEASIBLE_OVERLAY.json")
REASON = "sanitizer_oob (§1.4): trap_wrap reads a[-1] with boundscheck=False, wraparound=False"


def ub_config_ids():
    """The UB-executing configs of an ARMED trap_wrap kernel. Derived from theta, not listed."""
    return sorted(cid for cid in range(theta.N_CONFIGS)
                  if theta.config_of(cid)[0] is False and theta.config_of(cid)[1] is False)


def armed_trap_kernels():
    """Kernels whose spec is trap_wrap AND whose driver actually passes a non-None guard.
    An unarmed trap kernel executes no UB and must not be overlaid."""
    out = []
    for kid in sorted(os.listdir(KROOT)):
        sp = os.path.join(KROOT, kid, "spec.json")
        drv = os.path.join(KROOT, kid, "driver.py")
        if not (os.path.exists(sp) and os.path.exists(drv)):
            continue
        if json.load(open(sp)).get("feas_variant") != "trap_wrap":
            continue
        if ", 1)" not in open(drv).read():          # generator emits `, 1)` armed / `, None)` not
            continue
        out.append(kid)
    return out


def build():
    import a2_reclassify as a2                  # numpy — kept out of module scope so `load()`
    ub = set(ub_config_ids())                   # stays importable by the numpy-free callers
    kernels, n_cells, n_tables, corrected = {}, 0, 0, {}
    for kid in armed_trap_kernels():
        t = os.path.join(FLEET, kid, "table.jsonl")
        if not os.path.exists(t):
            continue
        n_tables += 1
        flip = [json.loads(l)["config_id"] for l in open(t)
                if (r := json.loads(l)).get("config_id") in ub and r.get("feasible") == 1]
        if flip:
            kernels[kid] = sorted(flip)
            n_cells += len(flip)
            kd = os.path.join(FLEET, kid)
            b, a = a2.reclassify(kd), a2.reclassify(kd, overlay=set(flip))
            corrected[kid] = {
                "class_before": b["v2_class"], "class_after": a["v2_class"],
                "delta_all_before": b["delta_all"], "delta_all_after": a["delta_all"],
                "delta_strict_before": b["delta_strict"], "delta_strict_after": a["delta_strict"],
                "if_strict_before": b["if_strict"], "if_strict_after": a["if_strict"],
                "infeasible_frac_before": b["infeasible_frac"],
                "infeasible_frac_after": a["infeasible_frac"],
                "flag_FM_after": a["flag_FM"], "flag_FEAS_after": a["flag_FEAS"],
            }
            with open(os.path.join(kd, "class_v2_san.json"), "w") as f:
                json.dump(a, f, indent=1)
    voided = endpoint_voided(kernels)
    return {
        "corrected_class": corrected,
        "endpoint_voided": voided,
        "schema": "phasep-sanitizer-infeasible-overlay-v1",
        "defect": "D23",
        "rule": "roadmap §1.4 — an ASan/UBSan report makes the candidate infeasible, independently "
                "of the oracle. Correctness absolute.",
        "reason": REASON,
        "derivation": "armed trap_wrap kernels × {boundscheck=False ∧ wraparound=False} × "
                      "currently-recorded-feasible; computed from spec.json + driver.py + theta",
        "ub_configs_per_kernel": len(ub),
        "n_configs_total": theta.N_CONFIGS,
        "armed_trap_kernels_with_tables": n_tables,
        "n_kernels_affected": len(kernels),
        "n_cells_overlaid": n_cells,
        "evidence": "results/sanitize/phasep_spot_audit/spot_audit.json (ASan heap-buffer-overflow "
                    "confirmed on each affected kernel at both checks-off corners); controls in "
                    "controls.json",
        "raw_untouched": "table.jsonl files are byte-identical; FREEZE_MANIFEST sha256 still "
                         "verifies. Only the FEASIBILITY LABEL is corrected, here, on top.",
        "kernels": kernels,
        "recompute": ("podman run --rm --security-opt label=disable -v \"$PWD\":/w -w /w "
                      "-e PYTHONPATH=/w/src localhost/motifbo-env:phase1 python3 "
                      "scripts/phasep/san_overlay.py"),
    }


def endpoint_voided(kernels):
    """Kernels whose ENDPOINT tier is entirely inside the overlay — found by the measurement-auditor.

    The endpoint tier re-measures the screen's top decile. For a kernel whose speed advantage WAS
    the out-of-bounds read, that top decile is exactly the UB set, so after the overlay not one
    endpoint-measured config survives. Its `agreement_binary_ok` — "does the screen argmin land
    within 2% of the endpoint argmin" — then describes a landscape the product is forbidden to
    emit. The bit is not FALSE and not TRUE; it is **not evaluable**, and cannot be recomputed
    without re-measuring the surviving decile.

    Returns {kernel_id: {measured, surviving, ...}} for kernels with `surviving == 0`."""
    out = {}
    for kid, cids in kernels.items():
        p = os.path.join(FLEET, kid, "endpoint.json")
        if not os.path.exists(p):
            continue
        ep = json.load(open(p))
        ids = [int(c) for c in ep.get("endpoints", {})]
        ub = set(cids)
        surviving = [c for c in ids if c not in ub]
        if ids and not surviving:
            out[kid] = {
                "endpoint_measured": len(ids), "surviving": 0,
                "screen_argmin": ep.get("screen_argmin"),
                "endpoint_argmin": ep.get("endpoint_argmin"),
                "screen_argmin_in_ub": ep.get("screen_argmin") in ub,
                "endpoint_argmin_in_ub": ep.get("endpoint_argmin") in ub,
                "committed_agreement_binary_ok": ep.get("agreement_binary_ok"),
                "ruling": "NOT EVALUABLE — excluded from per-class inference alongside "
                          "agreement_fail (PREREG §4's consequence, for a reason §4 does not name)",
            }
    return out


def voided_kernels(fleet=FLEET):
    """Kernel ids whose agreement bit is not evaluable post-overlay. Excluded from per-class
    inference: a check that could not be performed is not a check that passed."""
    o = _read(fleet)
    return set((o or {}).get("endpoint_voided", {}))


def _read(fleet):
    p = os.path.join(fleet, "SANITIZER_INFEASIBLE_OVERLAY.json")
    return json.load(open(p)) if os.path.exists(p) else None


def load(fleet=FLEET):
    """{kernel_id: set(config_id)} — the cells whose feasible bit is forced to 0. Empty if the
    overlay has not been generated (callers must treat that as 'not yet remediated', not 'clean')."""
    o = _read(fleet)
    return {k: set(v) for k, v in o["kernels"].items()} if o else {}


def corrected_classes(fleet=FLEET):
    """{kernel_id: v2_class} for kernels whose class CHANGED once §1.4 was applied. This is what
    makes the correction reach the cell counts: the append-only ledger still carries the
    uncorrected `measured_v2` (history is not rewritten), so every consumer of the cell rule
    consults this map instead of trusting the ledger field."""
    o = _read(fleet)
    if not o:
        return {}
    return {k: v["class_after"] for k, v in o.get("corrected_class", {}).items()
            if v["class_after"] != v["class_before"]}


def main():
    o = build()
    with open(OUT, "w") as f:
        json.dump(o, f, indent=1)
    print(f"overlay: {o['n_cells_overlaid']} (kernel,config) cells across "
          f"{o['n_kernels_affected']} kernels "
          f"(of {o['armed_trap_kernels_with_tables']} armed trap kernels, "
          f"{o['ub_configs_per_kernel']} UB configs each) -> {OUT}")
    for k, v in o["kernels"].items():
        print(f"  {k}: {len(v)} cells")


if __name__ == "__main__":
    main()
