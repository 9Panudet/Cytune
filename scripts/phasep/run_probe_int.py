"""A-2 Part-3 — bounded strict-INT probe (protocol committed BEFORE any probe run).

QUESTION: does Θ admit AND-gate mechanisms on the STRICT axis (fast_math=off) with Δ_strict ≥ 1.3
and a super-additive interaction signal, i.e. can taxonomy-v2 class INT be populated by generator
v2 with mechanism diversity? (ctrl_planted already evidences ONE strict-INT mechanism — elementwise
map vectorization, Δ_strict=10.18, IF_strict=0.41, raw results/pilot/pilot_ctrl_planted/ — so this
probe decides mechanism DIVERSITY, not bare existence; see A2_DECISION_MEMO.md Part 3.)

CANDIDATES (4, pre-registered; each a 2^4 factorial = 16 configs + the reference config):
  P1 int64-sum-reduction   — hypothesized gate boundscheck × opt_level. Integer addition is
     associative, so the reduction vectorizes WITHOUT fast-math, but only if the bc branch is gone
     (bc=False) AND the vectorizer runs (-O3). No partial payoff at bc=False∧-O1 or bc=True∧-O3.
  P2 int32-min-reduction   — same gate, conditional-min form (vpminsd); tests whether conditional
     reductions AND-gate the same way at 8 lanes.
  P3 int64-mod-by-constant — hypothesized gate cdivision × opt_level. cdivision=False emits Python
     division semantics (sign/zero handling) that block constant-divisor strength reduction;
     payoff needs cdivision=True AND -O3. Inputs are NON-NEGATIVE so C and Python semantics agree
     exactly and the oracle is unaffected (the checks differ in COST, not in RESULT).
  P4 int64-reversed-sum    — hypothesized gate wraparound × opt_level. a[n-1-i] cannot be proven
     non-negative, so wraparound=True emits per-access wrap handling that blocks vectorization;
     payoff needs wraparound=False AND -O3.
Design per candidate: vary {gate-directive, opt_level(-O1,-O3), march(x86-64,native),
funroll(omit,on)}; pin all other directives PERMISSIVE (bc=False, wrap=False, cdiv=True,
initializedcheck=False, nonecheck=False except where varied); fmffp=("off","off") ALWAYS (strict by
construction — all-integer kernels have no fast-math surface at all). march/funroll are context
factors (vector width / unroll), marginalized in the analysis.

ANALYSIS (pre-registered; instrument controls on committed pilot tables in a2_reclassify.py —
positive B01 S=1.651, positive planted S=2.796, negative csr S=0.903):
  S = [t̂(x1,y0)·t̂(x0,y1)] / [t̂(x0,y0)·t̂(x1,y1)]  over the 16 (reference excluded), cells =
  geometric means marginalizing march×funroll; x1/y1 = hypothesized-payoff levels.
  Δ_strict_16 = max/min of the 16 screen medians (feasible only).
  CANDIDATE PASSES ⇔ Δ_strict_16 ≥ 1.3 AND S ≥ 1.15   (both pre-stated; no post-hoc softening).
  Bars: 1.15 is ≈7× the 2% screen noise floor on a 4-cell log contrast; 1.3 sits between the FLAT
  ceiling (1.10) and the class floor (1.5) because a 16-config subset under-samples the full-table
  spread (the stride-subset lesson, CONTROLS_DEBUG.md).
KILL CRITERION (human's A-2 directive, verbatim rule): if NO candidate passes, INT is declared
NOT-EXHIBITED among the probed AND-gate mechanisms and the fleet proceeds without an INT regime.
Fleet-regime recommendation (memo Part 3/4): INT is fielded as a regime iff ≥ 2 candidates pass
(so that, with the planted-map mechanism, ≥ 3 mechanisms exist and the ≥6-template diversity
mandate is satisfiable without pseudoreplication).
BUDGET: ≤ 1 day hard; expected ≈ 5–10 min/candidate. measure_wrap on every timed run (CF-1
two-container split, host --verify-only first). Probe rows carry the N1 rig fingerprint.

Usage: python3 scripts/phasep/run_probe_int.py [--out results/probes/int] [--dry-design]
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import theta  # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE)) if HERE.endswith("scripts/phasep") else \
    os.path.abspath(os.path.join(HERE, "..", ".."))
IMG = "localhost/motifbo-env:phase1"
STRICT = ("off", "off")
# factor order: (bc, wrap, cdiv, initcheck, nonecheck, opt, march, funroll, fmffp)
PERMISSIVE = {"boundscheck": False, "wraparound": False, "cdivision": True,
              "initializedcheck": False, "nonecheck": False}
CONTEXT_VARY = {"march": ["x86-64", "native"], "funroll": ["omit", "on"]}
DELTA_BAR, S_BAR = 1.3, 1.15

_PYX_SUM64 = '''# cython: language_level=3
def run(long long[::1] a, long long n):
    cdef long long s = 0
    cdef long long i
    for i in range(n):
        s += a[i]
    return s
'''

_PYX_MIN32 = '''# cython: language_level=3
def run(int[::1] a, long long n):
    cdef int m = a[0]
    cdef long long i
    for i in range(n):
        if a[i] < m:
            m = a[i]
    return m
'''

_PYX_MOD64 = '''# cython: language_level=3
def run(long long[::1] x, long long[::1] out, long long n):
    cdef long long i
    for i in range(n):
        out[i] = x[i] % 7
    return out[n - 1]
'''

_PYX_REV64 = '''# cython: language_level=3
def run(long long[::1] a, long long n):
    cdef long long s = 0
    cdef long long i
    for i in range(n):
        s += a[n - 1 - i]
    return s
'''

_DRV_SCALAR = '''"""Probe driver — int scalar result, bit-exact oracle."""
import numpy as np

N = {n}
REPS = 400
OUTPUT_CLASS = "int"

def make_inputs(seed):
    rng = np.random.default_rng(seed)
    a = rng.integers({lo}, {hi}, size=N, dtype=np.{dtype})
    return (a, N)

def call(mod, inputs):
    a, n = inputs
    r = 0
    for _ in range(REPS):
        r = mod.run(a, n)
    return r

def canon(result):
    return np.asarray([result], dtype=np.int64)
'''

_DRV_MOD = '''"""Probe driver — int64 modulus map, bit-exact oracle on the out array."""
import numpy as np

N = {n}
REPS = 400
OUTPUT_CLASS = "int"

def make_inputs(seed):
    rng = np.random.default_rng(seed)
    x = rng.integers(0, 2**40, size=N, dtype=np.int64)   # NON-NEGATIVE: C%% == Python%% exactly
    out = np.zeros(N, dtype=np.int64)
    return (x, out, N)

def call(mod, inputs):
    x, out, n = inputs
    r = 0
    for _ in range(REPS):
        r = mod.run(x, out, n)
    return out

def canon(result):
    return np.asarray(result, dtype=np.int64).reshape(-1)
'''

CANDIDATES = {
    "probe_P1_sum64_bc_x_opt": {
        "pyx": _PYX_SUM64, "driver": _DRV_SCALAR.format(n=16384, lo=-2**40, hi=2**40, dtype="int64"),
        "gate": ("boundscheck", True, False), "mechanism": "int64 sum reduction; strict vectorization gated on bc=off AND -O3"},
    "probe_P2_min32_bc_x_opt": {
        "pyx": _PYX_MIN32, "driver": _DRV_SCALAR.format(n=32768, lo=-2**30, hi=2**30, dtype="int32"),
        "gate": ("boundscheck", True, False), "mechanism": "int32 conditional-min reduction (vpminsd); gate bc=off AND -O3"},
    "probe_P3_mod64_cdiv_x_opt": {
        "pyx": _PYX_MOD64, "driver": _DRV_MOD.format(n=16384),
        "gate": ("cdivision", False, True), "mechanism": "int64 %%const map; strength-reduction gated on cdivision=True AND -O3"},
    "probe_P4_rev64_wrap_x_opt": {
        "pyx": _PYX_REV64, "driver": _DRV_SCALAR.format(n=16384, lo=-2**40, hi=2**40, dtype="int64"),
        "gate": ("wraparound", True, False), "mechanism": "int64 reversed-index sum; wrap handling blocks vectorization; gate wrap=off AND -O3"},
}


def design(gate_factor, g0, g1):
    """16 strict configs: gate×opt full 2x2, march×funroll context 2x2; + reference for calibrate."""
    names = list(theta.FACTOR_NAMES)
    ids = []
    for g in (g0, g1):
        for opt in ("-O1", "-O3"):
            for march in CONTEXT_VARY["march"]:
                for fun in CONTEXT_VARY["funroll"]:
                    v = dict(PERMISSIVE)
                    v[gate_factor] = g
                    cfg = (v["boundscheck"], v["wraparound"], v["cdivision"],
                           v["initializedcheck"], v["nonecheck"], opt, march, fun, STRICT)
                    ids.append(theta.id_of(cfg))
    assert len(ids) == len(set(ids)) == 16
    for i in ids:
        assert theta.config_of(i)[8] == STRICT
    return sorted(ids), sorted(set(ids) | {theta.REFERENCE_ID})


def _run(cmd, log):
    with open(log, "a") as f:
        f.write("\n$ " + " ".join(cmd) + "\n")
        f.flush()
        return subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT).returncode


def analyse(out_kdir, gate_factor, g0, g1, probe_ids):
    import numpy as np
    names = list(theta.FACTOR_NAMES)
    gi, oi = names.index(gate_factor), names.index("opt_level")
    rows = [json.loads(l) for l in open(os.path.join(out_kdir, "table.jsonl"))]
    med = {r["config_id"]: r["screen"]["median_ns"] for r in rows
           if r["config_id"] in probe_ids and r.get("feasible") and r.get("screen")}
    n_feas = len(med)
    if n_feas < 16:
        return {"n_feasible_16": n_feas, "delta_16": None, "S": None, "passes": False,
                "note": "infeasible probe cells recorded; candidate cannot pass with missing cells"}
    cells = {}
    for cid, m in med.items():
        cfg = theta.config_of(cid)
        a = 0 if cfg[gi] == g0 else 1
        b = 0 if cfg[oi] == "-O1" else 1
        cells.setdefault((a, b), []).append(np.log(m))
    g = {k: float(np.mean(v)) for k, v in cells.items()}
    S = float(np.exp(g[(1, 0)] + g[(0, 1)] - g[(0, 0)] - g[(1, 1)]))
    d16 = max(med.values()) / min(med.values())
    return {"n_feasible_16": n_feas, "delta_16": d16, "S": S,
            "cell_geomean_ns": {str(k): float(np.exp(v)) for k, v in g.items()},
            "passes": bool(d16 >= DELTA_BAR and S >= S_BAR)}


def _analyse_in_container(okdir, gate_factor, g0, g1, ids16):
    """Analysis arithmetic needs numpy -> run it inside the pinned image (repo ro), stdout JSON."""
    rel = os.path.relpath(okdir, REPO)
    r = subprocess.run(["podman", "run", "--rm", "--network=none", "--security-opt", "label=disable",
                        "-v", f"{REPO}:/repo:ro", IMG, "python3",
                        "/repo/scripts/phasep/run_probe_int.py", "--analyse-one",
                        f"/repo/{rel}", gate_factor, json.dumps(g0), json.dumps(g1),
                        ",".join(str(i) for i in ids16)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {"passes": False, "note": f"ANALYSE_FAIL: {r.stderr[-300:]}"}
    return json.loads(r.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "results", "probes", "int"))
    ap.add_argument("--dry-design", action="store_true")
    ap.add_argument("--analyse-one", nargs=5, metavar=("KDIR", "FACTOR", "G0", "G1", "IDS"))
    a = ap.parse_args()
    if a.analyse_one:
        kdir, f, g0, g1, ids = a.analyse_one
        res = analyse(kdir, f, json.loads(g0), json.loads(g1),
                      {int(x) for x in ids.split(",")})
        json.dump(res, sys.stdout)
        return
    out = os.path.abspath(a.out)
    if a.dry_design:
        for name, c in CANDIDATES.items():
            f, g0, g1 = c["gate"]
            ids16, _ = design(f, g0, g1)
            print(name, f, ids16)
        return
    os.makedirs(out, exist_ok=True)
    log = os.path.join(out, "run_probe.log")
    ledger = open(os.path.join(out, "probe_ledger.jsonl"), "a")
    rm = {"run_id": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), "run_kind": "probe-int"}

    if subprocess.run(["bash", os.path.join(REPO, "scripts", "measure_wrap.sh"),
                       "--verify-only"]).returncode != 0:
        raise SystemExit("measure_wrap --verify-only FAILED — probe refused (quiesce first)")

    verdict = {"protocol": "A2_DECISION_MEMO.md Part 3", "bars": {"delta_16": DELTA_BAR, "S": S_BAR},
               "run_meta": rm, "candidates": {}}
    for name, c in CANDIDATES.items():
        f, g0, g1 = c["gate"]
        ids16, ids17 = design(f, g0, g1)
        kdir = os.path.join(out, "_kernels", name)
        os.makedirs(kdir, exist_ok=True)
        open(os.path.join(kdir, "kernel.pyx"), "w").write(c["pyx"])
        open(os.path.join(kdir, "driver.py"), "w").write(c["driver"])
        json.dump({"kernel_id": name, "family": "probe_int", "intended_class": "INT-candidate",
                   "mechanism": c["mechanism"], "gate": [f, str(g0), str(g1)],
                   "config_ids_16": ids16, "generated_by": "run_probe_int.py (A-2 Part 3)"},
                  open(os.path.join(kdir, "spec.json"), "w"), indent=2)
        okdir = os.path.join(out, name)
        idarg = "ids:" + ",".join(str(i) for i in ids17)
        table = os.path.join(okdir, "table.jsonl")
        have = {json.loads(l)["config_id"] for l in open(table)} if os.path.exists(table) else set()
        if set(ids17) <= have:
            rc, build_s, measure_s = 0, 0.0, 0.0   # resume: candidate fully measured already
        else:
            t0 = time.time()
            rc = _run(["podman", "run", "--rm", "--network=none", "--security-opt", "label=disable",
                       "-v", f"{REPO}/scripts:/probe:ro", "-v", f"{REPO}/results:/results:ro",
                       "-v", f"{out}:/work", IMG, "python3", "/probe/phasep/build_phase.py",
                       f"/work/_kernels/{name}", f"/work/{name}", idarg], log)
            build_s = round(time.time() - t0, 1)
            if rc != 0:
                ledger.write(json.dumps({"kernel_id": name, "status": "BUILD_FAIL", "build_s": build_s,
                                         **rm}) + "\n"); ledger.flush()
                verdict["candidates"][name] = {"passes": False, "note": "BUILD_FAIL"}
                continue
            t0 = time.time()
            rc = _run(["bash", f"{REPO}/scripts/measure_wrap.sh", "--security-opt", "label=disable",
                       "-v", f"{REPO}/scripts:/probe:ro", "-v", f"{REPO}/results:/results:ro",
                       "-v", f"{out}:/work", IMG, "python3", "/probe/phasep/measure_phase.py",
                       f"/work/_kernels/{name}", f"/work/{name}", idarg, "--target-ms", "65.0"], log)
            measure_s = round(time.time() - t0, 1)
        res = _analyse_in_container(okdir, f, g0, g1, ids16) if rc == 0 else {"passes": False, "note": "MEASURE_FAIL"}
        res.update({"mechanism": c["mechanism"], "gate": [f, str(g0), str(g1)],
                    "build_s": build_s, "measure_s": measure_s})
        verdict["candidates"][name] = res
        ledger.write(json.dumps({"kernel_id": name, "status": "DONE" if rc == 0 else "MEASURE_FAIL",
                                 "build_s": build_s, "measure_s": measure_s,
                                 "passes": res.get("passes"), **rm}) + "\n"); ledger.flush()
        print(f"{name}: Δ16={res.get('delta_16')} S={res.get('S')} -> "
              f"{'PASS' if res.get('passes') else 'no'}")

    n_pass = sum(1 for v in verdict["candidates"].values() if v.get("passes"))
    verdict["n_pass"] = n_pass
    verdict["kill_criterion_fired"] = (n_pass == 0)
    verdict["int_fleet_regime_recommended"] = (n_pass >= 2)
    with open(os.path.join(out, "probe_verdict.json"), "w") as fp:
        json.dump(verdict, fp, indent=2)
    print(f"\nPROBE VERDICT: {n_pass}/4 candidates pass -> "
          f"{'INT regime recommended (>=2)' if n_pass >= 2 else ('INT exhibited but mechanism-poor (1)' if n_pass == 1 else 'NOT-EXHIBITED among probed mechanisms')}")
    ledger.close()


if __name__ == "__main__":
    main()
