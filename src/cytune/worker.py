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
import glob
import json
import os
import sys
import threading

from ._vendor import theta  # noqa: F401  (also puts the vendored rig on sys.path)
import campaign  # noqa: E402

from . import binding, plan, probe  # noqa: E402

ENDPOINT_K = 30          # PREREG §4 endpoint tier
ENDPOINT_SUBS = 3        # median-of-3 sub-measures
ENDPOINT_MAX_SUBS = 5    # escalate to at most 5 while CV > 0.05
ENDPOINT_CV_GATE = 0.05

# Set by the host from `podman image inspect`; stamped onto every artifact and every measured row
# so the toolchain is a recorded fact rather than an assumption about what `IMAGE` resolved to.
IMAGE_DIGEST = os.environ.get("CYTUNE_IMAGE_DIGEST") or None


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


def _capture_first_failure_log(kdir, out, failed_ids):
    """Re-run ONE failing build to recover the compiler's actual words.

    campaign.build_all's manifest row keeps only `reason` ("cythonize_fail" / "build_fail") and
    drops build.build_config's `log`. That was cold-user finding F6: a .pyx with a syntax error
    produced `built 0/17 configs` and `cythonize_fail` and NOT ONE LINE of compiler output, so a
    user had nothing to act on.

    Recovering it here rather than widening campaign._row is deliberate: campaign.py is the
    study's operative build path with frozen tables behind it, and this failure mode is not
    reachable there. One extra compile of an already-failing config, only on the failure path.
    """
    import build as buildmod
    if not failed_ids:
        return None
    cid = sorted(failed_ids)[0]
    cache = os.path.join(out, "_ccache")
    try:
        b = buildmod.build_config(kdir, theta.config_of(cid), cache, os.path.join(out, "_so"))
    except Exception as e:                                    # noqa: BLE001 - diagnostics only
        return {"config_id": cid, "reason": "log_capture_failed", "log": f"{type(e).__name__}: {e}"}

    log = b.get("log") or ""
    # `_cythonize_synth` returns its REASON as the third element, so on a cached failure the "log"
    # is literally the string "cythonize_fail (cached)" — non-empty, and worth nothing. Anything
    # that is just a status word gets replaced by the real compiler output.
    if not log.strip() or log.strip() in {"cythonize_fail", "cythonize_fail (cached)",
                                          "build_fail", "cached", "ok"}:
        # T1 (systematic-tester agent): a total build failure shipped NO compiler diagnostic at
        # all — the console said `cythonize_fail (cached)` and the "full build log" was 79 bytes
        # containing that same string. Two documents promise "the compiler's own words".
        #
        # The words were never lost: `_cythonize_synth` writes the compiler's stdout+stderr to
        # `<c_path>.FAIL` on the first failure. But `build_all` has already run by the time this
        # is called, so the re-build hits that cache marker and returns the reason string with no
        # `log` — and nothing read the file back. Recovered here.
        #
        # The named proof test never caught it because it stubbed the build result instead of
        # driving a real cythonize failure; `test_cytune_buildfail.py` now uses a real one.
        log = _read_cached_failure(cache, cid)
    return {"config_id": cid, "reason": b.get("reason"), "log": log}


def _read_cached_failure(cache_dir, cid):
    """The compiler output `_cythonize_synth`/`_cythonize_closure` stashed beside the .c file."""
    import build as buildmod
    if not os.path.isdir(cache_dir):
        return ""
    combo = buildmod._combo_key(theta.config_of(cid))
    # synth writes kernel_<combo>.c.FAIL; closure writes <module>_<combo>.c.FAIL
    for fn in sorted(os.listdir(cache_dir)):
        if fn.endswith(".FAIL") and f"_{combo}." in fn:
            try:
                with open(os.path.join(cache_dir, fn)) as f:
                    return f.read()
            except OSError:
                continue
    return ""


