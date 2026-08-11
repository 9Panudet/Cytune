#!/usr/bin/env python3
"""A1 — the repeated nine-anchor dogfood, k>=5 per arm, under PREREG_LAUNCH.md §2.

Runs the nine Dataset-R anchors K times per arm, ARMS INTERLEAVED BY REPLICATE, each run in a
FRESH workspace, with the rig re-verified before every replicate and the build caches pruned after
every anchor.

What this script is for, in one sentence: the flagship number currently rests on ONE live run, and
two live runs of the same unchanged engine are known to disagree by 3.597 pp on one anchor
(`results/release/dogfood` vs `dogfood2`, fleet_R_09_predictor). A number without a measured range
cannot carry a launch claim.

DESIGN POINTS THAT ARE NOT ARBITRARY (PREREG_LAUNCH.md §2.1):

  * ARMS INTERLEAVED. D1 P1 D2 P2 ... not D1..D5 then P1..P5. A thermal or background-load trend
    across a 7-hour campaign would otherwise alias onto the arm factor -- the same confound this
    project recorded against itself on 2026-07-24, when a time-correlated slowdown could have
    aliased onto the -O1/-O3 factor because config id order correlates with it.

  * FRESH WORKSPACE EVERY RUN. A reused workspace RESUMES: the engine sees prior measurements and
    takes a cheaper, different trajectory. One DOE-v2 run was discarded for exactly this (49
    configs vs 33). A replicate must be an independent run of the tool as a user meets it.

  * ANCHOR ORDER FIXED. Anchors are analysed per-anchor and never pooled, so a fixed order keeps
    replicates comparable and makes drift VISIBLE as a trend across replicate index instead of
    dispersing it into the anchor factor. Both arms see the same order, so order effects cancel in
    the paired arm comparison.

  * PRUNE AFTER, NEVER DURING. 71 MB of the 71 MB a run leaves behind is `_so` + `_ccache`; the
    evidence is ~120 KB. With ~8 GB free, 90 runs do not fit unless the caches go. Pruning happens
    only after every evidence file is verified present and non-empty (the D12 precedent), and a
    prune failure ABORTS the campaign rather than continuing into a disk-full failure that would
    look like a measurement failure.

Reads the staged anchors read-only. Writes only under results/release/<outdir>/.
Nothing here touches results/fleet or any frozen table.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CY = os.path.join(REPO, ".venv", "bin", "cytune")
MEASURE_WRAP = os.path.join(REPO, "scripts", "measure_wrap.sh")

ANCHORS = ["fleet_R_01_csr", "fleet_R_02_pava", "fleet_R_03_lda", "fleet_R_04_binning",
           "fleet_R_05_ppoly", "fleet_R_06_floyd", "fleet_R_07_cc", "fleet_R_08_elkan",
           "fleet_R_09_predictor"]

# arm id -> extra argv. "D" is the shipped default; "P" is the candidate under test.
ARMS = {"D": [], "P": ["--probe-as-screen"]}

# PREREG_LAUNCH.md §2.2 / control L3. Every one of these must exist and be non-empty before the
# build caches of that anchor may be removed.
EVIDENCE = ["certificate.json", "certificate.txt", "table.jsonl", "artifacts.jsonl",
            "build_manifest.jsonl", "cache_key.json", "oracle.json"]
PRUNE = ["_so", "_ccache"]


def source_tree_sha256() -> str:
    """Hash of every tracked .py under src/cytune -- control L4 (one commit for all 90 runs)."""
    h = hashlib.sha256()
    root = os.path.join(REPO, "src", "cytune")
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for fn in sorted(filenames):
            if not fn.endswith(".py"):
                continue
            p = os.path.join(dirpath, fn)
            h.update(os.path.relpath(p, root).encode())
            with open(p, "rb") as f:
                h.update(f.read())
    return h.hexdigest()


def verify_rig() -> tuple[bool, str]:
    """Control L1. Run it -- never assume its outcome (the 2026-07-25 correction)."""
    if not os.path.exists(MEASURE_WRAP):
        return False, "measure_wrap.sh not found"
    p = subprocess.run(["bash", MEASURE_WRAP, "--verify-only"],
                       cwd=REPO, capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + p.stderr).strip()[-2000:]


def prune(session_dir: str) -> tuple[bool, str, int]:
    """Control L3: verify the evidence, THEN drop the caches. Returns (ok, why, bytes_freed)."""
    for name in EVIDENCE:
        p = os.path.join(session_dir, name)
        if not os.path.exists(p):
            return False, f"missing evidence file: {name}", 0
        if os.path.getsize(p) == 0:
            return False, f"empty evidence file: {name}", 0
    freed = 0
    for name in PRUNE:
        d = os.path.join(session_dir, name)
        if not os.path.isdir(d):
            continue
        for dirpath, _, filenames in os.walk(d):
            for fn in filenames:
                try:
                    freed += os.path.getsize(os.path.join(dirpath, fn))
                except OSError:
                    pass
        shutil.rmtree(d)
    return True, "", freed


def free_bytes(path: str) -> int:
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize


def run_one(staging: str, out: str, arm: str, k: int, kid: str, manifest_fh) -> dict:
    ws = os.path.join(out, "runs", f"{arm}{k}", kid)
    if os.path.exists(ws):                      # control L2: fresh workspace, asserted not assumed
        raise SystemExit(f"ABORT: workspace already exists, refusing to resume into it: {ws}")
    os.makedirs(ws, exist_ok=False)

    cert = os.path.join(out, "runs", f"{arm}{k}", f"{kid}.json")
    log = os.path.join(out, "runs", f"{arm}{k}", f"{kid}.log")
    argv = [CY, "tune", os.path.join(staging, kid),
            "--driver", os.path.join(staging, kid, "driver.py"),
            "--workspace", ws, "--name", kid, "--no-config", "--json"] + ARMS[arm]

    t0 = time.time()
    with open(cert, "w") as fo, open(log, "w") as fe:
        rc = subprocess.call(argv, cwd=REPO, stdout=fo, stderr=fe)
    wall = time.time() - t0

    session = os.path.join(ws, kid)
    ok, why, freed = prune(session)
    if not ok and rc == 0:
        # A successful run whose evidence is incomplete is a defect, not a disk problem.
        raise SystemExit(f"ABORT: {arm}{k}/{kid} exited 0 but {why}")

    row = {"arm": arm, "replicate": k, "kernel_id": kid, "exit": rc,
           "wall_s": round(wall, 1), "workspace": os.path.relpath(ws, REPO),
           "pruned": ok, "prune_note": why, "freed_bytes": freed,
           "free_bytes_after": free_bytes(out)}
    manifest_fh.write(json.dumps(row) + "\n")
    manifest_fh.flush()
    print(f"  {arm}{k} {kid:24s} exit={rc} wall={wall:7.1f}s "
          f"freed={freed / 1e6:6.1f}MB free={row['free_bytes_after'] / 1e9:.1f}GB", flush=True)
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--k", type=int, default=5, help="replicates per arm (PREREG: >=5)")
    ap.add_argument("--arms", default="D,P")
    ap.add_argument("--outdir", default="dogfood_repeat")
    ap.add_argument("--staging", default=os.path.join("results", "release", "dogfood3", "staging"))
    ap.add_argument("--anchors", nargs="*", default=ANCHORS)
    ap.add_argument("--skip-rig-verify", action="store_true",
                    help="ONLY for a dry structural check; a real campaign never uses it")
    args = ap.parse_args()

    if args.k < 5:
        raise SystemExit("PREREG_LAUNCH.md §2.1 fixes K >= 5; refusing")
    arms = [a for a in args.arms.split(",") if a]
    for a in arms:
        if a not in ARMS:
            raise SystemExit(f"unknown arm {a!r}; known: {sorted(ARMS)}")

    out = os.path.join(REPO, "results", "release", args.outdir)
    staging = os.path.join(REPO, args.staging)
    os.makedirs(os.path.join(out, "runs"), exist_ok=True)

    sha = source_tree_sha256()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "src/cytune"], cwd=REPO,
                           capture_output=True, text=True).stdout.strip()
    ver = subprocess.run([CY, "--version"], capture_output=True, text=True)
    campaign = {
        "prereg": "results/prereg/PREREG_LAUNCH.md",
        "k": args.k, "arms": arms, "anchors": args.anchors,
        "arm_argv": {a: ARMS[a] for a in arms},
        "git_head": head, "src_dirty": dirty, "source_tree_sha256": sha,
        "cytune_version": (ver.stdout + ver.stderr).strip(),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "free_bytes_at_launch": free_bytes(out),
    }
    with open(os.path.join(out, "CAMPAIGN.json"), "w") as f:
        json.dump(campaign, f, indent=2)
    print(json.dumps(campaign, indent=2), flush=True)
    if dirty:
        print("WARNING: src/cytune is dirty; L4 (one commit for all runs) is not provable",
              flush=True)

    rig_path = os.path.join(out, "RIG_VERIFY.jsonl")
    man_path = os.path.join(out, "MANIFEST.jsonl")
    with open(man_path, "a") as manifest_fh, open(rig_path, "a") as rig_fh:
        for k in range(1, args.k + 1):
            for arm in arms:                                    # interleaved: D1 P1 D2 P2 ...
                if args.skip_rig_verify:
                    ok, note = True, "SKIPPED (--skip-rig-verify)"
                else:
                    ok, note = verify_rig()
                rig_fh.write(json.dumps({
                    "arm": arm, "replicate": k, "ok": ok, "note": note,
                    "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}) + "\n")
                rig_fh.flush()
                print(f"[rig] {arm}{k} verify_only -> {'PASS' if ok else 'FAIL'}", flush=True)
                if not ok:
                    raise SystemExit(f"ABORT: rig verify failed before {arm}{k}:\n{note}")
                for kid in args.anchors:
                    if free_bytes(out) < 3e9:
                        raise SystemExit("ABORT: under 3 GB free; refusing to start another anchor")
                    run_one(staging, out, arm, k, kid, manifest_fh)

    with open(os.path.join(out, "DONE"), "w") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n")
    print("CAMPAIGN DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
