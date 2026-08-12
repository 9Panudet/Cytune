"""Sealed-replay conformance (cheat-test, §9.3) + RS/DOE behavior on synthetic frozen tables."""
import numpy as np
import theta
import replay
import algorithms


def _fake_table(opt_cid=100, opt=50.0, infeasible_every=7):
    tbl = {}
    for c in range(theta.N_CONFIGS):
        feas = (c % infeasible_every != 0)
        m = 100.0 + (c % 50)
        tbl[c] = (feas, (m if feas else None), "ok" if feas else "oracle_mismatch")
    tbl[theta.REFERENCE_ID] = (True, 120.0, "ok")
    tbl[opt_cid] = (True, opt, "ok")
    return tbl


def test_cheat_caught_attr():
    def cheater(sealed, budget, seed):
        return sealed.true_optimum          # forbidden peek
    r = replay.run_algorithm(cheater, _fake_table(), 16, 0)
    assert r["cheated"] is True


def test_cheat_caught_subscript():
    def cheater(sealed, budget, seed):
        return sealed[0]                    # forbidden subscript
    r = replay.run_algorithm(cheater, _fake_table(), 16, 0)
    assert r["cheated"] is True


def test_honest_not_flagged():
    r = replay.run_algorithm(algorithms.rs, _fake_table(), 16, 1)
    assert r["cheated"] is False


def test_rs_determinism_same_seed():
    tbl = _fake_table()
    a = replay.run_algorithm(algorithms.rs, tbl, 32, 42)
    b = replay.run_algorithm(algorithms.rs, tbl, 32, 42)
    assert a["best_ns"] == b["best_ns"] and a["budget_used"] == b["budget_used"] == 32


def test_rs_finds_true_opt_full_budget():
    tbl = _fake_table(opt_cid=100, opt=50.0)
    r = replay.run_algorithm(algorithms.rs, tbl, 1727, 1)   # query all non-reference
    assert abs(r["best_ns"] - 50.0) < 1e-9 and r["regret"] == 0.0


def test_budget_respected():
    tbl = _fake_table()
    for B in (8, 16, 32, 64):
        r = replay.run_algorithm(algorithms.rs, tbl, B, 7)
        assert r["budget_used"] <= B


def test_doe_runs_and_respects_budget():
    tbl = _fake_table()
    for B in (8, 16, 32):
        r = replay.run_algorithm(algorithms.doe, tbl, B, None)
        assert r["cheated"] is False and r["best_ns"] is not None
        assert r["budget_used"] <= B


def test_reference_is_free_obs0():
    tbl = _fake_table()
    # an algorithm that queries nothing still 'has' the reference observation (obs 0) as best
    def only_ref(sealed, budget, seed):
        rid, feas, m, _ = sealed.reference_obs
        return m if feas else None
    r = replay.run_algorithm(only_ref, tbl, 8, 0)
    assert r["budget_used"] == 0 and abs(r["best_ns"] - 120.0) < 1e-9


# ------------------------------------------------------------ A-5 SECONDARY slice (PREREG §12)
def _fm_table():
    """Frozen table where the true optimum is a FAST-MATH config the product may not emit.

    This is the study-vs-product gap the E3 live audit measured: an arm that searches the full
    feasible space can win on the primary metric while returning something cytune must refuse.
    """
    tbl = {}
    for c in range(theta.N_CONFIGS):
        fm = theta.config_of(c)[8][0] == "on"
        tbl[c] = (True, 60.0 if fm else 100.0, "ok")
    tbl[theta.REFERENCE_ID] = (True, 120.0, "ok")
    return tbl


def test_emittable_ids_is_feasible_and_fast_math_off():
    tbl = _fm_table()
    em = replay.emittable_ids(tbl)
    assert em, "the emittable set must not be empty on an all-feasible table"
    assert all(theta.config_of(c)[8][0] == "off" for c in em)
    assert len(em) == theta.N_CONFIGS - 576, "576 of 1728 configs are fast-math"


