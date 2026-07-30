"""Certificate assembly + the honest-flat output as a first-class, tested path (roadmap §8.2)."""
import pytest

from cytune import certify, routing
from cytune._phasep import theta

ORACLE = {"output_class": "float", "tolerance": {"rtol": 1e-9, "atol": 1e-12},
          "deterministic": True, "n_det_reps": 5, "golden_sha256": "abc"}
FEAS = {"n_measured": 40, "n_infeasible": 6, "infeasible_fraction": 0.15,
        "reasons": {"oracle_mismatch": 5, "crash": 1}}
SOURCES = {"table": "/w/x/table.jsonl", "workspace": "/w"}
REF = theta.REFERENCE_ID


def _route(kind=routing.DOE, rule="R4"):
    return {"label": routing.LABEL, "route": kind, "rule": rule, "engine": "DOE", "budget": 16,
            "why": "because", "fallback_note": None, "feasibility_note": None}


def _cert(winner, endpoint, route=None, allow_fm=False):
    return certify.build_certificate(
        name="demo", winner_id=winner, reference_id=REF, endpoint=endpoint, oracle=ORACLE,
        feasibility=FEAS, route=route or _route(), rig_mode="quiesced",
        rig_detail="quiesced — verified", budget={"probe": 17, "tuning": 16},
        sources=SOURCES, allow_fast_math=allow_fm)


def _ep(cid, ns, feasible=True, subs=None):
    return {str(cid): {"feasible": feasible, "endpoint_ns": ns,
                       "subs_ns": subs if subs is not None else [ns], "cv": 0.001}}


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
    c = _cert(5, ep)
    assert c["verdict"] == "honest-flat"
    assert "reference" in c["summary"]


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
    c = _cert(5, ep)
    assert c["speedup"] > 1.02, "fixture must clear the OLD fixed floor to be meaningful"
    assert c["verdict"] == "honest-flat"
    assert c["measurement"]["emit_margin"]["margin"] > (c["speedup"] - 1.0)
    assert "bar this run could actually resolve" in c["summary"]


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
    c = _cert(5, ep)
    assert c["speedup"] > 1.0 + certify.TAU, "fixture must clear the old fixed floor to be meaningful"
    assert c["verdict"] == "honest-flat"
    assert c["measurement"]["endpoint_separation"]["separated"] is False
    assert c["measurement"]["emit_margin"]["margin"] > (c["speedup"] - 1.0)


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
        assert "P3-VALIDATED" in rendered
        assert "NOT validated on real code" in rendered


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


def test_fast_math_status_is_always_disclosed():
    off = certify.render(_cert(None, {}))
    assert "FAST-MATH" in off and "not opted in" in off
    on = certify.render(_cert(None, {}, allow_fm=True))
    assert "opted in" in on