class _ArgvRecorder:
    """Capture the argv `build.py` actually ran, without editing a byte of it.

    `build.py` is whole-file sha256-pinned to the study copy, so the build command cannot be
    recorded by changing it. It calls the module-global `subprocess`, so substituting a shim for
    the DURATION of the build records every invocation and leaves the pinned source untouched.
    What lands in the certificate is therefore the command that ran, not a reconstruction of what
    the config id says should have run — which is the entire difference I4 exists to make.
    """

    def __init__(self, real):
        self._real = real
        self.calls = []
        self._lock = threading.Lock()

    def run(self, cmd, *a, **kw):
        r = self._real.run(cmd, *a, **kw)
        argv = list(cmd) if isinstance(cmd, (list, tuple)) else [str(cmd)]
        with self._lock:
            self.calls.append(argv)
        return r

    def __getattr__(self, name):
        return getattr(self._real, name)


def _argv_producing(calls, target):
    """The recorded argv whose `-o` names `target`. Exact match, so no naming convention is
    assumed; a cobuild config runs several gcc invocations and this returns the one that produced
    the module the measurement imports."""
    for argv in calls:
        if "-o" in argv:
            i = argv.index("-o")
            if i + 1 < len(argv) and argv[i + 1] == target:
                return argv
    return None


def _source_digest(out, cid):
    """The generated C this config was compiled from, hashed per directive combination.

    One digest whether the kernel is a single .pyx, a closure or a cobuild package: everything the
    cythonize step wrote for this combo is hashed together, path-qualified.
    """
    combo = binding.combo_key(cid)
    cache = os.path.join(out, "_ccache")
    files = sorted(glob.glob(os.path.join(cache, f"*_{combo}.c")))
    if not files:
        return None
    # THE COMBO IS STRIPPED FROM THE NAME BEFORE HASHING, and this is the whole check.
    #
    # `sha256_files` mixes each file's NAME into the digest, so that a rename counts — which is
    # right for an artifact set and catastrophic here: cythonize writes `<module>_<combo>.c`, so
    # leaving the combo in the name gave every directive combination a distinct source digest BY
    # CONSTRUCTION, and I4.2 could never observe two combinations producing identical code. The
    # end-to-end test did not catch it because it hashed the .c files itself rather than going
    # through this function — a named test asserting the wrong thing, which is the exact shape of
    # R2 and T1.
    #
    # Caught by comparing the shipped code's answer against a measurement taken before it existed:
    # the ad-hoc one found `initializedcheck` inert on six of the nine anchors, this reported none.
    return binding.sha256_files([(os.path.basename(p).replace(f"_{combo}.c", ".c"), p)
                                 for p in files])


def _artifact_digest(out, cid, so_path, meta):
    """The compiled bytes. A cobuild config ships several .so files inside its per-config package
    tree and importing it loads all of them, so all of them are the artifact."""
    if not so_path:
        return None
    if meta and meta.get("cobuild"):
        root = os.path.join(out, "_so", f"pkg_{cid}")
        files = [(os.path.relpath(os.path.join(dp, fn), root), os.path.join(dp, fn))
                 for dp, _dn, fns in os.walk(root) for fn in fns if fn.endswith(".so")]
        return binding.sha256_files(files) if files else None
    return binding.sha256_file(so_path)


def _build_workers():
    """One worker per CPU cytune is actually allowed to use.

    `sched_getaffinity` rather than `cpu_count`: the build container is pinned to the non-isolated
    cores, and asking the kernel how many it has is the only way to get that right without the
    host telling the container about its own cpuset twice.
    """
    env = os.environ.get("CYTUNE_BUILD_WORKERS")
    if env and env.isdigit() and int(env) > 0:
        return int(env)
    try:
        n = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        n = os.cpu_count() or 2
    return max(1, min(8, n))


