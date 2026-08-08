"""I1 — certificate coherence. Every test here drives a VIOLATION.

An invariant whose failure path has never fired is a claim, not an invariant — the project's own
rule, applied to the thing that enforces the project's own rule. So each test below builds a
certificate that lies in one specific way and asserts that `assert_certificate_coherent` refuses
it, plus a control asserting that a HONEST certificate passes (without which every test here would
pass on a function that raised unconditionally).

The four historical defects each get a test named after them: P1, P2, R2, P4.
"""
from __future__ import annotations

import copy

import pytest

from cytune import certify, coherence
from cytune._vendor import theta

REF = theta.REFERENCE_ID
FAST = theta.id_of((False, False, True, False, False, "-O3", "native", "on", ("off", "off")))
CONTRACT = theta.id_of((True, True, False, True, False, "-O2", "x86-64", "omit", ("off", "fast")))
FASTMATH = theta.id_of((True, True, False, True, False, "-O2", "x86-64", "omit", ("on", "NA")))

CLEAN_GATE = {"ran": True, "clean": True, "verdict": "CLEAN", "config_id": REF}


def _endpoint(win_ns, ref_ns, win_id, ref_id=REF):
    return {str(win_id): {"endpoint_ns": win_ns, "subs_ns": [win_ns] * 3, "n_sub": 3},
            str(ref_id): {"endpoint_ns": ref_ns, "subs_ns": [ref_ns] * 3, "n_sub": 3}}


ORACLE = {"output_class": "int", "tolerance": {"rtol": 0.0, "atol": 0.0},
          "deterministic": True, "n_det_reps": 5, "golden_sha256": "abc"}
FEAS = {"n_measured": 20, "n_infeasible": 0, "infeasible_fraction": 0.0, "reasons": {}}
ROUTE = {"rule": "R4", "route": "tune", "engine": "DOE", "budget": 20, "why": "separable lever"}


def _cert(winner=REF, endpoint=None, gate=None, policy=None, **kw):
    from cytune.plan import EmissionPolicy
    ep = endpoint if endpoint is not None else _endpoint(100e6, 100e6, winner)
    g = CLEAN_GATE if gate is None else gate
    if g is not None:
        g = {**g, "config_id": winner}
    return certify.build_certificate(
        name="demo", winner_id=winner, reference_id=REF, endpoint=ep, oracle=ORACLE,
        feasibility=FEAS, route=ROUTE, rig_mode="quiesced", rig_detail="quiesced — verified",
        budget={"probe": 17, "tuning": 3, "total_measured": 20},
        sources={"table": "/w/table.jsonl", "workspace": "/w"},
        allow_fast_math=False, emitted_gate=g,
        policy=policy or EmissionPolicy(), has_fp_work=True, **kw)


def _check(cert):
    """Structured only. The rendered text is no longer an input to the coherence gate: `render` is
    a pure function of the document (enforced at run time by I1.10), so what the user reads is
    settled in `test_cytune_render.py` instead of by searching prose for phrases."""
    return coherence.assert_certificate_coherent(
        cert,
        emitted_flags=(cert.get("emitted_config") or {}).get("gcc_flags"),
        gate_result=cert.get("sanitizer_gate"), exit_code=cert.get("exit_code"))


# ------------------------------------------------------------------- the control (not vacuous)
def test_an_honest_certificate_passes():
    """Without this, every other test here would pass against a function that always raised."""
    assert _check(_cert()) is True


def test_an_honest_improvement_certificate_passes():
    from cytune.plan import EmissionPolicy
    c = _cert(winner=FAST, endpoint=_endpoint(50e6, 100e6, FAST),
              gate={"ran": True, "clean": True, "verdict": "CLEAN"},
              policy=EmissionPolicy())
    assert c["verdict"] == certify.IMPROVEMENT, c["summary"]
    assert _check(c) is True


# --------------------------------------------------------------------------------- P2
def test_p2_emit_block_must_match_the_emitted_config():
    """P2, verbatim: the certificate said 'EMIT: the reference configuration (unchanged)' and
    printed boundscheck=False, wraparound=False underneath it.

    Checked on the FIELD the renderer prints, recomputed from the config id. The rendered-text half
    of P2 is `test_cytune_render.py::test_the_emit_block_prints_the_emitted_config_header`, which
    can assert on the whole document instead of one phrase of it."""
    c = _cert()
    c["emitted_config"]["directive_header"] = certify.directive_header(theta.config_of(FAST))
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant == "I1.2"


