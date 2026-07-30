"""Step 0.3.2 — bitwise comparator tests (TDD, red first).

Grounding (roadmap §3.1/§3.5): correctness-critical outputs must be
bitwise-identical to golden — bytes + dtype + shape — and the raised-exception
TYPE is itself correctness-critical ground truth ("wrong/missing exception"
=> infeasible). Bitwise means bitwise: -0.0 != 0.0, NaN payloads must match,
same values under a different dtype or shape are mismatches.
"""
import struct

import numpy as np
import pytest

from motifbo.oracle.bitwise import Outcome, compare_bitwise, compare_outcomes


def nan_with_payload(bits):
    return float(np.frombuffer(struct.pack("<Q", bits), dtype=np.float64)[0])


def assert_mismatch(reason, *fragments):
    assert reason is not None, "expected a mismatch, got a match"
    for f in fragments:
        assert f in reason, f"expected {f!r} in mismatch reason {reason!r}"


# --- arrays: bytes + dtype + shape -------------------------------------------

def test_identical_arrays_match_including_nan_and_negative_zero():
    a = np.array([1.5, -0.0, np.nan, np.inf])
    assert compare_bitwise(a, a.copy()) is None


def test_negative_zero_vs_zero_is_a_mismatch():
    g = np.array([-0.0])
    c = np.array([0.0])
    assert_mismatch(compare_bitwise(g, c), "bytes")


def test_nan_payload_difference_is_a_mismatch():
    g = np.array([nan_with_payload(0x7FF8000000000000)])
    c = np.array([nan_with_payload(0x7FF8000000000001)])
    assert_mismatch(compare_bitwise(g, c), "bytes")


def test_same_values_different_dtype_is_a_mismatch():
    g = np.arange(4, dtype=np.int64)
    c = np.arange(4, dtype=np.int32)
    assert_mismatch(compare_bitwise(g, c), "dtype")


def test_same_bytes_different_shape_is_a_mismatch():
    g = np.arange(6, dtype=np.float64).reshape(2, 3)
    c = np.arange(6, dtype=np.float64).reshape(3, 2)  # identical tobytes()
    assert_mismatch(compare_bitwise(g, c), "shape")


def test_noncontiguous_view_matches_its_copy():
    base = np.arange(10, dtype=np.float64)
    assert compare_bitwise(base[::2], base[::2].copy()) is None


def test_single_element_difference_is_a_mismatch_with_element_index():
    g = np.zeros(64, dtype=np.float64)
    c = g.copy()
    c[17] = 1.0  # little-endian 1.0 first differs at byte 6 within the element
    assert_mismatch(compare_bitwise(g, c), "bytes", "element index 17")


def test_empty_arrays_match_but_dtype_still_checked():
    assert compare_bitwise(np.empty(0, np.float64), np.empty(0, np.float64)) is None
    assert_mismatch(
        compare_bitwise(np.empty(0, np.float64), np.empty(0, np.float32)), "dtype")


def test_array_vs_list_is_a_type_mismatch():
    assert_mismatch(compare_bitwise(np.array([1, 2]), [1, 2]), "type")


def test_object_dtype_arrays_are_rejected_loudly():
    arr = np.array([object()], dtype=object)
    with pytest.raises(TypeError):
        compare_bitwise(arr, arr)


# --- scalars ------------------------------------------------------------------

def test_int_equality_and_inequality():
    assert compare_bitwise(2**80, 2**80) is None
    assert_mismatch(compare_bitwise(7, 8), "7", "8")


def test_bool_is_not_int():
    assert compare_bitwise(True, True) is None
    assert_mismatch(compare_bitwise(True, 1), "type")


def test_float_bit_pattern_scalars():
    assert compare_bitwise(1.5, 1.5) is None
    assert compare_bitwise(float("nan"), float("nan")) is None  # same CPython bits
    assert_mismatch(compare_bitwise(0.0, -0.0), "bit")
    assert_mismatch(
        compare_bitwise(nan_with_payload(0x7FF8000000000000),
                        nan_with_payload(0x7FF8000000000001)), "bit")


def test_complex_bit_pattern():
    assert compare_bitwise(complex(1.0, 2.0), complex(1.0, 2.0)) is None
    assert_mismatch(compare_bitwise(complex(0.0, 0.0), complex(0.0, -0.0)), "bit")


