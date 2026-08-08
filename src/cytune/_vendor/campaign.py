"""Per-kernel full-table campaign — shared phase library (PREREG §4/§5/§7, roadmap §4.4).

STRICT CF-1 phase split (roadmap §4.4): the BUILD phase (build_all) runs in a plain build container
(compile cores); the MEASURE phase (calibrate → golden+determinism → measure_all → suspicious →
endpoint → classify) runs inside ONE measure_wrap container on the isolated core, reading the
pre-built .so — NO compilation during measurement. build_phase.py and measure_phase.py are the two
container entrypoints; run_pilot.py orchestrates them per kernel. --rig plain runs everything in one
context for dev only (NOT decision-grade).

Table + manifest are append-only crash-safe resumable JSONL. Every measured number carries its raw
pointer (table.jsonl row) and a rig fingerprint.

--------------------------------------------------------------------------------------------
VENDORED AND TRIMMED for cytune. The study module additionally defines `config_set`,
`suspicious_remeasure`, `endpoint_tier` and `finalize`; `cytune/worker.py` calls none of them.
`endpoint_tier` in particular is deliberately NOT used — it re-measures the feasible top decile of
a full 1,728-row table, which answers the study's question and not the product's, so worker.py
implements the endpoint tier over the winner and the reference instead (see its docstring).

Dropping them also drops what they dragged in: `config_set` names `results/prereg/`, `finalize`
imports the study's `bc_effect`, and both would have made this file fail
`test_cytune_architecture.py`. `numpy` and `classify` were imported only by the dropped functions
and go with them.

Every function that remains is character-for-character the study's, pinned by
`test_cytune_vendor.py::test_vendored_functions_match_the_study_source`.
--------------------------------------------------------------------------------------------
"""
from __future__ import annotations
import json
import os
import subprocess
import time
import theta
import seeds

HERE = os.path.dirname(os.path.abspath(__file__))
K_MIN, K_MAX, WARMUP, CI_TARGET = 5, 10, 5, 0.02
ATOL_FLOOR, RTOL_FLOOR = 1e-12, 1e-9


def _rig():
    """Per-row rig fingerprint (A-2 Part-5, closes P-1 measurement-auditor N1): measure_wrap.sh
    exports the verified host state as RIG_FINGERPRINT into the container; every table row /
    endpoint record stamps it so the frozen dataset is self-describing. 'UNGATED' marks a row
    written outside measure_wrap (never legitimate for a fleet timing row)."""
    return os.environ.get("RIG_FINGERPRINT", "UNGATED")
def _module_of(kernel_dir):
    mp = os.path.join(kernel_dir, "kernel_meta.json")
    return json.load(open(mp))["module"] if os.path.exists(mp) else "kernel"


def _knob_line(src):
    for name in ("REPS", "SCALE"):
        for l in src.splitlines():
            if l.startswith(name + " ") and "=" in l:
                return name, int(l.split("=")[1].split("#")[0].strip())
    return None, None


# ---------------------------------------------------------------- BUILD phase
def build_all(kernel_dir, out_dir, config_ids, workers=None):
    """Compile every config; keep the .so; append build_manifest.jsonl (roadmap §4.4 parallel build).

    Phase 1 (serial): cythonize one representative per distinct directive combo — warms the .c cache
    and avoids a concurrent-combo cythonize race. Phase 2 (parallel): gcc every remaining config; gcc
    is a subprocess (releases the GIL) so a thread pool gives real multi-core build. Resumable."""
    import build as buildmod
    from concurrent.futures import ThreadPoolExecutor
    if workers is None:
        workers = max(1, (os.cpu_count() or 4) - 1)
    cache = os.path.join(out_dir, "_ccache")
    sod = os.path.join(out_dir, "_so")
    mpath = os.path.join(out_dir, "build_manifest.jsonl")
    done = set()
    if os.path.exists(mpath):
        for l in open(mpath):
            done.add(json.loads(l)["config_id"])
    todo = [c for c in config_ids if c not in done]

    def _row(cid, b):
        return {"config_id": cid, "ok": b["ok"], "reason": b["reason"],
                "compile_s": round(b["compile_s"], 4), "so_size_b": b["so_size_b"], "so_path": b.get("so_path")}

    # phase 1: warm the cythonize cache, one config per distinct combo (serial)
    reps = {}
    for cid in todo:
        reps.setdefault(buildmod._combo_key(theta.config_of(cid)), cid)
    rows = {}
    for cid in reps.values():
        rows[cid] = _row(cid, buildmod.build_config(kernel_dir, theta.config_of(cid), cache, sod))
    # phase 2: parallel gcc for the rest (cythonize cache hit)
    rest = [c for c in todo if c not in reps.values()]

    def _b(cid):
        return cid, _row(cid, buildmod.build_config(kernel_dir, theta.config_of(cid), cache, sod))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for cid, r in ex.map(_b, rest):
            rows[cid] = r
    mf = open(mpath, "a")
    n_ok = len(done)
    for cid in todo:
        mf.write(json.dumps(rows[cid]) + "\n")
        n_ok += int(rows[cid]["ok"])
    mf.close()
    return mpath, n_ok


def _manifest(out_dir):
    m = {}
    for l in open(os.path.join(out_dir, "build_manifest.jsonl")):
        r = json.loads(l)
        m[r["config_id"]] = r
    return m


