"""Certificate assembly + the honest-flat output as a first-class, tested path (roadmap §8.2)."""
import pytest

from cytune import certify, routing, schema
from cytune._vendor import theta

ORACLE = {"output_class": "float", "tolerance": {"rtol": 1e-9, "atol": 1e-12},
          "deterministic": True, "n_det_reps": 5, "golden_sha256": "abc"}
FEAS = {"n_measured": 40, "n_infeasible": 6, "infeasible_fraction": 0.15,
        "reasons": {"oracle_mismatch": 5, "crash": 1}}
SOURCES = {"table": "/w/x/table.jsonl", "workspace": "/w"}
REF = theta.REFERENCE_ID


def _route(kind=routing.DOE, rule="R4"):
    return {"label": routing.LABEL, "route": kind, "rule": rule, "engine": "DOE", "budget": 16,
            "why": "because", "fallback_note": None, "feasibility_note": None}


def _cert(winner, endpoint, route=None, allow_fm=False, **kw):
    return certify.build_certificate(
        name="demo", winner_id=winner, reference_id=REF, endpoint=endpoint, oracle=ORACLE,
        feasibility=FEAS, route=route or _route(), rig_mode="quiesced",
        rig_detail="quiesced — verified", budget={"probe": 17, "tuning": 16},
        sources=SOURCES, allow_fast_math=allow_fm, **kw)


def _ep(cid, ns, feasible=True, subs=None):
    return {str(cid): {"feasible": feasible, "endpoint_ns": ns,
                       "subs_ns": subs if subs is not None else [ns], "cv": 0.001}}


def _refused(cid, ep):
    """The emit decision for `cid`, plus the certificate that results from refusing it.

    The decision moved into `certify.assess` so the CLI can settle what it will emit BEFORE the
    §1.4 gate runs on it (P2's fix). `build_certificate` now REFUSES a non-clearing candidate
    outright rather than assembling a document whose EMIT block claims the reference above the
    candidate's directives, so these tests go through the same two steps the CLI does: assess,
    then certify the demoted result.
    """
    a = certify.assess(ep.get(str(cid)), ep.get(str(REF)))
    assert not a["clears"], f"fixture must NOT clear the bar, but assess says it does: {a}"
    with pytest.raises(AssertionError, match="demoted to the reference"):
        _cert(cid, ep)
    cert = _cert(REF, ep, flat_observation={
        "config_id": cid, "endpoint_ratio_vs_reference": a["speedup"],
        "note": "measured but NOT recommended: " + a["why"]})
    assert cert["verdict"] == "honest-flat"
    return a, cert


# ------------------------------------------------------------------ verdicts
def test_real_speedup_is_certified_as_an_improvement():
    ep = {**_ep(REF, 100e6), **_ep(5, 50e6)}
    c = _cert(5, ep)
    assert c["verdict"] == "improvement"
    assert c["speedup"] == pytest.approx(2.0)
    assert "2.000x faster" in c["summary"] or "2.0" in c["summary"]


def test_marginal_gain_is_reported_as_flat_not_as_a_speedup():
    """1.5% over the reference is inside noise; calling it a win would be the product lying."""
    ep = {**_ep(REF, 100e6), **_ep(5, 98.5e6)}
    a, c = _refused(5, ep)
    assert a["speedup"] == pytest.approx(100 / 98.5)
    assert "does not exceed" in a["why"]
    assert "reference" in c["summary"]
    assert c["emitted_config"]["config_id"] == REF, "a flat run must emit the user's own baseline"


def test_a_rejected_winner_must_be_replaced_before_certification():
    """I2.3 — FAILURE PATH.

    When the endpoint tier or the sanitizer refuses the winner, the CLI falls back to the reference
    BEFORE certifying. If some future path forgets, the certificate would carry a `winner_rejection`
    describing config N while emitting config N — recording the refusal and then handing over the
    refused configuration anyway. The assertion existed; nothing had ever fired it, which by this
    project's own rule makes it a claim rather than a guarantee.
    """
    ep = {**_ep(REF, 100e6, subs=[100e6, 101e6, 99e6]),
          **_ep(5, 50e6, subs=[50e6, 51e6, 49e6])}
    rejection = {"rejected_config_id": 5, "reason": "oracle_mismatch",
                 "action": "fell back to the reference config"}
    with pytest.raises(AssertionError, match="replaced by the reference"):
        _cert(5, ep, winner_rejection=rejection)

    # The correct shape — demoted first — certifies as no-safe-improvement.
    c = _cert(REF, ep, winner_rejection=rejection)
    assert c["verdict"] == certify.NO_SAFE_IMPROVEMENT
    assert c["emitted_config"]["config_id"] == REF


