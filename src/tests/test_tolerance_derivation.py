"""Step 1.1.3 — §3.1 tolerance-DERIVATION TDD (deferred from Phase 0).

derive_tolerance(reps, atol_floor=, rtol_floor=) computes
    tolerance = max(10 * cross-rep deviation, domain floor)
as a motifbo-oracle-v1 atol_rtol dict. These tests exercise the REAL comparator
(compare_tolerance) and the REAL manifest validator (validate_manifest) on the
derived tolerance — no vacuous assertions on a stubbed value.
"""
import numpy as np
import pytest

from motifbo.oracle.tolerance import derive_tolerance, compare_tolerance
from motifbo.oracle.manifest import validate_manifest


def _manifest_with(tol):
    """Embed a derived tolerance in a minimal valid oracle.json doc."""
    return {"schema": "motifbo-oracle-v1", "unit": "u",
            "outputs": [{"name": "y", "class": "numerically-approximate",
                         "tolerance": tol}]}


def test_deterministic_reps_yield_exactly_the_domain_floor():
    # spread 0 (a deterministic kernel, like our corpus under OMP=1) -> floor.
    x = np.array([1.0, 2.0, 3.0])
    tol = derive_tolerance([x.copy(), x.copy(), x.copy()],
                           atol_floor=1e-9, rtol_floor=1e-7)
    assert tol == {"mode": "atol_rtol", "atol": 1e-9, "rtol": 1e-7}
    assert validate_manifest(_manifest_with(tol)) == []   # not bitwise-in-disguise


def test_abs_deviation_drives_atol_at_10x():
    base = np.array([100.0, 100.0])
    D = 1e-3
    reps = [base, base + D, base - D]                 # median = base, max |dev| = D
    tol = derive_tolerance(reps, atol_floor=1e-12, rtol_floor=1e-12)
    assert tol["atol"] == pytest.approx(10 * D)       # 10x abs deviation beats the tiny floor
    assert tol["rtol"] == pytest.approx(10 * D / 100)  # rel_dev = D/|median|


def test_floor_wins_when_deviation_is_smaller_than_floor():
    base = np.array([1.0, 1.0])
    reps = [base, base + 1e-15, base - 1e-15]         # 10x dev ~1e-14 < floors
    tol = derive_tolerance(reps, atol_floor=1e-6, rtol_floor=1e-6)
    assert tol == {"mode": "atol_rtol", "atol": 1e-6, "rtol": 1e-6}


def test_roundtrip_through_the_real_comparator():
    base = np.array([100.0, 100.0, 100.0])
    D = 1e-3
    reps = [base, base + D, base - D]
    tol = derive_tolerance(reps, atol_floor=1e-12, rtol_floor=1e-12)
    # bound at golden=100: atol + rtol*100 = 10D + 10D = 20D
    golden = base
    assert compare_tolerance(golden, base + 1e-2, tol) is None          # 10D <= 20D -> PASS
    assert compare_tolerance(golden, base + 3e-2, tol) is not None      # 30D > 20D -> FAIL


def test_fewer_than_two_reps_raises():
    with pytest.raises(ValueError, match=">= 2"):
        derive_tolerance([np.array([1.0])], atol_floor=1e-9, rtol_floor=1e-9)


def test_shape_or_dtype_disagreement_raises():
    with pytest.raises(ValueError, match="shape"):
        derive_tolerance([np.zeros(3), np.zeros(4)], atol_floor=1e-9, rtol_floor=1e-9)
    with pytest.raises(TypeError, match="dtype"):
        derive_tolerance([np.zeros(3, np.float32), np.zeros(3, np.float64)],
                         atol_floor=1e-9, rtol_floor=1e-9)


def test_non_float_dtype_raises():
    with pytest.raises(TypeError, match="correctness-critical"):
        derive_tolerance([np.array([1, 2]), np.array([1, 2])],
                         atol_floor=1e-9, rtol_floor=1e-9)


def test_nonpositive_floor_raises():
    x = np.array([1.0, 2.0])
    with pytest.raises(ValueError, match="bitwise in disguise"):
        derive_tolerance([x, x], atol_floor=0.0, rtol_floor=1e-9)


def test_consistent_inf_excluded_but_finite_part_drives_tolerance():
    # inf in ALL reps (e.g. unreachable-node graph distance) -> excluded; finite part used.
    D = 1e-3
    reps = [np.array([np.inf, 100.0]),
            np.array([np.inf, 100.0 + D]),
            np.array([np.inf, 100.0 - D])]
    tol = derive_tolerance(reps, atol_floor=1e-12, rtol_floor=1e-12)
    assert tol["atol"] == pytest.approx(10 * D)


def test_inf_in_some_reps_only_is_nondeterminism_and_raises():
    reps = [np.array([np.inf, 1.0]), np.array([2.0, 1.0])]   # element 0 inf in only one rep
    with pytest.raises(ValueError, match="non-finite in some reps but not all"):
        derive_tolerance(reps, atol_floor=1e-9, rtol_floor=1e-9)
