"""cytune container-side worker (roadmap §8.1 steps 1/2/4).

The CLI is HOST-side orchestration (no numpy there, by design — the host only spawns containers,
exactly like run_pilot.py). Everything numeric or measured runs here, inside a container, via
`python3 -m cytune.worker <cmd> ...`.

It REUSES campaign.py rather than reimplementing the rig: the product must measure through exactly
the same path as the study, or its numbers mean something different from the study's numbers.

Sub-commands (one container invocation each, so the CF-1 phase split is structural):
  build     <kdir> <out> <ids>    compile only            (plain build container)
  golden    <kdir> <out> [ms]     determinism + oracle    (measure container)
  measure   <kdir> <out> <ids>    screen tier             (measure container)
  endpoint  <kdir> <out> <ids>    endpoint tier K=30      (measure container)
  features  <kdir> <out>          §9.2 probe features     (pure compute)
  screen    <kdir> <out> <budget> DOE batch-1 plan        (pure compute)
  walk      <kdir> <out> <budget> [--allow-fast-math]  DOE batch-2 plan   (pure compute)

`ids` is a comma-separated config_id list, or "probe" for the pre-registered 16-point design.
Output is a single JSON object on the last stdout line; the host parses that line and ignores any
chatter above it (measure_wrap prints its verified state there).
"""
from __future__ import annotations
import json
import os
import sys

from ._phasep import theta  # noqa: F401  (also puts scripts/phasep on sys.path)
import campaign  # noqa: E402

from . import plan, probe  # noqa: E402

ENDPOINT_K = 30          # PREREG §4 endpoint tier
ENDPOINT_SUBS = 3        # median-of-3 sub-measures
ENDPOINT_MAX_SUBS = 5    # escalate to at most 5 while CV > 0.05
ENDPOINT_CV_GATE = 0.05


def _ids(arg):
    if arg == "probe":
        return probe.probe_config_ids()
    return sorted({int(x) for x in arg.split(",") if x.strip() != ""})


def _emit(obj):
    print(json.dumps(obj))


def _rows(out, only=None):
    p = os.path.join(out, "table.jsonl")
    if not os.path.exists(p):
        return {}
    keep = set(only) if only is not None else None
    res = {}
    for line in open(p):
        r = json.loads(line)
        if keep is None or r["config_id"] in keep:
            res[r["config_id"]] = r
    return res


def _feasible(out, only=None):
    return {c: r["screen"]["median_ns"] for c, r in _rows(out, only).items()
            if r.get("feasible") and r.get("screen")}


# ------------------------------------------------------------------ measured phases
def _drop_stale_manifest_rows(out):
    """Forget manifest rows whose .so no longer exists, so they get rebuilt.

    campaign.build_all resumes by trusting build_manifest.jsonl alone: a config with a manifest row
    is "done". That holds inside the study, where a kernel's _so is only ever pruned once its table
    is complete and it is never rebuilt. It does NOT hold for a product workspace, which the user
    (or a disk cleanup, or a tmpfs reboot, or the D12 prune rule) can empty at any time — and then
    cytune reports "built 17/17" and dies on a raw ImportError from measure_child.

    Fixed HERE rather than in campaign.build_all deliberately: campaign.py is the operative study
    path with a paused campaign resuming against it, and this failure mode is not reachable there.
    Editing it would be unnecessary risk. (D17)
    """
    mpath = os.path.join(out, "build_manifest.jsonl")
    if not os.path.exists(mpath):
        return 0
    rows = [json.loads(l) for l in open(mpath)]
    keep, dropped = [], 0
    for r in rows:
        so = r.get("so_path")
        if r.get("ok") and so and not os.path.exists(so):
            dropped += 1
            continue
        keep.append(r)
    if dropped:
        with open(mpath, "w") as f:
            for r in keep:
                f.write(json.dumps(r) + "\n")
    return dropped


def cmd_build(kdir, out, ids):
    os.makedirs(out, exist_ok=True)
    stale = _drop_stale_manifest_rows(out)
    mpath, n_ok = campaign.build_all(kdir, out, ids)
    man = campaign._manifest(out)
    _emit({"ok": True, "manifest": mpath, "n_ok_total": n_ok, "stale_rebuilt": stale,
           "built": {str(c): bool(man.get(c, {}).get("ok")) for c in ids},
           "failed": {str(c): man.get(c, {}).get("reason") for c in ids
                      if not man.get(c, {}).get("ok")}})


def cmd_golden(kdir, out, target_ms):
    """Determinism gate + §1.3 automatic oracle derivation.

    Two deliberate departures from the fleet path, both because the input is a stranger's module
    rather than a generated kernel:
      - calibration is SKIPPED when the driver exposes no REPS/SCALE knob. campaign.calibrate would
        otherwise write the literal line "None = ..." into the driver; fleet kernels always carry a
        knob, user code need not.
      - non-determinism returns a structured refusal instead of SystemExit, so the CLI can say
        "cannot certify this module, and here is exactly why" rather than dying with a traceback.
    """
    calib, knob = None, None
    drv = os.path.join(kdir, "driver.py")
    if os.path.exists(drv):
        knob, _cur = campaign._knob_line(open(drv).read())
        if knob is not None and target_ms:
            calib = campaign.calibrate(kdir, out, target_ms)
    try:
        orc = campaign.golden_and_oracle(kdir, out)
    except SystemExit as e:
        _emit({"ok": False, "stage": "golden", "error": str(e),
               "hint": "the module's output is not bit-reproducible across repeated runs of the "
                       "REFERENCE config, so no oracle can be derived and no config can be "
                       "certified correct. cytune refuses rather than guess a tolerance."})
        return
    _emit({"ok": True, "calibrated": calib, "knob": knob,
           "oracle": {"output_class": orc["output_class"], "deterministic": orc["deterministic"],
                      "tolerance": orc["tolerance"], "golden_shape": orc["golden_shape"],
                      "n_det_reps": orc["n_det_reps"], "golden_sha256": orc["golden_sha256"]}})


