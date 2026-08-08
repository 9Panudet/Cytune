"""`cytune audit` — the deterministic risk-set gate (workstream C).

Every test here drives a FAILURE path: a defect that must be found, a directive that must be called
unsafe, an unchecked row that must not read as safety. The gate itself is injected, so the whole
decision layer is tested without a container; the live 5/5 detection run is recorded in
results/release/V1_RELEASE_REPORT.md.
"""
from __future__ import annotations

import pytest

from cytune import audit
from cytune._vendor import theta

REF = theta.REFERENCE_ID


def _gate(clean=True, verdict="CLEAN", tokens=(), note=None):
    return {"ran": True, "clean": clean, "verdict": verdict, "tokens": list(tokens), "note": note}


CLEAN_GATE = _gate()
REPORT_GATE = _gate(clean=False, verdict="SANITIZER_REPORT",
                    tokens=["AddressSanitizer", "buffer-overflow"])
RAISE_GATE = _gate(clean=None, verdict="RUN_FAIL_NO_TOKEN")
ABSENT_GATE = {"ran": False, "clean": None, "verdict": "IMAGE_UNAVAILABLE", "note": "no image"}


def _run(gate_for):
    """Drive audit.run with a gate function chosen per config name."""
    names = {cid: name for name, cid, _d, _w in audit.risk_configs()}
    return audit.run("/kdir", lambda _k, cid: gate_for(names[cid]))


# ------------------------------------------------------------------ the risk set itself
def test_the_risk_set_contains_the_d23_pair():
    """THE test for this feature. The per-directive singles cannot expose D23: with boundscheck off
    but wraparound on, a[-1] is rewritten to a[n-1] and is perfectly legal. Only the PAIR reads out
    of bounds. A risk set without it would miss the defect the whole product exists to catch."""
    pair = [c for n, c, _d, _w in audit.risk_configs() if n == "boundscheck_and_wraparound_off"]
    assert pair, "the risk set has no boundscheck+wraparound pair"
    bc, wa = theta.config_of(pair[0])[0], theta.config_of(pair[0])[1]
    assert bc is False and wa is False, "the pair row does not actually turn both off"


def test_every_single_directive_flip_is_from_the_reference():
    """Each single must differ from the reference in exactly one factor, or the audit is not
    measuring what it says it is."""
    ref = theta.REFERENCE
    for name, cid, directive, _why in audit.risk_configs():
        if directive is None or "+" in (directive or ""):
            continue
        cfg = theta.config_of(cid)
        differing = [i for i in range(9) if cfg[i] != ref[i]]
        assert len(differing) == 1, f"{name} differs from the reference in {len(differing)} factors"


def test_the_risk_set_is_deterministic_and_pre_registered():
    """Same list, same order, same ids, every call — the property that makes audit reproducible."""
    assert audit.risk_configs() == audit.risk_configs()
    assert [c for _n, c, _d, _w in audit.risk_configs()][0] == REF


def test_the_risk_set_includes_the_reference_so_a_baseline_defect_is_attributable():
    assert any(cid == REF for _n, cid, _d, _w in audit.risk_configs())


# ------------------------------------------------------------------------- outcome mapping
@pytest.mark.parametrize("gate,want", [
    (CLEAN_GATE, audit.OK),
    (REPORT_GATE, audit.REPORTED),
    (RAISE_GATE, audit.RAISED),
    (ABSENT_GATE, audit.NOT_RUN),
    ({"clean": None, "verdict": "BUILD_FAIL"}, audit.BUILD_FAIL),
    ({"clean": None, "verdict": "TIMEOUT"}, audit.NOT_RUN),
])
def test_outcome_mapping(gate, want):
    assert audit.outcome_of(gate) == want


def test_a_kernel_that_raises_is_not_reported_as_not_run():
    """RUN_FAIL_NO_TOKEN means the kernel threw, which is a finding about the user's code. Folding
    it into NOT RUN hid the most useful thing the audit learned about that directive."""
    assert audit.outcome_of(RAISE_GATE) == audit.RAISED
    assert audit.outcome_of(RAISE_GATE) != audit.NOT_RUN


# --------------------------------------------------------------------- directive verdicts
def test_the_pair_makes_both_of_its_directives_unsafe():
    """FAILURE PATH: the singles are clean and only the pair reports — exactly the D23 shape. Both
    boundscheck and wraparound must still come out UNSAFE, because disabling either one is what
    arms the bug once the other goes."""
    rows = _run(lambda n: REPORT_GATE if n == "boundscheck_and_wraparound_off" else CLEAN_GATE)
    rep = audit.build_report("k", rows)
    assert rep["directive_verdicts"]["boundscheck"] == audit.UNSAFE
    assert rep["directive_verdicts"]["wraparound"] == audit.UNSAFE
    assert rep["directive_verdicts"]["cdivision"] == audit.SAFE
    assert rep["verdict"] == audit.DEFECTS_FOUND
    assert rep["exit_code"] == audit.EXIT_DEFECTS_FOUND


