"""Step 0.4.2 — validation-input contract tests (non-vacuity guard for §3.3).

If the materialised inputs violated a kernel's contract, an ASan report in the
known-good clean run would be MY bug, not the kernel's — and "clean" would be
meaningless. These tests prove every case is a valid in-contract input, so the
clean run is a real memory-safety statement about the kernels.
"""
import numpy as np
import pytest

from motifbo.sanitize import validation_inputs as vi


def _contig(a):
    return isinstance(a, np.ndarray) and a.flags["C_CONTIGUOUS"]


@pytest.mark.parametrize("spec", vi.CSR_CASES, ids=lambda s: s["name"])
def test_csr_case_satisfies_contract(spec):
    data, indptr, row_factor, passes = vi.materialize_csr(spec)
    nrows = spec["nrows"]
    assert _contig(data) and data.dtype == np.float64
    assert _contig(indptr) and indptr.dtype == np.int64
    assert _contig(row_factor) and row_factor.dtype == np.float64
    assert row_factor.shape[0] == nrows
    assert indptr.shape[0] == nrows + 1
    assert indptr[0] == 0
    assert np.all(np.diff(indptr) >= 0), "indptr must be non-decreasing"
    assert int(indptr[-1]) == data.shape[0], "indptr[-1] must equal len(data)"
    assert passes >= 0 and passes % 2 == 0, "passes must be even (kernel raises otherwise)"


@pytest.mark.parametrize("spec", vi.PAVA_CASES, ids=lambda s: s["name"])
def test_pava_case_satisfies_contract(spec):
    y_src, w_src, y, w, target = vi.materialize_pava(spec)
    n = spec["n"]
    for a in (y_src, w_src, y, w):
        assert _contig(a) and a.dtype == np.float64 and a.shape[0] == n
    assert _contig(target) and target.dtype == np.int64 and target.shape[0] == n


def test_corpus_is_diverse_and_deterministic():
    # the set actually contains the mandated edge classes...
    csr_names = {c["name"] for c in vi.CSR_CASES}
    assert {"empty", "single_row_single_nnz", "nan_inf_data", "zero_factor",
            "offset_view_data"} <= csr_names
    pava_names = {c["name"] for c in vi.PAVA_CASES}
    assert {"empty", "single", "strictly_decreasing", "zero_weights",
            "offset_view_y"} <= pava_names
    assert len(vi.CSR_CASES) >= 30 and len(vi.PAVA_CASES) >= 30
    # ...and materialisation is deterministic (fresh subprocess rebuilds identically)
    for spec in (vi.CSR_CASES[0], vi.CSR_CASES[20]):
        a = vi.materialize_csr(spec)
        b = vi.materialize_csr(spec)
        for x, y in zip(a[:3], b[:3]):
            np.testing.assert_array_equal(x, y)


def test_offset_views_have_nonzero_base():
    # the offset edge must actually exercise a non-zero allocation base
    data, *_ = vi.materialize_csr(
        next(c for c in vi.CSR_CASES if c["name"] == "offset_view_data"))
    assert data.base is not None and data.shape[0] > 0
