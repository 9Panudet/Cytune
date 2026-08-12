"""A-3g: exact power at the ACHIEVED per-cell n, from the COMMITTED generator — never interpolated.

PREREG §12 A-3g, verbatim: "report-time power per confirmatory cell is computed by the COMMITTED
generator `scripts/power/clustered_power_preview.py::power(n, δ=0.4, rng)` at N_SIM=60,000 with the
committed extended-scan stream (SEED_EXT=20260628), run in the pinned container — never
hand-interpolated."

This script is the mechanism for that clause. It imports the committed `power` and the committed
constants (it does NOT restate them — a copied constant is a constant that can drift), evaluates
every achieved n it is given, and writes results/fleet/exact_power.json for report_p2.py to read.
No n is ever hardcoded here: they come from the survival ledger's MEASURED cells.

Runs in the pinned image (needs numpy/scipy, which the host does not have):

  podman run --rm --security-opt label=disable -v "$PWD":/w -w /w localhost/motifbo-env:phase1 \
      python3 scripts/phasep/exact_power.py

N_SIM=60,000 per n at ~9 cells is minutes of CPU — it must NOT overlap a measurement (CF-1).
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "scripts", "power"))

import clustered_power_preview as cpp          # noqa: E402  THE committed generator
import run_fleet as rf                         # noqa: E402  for the cell rule + ledger reader

DELTA = 0.4                                    # PREREG §2 floor MDE
OUT = os.path.join(REPO, "results", "fleet", "exact_power.json")


def _busy():
    r = subprocess.run(["bash", os.path.join(REPO, "scripts", "hooks", "campaign_busy.sh")],
                       capture_output=True, text=True)
    return r.returncode == 0, (r.stdout or "").strip()


def feas_arm_n(ledger_path, conformant):
    """A-2g rider R1: the FEAS on/off contrast arms, over the TRAINING set. The contrast is a
    POOLED test across cells, so its n is the arm size, not a per-cell count. `conformant`
    applies PREREG §4 (agreement_fail excluded from per-class inference)."""
    pos = neg = 0
    if os.path.exists(ledger_path):
        for l in open(ledger_path):
            e = json.loads(l)
            if (e.get("status") != "ACCEPTED" or e.get("holdout")
                    or e.get("dataset", "synthetic") == "R"):
                continue
            if conformant and e.get("agreement_ok") is False:
                continue
            if e.get("flag_FEAS"):
                pos += 1
            else:
                neg += 1
    return {"FEAS+": pos, "FEAS-": neg}


def achieved_n(ledger_path):
    """MEASURED cell counts, straight from the append-only ledger.

    Both views are emitted and the report must quote the CONFORMANT one for any inferential
    claim: `as_measured` is every ACCEPTED kernel; `conformant` drops the `agreement_fail`
    kernels that PREREG §4 excludes from per-class inference. Reporting power at the
    as-measured n would overstate the power of an inference that will never use those rows."""
    return {
        "training": dict(rf._cell_counts(ledger_path, holdout=False)),
        "training_conformant": dict(rf._cell_counts(ledger_path, holdout=False, conformant=True)),
        "holdout_H": dict(rf._cell_counts(ledger_path, holdout=True)),
        "holdout_H_conformant": dict(rf._cell_counts(ledger_path, holdout=True, conformant=True)),
        "feas_contrast": feas_arm_n(ledger_path, conformant=False),
        "feas_contrast_conformant": feas_arm_n(ledger_path, conformant=True),
    }


def main():
    import numpy as np
    if "--allow-busy" not in sys.argv:
        busy, why = _busy()
        if busy:
            raise SystemExit(f"CF-1: box is BUSY ({why}) — power sims must not overlap a measurement")
    ledger = os.path.join(REPO, "results", "fleet", "fleet_ledger.jsonl")
    ach = achieved_n(ledger)
    ns = sorted({n for grp in ach.values() for n in grp.values() if n and n > 0})
    t0 = time.time()
    table = {}
    for n in ns:
        # A fresh generator per n, seeded from the COMMITTED extended-scan stream, so the value for
        # a given n does not depend on which other n's this run happened to evaluate.
        rng = np.random.default_rng(cpp.SEED_EXT)
        table[str(n)] = round(float(cpp.power(n, DELTA, rng, n_sim=cpp.N_SIM_THRESH)), 5)
        print(f"  n={n:3d} -> power={table[str(n)]:.5f}", flush=True)
    out = {
        "spec": "PREREG §12 A-3g",
        "generator": {"source": "scripts/power/clustered_power_preview.py::power",
                      "delta": DELTA, "n_sim": cpp.N_SIM_THRESH, "seed": cpp.SEED_EXT,
                      "alpha": cpp.ALPHA,
                      "test": "paired one-sided Wilcoxon signed-rank (alternative='less')"},
        "floor_n": rf.FLOOR_N, "floor_power_target": 0.80,
        "achieved_n": ach,
        "power_by_n": table,
        "elapsed_s": round(time.time() - t0, 1),
        "recompute": ("podman run --rm --security-opt label=disable -v \"$PWD\":/w -w /w "
                      "localhost/motifbo-env:phase1 python3 scripts/phasep/exact_power.py"),
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nexact power -> {OUT}  ({out['elapsed_s']}s)")


if __name__ == "__main__":
    main()
