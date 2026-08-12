"""Pre-R bounded smoke for the 9 Dataset-R anchors (task #64) — runs BEFORE any full 1728 table.

WHY THIS EXISTS. Seven of the nine anchors — lda, binning, ppoly, floyd, cc, elkan, predictor —
have never been compiled anywhere in this repo. Only csr and pava were ever built (at pilot scale).
Committing R's measurement budget to nine full 1728-config tables on seven never-executed adapters
would discover a BUILD_FAIL hours in, nine times over. The roadmap's own rule applies: a new
instrument gets positive AND negative controls before its readings count.

WHAT IT IS NOT. This is a development instrument. It writes to results/rsmoke/, never to
results/fleet/ — the P3 firewall stands and no smoke artifact can reach the study or H.

SCOPE. Build only, on the pre-registered `probe` config set (16 + reference), which spans the key
levers (opt x march x boundscheck x fmffp) so a subset can never miss -O3. That is the cheapest
discriminating probe for the open risks:
  (a) cobuild — dep-ordered multi-module compilation (elkan 2 modules, predictor 3) has ZERO
      execution evidence anywhere.
  (b) five further single-module adapters have never been compiled.

ALREADY RESOLVED BY INSPECTION, so NOT re-litigated here: the OpenMP question. elkan cimports
omp_lock_t/omp_init_lock and both it and predictor use cython.parallel.prange, but the vendored
sklearn `_openmp_helpers.pxd` ships `#ifndef _OPENMP` no-op stubs (omp_lock_t -> int,
omp_get_max_threads() -> 1), so without -fopenmp they link cleanly and prange compiles to a SERIAL
loop; corpus_drivers.elkan_setup / predictor_setup already pass n_threads=1 ("single isolated
core"). No link failure and no oversubscription of the isolated cpu3. The consequence — both
anchors are measured on their serial path, not their parallel path — belongs in P2_REPORT's R
section, not in a gate.

CF-1: this compiles, so it must not overlap any measurement. Refuses to start on a busy box.

    python3 scripts/phasep/smoke_r_anchors.py            # all 9
    python3 scripts/phasep/smoke_r_anchors.py --only elkan,predictor
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r_anchor          # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
IMG = "localhost/motifbo-env:phase1"
OUT = os.path.join(REPO, "results", "rsmoke")
CONFIGS = "probe"


def _busy():
    """CF-1 quiesce-all: compiling next to a live measurement is exactly the D5 root cause."""
    rc = subprocess.run(["bash", os.path.join(REPO, "scripts", "hooks", "campaign_busy.sh")],
                        capture_output=True, text=True)
    return rc.returncode == 0, (rc.stdout or "").strip()


def _build_cmd(kid):
    return ["podman", "run", "--rm", "--network=none", "--security-opt", "label=disable",
            "-v", f"{REPO}/scripts:/probe:ro", "-v", f"{REPO}/results:/results:ro",
            "-v", f"{OUT}:/work", IMG,
            "python3", "/probe/phasep/build_phase.py", f"/work/_kernels/{kid}", f"/work/{kid}",
            CONFIGS]


def smoke_one(anchor_key, index, log):
    kid = f"rsmoke_R_{index:02d}_{anchor_key}"
    rec = {"anchor": anchor_key, "kernel_id": kid, "configs": CONFIGS}
    kroot = os.path.join(OUT, "_kernels")
    os.makedirs(kroot, exist_ok=True)
    a = r_anchor.ANCHORS[anchor_key]
    rec["cobuild_modules"] = len(a.get("cobuild") or []) or 1
    rec["openmp_declared"] = bool(a.get("openmp", False))
    rec["knob"] = a.get("knob")
    t0 = time.time()
    try:
        r_anchor.build_anchor(kroot, anchor_key, kid, repo_root=REPO)
    except Exception as e:                                   # source generation itself failed
        rec.update(status="EMIT_FAIL", error=f"{type(e).__name__}: {e}",
                   elapsed_s=round(time.time() - t0, 1))
        return rec
    os.makedirs(os.path.join(OUT, kid), exist_ok=True)
    with open(log, "a") as f:
        f.write(f"\n$ [{kid}] " + " ".join(_build_cmd(kid)) + "\n")
        f.flush()
        rc = subprocess.run(_build_cmd(kid), stdout=f, stderr=subprocess.STDOUT).returncode
    rec["elapsed_s"] = round(time.time() - t0, 1)
    rec["returncode"] = rc
    mpath = os.path.join(OUT, kid, "build_manifest.jsonl")
    built = ok = 0
    if os.path.exists(mpath):
        for line in open(mpath):
            built += 1
            if json.loads(line).get("ok"):
                ok += 1
    rec.update(manifest_rows=built, built_ok=ok)
    # A cythonize/compile failure is CACHED as feasibility-0 rather than raised (the committed
    # whole-combo rule), so rc==0 alone does NOT mean the adapter works. Judge on built_ok.
    rec["status"] = ("PASS" if ok > 0 and rc == 0 else
                     "ALL_CONFIGS_FAILED" if rc == 0 else "BUILD_FAIL")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="comma-separated anchor keys")
    ap.add_argument("--allow-busy", action="store_true", help="override the CF-1 guard (do not)")
    a = ap.parse_args()
    busy, why = _busy()
    if busy and not a.allow_busy:
        raise SystemExit(f"CF-1: box is BUSY ({why}) — a compile must never overlap a measurement")
    keys = a.only.split(",") if a.only else list(r_anchor.ALL_NINE)
    os.makedirs(OUT, exist_ok=True)
    log = os.path.join(OUT, "smoke.log")
    results = []
    for i, ak in enumerate(r_anchor.ALL_NINE, 1):
        if ak not in keys:
            continue
        print(f"[rsmoke] {ak} ...", flush=True)
        r = smoke_one(ak, i, log)
        results.append(r)
        print(f"  {r['status']}: built_ok={r.get('built_ok')}/{r.get('manifest_rows')} "
              f"cobuild={r['cobuild_modules']} openmp={r['openmp_declared']} "
              f"{r.get('elapsed_s')}s", flush=True)
        with open(os.path.join(OUT, "smoke_results.json"), "w") as f:
            json.dump(results, f, indent=2)
    bad = [r for r in results if r["status"] != "PASS"]
    print(f"\nrsmoke: {len(results) - len(bad)}/{len(results)} PASS")
    for r in bad:
        print(f"  FAIL {r['anchor']}: {r['status']} {r.get('error', '')}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