def test_secondary_slice_separates_primary_win_from_emittable_win():
    """An arm that only ever queries fast-math configs looks perfect on the primary metric and
    has found NOTHING emittable — which is exactly what the slice must expose."""
    fm_ids = [c for c in range(theta.N_CONFIGS) if theta.config_of(c)[8][0] == "on"]

    def fm_only(sealed, budget, seed):
        best = None
        for cid in fm_ids[:budget]:
            feas, m, _r = sealed.query(cid)
            if feas and m is not None:
                best = m if best is None else min(best, m)
        return best

    r = replay.run_algorithm(fm_only, _fm_table(), 16, 0)
    assert r["regret"] == 0.0, "it did find the true optimum over the full feasible space"
    assert r["n_emittable_queried"] == 0
    assert r["emittable_budget_frac"] == 0.0
    # nothing emittable found -> floored at the reference, against the emittable optimum
    assert r["regret_emittable"] == (120.0 / 100.0 - 1.0)


def test_secondary_slice_rewards_an_arm_that_searches_emittable_space():
    off_ids = [c for c in range(theta.N_CONFIGS)
               if theta.config_of(c)[8][0] == "off" and c != theta.REFERENCE_ID]

    def strict_only(sealed, budget, seed):
        best = None
        for cid in off_ids[:budget]:
            feas, m, _r = sealed.query(cid)
            if feas and m is not None:
                best = m if best is None else min(best, m)
        return best

    r = replay.run_algorithm(strict_only, _fm_table(), 16, 0)
    assert r["emittable_budget_frac"] == 1.0
    assert r["regret_emittable"] == 0.0, "it found the best emittable config"
    assert r["regret"] > 0.0, "but it never reached the fast-math optimum — primary is worse"


def test_secondary_slice_does_not_perturb_the_primary_metric():
    """A-5c: additive only. Primary numbers must be identical with the slice present."""
    tbl = _fake_table()
    r = replay.run_algorithm(algorithms.doe, tbl, 16, None)
    expected_opt = min(m for f, m, _ in tbl.values() if f and m is not None)
    assert r["regret"] == replay.regret_at(r["best_ns"], expected_opt, tbl[theta.REFERENCE_ID][1])


def test_secondary_slice_survives_a_cheating_arm_without_masking_it():
    def cheater(sealed, budget, seed):
        return sealed.true_optimum
    r = replay.run_algorithm(cheater, _fake_table(), 16, 0)
    assert r["cheated"] is True and "regret_emittable" not in r


# ---------------------------------------------------------------------------------------------
# D23 / amendment A-9 — the §1.4 sanitizer overlay must remove configs from FEASIBLE SPACE, not
# merely penalize them. If it did not reach `load_frozen_table`, the study would optimize straight
# into an out-of-bounds read and `cytune` could emit it. That is a correctness-absolute violation,
# so it gets a control that fails loudly if the wiring is ever removed.
# ---------------------------------------------------------------------------------------------
def _table_file(tmp_path, opt_cid, opt_ns):
    """A committed-format table.jsonl whose global optimum sits at `opt_cid`."""
    import json
    p = tmp_path / "table.jsonl"
    with open(p, "w") as f:
        for c in range(theta.N_CONFIGS):
            m = opt_ns if c == opt_cid else 100.0 + (c % 50)
            f.write(json.dumps({"config_id": c, "feasible": 1,
                                "screen": {"median_ns": m}, "reason": "ok"}) + "\n")
    return str(p)


def test_overlay_removes_the_optimum_from_feasible_space(tmp_path):
    opt = 777
    path = _table_file(tmp_path, opt, 1.0)

    tbl, true_opt = replay.load_frozen_table(path)
    assert tbl[opt][0] is True and true_opt == 1.0        # without the overlay it IS the optimum

    tbl, true_opt = replay.load_frozen_table(path, overlay={opt})
    assert tbl[opt][0] is False, "overlaid config still feasible — the search could select it"
    assert tbl[opt][1] is None, "overlaid config still exposes a timing — it can still win"
    assert tbl[opt][2] == "sanitizer_oob"
    assert true_opt > 1.0, "true_opt still points at the overlaid config"