def test_p2_a_tampered_flag_field_is_caught():
    c = _cert()
    c["emitted_config"]["gcc_flags"] = "-O3 -march=native -ffp-contract=off"
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant == "I1.2"


def test_the_emitted_flags_handed_to_the_caller_must_match():
    c = _cert()
    with pytest.raises(coherence.IncoherentCertificate):
        coherence.assert_certificate_coherent(c, emitted_flags="-O3 -march=native",
                                              gate_result=c["sanitizer_gate"],
                                              exit_code=c["exit_code"])


# --------------------------------------------------------------------------------- R2
def test_r2_fp_fields_must_agree_with_the_emitted_flag_string():
    """R2: --allow-fast-math emitted -ffp-contract=fast while the JSON field said contraction was
    not permitted. The field is the half a script reads."""
    from cytune.plan import EmissionPolicy
    c = _cert(winner=FASTMATH, endpoint=_endpoint(50e6, 100e6, FASTMATH),
              policy=EmissionPolicy(allow_fast_math=True))
    assert "-ffp-contract=fast" in c["emitted_config"]["gcc_flags"]
    assert _check(c) is True                      # honest today
    c["fp_semantics"]["fma_contraction_permitted"] = False      # the R2 lie
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant == "I1.3"


def test_r2_fast_math_must_record_that_contraction_came_with_it():
    from cytune.plan import EmissionPolicy
    c = _cert(winner=FASTMATH, endpoint=_endpoint(50e6, 100e6, FASTMATH),
              policy=EmissionPolicy(allow_fast_math=True))
    c["fp_semantics"]["fma_contraction_implied_by_fast_math"] = False
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant == "I1.3"


def test_g4_an_fp_config_beyond_the_policy_is_incoherent():
    """G4 says every FP-semantics change is opt-in. A certificate emitting one under a strict
    policy is a consent violation, and the invariant must catch it even if selection somehow
    produced it."""
    from cytune.plan import EmissionPolicy
    c = _cert(winner=FASTMATH, endpoint=_endpoint(50e6, 100e6, FASTMATH),
              policy=EmissionPolicy(allow_fast_math=True))
    c["emission_policy"] = EmissionPolicy().as_dict()          # strict, but fast-math emitted
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant == "I1.3"


def test_contract_only_config_needs_its_own_optin():
    from cytune.plan import EmissionPolicy
    c = _cert(winner=CONTRACT, endpoint=_endpoint(50e6, 100e6, CONTRACT),
              policy=EmissionPolicy(allow_fp_contract=True))
    assert _check(c) is True
    c["emission_policy"] = EmissionPolicy().as_dict()
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant == "I1.3"


# --------------------------------------------------------------------------------- P1
def test_p1_safety_wording_cannot_survive_a_reporting_gate():
    """P1: a sanitizer-reporting configuration was emitted under the words 'the best safe choice'.

    The document is built with a CLEAN gate — so it licenses the safety wording — and the gate is
    then replaced by a reporting one. That is P1's exact shape: a claim of safety standing over a
    verdict that withdrew it, and the licence field is where the two now have to meet."""
    c = _cert()
    assert c["safety_wording_earned"] is True
    c["sanitizer_gate"] = {"ran": True, "clean": False, "verdict": "SANITIZER_REPORT",
                           "config_id": REF, "tokens": ["AddressSanitizer"]}
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant == "I1.6"


def test_i1_6_a_clean_gate_from_an_unpinned_image_does_not_license_safety(): 
    """H6: the licence is CLEAN *from the pinned image*, and a retagged stub is not that."""
    c = _cert(gate={"ran": True, "clean": True, "verdict": "CLEAN",
                    "image_overridden": True, "image_digest": "sha256:" + "f" * 64})
    assert c["safety_wording_earned"] is False
    c["safety_wording_earned"] = True
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant == "I1.6"


def test_i1_6_a_certificate_with_no_licence_field_is_refused():
    """A missing field is a question that was never answered, not a default."""
    c = _cert()
    del c["safety_wording_earned"]
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant == "I1.6"


def test_an_improvement_verdict_cannot_have_a_reporting_gate():
    c = _cert(winner=FAST, endpoint=_endpoint(50e6, 100e6, FAST))
    c["verdict"] = certify.IMPROVEMENT
    c["exit_code"] = certify.EXIT_IMPROVEMENT
    c["sanitizer_gate"] = {"ran": True, "clean": False, "verdict": "SANITIZER_REPORT",
                           "config_id": FAST, "tokens": ["AddressSanitizer"]}
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant in ("I1.6", "I1.8")


