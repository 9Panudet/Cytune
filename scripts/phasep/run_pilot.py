"""Pilot/fleet orchestrator (roadmap §7 P1, PREREG §2/§9) — HOST-side, two containers per kernel.

Per kernel, CF-1 phase split across two containers:
  BUILD   : plain container -> build_phase.py (all 1728 .so + manifest)   [compile]
  MEASURE : measure_wrap.sh -> measure_phase.py (calibrate→golden→screen→suspicious→endpoint→class)
            on the isolated core 3, fail-loud if the host drifts.          [measure of record]
Serial (one measure container at a time). Resumable: a kernel with class_record.json is skipped.
Survival ledger + per-kernel per-phase wall-clock recorded live.

CLI:
  run_pilot.py --controls                       # planted+flat, HARD gate, exit!=0 on fail
  run_pilot.py --classes A:5 B:5 C:5 --anchors 2 # the 17-kernel pilot
  [--rig plain|measure_wrap] [--out results/pilot] [--target-ms 65] [--only <kid>]
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
IMG = "localhost/motifbo-env:phase1"
sys.path.insert(0, HERE)
import generate  # noqa: E402
import r_anchor  # noqa: E402

FAM_N = {"A": (100000, 120), "B": (200000, 120), "C": (60000, 120)}
# planted: small L1/L2 long array (compute-bound, bc-inhibits-int-SIMD) + many reps;
# flat: >>L3 double array (DRAM-bandwidth-bound) + few reps. calibrate tunes REPS to the band.
CTRL_N = {"planted": (2048, 40000), "flat": (1000000, 1), "bcprobe": (32768, 6000)}


def _run(cmd, log):
    with open(log, "a") as f:
        f.write(f"\n$ {' '.join(cmd)}\n")
        f.flush()
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    return r.returncode


def _build_cmd(kid, out, configs):
    return ["podman", "run", "--rm", "--network=none", "--security-opt", "label=disable",
            "-v", f"{REPO}/scripts:/probe:ro", "-v", f"{REPO}/results:/results:ro", "-v", f"{out}:/work",
            IMG, "python3", "/probe/phasep/build_phase.py", f"/work/_kernels/{kid}", f"/work/{kid}", configs]


def _measure_cmd(kid, out, rig, target_ms, configs):
    inner = ["python3", "/probe/phasep/measure_phase.py", f"/work/_kernels/{kid}", f"/work/{kid}",
             configs, "--target-ms", str(target_ms)]
    mounts = ["--security-opt", "label=disable", "-v", f"{REPO}/scripts:/probe:ro",
              "-v", f"{REPO}/results:/results:ro", "-v", f"{out}:/work"]
    if rig == "measure_wrap":
        return ["bash", f"{REPO}/scripts/measure_wrap.sh"] + mounts + [IMG] + inner
    return ["podman", "run", "--rm", "--network=none"] + mounts + [IMG] + inner


def process_kernel(kid, out, rig, target_ms, ledger, log, configs="all", run_meta=None):
    rm = run_meta or {}   # A-2 Part-5: {'run_id','run_kind'} distinguish controls/pilot/probe runs
    out_kdir = os.path.join(out, kid)
    rec_path = os.path.join(out_kdir, "class_record.json")
    if os.path.exists(rec_path):
        print(f"[skip complete] {kid}")
        return json.load(open(rec_path))
    os.makedirs(out_kdir, exist_ok=True)
    t = {"kernel_id": kid}
    print(f"[build] {kid}")
    t0 = time.time()
    rc = _run(_build_cmd(kid, out, configs), log)
    t["build_s"] = round(time.time() - t0, 1)
    if rc != 0:
        ledger.write(json.dumps({"kernel_id": kid, "status": "BUILD_FAIL", **t, **rm}) + "\n"); ledger.flush()
        return None
    print(f"[measure] {kid} (rig={rig})")
    t0 = time.time()
    rc = _run(_measure_cmd(kid, out, rig, target_ms, configs), log)
    t["measure_s"] = round(time.time() - t0, 1)
    if rc != 0 or not os.path.exists(rec_path):
        ledger.write(json.dumps({"kernel_id": kid, "status": "MEASURE_FAIL", **t, **rm}) + "\n"); ledger.flush()
        return None
    rec = json.load(open(rec_path))
    cl = rec.get("classification", {})
    entry = {"kernel_id": kid, "status": "DONE", **t, "intended": rec.get("intended_class"),
             "measured_class": cl.get("measured_class"), "delta_all": cl.get("delta_all"),
             "interaction_fraction": cl.get("interaction_fraction"), "n_feasible": rec.get("n_feasible"),
             **rm}
    ledger.write(json.dumps(entry) + "\n"); ledger.flush()
    print(f"  {kid}: measured={cl.get('measured_class')} Δ_all={cl.get('delta_all')} "
          f"IF={cl.get('interaction_fraction')} build={t['build_s']}s measure={t['measure_s']}s")
    return rec


def _gen_all(out):
    kroot = os.path.join(out, "_kernels")
    os.makedirs(kroot, exist_ok=True)
    return kroot


def controls_gate(out, rig, target_ms, ledger, log, configs="all"):
    """PREREG §9.1 as amended by A-1: planted = vectorization lever (Δ_all≥1.6 AND opt_level the
    largest main effect, -O3 faster than -O1); flat = Δ_all≤1.10 (A-1b IF Δ-floor gates IF out).
    bcprobe = A-1c bc-ceiling characterization (recorded, NOT gated)."""
    kroot = _gen_all(out)
    for kid, fam in (("pilot_ctrl_planted", "planted"), ("pilot_ctrl_flat", "flat"),
                     ("pilot_ctrl_bcprobe", "bcprobe")):
        n, reps = CTRL_N[fam]
        generate.generate_kernel(kroot, kid, "A", fam, 0, n, reps, is_control=True)
    rm = {"run_id": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), "run_kind": "controls"}
    recs = {kid: process_kernel(kid, out, rig, target_ms, ledger, log, configs, run_meta=rm)
            for kid in ("pilot_ctrl_planted", "pilot_ctrl_flat", "pilot_ctrl_bcprobe")}
    p = recs.get("pilot_ctrl_planted"); f = recs.get("pilot_ctrl_flat"); b = recs.get("pilot_ctrl_bcprobe")
    p_cl = (p or {}).get("classification", {}); f_cl = (f or {}).get("classification", {})
    pd = p_cl.get("delta_all"); p_opt_top = (p or {}).get("opt_top"); p_o3f = (p or {}).get("opt_o3_faster")
    verdicts = {
        "planted": {"delta_all": pd, "opt_top": p_opt_top, "opt_o3_faster": p_o3f,
                    "top_factor": (p or {}).get("top_factor"), "factor_effects": (p or {}).get("factor_effects"),
                    "ok": bool(pd and pd >= 1.6 and p_opt_top and p_o3f)},
        "flat": {"delta_all": f_cl.get("delta_all"), "IF": f_cl.get("interaction_fraction"),
                 "if_gated": f_cl.get("if_gated"), "measured_class": f_cl.get("measured_class"),
                 "ok": bool(f_cl.get("delta_all") is not None and f_cl["delta_all"] <= 1.10)},
        "bcprobe_characterization_A1c": {   # NOT gated — records the bc ceiling on this machine
            "top_factor": (b or {}).get("top_factor"), "bc_effect": ((b or {}).get("factor_effects") or {}).get("boundscheck"),
            "factor_effects": (b or {}).get("factor_effects"), "delta_all": (b or {}).get("classification", {}).get("delta_all")},
    }
    with open(os.path.join(out, "controls_gate.json"), "w") as fp:
        json.dump(verdicts, fp, indent=2)
    ok = verdicts["planted"]["ok"] and verdicts["flat"]["ok"]
    print(f"\nCONTROLS GATE (A-1): {'PASS' if ok else 'FAIL'}")
    print(f"  planted: Δ_all={pd} opt_top={p_opt_top} o3_faster={p_o3f} "
          f"(need Δ≥1.6 AND opt largest AND -O3 faster) -> {verdicts['planted']['ok']}")
    print(f"  flat:    Δ_all={f_cl.get('delta_all')} class={f_cl.get('measured_class')} if_gated={f_cl.get('if_gated')} "
          f"(need Δ≤1.10; A-1b IF-gated) -> {verdicts['flat']['ok']}")
    print(f"  bcprobe (A-1c char, not gated): top={verdicts['bcprobe_characterization_A1c']['top_factor']} "
          f"bc_effect={verdicts['bcprobe_characterization_A1c']['bc_effect']}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--classes", default="")
    ap.add_argument("--anchors", type=int, default=0)
    ap.add_argument("--rig", default="measure_wrap", choices=["plain", "measure_wrap"])
    ap.add_argument("--out", default=os.path.join(REPO, "results", "pilot"))
    ap.add_argument("--target-ms", type=float, default=65.0)
    ap.add_argument("--only", default=None)
    ap.add_argument("--configs", default="all")   # subset for orchestration smoke; "all" for record
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    log = os.path.join(out, "run_pilot.log")
    ledger = open(os.path.join(out, "survival_ledger.jsonl"), "a")

    if a.controls:
        ok = controls_gate(out, a.rig, a.target_ms, ledger, log, a.configs)
        ledger.close()
        sys.exit(0 if ok else 3)   # HARD STOP: nonzero on control failure

    kroot = _gen_all(out)
    jobs = []
    for tok in a.classes.split():
        cls, k = tok.split(":")
        for i in range(1, int(k) + 1):
            kid = f"pilot_{cls}_{i:02d}"
            n, reps = FAM_N[cls]
            generate.generate_kernel(kroot, kid, cls, cls, i, n, reps)
            jobs.append(kid)
    for i, ak in enumerate(("csr", "pava")[:a.anchors], 1):
        kid = f"pilot_R_{i:02d}_{ak}"
        r_anchor.build_anchor(kroot, ak, kid, repo_root=REPO)
        jobs.append(kid)
    if a.only:
        jobs = [j for j in jobs if j == a.only]

    summary = []
    rm = {"run_id": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), "run_kind": "pilot"}
    for kid in jobs:
        rec = process_kernel(kid, out, a.rig, a.target_ms, ledger, log, a.configs, run_meta=rm)
        if rec:
            summary.append({"kernel_id": kid, **rec.get("classification", {}),
                            "intended": rec.get("intended_class"), "n_feasible": rec.get("n_feasible")})
        with open(os.path.join(out, "pilot_summary.json"), "w") as f:
            json.dump({"n_done": len(summary), "kernels": summary}, f, indent=2)
    ledger.close()
    print(f"\npilot: {len(summary)}/{len(jobs)} kernels complete -> {out}/pilot_summary.json")


if __name__ == "__main__":
    main()
