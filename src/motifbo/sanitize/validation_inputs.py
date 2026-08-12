"""Validation input sets for the two Phase-0 reference kernels (Step 0.4.2, §3.3).

The §3.3 validation set is "diverse by construction": golden representative inputs
+ edge cases (empty, single-element, jagged/zero-size rows, contiguous offset
sub-views, NaN/Inf where the domain admits, zero divisors, boundary sizes) +
property-based cases. The property cases HERE are a fixed-seed numpy corpus
(`prop_*`) — deterministic, committed, and fast to materialise in-process for the
contract tests. `hypothesis` was added to the pinned lock at re-pin 0.4.2b; the §3.3
Hypothesis property-corpus pass over the known-good ASan/UBSan build lives in
`hypothesis_inputs.py` + `scripts/run_hypothesis_sanitize.py` (Step 0.P/G1), reusing
these same materialize_* contracts. Full Hypothesis wiring for the real corpus units
is at Steps 1.1.3/1.1.5 where input manifests are frozen.

Every case is a JSON-serialisable spec; `materialize_csr` / `materialize_pava` are
pure deterministic functions of the spec, so a fresh subprocess (§3.2(2)) rebuilds
the exact same arrays from the spec index — no array serialisation across the
process boundary. `test_validation_inputs.py` asserts every materialised case
satisfies its kernel's memory-safety contract, so a clean sanitizer run is
non-vacuous (a report would be a real kernel defect, never a malformed input).
"""
import numpy as np

# csr_scale contract: len(row_factor)=nrows; len(indptr)=nrows+1, indptr[0]=0,
#   non-decreasing, indptr[-1]=len(data); passes even >= 0.
# pava contract: n=len(y_src); w_src,y,w,target all length n.


def _rng(seed):
    return np.random.default_rng(seed)


def _values(mode, n, rng):
    if n == 0:
        return np.zeros(0, dtype=np.float64)
    if mode == "uniform":
        return rng.uniform(0.5, 2.0, size=n)
    if mode == "signed":
        return rng.uniform(-5.0, 5.0, size=n)
    if mode == "extreme":
        return rng.choice([1e-300, 1e300, -1e300, 1.0, -1.0], size=n)
    if mode == "nan_inf":
        v = rng.uniform(-1.0, 1.0, size=n)
        if n >= 3:
            v[0], v[1], v[2] = np.nan, np.inf, -np.inf
        return v
    if mode == "zeros":
        return np.zeros(n, dtype=np.float64)
    raise ValueError(f"unknown value mode {mode!r}")


def _maybe_offset(arr, spec):
    """Return a CONTIGUOUS sub-view with a non-zero base offset when requested —
    exercises pointer-offset handling without violating the [::1] contract."""
    if not spec.get("offset"):
        return arr
    pad = 3
    big = np.full(arr.shape[0] + pad + 2, np.nan, dtype=np.float64)
    big[pad:pad + arr.shape[0]] = arr
    view = big[pad:pad + arr.shape[0]]
    assert view.flags["C_CONTIGUOUS"]
    return view


def materialize_csr(spec):
    rng = _rng(spec.get("seed", 0))
    nrows = spec["nrows"]
    if "nnz_rows" in spec:
        nnz_rows = np.asarray(spec["nnz_rows"], dtype=np.int64)
    elif nrows == 0:
        nnz_rows = np.zeros(0, dtype=np.int64)
    else:
        lo, hi = spec.get("nnz_lo", 0), spec.get("nnz_hi", 8)
        nnz_rows = rng.integers(lo, hi + 1, size=nrows).astype(np.int64)
    indptr = np.empty(nrows + 1, dtype=np.int64)
    indptr[0] = 0
    if nrows:
        np.cumsum(nnz_rows, out=indptr[1:])
    nnz = int(indptr[-1])
    data = _maybe_offset(_values(spec.get("data", "uniform"), nnz, rng), spec)
    fmode = spec.get("factor", "uniform")        # semantic label, not a value mode
    factor = _values("uniform" if fmode == "zero" else fmode, nrows, rng).copy()
    if fmode == "zero" and nrows:
        factor[::3] = 0.0
    return data, indptr, np.ascontiguousarray(factor), int(spec.get("passes", 2))


