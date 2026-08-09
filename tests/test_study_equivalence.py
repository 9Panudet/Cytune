"""DOE planning + the correctness guarantees.

Integration here runs in REPLAY MODE against PILOT tables only — development data (demoted by
A-2b). The fleet, holdout H and the R anchors are off limits to cytune entirely (A-4d), and
test_cytune_firewall.py enforces that no test reaches for them.
"""
import json
import os

import pytest

from cytune import plan
from cytune._vendor import theta

from conftest import REPO, STUDY, load_study_module

# Loaded BY PATH, not by `import algorithms`. cytune/_vendor ships files with the same top-level
# names and owns the front of sys.path, so a plain import here resolves to cytune's own copy — and
# this test would then assert that cytune agrees with cytune. See tests/conftest.py.
algorithms = load_study_module("algorithms")
replay = load_study_module("replay")

if algorithms is None or replay is None:
    pytest.skip("study tree absent — equivalence cannot be checked here",
                allow_module_level=True)

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


PERMISSIVE = plan.EmissionPolicy(allow_fast_math=True, allow_fp_contract=True,
                                 portable_flags=False)


def _seed_observations(tbl, second_screen, budget):
    """The rows the fit is conditioned on before the walk, for each engine shape.

    `second_screen=True`  — the pre-1.1 shape: reference + the doe_{N_d} screen. This is the one
                            that can be compared against `algorithms.doe`, because that is the
                            observation set doe itself has.
    `second_screen=False` — the shipped 1.1 shape: reference + the PROBE, which the product has
                            already measured before routing. There is no second screen.
    """
    from cytune import probe as probemod
    ref = theta.REFERENCE_ID
    sp = plan.screen_plan(budget, second_screen=second_screen)
    seed_ids = sp["ids"] if second_screen else [c for c in probemod.probe_config_ids() if c != ref]
    feas, queried = {}, {ref}
    if tbl[ref][0] and tbl[ref][1] is not None:
        feas[ref] = tbl[ref][1]
    for cid in seed_ids:
        queried.add(cid)
        f, m, _r = tbl[cid]
        if f and m is not None:
            feas[cid] = m
    return sp, feas, queried


def _plan_trajectory(tbl, budget, policy=PERMISSIVE, second_screen=True):
    """Run the host-driven round structure against a frozen table.

    The equivalence claim is "given the same observations AND an emission policy that excludes
    nothing, the batched plan queries exactly what algorithms.doe queries". The study's DOE arm
    has no emission policy at all, so every exclusion cytune applies (fast-math since v0, FMA
    contraction since F19, non-baseline -march under --portable-flags) is a deliberate divergence
    and must be switched off to compare like with like."""
    sp, feas, queried = _seed_observations(tbl, second_screen, budget)
    wp = plan.walk_plan(feas, queried, budget - len(sp["ids"]), policy=policy)
    return sp["ids"] + wp["ids"], wp, sp["ids"], wp["ids"]


@pytest.mark.parametrize("kid", DEV_TABLES)
@pytest.mark.parametrize("budget", [8, 16, 32])
def test_walk_plan_reproduces_algorithms_doe_trajectory(kid, budget):
    """Given the SAME observations, the batched plan queries exactly what algorithms.doe queries.

    Driven with `second_screen=True`, which is the observation set `algorithms.doe` actually has.
    This is the DEFAULT engine. `--probe-as-screen` skips the second screen and is exercised by
    the tests below; it is experimental and off by default (DOE_V2_REPORT §10).
    """
    tbl, _opt = _table(kid)
    rec = Recorder(replay.SealedTable(tbl))
    algorithms.doe(rec, budget, seed=0)
    mine, _wp, _s, _w = _plan_trajectory(tbl, budget, policy=PERMISSIVE, second_screen=True)
    assert mine == rec.order, (
        f"{kid} B={budget}: batched plan diverged from algorithms.doe\n"
        f"  doe : {rec.order}\n  plan: {mine}")


@pytest.mark.parametrize("kid", DEV_TABLES)
@pytest.mark.parametrize("budget", [8, 16, 32])
def test_probe_as_screen_still_uses_the_studys_estimator_and_ranking(kid, budget):
    """What `--probe-as-screen` IS, stated precisely and pinned against the study's own functions.

    Dropping the second screen changes the DESIGN, not the METHOD. The fit is still
    `algorithms._fit` and the ranking is still `algorithms._pred_rank` — loaded here from the
    STUDY tree, not from cytune's vendored copy — so what the product does is the study's
    estimator applied to the probe instead of to a second D-optimal design.

    That is the honest form of the equivalence claim now, and asserting it here means the claim
    cannot quietly become false the way the old one did.
    """
    import math
    tbl, _opt = _table(kid)
    _sp, feas, queried = _seed_observations(tbl, second_screen=False, budget=budget)
    wp = plan.walk_plan(feas, queried, budget, policy=PERMISSIVE)

    obs = sorted(feas)
    beta, _ols = algorithms._fit(obs, [math.log(feas[c]) for c in obs])
    ranking, _pred = algorithms._pred_rank(beta)
    want = [c for c in ranking if c not in queried][:budget]
    assert wp["ids"] == want, (
        f"{kid} B={budget}: the walk is no longer the study's predicted-best ranking")


