"""A-3 basis artifact — final wave-1 producer/non-producer analysis (committed, recomputable).

Recomputes, from the ledger + per-kernel class_v2.json ONLY, the two tables Amendment A-3's
template selection is drawn from (F2 discipline: confirmatory CELLS, not bare classes):
  1. per (intended_regime, template): measured CELL tally, where the FLAT+FM cell is
     measured_v2 == FLAT AND flag_FM (A-2c: FLAT∧FM− is descriptive-only);
  2. per confirmatory cell: current measured n vs the PREREG §2 n=26 (δ=0.4) floor.
Writes results/fleet/template_analysis_final.json. Recompute: python3 this file.
"""
from __future__ import annotations
import json
import os
import sys

FLEET = sys.argv[1] if len(sys.argv) > 1 else "results/fleet"
FLOOR_N = 26


def cell_of(measured_v2, flag_fm):
    if measured_v2 == "FLAT":
        return "FLAT+FM" if flag_fm else "FLAT&FM- (descriptive)"
    return measured_v2


def main():
    led = [json.loads(l) for l in open(os.path.join(FLEET, "fleet_ledger.jsonl"))]
    acc = [e for e in led if e.get("status") == "ACCEPTED"
           and e.get("dataset", "synthetic") != "R" and not e.get("holdout")]
    by_tmpl, cells = {}, {}
    per_kernel = []
    for e in acc:
        cv = json.load(open(os.path.join(FLEET, e["kernel_id"], "class_v2.json")))
        cell = cell_of(e["measured_v2"], e.get("flag_FM"))
        cells[cell] = cells.get(cell, 0) + 1
        key = f'{e["intended_regime"]}|{e["template"]}'
        by_tmpl.setdefault(key, {}).setdefault(cell, 0)
        by_tmpl[key][cell] += 1
        per_kernel.append({
            "kernel_id": e["kernel_id"], "template": e["template"], "params": e.get("params"),
            "feas_variant": e.get("feas_variant"), "intended_regime": e["intended_regime"],
            "cell": cell, "fm_ratio": cv.get("fm_ratio"), "delta_strict": cv.get("delta_strict"),
            "if_strict": cv.get("if_strict"), "wave": e.get("wave", 1)})
    confirmatory = {c: cells.get(c, 0) for c in ("FLAT+FM", "MID", "LEVER-SEP", "INT")}
    out = {
        "n_accepted_synth": len(acc),
        "cell_definitions": {
            "source": "PREREG §12 A-2c (verbatim): confirmatory families = (regime × budget), "
                      "regimes {FLAT+FM, MID, LEVER-SEP, INT}; FLAT∧FM− is descriptive-only.",
            "FLAT+FM": "measured_v2 == FLAT AND flag_FM (A-2a: FM ⇔ Δ_all/Δ_strict ≥ 1.5)",
            "MID": "measured_v2 == MID", "LEVER-SEP": "measured_v2 == LEVER-SEP",
            "INT": "measured_v2 == INT"},
        "confirmatory_cell_n": confirmatory,
        "floor": {"n": FLOOR_N, "source": "PREREG §2 (δ=0.4, one-sided paired Wilcoxon, 80%)"},
        "shortfall": {c: max(0, FLOOR_N - n) for c, n in confirmatory.items()},
        "descriptive_cells": {c: n for c, n in cells.items()
                              if c not in ("FLAT+FM", "MID", "LEVER-SEP", "INT")},
        "by_intended_template": {k: v for k, v in sorted(by_tmpl.items())},
        "per_kernel": per_kernel,
        "raw": "results/fleet/fleet_ledger.jsonl + results/fleet/<kid>/class_v2.json",
        "recompute": "python3 scripts/phasep/template_analysis.py",
    }
    dst = os.path.join(FLEET, "template_analysis_final.json")
    with open(dst, "w") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {dst}")
    print("confirmatory cell n:", confirmatory, "| shortfall:", out["shortfall"])


if __name__ == "__main__":
    main()