def _build_all(kdir, out, config_ids):
    """Compile every config. Same `build.build_config`, same flags, same manifest rows as the
    study's `campaign.build_all` — a different SCHEDULE.

    WHY THIS IS NOT campaign.build_all. That function runs its cythonize phase SERIALLY, one
    representative per distinct directive combination, and only parallelises the gcc of the
    remainder. Inside the study that is free: a fleet run builds all 1,728 configs of a kernel, so
    the serial phase is 32 of 1,728 and everything else is parallel. In the product the ratio is
    inverted — a tuning run measures ~33 configs spanning ~22 distinct combinations, so the SERIAL
    phase is two thirds of the work. Measured on the nine dogfood anchors, the build phase was 71%
    of total wall clock (csr: 496 s of 695 s).

    The serialisation exists to stop two configs sharing a combination from racing on the same .c
    path. Taking exactly one representative per DISTINCT combination removes that possibility by
    construction — distinct combinations never share an output path — so phase 1 parallelises
    safely, which is what this does.

    WHY IT IS SAFE TO RESCHEDULE A BUILD AT ALL, and how that is checked rather than argued: the
    artifact is what gets measured, and I4 hashes it. `test_cytune_binding.py::
    test_the_parallel_scheduler_produces_byte_identical_artifacts` builds a real kernel both ways
    and compares every .so. Reordering is safe exactly because the bytes are verified, which is
    the second thing artifact binding buys.
    """
    import build as buildmod
    from concurrent.futures import ThreadPoolExecutor

    cache = os.path.join(out, "_ccache")
    sod = os.path.join(out, "_so")
    mpath = os.path.join(out, "build_manifest.jsonl")
    done = set()
    if os.path.exists(mpath):
        for line in open(mpath):
            done.add(json.loads(line)["config_id"])
    todo = [c for c in config_ids if c not in done]

    def _row(cid, b):
        return {"config_id": cid, "ok": b["ok"], "reason": b["reason"],
                "compile_s": round(b["compile_s"], 4), "so_size_b": b["so_size_b"],
                "so_path": b.get("so_path")}

    def _one(cid):
        return cid, _row(cid, buildmod.build_config(kdir, theta.config_of(cid), cache, sod))

    reps = {}
    for cid in todo:
        reps.setdefault(buildmod._combo_key(theta.config_of(cid)), cid)
    first = list(reps.values())
    rest = [c for c in todo if c not in reps.values()]

    recorder = _ArgvRecorder(buildmod.subprocess)
    buildmod.subprocess = recorder
    rows = {}
    try:
        workers = _build_workers()
        # phase 1: one representative per DISTINCT combination — warms the .c cache. Parallel,
        # because no two distinct combinations write the same file.
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for cid, r in ex.map(_one, first):
                rows[cid] = r
        # phase 2: every remaining config — cythonize is now a cache hit, so this is gcc only.
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for cid, r in ex.map(_one, rest):
                rows[cid] = r
    finally:
        buildmod.subprocess = recorder._real

    meta = buildmod._meta(kdir)
    records = []
    with open(mpath, "a") as mf:
        n_ok = len(done)
        for cid in todo:
            mf.write(json.dumps(rows[cid]) + "\n")
            n_ok += int(rows[cid]["ok"])
            if not rows[cid]["ok"]:
                continue
            so = rows[cid]["so_path"]
            records.append({
                "config_id": cid,
                "combo": binding.combo_key(cid),
                "artifact_sha256": _artifact_digest(out, cid, so, meta),
                "source_sha256": _source_digest(out, cid),
                "so_path": so,
                "so_size_b": rows[cid]["so_size_b"],
                "build_argv": _argv_producing(recorder.calls, so),
                "image_digest": IMAGE_DIGEST,
                "workers": workers,
            })
    binding.append(out, records)
    return mpath, n_ok


