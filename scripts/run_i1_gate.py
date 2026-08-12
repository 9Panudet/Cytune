"""Step 0.5.3 — apply gate I-1 to the committed raw (deterministic; recomputable).

Reads the four results/calibration/i1/raw/ files, verifies pairing (good/bad share
setup_sha256), computes speedup = median(bad)/median(good) per kernel via
motifbo.calibration.i1_gate, applies the PREREG_I1 thresholds, and writes the gate
report. Every number carries its raw-file pointer + the recompute command. Exit 1 on
FAIL (red gate). Run on the host:  PYTHONPATH=src python3 scripts/run_i1_gate.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")
from motifbo.calibration.i1_gate import evaluate  # noqa: E402

RAW = Path("results/calibration/i1/raw")
OUT = Path("results/calibration/i1")
RECOMPUTE = "PYTHONPATH=src python3 scripts/run_i1_gate.py"


def main():
    records, pointers = {}, {}
    for kernel in ("csr_scale", "horner"):    # I-1 references: raw-pointer + numeric-loop
                                              # (pava moved to characterization, 0.5.3-R R6)
        good = json.loads((RAW / f"{kernel}_good_K30.json").read_text())
        bad = json.loads((RAW / f"{kernel}_bad_K30.json").read_text())
        if good["setup_sha256"] != bad["setup_sha256"]:
            raise SystemExit(f"PAIRING BROKEN for {kernel}: good/bad setup_sha differ")
        records[kernel] = {"path_class": good["path_class"],
                           "good": good["result"]["samples_ns"],
                           "bad": bad["result"]["samples_ns"]}
        pointers[kernel] = {"good": f"{RAW}/{kernel}_good_K30.json",
                            "bad": f"{RAW}/{kernel}_bad_K30.json",
                            "setup_sha256": good["setup_sha256"]}

    res = evaluate(records)
    summary = {"schema": "motifbo-i1-gate-v1", "step": "0.5.3",
               "prereg": "results/prereg/PREREG_I1.md", "recompute": RECOMPUTE,
               "raw_pointers": pointers, **res}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "i1_gate.json").write_text(json.dumps(summary, indent=1) + "\n")

    lines = ["# Gate I-1 — Step 0.5.3 (§0.3, frozen in PREREG_I1.md)", "",
             f"Recompute: `{RECOMPUTE}` (median(bad)/median(good) over the K_final=30 "
             "reps; stats-auditor recomputes independently at preflight 0.P).", "",
             "| kernel | path class | median good ms | median bad ms | speedup | "
             "threshold | verdict | raw (good / bad) |",
             "|---|---|---|---|---|---|---|---|"]
    for kernel, r in res["per_kernel"].items():
        p = pointers[kernel]
        lines.append(
            f"| {kernel} | {r['path_class']} | {r['median_good_ns']/1e6:.3f} | "
            f"{r['median_bad_ns']/1e6:.3f} | **{r['speedup']:.3f}x** | "
            f">= {r['threshold']}x | {'PASS' if r['pass'] else 'FAIL'} | "
            f"{p['good']} / {p['bad']} |")
    pairing = ", ".join(f"{k} {p['setup_sha256'][:8]}" for k, p in pointers.items())
    lines += ["",
              f"Pairing verified: good/bad share setup_sha256 per kernel ({pairing}).",
              "",
              f"## GATE I-1: {'PASS' if res['i1_pass'] else 'FAIL — RED GATE'}"]
    if not res["i1_pass"]:
        lines += ["", "FAIL => §0.5.3: instrument presumed wrong until proven "
                  "otherwise -> debug-mantra. No tuning to force a pass."]
    (OUT / "I1_GATE.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    sys.exit(0 if res["i1_pass"] else 1)


if __name__ == "__main__":
    main()