@pytest.mark.parametrize("kid", DEV_TABLES)
def test_probe_as_screen_buys_no_second_screen_and_spends_it_all_on_the_walk(kid):
    """`--probe-as-screen`, as a test. Experimental and OFF by default, so this drives it
    explicitly; `test_the_shipped_default_still_buys_a_screen` pins the default separately."""
    tbl, _ = _table(kid)
    sp = plan.screen_plan(16, second_screen=False)
    assert sp["ids"] == [] and sp["design_key"] == "probe-as-screen"
    _all_, _wp, screen, walk = _plan_trajectory(tbl, 16, second_screen=False)
    assert screen == [] and len(walk) == 16, "the whole tuning budget must reach the walk"


@pytest.mark.parametrize("kid", DEV_TABLES)
def test_trajectory_is_deterministic(kid):
    tbl, _ = _table(kid)
    for ss in (True, False):
        a, *_ = _plan_trajectory(tbl, 16, second_screen=ss)
        b, *_ = _plan_trajectory(tbl, 16, second_screen=ss)
        assert a == b


@pytest.mark.parametrize("second_screen", [True, False])
def test_screen_plan_respects_budget_and_skips_the_reference(second_screen):
    for budget in (4, 8, 16, 32):
        sp = plan.screen_plan(budget, second_screen=second_screen)
        assert len(sp["ids"]) <= budget
        assert theta.REFERENCE_ID not in sp["ids"]
        assert len(set(sp["ids"])) == len(sp["ids"]), "no config is measured twice"


@pytest.mark.parametrize("budget", [8, 16, 17, 20, 24, 25, 32, 40])
def test_the_screen_never_starves_the_adaptive_walk(budget):
    """DEFECT D-2, as a regression test.

    `N_d = min(24, B-1)` reserves at least one point for the walk. Before 1.1 the fallback to the
    24-point design plus a cap at `budget` spent that reserve, so EVERY budget in [17,24] ran with
    walk = 0. Measured cost on the frozen fleet: median regret 3.95% against 1.46%, worst-case
    516% against 46%, on 58 of 149 kernels — and zero of the nine real anchors, which is why the
    live dogfood could not have caught it.
    """
    sp = plan.screen_plan(budget, second_screen=True)
    assert len(sp["ids"]) <= budget - 1, (
        f"budget {budget}: the screen took {len(sp['ids'])} of {budget} and left the walk nothing")


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
    _all_in, _wp_in, _s_in, walk_in = _plan_trajectory(tbl, 32, policy=PERMISSIVE)
    _all_ex, wp_ex, _s_ex, walk_ex = _plan_trajectory(
        tbl, 32, policy=plan.EmissionPolicy(allow_fast_math=False, allow_fp_contract=True))
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


def test_the_study_modules_are_not_the_vendored_ones():
    """The check that keeps this whole file from being vacuous.

    `cytune/_vendor/` ships `algorithms.py` and puts itself at sys.path[0], so `import algorithms`
    in this directory returns CYTUNE'S copy. Every equivalence assertion above would then be
    comparing cytune against itself and would pass no matter how far the two drifted. This asserts
    the modules under test really came out of scripts/phasep.
    """
    for mod in (algorithms, replay):
        assert os.path.dirname(os.path.abspath(mod.__file__)) == STUDY, (
            f"{mod.__name__} was loaded from {mod.__file__}, not from the study tree — the "
            f"equivalence test is comparing cytune against itself")
    assert hasattr(algorithms, "doe"), \
        "the study's algorithms.doe is missing; the vendored trim must not have reached it"

    import cytune._vendor.algorithms as vendored
    assert os.path.abspath(vendored.__file__) != os.path.abspath(algorithms.__file__)
    assert not hasattr(vendored, "doe"), \
        "the vendored copy should be trimmed to what the product reaches (A3)"


def test_the_shipped_default_still_buys_a_screen():
    """The default is the SECOND-SCREEN engine, and that is a decision, not an accident.

    `--probe-as-screen` measured better offline and on the live anchors, and still failed its
    pre-registered ship rule (PREREG_DOE_V2 §5.1c, one anchor +1.37pp against a 1.00pp bound).
    Flipping this default is a shipping decision that needs the evidence in DOE_V2_REPORT §10, so
    it gets a test rather than being left to whoever edits plan.py next.
    """
    assert plan.SECOND_SCREEN is True
    sp = plan.screen_plan(16)
    assert sp["ids"], "the default engine must still buy its D-optimal screen"
    assert sp["design_key"] == "doe_15"