# ------------------------------------------------- emit margin (D13/D15 generalised)
def test_emit_margin_scales_with_measured_endpoint_spread():
    """Noisy endpoints must raise the bar; clean endpoints fall back to the tau floor."""
    clean = certify.emit_margin({"subs_ns": [100.0, 100.1, 99.9]},
                                {"subs_ns": [200.0, 200.1, 199.9]})
    assert clean["margin"] == certify.TAU, "clean measurements should sit at the floor"
    noisy = certify.emit_margin({"subs_ns": [100.0, 120.0, 80.0]},
                                {"subs_ns": [200.0, 240.0, 160.0]})
    assert noisy["margin"] > certify.TAU, "noisy measurements must widen the bar"
    assert noisy["ci_term"] > certify.TAU


def test_emit_margin_falls_back_to_the_floor_and_says_so_without_enough_subs():
    m = certify.emit_margin({"subs_ns": [100.0]}, {"subs_ns": [200.0]})
    assert m["margin"] == certify.TAU and m["ci_term"] is None
    assert "floor only" in m["basis"]


def test_borderline_gain_inside_a_noisy_margin_is_refused():
    """The phantom-speedup case: a 10% apparent gain on measurements too noisy to resolve it.

    Selection over B configs manufactures gains of this size on a flat landscape (1.109x at B=32,
    s=0.05 in portable mode), so a fixed 1.02 floor would have certified it.
    """
    ep = {**_ep(REF, 100e6, subs=[100e6, 130e6, 70e6]),
          **_ep(5, 91e6, subs=[91e6, 118e6, 64e6])}
    a, c = _refused(5, ep)
    assert a["speedup"] > 1.02, "fixture must clear the OLD fixed floor to be meaningful"
    assert a["emit_margin"]["margin"] > (a["speedup"] - 1.0)
    assert "does not exceed" in a["why"]


def test_same_gain_on_clean_measurements_is_accepted():
    """The other side: identical 1.10x, but measured cleanly, must still certify."""
    ep = {**_ep(REF, 100e6, subs=[100e6, 100.1e6, 99.9e6]),
          **_ep(5, 91e6, subs=[91e6, 91.05e6, 90.95e6])}
    c = _cert(5, ep)
    assert c["verdict"] == "improvement"


def test_certificate_states_the_emit_margin():
    ep = {**_ep(REF, 100e6, subs=[100e6, 99e6, 101e6]),
          **_ep(5, 50e6, subs=[50e6, 49e6, 51e6])}
    r = certify.render(_cert(5, ep))
    assert "emit margin" in r
    assert "not a pre-registered study threshold" in r


def test_overlapping_endpoint_measurements_are_not_certified_as_a_speedup():
    """bo-math-reviewer F6: selecting the min over B configs biases the pick low on a flat
    landscape (phantom 1.064x at B=32, s=0.03). A 10% apparent gain whose repeated measurements
    OVERLAP the reference's must not be certified, even though it clears the 1.02 floor."""
    ep = {**_ep(REF, 100e6, subs=[100e6, 88e6, 105e6]),
          **_ep(5, 91e6, subs=[91e6, 86e6, 99e6])}
    a, _c = _refused(5, ep)
    assert a["speedup"] > 1.0 + certify.TAU, "fixture must clear the old fixed floor to be meaningful"
    assert a["separation"]["separated"] is False
    assert a["emit_margin"]["margin"] > (a["speedup"] - 1.0)


def test_separation_function_distinguishes_separated_from_overlapping():
    """Tested directly, because no end-to-end fixture can isolate it.

    The emit margin SUBSUMES separation in practice: both key off the same endpoint spread, and for
    n>=3 sub-measures a winner whose top sub-measure reaches the reference's bottom necessarily has
    a CV large enough to widen the margin past the gain. Separation is kept as a cheap rank-based
    second guard and a reported diagnostic — not as an independent verdict driver — and saying so
    here is better than writing a contrived fixture that pretends otherwise.
    """
    assert certify.endpoint_separation({"subs_ns": [10.0, 11.0]},
                                       {"subs_ns": [20.0, 21.0]})["separated"] is True
    assert certify.endpoint_separation({"subs_ns": [10.0, 21.0]},
                                       {"subs_ns": [20.0, 22.0]})["separated"] is False


def test_cleanly_separated_measurements_are_certified():
    """The other side of F6: real separation must still be reported as the improvement it is."""
    ep = {**_ep(REF, 100e6, subs=[100e6, 99e6, 101e6]),
          **_ep(5, 50e6, subs=[50e6, 49e6, 51e6])}
    c = _cert(5, ep)
    assert c["verdict"] == "improvement"
    assert c["measurement"]["endpoint_separation"]["separated"] is True


def test_separation_requires_actual_sub_measures():
    """No repeated measurements means no separation evidence — refuse rather than assume."""
    sep = certify.endpoint_separation({"subs_ns": []}, {"subs_ns": [1.0]})
    assert sep["separated"] is False and "missing" in sep["reason"]


