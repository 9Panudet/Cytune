"""CF-4 measurement-hygiene probe (Step 1.2.0). Runs IN the pinned container on the
isolated core (via measure_wrap.sh), reusing the real RUNTIME_NS rig.

Goal: identify the DOMINANT source of cross-subprocess run-to-run variance BEFORE
pinning any page policy (carry-forward CF-4; refinement #1 "Probe 1 is decisive").

Measurement structure (refinement #9):
  - WITHIN-process: each measure() call = ONE fresh _child subprocess running
    5 warmup + K reps; bootstrap CI half-width of the median over the K reps is the
    `ci30` (the pilot RED metric).
  - BETWEEN-process: M independent measure() calls (M fresh subprocesses); the spread
    of the M per-subprocess medians is the run-to-run offset (the CF-4 ~8 ms metric).

csr_scale kernel: work = passes * nnz multiplies on `data` (size nnz*8 B). SMALL nnz
=> cache-resident, no large allocation (isolates core/layout/scheduling). LARGE/HUGE
=> DRAM-streaming (memory-bound regime where the offset appeared). pilot_csr / pilot_pava
reproduce the EXACT Step-0.2.4 pilot inputs (seed 20260611) — the two real units that
showed RED (csr 2.75% / pava 1.67%) — for the refinement-#5 real-unit validation.

ASLR is controlled OUTSIDE this driver (setarch -R wraps the whole invocation; the
personality is inherited by the _child subprocesses).

Usage: cf4_probe.py <config> <M> <out.json>   config in KERNELS below.
Raw (all per-subprocess samples) is written to out.json and committed — summary printed
here is ORIENTATION only; statistics are recomputable from the raw (§6.1).
"""
import hashlib
import json
import os
import sys
import time

import numpy as np

K = 30
WARMUP = 5
SEED = 20260623
PILOT_SEED = 20260611
CSR = "/build/csr_scale.so"
PAVA = "/build/pava.so"


def csr_setup(nnz, nrows, passes, seed):
    return f"""
import numpy as np
rng = np.random.default_rng({seed})
nnz, nrows, passes = {nnz}, {nrows}, {passes}
data = rng.standard_normal(nnz)
counts = rng.multinomial(nnz - nrows, np.ones(nrows)/nrows) + 1
indptr = np.zeros(nrows + 1, dtype=np.int64); np.cumsum(counts, out=indptr[1:])
fac = rng.uniform(0.9, 1.1, nrows)
args = (data, indptr, fac, passes)
"""


def pava_setup(n, seed):
    # Verbatim the Step-0.2.4 pilot pava input (the real 1.67%-CI unit).
    return f"""
import numpy as np
rng = np.random.default_rng({seed})
n = {n}
y_src = rng.standard_normal(n); w_src = rng.uniform(0.5, 2.0, n)
y = np.empty(n); w = np.empty(n); tgt = np.empty(n, dtype=np.int64)
args = (y_src, w_src, y, w, tgt)
"""


# config -> (module, kernel, setup_code)
KERNELS = {
    "small":      (CSR, "kernel", csr_setup(16_384, 2_048, 6_000, SEED)),       # 128 KB cache
    "large":      (CSR, "kernel", csr_setup(4_000_000, 100_000, 24, SEED)),     # 32 MB DRAM
    "huge":       (CSR, "kernel", csr_setup(64_000_000, 1_000_000, 6, SEED)),   # 512 MB THP regime
    "pilot_csr":  (CSR, "kernel", csr_setup(4_000_000, 100_000, 24, PILOT_SEED)),  # real unit (2.75%)
    "pilot_pava": (PAVA, "kernel", pava_setup(4_000_000, PILOT_SEED)),          # real unit (1.67%)
    "pava_big": (PAVA, "kernel", pava_setup(27_000_000, PILOT_SEED)),           # ~500 ms (band-upper bias)
}


def boot_ci_halfwidth_rel(samples, B=2000, seed=0xC0FFEE):
    a = np.asarray(samples, float)
    rng = np.random.default_rng(seed)
    med = np.median(a)
    idx = rng.integers(0, a.size, size=(B, a.size))
    boot_meds = np.median(a[idx], axis=1)
    lo, hi = np.percentile(boot_meds, [2.5, 97.5])
    return 0.5 * (hi - lo) / med * 100.0, med


def main():
    which, M, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    module, kernel, sc = KERNELS[which]
    sys.path.insert(0, "/src")
    from motifbo.timing.runtime_ns import measure

    runs = []
    for m in range(M):
        res = measure(module_path=module, kernel=kernel, setup_code=sc,
                      reps=K, warmup=WARMUP)
        ns = res["samples_ns"]
        ci, med = boot_ci_halfwidth_rel(ns)
        runs.append({"subproc": m, "child_pid": res["child_pid"],
                     "median_ns": float(med), "ci30_rel_pct": float(ci),
                     "samples_ns": ns})

    meds = np.array([r["median_ns"] for r in runs])
    between_spread_pct = float((meds.max() - meds.min()) / np.median(meds) * 100.0)
    between_rstd_pct = float(meds.std(ddof=1) / np.median(meds) * 100.0)
    worst_ci30 = float(max(r["ci30_rel_pct"] for r in runs))
    med_ci30 = float(np.median([r["ci30_rel_pct"] for r in runs]))

    record = {
        "schema": "motifbo-cf4-probe-v1",
        "which": which, "M": M, "K": K, "warmup": WARMUP,
        "module": module, "kernel": kernel,
        "setup_sha256": hashlib.sha256(sc.encode()).hexdigest(),
        "aslr_off": os.environ.get("MOTIFBO_ASLR_OFF", "unknown"),
        "image_id": os.environ.get("MOTIFBO_IMAGE_ID", "unset"),
        "git_rev": os.environ.get("MOTIFBO_GIT_REV", "unset"),
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": {
            "median_of_medians_ms": float(np.median(meds) / 1e6),
            "between_subproc_spread_pct": between_spread_pct,
            "between_subproc_rstd_pct": between_rstd_pct,
            "within_proc_ci30_worst_pct": worst_ci30,
            "within_proc_ci30_median_pct": med_ci30,
        },
        "runs": runs,
    }
    with open(out, "w") as fh:
        json.dump(record, fh)
    s = record["summary"]
    print(f"[{which}] M={M} median={s['median_of_medians_ms']:.2f}ms "
          f"| BETWEEN-proc spread={between_spread_pct:.3f}% rstd={between_rstd_pct:.3f}% "
          f"| WITHIN-proc CI@30 worst={worst_ci30:.3f}% median={med_ci30:.3f}%")


if __name__ == "__main__":
    main()
