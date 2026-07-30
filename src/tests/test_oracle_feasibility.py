"""Step 0.P / D.2 (P1d) — §3.5 oracle-dimension feasibility, incl. the fast-math
exclusion (§3.2(1)). TDD, red first.

Validates the CENTRAL safety claim at the I-3 gate: a configuration that compiles
and runs cleanly but produces a wrong/out-of-tolerance result is rejected
(feasible=0) — and in particular **fast-math on a correctness-critical output is
infeasible** ("preserve the optimization ceiling at zero correctness cost").

§3.5: feasible=0 if any of {compile error | segfault/abort | sanitizer report != 0 |
correctness-critical mismatch (incl. wrong/missing exception) | numeric outside
declared tolerance | timeout | memory-cap kill}, else 1. This exercises the ORACLE
dimension of that disjunction; the full multi-cause composition + safety-class
memoization is Step 1.4.3.
"""
import numpy as np
import pytest

from motifbo.oracle.bitwise import Outcome, compare_bitwise, compare_outcomes
from motifbo.oracle.feasibility import oracle_feasible
from motifbo.oracle.manifest import validate_manifest
from motifbo.oracle.tolerance import compare_tolerance

_TOL = {"mode": "atol_rtol", "atol": 1e-9, "rtol": 1e-9}


def test_match_is_feasible_mismatch_is_infeasible():
    # the §3.5 oracle-dimension mapping itself
    assert oracle_feasible(None) == 1
    assert oracle_feasible("any non-None mismatch reason") == 0


def test_fast_math_reassociation_on_correctness_critical_output_is_infeasible():
    # -ffast-math permits FP reassociation; on a bit-exact output it changes bits.
    # The two evaluation orders the optimiser may pick for an a*b+c-style reduction:
    golden = np.array([(1e16 + -1e16) + 1.0])      # left-assoc   -> 1.0
    fastmath = np.array([1e16 + (-1e16 + 1.0)])    # reassociated -> 0.0
    assert golden[0] != fastmath[0]                # the divergence is real (1.0 vs 0.0)
    # a correctness-critical output is compared BITWISE (tolerance is forbidden on
    # it — see the next test), so any bit difference is a mismatch:
    reason = compare_bitwise(golden, fastmath)
    assert reason is not None
    # §3.5: correctness-critical mismatch -> feasible = 0. The whole exclusion claim.
    assert oracle_feasible(reason) == 0


def test_correctness_critical_output_cannot_declare_a_tolerance():
    # makes the exclusion non-escapable: a bit-exact output may NOT carry a
    # tolerance that would let a fast-math bit diff slip through. validate_manifest
    # RETURNS an errors list ([] == valid); the contradiction must appear in it.
    errors = validate_manifest({
        "schema": "motifbo-oracle-v1", "unit": "u",
        "outputs": [{"name": "o", "class": "correctness-critical", "tolerance": _TOL}]})
    assert any("tolerance" in e for e in errors), errors


def test_within_tolerance_numeric_diff_is_feasible_but_outside_is_not():
    # contrast (the Horner PASS case): on a numerically-approximate output an
    # FMA-rounding-scale diff within atol/rtol is FEASIBLE...
    g, c_ok = np.array([1.0]), np.array([1.0 + 3e-15])
    assert oracle_feasible(compare_tolerance(g, c_ok, _TOL)) == 1
    # ...but a diff OUTSIDE the declared tolerance is infeasible.
    c_bad = np.array([1.0 + 1e-6])
    assert oracle_feasible(compare_tolerance(g, c_bad, _TOL)) == 0


def test_wrong_or_missing_exception_is_infeasible():
    # §3.5 "wrong/missing exception": golden raises, candidate silently returns.
    g, c = Outcome.exception(ZeroDivisionError()), Outcome.value(0)
    assert oracle_feasible(compare_outcomes(g, c)) == 0


def test_oracle_feasible_rejects_non_integer_garbage_loudly():
    # the contract is a comparator return (None or a reason string); a bool is
    # NOT a valid comparison result and must not be silently coerced.
    with pytest.raises(TypeError):
        oracle_feasible(True)
