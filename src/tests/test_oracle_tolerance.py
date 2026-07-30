"""Step 0.3.3 — tolerance comparator tests (TDD, red first).

Grounding (roadmap §3.1): numerically-approximate outputs must satisfy the
declared per-benchmark tolerance — (atol, rtol) or max-ULP — from the
motifbo-oracle-v1 manifest. NaN/Inf policy (both modes): non-finite values
must match positionally and identically (NaN<->NaN, +inf<->+inf, -inf<->-inf);
tolerance arithmetic applies to finite pairs only.
"""
import numpy as np
import pytest

from motifbo.oracle.tolerance import compare_tolerance


def tol_ar(atol=0.0, rtol=0.0):
    return {"mode": "atol_rtol", "atol": atol, "rtol": rtol}


def tol_ulp(max_ulp):
    return {"mode": "ulp", "max_ulp": max_ulp}


def assert_mismatch(reason, *fragments):
    assert reason is not None, "expected a mismatch, got a match"
    for f in fragments:
        assert f in reason, f"expected {f!r} in mismatch reason {reason!r}"


# --- atol/rtol: bounds -----------------------------------------------------

def test_exact_equality_passes_with_zero_tolerance():
    a = np.array([1.0, -2.5, 0.0])
    assert compare_tolerance(a, a.copy(), tol_ar()) is None


def test_within_and_outside_atol():
    g = np.array([1.0, 2.0])
    c = np.array([1.0 + 5e-13, 2.0])
    assert compare_tolerance(g, c, tol_ar(atol=1e-12)) is None
    assert_mismatch(compare_tolerance(g, c, tol_ar(atol=1e-13)), "tolerance")


def test_rtol_scales_by_golden_not_candidate():
    # |c - g| = 1.0; bound = rtol * |golden|. golden=2 -> bound 1.0 (pass);
    # golden=1 -> bound 0.5 (fail). An implementation scaling by |candidate|
    # would get both wrong.
    assert compare_tolerance(np.array([2.0]), np.array([1.0]),
                             tol_ar(rtol=0.5)) is None
    assert_mismatch(compare_tolerance(np.array([1.0]), np.array([2.0]),
                                      tol_ar(rtol=0.5)), "tolerance")


def test_atol_and_rtol_combine_additively():
    g = np.array([10.0])
    c = np.array([10.0 + 0.2])
    assert compare_tolerance(g, c, tol_ar(atol=0.1, rtol=0.011)) is None  # 0.21
    assert_mismatch(compare_tolerance(g, c, tol_ar(atol=0.1, rtol=0.009)),
                    "tolerance")  # bound 0.19 < 0.2


def test_zero_golden_elements_get_atol_only():
    g = np.array([0.0])
    c = np.array([1e-9])
    assert_mismatch(compare_tolerance(g, c, tol_ar(rtol=0.9)), "tolerance")
    assert compare_tolerance(g, c, tol_ar(atol=1e-8)) is None


def test_worst_element_and_count_are_reported():
    g = np.zeros(8)
    c = g.copy()
    c[3] = 1e-6   # violation
    c[5] = 2e-6   # worst violation
    reason = compare_tolerance(g, c, tol_ar(atol=1e-9))
    assert_mismatch(reason, "(5,)", "2 of 8")


def test_scalars_and_empty_arrays():
    assert compare_tolerance(1.0, 1.0 + 5e-13, tol_ar(atol=1e-12)) is None
    assert_mismatch(compare_tolerance(1.0, 1.1, tol_ar(atol=1e-12)), "tolerance")
    assert compare_tolerance(np.empty(0), np.empty(0), tol_ar()) is None


def test_complex_uses_modulus_distance():
    g = np.array([1.0 + 1.0j])
    c = np.array([1.0 + 1.0j + (3e-13 + 4e-13j)])  # |diff| = 5e-13
    assert compare_tolerance(g, c, tol_ar(atol=6e-13)) is None
    assert_mismatch(compare_tolerance(g, c, tol_ar(atol=4e-13)), "tolerance")


# --- NaN/Inf policy (shared by both modes) ----------------------------------

def test_nan_matches_nan_positionally():
    g = np.array([1.0, np.nan, 3.0])
    c = np.array([1.0, np.nan, 3.0])
    assert compare_tolerance(g, c, tol_ar()) is None
    assert compare_tolerance(g, c, tol_ulp(1)) is None


def test_nan_against_finite_fails_both_directions():
    g = np.array([np.nan])
    c = np.array([0.0])
    assert_mismatch(compare_tolerance(g, c, tol_ar(atol=1e308)), "non-finite")
    assert_mismatch(compare_tolerance(c, g, tol_ar(atol=1e308)), "non-finite")


def test_inf_matches_only_same_signed_inf():
    inf = np.inf
    assert compare_tolerance(np.array([inf]), np.array([inf]), tol_ar()) is None
    assert compare_tolerance(np.array([-inf]), np.array([-inf]), tol_ulp(1)) is None
    assert_mismatch(compare_tolerance(np.array([inf]), np.array([-inf]),
                                      tol_ar(atol=1e308)), "non-finite")


