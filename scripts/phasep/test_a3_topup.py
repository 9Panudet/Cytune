"""Amendment A-3 wave-2 top-up TDD — cell counting (F2), cap accounting, allocation, wave
labels, W2 registry discipline. No measurement; container-free."""
import json
import os
import tempfile

import generate_v2 as g2
import run_fleet as rf


def _ledger(tmp, entries):
    p = os.path.join(tmp, "fleet_ledger.jsonl")
    with open(p, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    return p


# ---- F2: cells, not bare classes ----

def test_cell_counts_flat_fm_is_the_flagged_cell():
    """The F2 trap this campaign actually hit: bare FLAT must NOT count toward FLAT+FM."""
    with tempfile.TemporaryDirectory() as td:
        p = _ledger(td, [
            {"status": "ACCEPTED", "measured_v2": "FLAT", "flag_FM": True},
            {"status": "ACCEPTED", "measured_v2": "FLAT", "flag_FM": False},   # descriptive only
            {"status": "ACCEPTED", "measured_v2": "FLAT", "flag_FM": False},
            {"status": "ACCEPTED", "measured_v2": "MID", "flag_FM": False},
            {"status": "ACCEPTED", "measured_v2": "LEVER-SEP", "flag_FM": False},
            # excluded populations: holdout, R, non-accepted
            {"status": "ACCEPTED", "measured_v2": "FLAT", "flag_FM": True, "holdout": True},
            {"status": "ACCEPTED", "measured_v2": "FLAT", "flag_FM": True, "dataset": "R",
             "holdout": True},
            {"status": "REJECTED_CLONE", "measured_v2": "FLAT", "flag_FM": True},
        ])
        c = rf._cell_counts(p)
        assert c["FLAT+FM"] == 1                  # NOT 3: the two FM- rows are descriptive
        assert c["FLAT"] == 2
        assert c["MID"] == 1 and c["LEVER-SEP"] == 1
        assert rf._cell_counts(os.path.join(td, "missing.jsonl")) == {}


# ---- A-3d: cap accounting + allocation ----

def test_topup_spend_counts_wave2_any_status_only():
    with tempfile.TemporaryDirectory() as td:
        p = _ledger(td, [
            {"status": "ACCEPTED", "wave": 2, "build_s": 100.0, "measure_s": 200.0},
            {"status": "REJECTED_CLONE", "wave": 2, "build_s": 50.0, "measure_s": 25.0},
            {"status": "MEASURE_FAIL", "wave": 2, "build_s": 30.0},          # measure_s absent
            {"status": "ACCEPTED", "build_s": 9999.0, "measure_s": 9999.0},  # wave-1: excluded
            {"status": "PARAMS_DUPLICATE", "wave": 2},                       # free skip: 0
        ])
        assert rf._topup_spend(p) == 405.0


def test_fail_rows_are_charged_to_the_cap():
    """A-3d says "any status". The wave-1 ledger proves the leak was real: all 3 MEASURE_FAIL rows
    carry no timings, so ~1 h cycles each cost the cap 0. Rows must now carry what they burned."""
    with tempfile.TemporaryDirectory() as td:
        p = _ledger(td, [
            {"status": "BUILD_FAIL", "wave": 2, "build_s": 1500.0},
            {"status": "MEASURE_FAIL", "wave": 2, "build_s": 1500.0, "measure_s": 1750.0},
            {"status": "CYCLE_ORPHAN", "wave": 2, "orphan_s": 900.0},
            {"status": "ACCEPTED", "wave": 2, "build_s": 100.0, "measure_s": 200.0},
            {"status": "TOPUP_CAP_DEFERRED", "wave": 2},                      # free
            {"status": "MEASURE_FAIL", "build_s": 9999.0, "measure_s": 9999.0},  # wave-1 excluded
        ])
        assert rf._topup_spend(p) == 1500.0 + 3250.0 + 900.0 + 300.0


def test_reconcile_inflight_charges_a_killed_cycle():
    """A cycle killed mid-phase writes no ledger row; its cost must still reach the cap, measured
    from the phase's own continuous output (log / table.jsonl mtime)."""
    with tempfile.TemporaryDirectory() as td:
        kid = "fleet_MID_W2_50_mid_hist"
        os.makedirs(os.path.join(td, kid))
        log = os.path.join(td, "run.log")
        open(log, "w").write("building\n")
        t0 = os.path.getmtime(log) - 600.0                  # cycle started 10 min before last write
        with open(rf._inflight_path(td), "w") as f:
            json.dump({"kernel_id": kid, "t_start": t0, "log": log}, f)
        lp = os.path.join(td, "fleet_ledger.jsonl")
        with open(lp, "a") as ledger:
            charged = rf._reconcile_inflight(td, ledger, {"wave": 2})
        assert 595 <= charged <= 605, charged
        rows = [json.loads(l) for l in open(lp)]
        assert rows[0]["status"] == "CYCLE_ORPHAN" and rows[0]["kernel_id"] == kid
        assert rf._topup_spend(lp) == rows[0]["orphan_s"]
        assert not os.path.exists(rf._inflight_path(td))    # consumed, not re-charged next launch
        # idempotent: nothing left to reconcile
        with open(lp, "a") as ledger:
            assert rf._reconcile_inflight(td, ledger, {"wave": 2}) is None


def test_cap_stop_is_recorded_once():
    with tempfile.TemporaryDirectory() as td:
        p = _ledger(td, [{"status": "ACCEPTED", "wave": 2}])
        assert rf._cap_stop_recorded(p) is False
        with open(p, "a") as f:
            f.write(json.dumps({"status": "TOPUP_CAP_STOP", "wave": 2}) + "\n")
        assert rf._cap_stop_recorded(p) is True


def test_summary_is_rebuilt_from_the_ledger_not_the_walk():
    """Relaunch drops closed cells from the walk; the artifact must still list every wave-2
    acceptance, so it is derived from the append-only ledger."""
    with tempfile.TemporaryDirectory() as td:
        p = _ledger(td, [
            {"status": "ACCEPTED", "wave": 2, "kernel_id": "a", "slot": "a", "template": "mid_hist",
             "intended_regime": "MID", "measured_v2": "MID", "flag_FM": False, "flag_FEAS": True},
            {"status": "ACCEPTED", "wave": 1, "kernel_id": "old"},          # wave-1 excluded
            {"status": "REJECTED_CLONE", "wave": 2, "kernel_id": "b"},      # not an acceptance
        ])
        got = rf._topup_accepted(p)
        assert [g["kernel_id"] for g in got] == ["a"] and got[0]["wave"] == 2


def test_topup_open_skips_filled_cells_and_exhausted_rosters():
    lens = {r: 40 for r in rf.TOPUP_ORDER}
    ptr = {r: 0 for r in rf.TOPUP_ORDER}
    counts = {"FLAT+FM": 11, "MID": 26, "LEVER-SEP": 25}
    assert rf._topup_open(counts, ptr, lens) == ["FLAT_FM_W2", "LEVER_SEP_W2"]   # MID at floor
    counts["LEVER-SEP"] = 26
    assert rf._topup_open(counts, ptr, lens) == ["FLAT_FM_W2"]
    ptr["FLAT_FM_W2"] = 40                                                       # roster spent
    assert rf._topup_open(counts, ptr, lens) == []


def test_process_slot_cap_gate_defers_before_any_build():
    """attempt_gate False ⇒ TOPUP_CAP_DEFERRED ledgered + 'CAP' returned + nothing measured.
    Non-vacuous: the same walk with a True gate would reach the build step (absent here, so
    the deferral is the ONLY reason no BUILD_FAIL/etc entry appears)."""
    with tempfile.TemporaryDirectory() as td:
        kroot, out = os.path.join(td, "_kernels"), td
        os.makedirs(kroot)
        lp = os.path.join(td, "fleet_ledger.jsonl")
        slot = g2.roster("MID_W2", 1, start_index=50)[0]
        with open(lp, "a") as ledger:
            r = rf.process_slot(kroot, out, ledger, os.path.join(td, "log"), {"wave": 2},
                                "MID_W2", slot, 65.0, attempt_gate=lambda: False)
        assert r == "CAP"
        rows = [json.loads(l) for l in open(lp)]
        assert [e["status"] for e in rows] == ["TOPUP_CAP_DEFERRED"]
        assert rows[0]["wave"] == 2


# ---- A-3b/A-3c: wave labels + W2 registry discipline ----

def test_emit_kernel_stamps_wave():
    with tempfile.TemporaryDirectory() as td:
        g2.emit_kernel(td, "MID_W2", "fleet_MID_W2_50_mid_hist", "mid_hist",
                       {"bins": 512, "n": 49152}, None, 50)
        spec = json.load(open(os.path.join(td, "fleet_MID_W2_50_mid_hist", "spec.json")))
        assert spec["wave"] == 2
        assert spec["intended_regime"] == "MID"
        g2.emit_kernel(td, "MID", "fleet_MID_06_mid_gatherpoly", "mid_gatherpoly",
                       {"deg": 2, "n": 49152}, None, 6)
        spec1 = json.load(open(os.path.join(td, "fleet_MID_06_mid_gatherpoly", "spec.json")))
        assert spec1["wave"] == 1


def test_w2_param_spaces_disjoint_from_wave1():
    """Every W2 param point must be NEW vs the wave-1 space of the same template — an overlap
    would burn wave-2 slots on D8 dup-skips or measured re-rejections."""
    w1 = {}
    for reg in ("FLAT_FM", "MID", "LEVER_SEP", "INT"):
        for name, _p, _d, pspace, _f in g2.REGISTRY[reg]:
            w1.setdefault(name, []).extend(pspace)
    for reg in ("FLAT_FM_W2", "MID_W2", "LEVER_SEP_W2"):
        for name, _p, _d, pspace, _f in g2.REGISTRY[reg]:
            for pt in pspace:
                assert pt not in w1.get(name, []), (reg, name, pt)


def test_w2_flat_fm_is_double_only_and_producers_only():
    for name, _p, _d, pspace, _f in g2.REGISTRY["FLAT_FM_W2"]:
        assert name in ("fm_sum", "fm_dot", "fm_sumsq")          # A-3c producers only
        assert all(pt["dt"] == "double" for pt in pspace)        # measured: float never FM+
    # A-6a (A-4 resume): LEVER_SEP_W2 narrowed on measured wave-2 producer evidence.
    # lev_axpy measured INT in wave-2 and int_sum64 (INT-flavoured by construction) drifted and was
    # reconciled as a 1608.5 s CYCLE_ORPHAN — both are now EVIDENCE for the P-2 report, not supply.
    lev = [t[0] for t in g2.REGISTRY["LEVER_SEP_W2"]]
    assert set(lev) == {"lev_modconst", "lev_csr"}
    assert lev[0] == "lev_modconst", "the both-wave producer must be drawn first (A-6a)"
    for bad in ("lev_clipmap", "lev_sqrtmap", "lev_strided",     # 0/10 wave-1 non-producers
                "lev_axpy", "int_sum64"):                        # A-6b INT-ward drifters
        assert bad not in lev
    # A-6e: MID_W2 reordered, NOT narrowed — mid_hist stays as parameter supply.
    mid = [t[0] for t in g2.REGISTRY["MID_W2"]]
    assert set(mid) == {"mid_hist", "mid_gatherpoly"}
    assert mid[0] == "mid_gatherpoly", "the zero-clone producer must be drawn first (A-6e)"
    assert all(g2.REGIME_INTENDED[k] == v for k, v in
               (("FLAT_FM_W2", "FLAT+FM"), ("MID_W2", "MID"), ("LEVER_SEP_W2", "LEVER-SEP")))


def test_cell_counts_separates_training_from_holdout():
    """H has its own ≥3-per-cell requirement; the two populations must never be pooled — a
    holdout kernel counting toward a TRAINING floor would leak H into the training set."""
    with tempfile.TemporaryDirectory() as td:
        p = _ledger(td, [
            {"status": "ACCEPTED", "measured_v2": "LEVER-SEP", "flag_FM": False},
            {"status": "ACCEPTED", "measured_v2": "LEVER-SEP", "flag_FM": False, "holdout": True},
            {"status": "ACCEPTED", "measured_v2": "FLAT", "flag_FM": True, "holdout": True},
            {"status": "ACCEPTED", "measured_v2": "INT", "dataset": "R", "holdout": True},  # R
        ])
        assert rf._cell_counts(p) == {"LEVER-SEP": 1}
        assert rf._cell_counts(p, holdout=True) == {"LEVER-SEP": 1, "FLAT+FM": 1}


def test_accepted_holdout_excludes_training_and_R():
    with tempfile.TemporaryDirectory() as td:
        p = _ledger(td, [
            {"status": "ACCEPTED", "kernel_id": "h1", "holdout": True, "measured_v2": "MID"},
            {"status": "ACCEPTED", "kernel_id": "t1", "measured_v2": "MID"},
            {"status": "ACCEPTED", "kernel_id": "r1", "holdout": True, "dataset": "R"},
            {"status": "REJECTED_CLONE", "kernel_id": "h2", "holdout": True},
        ])
        assert [e["kernel_id"] for e in rf._accepted_holdout(p)] == ["h1"]


def test_h_config_matches_the_ruling():
    assert rf.H_PER_CELL == 3 and rf.H_MIN_TOTAL == 15
    assert set(rf.H_CELL.values()) == {"FLAT+FM", "MID", "LEVER-SEP", "INT"}
    # H draws on producer templates, and its indices cannot collide with any earlier band
    assert rf.H_START_INDEX >= rf.TOPUP_START_INDEX + rf.TOPUP_MAX_SLOTS
    for r in rf.H_ORDER:
        assert r in g2.REGISTRY


def test_freeze_manifest_carries_wave_and_study_set_slices_on_it():
    """A-3b: the freeze is WRITE-ONCE, so if the manifest ships without `wave` the pre-registered
    with/without-wave-2 robustness slice becomes impossible forever."""
    import run_study
    with tempfile.TemporaryDirectory() as td:
        rows = [
            {"status": "ACCEPTED", "kernel_id": "k1", "slot": "k1", "template": "fm_sum",
             "measured_v2": "FLAT", "flag_FM": True},                       # wave-1 (no field)
            {"status": "ACCEPTED", "kernel_id": "k2", "slot": "k2", "template": "mid_hist",
             "measured_v2": "MID", "wave": 2, "flag_FM": False},
            {"status": "ACCEPTED", "kernel_id": "k3", "slot": "k3", "measured_v2": "INT",
             "holdout": True},
        ]
        _ledger(td, rows)
        for kid in ("k1", "k2", "k3"):
            os.makedirs(os.path.join(td, kid))
            open(os.path.join(td, kid, "table.jsonl"), "w").write("{}\n")
            open(os.path.join(td, kid, "class_v2.json"), "w").write("{}")
        _out, man = run_study.make_freeze_manifest(td)
        assert man["kernels"]["k1"]["wave"] == 1      # absent ⇒ wave 1, not missing
        assert man["kernels"]["k2"]["wave"] == 2
        assert run_study.study_set(man) == ["k1", "k2"]          # holdout excluded
        assert run_study.study_set(man, waves=(1,)) == ["k1"]    # the robustness slice
        assert run_study.study_set(man, waves=(2,)) == ["k2"]


def test_w2_roster_ids_and_indices_clear_of_fleet_and_holdout():
    slots = g2.roster("LEVER_SEP_W2", 6, start_index=rf.TOPUP_START_INDEX)
    assert [s[4] for s in slots] == [50, 51, 52, 53, 54, 55]     # >41 spares, >>36-40 H
    assert slots[0][0].startswith("fleet_LEVER_SEP_W2_50_")
    # FEAS balance discipline carried over (A-2g): half the slots draw a trap variant
    assert sum(1 for s in slots if s[3] is not None) == 3