def test_a_raised_row_makes_its_directive_unsafe():
    rows = _run(lambda n: RAISE_GATE if n == "wraparound_off" else CLEAN_GATE)
    rep = audit.build_report("k", rows)
    assert rep["directive_verdicts"]["wraparound"] == audit.UNSAFE


def test_an_unchecked_row_never_reads_as_safe():
    """FAILURE PATH: absence of evidence must not become evidence of safety. This is the not-run
    rule from G2/N1 applied to the audit."""
    rows = _run(lambda n: ABSENT_GATE if n == "cdivision_on" else CLEAN_GATE)
    rep = audit.build_report("k", rows)
    assert rep["directive_verdicts"]["cdivision"] == audit.UNKNOWN
    assert rep["verdict"] == audit.INCOMPLETE
    assert rep["exit_code"] == audit.EXIT_ERROR, "an audit that could not run must not exit 0"


def test_a_fully_clean_audit_exits_zero_and_claims_only_evidence():
    rows = _run(lambda _n: CLEAN_GATE)
    rep = audit.build_report("k", rows)
    assert rep["verdict"] == audit.CLEAN
    assert rep["exit_code"] == audit.EXIT_CLEAN
    assert all(v == audit.SAFE for v in rep["directive_verdicts"].values())
    assert "evidence, not proof" in rep["summary"] or "evidence, not proof" in rep["scope"]
    assert "proof of memory safety" not in rep["summary"]


def test_a_reporting_reference_is_attributed_to_the_kernel_not_to_tuning():
    """If the baseline itself reports, the honest message is 'this is your code', not 'tuning found
    something'."""
    rows = _run(lambda n: REPORT_GATE if n == "reference" else CLEAN_GATE)
    rep = audit.build_report("k", rows)
    assert rep.get("reference_reports") is True
    assert "as you wrote it" in rep["summary"]
    assert rep["exit_code"] == audit.EXIT_DEFECTS_FOUND


def test_a_defect_dominates_an_unchecked_row():
    """FAILURE PATH: with both a report and a not-run row, the headline must be the buffer
    overflow, not 'we could not check one thing'."""
    rows = _run(lambda n: REPORT_GATE if n == "all_checks_off_O3_native"
                else (ABSENT_GATE if n == "cdivision_on" else CLEAN_GATE))
    rep = audit.build_report("k", rows)
    assert rep["verdict"] == audit.DEFECTS_FOUND
    assert "MEMORY-SAFETY DEFECT" in rep["summary"]


# ------------------------------------------------------------------------------ rendering
def test_the_rendered_report_names_every_reporting_config():
    rows = _run(lambda n: REPORT_GATE if n == "boundscheck_and_wraparound_off" else CLEAN_GATE)
    out = audit.render(audit.build_report("k", rows))
    assert "REPORTED" in out
    assert "boundscheck_and_wraparound_off" in out
    assert "UNSAFE to disable" in out
    assert "DEFECTS-FOUND" in out


def test_the_rendered_report_states_its_scope_limit():
    """A clean audit must not read as a proof. N1 still applies and the report has to say so."""
    out = audit.render(audit.build_report("k", _run(lambda _n: CLEAN_GATE)))
    assert "evidence, not proof" in out
    assert "pre-registered" in out


def test_every_row_carries_its_config_id_and_directives():
    rows = _run(lambda _n: CLEAN_GATE)
    for r in rows:
        assert isinstance(r["config_id"], int)
        assert set(r["directives"]) == set(theta.FACTOR_NAMES)
        assert r["outcome"] in (audit.OK, audit.REPORTED, audit.RAISED, audit.NOT_RUN,
                                audit.BUILD_FAIL)


def test_exit_codes_do_not_collide_with_a_usage_error():
    assert audit.EXIT_CLEAN == 0 and audit.EXIT_ERROR == 1 and audit.EXIT_DEFECTS_FOUND == 3
    assert len({audit.EXIT_CLEAN, audit.EXIT_ERROR, audit.EXIT_DEFECTS_FOUND}) == 3


