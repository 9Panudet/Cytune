"""STAGE B — bounded ASan+UBSan spot audit, memoized per SAFETY CLASS × TEMPLATE FAMILY.

WHY THIS EXISTS. Roadmap §1.4 makes the sanitizer a feasibility gate: a candidate that reports
under ASan/UBSan is infeasible. The Phase-P fleet harness NEVER INVOKED IT — every one of the
~149 kernels × 1,728 configs was gated on the ORACLE alone. That is a campaign-wide gate lapse,
recorded in DEVIATIONS_REGISTER.md. Re-running the gate at full cross is 257k sanitizer builds and
is not affordable; this script is the bounded remediation the human authorized: cover EVERY
template family at the RISK CORNERS of the §1.4 6-dim safety-class key, and report the result as
evidence with its scope stated, never as if the gate had run.

SCOPE, stated so it cannot be overread:
  - covered: every distinct `template` in the fleet (synthetic) + every Dataset-R anchor,
    at 3 configs each;
  - NOT covered: the other 1,725 configs per kernel, and the parameterization differences between
    two kernels of the same template.
  A clean result here is evidence that the template families' UB surface is clean at the corners
  where UB is most likely — it is NOT the §1.4 gate, and this script must never be cited as if it
  were.

THE CORNERS (each is a distinct `theta.safety_class`, so the memo key does real work):
  1. REFERENCE            — as-shipped Cython defaults; every runtime check the reference has.
  2. CHECKS-OFF           — boundscheck/wraparound/initializedcheck/nonecheck off, cdivision on,
                            -O3 -march=native -funroll-loops. Removing boundscheck is exactly what
                            converts a latent index bug into an out-of-bounds write, so this is
                            the corner where ASan earns its keep.
  3. CHECKS-OFF+FASTMATH  — corner 2 plus -ffast-math (fast_math IS in the safety-class key).
`-O` and `-march` are NOT in the safety-class key (§3.3), so the sanitizer build pins -O1 per
`profiles.SANITIZER`; the corners still differ in the key's own dimensions.

Runs IN the pinned container. Builds + runs only — no timing — so it may use all cores and does
NOT need a quiesced rig (it must still not overlap a timed measurement; CF-1 guard below).

  podman run --rm --security-opt label=disable -v "$PWD":/w -w /w -e PYTHONPATH=/w/src \\
      localhost/motifbo-env:phase1 python3 scripts/phasep/sanitizer_spot_audit.py
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "src"))

import build as bld                                        # noqa: E402
import san_overlay                                         # noqa: E402
import theta                                               # noqa: E402
from motifbo.build.profiles import (sanitizer_argv,        # noqa: E402
                                    sanitizer_runtime_env)

FLEET = os.path.join(REPO, "results", "fleet")
KROOT = os.path.join(FLEET, "_kernels")
OUT = os.path.join(REPO, "results", "sanitize", "phasep_spot_audit")

# A sanitizer report is decisive (halt_on_error=1) but the tokens are also matched textually,
# because a report that does not kill the process must not be silently accepted.
SAN_TOKENS = ("AddressSanitizer", "LeakSanitizer", "runtime error", "buffer-overflow",
              "use-after", "stack-overflow", "SUMMARY: AddressSanitizer",
              "SUMMARY: UndefinedBehavior", "UndefinedBehaviorSanitizer")

# (name, config) — see the module docstring for why these three.
CORNERS = [
    ("reference", theta.REFERENCE),
    ("checks_off_O3_native_unroll",
     (False, False, True, False, False, "-O3", "native", "on", ("off", "off"))),
    ("checks_off_fastmath_native",
     (False, False, True, False, False, "-O3", "native", "on", ("on", "NA"))),
]
N_REPS = 3          # 3 distinct input seeds per (kernel, corner) — see san_child.py
TIMEOUT_S = 900     # ASan on an R anchor's real input is slow; generous, still bounded


def _busy():
    r = subprocess.run(["bash", os.path.join(REPO, "scripts", "hooks", "campaign_busy.sh")],
                       capture_output=True, text=True)
    return r.returncode == 0, (r.stdout or "").strip()


def _spec(kid):
    p = os.path.join(KROOT, kid, "spec.json")
    return json.load(open(p)) if os.path.exists(p) else None


CONTROL_ROOT = os.path.join(HERE, "san_controls")
# A new instrument's readings do not count until it has been shown to DETECT a planted defect and
# to stay quiet on a known-good one. `--controls` runs both; the expected verdicts are asserted.
CONTROL_EXPECT = {
    # (kernel, corner) -> expected verdict. Under boundscheck ON the planted read raises IndexError
    # before it happens, so the reference corner is a RUN_FAIL, not a sanitizer report — that
    # asymmetry is itself the evidence that boundscheck is what stands between the fleet and the
    # overflow, which is exactly the claim the checks-off corners are testing.
    ("ctrl_oob", "reference"): "RUN_FAIL_NO_TOKEN",
    ("ctrl_oob", "checks_off_O3_native_unroll"): "SANITIZER_REPORT",
    ("ctrl_oob", "checks_off_fastmath_native"): "SANITIZER_REPORT",
    ("ctrl_clean", "reference"): "CLEAN",
    ("ctrl_clean", "checks_off_O3_native_unroll"): "CLEAN",
    ("ctrl_clean", "checks_off_fastmath_native"): "CLEAN",
    # ctrl_oob_under plants the UNDER-read a[-1] — the exact direction of the D23 defect, where
    # ctrl_oob plants an over-read. Without it the rig's sensitivity to the LEFT redzone rested on
    # the very readings it was supposed to validate.
    #
    # The reference row is CLEAN, and I predicted RUN_FAIL_NO_TOKEN. The prediction was wrong and
    # the control is right: the reference config has wraparound=TRUE, so `a[-1]` is translated to
    # `a[n-1]` — in bounds, well defined, no IndexError and nothing for ASan to see. ctrl_oob's
    # over-read `a[n+15]` cannot wrap, which is why THAT one trips boundscheck at the reference.
    # The asymmetry between these two rows IS the D23 mechanism exhibited directly: it is
    # wraparound=False, not boundscheck=False alone, that turns the trap into an out-of-bounds
    # read. Corrected here rather than quietly, because the wrong prediction is the evidence.
    ("ctrl_oob_under", "reference"): "CLEAN",
    ("ctrl_oob_under", "checks_off_O3_native_unroll"): "SANITIZER_REPORT",
    ("ctrl_oob_under", "checks_off_fastmath_native"): "SANITIZER_REPORT",
}


def roster(controls=False):
    """One representative kernel per (TEMPLATE, FEAS_VARIANT, trap-armed) group, plus every
    Dataset-R anchor.

    The memo key is NOT the template alone. `feas_variant` decides whether the kernel plants a
    correctness trap at all, and the driver decides whether that trap is ARMED (`guard=1`) — both
    vary between kernels of the same template. A template-only key picks a representative that may
    be unarmed while its siblings are armed, and then reports the whole family clean. That is
    exactly what happened on the first run: `int_min32`'s representative was the unarmed
    `fleet_INT_07`, so the three armed `int_min32`/`int_max32` kernels that D23 turned on were
    structurally outside the roster. Memoizing on the property that determines the answer is the
    whole point of memoizing.

    Representative = the lexicographically first kernel_id in each group, so the roster is a
    deterministic function of the committed tree and cannot be steered by results."""
    if controls:
        return sorted((k, k, "control") for k in os.listdir(CONTROL_ROOT)
                      if os.path.isdir(os.path.join(CONTROL_ROOT, k)))
    groups, anchors = {}, []
    for kid in sorted(os.listdir(KROOT)):
        kdir = os.path.join(KROOT, kid)
        if not os.path.isdir(kdir) or not os.path.exists(os.path.join(kdir, "driver.py")):
            continue
        sp = _spec(kid) or {}
        if kid.startswith("fleet_R_"):
            anchors.append((kid, sp.get("template") or kid, "R"))
            continue
        t = sp.get("template")
        if not t:
            continue
        fv = sp.get("feas_variant")
        armed = ", 1)" in open(os.path.join(kdir, "driver.py")).read()
        key = (t, fv, armed)
        if key not in groups:
            groups[key] = (kid, f"{t}|{fv}|{'armed' if armed else 'unarmed'}", "synthetic")
    out = sorted(groups.values()) + sorted(anchors)
    # EVERY kernel the §1.4 overlay touches gets its OWN direct reading, memoization notwithstanding.
    # Found by the validation-auditor (F1): `fleet_INT_20_int_sum64_r3` has template `int_min32`,
    # the same group key as `fleet_INT_14_int_min32`, so the group representative stood in for it —
    # and the overlay artifact then claimed "ASan confirmed on each affected kernel" when a third of
    # the overlaid cells rested on a sibling's reading. A kernel whose FEASIBILITY LABELS this
    # campaign rewrites is not a kernel that may be represented by a proxy.
    have = {k for k, _t, _kd in out}
    for kid in sorted(san_overlay.load(FLEET)):
        if kid not in have:
            sp = _spec(kid) or {}
            out.append((kid, f"{sp.get('template')}|overlay-affected", "synthetic"))
    return out


def _sanitizer_build(kdir, config, cache_dir, so_dir, module_hint):
    """Cythonize via THE campaign builder (so the C is byte-identical to what was measured), then
    link with profiles.sanitizer_argv instead of the performance profile. Returns dict."""
    meta = bld._meta(kdir)
    fm_on = config[8][0] == "on"
    _d, _o, ffp, _l = theta.build_flags(config)
    os.makedirs(so_dir, exist_ok=True)
    if meta and meta.get("cobuild"):
        # Co-build anchors: cythonize every module, then link them all with the sanitizer flags
        # into a per-config copy of the closure tree (same layout measure_child imports from).
        cid = theta.id_of(config)
        combo = bld._combo_key(config)
        work = os.path.join(cache_dir, f"sanwork_{combo}")
        if os.path.exists(work):
            shutil.rmtree(work)
        shutil.copytree(os.path.join(kdir, "closure"), work)
        dirs = _d
        c_map = []
        for pyx_rel, mod in meta["cobuild"]:
            c_path = os.path.join(cache_dir, f"san_{mod}_{combo}.c")
            if not os.path.exists(c_path):
                r = subprocess.run(["cython", "-3"] + dirs.split() + ["-I", ".", pyx_rel,
                                                                     "-o", c_path],
                                   cwd=work, capture_output=True, text=True)
                if r.returncode != 0 or not os.path.exists(c_path):
                    shutil.rmtree(work, ignore_errors=True)
                    return {"ok": False, "reason": "cythonize_fail",
                            "log": (r.stdout + r.stderr)[-600:]}
            c_map.append((pyx_rel, mod, c_path))
        shutil.rmtree(work, ignore_errors=True)
        pkg_root = os.path.join(so_dir, f"sanpkg_{cid}")
        if os.path.exists(pkg_root):
            shutil.rmtree(pkg_root)
        shutil.copytree(os.path.join(kdir, "closure"), pkg_root,
                        ignore=shutil.ignore_patterns("*.c"))
        main_so = None
        for pyx_rel, mod, c_path in c_map:
            so = os.path.join(pkg_root, pyx_rel[:-4] + ".so")
            argv = sanitizer_argv(ffp_contract=ffp, c_path=c_path, so_path=so,
                                  py_include=bld.PYINC, fast_math=fm_on)
            argv = argv[:1] + [f"-I{bld.NPINC}"] + argv[1:]
            if meta.get("openmp"):
                argv = argv[:1] + ["-fopenmp"] + argv[1:]
            r = subprocess.run(argv, capture_output=True, text=True)
            if r.returncode != 0 or not os.path.exists(so):
                return {"ok": False, "reason": "build_fail",
                        "log": f"{mod}: " + (r.stdout + r.stderr)[-600:]}
            main_so = so
        return {"ok": True, "so_path": main_so, "module": meta["module"]}

    if meta:
        c_path, ok, clog = bld._cythonize_closure(kdir, config, cache_dir, meta)
        module = meta["module"]
    else:
        c_path, ok, clog = bld._cythonize_synth(kdir, config, cache_dir)
        module = module_hint
    if not ok:
        return {"ok": False, "reason": "cythonize_fail", "log": clog}
    so = os.path.join(so_dir, f"san_{module}_{theta.id_of(config)}.so")
    argv = sanitizer_argv(ffp_contract=ffp, c_path=c_path, so_path=so,
                          py_include=bld.PYINC, fast_math=fm_on)
    argv = argv[:1] + [f"-I{bld.NPINC}"] + argv[1:]
    r = subprocess.run(argv, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(so):
        return {"ok": False, "reason": "build_fail", "log": (r.stdout + r.stderr)[-600:]}
    return {"ok": True, "so_path": so, "module": module}


def audit_one(kid, template, kind, corner_name, config, san_env, scratch):
    t0 = time.time()
    kdir = os.path.join(CONTROL_ROOT if kind == "control" else KROOT, kid)
    work = os.path.join(scratch, f"{kid}__{corner_name}")
    os.makedirs(work, exist_ok=True)
    rec = {"kernel_id": kid, "template": template, "kind": kind, "corner": corner_name,
           "config_id": theta.id_of(config),
           "safety_class": list(theta.safety_class(config))}
    b = _sanitizer_build(kdir, config, os.path.join(work, "cache"),
                         os.path.join(work, "so"), "kernel")
    if not b["ok"]:
        # A build that does not exist was never audited. It is NOT a clean result.
        rec.update({"verdict": "BUILD_FAIL", "clean": None, "reason": b["reason"],
                    "log": b.get("log", "")[-600:], "elapsed_s": round(time.time() - t0, 1)})
        return rec
    p = subprocess.run([sys.executable, os.path.join(HERE, "san_child.py"), kdir, b["so_path"],
                        str(N_REPS), "20260730", "--module", b["module"]],
                       capture_output=True, text=True, env=san_env, timeout=TIMEOUT_S)
    blob = p.stdout + p.stderr
    tokens = sorted({t for t in SAN_TOKENS if t in blob})
    ok_marker = "SAN_CHILD_OK" in p.stdout
    if tokens:
        verdict, clean = "SANITIZER_REPORT", False
    elif p.returncode != 0 or not ok_marker:
        # rc!=0 with no token: a Python-level failure, e.g. the driver cannot build its inputs.
        # Distinct finding, distinct name — never folded into "clean".
        verdict, clean = "RUN_FAIL_NO_TOKEN", None
    else:
        verdict, clean = "CLEAN", True
    rec.update({"verdict": verdict, "clean": clean, "returncode": p.returncode,
                "tokens": tokens, "elapsed_s": round(time.time() - t0, 1),
                "stderr_excerpt": "" if clean else blob[-1500:]})
    shutil.rmtree(work, ignore_errors=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--allow-busy", action="store_true")
    ap.add_argument("--only", default=None, help="substring filter on kernel_id (smoke runs)")
    ap.add_argument("--controls", action="store_true",
                    help="run the positive/negative controls and assert the expected verdicts")
    a = ap.parse_args()
    if not a.allow_busy:
        busy, why = _busy()
        if busy:
            raise SystemExit(f"CF-1: box is BUSY ({why}) — the spot audit must not overlap a "
                             f"timed measurement")
    asan_lib = subprocess.run(["gcc", "-print-file-name=libasan.so"],
                              capture_output=True, text=True, check=True).stdout.strip()
    san_env = {**os.environ, **sanitizer_runtime_env(asan_lib)}
    san_env["PYTHONDONTWRITEBYTECODE"] = "1"

    work = [(k, t, kd, cn, cfg) for (k, t, kd) in roster(controls=a.controls)
            for (cn, cfg) in CORNERS if not a.only or a.only in k]
    print(f"spot audit{' [CONTROLS]' if a.controls else ''}: {len(work)} (kernel × corner) "
          f"units, jobs={a.jobs}", flush=True)
    scratch = tempfile.mkdtemp(prefix="sanaudit_")
    recs, t0 = [], time.time()
    with cf.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futs = {ex.submit(audit_one, k, t, kd, cn, cfg, san_env, scratch): (k, cn)
                for (k, t, kd, cn, cfg) in work}
        for f in cf.as_completed(futs):
            k, cn = futs[f]
            try:
                r = f.result()
            except Exception as e:                      # timeout or harness failure
                r = {"kernel_id": k, "corner": cn, "verdict": "HARNESS_ERROR",
                     "clean": None, "error": repr(e)[:400]}
            recs.append(r)
            print(f"  [{len(recs):3d}/{len(work)}] {r['kernel_id']:44s} {cn:28s} "
                  f"{r['verdict']}", flush=True)
    shutil.rmtree(scratch, ignore_errors=True)

    recs.sort(key=lambda r: (r["kernel_id"], r.get("corner", "")))
    if a.controls:
        bad = [(r["kernel_id"], r["corner"], r["verdict"],
                CONTROL_EXPECT.get((r["kernel_id"], r["corner"])))
               for r in recs if r["verdict"] != CONTROL_EXPECT.get((r["kernel_id"], r["corner"]))]
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, "controls.json"), "w") as f:
            json.dump({"schema": "phasep-sanitizer-spot-audit-controls-v1",
                       "expected": {f"{k}|{c}": v for (k, c), v in CONTROL_EXPECT.items()},
                       "units": recs, "mismatches": bad, "pass": not bad}, f, indent=1)
        for k, c, got, exp in bad:
            print(f"  CONTROL MISMATCH {k} {c}: got {got}, expected {exp}")
        print(f"\ncontrols: {'PASS' if not bad else 'FAIL'} "
              f"({len(recs) - len(bad)}/{len(recs)} as expected) -> {OUT}/controls.json")
        sys.exit(1 if bad else 0)
    reports = [r for r in recs if r["verdict"] == "SANITIZER_REPORT"]
    unaudited = [r for r in recs if r.get("clean") is None]
    summary = {
        "schema": "phasep-sanitizer-spot-audit-v1",
        "why": "roadmap §1.4 sanitizer gate was never invoked by the Phase-P fleet harness; this "
               "is the bounded remediation, NOT the gate",
        "scope": {"templates_and_anchors": len(roster()), "corners": [c for c, _ in CORNERS],
                  "configs_per_kernel": len(CORNERS), "configs_in_theta": theta.N_CONFIGS,
                  "reps_per_unit": N_REPS,
                  "not_covered": "the other configs per kernel; parameterization differences "
                                 "within a template family"},
        "sanitizer_build": "-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer "
                           "(profiles.SAN_FIXED) + explicit -ffp-contract",
        "runtime_env": {k: san_env[k] for k in ("ASAN_OPTIONS", "UBSAN_OPTIONS", "LD_PRELOAD")},
        "asan_lib": asan_lib,
        "image_id": os.environ.get("MOTIFBO_IMAGE_ID", "unknown"),
        "n_units": len(recs),
        "n_clean": sum(1 for r in recs if r.get("clean") is True),
        "n_sanitizer_reports": len(reports),
        "n_unaudited": len(unaudited),
        "all_clean": len(reports) == 0 and len(unaudited) == 0,
        "elapsed_s": round(time.time() - t0, 1),
        "units": recs,
        "recompute": ("podman run --rm --security-opt label=disable -v \"$PWD\":/w -w /w "
                      "-e PYTHONPATH=/w/src localhost/motifbo-env:phase1 python3 "
                      "scripts/phasep/sanitizer_spot_audit.py"),
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "spot_audit.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(f"\nunits {summary['n_units']}  clean {summary['n_clean']}  "
          f"SANITIZER REPORTS {summary['n_sanitizer_reports']}  "
          f"unaudited(build/run fail) {summary['n_unaudited']}  "
          f"-> {OUT}/spot_audit.json  ({summary['elapsed_s']}s)")
    for r in reports + unaudited:
        print(f"  !! {r['kernel_id']} {r.get('corner')} {r['verdict']} "
              f"{r.get('tokens') or r.get('reason') or ''}")
    # Exit non-zero on a sanitizer report: the TRIPWIRE must be visible to the shell, not only
    # in JSON. Unaudited units are also non-zero — an un-run check is not a passed check.
    sys.exit(1 if not summary["all_clean"] else 0)


if __name__ == "__main__":
    main()
