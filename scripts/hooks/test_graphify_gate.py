"""F1 / PREREG §12 A-4h — the graphify rebuild must defer while a campaign cycle is live.

Both paths are exercised, including the failure path: a test that only ever saw the IDLE branch
would pass just as happily against a gate that never reports BUSY at all.

The BUSY case runs against a throwaway git repo so the real results/fleet/_topup_inflight.json is
never created or touched — writing a fake in-flight marker into the live campaign tree could make
a later relaunch reconcile a cycle that never ran.
"""
import subprocess
import pytest

HERE = __import__("pathlib").Path(__file__).resolve().parent
REPO = HERE.parent.parent


def _run(script, cwd=None):
    return subprocess.run(["bash", str(script)], cwd=cwd or REPO,
                          capture_output=True, text=True)


@pytest.fixture
def fake_repo(tmp_path):
    """A minimal repo with the gate scripts in place, so the predicate resolves to tmp_path."""
    (tmp_path / "scripts" / "hooks").mkdir(parents=True)
    (tmp_path / "results" / "fleet").mkdir(parents=True)
    for name in ("campaign_busy.sh", "graphify_gate.sh"):
        (tmp_path / "scripts" / "hooks" / name).write_text((HERE / name).read_text())
    # No `git init`: the pinned images ship no git, and the gate scripts already fall back to the
    # working directory when `git rev-parse` is unavailable. Running the tests on that fallback
    # path is deliberate — it is the path a user without git would hit.
    return tmp_path


def test_busy_when_inflight_marker_present(fake_repo):
    """The marker outlives a momentary process gap — it must read BUSY on its own."""
    (fake_repo / "results" / "fleet" / "_topup_inflight.json").write_text('{"kernel_id": "x"}')
    r = _run(fake_repo / "scripts" / "hooks" / "campaign_busy.sh", cwd=fake_repo)
    assert r.returncode == 0, f"expected BUSY (0), got {r.returncode}: {r.stdout}{r.stderr}"
    assert "in-flight cycle marker" in r.stdout


def test_idle_when_no_marker_and_no_runner(fake_repo):
    r = _run(fake_repo / "scripts" / "hooks" / "campaign_busy.sh", cwd=fake_repo)
    assert r.returncode == 1, f"expected IDLE (1), got {r.returncode}: {r.stdout}"


def test_gate_queues_the_debt_and_swallows_the_rebuild_when_busy(fake_repo):
    """On BUSY the gate must exit the hook 0 (commit still succeeds) AND record the owed rebuild."""
    (fake_repo / "results" / "fleet" / "_topup_inflight.json").write_text('{"kernel_id": "x"}')
    r = subprocess.run(["bash", "-c", 'set -e; cd "$1"; . scripts/hooks/graphify_gate.sh; '
                                      'echo REBUILD_WOULD_RUN', "_", str(fake_repo)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "DEFERRED" in r.stdout
    assert "REBUILD_WOULD_RUN" not in r.stdout, "gate did not stop the hook body"
    queue = fake_repo / "graphify-out" / ".graphify_deferred"
    assert queue.exists() and queue.read_text().strip(), "owed rebuild was not recorded"


def test_gate_falls_through_to_the_rebuild_when_idle(fake_repo):
    r = subprocess.run(["bash", "-c", 'set -e; cd "$1"; . scripts/hooks/graphify_gate.sh; '
                                      'echo REBUILD_WOULD_RUN', "_", str(fake_repo)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "REBUILD_WOULD_RUN" in r.stdout, "gate blocked the rebuild while idle"
    assert "DEFERRED" not in r.stdout


def test_drain_refuses_while_a_cycle_is_live(fake_repo):
    """The drain must not become the contaminating load it exists to prevent."""
    (fake_repo / "scripts" / "hooks" / "graphify_drain.sh").write_text(
        (HERE / "graphify_drain.sh").read_text())
    (fake_repo / "results" / "fleet" / "_topup_inflight.json").write_text('{"kernel_id": "x"}')
    (fake_repo / "graphify-out").mkdir()
    (fake_repo / "graphify-out" / ".graphify_deferred").write_text("abc123\tnow\treason\n")
    r = _run(fake_repo / "scripts" / "hooks" / "graphify_drain.sh", cwd=fake_repo)
    assert r.returncode == 2, f"drain should refuse (2), got {r.returncode}: {r.stdout}"
    assert "REFUSING" in r.stdout


def test_drain_fails_closed_when_the_busy_predicate_is_unavailable(fake_repo):
    """A safety check that cannot run must refuse, not assume idle.

    Regression: the drain resolved its repo root via `git rev-parse` with no fallback. Where git
    is absent (both pinned images) the path came out empty, the predicate silently failed to
    execute, and the drain reported "nothing owed" while a cycle was in flight.
    """
    (fake_repo / "scripts" / "hooks" / "graphify_drain.sh").write_text(
        (HERE / "graphify_drain.sh").read_text())
    (fake_repo / "scripts" / "hooks" / "campaign_busy.sh").unlink()
    (fake_repo / "graphify-out").mkdir()
    (fake_repo / "graphify-out" / ".graphify_deferred").write_text("abc123\tnow\treason\n")
    r = _run(fake_repo / "scripts" / "hooks" / "graphify_drain.sh", cwd=fake_repo)
    assert r.returncode == 2, f"drain should fail closed (2), got {r.returncode}: {r.stdout}"
    assert "failing closed" in r.stdout


@pytest.mark.skipif(not (REPO / ".git" / "hooks").is_dir(),
                    reason="no .git visible (containers mount scripts/ only)")
def test_guard_is_installed_in_the_live_hook():
    """Regression: `graphify hook install` regenerates post-commit and drops the guard."""
    r = _run(REPO / "scripts" / "hooks" / "verify_graphify_gate.sh")
    assert r.returncode == 0, r.stdout + r.stderr


def test_predicate_ignores_its_own_callers_command_line(fake_repo):
    """D19: `pgrep -f` matches whole command lines, including the caller's.

    Invoking the predicate from a shell whose command line mentions `measure_wrap.sh` used to make
    it report BUSY on a completely idle box. Fails SAFE (over-reports busy) but makes the predicate
    useless as a status signal, and would make graphify_drain refuse forever.
    """
    script = fake_repo / "scripts" / "hooks" / "campaign_busy.sh"
    # the caller's command line deliberately contains the pattern the predicate greps for
    r = subprocess.run(
        ["bash", "-c", f'# measure_wrap.sh measure_child.py run_fleet.py\nbash "{script}"'],
        capture_output=True, text=True, cwd=fake_repo)
    assert r.returncode == 1, (
        f"predicate matched its own caller and reported BUSY on an idle box: {r.stdout}")


def test_predicate_still_detects_a_genuine_measurement(fake_repo):
    """Non-vacuity: the ancestry exclusion must not blind the predicate to a REAL process."""
    proc = subprocess.Popen(["bash", "-c", "exec -a measure_child.py sleep 30"])
    try:
        r = subprocess.run(["bash", str(fake_repo / "scripts" / "hooks" / "campaign_busy.sh")],
                           capture_output=True, text=True, cwd=fake_repo)
        assert r.returncode == 0, "a real measure_child process must read BUSY"
        assert "timed measurement" in r.stdout
    finally:
        proc.kill()
        proc.wait()
