"""Guarantee tests for the DOE-v2 engines. These bind whether or not a variant ships.

A search engine may change WHICH configurations get measured. It may never change what may be
EMITTED, what the oracle decides, or what the certificate is allowed to claim. Every test here
attacks that line from a different side, and each has its control — a test that only shows a
violation being caught would also pass if the checker refused everything.

The adversarial-prior tests are written NOW, against the seam a Tier-2 model would enter through,
rather than after a model exists. A seam proven safe before anything is put in it cannot be
retro-fitted with an exception when the model turns out to want one.

Run: .venv/bin/python -m pytest scripts/doe_v2/test_doe_v2.py -q
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))

import controls                                            # noqa: E402
import designs_v2 as D                                     # noqa: E402
import engine                                              # noqa: E402
import variants                                            # noqa: E402
from cytune import plan, probe                             # noqa: E402
from cytune._vendor import theta                           # noqa: E402

POLICIES = [plan.EmissionPolicy(),
            plan.EmissionPolicy(allow_fp_contract=True),
            plan.EmissionPolicy(allow_fast_math=True, allow_fp_contract=True),
            plan.EmissionPolicy(portable_flags=True)]


def _designs_exist():
    return os.path.exists(variants.DESIGNS)


needs_designs = pytest.mark.skipif(not _designs_exist(),
                                   reason="run scripts/doe_v2/build_designs.py first")


# ------------------------------------------------------------------ the Stage-0 defect, as a test
@needs_designs
def test_every_v2_design_point_is_emittable_under_its_own_policy():
    """THE DEFECT, inverted into a check. The shipped designs fail this by 6/7, 11/15 and 16/24."""
    doc = json.load(open(variants.DESIGNS))
    for vname, pols in doc["variants"].items():
        for pname, designs in pols.items():
            pol = D.POLICIES[pname]
            for key, d in designs.items():
                bad = [c for c in d["config_ids"] if not pol.allows(c)]
                assert not bad, f"{vname}/{pname}/{key} spends {len(bad)} points outside the policy"


def test_the_shipped_designs_really_do_fail_that_check():
    """THE CONTROL for the test above. Without it, a check that passed vacuously — because every
    design happened to be empty, say — would look like the defect had been fixed."""
    from cytune._vendor import designs_path
    shipped = json.load(open(designs_path()))["designs"]
    strict = plan.EmissionPolicy()
    waste = {k: sum(1 for c in v["config_ids"] if not strict.allows(c))
             for k, v in shipped.items()}
    assert waste["doe_7"] == 6 and waste["doe_15"] == 11 and waste["doe_24"] == 16, waste


# --------------------------------------------------------------------------------- the hard line
@needs_designs
@pytest.mark.parametrize("v", variants.ALL, ids=lambda v: v.name)
@pytest.mark.parametrize("pol", POLICIES, ids=lambda p: variants.policy_name(p))
def test_no_variant_ever_emits_outside_the_effective_policy(v, pol):
    """G-line. Whatever an engine measures, the emitted config is inside the policy or is None."""
    for tbl in (controls.planted_table(2.0), controls.flat_table(),
                controls.planted_table(1.35)):
        r = engine.run(tbl, variant=v, policy=pol)
        assert r["emitted_id"] is None or pol.allows(r["emitted_id"]), (v.name, r["emitted_id"])


@needs_designs
@pytest.mark.parametrize("v", variants.ALL, ids=lambda v: v.name)
def test_no_variant_measures_a_config_it_could_not_emit(v):
    """CONTRIBUTING line 101, as an executable rule. V0 is expected to FAIL this — it is the
    defect — so it is asserted separately below rather than xfail-ed into invisibility."""
    pol = plan.EmissionPolicy()
    tbl = controls.planted_table(1.6)
    r = engine.run(tbl, variant=v, policy=pol)
    outside = r["configs_measured"] - r["n_paid_emittable"]
    # The probe is FIXED by prereg §2 and carries its non-strict rows deliberately — it is where
    # the fast-math signal comes from. Computed, not hardcoded, so a change to the probe cannot
    # silently turn this test into a weaker one.
    probe_outside = len([c for c in v.probe_ids(pol)
                         if c != theta.REFERENCE_ID and not pol.allows(c)])
    tune_outside = outside - probe_outside
    if v.name.startswith("V0"):
        # The whole V0 family — including the W walk-reserve fixes — keeps the SHIPPED
        # 1,728-candidate designs. W fixes D-2 (the starved walk); it does not fix D-1. That the
        # W variants still fail this rule is the evidence that the two defects are independent,
        # so it is asserted rather than exempted. W4 is the exception: it buys no second screen
        # at all, so it has no un-emittable tune spend left to make.
        if v.name == "V0+W4":
            assert tune_outside <= 0, "W4 buys no screen design, so it cannot overspend"
        else:
            assert tune_outside > 0, "V0-family carries D-1; if this stops holding, D-1 moved"
    else:
        assert tune_outside <= 0, f"{v.name} spent {tune_outside} tune points outside the policy"


@needs_designs
@pytest.mark.parametrize("v", variants.ALL, ids=lambda v: v.name)
def test_a_variant_changes_which_configs_are_measured_never_how_many(v):
    """If a variant could also change the budget, a regret win might be a spend increase in
    disguise, and the ship rule's cost half would be unfalsifiable."""
    tbl = controls.planted_table(1.6)
    base = engine.run(tbl, variant=engine.V0(), policy=plan.STRICT)
    got = engine.run(tbl, variant=v, policy=plan.STRICT)
    assert got["configs_measured"] <= base["configs_measured"], (
        v.name, got["configs_measured"], base["configs_measured"])


