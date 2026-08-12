"""Step 0.5.1 — D2 input-scaling check + §4.4 profile evidence (runs IN the container).

For each reference kernel: build it known-good (cython known-good directives + the
performance profile -O3 -march=native -ffp-contract=fast), measure median runtime at
the declared small and large (=2x) sizes via the RUNTIME_NS harness (fresh subprocess,
kernel-only timing), and check median(large)/median(small) ∈ the declared band (§4.4
item 4 / D2 guard, §0.2).

§4.4 item-1 profile evidence ("≥90% of the timed region is the kernel") is produced by
a MODEL-FREE overhead decomposition: an extra measurement at a near-zero-compute config
(csr passes=0 on the same arrays; pava n=64) bounds the fixed per-call overhead
(buffer-protocol coercion + Python->C dispatch), giving kernel_fraction = 1 -
overhead/work. cProfile is NOT usable here: lsprof only records Python-call boundaries,
so a tight C kernel with no Python subcalls registers ~0 profiled time even with
cython profile=True (verified empirically, Step-0.5.1 log) — perf-style decomposition
is the right tool. The harness import_ns/setup_ns are also recorded and EXCLUDED from
the timed signal — the structural D2 guard.

Raw -> /results/calibration/d2/. Exit 1 on any band violation (red gate => debug-mantra).

Launch on the isolated core via measure_wrap:
  bash scripts/measure_wrap.sh -v ./src:/src:ro,Z -v ./scripts:/scripts:ro,Z \
    -v ./results:/results:Z -e PYTHONPATH=/src -e MOTIFBO_IMAGE_ID=$ID \
    -e MOTIFBO_GIT_REV=$REV localhost/motifbo-env:phase0 python /scripts/run_d2_scaling.py
"""
import json
import os
import shutil
import statistics
import subprocess
import sys
import sysconfig
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "/src")
from motifbo.build.profiles import performance_argv  # noqa: E402
from motifbo.timing import drivers  # noqa: E402
from motifbo.timing.runtime_ns import measure  # noqa: E402

KNOWN_GOOD_DIRECTIVES = ["boundscheck=False", "wraparound=False",
                         "initializedcheck=False", "nonecheck=False",
                         "cdivision=True"]
KNOWN_GOOD_CONFIG = ("cython known-good (boundscheck/wraparound/initializedcheck/"
                     "nonecheck off, cdivision on) + gcc -O3 -march=native "
                     "-ffp-contract=fast -g0 -pipe")
REPS = 10
WARMUP = 5
OUT = Path("/results/calibration/d2")


def build(kernel, outdir, py_include):
    outdir.mkdir(parents=True, exist_ok=True)
    pyx = outdir / f"{kernel}.pyx"
    shutil.copy(f"/src/motifbo/refkernels/{kernel}.pyx", pyx)
    xflags = []
    for d in KNOWN_GOOD_DIRECTIVES:
        xflags += ["-X", d]
    subprocess.run(["cython", "-3", *xflags, str(pyx)], check=True)
    so = outdir / f"{kernel}.so"
    subprocess.run(performance_argv(["-O3", "-march=native"], ffp_contract="fast",
                                    c_path=str(outdir / f"{kernel}.c"),
                                    so_path=str(so), py_include=py_include), check=True)
    return so


def median_ns(so, kernel, size):
    r = measure(module_path=str(so), kernel="kernel",
                setup_code=drivers.setup_code(kernel, size), reps=REPS, warmup=WARMUP)
    return float(statistics.median(r["samples_ns"])), r


def overhead_size(kernel, small):
    """A near-zero-compute config: same coercion/dispatch cost, ~no kernel work."""
    if kernel == "csr_scale":
        return {**small, "passes": 0}      # outer pass-loop body never runs
    return {"n": 64}                       # pava: trivial compute, real coercion


def main():
    py_include = sysconfig.get_paths()["include"]
    workdir = Path(tempfile.mkdtemp())
    results, all_ok = [], True
    for kernel, spec in drivers.DRIVERS.items():
        so = build(kernel, workdir / kernel, py_include)
        small_med, small_r = median_ns(so, kernel, spec["small"])
        large_med, _ = median_ns(so, kernel, spec["large"])
        ratio = drivers.scaling_ratio(small_med, large_med)
        ok = drivers.in_band(ratio, spec["band"])
        all_ok = all_ok and ok
        ovh_med, _ = median_ns(so, kernel, overhead_size(kernel, spec["small"]))
        kernel_fraction = max(0.0, 1.0 - ovh_med / small_med)
        results.append({
            "kernel": kernel, "complexity": spec["complexity"],
            "param": spec["param"], "band": list(spec["band"]),
            "ratio": ratio, "in_band": ok,
            "small": {"size": spec["small"], "median_ns": small_med,
                      "import_ns": small_r["import_ns"], "setup_ns": small_r["setup_ns"],
                      "samples_ns": small_r["samples_ns"]},
            "large": {"size": spec["large"], "median_ns": large_med},
            "overhead_median_ns": ovh_med, "kernel_fraction": kernel_fraction,
            "kernel_ge_90pct": kernel_fraction >= 0.90,
        })

    summary = {
        "schema": "motifbo-d2-scaling-v1", "step": "0.5.1",
        "config": KNOWN_GOOD_CONFIG, "reps": REPS, "warmup": WARMUP,
        "image_id": os.environ.get("MOTIFBO_IMAGE_ID", "unset"),
        "git_rev": os.environ.get("MOTIFBO_GIT_REV", "unset"),
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "all_in_band": all_ok,
        "all_kernel_ge_90pct": all(r["kernel_ge_90pct"] for r in results),
        "kernels": results,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "d2_scaling.json").write_text(json.dumps(summary, indent=1) + "\n")

    lines = ["# D2 input-scaling check + §4.4 profile evidence — Step 0.5.1", "",
             f"Config: {KNOWN_GOOD_CONFIG}", f"Reps: {REPS} (+{WARMUP} warmup); "
             f"image {summary['image_id']} git {summary['git_rev']}", "",
             "| kernel | cx | n->2n | med(n) ms | med(2n) ms | ratio | band | in-band "
             "| import/setup ms (excl.) | overhead ms | kernel % |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        sm = r["small"]
        lines.append(
            f"| {r['kernel']} | {r['complexity']} | {r['param']} | "
            f"{sm['median_ns']/1e6:.3f} | {r['large']['median_ns']/1e6:.3f} | "
            f"{r['ratio']:.3f} | {r['band']} | {'YES' if r['in_band'] else 'NO'} | "
            f"{sm['import_ns']/1e6:.2f}/{sm['setup_ns']/1e6:.2f} | "
            f"{r['overhead_median_ns']/1e6:.4f} | {r['kernel_fraction']*100:.2f}% |")
    lines += ["", f"All kernels in band (D2 guard, §4.4 item 4): "
              f"**{'YES' if all_ok else 'NO — RED GATE'}**.",
              f"All kernels ≥90% of timed region (§4.4 item 1): "
              f"**{'YES' if summary['all_kernel_ge_90pct'] else 'NO'}**.",
              "import_ns/setup_ns are recorded by the harness and EXCLUDED from the "
              "timed signal (samples_ns is kernel-only). kernel % = 1 - overhead/work "
              "(overhead = near-zero-compute config; cProfile is inapplicable to a "
              "no-Python-subcall C kernel — see the step log).",
              "Raw: results/calibration/d2/d2_scaling.json"]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    shutil.rmtree(workdir, ignore_errors=True)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