def cmd_build(kdir, out, ids):
    os.makedirs(out, exist_ok=True)
    stale = _drop_stale_manifest_rows(out)
    mpath, n_ok = _build_all(kdir, out, ids)
    man = campaign._manifest(out)
    failed = {str(c): man.get(c, {}).get("reason") for c in ids if not man.get(c, {}).get("ok")}
    records = binding.read(out)
    payload = {"ok": True, "manifest": mpath, "n_ok_total": n_ok, "stale_rebuilt": stale,
               "n_requested": len(ids), "n_built": sum(1 for c in ids
                                                       if man.get(c, {}).get("ok")),
               "built": {str(c): bool(man.get(c, {}).get("ok")) for c in ids},
               "failed": failed,
               # I4 — reported on EVERY build call, so the host sees degeneracy as soon as it is
               # observable rather than after a whole search has been spent on inert factors.
               "degeneracy": binding.degeneracy(records),
               "image_digest": IMAGE_DIGEST,
               "artifacts": {str(c): (records.get(c) or {}).get("artifact_sha256")
                             for c in ids if c in records}}
    if failed:
        diag = _capture_first_failure_log(kdir, out, [int(c) for c in failed])
        if diag:
            log_path = os.path.join(out, "build_failure.log")
            with open(log_path, "w") as f:
                f.write(f"# cytune build failure — config {diag['config_id']} "
                        f"({diag.get('reason')})\n\n{diag.get('log') or '(no compiler output)'}\n")
            payload["first_failure"] = diag
            payload["build_log_path"] = log_path
    _emit(payload)


def _set_knob(driver_path, name, value):
    """Write `name = value` onto the driver's knob line — the same rewrite `campaign.calibrate`
    performs, so a reused calibration and a fresh one leave the driver in identical states."""
    src = open(driver_path).read()
    open(driver_path, "w").write("\n".join(
        (f"{name} = {value}" if l.startswith(name + " ") else l) for l in src.splitlines()))


def cmd_golden(kdir, out, target_ms, reuse_knob=None):
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
        knob, cur = campaign._knob_line(open(drv).read())
        if knob is not None and reuse_knob is not None:
            # RESUME. Calibration is a property of (module, driver, target_ms, image, rig) and the
            # host has already established that none of them changed, so re-deriving it would only
            # re-measure the reference to land on a different integer.
            #
            # THE DEFECT THIS FIXES, found by the live smoke gate and not by 602 unit tests:
            # `vendor()` re-copies the user's driver at the start of every run, resetting the knob
            # to its written value, so calibration always extrapolated from scratch. Timing noise
            # on that single measurement moved the result by a fraction of a percent every time
            # (33831 -> 33699 on consecutive runs of an unchanged kernel), the calibrated workload
            # is in the measurement cache key, and so EVERY re-run discarded the whole table and
            # re-measured from nothing. The docs claimed cytune resumed; its builds did and its
            # measurements never had.
            _set_knob(drv, knob, reuse_knob)
            calib = {"knob": knob, "cur": cur, "cur_ms": None, "new": reuse_knob,
                     "target_ms": target_ms, "reused": True}
        elif knob is not None and target_ms:
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


def implausible_timings(rows):
    """Configs whose reported time could not physically have elapsed.

    H1, from the adversarial campaign: `measure_child` loads the driver with `exec_module` into the
    very process that calls `perf_counter_ns()` around it, computes the median and prints the JSON
    the host parses. A driver's import-time code therefore runs inside the process that owns the
    clock, and a twelve-line driver produced a certified `5.0000x` on a kernel where no config is
    faster than any other.

    This does not close that hole — see SECURITY.md, which now states it plainly instead of
    claiming the opposite. What it does close is the OVER-claim half, decisively and with no false
    positives: the PARENT process measures `wall_ns` around the whole child, so a child reporting
    `K * median_ns` greater than the wall time that actually elapsed is reporting time that did not
    happen. No honest measurement can do this — spawn, import and build overhead only ever make the
    wall LARGER than the timed region.

    The UNDER-claim direction (a driver reporting less time than it took) is not detectable this
    way, because it is indistinguishable from real spawn overhead — by THIS check. It is attacked
    from the other side by `certify.corroborate_ratio`, which compares the winner's and the
    reference's non-timed remainders instead of one config's claim against its own wall: those two
    share spawn, imports, inputs and K, so the overhead cancels and the under-claim stops hiding
    inside it. See GUARANTEES N8 for the power curve and what it still does not reach.
    """
    bad = []
    for cid, r in rows.items():
        s = r.get("screen") or {}
        med, k, wall = s.get("median_ns"), s.get("K"), s.get("wall_ns")
        if not (med and k and wall):
            continue
        claimed = med * k
        if claimed > wall * 1.02:          # 2% slack for clock granularity between the two timers
            bad.append({"config_id": cid, "claimed_ns": claimed, "wall_ns": wall,
                        "ratio": claimed / wall})
    return bad


