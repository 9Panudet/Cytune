"""Step 0.5.3 — gate I-1 evaluation tests (TDD, §0.3 / PREREG_I1).

speedup = median(known-bad)/median(known-good); pass iff >= the path-class threshold
(raw-pointer 1.15x, numeric-loop 1.50x). These pin the decision logic so the gate can
genuinely FAIL (a flat 1.0x must not pass; the direction bad/good must not invert).
"""
import pytest

from motifbo.calibration.i1_gate import (
    THRESHOLDS,
    evaluate,
    gate_pass,
    speedup,
)


def test_thresholds_match_section_0_3():
    assert THRESHOLDS == {"raw-pointer": 1.15, "numeric-loop": 1.50}


def test_speedup_is_median_bad_over_median_good():
    assert speedup([10, 10, 10], [20, 20, 20]) == 2.0          # bad 2x slower
    assert speedup([10, 12, 8], [10, 12, 8]) == 1.0            # identical -> 1.0
    # direction matters: faster-good => ratio > 1, NOT < 1
    assert speedup([10, 10], [15, 15]) == 1.5


def test_speedup_uses_median_not_mean():
    # an outlier in bad must not drag the ratio via the mean
    assert speedup([10] * 5, [10, 10, 10, 10, 1000]) == 1.0    # median bad = 10


def test_speedup_rejects_nonpositive_good():
    with pytest.raises(ValueError):
        speedup([0, 0], [10, 10])


def test_gate_pass_is_inclusive_at_threshold():
    assert gate_pass(1.15, 1.15)
    assert not gate_pass(1.1499, 1.15)
    assert gate_pass(2.0, 1.5)
    assert not gate_pass(1.4, 1.5)


def test_evaluate_overall_requires_all_kernels_pass():
    # csr passes (1.2 >= 1.15) but pava fails (1.4 < 1.5) -> overall FAIL
    recs = {
        "csr_scale": {"path_class": "raw-pointer",
                      "good": [10.0] * 5, "bad": [12.0] * 5},   # 1.20x
        "pava": {"path_class": "numeric-loop",
                 "good": [10.0] * 5, "bad": [14.0] * 5},        # 1.40x
    }
    res = evaluate(recs)
    assert res["per_kernel"]["csr_scale"]["pass"] is True
    assert res["per_kernel"]["pava"]["pass"] is False
    assert res["i1_pass"] is False


def test_evaluate_all_pass():
    recs = {
        "csr_scale": {"path_class": "raw-pointer",
                      "good": [10.0] * 5, "bad": [12.0] * 5},   # 1.20 >= 1.15
        "pava": {"path_class": "numeric-loop",
                 "good": [10.0] * 5, "bad": [16.0] * 5},        # 1.60 >= 1.50
    }
    res = evaluate(recs)
    assert res["i1_pass"] is True
    assert res["per_kernel"]["pava"]["threshold"] == 1.50
    assert res["per_kernel"]["csr_scale"]["speedup"] == pytest.approx(1.20)