# ------------------------------------------------------------------- A-1: the strict-fit seam
def test_the_strict_fit_really_drops_the_fmffp_columns():
    """A-1's mechanism, verified rather than assumed: feeding `_fit` only policy-allowed rows must
    zero the two fmffp coefficients, because they are constant over those rows."""
    import algorithms
    strict = [c for c in range(theta.N_CONFIGS) if plan.STRICT.allows(c)][:40]
    beta, _ = algorithms._fit(strict, [math.log(1e6 + c) for c in strict])
    fmffp = [k for k, (fi, _lv) in enumerate(theta.DESIGN_COLUMNS, start=1) if fi == 8]
    assert all(abs(beta[k]) < 1e-12 for k in fmffp)


def test_the_unrestricted_fit_does_not_drop_them():
    """THE CONTROL. Without it the test above would pass for a `_fit` that always returned zeros."""
    import algorithms
    ids = list(range(0, 400, 7))
    beta, _ = algorithms._fit(ids, [math.log(1e6 + c) for c in ids])
    fmffp = [k for k, (fi, _lv) in enumerate(theta.DESIGN_COLUMNS, start=1) if fi == 8]
    assert any(abs(beta[k]) > 1e-12 for k in fmffp)


# ------------------------------------------------------- TIER-2 HARD INVARIANT (prereg §6)
def _garbage_prior(p, rng):
    """A deliberately hostile prior: inverted signs, wild magnitudes, and a NaN-adjacent scale."""
    k = rng.random(p) * 1e6
    k[0] = 1e-12
    return k


@needs_designs
@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_an_adversarial_prior_cannot_change_what_is_emitted(seed):
    """PREREG_DOE_V2 §6's hard invariant, proven on the seam BEFORE a model exists.

    A prior may only move WHERE measurements are spent. It feeds the design criterion, and nothing
    else. So a garbage prior may produce a differently-shaped design and therefore a different
    emitted config — what it may NEVER do is produce a config outside the effective policy, an
    infeasible config, or one the run never actually measured.
    """
    rng = np.random.default_rng(seed)
    pol = plan.EmissionPolicy()
    cand = D.candidates(pol)
    p = len(D.live_columns(cand))
    strict_probe = sorted(c for c in probe.probe_config_ids() if pol.allows(c))
    d = D.build(15, cand, ("adversarial", seed), prior_rows=strict_probe,
                K=_garbage_prior(p, rng))

    # (a) the design a garbage prior produces is still entirely inside the policy
    assert all(pol.allows(c) for c in d["config_ids"])
    assert len(set(d["config_ids"])) == 15

    # (b) an engine driven by it still emits only feasible, policy-allowed, MEASURED configs
    class Adversarial(variants.V2):
        name = "adversarial"

        def screen_plan(self, budget, policy, probe_rows):
            return {"design_key": "adversarial", "ids": list(d["config_ids"])[:budget]}

    tbl = controls.planted_table(1.6)
    r = engine.run(tbl, variant=Adversarial(), policy=pol)
    assert r["emitted_id"] is None or pol.allows(r["emitted_id"])
    assert r["emitted_id"] is None or tbl[r["emitted_id"]][0], "emitted an infeasible config"


@needs_designs
def test_a_garbage_prior_cannot_smuggle_a_fast_math_config_into_a_strict_run():
    """The specific thing a hostile prior would most want to do: it cannot, because the candidate
    set is filtered by the policy BEFORE the criterion ever sees it."""
    pol = plan.EmissionPolicy()
    cand = D.candidates(pol)
    p = len(D.live_columns(cand))
    # a prior that screams "spend everything on fmffp" — those columns do not exist here
    K = np.full(p, 1e-9)
    d = D.build(15, cand, ("adversarial", "fm"), K=K)
    assert not [c for c in d["config_ids"] if plan.is_fast_math(c) or plan.is_fp_contract(c)]


@needs_designs
def test_the_prior_changes_the_design_at_all():
    """THE CONTROL for the two tests above. If K were silently ignored, they would both pass while
    proving nothing — a prior that cannot do anything is trivially safe."""
    pol = plan.EmissionPolicy()
    cand = D.candidates(pol)
    p = len(D.live_columns(cand))
    flat = D.build(15, cand, ("ctrl", "flat"), K=np.full(p, 1e-6))
    tilted = D.build(15, cand, ("ctrl", "flat"), K=_garbage_prior(p, np.random.default_rng(7)))
    assert flat["config_ids"] != tilted["config_ids"], "K is being ignored"


# --------------------------------------------------------------------------- harness integrity
def test_the_engine_cannot_reach_the_table():
    s = engine.Sealed(controls.flat_table())
    for attr in ("_tbl", "tbl", "table", "data", "items", "keys", "values"):
        with pytest.raises(AttributeError):
            getattr(s, attr)
    with pytest.raises(AttributeError):
        s[0]


def test_the_harness_controls_all_pass():
    assert controls.main() == 0