# ---------------------------------------------------------------- MEASURE phase (inside measure_wrap)
def _measure_one(kernel_dir, so_path, cid, module, input_seed, oracle_path=None,
                 save_output=None, k_min=K_MIN, k_max=K_MAX):
    kid = os.path.basename(kernel_dir.rstrip("/"))
    bs = seeds.state_int("screen", seeds.kernel_hash(kid), cid) & 0x7FFFFFFF
    cmd = ["python3", os.path.join(HERE, "measure_child.py"), kernel_dir, so_path,
           str(k_min), str(k_max), str(WARMUP), str(CI_TARGET), str(bs), str(input_seed),
           "--module", module]
    if oracle_path:
        cmd += ["--oracle", oracle_path]
    if save_output:
        cmd += ["--save-output", save_output]
    t0 = time.perf_counter_ns()
    r = subprocess.run(cmd, capture_output=True, text=True,
                       env={**os.environ, "OMP_NUM_THREADS": "1"})  # single isolated core (v1)
    wall_ns = time.perf_counter_ns() - t0
    if r.returncode != 0:
        return None, wall_ns, (r.stdout + r.stderr)[-400:]
    return json.loads(r.stdout.strip().splitlines()[-1]), wall_ns, None


def calibrate(kernel_dir, out_dir, target_ms):
    """Tune the driver knob (REPS synthetic / SCALE R-anchor) so the reference lands ~target_ms."""
    mod = _module_of(kernel_dir)
    ref = _manifest(out_dir)[theta.REFERENCE_ID]
    if not ref["ok"]:
        raise SystemExit(f"calibrate: reference build failed ({ref['reason']})")
    m, _w, err = _measure_one(kernel_dir, ref["so_path"], theta.REFERENCE_ID, mod, 12345)
    if m is None:
        raise SystemExit(f"calibrate: reference measure failed: {err}")
    drv = os.path.join(kernel_dir, "driver.py")
    src = open(drv).read()
    name, cur = _knob_line(src)
    cur_ms = m["median_ns"] / 1e6
    new = max(1, int(round(cur * target_ms / cur_ms)))
    open(drv, "w").write("\n".join((f"{name} = {new}" if l.startswith(name + " ") else l)
                                   for l in src.splitlines()))
    return {"knob": name, "cur": cur, "cur_ms": round(cur_ms, 3), "new": new, "target_ms": target_ms}


def golden_and_oracle(kernel_dir, out_dir, det_reps=5):
    """Determinism gate (bit-identical ≥5 fresh reps at reference; §3.2-4) + golden + oracle floor.

    Deterministic ⇒ cross-rep deviation 0 ⇒ tolerance = floor (v1 §3.1). Non-deterministic ⇒ the
    kernel FAILS the determinism gate and is dropped (raised here)."""
    mod = _module_of(kernel_dir)
    ref = _manifest(out_dir)[theta.REFERENCE_ID]
    golden_npy = os.path.abspath(os.path.join(out_dir, "golden.npy"))
    hashes, first = [], None
    for i in range(det_reps):
        save = golden_npy if i == 0 else None
        m, _w, err = _measure_one(kernel_dir, ref["so_path"], theta.REFERENCE_ID, mod, 12345,
                                  save_output=save, k_min=1, k_max=1)
        if m is None:
            raise SystemExit(f"golden: measure failed: {err}")
        hashes.append(m["output_sha256"])
        first = first or m
    deterministic = len(set(hashes)) == 1
    cls = first["output_class"]
    oracle = {"output_class": cls, "golden_sha256": hashes[0], "golden_npy": golden_npy,
              "golden_shape": first["output_shape"], "deterministic": deterministic,
              "n_det_reps": det_reps, "det_hashes": hashes,
              "tolerance": {"rtol": (RTOL_FLOOR if cls == "float" else 0.0),
                            "atol": (ATOL_FLOOR if cls == "float" else 0.0)}}
    with open(os.path.join(out_dir, "oracle.json"), "w") as f:
        json.dump(oracle, f, indent=2)
    if not deterministic:
        raise SystemExit(f"determinism_gate_FAIL: {len(set(hashes))} distinct hashes over {det_reps} reps")
    return oracle


def measure_all(kernel_dir, out_dir, config_ids):
    """Screen every BUILT config in a fresh subprocess, oracle inline. Append table.jsonl."""
    mod = _module_of(kernel_dir)
    man = _manifest(out_dir)
    oracle_path = os.path.join(out_dir, "oracle.json")
    table_path = os.path.join(out_dir, "table.jsonl")
    done = set()
    if os.path.exists(table_path):
        for l in open(table_path):
            done.add(json.loads(l)["config_id"])
    fout = open(table_path, "a")
    n_feas = 0
    for cid in config_ids:
        if cid in done:
            continue
        b = man.get(cid, {"ok": False, "reason": "not_built"})
        row = {"config_id": cid, "factors": theta.as_dict(theta.config_of(cid)),
               "compile_s": b.get("compile_s"), "so_size_b": b.get("so_size_b"),
               "rig": _rig()}
        if not b["ok"]:
            row.update({"feasible": 0, "reason": b["reason"], "screen": None, "peak_rss_kb": None})
        else:
            m, wall_ns, err = _measure_one(kernel_dir, b["so_path"], cid, mod, 12345, oracle_path=oracle_path)
            if m is None:
                row.update({"feasible": 0, "reason": "crash", "screen": None, "peak_rss_kb": None, "err": err})
            else:
                n_feas += int(m["feasible"])
                spawn_ns = max(0, wall_ns - m["K"] * m["median_ns"])
                row.update({"feasible": m["feasible"], "reason": m["reason"],
                            "peak_rss_kb": m["ru_maxrss_kb"],
                            "screen": {"median_ns": m["median_ns"], "ci_halfwidth": m["ci_halfwidth"],
                                       "ci_rel": m["ci_rel"], "K": m["K"], "wall_ns": wall_ns,
                                       "spawn_overhead_ns": spawn_ns}})
        fout.write(json.dumps(row) + "\n")
        fout.flush()
    fout.close()
    return table_path, n_feas
