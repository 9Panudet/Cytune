"""Step 0.5.2 — build the I-1 known-good / known-bad configs (runs IN the container,
off the measurement core). Per PREREG_I1.md: each config in its own /build subdir so
the .so stem matches PyInit_<kernel>. Uses the 0.4.1 performance_argv (enforces the
explicit -ffp-contract invariant, §3.2 item 3).
"""
import subprocess
import sys
import os
import sysconfig
from pathlib import Path

sys.path.insert(0, "/src")
from motifbo.build.profiles import performance_argv  # noqa: E402

SRC = "/src/motifbo/refkernels"
KERNELS = tuple(os.environ.get("MOTIFBO_I1_KERNELS", "csr_scale pava horner").split())
CONFIGS = {
    "good": {"directives": ["boundscheck=False", "wraparound=False",
                            "initializedcheck=False", "nonecheck=False",
                            "cdivision=True"],
             "opt": ["-O3", "-march=native"], "contract": "fast"},
    "bad": {"directives": ["boundscheck=True", "wraparound=True",
                           "initializedcheck=True", "nonecheck=True",
                           "cdivision=False"],
            "opt": ["-O1", "-march=x86-64"], "contract": "off"},
}


def main():
    py_include = sysconfig.get_paths()["include"]
    for config, c in CONFIGS.items():
        outdir = Path("/build") / config
        outdir.mkdir(parents=True, exist_ok=True)
        xflags = []
        for d in c["directives"]:
            xflags += ["-X", d]
        for kernel in KERNELS:
            cpath = outdir / f"{kernel}.c"
            sopath = outdir / f"{kernel}.so"
            subprocess.run(["cython", "-3", *xflags, f"{SRC}/{kernel}.pyx",
                            "-o", str(cpath)], check=True)
            subprocess.run(performance_argv(c["opt"], ffp_contract=c["contract"],
                                            c_path=str(cpath), so_path=str(sopath),
                                            py_include=py_include), check=True)
            print(f"built {config}/{kernel}.so")


if __name__ == "__main__":
    main()
