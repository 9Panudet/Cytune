"""The G1-G7 control sweep: for every guarantee, does a deliberately WRONG input make it fire?

WHY THIS FILE EXISTS. D26 was a certified `IMPROVEMENT` on a kernel where the correctness oracle
could not fail, and the thing that made it possible is that G1 -- the oldest and most load-bearing
guarantee in the product -- had never once been handed a wrong answer and asked to reject it. Its
evidence line named a test that drives `confirm_winner` on an *injected* endpoint failure, which
tests the orchestration around the oracle and never the oracle. So G1 shipped for its whole life
with negative controls only.

That is a defect class, not an incident, so the whole guarantee list was swept the same way:
`docs/GUARANTEES.md` now carries the table, and what follows is the tests it found missing.

  G1  the oracle predicate itself, `_vendor/measure_child._feasible` -- NO test called it, at all
  G2  `SAN_TOKENS` decides what counts as a sanitizer report, and nothing checked the token set
      against real sanitizer output
  G5  the whole-space subset test had no proof it would catch a policy that widened
  G6  "every number recomputes" was enforced by nothing; the headline speedup was never compared
      against the two measurements printed beneath it (now invariant I1.11)

G3, G4, G7 and G8 already had firing controls and are cited in the table rather than re-tested here.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pytest

from cytune import coherence, plan
from cytune._vendor import measure_child, theta


# ==================================================================== G1 — the oracle can fail
#
# `_feasible` is the entire correctness guarantee at the per-configuration level: it is what makes
# a build that computes the wrong answer infeasible no matter how fast it is. Both classes, both
# directions, and the shape check that keeps a differently-sized output from reaching allclose.
def _sha(arr):
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def _int_oracle(golden):
    return {"output_class": "int", "golden_sha256": _sha(golden),
            "tolerance": {"rtol": 0.0, "atol": 0.0}}


def _float_oracle(tmp_path, golden):
    p = tmp_path / "golden.npy"
    np.save(p, golden)
    return {"output_class": "float", "golden_sha256": _sha(golden),
            "golden_npy": str(p), "tolerance": {"rtol": 1e-9, "atol": 1e-12}}


def test_g1_an_integer_output_that_is_wrong_by_one_element_is_infeasible():
    """POSITIVE CONTROL. The bit-exact branch: one element differs and nothing else."""
    golden = np.arange(64, dtype=np.int64)
    wrong = golden.copy()
    wrong[7] += 1
    feasible, reason = measure_child._feasible(wrong, _sha(wrong), _int_oracle(golden))
    assert feasible == 0 and reason == "oracle_mismatch"


def test_g1_the_correct_integer_output_is_feasible():
    """Negative control. Without it, a `_feasible` that returned 0 unconditionally would pass every
    positive control above."""
    golden = np.arange(64, dtype=np.int64)
    feasible, reason = measure_child._feasible(golden, _sha(golden), _int_oracle(golden))
    assert feasible == 1 and reason == "ok"


def test_g1_a_float_output_outside_tolerance_is_infeasible(tmp_path):
    """POSITIVE CONTROL for the toleranced branch, which is the one D26 rendered vacuous."""
    golden = np.linspace(1.0, 2.0, 64)
    wrong = golden.copy()
    wrong[3] *= 1.01                                   # 1%, against an rtol of 1e-9
    feasible, reason = measure_child._feasible(wrong, _sha(wrong), _float_oracle(tmp_path, golden))
    assert feasible == 0 and reason == "oracle_mismatch"


def test_g1_a_float_output_inside_tolerance_is_feasible(tmp_path):
    """Negative control, and the reason the float class has a tolerance at all: -O3 and -ffast-math
    legitimately reassociate, so bit-exactness would refuse honest builds."""
    golden = np.linspace(1.0, 2.0, 64)
    close = golden * (1.0 + 1e-12)
    feasible, reason = measure_child._feasible(close, _sha(close),
                                               _float_oracle(tmp_path, golden))
    assert feasible == 1 and reason == "ok"


def test_g1_a_differently_shaped_output_is_infeasible_and_never_reaches_allclose(tmp_path):
    """numpy would BROADCAST a (1,) against a (64,) and call it close. The shape guard is what
    stops a kernel that returns a scalar from passing an oracle derived from an array."""
    golden = np.full(64, 3.0)
    feasible, _r = measure_child._feasible(np.array([3.0]), _sha(np.array([3.0])),
                                           _float_oracle(tmp_path, golden))
    assert feasible == 0
    assert np.allclose(np.array([3.0]), golden), "the broadcast this guard exists to prevent"


def test_g1_a_nan_where_the_golden_has_a_number_is_infeasible(tmp_path):
    """`equal_nan=True` makes NaN==NaN, which is right for a kernel that legitimately produces
    them — and would be a hole if it also swallowed a NaN that appeared out of nowhere."""
    golden = np.linspace(1.0, 2.0, 8)
    wrong = golden.copy()
    wrong[0] = np.nan
    feasible, _r = measure_child._feasible(wrong, _sha(wrong), _float_oracle(tmp_path, golden))
    assert feasible == 0


def test_g1_an_all_nan_output_matching_an_all_nan_golden_is_still_feasible(tmp_path):
    """Negative control for the clause above: the tolerance branch must not start refusing a kernel
    whose correct answer contains NaN."""
    golden = np.full(8, np.nan)
    feasible, _r = measure_child._feasible(golden.copy(), _sha(golden),
                                           _float_oracle(tmp_path, golden))
    assert feasible == 1


# =========================================================== G2 — the token set matches reality
#
# `sanitize_gate` classifies a run as SANITIZER_REPORT iff a token from `SAN_TOKENS` appears in the
# child's combined output. Every existing test of the gate feeds it a hand-built verdict dict, so
# all of them would still pass if `SAN_TOKENS` were a tuple of plausible-looking strings that no
# sanitizer ever emits. The vendor manifest pins the set by hash, which stops it DRIFTING and says
# nothing about whether it was ever right.
#
# The excerpt below is copied verbatim from `evidence/example_sanitizer_report.log`, produced by
# the real ASan gate on the real out-of-bounds fixture (config 1584). It is embedded rather than
# read from that path so this control cannot go vacuous on a checkout that lacks `evidence/` --
# which is B2's lesson, applied to the test that was written because of it.
REAL_ASAN_OUTPUT = """\
=================================================================
==19==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x7fb4df41d7f8 at pc 0x7fb4e05a36ae
READ of size 8 at 0x7fb4df41d7f8 thread T0
    #0 0x7fb4e05a36ad in __pyx_pf_6kernel_run /tmp/tmp02dd_uor/c/kernel_00010.c:15912
