"""D20 regression — a cycle killed during the BUILD phase must charge its real cost to the cap.

ROOT CAUSE. `_run` writes the "$ podman run …" header to the run log, flushes, then hands the fd
to the child. build_phase.py's stdout is block-buffered, so nothing further reaches the log until
the child EXITS. `_reconcile_inflight` scanned only (log, table.jsonl) — neither of which advances
during a build — so `max()` collapsed to t_start and the dead cycle charged 0.0 s.

FIELD EVIDENCE. Three of the seven wave-2 CYCLE_ORPHAN rows on the survival ledger carry
orphan_s == 0.0 exactly (fleet_MID_W2_52_mid_hist_r2, _r3, _r3) — build-phase deaths that charged
the A-3d cap nothing. The defect was found when the A-7 transition tried to charge a killed H
build and the committed reconciler returned 0.0 s for 27 minutes of real compile time.

The first test below is RED against the pre-fix reconciler (it charges 0.0) and green after.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_fleet as rf     # noqa: E402


def _stale_log(td):
    """A run log frozen at t_start — exactly what a buffered child leaves behind."""
    log = os.path.join(td, "run.log")
    open(log, "w").write("$ podman run ... build_phase.py\n")
    return log


def test_build_phase_death_charges_from_the_build_manifest():
    """D20: build_manifest.jsonl is the build's continuous progress artifact. RED pre-fix."""
    with tempfile.TemporaryDirectory() as td:
        kid = "fleet_MID_W2_52_mid_hist_r2"
        kdir = os.path.join(td, kid)
        os.makedirs(kdir)
        log = _stale_log(td)
        t0 = os.path.getmtime(log)
        bm = os.path.join(kdir, "build_manifest.jsonl")
        open(bm, "w").write('{"config_id": 417}\n')
        os.utime(bm, (t0 + 1620.0, t0 + 1620.0))            # 27 min of compiling, then killed
        with open(rf._inflight_path(td), "w") as f:
            json.dump({"kernel_id": kid, "t_start": t0, "log": log}, f)
        lp = os.path.join(td, "fleet_ledger.jsonl")
        with open(lp, "a") as ledger:
            charged = rf._reconcile_inflight(td, ledger, {"wave": 2, "run_kind": "fleet-topup"})
        assert 1615 <= charged <= 1625, f"build death charged {charged}s — D20 regression"
        assert rf._topup_spend(lp) == charged


def test_so_directory_is_the_backstop():
    """If the manifest has not been flushed yet, the _so dir mtime still advances per .so."""
    with tempfile.TemporaryDirectory() as td:
        kid = "fleet_INT_H_200_int_revsum"
        kdir = os.path.join(td, kid)
        so = os.path.join(kdir, "_so")
        os.makedirs(so)
        log = _stale_log(td)
        t0 = os.path.getmtime(log)
        os.utime(so, (t0 + 300.0, t0 + 300.0))
        with open(rf._inflight_path(td), "w") as f:
            json.dump({"kernel_id": kid, "t_start": t0, "log": log}, f)
        lp = os.path.join(td, "fleet_ledger.jsonl")
        with open(lp, "a") as ledger:
            charged = rf._reconcile_inflight(td, ledger, {"run_kind": "holdout"})
        assert 295 <= charged <= 305, charged
        assert rf._h_spend(lp) == charged                   # A-7d cap sees it too


def test_measure_phase_death_still_charges_from_table():
    """NEGATIVE CONTROL — the pre-existing measure-phase path must not regress."""
    with tempfile.TemporaryDirectory() as td:
        kid = "fleet_MID_W2_53_mid_hist_r4"
        kdir = os.path.join(td, kid)
        os.makedirs(kdir)
        log = _stale_log(td)
        t0 = os.path.getmtime(log)
        tb = os.path.join(kdir, "table.jsonl")
        open(tb, "w").write('{"config_id": 3}\n')
        os.utime(tb, (t0 + 2760.6, t0 + 2760.6))
        with open(rf._inflight_path(td), "w") as f:
            json.dump({"kernel_id": kid, "t_start": t0, "log": log}, f)
        lp = os.path.join(td, "fleet_ledger.jsonl")
        with open(lp, "a") as ledger:
            charged = rf._reconcile_inflight(td, ledger, {"wave": 2})
        assert 2755 <= charged <= 2765, charged


def test_a_cycle_that_truly_did_nothing_still_charges_zero():
    """The bound stays a LOWER bound: no artifacts ⇒ no evidence of work ⇒ 0.0, not a guess."""
    with tempfile.TemporaryDirectory() as td:
        kid = "fleet_INT_H_201_int_sumsq"
        os.makedirs(os.path.join(td, kid))
        log = _stale_log(td)
        with open(rf._inflight_path(td), "w") as f:
            json.dump({"kernel_id": kid, "t_start": os.path.getmtime(log), "log": log}, f)
        lp = os.path.join(td, "fleet_ledger.jsonl")
        with open(lp, "a") as ledger:
            assert rf._reconcile_inflight(td, ledger, {"run_kind": "holdout"}) == 0.0