def materialize_pava(spec):
    rng = _rng(spec.get("seed", 0))
    n = spec["n"]
    shape = spec.get("shape", "random")
    if n == 0:
        y_src = np.zeros(0)
    elif shape == "decreasing":
        y_src = np.linspace(10.0, 0.0, n)
    elif shape == "increasing":
        y_src = np.linspace(0.0, 10.0, n)
    elif shape == "equal":
        y_src = np.full(n, 3.0)
    else:
        y_src = _values(spec.get("data", "signed"), n, rng)
    wmode = spec.get("weight", "uniform")        # semantic label, not a value mode
    w_src = _values("uniform" if wmode in ("zero", "negative") else wmode, n, rng)
    if wmode == "zero" and n:
        w_src[:] = 0.0
    elif wmode == "negative" and n:
        w_src = -np.abs(w_src) - 0.1
    y_src = _maybe_offset(np.ascontiguousarray(y_src), spec)
    return (y_src, np.ascontiguousarray(w_src), np.zeros(n), np.zeros(n),
            np.zeros(n, dtype=np.int64))


def _csr_cases():
    cases = [
        {"name": "golden", "nrows": 1000, "nnz_lo": 20, "nnz_hi": 80, "seed": 1},
        {"name": "empty", "nrows": 0, "passes": 2},
        {"name": "single_row_single_nnz", "nrows": 1, "nnz_rows": [1]},
        {"name": "single_row_many_nnz", "nrows": 1, "nnz_rows": [4096]},
        {"name": "all_empty_rows", "nrows": 64, "nnz_rows": [0] * 64},
        {"name": "jagged_some_empty", "nrows": 6,
         "nnz_rows": [0, 5, 0, 1, 0, 9]},
        {"name": "passes_zero", "nrows": 32, "nnz_lo": 0, "nnz_hi": 4,
         "passes": 0, "seed": 5},
        {"name": "passes_eight", "nrows": 32, "nnz_lo": 1, "nnz_hi": 4,
         "passes": 8, "seed": 6},
        {"name": "nan_inf_data", "nrows": 16, "nnz_lo": 3, "nnz_hi": 6,
         "data": "nan_inf", "seed": 7},
        {"name": "extreme_data", "nrows": 16, "nnz_lo": 2, "nnz_hi": 5,
         "data": "extreme", "seed": 8},
        {"name": "zero_factor", "nrows": 30, "nnz_lo": 1, "nnz_hi": 4,
         "factor": "zero", "seed": 9},
        {"name": "offset_view_data", "nrows": 50, "nnz_lo": 1, "nnz_hi": 6,
         "offset": True, "seed": 10},
        {"name": "boundary_two_rows", "nrows": 2, "nnz_rows": [1, 1]},
    ]
    for i in range(24):  # property-based: fixed-seed corpus
        cases.append({"name": f"prop_{i:02d}", "nrows": int(7 * i % 400),
                      "nnz_lo": 0, "nnz_hi": int(2 + i % 20),
                      "data": ["uniform", "signed", "nan_inf", "extreme"][i % 4],
                      "factor": ["uniform", "zero"][i % 2],
                      "passes": [0, 2, 4][i % 3], "offset": bool(i % 5 == 0),
                      "seed": 1000 + i})
    return cases


def _pava_cases():
    cases = [
        {"name": "golden", "n": 2000, "seed": 2},
        {"name": "empty", "n": 0},
        {"name": "single", "n": 1, "seed": 3},
        {"name": "two_increasing", "n": 2, "shape": "increasing"},
        {"name": "two_decreasing", "n": 2, "shape": "decreasing"},
        {"name": "strictly_decreasing", "n": 500, "shape": "decreasing"},
        {"name": "strictly_increasing", "n": 500, "shape": "increasing"},
        {"name": "all_equal", "n": 256, "shape": "equal"},
        {"name": "nan_inf_y", "n": 64, "data": "nan_inf", "seed": 11},
        {"name": "extreme_y", "n": 64, "data": "extreme", "seed": 12},
        {"name": "zero_weights", "n": 128, "weight": "zero", "seed": 13},
        {"name": "negative_weights", "n": 128, "weight": "negative", "seed": 14},
        {"name": "offset_view_y", "n": 100, "offset": True, "seed": 15},
        {"name": "boundary_three", "n": 3, "shape": "decreasing"},
    ]
    for i in range(24):
        cases.append({"name": f"prop_{i:02d}", "n": int(11 * i % 800),
                      "shape": ["random", "decreasing", "increasing", "equal"][i % 4],
                      "data": ["signed", "nan_inf", "extreme"][i % 3],
                      "weight": ["uniform", "zero", "negative"][i % 3],
                      "offset": bool(i % 6 == 0), "seed": 2000 + i})
    return cases


CSR_CASES = _csr_cases()
PAVA_CASES = _pava_cases()
CASES = {"csr": CSR_CASES, "pava": PAVA_CASES}
MATERIALIZE = {"csr": materialize_csr, "pava": materialize_pava}