# --------------------------------------------------------------------------------- F5
def test_f5_the_gate_must_describe_the_emitted_config():
    """F5: after a sanitizer fallback the gate result described the REJECTED config, so the
    emitted one's status was never stated at all."""
    c = _cert()
    c["sanitizer_gate"] = {**CLEAN_GATE, "config_id": FAST}     # a DIFFERENT config
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant == "I1.4"


# --------------------------------------------------------------------------------- P4
def test_p4_a_not_run_gate_must_qualify_the_verdict_line():
    """P4: a not-run gate left the summary unqualified, so a reader who stopped at the summary saw
    a clean verdict for a recommendation nobody memory-checked."""
    c = _cert(gate={"ran": False, "clean": None, "verdict": "IMAGE_UNAVAILABLE"})
    assert _check(c) is True                                    # cytune adds the NOTE itself
    c["summary"] = "No improvement found. Best safe config = the reference."
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant == "I1.5"


def test_p4_not_run_must_also_set_the_machine_readable_flag():
    c = _cert(gate={"ran": False, "clean": None, "verdict": "IMAGE_UNAVAILABLE"})
    c["sanitizer_gate_ran"] = True
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant == "I1.5"


# --------------------------------------------------------------------------------- R3 / exit codes
@pytest.mark.parametrize("verdict,code", [
    (certify.IMPROVEMENT, certify.EXIT_IMPROVEMENT),
    (certify.HONEST_FLAT, certify.EXIT_HONEST_FLAT),
    (certify.NO_SAFE_IMPROVEMENT, certify.EXIT_NO_SAFE_IMPROVEMENT),
])
def test_verdict_and_exit_code_must_agree(verdict, code):
    c = _cert()
    c["verdict"] = verdict
    c["exit_code"] = code + 1                                   # any wrong code
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant == "I1.1"


def test_a_non_improvement_must_emit_the_reference():
    """Anything cytune is not recommending as an improvement must be the user\'s own baseline.

    This used to be ambiguous about which invariant caught it, because the rendered text tripped
    I1.2 first. With the text out of the gate it is I1.7 and nothing else, which is what the
    registry claims."""
    c = _cert(winner=FAST, endpoint=_endpoint(50e6, 100e6, FAST))
    c["verdict"] = certify.HONEST_FLAT
    c["exit_code"] = certify.EXIT_HONEST_FLAT
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant == "I1.7"


def test_an_impossible_config_id_is_rejected():
    c = _cert()
    c["emitted_config"]["config_id"] = 99999
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant == "I1.2"


# ------------------------------------------------------------------------------ B2: property test
def _outcomes():
    """The cross-product of run shapes the invariant must hold over."""
    from cytune.plan import EmissionPolicy
    gates = [
        {"ran": True, "clean": True, "verdict": "CLEAN"},
        {"ran": True, "clean": False, "verdict": "SANITIZER_REPORT", "tokens": ["AddressSanitizer"]},
        {"ran": False, "clean": None, "verdict": "IMAGE_UNAVAILABLE"},
    ]
    policies = [
        EmissionPolicy(),
        EmissionPolicy(allow_fast_math=True),
        EmissionPolicy(allow_fp_contract=True),
        EmissionPolicy(allow_fast_math=True, allow_fp_contract=True, portable_flags=True),
    ]
    winners = [REF, FAST, CONTRACT, FASTMATH]
    speeds = [(100e6, 100e6), (50e6, 100e6), (99e6, 100e6)]
    for g in gates:
        for p in policies:
            for w in winners:
                for win_ns, ref_ns in speeds:
                    yield g, p, w, win_ns, ref_ns


def _as_the_cli_would(winner, endpoint, gate, policy):
    """Reproduce the CLI's decision order, so the sweep exercises the real composition.

    Two steps, in the order cli.tune does them and for the reasons it does them:
      1. a candidate the SANITIZER reports on is refused and replaced by the reference (G2) —
         gated first, because the gate is a bug finder and not only an emission filter;
      2. a candidate that survives but does not clear the emit margin is demoted (P2's fix), so
         the §1.4 gate and the EMIT block both describe the config actually emitted.

    A sweep that skipped these would test states the product cannot reach; one that ignored them
    would only re-find the two assertions in `build_certificate`.
    """
    ep, rejection = endpoint, None
    if winner != REF:
        if gate.get("clean") is False:
            rejection = {"rejected_config_id": winner,
                         "reason": f"sanitizer_report: {', '.join(gate.get('tokens') or [])}",
                         "action": "fell back to the reference config",
                         "gate": "roadmap §1.4 / PREREG §301", "observed_ratio": None}
            winner = REF
        elif not certify.assess(ep.get(str(winner)), ep.get(str(REF)))["clears"]:
            winner = REF
    return _cert(winner=winner, endpoint=ep, gate=copy.deepcopy(gate), policy=policy,
                 winner_rejection=rejection)