SUMMARY: AddressSanitizer: heap-buffer-overflow /tmp/tmp02dd_uor/c/kernel_00010.c:15912
"""

CLEAN_CHILD_OUTPUT = "SAN_CHILD_OK\n{\"ok\": true, \"n\": 3}\n"


def _tokens_in(blob):
    """The gate's own rule, applied to a blob. Kept to one expression so it cannot drift from the
    container-side line it mirrors (`sanitize_gate.py`, `tokens = sorted({t for t in
    S.SAN_TOKENS if t in blob})`)."""
    from cytune._vendor import sanitizer_build as S
    return sorted({t for t in S.SAN_TOKENS if t in blob})


def test_g2_the_token_set_actually_matches_real_sanitizer_output():
    """POSITIVE CONTROL. A token set that matched nothing real would make every gate return CLEAN,
    silently, and every existing gate test would still pass."""
    assert _tokens_in(REAL_ASAN_OUTPUT), (
        "SAN_TOKENS matched NOTHING in a real AddressSanitizer report. The §1.4 gate would have "
        "returned CLEAN on the out-of-bounds fixture that G2 exists for.")


def test_g2_a_clean_run_matches_no_token():
    """Negative control: a token set broad enough to match ordinary output would refuse every
    kernel, which is the other way for the gate to be worthless."""
    assert _tokens_in(CLEAN_CHILD_OUTPUT) == []


def test_g2_the_undefined_behaviour_half_is_covered_too():
    """UBSan does not print `AddressSanitizer`, and it is the half that caught the int64 overflow
    in the P1 fixture."""
    assert _tokens_in("kernel.c:41:9: runtime error: signed integer overflow: "
                      "9223372036854775807 + 1 cannot be represented in type 'long int'")


# ================================================ G5 — the subset check would catch a wider policy
#
# `test_policy_flags_only_ever_narrow_the_candidate_set` quantifies over all 1,728 configs, which
# makes it strong evidence that today's flags narrow -- and no evidence at all that the COMPARISON
# would notice if a future flag widened. Both are needed: the whole-space sweep is the assertion,
# this is the proof the assertion can fail.
class _WideningPolicy:
    """A stand-in for a flag someone adds later that admits what strict forbids."""

    def allows(self, cid):
        return True


def test_g5_the_subset_check_fires_on_a_policy_that_widens():
    """POSITIVE CONTROL for the G5 obligation in CONTRIBUTING: a flag is not done when it works,
    it is done when it has been shown it cannot loosen a guarantee."""
    strict = {c for c in range(theta.N_CONFIGS) if plan.EmissionPolicy().allows(c)}
    wide = {c for c in range(theta.N_CONFIGS) if _WideningPolicy().allows(c)}
    assert strict < wide, "the widening stand-in must actually widen, or this proves nothing"
    # The check G5 is made of, in the direction that must FAIL: `--portable-flags` promises to
    # only ever remove, so a policy admitting everything must not be a subset of strict.
    assert not (wide <= strict), (
        "the subset comparison G5 rests on did not notice a policy that admits every config")


def test_g5_the_same_comparison_passes_the_real_flags():
    """Negative control, so the assertion above is not passing because subset comparison is broken
    in general."""
    strict = {c for c in range(theta.N_CONFIGS) if plan.EmissionPolicy().allows(c)}
    loose = {c for c in range(theta.N_CONFIGS)
             if plan.EmissionPolicy(allow_fast_math=True, allow_fp_contract=True).allows(c)}
    assert strict <= loose


# ======================================================= G6 — the headline number recomputes (I1.11)
#
# G6's claim is "every number recomputes", and its evidence was a `RAW:` pointer on the certificate.
# A pointer is a promise about where numbers came from, not a check that they did. Nothing compared
# the speedup against the two endpoint medians recorded four keys away in the same document.
def _measured(win_ns, ref_ns, speedup):
    return {"verdict": "improvement", "speedup": speedup,
            "measurement": {"winner_endpoint_ns": win_ns, "reference_endpoint_ns": ref_ns}}


def test_i1_11_a_speedup_that_contradicts_its_own_measurements_is_refused():
    """POSITIVE CONTROL: the document says 2x above measurements that give 1.25x."""
    with pytest.raises(coherence.IncoherentCertificate) as e:
        coherence._assert_speedup_recomputes(_measured(800.0, 1000.0, 2.0))
    assert "I1.11" in str(e.value)


def test_i1_11_an_honest_document_passes():
    """Negative control. A check that raised unconditionally would satisfy the test above."""
    coherence._assert_speedup_recomputes(_measured(800.0, 1000.0, 1000.0 / 800.0))


def test_i1_11_survives_float_representation_rather_than_demanding_bit_equality():
    """The ratio is recomputed, not read back, so the comparison is a tolerance and not `==`."""
    win, ref = 3.0, 7.0
    coherence._assert_speedup_recomputes(_measured(win, ref, (ref / win) * (1 + 1e-15)))


def test_i1_11_says_nothing_when_there_is_nothing_to_check():
    """The flat route claims no speedup, and the C1-withheld route records the measurements while
    refusing to claim a ratio from them. Neither is a violation, and firing on either would refuse
    honest certificates -- the failure direction this product cannot take."""
    coherence._assert_speedup_recomputes({"verdict": "honest-flat", "speedup": None,
                                          "measurement": {"winner_endpoint_ns": 1.0,
                                                          "reference_endpoint_ns": 2.0}})
    coherence._assert_speedup_recomputes({"speedup": 1.5, "measurement": {}})
    coherence._assert_speedup_recomputes({"speedup": 1.5})
    coherence._assert_speedup_recomputes({})


def _real_improvement_certificate():
    """A genuine 2x certificate, assembled by the production builder.

    Built rather than hand-written on purpose: an invented dict trips an earlier invariant and
    would prove only that SOME check fired. This document is coherent in every other respect, so
    the single tampered field is the only thing left for the entry point to object to.
    """
    from cytune import certify, routing
    ep = {str(theta.REFERENCE_ID): {"feasible": True, "endpoint_ns": 100e6,
                                    "subs_ns": [100e6, 100e6, 100e6], "cv": 0.001},
          "3": {"feasible": True, "endpoint_ns": 50e6, "subs_ns": [50e6, 50e6, 50e6], "cv": 0.001}}
    return certify.build_certificate(
        name="demo", winner_id=3, reference_id=theta.REFERENCE_ID, endpoint=ep,
        oracle={"output_class": "float", "tolerance": {"rtol": 1e-9, "atol": 1e-12},
                "deterministic": True, "n_det_reps": 5, "golden_sha256": "abc"},
        feasibility={"n_measured": 40, "n_infeasible": 0, "infeasible_fraction": 0.0,
                     "reasons": {}},
        route={"label": routing.LABEL, "route": routing.DOE, "rule": "R4", "engine": "DOE",
               "budget": 16, "why": "because", "fallback_note": None, "feasibility_note": None},
        rig_mode="quiesced", rig_detail="quiesced — verified",
        budget={"probe": 17, "tuning": 16}, sources={"table": "/w/table.jsonl", "workspace": "/w"},
        allow_fast_math=False,
        emitted_gate={"ran": True, "clean": True, "verdict": "CLEAN", "tokens": [],
                      "config_id": 3})


def test_i1_11_an_honest_certificate_passes_the_real_entry_point():
    """Negative control for the test below, and the anti-vacuity guard for the whole pair: if this
    document did not pass, the refusal below would prove nothing about the tampering."""
    cert = _real_improvement_certificate()
    assert cert["verdict"] == "improvement"
    assert cert["speedup"] == pytest.approx(2.0)
    assert coherence.assert_certificate_coherent(cert) is True


def test_i1_11_is_reached_through_the_real_entry_point():
    """An invariant that only fires when a test calls its private helper is a test, not an
    invariant (CONTRIBUTING, "adding an invariant"). This tampers with ONE field of an otherwise
    honest document and drives the function production calls.

    This is K-14's shape made to happen: nothing hostile, just the headline number describing a
    different pair of measurements from the ones printed beneath it."""
    cert = _real_improvement_certificate()
    cert["speedup"] = 9.0
    with pytest.raises(coherence.IncoherentCertificate) as e:
        coherence.assert_certificate_coherent(cert)
    assert "I1.11" in str(e.value), (
        f"assert_certificate_coherent did not reach I1.11; it stopped at {e.value}")
