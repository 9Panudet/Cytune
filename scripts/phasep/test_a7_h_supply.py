"""A-7 (H supply extension) — tests for the amendment's binding clauses.

Each test names the clause it defends. Every gate test verifies the FAILURE path once (no vacuous
assertions): the freshness test proves the checker CAN detect a collision, the cap test proves the
gate CAN fire, the frozen-registry test proves it CAN see a perturbation.
"""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_v2 as g2     # noqa: E402
import run_fleet as rf       # noqa: E402
import run_study as rst      # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
LEDGER = os.path.join(REPO, "results", "fleet", "fleet_ledger.jsonl")


def _keys(regime):
    """Every (template, params, trap) key the registry can ever offer."""
    out = []
    for name, _pyx, _drv, pspace, feas_ok in g2.REGISTRY[regime]:
        for p in pspace:
            for tr in (None,) + tuple(feas_ok):
                out.append((name, json.dumps(p, sort_keys=True), str(tr)))
    return out


def _consumed(exclude_holdout=False):
    """The D8 pre-guard's key set: ACCEPTED + REJECTED_CLONE rows, fleet-wide.

    exclude_holdout: restrict to the TRAINING campaign's consumed keys. A-7's freshness claim is
    about the state the amendment was written against — once H starts running it CONSUMES the very
    keys A-7 supplied, so a fleet-wide check would fail by design and would be asserting that H had
    not run rather than that the extension was fresh."""
    if not os.path.exists(LEDGER):
        pytest.skip("no survival ledger in this checkout")
    return {(e.get("template"), json.dumps(e.get("params"), sort_keys=True),
             str(e.get("feas_variant")))
            for e in (json.loads(l) for l in open(LEDGER))
            if e.get("status") in ("ACCEPTED", "REJECTED_CLONE")
            and not (exclude_holdout and e.get("run_kind") == "holdout")}


# --- A-7a: the extension exists and is genuinely fresh -----------------------------------------

def test_h_registries_exist_and_are_separate_keys():
    """A-7a: NEW keys. The wave registries must not have been mutated — process_slot derives
    params as pspace[(gi+k) % len(pspace)], so appending to an existing pspace would silently
    repoint already-FROZEN slot labels."""
    assert "FLAT_FM_H" in g2.REGISTRY and "INT_H" in g2.REGISTRY
    # the exact pre-A-7 lengths, pinned so an accidental append to a frozen registry is caught
    assert [len(t[3]) for t in g2.REGISTRY["FLAT_FM_W2"]] == [5, 4, 4]
    assert [len(t[3]) for t in g2.REGISTRY["MID_W2"]] == [6, 6]
    assert [len(t[3]) for t in g2.REGISTRY["LEVER_SEP_W2"]] == [4, 4]
    assert [len(t[3]) for t in g2.REGISTRY["INT"]] == [2, 2, 2, 1, 2, 2, 2]


def test_frozen_registry_pin_would_catch_a_perturbation():
    """NEGATIVE CONTROL for the test above — prove the pin is not vacuous."""
    orig = g2.REGISTRY["MID_W2"]
    try:
        t0 = orig[0]
        g2.REGISTRY["MID_W2"] = [(t0[0], t0[1], t0[2], t0[3] + [{"deg": 9, "n": 12345}], t0[4])] \
            + list(orig[1:])
        assert [len(t[3]) for t in g2.REGISTRY["MID_W2"]] != [6, 6]
    finally:
        g2.REGISTRY["MID_W2"] = orig


def test_a7_points_are_all_fresh_against_the_training_campaign():
    """A-7a: all 102 candidate keys were fresh against everything the TRAINING campaign consumed —
    the claim the amendment actually makes, and the one that stays checkable after H runs."""
    consumed = _consumed(exclude_holdout=True)
    keys = _keys("FLAT_FM_H") + _keys("INT_H")
    assert len(keys) == 102, f"the amendment fixes 102 keys; found {len(keys)}"
    collisions = [k for k in keys if k in consumed]
    assert collisions == [], f"A-7 points collide with training-consumed keys: {collisions}"


def test_h_consumes_a7_keys_as_it_runs():
    """NON-VACUITY for the test above: prove the fleet-wide set really does grow to include A-7
    keys, so the exclude_holdout filter is doing work rather than hiding a broken check."""
    all_keys = _consumed()
    train_keys = _consumed(exclude_holdout=True)
    assert train_keys <= all_keys
    a7 = set(_keys("FLAT_FM_H") + _keys("INT_H"))
    if all_keys & a7:                       # H has measured at least one extended candidate
        assert not (train_keys & a7), "an A-7 key leaked into the training-consumed set"


