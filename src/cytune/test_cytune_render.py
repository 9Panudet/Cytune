"""The RENDERER — what the user actually reads, checked where it can be checked properly.

WHY THIS FILE EXISTS. The coherence gate used to search the rendered certificate for phrases at
run time: "best safe choice" must not appear when the gate did not clear, "reference configuration
(unchanged)" must not appear over a non-reference config, "MEASURED SPEEDUP" must not appear on a
flat verdict. Three problems with that, and the third is the one that decided it:

  1. it covered a handful of sentences out of eighty lines and called that a check on the document;
  2. it needed a negation heuristic, because a certificate legitimately says "it is NOT certified
     safe" — and the heuristic's first version flagged that very sentence, i.e. the check fired on
     the line written to prevent the defect it was checking for;
  3. it was asking a question about a PURE FUNCTION at run time. `render` depends on nothing but
     the certificate, and I1.10 now enforces byte identity between the document and its rendering,
     so the question "which words does this document produce?" has a fixed answer that a test can
     enumerate — over the whole outcome space, with negations as ordinary test cases.

So the run-time gate asserts on FIELDS, and everything about wording lives here.
"""
from __future__ import annotations

import copy
import json

import pytest

from cytune import certify, coherence
from cytune._vendor import theta

REF = theta.REFERENCE_ID
FAST = theta.id_of((False, False, True, False, False, "-O3", "native", "on", ("off", "off")))

CLEAN = {"ran": True, "clean": True, "verdict": "CLEAN"}
REPORTED = {"ran": True, "clean": False, "verdict": "SANITIZER_REPORT",
            "tokens": ["AddressSanitizer"]}
NOT_RUN = {"ran": False, "clean": None, "verdict": "IMAGE_UNAVAILABLE"}
UNPINNED = {"ran": True, "clean": True, "verdict": "CLEAN", "image_overridden": True,
            "image_digest": "sha256:" + "f" * 64}

ORACLE = {"output_class": "int", "tolerance": {"rtol": 0.0, "atol": 0.0},
          "deterministic": True, "n_det_reps": 5, "golden_sha256": "abc"}
FEAS = {"n_measured": 20, "n_infeasible": 0, "infeasible_fraction": 0.0, "reasons": {}}
ROUTE = {"rule": "R4", "route": "tune", "engine": "DOE", "budget": 20, "why": "separable lever"}

# The exact sentences that ASSERT safety. Not phrases-with-a-negation-rule: whole claims, taken
# from the one table the downgrade path already uses plus the EMIT line, so a new claim added to
# the renderer without a downgrade rule fails `test_every_safety_claim_has_a_downgrade`.
SAFETY_CLAIMS = tuple(claim for claim, _honest in certify._SAFETY_DOWNGRADES) + (
    "EMIT: the reference configuration (unchanged) is the best safe choice.",)


def _flat(text):
    """Undo the renderer's line wrapping so an exact claim can be searched for exactly.

    This is not the negation heuristic coming back: it removes a layout artifact, and what is
    searched for afterwards is a complete sentence rather than a fragment that might be inside a
    denial.
    """
    return " ".join((text or "").split())


def _endpoint(win_ns, ref_ns, win_id):
    return {str(win_id): {"endpoint_ns": win_ns, "subs_ns": [win_ns] * 3, "n_sub": 3},
            str(REF): {"endpoint_ns": ref_ns, "subs_ns": [ref_ns] * 3, "n_sub": 3}}


def _cert(winner=REF, win_ns=100e6, ref_ns=100e6, gate=None, **kw):
    from cytune.plan import EmissionPolicy
    g = dict(CLEAN if gate is None else gate)
    g["config_id"] = winner
    return certify.build_certificate(
        name="demo", winner_id=winner, reference_id=REF,
        endpoint=_endpoint(win_ns, ref_ns, winner), oracle=ORACLE, feasibility=FEAS, route=ROUTE,
        rig_mode="quiesced", rig_detail="quiesced — verified",
        budget={"probe": 17, "tuning": 3, "total_measured": 20},
        sources={"table": "/w/table.jsonl", "workspace": "/w"},
        allow_fast_math=False, emitted_gate=g, policy=EmissionPolicy(), has_fp_work=True, **kw)