# --------------------------------------------------------------- C2: tune points at audit
def test_a_refused_run_tells_the_user_to_run_audit():
    """C2. `tune` gates two configs out of 1,728, so WHICH directive is unsafe depends on where the
    search landed. A run that refuses something must point at the tool that answers that
    deterministically — otherwise the user is left with 'something here is unsafe' and no next
    step."""
    from cytune import certify
    ep = {str(REF): {"endpoint_ns": 100e6, "subs_ns": [100e6, 101e6, 99e6], "n_sub": 3}}
    cert = certify.build_certificate(
        name="k", winner_id=REF, reference_id=REF, endpoint=ep,
        oracle={"output_class": "int", "tolerance": {"rtol": 0.0, "atol": 0.0},
                "deterministic": True, "n_det_reps": 5, "golden_sha256": "a"},
        feasibility={"n_measured": 20, "n_infeasible": 0, "infeasible_fraction": 0.0,
                     "reasons": {}},
        route={"rule": "R4", "route": "doe", "engine": "DOE", "budget": 16, "why": "lever"},
        rig_mode="quiesced", rig_detail="quiesced", budget={"probe": 17, "tuning": 3},
        sources={"table": "/t", "workspace": "/w"}, allow_fast_math=False,
        emitted_gate={"ran": True, "clean": True, "verdict": "CLEAN", "config_id": REF},
        winner_rejection={"rejected_config_id": 1326,
                          "reason": "sanitizer_report: AddressSanitizer, buffer-overflow",
                          "action": "fell back to the reference config",
                          "observed_ratio": 1.045})
    assert cert["verdict"] == certify.NO_SAFE_IMPROVEMENT
    assert "cytune audit" in cert["summary"], "a refusal must name the tool that diagnoses it"
    assert "cytune audit" in cert["memory_safety_finding"]["next_step"]
    assert "cytune audit" in certify.render(cert)


def test_the_audit_pointer_is_defined_once():
    """The finding block, the summary and the rendered certificate must not drift into three
    different recommendations — the D11/D22 lesson."""
    from cytune import certify
    assert certify.AUDIT_POINTER.count("cytune audit") == 1
    assert "deterministic" in certify.AUDIT_POINTER or "same answer" in certify.AUDIT_POINTER


# ------------------------------------------------- U1: the report must not contradict itself
def test_a_clean_row_is_never_also_labelled_not_checked():
    """U1, found by the novice-user agent. Every CLEAN row carried
    `>>> NOT CHECKED (CLEAN). Not-run is not a pass.` — so a report whose own verdict was "no
    sanitizer report in any of the 8 configurations" told the reader eight times that nothing had
    been checked.

    The existing tests all asserted that a string was PRESENT. None asserted that the document does
    not contradict itself, which is why a rendering bug in the feature that sells determinism
    survived 21 tests."""
    out = audit.render(audit.build_report("k", _run(lambda _n: CLEAN_GATE)))
    for line in out.splitlines():
        assert not ("CLEAN" in line and "NOT CHECKED" in line), \
            f"a row is marked clean and not-checked at once: {line!r}"
    assert "NOT CHECKED" not in out, "a fully clean audit must not say NOT CHECKED anywhere"
    assert "Not-run is not a pass" not in out


def test_not_checked_still_appears_when_a_row_really_was_not_checked():
    """The other direction — the warning must not have been deleted along with the bug."""
    out = audit.render(audit.build_report("k", _run(
        lambda n: ABSENT_GATE if n == "cdivision_on" else CLEAN_GATE)))
    assert "NOT CHECKED (IMAGE_UNAVAILABLE)" in out
    assert "Not-run is not a pass" in out


@pytest.mark.parametrize("outcome_gate,forbidden", [
    (CLEAN_GATE, ["NOT CHECKED", "did not compile", "raised in this configuration"]),
    (RAISE_GATE, ["NOT CHECKED", "did not compile"]),
    (REPORT_GATE, ["NOT CHECKED", "did not compile"]),
])
def test_each_outcome_prints_only_its_own_explanation(outcome_gate, forbidden):
    out = audit.render(audit.build_report("k", _run(lambda _n: outcome_gate)))
    for f in forbidden:
        assert f not in out, f"{f!r} appears for an outcome it does not describe"


def test_the_report_explains_which_directive_it_does_not_audit():
    """U14. `nonecheck` was absent from the 'IS IT SAFE TO DISABLE' table with no explanation —
    and it is the one directive a user may see emitted at a non-reference value."""
    rep = audit.build_report("k", _run(lambda _n: CLEAN_GATE))
    assert "nonecheck" in rep["directives_not_audited"]
    out = audit.render(rep)
    assert "nonecheck" in out
    assert "not audited" in out
    assert "already off at the reference" in out


def test_the_audited_and_unaudited_sets_do_not_overlap_and_cover_the_five():
    assert set(audit.DIRECTIVES) & set(audit.NOT_AUDITED) == set()
    assert set(audit.DIRECTIVES) | set(audit.NOT_AUDITED) == {
        "boundscheck", "wraparound", "cdivision", "initializedcheck", "nonecheck"}


def test_t8_the_raised_explanation_matches_the_row_it_annotates():
    """T8. Every RAISED row was annotated 'With boundscheck ON that is usually Cython catching a
    bad index' — including the checks-off corners, where boundscheck is OFF. A cdivision failure
    was explained by an unrelated directive."""
    bc_on = audit.render(audit.build_report("k", _run(
        lambda n: RAISE_GATE if n == "wraparound_off" else CLEAN_GATE)))
    assert "boundscheck is ON here" in bc_on

    bc_off = audit.render(audit.build_report("k", _run(
        lambda n: RAISE_GATE if n == "all_checks_off_O3_native" else CLEAN_GATE)))
    assert "boundscheck is OFF here" in bc_off
    assert "boundscheck is ON here" not in bc_off