def _verify_artifacts(kdir, out, ids, when):
    """Re-hash every .so about to be (or just) measured against its build record.

    The manifest says which FILE to measure; only this says whether that file is still the one that
    was built. A stale artifact left by an interrupted run, a path rewritten between phases, or a
    binary replaced while the workspace sat on disk all reach the measurement otherwise, and every
    downstream check would still pass because every downstream check re-derives its truth from the
    config id.

    Run on both sides of the phase, so the window in which a swap goes unnoticed is the phase
    itself rather than the whole run.
    """
    records = binding.read(out)
    man = campaign._manifest(out) if os.path.exists(
        os.path.join(out, "build_manifest.jsonl")) else {}
    import build as buildmod
    meta = buildmod._meta(kdir)
    drifted = []
    for cid in ids:
        rec = records.get(cid)
        b = man.get(cid) or {}
        if not rec or not b.get("ok"):
            continue
        now = _artifact_digest(out, cid, b.get("so_path"), meta)
        if now != rec.get("artifact_sha256"):
            drifted.append({"config_id": cid, "built": rec.get("artifact_sha256"), "now": now,
                            "when": when})
    return drifted


def cmd_measure(kdir, out, ids):
    before = _verify_artifacts(kdir, out, ids, "before the measure phase")
    if before:
        _emit({"ok": False, "stage": "measure", "error": "artifact_drift",
               "drifted": before,
               "hint": "a compiled artifact changed between the build phase and the measure "
                       "phase. Nothing was measured: a timing of a binary other than the one "
                       "that was built cannot be attributed to a configuration."})
        return

    # B1 — IDENTICAL-ARTIFACT REUSE. Two configs whose .so files hash the same are the same
    # program, so measuring both twice buys a second sample of one number and reports it as two.
    # Measured on the nine dogfood anchors this fires on 0 of 33-49 configs: distinct configs
    # differ in at least one gcc factor and gcc produces distinct bytes. It is kept because when
    # it DOES fire, re-measuring is not merely wasted — a "speedup" between two configs that are
    # byte-identical binaries is measurement noise being certified as a gain.
    records = binding.read(out)
    seen_rows = _rows(out)
    by_artifact = {}
    for cid, rec in records.items():
        if rec.get("artifact_sha256") and cid in seen_rows and seen_rows[cid].get("screen"):
            by_artifact.setdefault(rec["artifact_sha256"], cid)
    reuse, to_measure = {}, []
    for cid in ids:
        h = (records.get(cid) or {}).get("artifact_sha256")
        src = by_artifact.get(h) if h else None
        if src is not None and src != cid and cid not in seen_rows:
            reuse[cid] = src
        else:
            to_measure.append(cid)

    tp, nf = campaign.measure_all(kdir, out, to_measure)
    if reuse:
        _write_reused_rows(out, reuse, seen_rows)
    after = _verify_artifacts(kdir, out, to_measure, "after the measure phase")
    rows = _rows(out, ids)
    payload = {"ok": True, "table": tp, "n_feasible_total": nf,
               "n_measured": len(to_measure), "n_reused_by_identity": len(reuse),
               "reused_by_identity": {str(k): v for k, v in reuse.items()},
               "rows": {str(c): {"feasible": r.get("feasible"), "reason": r.get("reason"),
                                 "median_ns": (r.get("screen") or {}).get("median_ns"),
                                 "rig": r.get("rig"),
                                 "measurement_source": r.get("measurement_source")}
                        for c, r in rows.items()}}
    if after:
        payload["artifact_drift"] = after
    bad = implausible_timings(rows)
    if bad:
        payload["timing_implausible"] = bad
    _emit(payload)


