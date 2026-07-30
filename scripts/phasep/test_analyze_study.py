"""analyze_study — the statistical instrument's own controls.

A harness run over the 13-seed partial data confirmed every path EXECUTES except one: the
degenerate-BCa branch, which only fires when all paired differences are identical. An unexercised
branch in a statistical instrument is exactly what breaks silently at the wrong moment, so it is
covered here along with the other decision rules the report will rest on.
"""
import numpy as np
import analyze_study as A


def test_bca_degenerate_returns_a_point_interval_and_says_so():
    """All differences equal ⇒ a bootstrap of a constant IS the constant. Reporting [d,d] as a
    plain CI would read as extraordinary precision rather than as no variation, so it is flagged."""
    lo, hi, note = A.bca_ci(np.full(12, 0.25), ("bca", "MID", 8, "bo|rs"))
    assert lo == hi == 0.25
    assert note and "degenerate" in note


def test_bca_too_few_points_is_refused_not_faked():
    lo, hi, note = A.bca_ci(np.array([0.3]), ("bca", "MID", 8, "bo|rs"))
    assert lo is None and hi is None and note == "n<2"


def test_failure_path_ordinary_data_gets_a_real_interval():
    """Non-vacuity: the degenerate branch must not swallow ordinary data."""
    rng = np.random.default_rng(0)
    lo, hi, note = A.bca_ci(rng.normal(0.5, 0.2, 40), ("bca", "MID", 8, "bo|rs"))
    assert note is None and lo < hi


def test_cliffs_delta_orientation_and_zero_handling():
    """§3.3 verbatim: δ > 0 means the FIRST-named algorithm has LOWER regret, and zero differences
    count in n while contributing 0. Getting the sign backwards would invert every routing call."""
    assert A.cliffs_delta([-1.0, -1.0, -1.0, -1.0]) == 1.0     # A always lower ⇒ δ = +1
    assert A.cliffs_delta([1.0, 1.0, 1.0, 1.0]) == -1.0        # A always higher ⇒ δ = −1
    assert A.cliffs_delta([-1.0, 1.0]) == 0.0
    assert A.cliffs_delta([-1.0, 1.0, 0.0, 0.0]) == 0.0        # zeros are in n, contribute 0
    assert A.cliffs_delta([-1.0, 0.0]) == 0.5                  # 1 win, 1 tie, n=2


def test_holm_is_step_down_and_monotone():
    raw = {"a": 0.01, "b": 0.02, "c": 0.04}
    adj = A.holm(raw)
    assert adj["a"] == 0.03 and abs(adj["b"] - 0.04) < 1e-12 and abs(adj["c"] - 0.04) < 1e-12
    assert adj["a"] <= adj["b"] <= adj["c"]                    # monotonicity enforced


def test_holm_passes_none_through_rather_than_treating_it_as_significant():
    """A pair with too few kernels has p=None. Coercing that to a number would invent a result."""
    adj = A.holm({"a": 0.01, "b": None})
    assert adj["b"] is None


def test_wilcoxon_method_choice_is_deterministic_not_a_library_default():
    """§3.3 pins exact iff n<=25 AND no zero differences AND no tied absolute differences."""
    x = np.arange(1.0, 11.0)
    _p, method, _n = A.wilcoxon(x, x + np.arange(10) * 0.1 + 0.05)
    assert method == "exact"
    big = np.arange(1.0, 31.0)
    _p, method, _n = A.wilcoxon(big, big + 0.5)                # n>25 and tied |differences|
    assert method == "approx"


def test_all_zero_differences_is_reported_not_tested():
    p, _m, note = A.wilcoxon(np.ones(8), np.ones(8))
    assert p is None and note == "all differences zero"