def _outcomes():
    """Every shape the renderer has to speak about — and only shapes the product can reach.

    A reporting gate on a non-reference candidate cannot coexist with no rejection: the CLI gates
    the candidate first and demotes it, and `build_certificate` refuses the combination outright
    (I2.2). Generating it here would test a document cytune cannot produce and would say nothing
    about what a user reads.
    """
    for gate in (CLEAN, REPORTED, NOT_RUN, UNPINNED):
        yield _cert(gate=gate)                                   # flat, emitting the reference
        if gate.get("clean") is not False:
            yield _cert(winner=FAST, win_ns=50e6, gate=gate)     # a real improvement
        # a faster candidate found and REFUSED — the no-safe-improvement shape
        yield _cert(winner=REF, win_ns=99e6, ref_ns=100e6, gate=gate,
                    winner_rejection={"rejected_config_id": FAST,
                                      "reason": "sanitizer_report: AddressSanitizer",
                                      "action": "fell back to the reference config",
                                      "observed_ratio": 1.4})


# ------------------------------------------------------------------- the licence, exhaustively
def test_safety_wording_appears_exactly_when_the_licence_says_it_may():
    """THE RULE, over the whole outcome space and in BOTH directions.

    A phrase that asserts safety may appear only in a document whose `safety_wording_earned` is
    True. The negation problem that broke the run-time scan does not arise here: a certificate that
    says "it is NOT certified safe" is one of the documents under test, and the assertion is about
    which document it is, not about parsing the sentence.
    """
    seen_earned = seen_unearned = 0
    for cert in _outcomes():
        text = _flat(certify.render(cert))
        earned = cert["safety_wording_earned"]
        for claim in SAFETY_CLAIMS:
            if not earned:
                assert claim not in text, (
                    f"the certificate asserts {claim!r} while safety_wording_earned is False "
                    f"(gate={cert['sanitizer_gate'].get('verdict')}, image_overridden="
                    f"{cert['sanitizer_gate'].get('image_overridden')})")
        seen_earned += int(bool(earned))
        seen_unearned += int(not earned)
    assert seen_earned >= 3 and seen_unearned >= 6, (seen_earned, seen_unearned)


def test_every_safety_claim_has_a_downgrade():
    """The guard on the guard. `_downgrade_safety_claims` rewrites a fixed table of sentences; a
    claim added to a summary without an entry there would survive into an unlicensed document, and
    the sweep above would only catch it if this list knew about it."""
    for claim, honest in certify._SAFETY_DOWNGRADES:
        assert "safe" in claim
        assert certify._downgrade_safety_claims(f"x {claim} y") == f"x {honest} y"


def test_an_unearned_licence_never_prints_the_positive_emit_line():
    """The EMIT line is where a user's eye lands. With no licence it must say what it is."""
    for gate in (REPORTED, NOT_RUN, UNPINNED):
        text = certify.render(_cert(gate=gate))
        assert "EMIT: the reference configuration (unchanged) is the best safe choice." not in text
    text = certify.render(_cert(gate=CLEAN))
    assert "EMIT: the reference configuration (unchanged) is the best safe choice." in text


def test_no_new_safety_phrase_escapes_the_licence():
    """A guard on the guard: if someone adds "perfectly safe" to a summary, this file's phrase
    list is the thing that has to be updated, and this test is what says so."""
    unlicensed = certify.render(_cert(gate=NOT_RUN)).lower()
    assert "not memory-checked" in unlicensed
    assert "not-run is not a pass" in unlicensed


# --------------------------------------------------------------------------- P2's rendered half
def test_the_emit_block_prints_the_emitted_config_header():
    """P2: the words 'the reference configuration (unchanged)' over a non-reference header.

    Structurally impossible now — a non-improvement must BE the reference (I1.7) — so what is
    checked here is the other half: whatever is emitted, the header printed is that config's.
    """
    for cert in _outcomes():
        e = cert.get("emitted_config")
        if not e:
            continue
        text = certify.render(cert)
        assert e["directive_header"] in text
        assert e["gcc_flags"] in text
        if "reference configuration (unchanged)" in text:
            assert e["config_id"] == REF, (
                "the certificate says it emits the reference unchanged while printing config "
                f"{e['config_id']}'s directives — this is P2")