def test_honest_flat_route_produces_a_first_class_output_not_an_error():
    ep = _ep(REF, 100e6)
    c = _cert(REF, ep, route=_route(routing.HONEST_FLAT, "R1"))
    assert c["verdict"] == "honest-flat"
    assert "common case" in c["summary"], "the flat answer should be stated as a real result"
    assert c["emitted_config"]["config_id"] == REF
    certify.render(c)  # must render, not raise


def test_flat_route_never_certifies_an_incidental_probe_winner():
    """Found by smoke run 2 (pilot_C_01): the router said R1 honest-flat ("any apparent speedup
    here is not distinguishable from noise") and the certificate then said IMPROVEMENT 1.031x —
    two contradictory claims in one document. On the flat route no search ran, so the best of the
    probe sample is a selection-biased minimum, not a tuning result. It is reported, never emitted.
    """
    ep = {**_ep(REF, 100e6, subs=[100e6, 99e6, 101e6]),
          **_ep(9, 97e6, subs=[97e6, 96e6, 98e6])}
    c = certify.build_certificate(
        name="demo", winner_id=REF, reference_id=REF, endpoint=ep, oracle=ORACLE,
        feasibility=FEAS, route=_route(routing.HONEST_FLAT, "R1"), rig_mode="quiesced",
        rig_detail="q", budget={}, sources=SOURCES, allow_fast_math=False,
        flat_observation={"config_id": 9, "endpoint_ratio_vs_reference": 1.031,
                          "note": "measured but NOT recommended"})
    assert c["verdict"] == "honest-flat"
    assert c["emitted_config"]["config_id"] == REF, "the flat route must emit the reference"
    r = certify.render(c)
    assert "OBSERVED BUT NOT RECOMMENDED" in r
    assert "1.0310x" in r, "the observation must still be reported with its real number"


def test_no_feasible_config_at_all_is_reported_honestly():
    c = _cert(None, {})
    assert c["verdict"] == "no-safe-improvement"
    assert c["emitted_config"] is None
    assert c["speedup"] is None
    certify.render(c)


# -------------------------------------------------------------- emitted flags
def test_ffp_contract_is_always_explicit():
    """GCC's default is `fast`; leaving it implicit silently permits FMA contraction."""
    for cid in (0, REF, 999, theta.N_CONFIGS - 1):
        assert "-ffp-contract=" in certify.gcc_flags(theta.config_of(cid))


def test_directive_header_covers_all_five_cython_directives():
    h = certify.directive_header(theta.config_of(REF))
    for d in ("boundscheck", "wraparound", "cdivision", "initializedcheck", "nonecheck"):
        assert d in h


def test_emitted_flags_round_trip_to_the_same_config():
    """What is printed must be what was measured — not a re-derivation that could drift."""
    for cid in (0, REF, 1234):
        cfg = theta.config_of(cid)
        dirs, opt, ffp, _ = theta.build_flags(cfg)
        assert certify.gcc_flags(cfg) == f"{opt} -ffp-contract={ffp}"
        assert certify.cython_x_flags(cfg) == dirs


# --------------------------------------------------------------- disclosures
def test_certificate_always_carries_the_routing_provenance_and_its_limit():
    for c in (_cert(None, {}), _cert(5, {**_ep(REF, 100e6), **_ep(5, 50e6)})):
        assert c["routing_label"] == routing.LABEL
        rendered = certify.render(c)
        # ONE routing sentence, and it must state the limit as well as the support (F14/F15).
        assert "engineering default" in rendered
        assert "NOT a validated per-cell router" in rendered
        assert "P3-VALIDATED" not in rendered


def test_certificate_reports_what_was_rejected_as_incorrect():
    c = _cert(5, {**_ep(REF, 100e6), **_ep(5, 50e6)})
    assert c["correctness"]["configs_rejected_infeasible"] == 6
    r = certify.render(c)
    assert "rejected as incorrect" in r and "oracle_mismatch" in r


def test_certificate_states_the_rig_mode_in_both_modes():
    q = certify.render(_cert(None, {}))
    assert "quiesced" in q
    from cytune import rig
    portable = rig.certificate_line(rig.PORTABLE, "no measure_wrap")
    assert "INDICATIVE" in portable and "Correctness guarantees are unaffected" in portable


