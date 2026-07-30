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
