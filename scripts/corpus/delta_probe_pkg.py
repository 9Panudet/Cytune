"""Step-1.3.1 Δ-probe for PACKAGE-IMPORT multi-module units (elkan, predictor).

Same 16 PRE-REGISTERED configs as delta_probe.py (CHK·DIV·OPT·FP, imported from it — single
source of truth), same Δ(unit)=t_worst/t_best, same /out/<unit>.json schema. The difference:
these kernels' .so does a RELATIVE import of a sibling vendored .so (from ._k_means_common /
from ._bitset), so they cannot be bare-loaded (spec_from_file_location sets __package__='').
They are built as a PACKAGE: each module in u['cobuild'] (dep order) is cythonized+compiled
IN PLACE in a per-config copy of the closure, then timed via importlib.import_module(pkg_module)
with the closure on sys.path[0]. Each config is timed in a FRESH subprocess (§3.2(2) FTZ/DAZ).

NEVER fabricates: every median_ns is a real kernel call; cythonize/compile failure -> feasibility-0
(excluded from the ratio). Runs INSIDE :phase1 with the closure mounted at /unit/closure.

Usage (in-container):
  delta_probe_pkg.py <unit_key> [nreps=25]              # orchestrate 16 configs
  delta_probe_pkg.py time-one <unit_key> <closure_dir> <scale_json> <nreps>   # internal
"""
import json
import os
import shutil
import statistics
import subprocess
import sys
import time

sys.path.insert(0, "/probe/corpus")
import corpus_drivers as cd  # noqa: E402
from delta_probe import configs, delta  # noqa: E402  (identical 16-config factorial + Δ)

CLOSURE_SRC = "/unit/closure"


def _incs():
    import sysconfig
    import numpy as np
    return sysconfig.get_path("include"), np.get_include()


def build_pkg(u, cfg):
    """Cythonize+compile every cobuild module (dep order) IN PLACE in a per-config closure copy."""
    work = f"/tmp/pkgprobe_{cfg['label']}/closure"
    if os.path.isdir(os.path.dirname(work)):
        shutil.rmtree(os.path.dirname(work))
    shutil.copytree(CLOSURE_SRC, work)
    pyinc, npinc = _incs()
    logs = []
    for pyx_rel, mod in u["cobuild"]:
        cbase = os.path.join(work, pyx_rel[:-4])           # strip .pyx
        for ext in (".c", ".so"):
            try:
                os.remove(cbase + ext)
            except OSError:
                pass
        cy = ["cython", "-3", *cfg["cydirs"].split(), "-I", ".", pyx_rel, "-o", cbase + ".c"]
        rc = subprocess.run(cy, cwd=work, capture_output=True, text=True)
        if not os.path.exists(cbase + ".c"):
            return work, False, f"CYTHONIZE {mod}: {(rc.stdout + rc.stderr)[-300:]}"
        gcc = ["gcc-13", "-shared", "-fPIC", *cfg["opt_flags"].split(),
               f"-ffp-contract={cfg['ffp']}", "-fopenmp", "-g0", "-pipe",
               "-I", pyinc, "-I", npinc, cbase + ".c", "-o", cbase + ".so"]
        rc = subprocess.run(gcc, cwd=work, capture_output=True, text=True)
        if not os.path.exists(cbase + ".so"):
            return work, False, f"COMPILE {mod}: {(rc.stdout + rc.stderr)[-300:]}"
    return work, True, None


def time_pkg(unit_key, closure_dir, scale, nreps):
    cmd = ["python", "/probe/corpus/delta_probe_pkg.py", "time-one", unit_key,
           closure_dir, json.dumps(scale), str(nreps)]
    env = dict(os.environ, OMP_NUM_THREADS="1", PYTHONPATH="/probe/corpus")
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        return None, (r.stdout + r.stderr)[-400:]
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])["median_ns"], None
    except Exception as e:  # noqa: BLE001
        return None, f"parse {e}: {r.stdout[-300:]} {r.stderr[-200:]}"