def test_numpy_scalars_compare_by_dtype_and_bits():
    assert compare_bitwise(np.float64(1.5), np.float64(1.5)) is None
    assert_mismatch(compare_bitwise(np.float64(1.5), np.float32(1.5)), "type")
    assert_mismatch(compare_bitwise(np.float64(1.5), 1.5), "type")  # no coercion


def test_str_bytes_none():
    assert compare_bitwise("abc", "abc") is None
    assert_mismatch(compare_bitwise("abc", "abd"), "abd")
    assert compare_bitwise(b"\x00\x01", b"\x00\x01") is None
    assert_mismatch(compare_bitwise(b"\x00", b"\x01"), "mismatch")
    assert compare_bitwise(None, None) is None
    assert_mismatch(compare_bitwise(None, 0), "type")


def test_unsupported_type_raises():
    with pytest.raises(TypeError):
        compare_bitwise(object(), object())


# --- containers: contents/layout (§3.1) ----------------------------------------

def test_nested_containers_match():
    g = {"d": np.arange(3), "meta": (1, [True, None], "x")}
    c = {"d": np.arange(3), "meta": (1, [True, None], "x")}
    assert compare_bitwise(g, c) is None


def test_list_vs_tuple_is_a_layout_mismatch():
    assert_mismatch(compare_bitwise([1, 2], (1, 2)), "type")


def test_length_mismatch():
    assert_mismatch(compare_bitwise([1, 2], [1, 2, 3]), "length")


def test_nested_mismatch_reports_path():
    g = {"pred": [0, 1, 2]}
    c = {"pred": [0, 9, 2]}
    reason = compare_bitwise(g, c)
    assert_mismatch(reason, "pred", "[1]")


def test_dict_key_set_mismatch():
    reason = compare_bitwise({"a": 1, "b": 2}, {"a": 1, "z": 2})
    assert_mismatch(reason, "key", "b", "z")


def test_dict_insertion_order_is_not_compared():
    assert compare_bitwise({"a": 1, "b": 2}, {"b": 2, "a": 1}) is None


# --- exception identity (§3.1: raised-exception type; §3.5: wrong/missing) -----

def test_value_outcomes_delegate_to_bitwise():
    assert compare_outcomes(Outcome.value(7), Outcome.value(7)) is None
    assert_mismatch(compare_outcomes(Outcome.value(0.0), Outcome.value(-0.0)),
                    "bit")


def test_cdivision_style_missing_exception_is_caught():
    # Golden (Python semantics) raises ZeroDivisionError; a cdivision=True
    # candidate silently returns a value instead — must be infeasible (§3.5).
    g = Outcome.exception(ZeroDivisionError("integer division by zero"))
    c = Outcome.value(0)
    assert_mismatch(compare_outcomes(g, c), "missing exception",
                    "ZeroDivisionError")


def test_unexpected_exception_is_caught():
    g = Outcome.value(1.0)
    c = Outcome.exception(MemoryError())
    assert_mismatch(compare_outcomes(g, c), "unexpected exception", "MemoryError")


def test_same_exception_type_matches():
    g = Outcome.exception(ZeroDivisionError("a"))
    c = Outcome.exception(ZeroDivisionError("b"))  # message is NOT ground truth
    assert compare_outcomes(g, c) is None


def test_subclass_does_not_satisfy_exception_identity():
    # ZeroDivisionError IS-A ArithmeticError; identity must still reject it —
    # an isinstance-based comparator would wrongly pass this.
    g = Outcome.exception(ArithmeticError())
    c = Outcome.exception(ZeroDivisionError())
    assert_mismatch(compare_outcomes(g, c), "ArithmeticError", "ZeroDivisionError")
    assert_mismatch(compare_outcomes(c, g), "exception")


def test_outcome_exception_accepts_instance_type_and_canonical_name():
    by_instance = Outcome.exception(ZeroDivisionError())
    by_type = Outcome.exception(ZeroDivisionError)
    by_name = Outcome.exception("builtins.ZeroDivisionError")
    assert compare_outcomes(by_instance, by_type) is None
    assert compare_outcomes(by_instance, by_name) is None


def test_outcome_exception_rejects_non_exceptions():
    for bad in (7, int, "not.an identifier!"):
        with pytest.raises(TypeError):
            Outcome.exception(bad)
