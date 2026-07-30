"""Generator v2 TDD (A-2d/g/h/i): diversity mandate, roster balance, anti-clone math, knife-edges."""
import json
import math
import os
import tempfile
import generate_v2 as g2


def test_registry_diversity_mandate():
    for regime in ("FLAT_FM", "MID", "LEVER_SEP", "INT"):
        names = [t[0] for t in g2.REGISTRY[regime]]
        assert len(names) >= 6 and len(set(names)) == len(names), regime
    assert len(g2.REGISTRY["NULL"]) >= 3       # descriptive stratum: diversity desirable, not mandated


def test_roster_feas_balance_15_15():
    for regime in ("FLAT_FM", "MID", "LEVER_SEP", "INT"):
        r = g2.roster(regime, 30)
        traps = [t for (_k, _n, _p, t, _i) in r]
        assert len(r) == 30
        assert sum(1 for t in traps if t is not None) == 15, (regime, traps)  # rider R1 exact 15/15
        used = {}
        for (_k, name, _p, _t, _i) in r:
            used[name] = used.get(name, 0) + 1
        assert len(used) >= 6 and max(used.values()) <= 5, (regime, used)     # 6 templates × ≤5


def test_roster_never_traps_trap_incompatible_templates():
    r = g2.roster("INT", 30)
    for (_k, name, _p, trap, _i) in r:
        if name == "int_revsum":               # its gate IS wraparound — trap would collide
            assert trap is None
    fm = g2.roster("FLAT_FM", 30)
    assert all(t in (None, "trap_wrap") for (_k, _n, _p, t, _i) in fm)  # fm_cliff never inside FM+


def test_anti_clone_rejects_pilot_A_clones():
    # measured pilot values (a2_reclassify_v2.json): A_01 vs A_02 are clones under ε=0.05
    a01 = g2.property_vector(1.2059, 1.2055, 0.476, 0.25, 0.1623)
    a02 = g2.property_vector(1.2048, 1.2048, 0.478, 0.25, 0.1469)
    ok, d = g2.anti_clone_check(a02, [a01])
    assert not ok and all(x < g2.EPS_CLONE for x in d)


def test_anti_clone_accepts_distinct_and_exact_eps():
    csr = g2.property_vector(2.1538, 2.0156, 0.092, 0.0, 0.0)
    pava = g2.property_vector(1.0956, 1.0956, 0.407, 0.0, 0.0)
    ok, _ = g2.anti_clone_check(pava, [csr])
    assert ok
    # rider R2: a component EXACTLY at 0.05 counts as distinct (strict <)
    base = g2.property_vector(1.20, 1.20, 0.40, 0.0, 0.0)
    edge = (base[0] + g2.EPS_CLONE, base[1], base[2], base[3], base[4])
    ok, _ = g2.anti_clone_check(edge, [base])
    assert ok


def test_boundary_flags_a_family_case():
    flags = g2.boundary_flags(delta_strict=1.205, if_strict=0.478, fm_ratio=1.0,
                              n_infeasible=432, n_total=1728)
    assert flags == ["infeas_frac~0.25"]       # the pinned A-family knife-edge, and only it
    assert g2.boundary_flags(1.105, None, 1.0, 0, 1728) == ["delta_strict~1.10"]


def test_emit_kernel_files_and_spec():
    with tempfile.TemporaryDirectory() as td:
        for regime in g2.REGISTRY:
            kid, name, params, trap, gi = g2.roster(regime, 2)[0]
            kdir = g2.emit_kernel(td, regime, kid, name, params, trap, gi)
            for f in ("kernel.pyx", "driver.py", "spec.json"):
                assert os.path.exists(os.path.join(kdir, f)), (regime, f)
            spec = json.load(open(os.path.join(kdir, "spec.json")))
            assert spec["template"] == name and spec["generator"] == "v2 (A-2d)"
            assert "membership_rule" in spec               # rider R3 recorded per kernel
            # campaign.finalize's contract (the fleet kernel #1 KeyError): intended_class REQUIRED
            assert spec["intended_class"] == g2.REGIME_INTENDED[regime]
            drv = open(os.path.join(kdir, "driver.py")).read()
            assert "REPS = " in drv and "OUTPUT_CLASS" in drv   # calibrate knob + oracle class
            if trap == "fm_cliff":
                assert "run_cliff" in open(os.path.join(kdir, "kernel.pyx")).read()


def test_float_dt_driver_matches_pyx_dtype():
    # D8: a float-dt FLAT_FM instance must emit float32 arrays (float64 into float[::1] raises
    # "Buffer dtype mismatch" on every call -> MEASURE_FAIL at calibrate)
    with tempfile.TemporaryDirectory() as td:
        kdir = g2.emit_kernel(td, "FLAT_FM", "k_f32", "fm_sum", {"dt": "float", "n": 4096},
                              None, 0)
        drv = open(os.path.join(kdir, "driver.py")).read()
        pyx = open(os.path.join(kdir, "kernel.pyx")).read()
        assert "float32" in drv and "float[::1]" in pyx
        kdir = g2.emit_kernel(td, "FLAT_FM", "k_f64", "fm_sum", {"dt": "double", "n": 4096},
                              None, 0)
        drv = open(os.path.join(kdir, "driver.py")).read()
        assert "float64" in drv and "float32" not in drv


def test_property_vector_log_scale():
    p = g2.property_vector(2.0, 1.5, 0.3, 0.5, 0.2)
    assert abs(p[0] - math.log(2.0)) < 1e-12 and abs(p[1] - math.log(1.5)) < 1e-12
