"""Step 0.5.1 — D2 input-scaling logic + driver-validity tests (§4.4 item 4, §0.2).

The pure ratio/band logic is the D2 regression check's core; these tests pin it so it
cannot silently drift (e.g. accept a flat, import-dominated driver). The driver-
validity tests prove each parameterised setup builds VALID kernel inputs, so a real
scaling run measures the kernel, not a malformed call.
"""
import numpy as np
import pytest

from motifbo.timing.drivers import (
    DRIVERS,
    in_band,
    scaling_ratio,
    setup_code,
)


# --- D2 ratio/band logic (non-vacuous: must reject D2 and super-linear) ------

def test_scaling_ratio_is_large_over_small():
    assert scaling_ratio(10.0, 20.0) == 2.0
    assert scaling_ratio(4.0, 5.0) == 1.25


def test_scaling_ratio_rejects_nonpositive_baseline():
    with pytest.raises(ValueError):
        scaling_ratio(0.0, 5.0)


def test_linear_band_accepts_two_and_rejects_d2_and_superlinear():
    band = (1.7, 2.3)
    assert in_band(2.0, band)            # ideal O(n)
    assert not in_band(1.0, band)        # D2: import/startup-dominated => ~1.0x
    assert not in_band(1.5, band)        # sub-linear: still a D2 smell
    assert not in_band(4.0, band)        # super-linear surprise (e.g. O(n^2))
    assert in_band(1.7, band) and in_band(2.3, band)   # closed interval


def test_every_declared_band_excludes_unity_so_d2_always_fails():
    # the structural D2 guarantee: a flat driver (ratio ~1.0) fails EVERY band
    for name, spec in DRIVERS.items():
        lo, hi = spec["band"]
        assert lo > 1.0, f"{name} band lower bound must exclude 1.0 (D2 guard)"
        assert hi > lo
        assert not in_band(1.0, spec["band"]), name


def test_drivers_registry_covers_both_reference_kernels():
    assert set(DRIVERS) == {"csr_scale", "pava"}
    for spec in DRIVERS.values():
        p = spec["param"]
        assert spec["large"][p] == 2 * spec["small"][p], "large must double the param"


# --- driver validity: the generated setups build in-contract kernel inputs ---

def _exec_setup(kernel, size):
    ns = {}
    exec(setup_code(kernel, size), ns)          # noqa: S102 — trusted local source
    return ns["args"]


def test_csr_setup_builds_valid_inputs_at_both_sizes():
    for size in (DRIVERS["csr_scale"]["small"], DRIVERS["csr_scale"]["large"]):
        data, indptr, fac, passes = _exec_setup("csr_scale", size)
        assert data.dtype == np.float64 and indptr.dtype == np.int64
        assert fac.shape[0] == size["nrows"]
        assert indptr.shape[0] == size["nrows"] + 1
        assert indptr[0] == 0 and int(indptr[-1]) == data.shape[0] == size["nnz"]
        assert np.all(np.diff(indptr) >= 0)
        assert passes % 2 == 0


def test_pava_setup_builds_valid_inputs_at_both_sizes():
    for size in (DRIVERS["pava"]["small"], DRIVERS["pava"]["large"]):
        y_src, w_src, y, w, tgt = _exec_setup("pava", size)
        n = size["n"]
        for a in (y_src, w_src, y, w):
            assert a.dtype == np.float64 and a.shape[0] == n
        assert tgt.dtype == np.int64 and tgt.shape[0] == n


def test_setup_is_deterministic_and_size_reflected():
    s1 = setup_code("pava", {"n": 2_000_000})
    s2 = setup_code("pava", {"n": 2_000_000})
    assert s1 == s2 and "2000000" in s1
    assert setup_code("pava", {"n": 4_000_000}) != s1


def test_unknown_kernel_rejected():
    with pytest.raises(KeyError):
        setup_code("nope", {"n": 10})
