"""`cytune doctor` — the checks must DISCRIMINATE, and the tiers must mean what they say.

The reason this has tests at all: doctor's whole job is to tell a user which guarantees are live
BEFORE they spend an hour measuring. A doctor that reports "ok" for a check it did not really
perform is the same defect class as D23, one layer up.
"""
from cytune import doctor as doc
from cytune import sanitize_gate


def test_blocking_and_degraded_are_different_verdicts(monkeypatch):
    """A missing image BLOCKS; a portable rig only DEGRADES. Collapsing the two would either
    refuse to run on a perfectly usable laptop, or let a blocking failure through as a warning."""
    tiers = {name: fn()[0] for name, fn in doc.CHECKS}
    assert tiers["podman"] == doc.BLOCKING
    assert tiers["pinned image"] == doc.BLOCKING
    assert tiers["measurement rig"] == doc.DEGRADED
    assert tiers["sanitizer gate"] == doc.DEGRADED


def test_sanitizer_check_fails_when_the_image_is_absent(monkeypatch):
    monkeypatch.setattr(doc, "_run", lambda cmd, timeout=30: (1, "", "no such image"))
    tier, ok, detail, fix = doc._check_sanitizer_gate()
    assert tier == doc.DEGRADED and ok is False
    assert "CANNOT RUN" in detail
    assert "NOT a pass" in fix          # the D23 distinction must survive into the user-facing text


def test_failure_path_sanitizer_check_passes_when_the_image_is_present(monkeypatch):
    """Non-vacuity: the check discriminates on the image, rather than always failing.

    D33. This used to stub only `doctor._run`, but `_check_sanitizer_gate` has a SECOND external
    dependency — `sanitize_gate.is_pinned_image()` shells out to podman on its own — so the
    assertion was really reading the host's image store. It passed on the development machine
    because the pinned image happens to be there, and failed on every machine without it, which is
    every machine a new contributor starts from. Found by running the Python 3.9-3.13 matrix cell
    the launch pass had left unrun: six interpreters, one identical failure, none of it about
    Python. Both dependencies are stubbed now, so the test is about the code again.
    """
    monkeypatch.setattr(doc, "_run", lambda cmd, timeout=30: (0, "", ""))
    monkeypatch.setattr(sanitize_gate, "is_pinned_image", lambda: True)
    tier, ok, _d, fix = doc._check_sanitizer_gate()
    assert ok is True and fix == ""


def test_an_image_that_exists_but_is_not_the_pinned_one_is_not_a_pass(monkeypatch):
    """The other half of the branch, and it had no test at the doctor layer at all: podman has AN
    image under the pinned name, and its digest is somebody else's. That is H6 — `podman tag stub
    localhost/motifbo-env:phase1` — arriving at the one check whose job is to tell a user before
    they spend an hour measuring."""
    monkeypatch.setattr(doc, "_run", lambda cmd, timeout=30: (0, "", ""))
    monkeypatch.setattr(sanitize_gate, "is_pinned_image", lambda: False)
    tier, ok, detail, fix = doc._check_sanitizer_gate()
    assert tier == doc.DEGRADED and ok is False
    assert "NOT the pinned toolchain" in detail
    assert "--apply refuses" in fix


def test_blocking_failure_makes_doctor_exit_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(doc, "CHECKS",
                        [("x", lambda: (doc.BLOCKING, False, "broken", "fix it"))])
    assert doc.doctor() == 1
    assert "BLOCKED" in capsys.readouterr().out


def test_degraded_only_still_exits_zero_but_says_so(monkeypatch, capsys):
    """Degraded must not block — refusing to run where the tool is still useful would push users
    to work around the check entirely, which is worse than a stated weaker guarantee."""
    monkeypatch.setattr(doc, "CHECKS",
                        [("x", lambda: (doc.DEGRADED, False, "portable", "run host_prep"))])
    assert doc.doctor() == 0
    out = capsys.readouterr().out
    assert "degraded guarantee" in out and "silently ignored" in out


def test_every_failing_check_names_a_fix():
    """A failure with no remedy is a dead end for the user."""
    for name, fn in doc.CHECKS:
        tier, ok, _detail, fix = fn()
        if not ok:
            assert fix.strip(), f"{name} failed with no suggested fix"
