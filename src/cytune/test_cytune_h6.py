"""H6 — `CYTUNE_SANITIZER_IMAGE` could manufacture a clean gate.

`sanitize_gate.gate()` runs a container and parses the JSON its `python3` prints on stdout. The
override exists so the NOT-RUN path can be exercised without deleting the pinned image, and the
module docstring claimed it "CANNOT produce a false pass ... the only thing it can do is make the
guarantee weaker AND SAY SO".

That was false, and the adversarial campaign demonstrated it end-to-end: a stub image whose
`python3` echoes one JSON line turned a kernel whose real §1.4 gate returns `SANITIZER_REPORT` into
`clean: true`, under the words "is the best safe choice".

WHY THE OLD TEST MISSED IT. `test_sanitizer_image_override_cannot_manufacture_a_pass` asserted on
hand-written dictionaries. It never pointed the override at an image, so it was testing the
claim's restatement rather than the claim.

THE FIX is not to remove the override — the not-run path needs it — but to stop treating a clean
result from an unpinned image as a pass. The claim is now true because the behaviour changed.
"""
from __future__ import annotations

import pytest

from cytune import apply as applymod
from cytune import certify, coherence, sanitize_gate
from cytune._vendor import theta

REF = theta.REFERENCE_ID

PINNED_CLEAN = {"ran": True, "clean": True, "verdict": "CLEAN", "config_id": REF,
                "image": sanitize_gate.DEFAULT_IMAGE, "image_overridden": False}
STUB_CLEAN = {"ran": True, "clean": True, "verdict": "CLEAN", "config_id": REF,
              "image": "localhost/attacker-stub:latest", "image_overridden": True}


def _cert(gate):
    ep = {str(REF): {"endpoint_ns": 100e6, "subs_ns": [100e6, 100.1e6, 99.9e6], "n_sub": 3}}
    return certify.build_certificate(
        name="k", winner_id=REF, reference_id=REF, endpoint=ep,
        oracle={"output_class": "int", "tolerance": {"rtol": 0.0, "atol": 0.0},
                "deterministic": True, "n_det_reps": 5, "golden_sha256": "a"},
        feasibility={"n_measured": 20, "n_infeasible": 0, "infeasible_fraction": 0.0,
                     "reasons": {}},
        route={"rule": "R1", "route": "honest-flat", "engine": None, "budget": 0, "why": "flat"},
        rig_mode="quiesced", rig_detail="q", budget={"probe": 17, "tuning": 0},
        sources={"table": "/t", "workspace": "/w"}, allow_fast_math=False, emitted_gate=gate)


def test_a_clean_result_from_an_unpinned_image_is_not_authoritative():
    assert sanitize_gate.is_authoritative(PINNED_CLEAN) is True
    assert sanitize_gate.is_authoritative(STUB_CLEAN) is False


def test_the_certificate_records_which_image_gated_it():
    """H6 aggravating factor: the `tune` certificate never recorded the image, so a reader could
    not tell a pinned gate from a stub one even in principle."""
    c = _cert(STUB_CLEAN)
    assert c["sanitizer_gate"]["image"] == "localhost/attacker-stub:latest"
    assert c["sanitizer_gate"]["image_overridden"] is True


def test_a_stub_image_cannot_buy_the_word_safe():
    """FAILURE PATH. The document must not call anything safe on the strength of an unpinned
    image's say-so."""
    c = _cert(STUB_CLEAN)
    assert c.get("sanitizer_gate_authoritative") is False
    assert "best safe config" not in c["summary"]
    assert "NOT the pinned image" in c["summary"]
    rendered = certify.render(c)
    assert "is the best safe choice" not in rendered
    # ... and the coherence gate agrees, so no future wording change can smuggle it back.
    assert c["safety_wording_earned"] is False
    coherence.assert_certificate_coherent(
        c, emitted_flags=c["emitted_config"]["gcc_flags"],
        gate_result=c["sanitizer_gate"], exit_code=c["exit_code"])


def test_the_pinned_image_still_earns_the_word_safe():
    """Control: without this the fix could be 'never say safe', which would be useless."""
    c = _cert(PINNED_CLEAN)
    assert "is the best safe choice" in certify.render(c)
    assert c.get("sanitizer_gate_authoritative") is not False


def test_apply_refuses_on_an_overridden_image():
    c = _cert(STUB_CLEAN)
    c["verdict"] = certify.IMPROVEMENT          # the most permissive state apply can meet
    with pytest.raises(applymod.ApplyRefused, match="NOT the pinned image"):
        applymod.check_applicable(c)


def test_i1_6_forbids_safe_wording_under_an_overridden_image():
    """A stub image cannot license the safety wording, and the licence FIELD is where that is
    enforced — so a document that claims the licence over an overridden gate is refused whatever
    its prose says."""
    c = _cert(STUB_CLEAN)
    assert c["safety_wording_earned"] is False
    c["safety_wording_earned"] = True
    with pytest.raises(coherence.IncoherentCertificate) as e:
        coherence.assert_certificate_coherent(
            c, emitted_flags=c["emitted_config"]["gcc_flags"],
            gate_result=c["sanitizer_gate"], exit_code=c["exit_code"])
    assert e.value.invariant == "I1.6"


def test_the_override_can_still_make_the_guarantee_weaker():
    """The override's legitimate use — exercising the NOT-RUN path — must keep working, and
    not-run must still not be a pass."""
    absent = {"ran": False, "clean": None, "verdict": "IMAGE_UNAVAILABLE",
              "image": "nope:latest", "image_overridden": True}
    assert sanitize_gate.is_authoritative(absent) is False
    assert sanitize_gate.rejects(absent) is False       # not-run is not a rejection either
    c = _cert(absent)
    assert c["sanitizer_gate_ran"] is False
    assert "did NOT run" in c["summary"]


def test_a_report_from_any_image_is_still_a_rejection():
    """An override must not be able to SUPPRESS a report either."""
    rep = {"ran": True, "clean": False, "verdict": "SANITIZER_REPORT", "config_id": REF,
           "tokens": ["AddressSanitizer"], "image": "stub", "image_overridden": True}
    assert sanitize_gate.rejects(rep) is True
    assert sanitize_gate.is_authoritative(rep) is False