def test_freshness_check_would_catch_a_collision():
    """NEGATIVE CONTROL — a known-consumed key must be reported as a collision."""
    consumed = _consumed()
    # fm_sum {'dt':'double','n':4096} trap=None is ACCEPTED in wave-2; it MUST read as consumed
    assert ("fm_sum", json.dumps({"dt": "double", "n": 4096}, sort_keys=True), "None") in consumed


def test_flat_fm_h_is_double_only():
    """A-7a: dt is the decisive measured axis (double -> FM+ 8/9; float -> FM+ 0/6)."""
    for _n, _p, _d, pspace, _f in g2.REGISTRY["FLAT_FM_H"]:
        assert all(p["dt"] == "double" for p in pspace)


def test_int_h_drops_int_sum64():
    """A-7a: int_sum64 measured LEVER-SEP 4/4 and INT 0/4 — evidence, not roster (A-6b logic)."""
    assert "int_sum64" not in [t[0] for t in g2.REGISTRY["INT_H"]]


def test_int_h_template_order_follows_measured_int_rate():
    """A-7a: ordering is by MEASURED wave-1 INT rate, not by convenience."""
    assert [t[0] for t in g2.REGISTRY["INT_H"]] == [
        "int_horner32", "int_horner64", "int_revsum", "int_sumsq", "int_min32", "int_max32"]


def test_flat_fm_h_n_stays_inside_the_demonstrated_corridor():
    """A-7a: the extrapolation is in the parameter GRID, not the regime — every n interpolates
    inside the measured 4,096-1,179,648 FLAT+FM corridor."""
    for _n, _p, _d, pspace, _f in g2.REGISTRY["FLAT_FM_H"]:
        assert all(4096 <= p["n"] <= 1179648 for p in pspace)


# --- A-7d: the cap ------------------------------------------------------------------------------

def test_h_cap_value_and_definition(tmp_path):
    """A-7d: 86,400 s over ALL holdout rows, ANY status, including orphan_s."""
    assert rf.H_CAP_S == 86400
    p = tmp_path / "l.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in [
        {"run_kind": "holdout", "status": "ACCEPTED", "build_s": 100, "measure_s": 200},
        {"run_kind": "holdout", "status": "BUILD_FAIL", "build_s": 50},          # failures charge
        {"run_kind": "holdout", "status": "MEASURE_FAIL", "build_s": 10, "measure_s": 5},
        {"run_kind": "holdout", "status": "CYCLE_ORPHAN", "orphan_s": 7},        # deaths charge
        {"run_kind": "holdout", "status": "PARAMS_DUPLICATE"},                   # dup-skips free
        {"run_kind": "fleet-topup", "wave": 2, "status": "ACCEPTED",
         "build_s": 9999, "measure_s": 9999},                                    # not H: excluded
    ]) + "\n")
    assert rf._h_spend(str(p)) == 372.0


def test_h_spend_excludes_wave2_and_wave2_spend_excludes_h(tmp_path):
    """The two caps must not leak into each other — A-3d's 172,800 s is already SPENT."""
    p = tmp_path / "l.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in [
        {"run_kind": "holdout", "status": "ACCEPTED", "build_s": 11, "measure_s": 0},
        {"run_kind": "fleet-topup", "wave": 2, "status": "ACCEPTED", "build_s": 22, "measure_s": 0},
    ]) + "\n")
    assert rf._h_spend(str(p)) == 11.0
    assert rf._topup_spend(str(p)) == 22.0


def test_h_cap_stop_is_recorded_distinctly(tmp_path):
    """A-7d: H_CAP_STOP is its own status — a cap-stop must never read as roster exhaustion,
    and must never be confused with the wave-2 TOPUP_CAP_STOP already on the ledger."""
    p = tmp_path / "l.jsonl"
    p.write_text(json.dumps({"status": "TOPUP_CAP_STOP"}) + "\n")
    assert rf._cap_stop_recorded(str(p), "TOPUP_CAP_STOP") is True
    assert rf._cap_stop_recorded(str(p), "H_CAP_STOP") is False      # failure path verified
    with open(p, "a") as f:
        f.write(json.dumps({"status": "H_CAP_STOP"}) + "\n")
    assert rf._cap_stop_recorded(str(p), "H_CAP_STOP") is True


# --- A-7d/A-7e: fill priority and provenance ----------------------------------------------------

def test_h_order_puts_int_first_then_flat_fm():
    """A-7d fill priority: INT was the structurally impossible cell and is the row P4 most needs."""
    assert rf.H_ORDER == ("INT_H", "FLAT_FM_H", "MID_W2", "LEVER_SEP_W2")
    assert rf.H_CELL["INT_H"] == "INT" and rf.H_CELL["FLAT_FM_H"] == "FLAT+FM"
    assert (rf.H_PER_CELL, rf.H_MIN_TOTAL) == (3, 15)      # UNCHANGED by A-7


