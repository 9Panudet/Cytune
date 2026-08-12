"""P-2 report generator — attrition counting must reflect DATA, not relaunch count.

Regression guard for the ledger-inflation defect: the fleet runner re-walks an already-exhausted
slot on every relaunch and re-ledgers SLOT_EXHAUSTED (each re-attempt hits the free
PARAMS_DUPLICATE pre-guard, so no measurement is burned). An undeduped count therefore scales with
the number of relaunches. Observed live at 30/130: 25 SLOT_EXHAUSTED entries for 5 real slots.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report_p2  # noqa: E402


def _write_ledger(d, entries):
    with open(os.path.join(d, "fleet_ledger.jsonl"), "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _ledger_fixture():
    """2 distinct exhausted slots (one re-ledgered 3x by relaunches) + 2 distinct clone-rejections
    on a SINGLE slot (legitimately separate attempts) + 1 acceptance."""
    return (
        [{"status": "SLOT_EXHAUSTED", "kernel_id": "fleet_FLAT_FM_30_fm_sum"}] * 3
        + [{"status": "SLOT_EXHAUSTED", "kernel_id": "fleet_FLAT_FM_32_fm_sumsq"}]
        + [{"status": "REJECTED_CLONE", "kernel_id": "fleet_MID_06_x", "params": {"n": 1}},
           {"status": "REJECTED_CLONE", "kernel_id": "fleet_MID_06_x", "params": {"n": 2}},
           {"status": "ACCEPTED", "kernel_id": "fleet_MID_06_x", "measured_v2": "MID"}]
    )


def test_exhausted_deduped_by_slot_rejected_not_deduped(tmp_path):
    d = str(tmp_path)
    _write_ledger(d, _ledger_fixture())
    out = report_p2.build_report(d)

    # Attrition counts DISTINCT slots: 2 exhausted, not the 4 raw entries.
    assert "exhausted slots: 2" in out, out
    # Clone-rejections are per-attempt and must NOT be collapsed: 2 distinct parameterizations.
    assert "rejected clones: 2" in out, out


def test_failure_path_undeduped_count_would_be_wrong(tmp_path):
    """Non-vacuous guard: prove the fixture actually discriminates — the naive undeduped count
    differs from the correct one, so a regression to `[e for e in led if ...]` fails the test above.
    """
    d = str(tmp_path)
    entries = _ledger_fixture()
    _write_ledger(d, entries)

    naive = len([e for e in entries if e["status"] == "SLOT_EXHAUSTED"])
    deduped = len({e["kernel_id"] for e in entries if e["status"] == "SLOT_EXHAUSTED"})
    assert naive == 4 and deduped == 2, (naive, deduped)
    # The buggy rendering must NOT be what build_report emits.
    assert f"exhausted slots: {naive}" not in report_p2.build_report(d)


def _cell_fixture():
    """3 FLAT kernels of which only 2 carry FM+ (the confirmatory cell), 1 MID, and a holdout +
    an R anchor that must be excluded from the confirmatory counts."""
    return [
        {"status": "ACCEPTED", "kernel_id": "k1", "measured_v2": "FLAT", "flag_FM": True,
         "intended_regime": "FLAT+FM", "wave": 1},
        {"status": "ACCEPTED", "kernel_id": "k2", "measured_v2": "FLAT", "flag_FM": True,
         "intended_regime": "FLAT+FM", "wave": 2},
        {"status": "ACCEPTED", "kernel_id": "k3", "measured_v2": "FLAT", "flag_FM": False,
         "intended_regime": "FLAT+FM", "wave": 1},
        {"status": "ACCEPTED", "kernel_id": "k4", "measured_v2": "MID", "flag_FM": False,
         "intended_regime": "MID", "wave": 1, "flag_FEAS": True},
        {"status": "ACCEPTED", "kernel_id": "k5", "measured_v2": "FLAT", "flag_FM": True,
         "intended_regime": "FLAT+FM", "holdout": True},
        {"status": "ACCEPTED", "kernel_id": "k6", "measured_v2": "FLAT", "flag_FM": True,
         "dataset": "R", "holdout": True},
    ]


def test_flat_fm_is_the_flagged_cell_not_the_bare_class(tmp_path):
    """D11 regression: `measured_v2` never equals 'FLAT+FM', so counting the bare class renders the
    confirmatory family as 0 and credits FM− kernels to a floor they do not belong to."""
    d = str(tmp_path)
    _write_ledger(d, _cell_fixture())
    out = report_p2.build_report(d)
    # 2 confirmatory FLAT+FM (k1,k2) — NOT 0, and NOT 3 (k3 is FM−), and NOT 4 (holdout/R excluded)
    assert "| FLAT+FM | 2 | 0 | **2** | 1 | 1 |" in out, out
    # the FM− kernel is reported, but explicitly outside the floor
    assert "not confirmatory" in out
    assert f"| {report_p2.DESCRIPTIVE_CELL} | 1 |" in out, out
    # the shortfall is stated with its size rather than a bare dash
    assert "BELOW FLOOR by 24" in out


def test_confusion_columns_use_cells_and_span_holdout(tmp_path):
    """The confusion table covers ALL fleet kernels (synth + holdout) — H is measured in the same
    campaign and its intended-vs-measured behaviour is evidence about the GENERATOR. The floor
    counts in §1 deliberately do NOT include holdout (H is sealed from the training set), so the
    two tables legitimately disagree: 3 FM+ here vs 2 confirmatory in §1."""
    d = str(tmp_path)
    _write_ledger(d, _cell_fixture())
    out = report_p2.build_report(d)
    conf = [l for l in out.splitlines() if l.startswith("| FLAT+FM |")][-1]
    assert conf.split("|")[2].strip() == "3", conf          # k1, k2 + holdout k5
    assert conf.split("|")[6].strip() == "1", conf          # k3 landed FM− (descriptive)
    assert "| FLAT+FM | 2 | 0 | **2** | 1 | 1 |" in out     # §1 floor row excludes the holdout


def test_failure_path_bare_class_counting_would_be_wrong(tmp_path):
    """Non-vacuity: prove the fixture discriminates — the naive bare-class count differs from the
    cell count in BOTH directions (FLAT+FM 0 vs 2; bare FLAT 3 vs descriptive 1)."""
    entries = _cell_fixture()
    synth = [e for e in entries if not e.get("holdout")]
    naive_flatfm = sum(1 for e in synth if e["measured_v2"] == "FLAT+FM")
    naive_flat = sum(1 for e in synth if e["measured_v2"] == "FLAT")
    cell_flatfm = sum(1 for e in synth if report_p2._cell(e) == "FLAT+FM")
    assert naive_flatfm == 0 and cell_flatfm == 2
    assert naive_flat == 3 and sum(
        1 for e in synth if report_p2._cell(e) == report_p2.DESCRIPTIVE_CELL) == 1
    d = str(tmp_path)
    _write_ledger(d, entries)
    # Target §1's floor row specifically — §1c's FEAS split legitimately contains a zero cell.
    assert "| FLAT+FM | 0 | 0 | **0** |" not in report_p2.build_report(d)


def test_feas_contrast_reported_on_the_conformant_arms(tmp_path):
    """A-2g rider R1: the FEAS contrast is the product's key question, so its arm sizes are the
    §4-conformant ones. 1 FEAS+ / 3 FEAS− here, both far below the floor."""
    d = str(tmp_path)
    _write_ledger(d, _cell_fixture())
    out = report_p2.build_report(d)
    assert "| FEAS+ | 1 | 0 | **1** |" in out, out
    assert "| FEAS− | 3 | 0 | **3** |" in out, out
    assert "BELOW FLOOR" in out


# ---------------------------------------------------------------------------------------------
# D22 — the report generator IS an instrument, so it gets the control it was missing: the §4
# exclusion must be able to MOVE a floor verdict. Without this assertion the fix is untested and
# could regress exactly as silently as the original defect did.
# ---------------------------------------------------------------------------------------------
def _floor_fixture(n_agreement_fail):
    """FLOOR_N MID kernels, of which `n_agreement_fail` failed the binary agreement check."""
    out = []
    for i in range(report_p2.FLOOR_N):
        out.append({"status": "ACCEPTED", "kernel_id": f"m{i}", "measured_v2": "MID",
                    "intended_regime": "MID", "wave": 1,
                    "agreement_ok": i >= n_agreement_fail})
    return out


def test_agreement_fail_moves_a_cell_below_the_floor(tmp_path):
    """PREREG §4 applied verbatim: exactly-at-floor as measured, below it on the inference set."""
    d = str(tmp_path)
    _write_ledger(d, _floor_fixture(0))
    assert f"| MID | {report_p2.FLOOR_N} | 0 | **{report_p2.FLOOR_N}** |" in report_p2.build_report(d)
    assert "1 of 4 confirmatory cells meet" in report_p2.build_report(d)

    _write_ledger(d, _floor_fixture(2))
    out = report_p2.build_report(d)
    assert f"| MID | {report_p2.FLOOR_N} | 2 | **{report_p2.FLOOR_N - 2}** |" in out, out
    assert "BELOW FLOOR by 2" in out, out
    assert "the whole gap is the 2 §4/voided exclusions" in out, out
    assert "0 of 4 confirmatory cells meet" in out, out


def test_failure_path_as_measured_n_would_read_met(tmp_path):
    """Non-vacuity: the fixture discriminates. The as-measured n is exactly at the floor, so a
    generator that ignores §4 renders MET on the very same data — which is what D22 was."""
    entries = _floor_fixture(2)
    as_measured = sum(1 for e in entries if e["measured_v2"] == "MID")
    conformant = sum(1 for e in entries if e["agreement_ok"])
    assert as_measured == report_p2.FLOOR_N and conformant == report_p2.FLOOR_N - 2
    d = str(tmp_path)
    _write_ledger(d, entries)
    assert "1 of 4 confirmatory cells meet" not in report_p2.build_report(d)


def test_no_memo_threshold_survives_in_the_generator():
    """D22: the ">10%" rule is deleted, not merely re-labelled. It must not be able to gate
    anything again — a threshold that still exists in code is a threshold that can be re-wired."""
    src = open(report_p2.__file__.replace(".pyc", ".py")).read()
    assert "frac > 0.10" not in src
    assert "fired = " not in src.split("## 4. Measurement validity")[0]


def test_report_runs_on_empty_ledger(tmp_path):
    """Mid-campaign snapshot robustness: no ledger, no freeze manifest, still renders."""
    out = report_p2.build_report(str(tmp_path))
    assert "NOT FROZEN YET" in out
    assert "exhausted slots: 0" in out
