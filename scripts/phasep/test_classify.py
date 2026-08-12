"""classify() tests — measured A/B/C/boundary on constructed tables with known structure."""
import math
import numpy as np
import theta
import classify as C


def _table(fn, feasible=None):
    """Build {config_id: median_ns} = exp(fn(config)) over feasible configs (all, unless a set given)."""
    out = {}
    for cid in range(theta.N_CONFIGS):
        if feasible is not None and cid not in feasible:
            continue
        out[cid] = math.exp(fn(theta.config_of(cid)))
    return out


def test_flat_is_A():
    r = C.classify(_table(lambda c: 0.0))  # all equal
    assert r["measured_class"] == "A"
    assert r["interaction_fraction"] == 0.0
    assert abs(r["delta_all"] - 1.0) < 1e-9


def test_additive_big_lever_is_A():
    # large SEPARABLE main effects (boundscheck False -0.5, -O3 -0.4) — the real-code finding: flat class
    def fn(c):
        bc, wa, cd, ic, nc, opt, march, fun, fmffp = c
        return (-0.5 if bc is False else 0.0) + (-0.4 if opt == "-O3" else 0.0) \
               + (-0.2 if march == "native" else 0.0)
    r = C.classify(_table(fn))
    assert r["measured_class"] == "A", r
    assert r["interaction_fraction"] < 0.10
    assert r["delta_all"] > 1.5   # big lever, but separable ⇒ still A


def test_strong_interaction_is_B():
    # main effect + a strong boundscheck×opt interaction the main-effects model cannot capture
    def fn(c):
        bc, wa, cd, ic, nc, opt, march, fun, fmffp = c
        main = (-0.10 if bc is False else 0.0)
        inter = (-1.0 if (bc is False and opt == "-O3") else 0.0)
        return main + inter
    r = C.classify(_table(fn))
    assert r["interaction_fraction"] >= 0.25, r["interaction_fraction"]
    assert r["delta_all"] >= 1.5, r["delta_all"]
    assert r["measured_class"] == "B", r


def test_deceptive_greedy_stuck_is_C():
    # reference is a local optimum (all 12 neighbors worse), global optimum is the far 'expert' config
    expert = theta.id_of((False, False, True, False, False, "-O3", "native", "on", ("off", "fast")))
    ref = theta.REFERENCE_ID
    refN = set(theta.neighbors(ref))

    def fn(c):
        cid = theta.id_of(c)
        if cid == expert:
            return math.log(0.70)      # global min
        if cid in refN:
            return math.log(1.10)      # every ref-neighbor worse than ref ⇒ greedy halts at ref
        return math.log(1.00)
    r = C.classify(_table(fn))
    assert r["flags"]["is_C"], r
    assert r["greedy_gap"] >= 0.15, r["greedy_gap"]
    assert r["measured_class"] == "C", r


def test_if_floor_forces_A_A1b():
    # Amendment A-1b: a low-Δ kernel (Δ_all<1.10) with interaction structure is class A directly,
    # IF not evaluated (at Δ→1 IF=noise/noise). Tiny bc×opt interaction -> range ~1.02.
    def fn(c):
        bc, wa, cd, ic, nc, opt, march, fun, fmffp = c
        return (-0.02 if (bc is False and opt == "-O3") else 0.0)
    r = C.classify(_table(fn))
    assert r["delta_all"] < 1.10 and r["if_gated"] is True and r["measured_class"] == "A"


def test_reference_infeasible():
    feas = set(range(theta.N_CONFIGS)) - {theta.REFERENCE_ID}
    r = C.classify(_table(lambda c: 0.0, feasible=feas))
    assert r["measured_class"] is None and r["reason"] == "reference_infeasible"


def test_too_few_feasible():
    feas = {theta.REFERENCE_ID} | set(range(20))   # reference feasible, but < 32 total
    r = C.classify(_table(lambda c: 0.0, feasible=feas))
    assert r["measured_class"] is None and r["reason"] == "table_degenerate"


def test_cliff_island_singular_ok():
    # all fast_math=on rows infeasible (a feasibility-cliff) — constant fmffp columns must not crash IF
    feas = {c for c in range(theta.N_CONFIGS) if theta.config_of(c)[8][0] == "off"}
    r = C.classify(_table(lambda c: (-0.3 if c[0] is False else 0.0), feasible=feas))
    assert r["measured_class"] in ("A", "B", "C", "boundary")
    assert math.isfinite(r["interaction_fraction"])