def test_no_algorithm_can_return_an_overlaid_config(tmp_path):
    """End-to-end: an arm that exhaustively sweeps must not come back with the overlaid optimum."""
    opt = 777
    path = _table_file(tmp_path, opt, 1.0)
    tbl, _ = replay.load_frozen_table(path, overlay={opt})

    def sweep(sealed, budget, seed):
        best = None
        for c in range(budget):
            feas, m, _r = sealed.query(c if c != 0 else opt)   # deliberately probes the bad config
            if feas and m is not None and (best is None or m < best):
                best = m
        return best

    r = replay.run_algorithm(sweep, tbl, 64, 0)
    assert r["cheated"] is False
    assert r["best_ns"] != 1.0, "an arm returned the sanitizer-rejected config"


def test_failure_path_absent_overlay_would_select_it(tmp_path):
    """Non-vacuity: on the SAME table with no overlay the sweep does return the bad config, so the
    assertions above discriminate rather than passing for unrelated reasons."""
    opt = 777
    path = _table_file(tmp_path, opt, 1.0)
    tbl, _ = replay.load_frozen_table(path)

    def sweep(sealed, budget, seed):
        best = None
        for c in range(budget):
            feas, m, _r = sealed.query(c if c != 0 else opt)
            if feas and m is not None and (best is None or m < best):
                best = m
        return best

    assert replay.run_algorithm(sweep, tbl, 64, 0)["best_ns"] == 1.0


# ---------------------------------------------------------------------------------------------
# Nested-budget prefix trajectories. The claim is EQUIVALENCE, not approximation, so it is pinned
# against independent per-budget runs rather than asserted in a docstring.
# ---------------------------------------------------------------------------------------------
_PREFIX_BUDGETS = (8, 16, 32, 64, 128)


def test_prefix_equals_independent_runs_for_stopping_condition_arms():
    """RS uses `budget` only as a stopping condition, so the first b paid queries of a B=128 run
    ARE the whole of a B=b run at the same seed. Every reported field must agree, not just regret."""
    tbl = _fake_table()
    pref = replay.run_algorithm_prefixes(algorithms.rs, tbl, _PREFIX_BUDGETS, seed=7)
    for b in _PREFIX_BUDGETS:
        indep = replay.run_algorithm(algorithms.rs, tbl, b, seed=7)
        for k in ("best_ns", "budget_used", "regret", "regret_nofloor", "best_emittable_ns",
                  "n_emittable_queried", "emittable_budget_frac", "regret_emittable"):
            assert pref[b][k] == indep[k], (b, k, pref[b][k], indep[k])


def test_prefix_regret_is_monotone_nonincreasing():
    """A larger budget observes a superset of the same trajectory, so regret can never rise."""
    pref = replay.run_algorithm_prefixes(algorithms.rs, _fake_table(), _PREFIX_BUDGETS, seed=3)
    r = [pref[b]["regret"] for b in _PREFIX_BUDGETS]
    assert all(a >= b for a, b in zip(r, r[1:])), r


def test_failure_path_doe_is_not_prefix_equivalent():
    """Non-vacuity, and the reason DOE is excluded from prefix reading: its design SIZE is
    min(24, B-1), so a smaller budget is a DIFFERENT design, not a truncation. If this ever starts
    passing, DOE's budget dependence has gone and the exclusion should be revisited."""
    tbl = _fake_table()
    pref = replay.run_algorithm_prefixes(algorithms.doe, tbl, _PREFIX_BUDGETS, seed=None)
    indep8 = replay.run_algorithm(algorithms.doe, tbl, 8, seed=None)
    assert pref[8]["best_ns"] != indep8["best_ns"] or \
        pref[8]["n_emittable_queried"] != indep8["n_emittable_queried"], \
        "DOE now looks prefix-equivalent — re-check algorithms.doe's Nd = min(24, B-1)"


def test_prefix_cheat_is_still_caught():
    def cheater(sealed, budget, seed):
        return sealed.true_optimum
    out = replay.run_algorithm_prefixes(cheater, _fake_table(), _PREFIX_BUDGETS, 0)
    assert all(out[b]["cheated"] is True for b in _PREFIX_BUDGETS)
