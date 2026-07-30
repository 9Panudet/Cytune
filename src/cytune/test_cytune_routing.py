"""Unit tests — the INTERIM routing policy transcription (routing.py vs the frozen document).

routing.py is only the executable form of results/prereg/CYTUNE_V0_ROUTING_INTERIM.md §2. These
tests assert the transcription: every rule fires where the document says it fires, the thresholds
are the inherited ones, and the boundaries land on the stated side.
"""
import pytest

from cytune import routing


def feat(delta=None, if_probe=None, na=False, feas_frac=1.0, n_feas=17, ref=True):
    return {"delta_probe": delta, "if_probe": if_probe, "if_probe_na": na,
            "feas_frac": feas_frac, "n_probe_feasible": n_feas, "n_probe_attempted": 17,
            "reference_feasible": ref}


# ------------------------------------------------------------------ R0: abort
def test_r0_aborts_when_reference_is_infeasible():
    r = routing.route(feat(delta=2.0, if_probe=0.1, ref=False))
    assert r["route"] == routing.ABORT and r["rule"] == "R0"
    assert "reference" in r["why"]


def test_r0_aborts_on_too_few_feasible_probe_rows():
    r = routing.route(feat(delta=2.0, if_probe=0.1, n_feas=3))
    assert r["route"] == routing.ABORT and r["rule"] == "R0"


def test_r0_does_not_abort_at_exactly_the_minimum_rows():
    r = routing.route(feat(delta=2.0, if_probe=0.1, n_feas=routing.MIN_FEASIBLE_PROBE_ROWS))
    assert r["route"] != routing.ABORT


# ------------------------------------------------------- R1: the honest-flat exit
def test_r1_honest_flat_at_and_below_the_noise_floor():
    for d in (1.0, 1.05, routing.FLAT_DELTA):
        r = routing.route(feat(delta=d, if_probe=0.9))
        assert r["route"] == routing.HONEST_FLAT, d
        assert r["budget"] == 0, "a flat landscape must not consume a tuning budget"


def test_r1_boundary_is_inclusive_and_the_next_step_up_tunes():
    assert routing.route(feat(delta=1.10, if_probe=0.0))["route"] == routing.HONEST_FLAT
    assert routing.route(feat(delta=1.1001, if_probe=0.0))["route"] == routing.DOE


def test_r1_beats_a_high_interaction_signal():
    """Flat wins over IF: below the noise floor, IF is noise/noise (A-1b)."""
    r = routing.route(feat(delta=1.05, if_probe=0.99))
    assert r["route"] == routing.HONEST_FLAT


# --------------------------------------------------------------- R2..R5: tuning
def test_r2_degenerate_probe_routes_conservatively_to_doe():
    r = routing.route(feat(delta=3.0, if_probe=None, na=True))
    assert r["rule"] == "R2" and r["engine"] == "DOE"


def test_r3_interaction_selects_bo_when_available():
    r = routing.route(feat(delta=2.0, if_probe=0.4), bo_available=True)
    assert r["rule"] == "R3" and r["engine"] == "BO"
    assert r["budget"] == routing.BUDGET_INTERACTION
    assert r["fallback_note"] is None


def test_r3_falls_back_to_doe_loudly_when_bo_is_absent():
    r = routing.route(feat(delta=2.0, if_probe=0.4), bo_available=False)
    assert r["rule"] == "R3" and r["engine"] == "DOE"
    assert r["budget"] == routing.BUDGET_INTERACTION, "fallback keeps the same budget"
    assert r["fallback_note"] and "not available" in r["fallback_note"], \
        "a silent fallback would misrepresent which engine produced the result"


def test_r4_separable_lever_routes_to_doe():
    r = routing.route(feat(delta=2.0, if_probe=0.1))
    assert r["rule"] == "R4" and r["engine"] == "DOE"


def test_r5_modest_spread_routes_to_doe():
    r = routing.route(feat(delta=1.3, if_probe=0.5))
    assert r["rule"] == "R5" and r["engine"] == "DOE"


@pytest.mark.parametrize("if_probe,expected", [(0.2499, "R4"), (0.25, "R3")])
def test_int_boundary_is_inclusive_on_the_interaction_side(if_probe, expected):
    assert routing.route(feat(delta=2.0, if_probe=if_probe))["rule"] == expected


@pytest.mark.parametrize("delta,expected", [(1.4999, "R5"), (1.5, "R4")])
def test_lever_boundary_is_inclusive_on_the_lever_side(delta, expected):
    assert routing.route(feat(delta=delta, if_probe=0.1))["rule"] == expected


# ------------------------------------------------------- feasibility modifier
def test_feasibility_modifier_raises_budget_and_says_so():
    r = routing.route(feat(delta=2.0, if_probe=0.1, feas_frac=0.5))
    assert r["budget"] == routing.BUDGET_DOE + routing.BUDGET_FEAS_BONUS
    assert r["feasibility_note"] and "50.0%" in r["feasibility_note"]


def test_feasibility_modifier_does_not_apply_to_the_flat_exit():
    """A flat kernel with an infeasible region still gets no tuning budget."""
    r = routing.route(feat(delta=1.02, if_probe=0.1, feas_frac=0.4))
    assert r["route"] == routing.HONEST_FLAT and r["budget"] == 0


def test_feasibility_modifier_never_changes_the_engine():
    a = routing.route(feat(delta=2.0, if_probe=0.4, feas_frac=1.0), bo_available=True)
    b = routing.route(feat(delta=2.0, if_probe=0.4, feas_frac=0.3), bo_available=True)
    assert a["engine"] == b["engine"] == "BO"


# ------------------------------------------------------------------ invariants
def test_thresholds_are_the_inherited_ones():
    """These are A-1b / A-2a values. A change here is a science change, not a code tweak."""
    assert routing.FLAT_DELTA == 1.10
    assert routing.LEVER_DELTA == 1.50
    assert routing.INT_IF == 0.25
    assert routing.FEAS_FRAC == 0.75


def test_every_route_carries_the_provenance_label_including_its_limit():
    for f in (feat(delta=1.0, if_probe=0.1), feat(delta=2.0, if_probe=0.4),
              feat(delta=2.0, if_probe=0.1, ref=False), feat(delta=1.3, if_probe=0.5)):
        assert routing.route(f)["label"] == routing.LABEL
        lab = routing.route(f)["label"]
        # The label must carry BOTH halves. "P3-VALIDATED" alone would overclaim — the study ran
        # on a synthetic benchmark and RQ-P2 acceptance on real code has not run. A user reading
        # only the first half would think the routing was validated for their code.
        assert "P3-VALIDATED" in lab
        assert "NOT validated on real code" in lab
