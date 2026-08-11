"""C3 — the one-sentence human answer printed above the certificate.

A verdict a non-expert can act on without reading a manual. These tests pin the two properties
that make it safe to put at the top: it is TOTAL over the verdict space (no outcome falls through
to silence) and it never says something the document does not support.
"""
from __future__ import annotations

import pytest

from cytune import certify
from cytune._vendor import theta

REF = theta.REFERENCE_ID
FAST = theta.id_of((False, False, True, False, False, "-O3", "native", "on", ("off", "off")))


def _cert(**kw):
    base = {"verdict": certify.HONEST_FLAT, "emitted_config": {"config_id": REF},
            "sanitizer_gate": {"ran": True, "clean": True, "verdict": "CLEAN"}, "speedup": None}
    base.update(kw)
    return base


@pytest.mark.parametrize("verdict", sorted(certify.EXIT_BY_VERDICT))
def test_every_verdict_gets_an_answer(verdict):
    """Total over the verdict space. A user must never be handed a certificate with no answer."""
    line = certify.next_step(_cert(verdict=verdict))
    assert line and line.startswith("WHAT TO DO"), line
    assert len(line) > 40, "an answer that short is not an answer"


def test_an_unknown_verdict_still_answers_rather_than_crashing():
    line = certify.next_step(_cert(verdict="something-new"))
    assert line.startswith("WHAT TO DO")


def test_a_memory_finding_outranks_a_good_speed_result():
    """The ordering judgement, pinned. A kernel that reads out of bounds must not be told to go
    faster first, even when the speed result is real."""
    line = certify.next_step(_cert(verdict=certify.IMPROVEMENT, speedup=2.0,
                                   emitted_config={"config_id": FAST},
                                   memory_safety_finding={"tokens": ["AddressSanitizer"]}))
    assert "memory-safety" in line
    assert "2.0" not in line and "faster" not in line, (
        "the speed number must not appear beside an unfixed memory-safety report")


def test_the_emitted_finding_variant_is_also_caught():
    """certify uses `memory_safety_finding_emitted` when a rejection finding already exists. If
    next_step only knew the first key, the highest-consequence case would print a speed answer."""
    line = certify.next_step(_cert(verdict=certify.NO_SAFE_IMPROVEMENT,
                                   memory_safety_finding_emitted={"tokens": ["AddressSanitizer"]}))
    assert "memory-safety" in line


def test_an_improvement_says_paste_the_header_and_quotes_the_measured_ratio():
    line = certify.next_step(_cert(verdict=certify.IMPROVEMENT, speedup=1.9621,
                                   emitted_config={"config_id": FAST}))
    assert "paste" in line and "1.962" in line


def test_an_unearned_safety_claim_is_qualified_in_the_same_sentence():
    """H6/V-7: when the gate could not run authoritatively, the speed claim stands and the safety
    claim does not — and the user is told so where they will read it, not two screens down."""
    line = certify.next_step(_cert(verdict=certify.IMPROVEMENT, speedup=1.5,
                                   emitted_config={"config_id": FAST},
                                   safety_wording_earned=False))
    assert "did not run authoritatively" in line


def test_honest_flat_says_do_nothing_and_says_it_is_not_a_failure():
    line = certify.next_step(_cert(verdict=certify.HONEST_FLAT))
    assert "keep your current settings" in line
    assert "not a failure" in line, (
        "G3's whole point is that 'no improvement' is an answer; the sentence a user reads first "
        "is where that has to be said")


def test_no_safe_improvement_points_at_the_rejection_block():
    line = certify.next_step(_cert(verdict=certify.NO_SAFE_IMPROVEMENT,
                                   emitted_config={"config_id": REF}))
    assert "REJECTED" in line


def test_it_is_not_part_of_the_rendered_certificate():
    """The document is unchanged: certificate.txt must still round-trip from certificate.json.
    This is what keeps I1.10 true while adding a line above it."""
    c = _cert(verdict=certify.HONEST_FLAT)
    assert certify.next_step(c) not in str(c)