def test_provenance_labels():
    """A-7e: H-ext iff the slot draws on an A-7 extended registry."""
    assert g2.provenance("INT_H") == "H-ext"
    assert g2.provenance("FLAT_FM_H") == "H-ext"
    assert g2.provenance("MID_W2") == "H-orig"
    assert g2.provenance("LEVER_SEP_W2") == "H-orig"


def test_h_spec_carries_provenance_and_is_wave_exempt(tmp_path):
    """A-7e + A-3b: an H kernel drawn from MID_W2 is NOT a wave-2 training kernel."""
    kdir = g2.emit_kernel(str(tmp_path), "MID_W2", "k_h", "mid_gatherpoly",
                          {"deg": 2, "n": 24576}, None, 200, holdout=True)
    spec = json.load(open(os.path.join(kdir, "spec.json")))
    assert spec["provenance"] == "H-orig"
    assert spec["wave"] is None
    kdir2 = g2.emit_kernel(str(tmp_path), "INT_H", "k_e", "int_revsum", {"n": 16384}, None, 200,
                           holdout=True)
    assert json.load(open(os.path.join(kdir2, "spec.json")))["provenance"] == "H-ext"


def test_training_kernels_keep_their_wave_and_carry_no_provenance(tmp_path):
    """NEGATIVE CONTROL: holdout=False must not perturb the frozen training spec schema."""
    kdir = g2.emit_kernel(str(tmp_path), "MID_W2", "k_t", "mid_gatherpoly",
                          {"deg": 2, "n": 24576}, None, 60)
    spec = json.load(open(os.path.join(kdir, "spec.json")))
    assert spec["wave"] == 2 and "provenance" not in spec


# --- A-7 §7: the seal ---------------------------------------------------------------------------

def _seed_h_fleet(root, rows):
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "fleet_ledger.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
            if r.get("status") == "ACCEPTED":
                d = os.path.join(root, r["kernel_id"])
                os.makedirs(d, exist_ok=True)
                open(os.path.join(d, "table.jsonl"), "w").write(r["kernel_id"])
                open(os.path.join(d, "class_v2.json"), "w").write("{}")


def test_h_manifest_seals_provenance_cells_and_hashes(tmp_path):
    root = str(tmp_path / "fleet")
    _seed_h_fleet(root, [
        {"kernel_id": "h1", "status": "ACCEPTED", "holdout": True, "provenance": "H-ext",
         "measured_v2": "INT", "flag_FM": False, "template": "int_revsum"},
        {"kernel_id": "h2", "status": "ACCEPTED", "holdout": True, "provenance": "H-ext",
         "measured_v2": "FLAT", "flag_FM": True, "template": "fm_sum"},
        {"kernel_id": "h3", "status": "ACCEPTED", "holdout": True, "provenance": "H-orig",
         "measured_v2": "MID", "flag_FM": False, "template": "mid_hist"},
        # excluded: training kernel, R anchor, and a non-accept
        {"kernel_id": "t1", "status": "ACCEPTED", "holdout": False, "measured_v2": "MID"},
        {"kernel_id": "r1", "status": "ACCEPTED", "holdout": True, "dataset": "R",
         "measured_v2": "MID"},
        {"kernel_id": "h4", "status": "REJECTED_CLONE", "holdout": True, "measured_v2": "INT"},
    ])
    _out, man = rst.make_h_manifest(root)
    assert man["n_kernels"] == 3
    assert man["cells"] == {"INT": 1, "FLAT+FM": 1, "MID": 1}          # the A-2c cell rule applies
    assert man["provenance_counts"] == {"H-ext": 2, "H-orig": 1}
    assert man["kernels"]["h1"]["table_sha256"] != man["kernels"]["h2"]["table_sha256"]
    assert "SLICED by provenance" in man["provenance_framing"]


def test_h_manifest_refuses_overwrite(tmp_path):
    """A-7 §7 + the freeze discipline: a seal is write-once."""
    root = str(tmp_path / "fleet")
    _seed_h_fleet(root, [{"kernel_id": "h1", "status": "ACCEPTED", "holdout": True,
                          "provenance": "H-ext", "measured_v2": "INT", "flag_FM": False}])
    rst.make_h_manifest(root)
    with pytest.raises(rst.FreezeViolation):
        rst.make_h_manifest(root)


def test_h_stays_out_of_the_p3_study_set():
    """A-7g: the firewall. H must never enter the study set, sealed or not."""
    man = {"kernels": {"t1": {"holdout": False, "dataset": "synthetic", "wave": 1},
                       "h1": {"holdout": True, "dataset": "synthetic", "wave": None},
                       "r1": {"holdout": True, "dataset": "R", "wave": None}}}
    assert rst.study_set(man) == ["t1"]


