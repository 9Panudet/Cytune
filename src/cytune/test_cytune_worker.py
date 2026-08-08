"""Worker-side resume robustness (D17).

The pruned-cache case is the one a real user hits: a workspace survives, its .so files do not.
"""
import json
import os

from cytune.worker import _drop_stale_manifest_rows


def _manifest(tmp_path, rows):
    p = tmp_path / "build_manifest.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def test_rows_whose_so_is_missing_are_dropped_so_they_rebuild(tmp_path):
    so = tmp_path / "kernel_1.so"
    so.write_text("x")
    m = _manifest(tmp_path, [
        {"config_id": 1, "ok": True, "so_path": str(so)},                       # present -> keep
        {"config_id": 2, "ok": True, "so_path": str(tmp_path / "gone.so")},     # missing -> drop
    ])
    assert _drop_stale_manifest_rows(str(tmp_path)) == 1
    rows = [json.loads(l) for l in open(m)]
    assert [r["config_id"] for r in rows] == [1]


def test_failed_build_rows_are_kept(tmp_path):
    """A cythonize failure is cached as feasibility-0 on purpose (the inherited beta policy);
    dropping it would silently re-attempt a build the study deliberately caches as failed."""
    m = _manifest(tmp_path, [{"config_id": 3, "ok": False, "reason": "cythonize_fail",
                              "so_path": str(tmp_path / "never.so")}])
    assert _drop_stale_manifest_rows(str(tmp_path)) == 0
    assert len([l for l in open(m)]) == 1


def test_intact_manifest_is_left_completely_alone(tmp_path):
    so = tmp_path / "k.so"
    so.write_text("x")
    m = _manifest(tmp_path, [{"config_id": 1, "ok": True, "so_path": str(so)}])
    before = m.read_text()
    assert _drop_stale_manifest_rows(str(tmp_path)) == 0
    assert m.read_text() == before, "an intact manifest must not be rewritten"


def test_missing_manifest_is_not_an_error(tmp_path):
    assert _drop_stale_manifest_rows(str(tmp_path)) == 0


# ------------------------------------------------------ H1: a child cannot report time that
#                                                             did not elapse
def test_a_child_claiming_more_time_than_elapsed_is_flagged():
    """H1 (partial). The driver shares the interpreter that times it, so it can choose the numbers
    the host is handed. The parent, however, times the WHOLE child — so `K * median` exceeding the
    wall clock is time that did not happen, and no honest measurement can produce it."""
    from cytune.worker import implausible_timings
    rows = {5: {"screen": {"median_ns": 65e6, "K": 5, "wall_ns": 100e6}}}   # claims 325ms in 100ms
    bad = implausible_timings(rows)
    assert len(bad) == 1 and bad[0]["config_id"] == 5
    assert bad[0]["ratio"] > 3


def test_an_honest_measurement_is_never_flagged():
    """Control. Spawn, import and build overhead only ever make the wall LARGER, so an honest row
    always has K*median < wall. Flagging one would make the check useless."""
    from cytune.worker import implausible_timings
    rows = {
        1: {"screen": {"median_ns": 65e6, "K": 5, "wall_ns": 2_800_000_000}},  # big spawn overhead
        2: {"screen": {"median_ns": 10e6, "K": 30, "wall_ns": 305e6}},         # tight
        3: {"screen": {"median_ns": 10e6, "K": 30, "wall_ns": 300e6}},         # exactly equal
        4: {"screen": None},
        5: {},
    }
    assert implausible_timings(rows) == []


def test_the_check_tolerates_clock_granularity_but_not_a_real_overclaim():
    from cytune.worker import implausible_timings
    assert implausible_timings({1: {"screen": {"median_ns": 101e6, "K": 1, "wall_ns": 100e6}}}) == []
    assert implausible_timings({1: {"screen": {"median_ns": 150e6, "K": 1, "wall_ns": 100e6}}})