def _write_reused_rows(out, reuse, rows):
    """Record a reused row as what it is: a measurement of a DIFFERENT config id whose binary is
    the same file. Never silently copied — `measurement_source` names the config it came from, so
    the raw table still supports the recompute claim."""
    with open(os.path.join(out, "table.jsonl"), "a") as f:
        for cid, src in sorted(reuse.items()):
            base = dict(rows[src])
            base["config_id"] = cid
            base["factors"] = theta.as_dict(theta.config_of(cid))
            base["measurement_source"] = f"reused-by-identity from config {src}"
            f.write(json.dumps(base) + "\n")


def cmd_endpoint(kdir, out, ids):
    """PREREG §4 endpoint tier on SPECIFIC configs (the winner and the reference).

    campaign.endpoint_tier re-measures the feasible top decile of a full table, which answers the
    study's question. The product's question is narrower — "is THIS winner really faster than the
    reference?" — so the same protocol (median-of-3 K=30 sub-measures, escalate while CV > 0.05, at
    most 5) is applied to a caller-chosen set. The oracle is re-checked here as well: a config that
    passed the screen but fails at endpoint must never be emitted.
    """
    import build as buildmod
    import numpy as np
    mod = campaign._module_of(kdir)
    man = campaign._manifest(out)
    meta = buildmod._meta(kdir)
    records = binding.read(out)
    oracle_path = os.path.join(out, "oracle.json")
    res = {}
    for cid in ids:
        b = man.get(cid, {})
        if not b.get("ok"):
            res[str(cid)] = {"feasible": False, "reason": f"not_built: {b.get('reason')}",
                             "endpoint_ns": None, "n_sub": 0, "subs_ns": []}
            continue
        # I4.1 — hash the binary about to be timed, HERE, not at build time. The build record says
        # what was compiled; this says what was run. They are compared in the host's emission
        # check, and a certificate is refused if they differ.
        timed_sha = _artifact_digest(out, cid, b["so_path"], meta)
        subs, walls, ok, reason = [], [], True, "ok"
        while ok and len(subs) < ENDPOINT_MAX_SUBS:
            m, wall_ns, err = campaign._measure_one(kdir, b["so_path"], cid, mod, 12345,
                                                   oracle_path=oracle_path,
                                                   k_min=ENDPOINT_K, k_max=ENDPOINT_K)
            if m is None:
                ok, reason = False, f"measure_failed: {err}"
                break
            if not m.get("feasible"):
                ok, reason = False, m.get("reason", "oracle_mismatch")
                break
            subs.append(m["median_ns"])
            # C1 — the PARENT's clock. `wall_ns` brackets the whole child from this process, which
            # the child cannot reach. Kept per sub-measure so the non-timed remainder
            # (wall - K x median) can be compared between the winner and the reference: same
            # driver, same K, same inputs, so it must be the same, and it is not when the reported
            # median is not the time that elapsed.
            walls.append(wall_ns)
            if len(subs) >= ENDPOINT_SUBS:
                cv = float(np.std(subs) / np.mean(subs))
                if cv <= ENDPOINT_CV_GATE:
                    break
        # Re-hash AFTER the measurement as well. The read-only mount of `_so` is what makes the
        # swap impossible (rig._readonly_artifacts); this is the evidence that it stayed that way,
        # and it is what would fire if that mount were ever dropped. A hash taken only before the
        # child ran is a hash of a file, not of what was loaded — Attack B.
        after_sha = _artifact_digest(out, cid, b["so_path"], meta)
        if after_sha != timed_sha:
            ok, reason = False, ("artifact_swapped_during_measurement: the .so changed between "
                                 "the hash taken before the endpoint tier and the hash taken "
                                 "after it")
        res[str(cid)] = {
            "feasible": bool(ok and subs), "reason": reason,
            "endpoint_ns": (float(np.median(subs)) if (ok and subs) else None),
            "n_sub": len(subs), "subs_ns": subs, "wall_ns": walls,
            "cv": (float(np.std(subs) / np.mean(subs)) if len(subs) >= 2 else None),
            "K": ENDPOINT_K,
            "artifact_sha256": timed_sha,
            "artifact_sha256_after": after_sha,
            "artifact_sha256_at_build": (records.get(cid) or {}).get("artifact_sha256"),
            "image_digest": IMAGE_DIGEST,
            "rig": campaign._rig()}
    _emit({"ok": True, "endpoints": res, "rig": campaign._rig(),
           "image_digest": IMAGE_DIGEST,
           "screen_overhead_ns": _screen_overheads(out),
           "protocol": {"K": ENDPOINT_K, "subs": ENDPOINT_SUBS, "max_subs": ENDPOINT_MAX_SUBS,
                        "cv_gate": ENDPOINT_CV_GATE}})


