"""BO math TDD (PREREG §8.3) — hand-computed fixtures the bo-math-reviewer verifies.

EI closed form, σ-floor engagement, Laplace-smoothed P̂ bounds, feasible-only μ/σ, 1-in-4 interleave,
8-config init contents, conditional-fmffp validity of every proposal.
"""
import math
import numpy as np
import theta
import bo
import replay


def test_ei_improvement_hand():
    # y*=0, μ=-1, σ=1 -> z=1; EI = 1·Φ(1) + 1·φ(1) = 0.8413447 + 0.2419707 = 1.0833154
    got = float(bo.ei(0.0, -1.0, 1.0))
    assert abs(got - 1.0833154) < 1e-6, got


def test_ei_no_improvement_near_zero():
    # y* far below μ (minimization: incumbent already much better) -> EI ~ 0
    got = float(bo.ei(-5.0, 0.0, 1.0))
    assert 0.0 <= got < 1e-6, got


def test_sigma_floor_engages():
    # DISCRIMINATING (bo-math-reviewer V1): at μ≈y* (z≈0) the floor dominates. Floored
    # EI(0,0,σ→0) = SIGMA_FLOOR·φ(0) = 1e-3·0.3989423 = 3.98942e-4; WITHOUT the floor, raw σ=1e-9
    # gives 1e-9·φ(0) ≈ 3.99e-10 (1e6× smaller). So this fixture goes RED if the floor is removed.
    got = float(bo.ei(0.0, 0.0, 1e-9))
    assert abs(got - 1e-3 * (2 * math.pi) ** -0.5) < 1e-9, got
    assert got > 1e-5, got                       # ~4e-10 without the floor -> would fail
    # σ=0 input is treated as σ=SIGMA_FLOOR (floor applied before z/φ)
    assert float(bo.ei(0.0, -1.0, 0.0)) == float(bo.ei(0.0, -1.0, bo.SIGMA_FLOOR))


def test_ei_nonnegative_vectorized():
    mu = np.array([-1.0, 0.0, 2.0]); sigma = np.array([1.0, 1e-9, 0.5])
    out = bo.ei(0.0, mu, sigma)
    assert np.all(out >= 0.0) and out.shape == (3,)


def test_laplace_never_0_or_1():
    assert 0.0 < bo.laplace_pfeasible(0, 100) < bo.laplace_pfeasible(100, 100) < 1.0
    assert abs(bo.laplace_pfeasible(0, 100) - 1 / 102) < 1e-12
    assert abs(bo.laplace_pfeasible(100, 100) - 101 / 102) < 1e-12


def test_init_design_contents():
    tbl = {c: (True, 100.0, "ok") for c in range(theta.N_CONFIGS)}
    sealed = replay.SealedTable(tbl)
    d = bo._init_design(sealed, np.random.default_rng(0))
    assert len(d) == 8 and len(set(d)) == 8
    assert d[0] == theta.REFERENCE_ID
    assert d[1] == theta.id_of(bo.EXPERT) and d[2] == theta.id_of(bo.KNOWN_BAD)


def test_expert_knownbad_valid_theta_configs():
    # conditional-fmffp native: EXPERT/KNOWN_BAD are valid Θ points (id_of round-trips)
    assert theta.config_of(theta.id_of(bo.EXPERT)) == bo.EXPERT
    assert theta.config_of(theta.id_of(bo.KNOWN_BAD)) == bo.KNOWN_BAD


def test_feasible_only_musigma_excludes_infeasible():
    # POSITIVELY verify (bo-math-reviewer V3): μ/σ come from the FEASIBLE-only surrogate — adding an
    # infeasible observation must NOT change the RF regressor's μ/σ (a mis-imputation that gave the
    # infeasible row a finite penalty would change them). Then _propose runs without imputing it.
    from sklearn.ensemble import RandomForestRegressor
    Xall = theta.design_matrix(range(theta.N_CONFIGS))
    rf_state = 12345
    feas = {0: (True, 100.0), 2: (True, 50.0), 3: (True, 80.0), 5: (True, 60.0)}
    withinf = dict(feas); withinf[1] = (False, None)         # + one infeasible obs

    def musigma(q):
        f = [c for c, (ff, m) in q.items() if ff and m is not None]
        reg = RandomForestRegressor(random_state=rf_state, **bo.RF_PARAMS).fit(
            Xall[f], np.log(np.array([q[c][1] for c in f], float)))
        return bo._surrogate_mu_sigma(reg, Xall)

    mu_a, sg_a = musigma(feas); mu_b, sg_b = musigma(withinf)
    assert np.allclose(mu_a, mu_b) and np.allclose(sg_a, sg_b)   # infeasible obs excluded from μ/σ
    cand = bo._propose(withinf, Xall, best_ns=50.0, rng=np.random.default_rng(1), rf_state=rf_state)
    assert isinstance(cand, int) and cand not in withinf


