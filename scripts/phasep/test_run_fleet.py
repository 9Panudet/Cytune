"""run_fleet helper TDD — resume/acceptance bookkeeping (no measurement here)."""
import json
import os
import tempfile
import run_fleet as rf


def _ledger(tmp, entries):
    p = os.path.join(tmp, "fleet_ledger.jsonl")
    with open(p, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    return p


def test_accepted_props_filters_status_and_template():
    with tempfile.TemporaryDirectory() as td:
        p = _ledger(td, [
            {"status": "ACCEPTED", "template": "fm_sum", "p": [0.1, 0.2, 0.3, 0.4, 0.5]},
            {"status": "REJECTED_CLONE", "template": "fm_sum", "p": [9, 9, 9, 9, 9]},
            {"status": "ACCEPTED", "template": "fm_dot", "p": [1, 1, 1, 1, 1]},
        ])
        assert rf._accepted_props(p, "fm_sum") == [(0.1, 0.2, 0.3, 0.4, 0.5)]
        assert rf._accepted_props(p, "fm_dot") == [(1, 1, 1, 1, 1)]
        assert rf._accepted_props(os.path.join(td, "missing.jsonl"), "fm_sum") == []


def test_params_duplicate_guard():
    with tempfile.TemporaryDirectory() as td:
        p = _ledger(td, [
            {"status": "ACCEPTED", "template": "fm_dot", "params": {"dt": "double", "n": 49152},
             "feas_variant": None},
            {"status": "REJECTED_CLONE", "template": "fm_dot", "params": {"dt": "double", "n": 4096},
             "feas_variant": None},
        ])
        assert rf._params_duplicate(p, "fm_dot", {"dt": "double", "n": 49152}, None) is True
        assert rf._params_duplicate(p, "fm_dot", {"dt": "double", "n": 4096}, None) is True
        assert rf._params_duplicate(p, "fm_dot", {"dt": "float", "n": 49152}, None) is False
        assert rf._params_duplicate(p, "fm_dot", {"dt": "double", "n": 49152}, "trap_wrap") is False
        assert rf._params_duplicate(p, "fm_sum", {"dt": "double", "n": 49152}, None) is False


def test_slot_done_requires_accepted():
    with tempfile.TemporaryDirectory() as td:
        p = _ledger(td, [
            {"slot": "fleet_MID_06_mid_gatherpoly", "status": "REJECTED_CLONE"},
            {"slot": "fleet_MID_06_mid_gatherpoly", "status": "ACCEPTED", "kernel_id": "x_r1"},
        ])
        e = rf._slot_done(p, "fleet_MID_06_mid_gatherpoly")
        assert e and e["kernel_id"] == "x_r1"
        assert rf._slot_done(p, "fleet_MID_07_other") is None


def test_clean_interrupted_deletes_partial_measure_keeps_build():
    with tempfile.TemporaryDirectory() as td:
        k = os.path.join(td, "k")
        os.makedirs(k)
        for f in ("table.jsonl", "oracle.json", "build_manifest.jsonl"):
            open(os.path.join(k, f), "w").write("{}")
        assert rf._clean_interrupted(k) is True
        assert not os.path.exists(os.path.join(k, "table.jsonl"))
        assert os.path.exists(os.path.join(k, "build_manifest.jsonl"))   # build kept
        # FINALIZE-CRASH shape (the fleet kernel #1 bug): table+endpoint but NO class_record
        # is NOT complete — must be cleaned including the stale endpoint
        for f in ("table.jsonl", "endpoint.json"):
            open(os.path.join(k, f), "w").write("{}")
        assert rf._measure_complete(k) is False
        assert rf._clean_interrupted(k) is True
        assert not os.path.exists(os.path.join(k, "endpoint.json"))
        # complete kernel (class_record present) is untouched
        for f in ("table.jsonl", "endpoint.json", "class_record.json"):
            open(os.path.join(k, f), "w").write("{}")
        assert rf._measure_complete(k) is True
        assert rf._clean_interrupted(k) is False
        assert os.path.exists(os.path.join(k, "table.jsonl"))


# --------------------------------------------------- A-4 resume: explicit gate dir selection
def _gate_dir(stage, controls_dir):
    """Mirrors run_fleet.main's gate_dir resolution (kept in sync by the tests below)."""
    return controls_dir if controls_dir != "controls" else \
        ("controls_a3" if stage == "topup" else "controls")


def test_gate_dir_default_preserves_prior_behaviour():
    assert _gate_dir("topup", "controls") == "controls_a3"
    assert _gate_dir("synth", "controls") == "controls"
    assert _gate_dir("holdout", "controls") == "controls"


def test_explicit_controls_dir_selects_the_gate_it_checks():
    """A-4 resume re-gates into its own dir so an earlier gate's evidence is never overwritten."""
    assert _gate_dir("topup", "controls_a4") == "controls_a4"
    assert _gate_dir("holdout", "controls_a4") == "controls_a4"


def test_gate_dir_resolution_matches_run_fleet_source():
    """Non-vacuity: pin the helper above against the real expression in run_fleet.main."""
    import os
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_fleet.py")).read()
    assert 'gate_dir = a.controls_dir if a.controls_dir != "controls" else' in src
    assert '("controls_a3" if a.stage == "topup" else "controls")' in src