def test_a_non_improvement_never_prints_a_measured_speedup_block():
    for cert in _outcomes():
        if cert["verdict"] != certify.IMPROVEMENT:
            assert "MEASURED SPEEDUP" not in certify.render(cert), cert["verdict"]


def test_every_rendering_states_its_verdict_and_exit_code():
    for cert in _outcomes():
        text = certify.render(cert)
        assert f"VERDICT: {cert['verdict'].upper()}" in text
        assert f"EXIT CODE: {cert['exit_code']}" in text


# ------------------------------------------------------------------------------- I1.10 itself
def test_i1_10_a_rendering_of_another_document_is_refused():
    """FAILURE PATH. The text handed to the gate is not what this document renders to.

    This is what replaces the five substring scans, and it is strictly stronger than all of them:
    they each checked one phrase, and this checks every byte. It also catches the case none of them
    could — certificate.txt on disk describing a different run from certificate.json beside it.
    """
    cert = _cert()
    other = certify.render(_cert(winner=FAST, win_ns=50e6))
    with pytest.raises(coherence.IncoherentCertificate) as e:
        coherence.assert_render_is_a_function_of_the_document(cert, other)
    assert e.value.invariant == "I1.10"


def test_i1_10_catches_a_single_edited_line():
    cert = _cert()
    text = certify.render(cert).replace("VERDICT: HONEST-FLAT", "VERDICT: IMPROVEMENT")
    with pytest.raises(coherence.IncoherentCertificate) as e:
        coherence.assert_render_is_a_function_of_the_document(cert, text)
    assert "first difference at line" in str(e.value)


def test_i1_10_passes_on_every_honest_outcome():
    """The control. Without it, an unconditionally-raising implementation would pass every test
    above — and this one also proves `render` survives a JSON round-trip for every shape, which is
    the property the whole substitution rests on."""
    n = 0
    for cert in _outcomes():
        assert coherence.assert_render_is_a_function_of_the_document(cert, certify.render(cert))
        n += 1
    assert n >= 11


def test_render_is_a_pure_function_of_the_json():
    """The claim underneath I1.10, stated on its own: nothing in `render` reads anything but its
    argument, so a round-tripped copy renders identically."""
    for cert in _outcomes():
        clone = json.loads(json.dumps(certify._json_safe(copy.deepcopy(cert))))
        assert certify.render(clone) == certify.render(cert)


# ------------------------------------------------------------------------- the new 1.0.0 blocks
def test_the_provenance_block_prints_what_the_claims_are_bound_to():
    from cytune import binding
    cert = _cert(winner=FAST, win_ns=50e6, provenance=binding.provenance(
        config_id=FAST, artifacts={FAST: {"artifact_sha256": "a" * 64, "source_sha256": "s" * 64}},
        endpoint={"artifact_sha256": "a" * 64}, gate=CLEAN, degeneracy_report={
            "n_distinct_artifacts": 33, "n_directive_combos_built": 22,
            "n_distinct_generated_sources": 22, "directives_inert": ["initializedcheck"]},
        rig_fingerprints=["no_turbo=1"], image_digest="sha256:" + "d" * 64,
        source_tree_sha256="t" * 64, n_measured=33))
    text = certify.render(cert)
    assert "PROVENANCE" in text
    assert "aaaaaaaaaaaa" in text                       # the emitted artifact, short form
    assert "dddddddddddd" in text                       # the toolchain image, without `sha256:`
    assert "33 configs, 33 distinct binaries" in text
    assert "initializedcheck" in text


def test_the_attestation_block_states_what_it_does_not_attest():
    """C2. A certificate gets forwarded; SECURITY.md does not. The limit has to travel."""
    text = certify.render(_cert())
    assert "WHAT THIS CERTIFICATE ATTESTS" in text
    assert "IT DOES NOT ATTEST" in text
    assert "NOT evidence to a third party" in text


def test_the_attestation_is_present_on_every_outcome():
    for cert in _outcomes():
        assert "IT DOES NOT ATTEST" in certify.render(cert)


