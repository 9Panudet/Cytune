"""Step 0.5.2 — I-1 measurement (runs IN the container under measure_wrap on core 3).

Measures ONE (kernel, config) at K_final=30 on the PAIRED pilot inputs and writes the
RAW measure() result (no aggregation — §6.1, raw before any ratio). The paired inputs
are imported from pilot_measure.SETUPS so they are byte-identical to the pilot and
identical across configs (the recorded setup_sha256 is the pairing proof).

Usage: i1_measure.py <csr_scale|pava> <good|bad> <out_path>
"""
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pilot_measure import SETUPS as PILOT_SETUPS  # noqa: E402 — frozen paired inputs

# Horner numeric-loop reference (Step 0.5.3-R; replaces PAVA as the I-1 numeric ref).
# Paired input, seed 20260611; 12 coeffs (degree-11). n LENGTHENED 4M->64M at Step 0.P/B.2
# (PREREG_I1_horner_lengthen.md): the 5.3ms reference missed exit-criterion-4 (CI@30 4.005%)
# from short-runtime jitter; 64M puts one run at ~84ms (in the §4.2 50-500ms band) so jitter
# averages out (predicted CI@30 ~0.25%). Compute-bound -> I-1 ratio preserved; oracle scale-invariant.
HORNER_SETUP = """
import numpy as np
rng = np.random.default_rng(20260611)
n, deg = 64_000_000, 12
x = rng.uniform(-1.0, 1.0, n)
c = rng.standard_normal(deg)
out = np.empty(n)
args = (x, c, out)
"""
SETUPS = {**PILOT_SETUPS, "horner": HORNER_SETUP}

K_FINAL = 30
WARMUP = 5
PATH_CLASS = {"csr_scale": "raw-pointer", "pava": "numeric-loop",
              "horner": "numeric-loop"}
CONFIG_DETAIL = {
    "good": ("cython boundscheck/wraparound/initializedcheck/nonecheck=False, "
             "cdivision=True; gcc -O3 -march=native -ffp-contract=fast -g0 -pipe"),
    "bad": ("cython boundscheck/wraparound/initializedcheck/nonecheck=True, "
            "cdivision=False; gcc -O1 -march=x86-64 -ffp-contract=off -g0 -pipe"),
}


def main():
    kernel, config, out = sys.argv[1], sys.argv[2], sys.argv[3]
    from motifbo.timing.runtime_ns import measure
    res = measure(module_path=f"/build/{config}/{kernel}.so", kernel="kernel",
                  setup_code=SETUPS[kernel], reps=K_FINAL, warmup=WARMUP, cycles=True)
    record = {
        "schema": "motifbo-i1-raw-v1",
        "kernel": kernel, "path_class": PATH_CLASS[kernel],
        "config": config, "config_detail": CONFIG_DETAIL[config],
        "module_path": f"/build/{config}/{kernel}.so",
        "setup_sha256": hashlib.sha256(SETUPS[kernel].encode()).hexdigest(),
        "K_final": K_FINAL, "warmup": WARMUP,
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "image_id": os.environ.get("MOTIFBO_IMAGE_ID", "unset"),
        "git_rev": os.environ.get("MOTIFBO_GIT_REV", "unset"),
        "result": res,
    }
    with open(out, "w") as fh:
        json.dump(record, fh, indent=1)
    print(f"{kernel}/{config}: {len(res['samples_ns'])} samples -> {out}")


if __name__ == "__main__":
    main()
