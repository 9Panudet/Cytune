"""cdivision edge-suite generator (Step 0.3.4, roadmap §3.2(4)).

cdivision=True swaps Python integer-division semantics for C's: quotients
truncate toward zero instead of flooring, the modulo takes the dividend's
sign instead of the divisor's, and a zero divisor is undefined behavior
(SIGFPE on x86) instead of ZeroDivisionError. The oracle edge-suite probes
both divergence surfaces for every unit whose kernel divides.

This module is the generic probe source: frozen operand pairs, the golden
outcome under Python semantics, and the §3.1 expected_exceptions manifest
entries for the zero-divisor cases. Mapping probes into a specific unit's
inputs happens at corpus curation (Step 1.1.3).

Golden outcomes are produced by evaluating the probes in Python itself —
the semantics oracle by construction, never a reimplementation. Values are
lists (not tuples) because probe outcomes cross the fresh-subprocess
boundary (§3.2(2)) as JSON, which has no tuples.
"""
from motifbo.oracle.bitwise import Outcome

# (case_name, dividend, divisor) — frozen; §3.2(4) negative-operand and
# zero-divisor probes plus agreement controls (sign combinations where C and
# Python coincide, so the suite is also tested against false positives).
DIVISION_EDGE_CASES = (
    ("positive_control", 7, 2),          # agree: (3, 1) both semantics
    ("neg_dividend", -7, 2),             # Py (-4, 1)  vs C (-3, -1)
    ("neg_divisor", 7, -2),              # Py (-4, -1) vs C (-3, 1)
    ("neg_both", -7, -2),                # agree: (3, -1) both semantics
    ("zero_divisor", 7, 0),              # Py ZeroDivisionError vs C UB
    ("zero_divisor_neg_dividend", -7, 0),
)


def division_edge_cases():
    """The frozen probe set: tuples of (case_name, dividend, divisor)."""
    return DIVISION_EDGE_CASES


def python_div_outcome(dividend, divisor):
    """Golden outcome of [dividend // divisor, dividend % divisor] under
    Python semantics — evaluated by Python itself."""
    try:
        return Outcome.value([dividend // divisor, dividend % divisor])
    except ZeroDivisionError as exc:
        return Outcome.exception(exc)


def manifest_exception_entries():
    """The motifbo-oracle-v1 expected_exceptions entries implied by the
    zero-divisor probes (§3.1: the probe expects ZeroDivisionError under
    Python semantics)."""
    return tuple({"case": name, "type": "ZeroDivisionError"}
                 for name, _, divisor in DIVISION_EDGE_CASES if divisor == 0)
