"""DOE planning + the correctness guarantees.

Integration here runs in REPLAY MODE against PILOT tables only — development data (demoted by
A-2b). The fleet, holdout H and the R anchors are off limits to cytune entirely (A-4d), and
test_cytune_firewall.py enforces that no test reaches for them.
"""
import json
import os

import pytest

from cytune import plan
from cytune._phasep import theta

import algorithms  # noqa: E402  (container-side; imports numpy)
import replay  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PILOT = os.path.join(REPO, "results", "pilot")
DEV_TABLES = ["pilot_A_01", "pilot_B_01", "pilot_C_01"]


def _table(kid):
    p = os.path.join(PILOT, kid, "table.jsonl")
    if not os.path.exists(p):
        pytest.skip(f"development table not present: {p}")
    return replay.load_frozen_table(p)


class Recorder:
    """Delegating proxy exposing exactly the SealedTable surface, recording paid query order.

    Only the whitelisted attributes are touched, so the §9.3 cheat guard stays armed underneath.
    """

    def __init__(self, sealed):
        self._s = sealed
        self.order = []

    def query(self, cid):
        if cid not in self._s.queried_ids:
            self.order.append(cid)
        return self._s.query(cid)

    n_configs = property(lambda self: self._s.n_configs)
    reference_id = property(lambda self: self._s.reference_id)
    reference_obs = property(lambda self: self._s.reference_obs)
    budget_used = property(lambda self: self._s.budget_used)
    queried_ids = property(lambda self: self._s.queried_ids)


def _plan_trajectory(tbl, budget, allow_fast_math=True):
    """Run the host-driven round structure against a frozen table."""
    ref = theta.REFERENCE_ID
    sp = plan.screen_plan(budget)
    feas, queried = {}, {ref}
    rfeas, rm = tbl[ref][0], tbl[ref][1]
    if rfeas and rm is not None:
        feas[ref] = rm
    for cid in sp["ids"]:
        queried.add(cid)
        f, m, _r = tbl[cid]
        if f and m is not None:
            feas[cid] = m
    wp = plan.walk_plan(feas, queried, budget - len(sp["ids"]), allow_fast_math=allow_fast_math)
    return sp["ids"] + wp["ids"], wp, sp["ids"], wp["ids"]


@pytest.mark.parametrize("kid", DEV_TABLES)
@pytest.mark.parametrize("budget", [8, 16, 32])
def test_walk_plan_reproduces_algorithms_doe_trajectory(kid, budget):
    """Given the SAME observations, the batched plan queries exactly what algorithms.doe queries.

    This is the claim plan.py's docstring makes, so it is pinned against the real algorithm rather
    than against a reimplementation of it.
    """
    tbl, _opt = _table(kid)
    rec = Recorder(replay.SealedTable(tbl))
    algorithms.doe(rec, budget, seed=0)
    mine, _wp, _s, _w = _plan_trajectory(tbl, budget, allow_fast_math=True)
    assert mine == rec.order, (
        f"{kid} B={budget}: batched plan diverged from algorithms.doe\n"
        f"  doe : {rec.order}\n  plan: {mine}")


@pytest.mark.parametrize("kid", DEV_TABLES)
def test_trajectory_is_deterministic(kid):
    tbl, _ = _table(kid)
    a, *_ = _plan_trajectory(tbl, 16)
    b, *_ = _plan_trajectory(tbl, 16)
    assert a == b


def test_screen_plan_respects_budget_and_skips_the_reference():
    for budget in (4, 8, 16, 32):
        sp = plan.screen_plan(budget)
        assert len(sp["ids"]) <= budget
        assert theta.REFERENCE_ID not in sp["ids"]
        assert len(set(sp["ids"])) == len(sp["ids"]), "no config is measured twice"


# ------------------------------------------------------- fast-math is opt-in
@pytest.mark.parametrize("kid", DEV_TABLES)
def test_walk_excludes_fast_math_unless_opted_in(kid):
    """The exclusion must actually bite — verified by the failure path, not just the happy one.

    Only the ADAPTIVE WALK is compared. The screen design is a fixed pre-registered set and is
    measured as specified whether or not the user opted in (frozen routing policy §4): measuring is
    not emitting, and dropping design points would break the design's D-optimality. Comparing full
    trajectories would therefore always show fast-math present and prove nothing.
    """
    tbl, _ = _table(kid)
    _all_in, _wp_in, _s_in, walk_in = _plan_trajectory(tbl, 32, allow_fast_math=True)
    _all_ex, wp_ex, _s_ex, walk_ex = _plan_trajectory(tbl, 32, allow_fast_math=False)
    assert not any(plan.is_fast_math(c) for c in walk_ex), \
        "a fast-math config entered the adaptive walk without --allow-fast-math"
    if any(plan.is_fast_math(c) for c in walk_in):
        assert walk_ex != walk_in, "exclusion changed nothing — the test would be vacuous"
        assert wp_ex["fit"]["fast_math_skipped"] > 0
    else:
        pytest.skip(f"{kid}: no fast-math config ranked into the walk, nothing to exclude")


def test_select_winner_excludes_fast_math_unless_opted_in():
    fm = next(c for c in range(theta.N_CONFIGS) if plan.is_fast_math(c))
    strict = theta.REFERENCE_ID
    feas = {fm: 100.0, strict: 500.0}      # fast-math is 5x faster and still must not be chosen
    w, d = plan.select_winner(feas, allow_fast_math=False)
    assert w == strict and d["n_excluded_fast_math"] == 1
    w2, _ = plan.select_winner(feas, allow_fast_math=True)
    assert w2 == fm, "opting in must actually make it selectable"


def test_select_winner_returns_none_when_nothing_is_feasible():
    assert plan.select_winner({}, allow_fast_math=True)[0] is None


def test_select_winner_only_ever_sees_feasible_configs():
    """Structural half of the guarantee: infeasible configs never enter the candidate mapping.

    feasible_medians is built from table rows with feasible=1 AND a screen median, so an
    oracle-failing config is not merely ranked last — it is absent.
    """
    feas = {theta.REFERENCE_ID: 10.0}
    w, _ = plan.select_winner(feas, allow_fast_math=True)
    assert w == theta.REFERENCE_ID


# ------------------------------------- endpoint confirmation (the second half)
def test_confirm_winner_accepts_a_config_that_passes_the_endpoint():
    ep = {"5": {"feasible": True, "endpoint_ns": 42.0}}
    final, rej = plan.confirm_winner(5, 288, ep)
    assert final == 5 and rej is None


def test_confirm_winner_rejects_a_config_that_fails_the_oracle_at_endpoint():
    """Screen-pass is not a licence: a config failing the endpoint oracle is never emitted."""
    ep = {"5": {"feasible": False, "reason": "oracle_mismatch", "endpoint_ns": None}}
    final, rej = plan.confirm_winner(5, 288, ep)
    assert final == 288, "must fall back to the reference"
    assert rej["rejected_config_id"] == 5 and rej["reason"] == "oracle_mismatch"


def test_confirm_winner_rejects_when_the_endpoint_is_missing_entirely():
    """A measurement that never happened is not evidence of correctness."""
    final, rej = plan.confirm_winner(5, 288, {})
    assert final == 288 and rej is not None


def test_confirm_winner_rejects_a_feasible_row_with_no_timing():
    final, rej = plan.confirm_winner(5, 288, {"5": {"feasible": True, "endpoint_ns": None}})
    assert final == 288 and rej is not None