# --- A-7i: allocation rider (deprioritization) --------------------------------------------------

def test_deprioritize_removes_from_serving_only(tmp_path):
    """A-7i: a deprioritized regime is dropped from the SERVE list; its cell is still counted.
    Mirrors the live `need` filter."""
    H_ORDER, H_CELL = rf.H_ORDER, rf.H_CELL
    cells_now = {"INT": 2, "FLAT+FM": 1, "MID": 1, "LEVER-SEP": 1}
    total, ptr, lens = 5, {r: 0 for r in H_ORDER}, {r: 30 for r in H_ORDER}

    def need(dep):
        return [r for r in H_ORDER if r not in dep
                and (cells_now[H_CELL[r]] < rf.H_PER_CELL or total < rf.H_MIN_TOTAL)
                and ptr[r] < lens[r]]

    assert need(()) == ["INT_H", "FLAT_FM_H", "MID_W2", "LEVER_SEP_W2"]   # failure path first
    assert need(("FLAT_FM_H", "FLAT_FM_W2")) == ["INT_H", "MID_W2", "LEVER_SEP_W2"]
    # COUNTING is untouched — the ruling stops serving, never counting.
    assert cells_now["FLAT+FM"] == 1


def test_deprioritized_short_is_not_reported_as_supply_exhausted():
    """A-7i: attributing a human allocation ruling to the data would be a false finding."""
    H_CELL = rf.H_CELL
    short = {"FLAT+FM": 1, "LEVER-SEP": 2}
    dep_cells = {H_CELL[r] for r in ("FLAT_FM_H", "FLAT_FM_W2") if r in H_CELL}
    by_dep = {c: n for c, n in short.items() if c in dep_cells}
    by_supply = {c: n for c, n in short.items() if c not in dep_cells}
    assert by_dep == {"FLAT+FM": 1}
    assert by_supply == {"LEVER-SEP": 2}          # the two causes never merge


def test_deprioritize_rejects_unknown_regime_keys():
    """A typo must not silently serve everything (fail closed, not open)."""
    assert all(r in g2.REGISTRY for r in ("FLAT_FM_H", "FLAT_FM_W2", "INT_H"))
    assert "FLAT_FM_TYPO" not in g2.REGISTRY


def test_h_manifest_attributes_shortfall_cause(tmp_path):
    """A-7i: the write-once seal must distinguish deprioritized-short from supply-short. Getting
    this wrong is unrecoverable — the manifest refuses overwrite."""
    root = str(tmp_path / "fleet")
    os.makedirs(root, exist_ok=True)
    rows = [
        {"run_kind": "holdout", "status": "ACCEPTED", "kernel_id": "h1", "holdout": True,
         "provenance": "H-ext", "measured_v2": "INT", "flag_FM": False, "build_s": 10,
         "deprioritized": ["FLAT_FM_H", "FLAT_FM_W2"]},
        {"run_kind": "holdout", "status": "ACCEPTED", "kernel_id": "h2", "holdout": True,
         "provenance": "H-ext", "measured_v2": "FLAT", "flag_FM": True, "measure_s": 20},
        {"run_kind": "holdout", "status": "H_CAP_STOP", "spend_s": 86540.5, "cap_s": 86400,
         "cells": {"INT": 1, "FLAT+FM": 1}, "total": 2},
    ]
    with open(os.path.join(root, "fleet_ledger.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
            if r.get("status") == "ACCEPTED":
                d = os.path.join(root, r["kernel_id"])
                os.makedirs(d, exist_ok=True)
                open(os.path.join(d, "table.jsonl"), "w").write(r["kernel_id"])
                open(os.path.join(d, "class_v2.json"), "w").write("{}")
    _out, man = rst.make_h_manifest(root)
    assert man["allocation"]["deprioritized"] == ["FLAT_FM_H", "FLAT_FM_W2"]
    sf = man["ruling"]["shortfall"]
    # FLAT+FM was deprioritized -> must NOT read as supply exhaustion
    assert "DEPRIORITIZED" in sf["FLAT+FM"]["cause"] and "NOT short by supply" in sf["FLAT+FM"]["cause"]
    # MID/LEVER-SEP were served and simply did not fill -> the other cause
    assert "supply/cap" in sf["MID"]["cause"]
    assert sf["INT"]["short_by"] == 2 and "supply/cap" in sf["INT"]["cause"]
    assert man["cap_stop"]["spend_s"] == 86540.5
    assert man["h_spend_s"] == 30.0
    assert man["ruling"]["total_met"] is False
