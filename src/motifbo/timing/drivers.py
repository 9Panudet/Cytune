"""Hot-loop drivers for the Phase-0 reference kernels (Step 0.5.1, roadmap §4.4).

A "driver" is the size-parameterised input construction for a kernel; the RUNTIME_NS
harness (runtime_ns.measure) supplies the §4.4 discipline around it — fresh subprocess
(§3.2(2)), perf_counter_ns immediately around the kernel call only, input construction
and import recorded SEPARATELY (import_ns/setup_ns) and excluded from samples_ns. That
separation is the structural guard against D2 (drivers that measured import/startup
instead of the hot loop, §0.2).

Each driver declares a complexity band (Tier-3, frozen): for an input doubling n->2n
the median-runtime ratio must fall inside it. The lower bound > 1.0 is the D2 guard —
an import/startup-dominated driver scales ~1.0x and fails; the upper bound catches a
super-linear surprise. Both reference kernels are O(n):
  - csr_scale: passes * nnz inner multiplies => linear in nnz (passes fixed).
  - pava:      pool-adjacent-violators is O(n) amortised (each element merged/
               expanded O(1) times).
"""

# Declared per-kernel scaling spec. `param` is the size knob; small/large are the
# two D2 measurement sizes (large = 2 * small in the scaling dimension); `band` is
# the frozen acceptance interval for median(large)/median(small).
DRIVERS = {
    "csr_scale": {
        "param": "nnz", "complexity": "O(n)", "band": (1.7, 2.3),
        "small": {"nnz": 2_000_000, "nrows": 50_000, "passes": 8},
        "large": {"nnz": 4_000_000, "nrows": 100_000, "passes": 8},
    },
    "pava": {
        "param": "n", "complexity": "O(n)", "band": (1.7, 2.3),
        "small": {"n": 2_000_000},
        "large": {"n": 4_000_000},
    },
}

DEFAULT_SEED = 20260611


def setup_code(kernel, size, seed=DEFAULT_SEED):
    """Return the harness setup_code that builds `kernel`'s inputs at `size`.

    The string defines `args` (the kernel call tuple); input construction runs
    UNTIMED in the child (§4.4 item 2). Deterministic in (kernel, size, seed).
    """
    if kernel == "csr_scale":
        nnz, nrows, passes = size["nnz"], size["nrows"], size["passes"]
        if nnz <= nrows:
            raise ValueError("csr_scale needs nnz > nrows")
        return (
            "import numpy as np\n"
            f"rng = np.random.default_rng({seed})\n"
            f"nnz, nrows, passes = {nnz}, {nrows}, {passes}\n"
            "data = rng.standard_normal(nnz)\n"
            "counts = rng.multinomial(nnz - nrows, np.ones(nrows)/nrows) + 1\n"
            "indptr = np.zeros(nrows + 1, dtype=np.int64)\n"
            "np.cumsum(counts, out=indptr[1:])\n"
            "fac = rng.uniform(0.9, 1.1, nrows)\n"
            "args = (data, indptr, fac, passes)\n")
    if kernel == "pava":
        n = size["n"]
        return (
            "import numpy as np\n"
            f"rng = np.random.default_rng({seed})\n"
            f"n = {n}\n"
            "y_src = rng.standard_normal(n); w_src = rng.uniform(0.5, 2.0, n)\n"
            "y = np.empty(n); w = np.empty(n); tgt = np.empty(n, dtype=np.int64)\n"
            "args = (y_src, w_src, y, w, tgt)\n")
    raise KeyError(f"unknown kernel {kernel!r}")


def scaling_ratio(median_small, median_large):
    """Input-scaling ratio median(2n)/median(n) (§4.4 item 4)."""
    if median_small <= 0:
        raise ValueError(f"median_small must be > 0, got {median_small}")
    return median_large / median_small


def in_band(ratio, band):
    """True iff ratio is within the closed declared band [lo, hi]."""
    lo, hi = band
    return lo <= ratio <= hi
