"""Step 0.P / G1 — Hypothesis property-corpus contract tests (non-vacuity guard, §3.3).

The Hypothesis sanitizer pass (run_hypothesis_sanitize.py) is only a real
memory-safety statement if every GENERATED spec is in-contract — otherwise a
ValueError (e.g. odd `passes`) would masquerade as a "report" (it did, on the first
run). These tests prove the strategies emit only in-contract specs and that the
corpus is deterministic (committable), mirroring test_validation_inputs.py.
"""
import numpy as np
import pytest

from motifbo.sanitize import hypothesis_inputs as hi
from motifbo.sanitize import validation_inputs as vi

_N = 40
_CSR = hi.generate_corpus("csr", _N)
_PAVA = hi.generate_corpus("pava", _N)


def _contig(a):
    return isinstance(a, np.ndarray) and a.flags["C_CONTIGUOUS"]


@pytest.mark.parametrize("spec", _CSR, ids=lambda s: s["name"])
def test_hyp_csr_spec_in_contract(spec):
    data, indptr, row_factor, passes = vi.materialize_csr(spec)
    nrows = spec["nrows"]
    assert _contig(data) and data.dtype == np.float64
    assert _contig(indptr) and indptr.dtype == np.int64
    assert _contig(row_factor) and row_factor.dtype == np.float64
    assert row_factor.shape[0] == nrows
    assert indptr.shape[0] == nrows + 1 and indptr[0] == 0
    assert np.all(np.diff(indptr) >= 0)
    assert int(indptr[-1]) == data.shape[0]
    assert passes >= 0 and passes % 2 == 0, "csr_scale kernel raises on odd passes"


@pytest.mark.parametrize("spec", _PAVA, ids=lambda s: s["name"])
def test_hyp_pava_spec_in_contract(spec):
    y_src, w_src, y, w, target = vi.materialize_pava(spec)
    n = spec["n"]
    for a in (y_src, w_src, y, w):
        assert _contig(a) and a.dtype == np.float64 and a.shape[0] == n
    assert _contig(target) and target.dtype == np.int64 and target.shape[0] == n


def test_generate_corpus_is_deterministic():
    # derandomize + no DB + generate-only => identical corpus every call (committable)
    assert hi.generate_corpus("csr", _N) == _CSR
    assert hi.generate_corpus("pava", _N) == _PAVA


def test_corpus_is_diverse():
    # the generated set actually spans the value/shape classes that matter for ASan
    csr_data_modes = {s["data"] for s in _CSR}
    assert {"nan_inf", "extreme"} <= csr_data_modes
    assert any(s.get("offset") for s in _CSR)
    pava_shapes = {s["shape"] for s in _PAVA}
    assert len(pava_shapes) >= 3
    assert len(_CSR) == _N and len(_PAVA) == _N
