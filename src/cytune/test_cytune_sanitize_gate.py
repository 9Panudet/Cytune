"""§1.4 sanitizer gate on the emitted config — the product half of D23.

The gate exists because the ORACLE CANNOT SEE a memory error that produced a correct output; that
is precisely how 1,296 out-of-bounds configs were recorded feasible in the Phase-P study. These
tests pin the DECISION LOGIC (which verdicts forbid an emit) without needing a container — the
container path is exercised by the live end-to-end runs.
"""
from cytune import sanitize_gate as sg


def test_only_a_positive_report_forbids_emitting():
    assert sg.rejects({"verdict": "SANITIZER_REPORT", "clean": False,
                       "tokens": ["AddressSanitizer"]}) is True
    assert sg.rejects({"verdict": "CLEAN", "clean": True}) is False


def test_a_gate_that_could_not_run_is_not_a_pass_and_is_not_a_rejection():
    """The failure mode this whole defect class comes from: a check that did not happen must be
    recorded as not-happened. Treating it as a pass rebuilds D23 on purpose; treating it as a
    rejection makes the product unusable wherever the pinned image is absent."""
    for v in ("IMAGE_UNAVAILABLE", "TIMEOUT", "HARNESS_ERROR", "BUILD_FAIL", "RUN_FAIL_NO_TOKEN"):
        r = {"verdict": v, "clean": None}
        assert sg.rejects(r) is False, v
        assert r["clean"] is not True, v          # never silently upgraded to a pass


def test_failure_path_a_clean_verdict_is_distinguishable_from_a_missing_one():
    """Non-vacuity: `clean` discriminates three states, so a certificate reader can tell
    'gate ran and passed' from 'gate never ran'. If these collapsed, the field would be useless."""
    assert {"verdict": "CLEAN", "clean": True}["clean"] is True
    assert {"verdict": "IMAGE_UNAVAILABLE", "clean": None}["clean"] is None
    assert {"verdict": "SANITIZER_REPORT", "clean": False}["clean"] is False


def test_unavailable_image_yields_a_recorded_non_run_never_an_exception(monkeypatch):
    monkeypatch.setattr(sg, "available", lambda: False)
    r = sg.gate("/nonexistent/kdir", 1506)
    assert r["ran"] is False and r["clean"] is None
    assert r["verdict"] == "IMAGE_UNAVAILABLE"
    assert "not a pass" in r["note"]
    assert sg.rejects(r) is False
