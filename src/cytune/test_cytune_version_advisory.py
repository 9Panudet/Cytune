"""The 1.0.0 advisory — a released version whose certificates this one refuses to reproduce.

1.0.0 is published. It could certify `IMPROVEMENT` on a run where the correctness oracle had no
power to fail (D26), on a workload its own module hash had invalidated (D28), and on a calibration
that missed its target by 215x (D30). 1.1.0 refuses all three, which means a 1.0.0 certificate is
not merely older -- it may be a confident wrong answer that this build would never have produced.

This project's rule is that a claim known to be unsound cannot be left standing unmarked. The
CHANGELOG carries the written advisory; these tests pin the RUNTIME half, so a user who never reads
a changelog still meets it at the moment it matters.

WHY THE ANTI-VACUITY TEST IS THE IMPORTANT ONE HERE. A version ceiling is a comparison, and a
comparison written the wrong way round warns about everything or nothing. Either failure is
invisible in a test suite that only ever feeds it 1.0.0, so the shipping version and a future
version are both checked explicitly.
"""
from __future__ import annotations

import ast
import json
import os

from cytune import __version__, certify

HERE = os.path.dirname(os.path.abspath(__file__))


def _cert(version):
    return {"schema": "cytune-certificate/1.0", "cytune_version": version,
            "module": "demo", "verdict": "improvement", "speedup": 1.5}


# ------------------------------------------------------------------ the ceiling, both directions
def test_a_1_0_0_certificate_gets_the_advisory():
    """Positive control: the version the advisory exists for."""
    assert certify.version_advisory(_cert("1.0.0")) is not None


def test_the_release_candidates_of_1_0_0_are_covered_too():
    """`1.0.0rc0`/`rc1` carry the same defects; a suffix must not buy an exemption."""
    for v in ("1.0.0rc0", "1.0.0rc1", "1.0.0-rc1", "0.9.0"):
        assert certify.version_advisory(_cert(v)) is not None, v


def test_the_shipping_version_is_not_advised_against():
    """ANTI-VACUITY. If this fired, every certificate cytune writes would warn about itself, and
    the advisory would mean nothing. It is asserted against `__version__` rather than a literal so
    it keeps holding across the next bump."""
    assert certify.version_advisory(_cert(__version__)) is None


def test_a_future_version_is_not_advised_against():
    for v in ("1.1.0", "1.2.3", "2.0.0", "10.0.0"):
        assert certify.version_advisory(_cert(v)) is None, v


def test_an_unparseable_version_is_not_guessed_at():
    """Silence, not a warning. The advisory is a statement about specific released versions; firing
    it at something we cannot place would be an overclaim of exactly the kind this project refuses
    everywhere else."""
    for v in ("banana", "", None, 1.0, {"1": "0"}):
        assert certify.version_advisory({"cytune_version": v}) is None, repr(v)
    assert certify.version_advisory({}) is None
    assert certify.version_advisory(None) is None


# --------------------------------------------------------------------------- what it actually says
def test_the_advisory_names_the_defects_and_the_user_action():
    """A notice that says "this is old" tells a user nothing to do. This one has to name what was
    wrong and what to check in their own source."""
    text = certify.version_advisory(_cert("1.0.0"))
    for token in ("D26", "D28", "D30", "1.0.0", "--apply", "# cython:", "CHANGELOG.md"):
        assert token in text, token
    assert "supersedes" in text


# -------------------------------------------------------------------------------- the disk read
def test_it_reads_the_certificate_an_earlier_run_left_in_the_workspace(tmp_path):
    with open(tmp_path / "certificate.json", "w") as f:
        json.dump(_cert("1.0.0"), f)
    assert certify.prior_certificate_advisory(str(tmp_path)) is not None


def test_a_current_certificate_in_the_workspace_is_silent(tmp_path):
    with open(tmp_path / "certificate.json", "w") as f:
        json.dump(_cert(__version__), f)
    assert certify.prior_certificate_advisory(str(tmp_path)) is None


def test_no_certificate_at_all_is_silent(tmp_path):
    assert certify.prior_certificate_advisory(str(tmp_path)) is None
    assert certify.prior_certificate_advisory(str(tmp_path / "nope")) is None


def test_a_malformed_certificate_does_not_abort_the_run(tmp_path):
    """The failure path that matters operationally. A leftover document from a previous version is
    the least trustworthy file in the directory, and the user came here to tune a kernel -- a
    truncated or hand-edited certificate must not take the run down with it."""
    for junk in ("", "{", "not json at all", '{"cytune_version": ', "\x00\x01"):
        with open(tmp_path / "certificate.json", "w") as f:
            f.write(junk)
        assert certify.prior_certificate_advisory(str(tmp_path)) is None, repr(junk)


def test_a_directory_where_the_certificate_should_be_is_survivable(tmp_path):
    os.mkdir(tmp_path / "certificate.json")
    assert certify.prior_certificate_advisory(str(tmp_path)) is None


# ------------------------------------------------------------------------------- reachability
def test_the_cli_actually_calls_it():
    """D25's lesson applied to a new function: a check nobody invokes prints nothing, and its
    silence is indistinguishable from its success. Parsed rather than grepped so a mention in a
    comment or a docstring cannot satisfy it."""
    tree = ast.parse(open(os.path.join(HERE, "cli.py")).read())
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "prior_certificate_advisory" in called, (
        "cli.py no longer calls certify.prior_certificate_advisory — the 1.0.0 advisory is dead "
        "code and a user re-running in a 1.0.0 workspace is told nothing.")