def test_b2_the_invariant_holds_over_every_generated_run_outcome():
    """B2 — property test over the outcome space rather than a handful of examples.

    For every (gate state x policy x winner x speed), the composition the CLI actually performs
    must produce a document the coherence gate accepts. This sweep is what found that
    `build_certificate` would still assemble a P2-shaped certificate when handed a non-clearing
    winner; that path now raises at its source.
    """
    n = 0
    for gate, policy, winner, win_ns, ref_ns in _outcomes():
        # The CLI never certifies a config the policy forbids; mirror that precondition rather
        # than testing a state the product cannot reach.
        if policy.excluded_reason(winner):
            continue
        _check(_as_the_cli_would(winner, _endpoint(win_ns, ref_ns, winner), gate, policy))
        n += 1
    assert n >= 30, f"the property sweep only exercised {n} combinations"


def test_b2_a_non_clearing_winner_is_refused_at_its_source():
    """The hole the sweep found: without the demotion, the certificate builder must REFUSE rather
    than emit 'the reference configuration (unchanged)' above config 1506's directives."""
    ep = _endpoint(99e6, 100e6, FAST)          # a ~1.01x gain: below any plausible margin
    with pytest.raises(AssertionError, match="demoted to the reference"):
        _cert(winner=FAST, endpoint=ep)


def test_b2_the_emitted_config_is_always_inside_the_effective_policy():
    """The other half of B2: whatever comes out must be something the policy allowed."""
    for gate, policy, winner, win_ns, ref_ns in _outcomes():
        if policy.excluded_reason(winner):
            continue
        c = _as_the_cli_would(winner, _endpoint(win_ns, ref_ns, winner), gate, policy)
        emitted = (c.get("emitted_config") or {}).get("config_id")
        if emitted is None:
            continue
        assert policy.excluded_reason(emitted) is None, (
            f"emitted config {emitted} is forbidden by the run's own policy {policy.as_dict()}")


def test_i1_9_a_certificate_violating_its_own_schema_is_refused():
    """I1.9 — FAILURE PATH. cytune publishes a schema and tells consumers to build against it.
    A document that breaks it must never leave the process, however coherent its prose is."""
    c = _cert()
    c["exit_code"] = "2"                      # was int; a typed consumer breaks on this
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant in ("I1.1", "I1.9")

    c2 = _cert()
    del c2["emission_policy"]                 # a required field, removed
    with pytest.raises(coherence.IncoherentCertificate) as e2:
        _check(c2)
    assert e2.value.invariant == "I1.9"


def test_i1_9_passes_on_a_real_certificate():
    """Control: the schema check must not be firing on cytune's own honest output."""
    from cytune import schema
    assert schema.validate(_cert()) == []


def test_i1_3_catches_a_config_outside_portable_flags():
    """FAILURE PATH found by scrutinising the invariant against its own claim.

    I1.3 said "neither exceeds the policy" but only re-derived the two FP axes, so a
    `--portable-flags` run could emit `-march=native` and pass. The check now asks the
    EmissionPolicy itself, so every axis is covered — including ones added later."""
    from cytune.plan import EmissionPolicy
    NATIVE = theta.id_of((True, True, False, True, False, "-O2", "native", "omit", ("off", "off")))
    c = _cert(winner=NATIVE, endpoint=_endpoint(50e6, 100e6, NATIVE),
              policy=EmissionPolicy(portable_flags=True))
    assert theta.config_of(NATIVE)[6] == "native"
    with pytest.raises(coherence.IncoherentCertificate) as e:
        _check(c)
    assert e.value.invariant == "I1.3"
    assert "non_baseline_march" in str(e.value)


def test_i1_3_allows_native_when_portable_flags_was_not_requested():
    """Control: the check must bite only when the user actually asked for portability."""
    from cytune.plan import EmissionPolicy
    NATIVE = theta.id_of((True, True, False, True, False, "-O2", "native", "omit", ("off", "off")))
    c = _cert(winner=NATIVE, endpoint=_endpoint(50e6, 100e6, NATIVE), policy=EmissionPolicy())
    assert _check(c) is True