def cmd_measure(kdir, out, ids):
    tp, nf = campaign.measure_all(kdir, out, ids)
    rows = _rows(out, ids)
    _emit({"ok": True, "table": tp, "n_feasible_total": nf,
           "rows": {str(c): {"feasible": r.get("feasible"), "reason": r.get("reason"),
                             "median_ns": (r.get("screen") or {}).get("median_ns"),
                             "rig": r.get("rig")}
                    for c, r in rows.items()}})


def cmd_endpoint(kdir, out, ids):
    """PREREG §4 endpoint tier on SPECIFIC configs (the winner and the reference).

    campaign.endpoint_tier re-measures the feasible top decile of a full table, which answers the
    study's question. The product's question is narrower — "is THIS winner really faster than the
    reference?" — so the same protocol (median-of-3 K=30 sub-measures, escalate while CV > 0.05, at
    most 5) is applied to a caller-chosen set. The oracle is re-checked here as well: a config that
    passed the screen but fails at endpoint must never be emitted.
    """
    import numpy as np
    mod = campaign._module_of(kdir)
    man = campaign._manifest(out)
    oracle_path = os.path.join(out, "oracle.json")
    res = {}
    for cid in ids:
        b = man.get(cid, {})
        if not b.get("ok"):
            res[str(cid)] = {"feasible": False, "reason": f"not_built: {b.get('reason')}",
                             "endpoint_ns": None, "n_sub": 0, "subs_ns": []}
            continue
        subs, ok, reason = [], True, "ok"
        while ok and len(subs) < ENDPOINT_MAX_SUBS:
            m, _w, err = campaign._measure_one(kdir, b["so_path"], cid, mod, 12345,
                                               oracle_path=oracle_path,
                                               k_min=ENDPOINT_K, k_max=ENDPOINT_K)
            if m is None:
                ok, reason = False, f"measure_failed: {err}"
                break
            if not m.get("feasible"):
                ok, reason = False, m.get("reason", "oracle_mismatch")
                break
            subs.append(m["median_ns"])
            if len(subs) >= ENDPOINT_SUBS:
                cv = float(np.std(subs) / np.mean(subs))
                if cv <= ENDPOINT_CV_GATE:
                    break
        res[str(cid)] = {
            "feasible": bool(ok and subs), "reason": reason,
            "endpoint_ns": (float(np.median(subs)) if (ok and subs) else None),
            "n_sub": len(subs), "subs_ns": subs,
            "cv": (float(np.std(subs) / np.mean(subs)) if len(subs) >= 2 else None),
            "rig": campaign._rig()}
    _emit({"ok": True, "endpoints": res, "rig": campaign._rig(),
           "protocol": {"K": ENDPOINT_K, "subs": ENDPOINT_SUBS, "max_subs": ENDPOINT_MAX_SUBS,
                        "cv_gate": ENDPOINT_CV_GATE}})


# ------------------------------------------------------------------ pure compute
def cmd_features(kdir, out):
    ids = probe.probe_config_ids()
    _emit({"ok": True, "features": probe.features(_rows(out, ids)),
           "probe_ids": ids})


def cmd_screen(kdir, out, budget):
    _emit({"ok": True, **plan.screen_plan(budget)})


def cmd_walk(kdir, out, budget, allow_fm):
    rows = _rows(out)
    feas = {c: r["screen"]["median_ns"] for c, r in rows.items()
            if r.get("feasible") and r.get("screen")}
    queried = set(rows)
    _emit({"ok": True, **plan.walk_plan(feas, queried, budget, allow_fast_math=allow_fm),
           "n_queried": len(queried)})


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    allow_fm = "--allow-fast-math" in argv
    argv = [a for a in argv if a != "--allow-fast-math"]
    cmd, kdir, out = argv[0], argv[1], argv[2]
    rest = argv[3:]
    if cmd == "build":
        cmd_build(kdir, out, _ids(rest[0]))
    elif cmd == "golden":
        cmd_golden(kdir, out, float(rest[0]) if rest else 0.0)
    elif cmd == "measure":
        cmd_measure(kdir, out, _ids(rest[0]))
    elif cmd == "endpoint":
        cmd_endpoint(kdir, out, _ids(rest[0]))
    elif cmd == "features":
        cmd_features(kdir, out)
    elif cmd == "screen":
        cmd_screen(kdir, out, int(rest[0]))
    elif cmd == "walk":
        cmd_walk(kdir, out, int(rest[0]), allow_fm)
    else:
        raise SystemExit(f"unknown cytune.worker command: {cmd}")


if __name__ == "__main__":
    main()