def _time_one():
    unit_key, closure_dir, scale_json, nreps = sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
    sys.path.insert(0, closure_dir)                        # closure sklearn shadows installed
    import importlib
    u = cd.UNITS[unit_key]
    m = importlib.import_module(u["pkg_module"])
    fn = getattr(m, u["kernel"])
    setup_code = u["setup"](json.loads(scale_json))
    mutated = u.get("mutated_arg_indices") or []
    regen = bool(mutated) and not u.get("recallable", False)

    def mk():
        ns = {"__name__": "setup"}
        exec(setup_code, ns)  # noqa: S102
        return tuple(ns["args"]), dict(ns.get("kwargs", {}))

    args, kwargs = mk()
    for _ in range(3):
        if regen:
            args, kwargs = mk()
        fn(*args, **kwargs)                                # warmup
    samples = []
    for _ in range(nreps):
        if regen:
            args, kwargs = mk()                            # UNTIMED fresh input
        t0 = time.perf_counter_ns(); fn(*args, **kwargs); samples.append(time.perf_counter_ns() - t0)
    print(json.dumps({"unit": unit_key, "median_ns": statistics.median(samples),
                      "min_ns": min(samples), "max_ns": max(samples)}))


def main():
    unit_key = sys.argv[1]
    nreps = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    nsub = int(sys.argv[3]) if len(sys.argv) > 3 else 1   # >1 => median-of-nsub-subprocess ENDPOINT
    u = cd.UNITS[unit_key]
    endpoint = nsub > 1
    scale = u.get("endpoint_scale", u["delta_scale"]) if endpoint else u["delta_scale"]
    results = []
    import statistics as _st
    for cfg in configs():
        work, ok, err = build_pkg(u, cfg)
        rec = {"label": cfg["label"], "fp": cfg["fp"], "opt_flags": cfg["opt_flags"],
               "ffp": cfg["ffp"], "cydirs": cfg["cydirs"], "build_ok": ok, "build_rc": 0 if ok else 3}
        if ok:
            subs = []
            for _ in range(nsub):                          # nsub FRESH subprocesses (FTZ/DAZ isolation)
                med, terr = time_pkg(unit_key, work, scale, nreps)
                if med is not None:
                    subs.append(med)
            rec["median_ns"] = _st.median(subs) if subs else None   # median-of-subprocess
            rec["subproc_medians_ns"] = subs
            if not subs:
                rec["time_err"] = terr
        else:
            rec["build_log"] = err
        results.append(rec)
        print(json.dumps({"label": rec["label"], "build_ok": ok,
                          "median_ns": rec.get("median_ns")}), flush=True)

    timed = [r for r in results if r.get("median_ns")]
    feasible = [r for r in timed if r["fp"] == "T"]
    summ = {"unit": unit_key, "module": u["module"], "fold": u["fold"],
            "archetype": u.get("archetype"), "scale": scale, "nreps": nreps, "nsub": nsub,
            "rig": ("v1.4 endpoint (median-of-%d-subprocess, pkg)" % nsub) if endpoint
                   else "screen (in-process median, pkg)",
            "n_built": sum(r["build_ok"] for r in results), "n_timed": len(timed),
            "delta_all": delta(timed), "delta_feasible_strict": delta(feasible),
            "t_best_ns": min((r["median_ns"] for r in timed), default=None),
            "t_worst_ns": max((r["median_ns"] for r in timed), default=None),
            "best_label": min(timed, key=lambda r: r["median_ns"])["label"] if timed else None,
            "worst_label": max(timed, key=lambda r: r["median_ns"])["label"] if timed else None,
            "build_path": "package-import multi-module co-build (delta_probe_pkg.py)",
            "configs": results}
    os.makedirs("/out", exist_ok=True)
    out_name = f"{unit_key}__endpoint.json" if endpoint else f"{unit_key}.json"
    with open(f"/out/{out_name}", "w") as fh:
        json.dump(summ, fh, indent=2)
    print(json.dumps({k: summ[k] for k in ("unit", "delta_all", "delta_feasible_strict",
                                           "t_best_ns", "t_worst_ns", "best_label",
                                           "worst_label", "n_built", "n_timed")}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "time-one":
        _time_one()
    else:
        main()
