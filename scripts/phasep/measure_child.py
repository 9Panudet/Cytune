"""Screening-tier measurement child — ONE config in a FRESH subprocess (PREREG §4, §5).

Protocol: import the kernel's driver + the built .so; warmup=5 (untimed); then in-process K
adaptive ∈ [Kmin,Kmax] timing run(), early-stop when bootstrap 95% CI half-width of the median
≤ ci_target·median. Per-rep input regeneration is UNTIMED (constructed outside perf_counter_ns) —
this is also v1.4/D6 per-rep regen for in-place kernels. The ORACLE runs INLINE here (§4.3): given
--oracle, the child loads the golden output + tolerance and emits the feasible bit + reason itself,
so arbitrary-size float arrays are compared with tolerance (not by bit-exact hash).

Emits JSON: median_ns, ci_halfwidth, K, ru_maxrss_kb (RUSAGE_SELF), output_sha256, feasible, reason,
(small) output_values.

argv: kdir so_path K_min K_max warmup ci_target boot_seed input_seed
      [--module NAME] [--oracle oracle.json] [--save-output PATH]
"""
import argparse
import hashlib
import importlib.util
import json
import resource
import time
import numpy as np


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _boot_ci_halfwidth(times, seed, B=10000):
    rng = np.random.default_rng(seed)
    arr = np.asarray(times, float)
    idx = rng.integers(0, len(arr), size=(B, len(arr)))
    meds = np.median(arr[idx], axis=1)
    lo, hi = np.percentile(meds, [2.5, 97.5])
    return (hi - lo) / 2.0


def _feasible(canon, out_hash, oracle):
    """Return (feasible_bit, reason). Bit-exact for int/bool, toleranced for float (§5)."""
    if oracle["output_class"] in ("int", "bool"):
        return (1, "ok") if out_hash == oracle["golden_sha256"] else (0, "oracle_mismatch")
    golden = np.load(oracle["golden_npy"])
    if canon.shape != golden.shape:
        return 0, "oracle_mismatch"
    tol = oracle["tolerance"]
    if np.allclose(canon, golden, rtol=tol["rtol"], atol=tol["atol"], equal_nan=True):
        return 1, "ok"
    return 0, "oracle_mismatch"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kdir"); ap.add_argument("so_path")
    ap.add_argument("K_min", type=int); ap.add_argument("K_max", type=int)
    ap.add_argument("warmup", type=int); ap.add_argument("ci_target", type=float)
    ap.add_argument("boot_seed", type=int); ap.add_argument("input_seed", type=int)
    ap.add_argument("--module", default="kernel")
    ap.add_argument("--oracle", default=None)
    ap.add_argument("--save-output", default=None)
    a = ap.parse_args()

    driver = _load(f"{a.kdir}/driver.py", "driver")
    module_name = getattr(driver, "KERNEL_MODULE", a.module)
    preimport = getattr(driver, "PREIMPORT", None)
    if preimport:                       # Decision-C (v1): initialize the wrapper package first so
        import importlib                # the vendored .so's absolute imports resolve (floyd/cc)
        importlib.import_module(preimport)
    pkg_module = getattr(driver, "PKG_MODULE", None)
    if pkg_module:                      # co-build package import (v1 delta_probe_pkg recipe):
        import importlib                # the .so sits inside the per-config closure tree; put the
        import os as _os                # tree root on sys.path[0] and import the dotted module
        import sys as _sys
        root = a.so_path
        for _ in pkg_module.split("."):
            root = _os.path.dirname(root)
        _sys.path.insert(0, root)
        kernel = importlib.import_module(pkg_module)
    else:
        kernel = _load(a.so_path, module_name)

    for _ in range(a.warmup):
        driver.call(kernel, driver.make_inputs(a.input_seed))

    times, out_hash, canon = [], None, None
    while len(times) < a.K_max:
        inp = driver.make_inputs(a.input_seed)          # UNTIMED per-rep regen
        t0 = time.perf_counter_ns()
        res = driver.call(kernel, inp)
        t1 = time.perf_counter_ns()
        times.append(t1 - t0)
        if out_hash is None:
            canon = np.ascontiguousarray(driver.canon(res))
            out_hash = hashlib.sha256(canon.tobytes()).hexdigest()
        if len(times) >= a.K_min:
            med = float(np.median(times))
            if med > 0 and _boot_ci_halfwidth(times, a.boot_seed) <= a.ci_target * med:
                break

    med = float(np.median(times))
    half = _boot_ci_halfwidth(times, a.boot_seed)
    if a.save_output:
        np.save(a.save_output, canon)
    feasible, reason = (None, None)
    if a.oracle:
        oracle = json.load(open(a.oracle))
        feasible, reason = _feasible(canon, out_hash, oracle)
    print(json.dumps({
        "median_ns": med, "ci_halfwidth": half, "ci_rel": (half / med if med else None),
        "K": len(times), "ru_maxrss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "output_sha256": out_hash, "output_shape": list(canon.shape),
        "output_values": (canon.tolist() if canon.size <= 64 else None),
        "output_class": getattr(driver, "OUTPUT_CLASS", "float"),
        "feasible": feasible, "reason": reason,
    }))


if __name__ == "__main__":
    main()
