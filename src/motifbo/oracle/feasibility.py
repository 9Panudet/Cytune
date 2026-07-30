"""§3.5 feasibility encoding — ORACLE dimension (Step 0.P / D.2, P1d).

§3.5: feasible(unit, theta) = 0 if any of {compile error | segfault/abort |
sanitizer report != 0 | correctness-critical mismatch (incl. wrong/missing
exception) | numeric output outside declared tolerance | timeout | memory-cap
kill}, else 1.

This module encodes ONLY the oracle dimension of that disjunction: given the
return of a comparator (`compare_bitwise` / `compare_tolerance` /
`compare_outcomes` — `None` for a match, a non-empty reason string for a
divergence), it yields the feasibility bit those comparators contribute. It is
the primitive exhibited at the I-3 gate to validate the central exclusion claim
(e.g. fast-math on a correctness-critical output -> bitwise mismatch -> 0,
§3.2(1)). The FULL composition over all §3.5 causes (compile/sanitizer/process/
timeout/memory) and the safety-class memoization is Step 1.4.3; this is not that.
"""


def oracle_feasible(comparison_result):
    """Return the §3.5 oracle-dimension feasibility bit for one output.

    `comparison_result` MUST be a comparator return value: `None` (the
    candidate matched golden / stayed within tolerance / raised the right
    exception) -> 1; a non-empty reason `str` (any correctness-critical
    mismatch, wrong/missing exception, or numeric outside tolerance) -> 0.

    Anything else (bool, int, object, empty string) is not a valid comparator
    result and raises `TypeError` rather than being silently coerced — so a
    vacuous caller cannot launder a non-answer into "feasible".
    """
    if comparison_result is None:
        return 1
    if type(comparison_result) is str and comparison_result:
        return 0
    raise TypeError(
        "oracle_feasible expects a comparator result (None or a non-empty "
        f"reason str), got {comparison_result!r}")