def _fake_table(opt_cid=200, opt=40.0):
    tbl = {}
    for c in range(theta.N_CONFIGS):
        feas = (c % 5 != 0)
        tbl[c] = (feas, (90.0 + (c % 40) if feas else None), "ok" if feas else "oracle_mismatch")
    tbl[theta.REFERENCE_ID] = (True, 110.0, "ok")
    tbl[opt_cid] = (True, opt, "ok")
    return tbl


def test_bo_runs_and_respects_budget():
    tbl = _fake_table()
    for B in (8, 16, 32):
        r = replay.run_algorithm(bo.bo, tbl, B, 3)
        assert r["cheated"] is False and r["best_ns"] is not None
        assert r["budget_used"] <= B


def test_bo_interleave_schedule():
    # DISCRIMINATING (bo-math-reviewer V2): (a) the schedule fires at the 4th/8th/12th proposals,
    # (b) bo() ACTUALLY takes the random branch there (a build with the interleave deleted would call
    # _propose on every proposal). Spy _propose; assert it is called FEWER times than the proposals.
    randsteps = [s for s in range(8, 8 + 40) if bo._is_random_step(s)]
    assert randsteps[:3] == [11, 15, 19]                     # 4th/8th/12th proposals after 8-init
    tbl = _fake_table()
    calls = {"n": 0}
    orig = bo._propose
    bo._propose = lambda *a, **k: (calls.__setitem__("n", calls["n"] + 1), orig(*a, **k))[1]
    try:
        r = replay.run_algorithm(bo.bo, tbl, 32, 5)
    finally:
        bo._propose = orig
    n_while = r["budget_used"] - 7                            # 8-config init minus the free reference
    assert 0 < calls["n"] < n_while, (calls["n"], n_while)    # some proposals were random, not all


def test_bo_deterministic_same_seed():
    tbl = _fake_table()
    a = replay.run_algorithm(bo.bo, tbl, 16, 9)
    b = replay.run_algorithm(bo.bo, tbl, 16, 9)
    assert a["best_ns"] == b["best_ns"] and a["budget_used"] == b["budget_used"]


def test_e3_rf_random_state_reduced_at_the_consumer():
    """ERRATUM E3, named regression guard (bo-math-reviewer note N3, 2026-07-24).

    sklearn requires random_state ∈ [0, 2^32-1]; the §8.3/E2 pin derives a FULL uint64. The fix
    reduces mod 2^32 AT THE CONSUMER — the committed derivation (seeds.state_int /
    seed_fixtures.json) must stay untouched. Before this test the pinned branch (hash_k not None)
    was exercised by NO test in this file: bo()/motifbo() default hash_k=None, so a revert would
    have surfaced only as an unnamed sklearn crash inside test_run_study.
    """
    import seeds
    hash_k = seeds.kernel_hash("example_kernel_id")
    derived = seeds.state_int("bo-rf", hash_k, 3, 0)
    assert derived > 2 ** 32 - 1, "fixture no longer exercises the reduction"   # non-vacuity
    _rng, rf_state = bo._streams(0, hash_k, 0, 3)
    assert 0 <= rf_state <= 2 ** 32 - 1                    # the sklearn contract
    assert rf_state == derived % (2 ** 32)                 # reduction, not re-derivation
    # alg_id must still discriminate the RF stream after reduction (BO vs Motif+BO)
    assert bo._streams(0, hash_k, 0, 4)[1] != rf_state
    # deterministic across calls
    assert bo._streams(0, hash_k, 0, 3)[1] == rf_state
