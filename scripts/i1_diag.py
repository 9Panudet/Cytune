"""Step 0.5.3 debug-mantra diagnostic (NOT the gate) — 2x2 decomposition of the pava
I-1 speedup into the cython-directive effect vs the gcc-flag effect. Runs IN the
container under measure_wrap. Builds pava under 4 configs, measures each at K=15 on the
paired pilot input, writes the decomposition to /results/calibration/i1/diag/.
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
sys.path.insert(0, "/probe")
from motifbo.build.profiles import performance_argv  # noqa: E402
from motifbo.timing.runtime_ns import measure  # noqa: E402
from pilot_measure import SETUPS  # noqa: E402

OFF = ["boundscheck=False", "wraparound=False", "initializedcheck=False",
       "nonecheck=False", "cdivision=True"]
ON = ["boundscheck=True", "wraparound=True", "initializedcheck=True",
      "nonecheck=True", "cdivision=False"]
CONFIGS = {                       # name: (directives, opt_flags, contract)
    "off_O3nat": (OFF, ["-O3", "-march=native"], "fast"),   # = known-good
    "on_O1base": (ON, ["-O1", "-march=x86-64"], "off"),     # = known-bad
    "off_O1base": (OFF, ["-O1", "-march=x86-64"], "off"),   # isolate gcc effect
    "on_O3nat": (ON, ["-O3", "-march=native"], "fast"),     # isolate directive effect
}
REPS, WARMUP = 15, 5
OUT = Path("/results/calibration/i1/diag")


def main():
    py_include = sysconfig.get_paths()["include"]
    workdir = Path(tempfile.mkdtemp())
    med = {}
    for name, (directives, opt, contract) in CONFIGS.items():
        outdir = workdir / name
        outdir.mkdir(parents=True)
        shutil.copy("/src/motifbo/refkernels/pava.pyx", outdir / "pava.pyx")
        xflags = []
        for d in directives:
            xflags += ["-X", d]
        subprocess.run(["cython", "-3", *xflags, str(outdir / "pava.pyx")], check=True)
        subprocess.run(performance_argv(opt, ffp_contract=contract,
                                        c_path=str(outdir / "pava.c"),
                                        so_path=str(outdir / "pava.so"),
                                        py_include=py_include), check=True)
        r = measure(module_path=str(outdir / "pava.so"), kernel="kernel",
                    setup_code=SETUPS["pava"], reps=REPS, warmup=WARMUP)
        med[name] = float(statistics.median(r["samples_ns"]))

    g, b = med["off_O3nat"], med["on_O1base"]
    decomp = {
        "total_bad_over_good": b / g,
        "directive_effect_at_O3nat": med["on_O3nat"] / g,
        "directive_effect_at_O1base": b / med["off_O1base"],
        "gcc_effect_at_off": med["off_O1base"] / g,
        "gcc_effect_at_on": b / med["on_O3nat"],
    }
    summary = {"schema": "motifbo-i1-diag-v1", "step": "0.5.3-debug",
               "kernel": "pava", "reps": REPS, "warmup": WARMUP,
               "image_id": os.environ.get("MOTIFBO_IMAGE_ID", "unset"),
               "git_rev": os.environ.get("MOTIFBO_GIT_REV", "unset"),
               "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "median_ns": med, "decomposition": decomp}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pava_decomposition.json").write_text(json.dumps(summary, indent=1) + "\n")
    print("pava median ms:", {k: round(v / 1e6, 3) for k, v in med.items()})
    print("decomposition (xfaster):", {k: round(v, 3) for k, v in decomp.items()})
    shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