def _screen_overheads(out):
    """Every `wall - K x median` this run already paid, from the screen table.

    C1 needs to know how much two of these can honestly differ. Rather than pick a constant, the
    run supplies its own: `campaign.measure_all` records `spawn_overhead_ns` for every config it
    screened, which is exactly the same quantity measured tens of times on this machine, this
    kernel and this driver. The corroboration budget is derived from their spread.
    """
    return sorted(r["screen"]["spawn_overhead_ns"] for r in _rows(out).values()
                  if (r.get("screen") or {}).get("spawn_overhead_ns") is not None)


# ------------------------------------------------------------------ pure compute
def cmd_features(kdir, out):
    ids = probe.probe_config_ids()
    _emit({"ok": True, "features": probe.features(_rows(out, ids)),
           "probe_ids": ids})


def cmd_screen(kdir, out, budget, second_screen=False):
    _emit({"ok": True, **plan.screen_plan(budget, second_screen=second_screen)})


def cmd_walk(kdir, out, budget, policy):
    rows = _rows(out)
    feas = {c: r["screen"]["median_ns"] for c, r in rows.items()
            if r.get("feasible") and r.get("screen")}
    queried = set(rows)
    _emit({"ok": True, **plan.walk_plan(feas, queried, budget, policy=policy),
           "n_queried": len(queried)})


_POLICY_FLAGS = ("--allow-fast-math", "--allow-fp-contract", "--portable-flags")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    policy = plan.EmissionPolicy(
        allow_fast_math="--allow-fast-math" in argv,
        allow_fp_contract="--allow-fp-contract" in argv,
        portable_flags="--portable-flags" in argv)
    argv = [a for a in argv if a not in _POLICY_FLAGS]
    cmd, kdir, out = argv[0], argv[1], argv[2]
    rest = argv[3:]
    if cmd == "build":
        cmd_build(kdir, out, _ids(rest[0]))
    elif cmd == "golden":
        cmd_golden(kdir, out, float(rest[0]) if rest else 0.0,
                   reuse_knob=(int(rest[1]) if len(rest) > 1 and rest[1] != "-" else None))
    elif cmd == "measure":
        cmd_measure(kdir, out, _ids(rest[0]))
    elif cmd == "endpoint":
        cmd_endpoint(kdir, out, _ids(rest[0]))
    elif cmd == "features":
        cmd_features(kdir, out)
    elif cmd == "screen":
        cmd_screen(kdir, out, int(rest[0]), second_screen="--second-screen" in rest)
    elif cmd == "walk":
        cmd_walk(kdir, out, int(rest[0]), policy)
    else:
        raise SystemExit(f"unknown cytune.worker command: {cmd}")


if __name__ == "__main__":
    main()
