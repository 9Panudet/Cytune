"""Step 0.2.4 pilot measurement program (runs IN the pinned container, launched by
scripts/run_pilot.sh through measure_wrap on the isolated core).

Frozen pilot constants live here: the setup codes ARE the input manifest source
(seed-generated inputs, §4.4 item 3); results/pilot/INPUT_MANIFEST.json is derived
from these strings. Raw output: one JSON per kernel with the untouched measure()
result + run metadata. NO aggregation here — raw is committed first (§6.1).

Usage: pilot_measure.py {csr_scale|pava|manifest} [out_path]
"""
import hashlib
import json
import os
import sys
import time

K_PILOT = 30
WARMUP = 5
SEED = 20260611
REFERENCE_CONFIG = ("cython-defaults(all checks on) + gcc -O2 -march=x86-64 "
                    "-ffp-contract=off -g0 -pipe -shared -fPIC")

SETUPS = {
    "csr_scale": """
import numpy as np
rng = np.random.default_rng(20260611)
nnz, nrows, passes = 4_000_000, 100_000, 24
data = rng.standard_normal(nnz)
counts = rng.multinomial(nnz - nrows, np.ones(nrows)/nrows) + 1
indptr = np.zeros(nrows + 1, dtype=np.int64); np.cumsum(counts, out=indptr[1:])
fac = rng.uniform(0.9, 1.1, nrows)
args = (data, indptr, fac, passes)
""",
    "pava": """
import numpy as np
rng = np.random.default_rng(20260611)
n = 4_000_000
y_src = rng.standard_normal(n); w_src = rng.uniform(0.5, 2.0, n)
y = np.empty(n); w = np.empty(n); tgt = np.empty(n, dtype=np.int64)
args = (y_src, w_src, y, w, tgt)
""",
}
SIZES = {"csr_scale": {"nnz": 4_000_000, "nrows": 100_000, "passes": 24},
         "pava": {"n": 4_000_000}}


def manifest():
    return {
        "schema": "motifbo-pilot-inputs-v1",
        "seed": SEED, "K_pilot": K_PILOT, "warmup": WARMUP,
        "reference_config": REFERENCE_CONFIG,
        "kernels": {k: {"sizes": SIZES[k],
                        "setup_sha256": hashlib.sha256(s.encode()).hexdigest()}
                    for k, s in SETUPS.items()},
    }


def main():
    which = sys.argv[1]
    if which == "manifest":
        json.dump(manifest(), sys.stdout, indent=1)
        return
    from motifbo.timing.runtime_ns import measure
    res = measure(module_path=f"/build/{which}.so", kernel="kernel",
                  setup_code=SETUPS[which], reps=K_PILOT, warmup=WARMUP, cycles=True)
    record = {
        "schema": "motifbo-pilot-raw-v1",
        "kernel": which,
        "module_path": f"/build/{which}.so",
        "setup_sha256": hashlib.sha256(SETUPS[which].encode()).hexdigest(),
        "reference_config": REFERENCE_CONFIG,
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "image_id": os.environ.get("MOTIFBO_IMAGE_ID", "unset"),
        "git_rev": os.environ.get("MOTIFBO_GIT_REV", "unset"),
        "result": res,
    }
    with open(sys.argv[2], "w") as fh:
        json.dump(record, fh, indent=1)
    print(f"{which}: {len(res['samples_ns'])} samples written to {sys.argv[2]}")


if __name__ == "__main__":
    main()