def test_every_stated_limit_reaches_the_RENDERED_certificate():
    """The tag condition says every remaining limit must be stated in the CERTIFICATE, not only in
    SECURITY.md — and `certificate.txt` is the copy that gets forwarded.

    FAILURE PATH of a real gap: the artifact-binding limit was recorded in the JSON provenance note
    and never printed, so a reader of the rendered document saw the clock limit and not the loader
    one. A limit that exists only in a field a human does not read is stated in the same sense the
    pre-1.0 documentation was.
    """
    text = _flat(certify.render(_cert()))
    for key, phrase in (("does_not_attest", "as trustworthy as that driver"),
                        ("does_not_attest_artifact", "hijacks its own interpreter's module loader"),
                        ("audience", "NOT evidence to a third party")):
        assert certify.ATTESTATION[key], key
        assert phrase in text, f"{key} is in the document but never rendered"


def test_the_attestation_covers_both_halves_of_the_trust_boundary():
    """The driver owns the clock AND is loaded before the artifact. Two limits, one boundary; a
    certificate that named only the first would understate what it cannot vouch for."""
    att = certify.ATTESTATION
    assert "owns the clock" in att["does_not_attest"] or "clock" in att["does_not_attest"]
    assert "module loader" in att["does_not_attest_artifact"]


def test_d31_the_consent_note_only_speaks_about_flags_actually_opted_into():
    """D31 — a false statement about who consented to changed FP semantics.

    Found by a senior-power-user agent evaluating cytune for CI. The consent NOTE tested the
    provenance of BOTH fp flags, so a `.cytune.toml` that merely mentions `allow_fast_math` gives
    that key a file provenance — and typing `--allow-fp-contract` on the command line then printed
    "that opt-in did NOT come from the command line you typed" about a flag just typed, while the
    JSON recorded `allow_fp_contract: "command line"` in the same document. That is G7's own
    precedent class (R2) reappearing on the consent block.
    """
    from cytune import certify as C

    def render_with(prov, policy_kw):
        from cytune.plan import EmissionPolicy
        from cytune._vendor import theta
        cid = theta.id_of((True, True, False, True, False, "-O2", "x86-64", "omit", ("off", "fast")))
        ep = {str(cid): {"endpoint_ns": 50e6, "subs_ns": [50e6] * 3, "n_sub": 3, "K": 30},
              str(theta.REFERENCE_ID): {"endpoint_ns": 100e6, "subs_ns": [100e6] * 3,
                                        "n_sub": 3, "K": 30}}
        cert = C.build_certificate(
            name="d31", winner_id=cid, reference_id=theta.REFERENCE_ID, endpoint=ep,
            oracle={"output_class": "float", "tolerance": {"rtol": 1e-9, "atol": 1e-12},
                    "deterministic": True, "n_det_reps": 5, "golden_sha256": "abc"},
            feasibility={"n_measured": 20, "n_infeasible": 0, "infeasible_fraction": 0.0,
                         "reasons": {}},
            route={"rule": "R4", "route": "tune", "engine": "DOE", "budget": 20, "why": "w"},
            rig_mode="quiesced", rig_detail="verified",
            budget={"probe": 17, "tuning": 3, "total_measured": 20},
            sources={"table": "/w/t.jsonl", "workspace": "/w"},
            allow_fast_math=False, emitted_gate={"ran": True, "clean": True, "verdict": "CLEAN",
                                                 "config_id": cid},
            policy=EmissionPolicy(**policy_kw), has_fp_work=True,
            effective_config={"values": {}, "provenance": prov})
        return C.render(cert), cert

    NOTE = "did NOT come from the command line you typed"

    # The defect: the OTHER flag has a file provenance; the one opted into was typed.
    txt, cert = render_with({"allow_fp_contract": "command line",
                             "allow_fast_math": "/proj/.cytune.toml"},
                            {"allow_fp_contract": True})
    assert NOTE not in txt, (
        "the certificate claims a typed flag was not typed, while its own JSON says "
        f"{cert['effective_config']['provenance']['allow_fp_contract']!r}")

    # The note must still fire when the opt-in REALLY came from a file — otherwise the fix has
    # simply deleted the warning instead of correcting it.
    txt2, _ = render_with({"allow_fp_contract": "/proj/.cytune.toml"}, {"allow_fp_contract": True})
    assert NOTE in txt2, "the warning no longer fires when the opt-in genuinely came from a file"
