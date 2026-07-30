"""Step-1.3.1 fixed 16-config Δ-probe orchestrator (PREREG_DELTA_PROBE.md).

Runs INSIDE the pinned :phase1 container (via measure_wrap), ONE unit per invocation with that
unit's closure mounted at /unit/closure. For each of the 16 PRE-REGISTERED configs it BUILDS the
unit (build_unit.sh) then TIMES it in a FRESH subprocess (gate_runner scale-probe) so each config's
FTZ/DAZ MXCSR state is isolated (§3.2(2) fresh-subprocess rule). Computes Δ(unit)=t_worst/t_best.

NEVER fabricates: every median_ns comes from a real kernel call; cythonize/compile failure is
recorded as feasibility-0 (excluded from the ratio, not silently dropped). Raw -> /out/<unit>.json.

Usage (in-container): delta_probe.py <unit_key> [nreps=25]
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, "/probe/corpus")
import corpus_drivers as cd  # noqa: E402

# The 16 pre-registered configs (label = CHK·DIV·OPT·FP). See PREREG_DELTA_PROBE.md.
CHK = {"S": "-X boundscheck=True -X wraparound=True -X initializedcheck=True -X nonecheck=True",
       "U": "-X boundscheck=False -X wraparound=False -X initializedcheck=False -X nonecheck=False"}
DIV = {"P": "-X cdivision=False", "C": "-X cdivision=True"}
OPT = {"L": "-O1 -march=x86-64", "H": "-O3 -march=native -funroll-loops"}
FP = {"T": ("", "off"), "A": ("-ffast-math", "fast")}   # (extra gcc flag, ffp-contract)


def configs():
    out = []
    for chk in "SU":
        for div in "PC":
            for opt in "LH":
                for fp in "TA":
                    extra, ffp = FP[fp]
                    opt_flags = (OPT[opt] + (" " + extra if extra else "")).strip()
                    out.append({"label": chk + div + opt + fp, "fp": fp,
                                "cydirs": f"{CHK[chk]} {DIV[div]}",
                                "opt_flags": opt_flags, "ffp": ffp})
    return out


def build(u, cfg):
    so_dir = f"/tmp/probe_{cfg['label']}"
    os.makedirs(so_dir, exist_ok=True)
    so = f"{so_dir}/{u['mod']}.so"
    if os.path.exists(so):
        os.remove(so)
    cmd = ["bash", "/probe/corpus/build_unit.sh", u["pyx"], u["mod"], so,
           cfg["opt_flags"], cfg["ffp"], u.get("lang", "c"), cfg["cydirs"]]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = (r.returncode == 0 and os.path.exists(so))
    return so, ok, r.returncode, (r.stdout + r.stderr)[-500:]


def time_so(unit_key, so, scale, nreps):
    cmd = ["python", "/probe/corpus/gate_runner.py", "scale-probe", unit_key, so,
           json.dumps(scale), str(nreps)]
    env = dict(os.environ, PYTHONPATH="/src")
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        return None, (r.stdout + r.stderr)[-500:]
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])["median_ns"], None
    except Exception as e:  # noqa: BLE001
        return None, f"parse {e}: {r.stdout[-300:]} {r.stderr[-200:]}"


def delta(rs):
    ts = [r["median_ns"] for r in rs if r.get("median_ns")]
    return (max(ts) / min(ts)) if len(ts) >= 2 else None


def main():
    unit_key = sys.argv[1]
    nreps = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    u = cd.UNITS[unit_key]
    scale = u["delta_scale"]
    results = []
    for cfg in configs():
        so, ok, rc, log = build(u, cfg)
        rec = {"label": cfg["label"], "fp": cfg["fp"], "opt_flags": cfg["opt_flags"],
               "ffp": cfg["ffp"], "cydirs": cfg["cydirs"], "build_ok": ok, "build_rc": rc}
        if ok:
            med, err = time_so(unit_key, so, scale, nreps)
            rec["median_ns"] = med
            if med is None:
                rec["time_err"] = err
        else:
            rec["build_log"] = log
        results.append(rec)
        print(json.dumps({"label": rec["label"], "build_ok": ok,
                          "median_ns": rec.get("median_ns")}), flush=True)

    timed = [r for r in results if r.get("median_ns")]
    feasible = [r for r in timed if r["fp"] == "T"]    # strict bit-preserving subset
    summ = {"unit": unit_key, "module": u["module"], "fold": u["fold"],
            "archetype": u.get("archetype"), "scale": scale, "nreps": nreps,
            "n_built": sum(r["build_ok"] for r in results), "n_timed": len(timed),
            "delta_all": delta(timed), "delta_feasible_strict": delta(feasible),
            "t_best_ns": min((r["median_ns"] for r in timed), default=None),
            "t_worst_ns": max((r["median_ns"] for r in timed), default=None),
            "best_label": min(timed, key=lambda r: r["median_ns"])["label"] if timed else None,
            "worst_label": max(timed, key=lambda r: r["median_ns"])["label"] if timed else None,
            "configs": results}
    os.makedirs("/out", exist_ok=True)
    with open(f"/out/{unit_key}.json", "w") as fh:
        json.dump(summ, fh, indent=2)
    print(json.dumps({k: summ[k] for k in ("unit", "delta_all", "delta_feasible_strict",
                                           "t_best_ns", "t_worst_ns", "best_label",
                                           "worst_label", "n_built", "n_timed")}, indent=2))


if __name__ == "__main__":
    main()