def test_inf_is_never_within_ulps_of_a_finite_value():
    # DBL_MAX is adjacent to +inf in bit space; the identity policy must
    # still reject it — "within N ULPs of inf" does not exist.
    g = np.array([np.inf])
    c = np.array([np.finfo(np.float64).max])
    assert_mismatch(compare_tolerance(g, c, tol_ulp(1000)), "non-finite")


def test_nan_position_disagreement_fails_in_ulp_mode():
    g = np.array([np.nan, 1.0])
    c = np.array([1.0, np.nan])
    assert_mismatch(compare_tolerance(g, c, tol_ulp(10)), "non-finite", "(0,)")


# --- ULP mode ----------------------------------------------------------------

def test_zero_and_one_ulp_distances():
    one = np.array([1.0])
    up1 = np.nextafter(one, 2.0)
    assert compare_tolerance(one, one.copy(), tol_ulp(1)) is None
    assert compare_tolerance(one, up1, tol_ulp(1)) is None
    up2 = np.nextafter(up1, 2.0)
    assert_mismatch(compare_tolerance(one, up2, tol_ulp(1)), "ULP")
    assert compare_tolerance(one, up2, tol_ulp(2)) is None


def test_ulp_counts_across_binade_boundary():
    one = np.array([1.0])
    down1 = np.nextafter(one, 0.0)  # mantissa wraps into the lower binade
    assert compare_tolerance(one, down1, tol_ulp(1)) is None
    assert_mismatch(compare_tolerance(one, np.nextafter(down1, 0.0),
                                      tol_ulp(1)), "ULP")


def test_signed_zeros_are_zero_ulps_apart():
    assert compare_tolerance(np.array([0.0]), np.array([-0.0]),
                             tol_ulp(1)) is None


def test_sign_straddle_counts_through_zero():
    pos = np.nextafter(np.array([0.0]), 1.0)   # smallest positive subnormal
    neg = np.nextafter(np.array([0.0]), -1.0)  # smallest negative subnormal
    assert compare_tolerance(pos, neg, tol_ulp(2)) is None
    assert_mismatch(compare_tolerance(pos, neg, tol_ulp(1)), "ULP")


def test_opposite_sign_huge_values_do_not_wrap_around():
    # The ordered-int distance between -1e300 and 1e300 exceeds 2**63; naive
    # int64 arithmetic wraps and could falsely pass a small max_ulp.
    g = np.array([1e300])
    c = np.array([-1e300])
    assert_mismatch(compare_tolerance(g, c, tol_ulp(4)), "ULP")


def test_ulp_respects_float32_grid():
    one = np.array([1.0], dtype=np.float32)
    up1 = np.nextafter(one, np.float32(2.0))
    assert compare_tolerance(one, up1, tol_ulp(1)) is None
    assert_mismatch(compare_tolerance(one, np.nextafter(up1, np.float32(2.0)),
                                      tol_ulp(1)), "ULP")


def test_ulp_worst_element_is_reported():
    g = np.array([1.0, 1.0, 1.0])
    c = g.copy()
    c[1] = np.nextafter(np.nextafter(1.0, 2.0), 2.0)  # 2 ULPs
    reason = compare_tolerance(g, c, tol_ulp(1))
    assert_mismatch(reason, "(1,)", "2")


# --- strictness gates ----------------------------------------------------------

def test_shape_mismatch_is_a_mismatch():
    assert_mismatch(compare_tolerance(np.zeros(3), np.zeros(4), tol_ar(atol=1.0)),
                    "shape")


def test_dtype_mismatch_is_a_mismatch_in_both_modes():
    g32 = np.zeros(2, dtype=np.float32)
    g64 = np.zeros(2, dtype=np.float64)
    assert_mismatch(compare_tolerance(g64, g32, tol_ar(atol=1.0)), "dtype")
    assert_mismatch(compare_tolerance(g32, g64, tol_ulp(1)), "dtype")


def test_integer_golden_is_rejected_loudly():
    # §3.1: integer outputs are correctness-critical — declaring them
    # numerically-approximate is a manifest/programming error, not a mismatch.
    with pytest.raises(TypeError):
        compare_tolerance(np.arange(3), np.arange(3), tol_ar(atol=1.0))


def test_ulp_mode_rejects_complex_and_unsupported_float_widths():
    z = np.zeros(2, dtype=np.complex128)
    with pytest.raises(TypeError):
        compare_tolerance(z, z, tol_ulp(1))
    h = np.zeros(2, dtype=np.float16)
    with pytest.raises(TypeError):
        compare_tolerance(h, h, tol_ulp(1))


def test_unknown_tolerance_mode_raises():
    with pytest.raises(ValueError):
        compare_tolerance(np.zeros(1), np.zeros(1), {"mode": "relative"})
    with pytest.raises(ValueError):
        compare_tolerance(np.zeros(1), np.zeros(1), None)