def test_fma_contraction_is_disclosed_even_when_fast_math_was_declined():
    """fmffp has three levels; only (on,NA) is -ffast-math. (off,fast) permits FMA contraction,
    which still changes FP results — a user who declined fast-math must not be left believing FP
    semantics were untouched. Found in the first live smoke run, not by inspection."""
    contract_id = next(c for c in range(theta.N_CONFIGS)
                       if theta.config_of(c)[8] == ("off", "fast"))
    ep = {**_ep(REF, 100e6, subs=[100e6, 99e6, 101e6]),
          **_ep(contract_id, 50e6, subs=[50e6, 49e6, 51e6])}
    c = _cert(contract_id, ep, allow_fm=False)
    assert c["fast_math"]["emitted_config_uses_fast_math"] is False
    assert c["fp_semantics"]["fma_contraction_permitted"] is True
    r = certify.render(c)
    assert "FLOATING-POINT SEMANTICS" in r and "-ffp-contract=fast" in r
    assert "NOT -ffast-math" in r


def test_no_contraction_disclosure_when_contraction_is_off():
    ep = {**_ep(REF, 100e6, subs=[100e6, 99e6, 101e6])}
    c = _cert(REF, ep)
    assert c["fp_semantics"]["fma_contraction_permitted"] is False
    assert "FLOATING-POINT SEMANTICS" not in certify.render(c)


def test_fp_consent_status_is_always_disclosed():
    """Every certificate states the floating-point consent status, in both directions.

    Since F19 this covers BOTH semantics-changing axes, not just -ffast-math: the default is
    strict and the certificate says so, and an opt-in names the flag that produced it."""
    off = certify.render(_cert(None, {}))
    assert "FLOATING-POINT CONSENT: strict (default)" in off
    assert "neither -ffast-math nor FMA contraction" in off
    on = certify.render(_cert(None, {}, allow_fm=True))
    assert "FLOATING-POINT CONSENT: opted in via --allow-fast-math" in on


# ------------------------------------------------- U3/U4: state the magnitude, admit the cap
def test_separation_reports_how_thin_it_is():
    """U3. A 74 microsecond gap — 0.2%, a tenth of tau — read exactly like a 40% one, because
    separation was a bare yes/no."""
    thin = certify.endpoint_separation({"subs_ns": [99.9e6, 99.8e6, 99.7e6]},
                                       {"subs_ns": [100e6, 101e6, 102e6]})
    assert thin["separated"] is True
    assert thin["thin"] is True
    assert "THIN" in thin["reason"]
    assert thin["gap_relative"] < certify.TAU

    wide = certify.endpoint_separation({"subs_ns": [50e6, 50.1e6, 49.9e6]},
                                       {"subs_ns": [100e6, 101e6, 99e6]})
    assert wide["separated"] is True and wide["thin"] is False
    assert "THIN" not in wide["reason"] and "%" in wide["reason"]


def test_escalation_admits_when_it_ran_out_of_sub_measures():
    """U4. The protocol escalates while CV > 0.05 to at most 5, so it can END above target — and
    a run whose reference finished at CV 0.1097 printed the protocol sentence unchanged."""
    noisy = {"subs_ns": [36.8e6, 49.0e6, 49.2e6, 49.2e6, 42.5e6]}
    clean = {"subs_ns": [50e6, 50.1e6, 49.9e6]}
    st = certify.escalation_status(clean, noisy)
    assert st["target_met"] is False
    assert any(c["which"] == "reference" for c in st["capped"])
    assert "did NOT reach its noise target" in st["warning"]
    assert st["cv"]["reference"] > certify.CV_TARGET

    ok = certify.escalation_status(clean, clean)
    assert ok["target_met"] is True and ok["capped"] == [] and "warning" not in ok


def test_a_capped_escalation_is_printed_on_the_certificate():
    ep = {**_ep(REF, 100e6, subs=[36.8e6, 49.0e6, 49.2e6, 49.2e6, 42.5e6]),
          **_ep(5, 20e6, subs=[20e6, 20.1e6, 19.9e6])}
    r = certify.render(_cert(5, ep))
    assert "above the 0.05 target" in r
    assert "did NOT reach its noise target" in r


# ------------------------------------------------ 1.1: which engine produced this answer
def test_the_certificate_records_which_search_produced_the_answer():
    """Two releases of cytune can emit different configs for the same module because the SEARCH
    changed, not because the module did. A certificate that does not say which search ran leaves
    the reader unable to reproduce or compare it — and 1.1 changed the search.
    """
    search = {"engine": "probe-screen + predicted-best walk", "design_key": "probe-as-screen",
              "second_screen": False, "prior": "none (classical D-optimal probe design)"}
    c = _cert(REF, _ep(REF, 1000.0), search=search)
    assert c["search"]["design_key"] == "probe-as-screen"
    assert c["search"]["second_screen"] is False
    assert schema.validate(c) == []


def test_a_certificate_without_search_provenance_still_validates():
    """THE CONTROL, and a compatibility requirement. Every certificate archived under results/ was
    written before this field existed; making it required would retroactively invalidate them, and
    `test_every_archived_certificate_validates` would fail — correctly."""
    c = _cert(REF, _ep(REF, 1000.0))
    assert c["search"] is None
    assert schema.validate(c) == []
