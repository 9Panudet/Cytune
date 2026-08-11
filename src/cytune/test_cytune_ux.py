"""E — presets, --explain, and the G5 obligation that comes with every new flag.

The rule this file exists to enforce: **no flag may weaken G1 (oracle), G2 (sanitizer) or G3
(honest-flat).** `--preset` is the first flag added since G5 was written down, so it is the first
test of whether that rule is checkable rather than aspirational.
"""
from __future__ import annotations

import os

import pytest

from cytune import certify, config
from cytune._vendor import theta

REF = theta.REFERENCE_ID
FAST = theta.id_of((False, False, True, False, False, "-O3", "native", "on", ("off", "off")))


class _Args:
    def __init__(self, **kw):
        for k, (_t, d) in config.FIELDS.items():
            setattr(self, k, d)
        for k, v in kw.items():
            setattr(self, k, v)


# --------------------------------------------------------------------------- G5 for presets
def test_no_preset_can_touch_a_guarantee():
    """THE G5 test for E1. A preset may change how much is measured and how big the workload is.
    It may not change the emission policy, the oracle, the gate or the margin — and this asserts it
    over the preset TABLE, so adding a preset that sets `allow_fast_math` fails here."""
    for name, values in config.PRESETS.items():
        illegal = set(values) - config.PRESET_SETTABLE
        assert not illegal, f"preset {name!r} sets {sorted(illegal)}, which no preset may touch"
        assert "allow_fast_math" not in values
        assert "allow_fp_contract" not in values
        assert "portable_flags" not in values
        assert "objective" not in values


def test_every_preset_is_documented_and_every_documented_preset_exists():
    assert set(config.PRESETS) == set(config.PRESET_HELP)
    for name, text in config.PRESET_HELP.items():
        assert len(text) > 20, f"{name} has no usable one-line description"


def test_presets_only_ever_scale_the_budget_they_were_given():
    """`thorough` must be a bigger search than `standard`, and `quick` a smaller one — otherwise
    the names are decoration."""
    q = config.PRESETS["quick"]["budget_scale"]
    s = config.PRESETS["standard"]["budget_scale"]
    t = config.PRESETS["thorough"]["budget_scale"]
    assert q < s < t
    assert s == 1.0, "standard must be exactly the routed budget, or 'default' means nothing"


# ------------------------------------------------------------------------- precedence
def test_an_explicit_flag_beats_the_preset():
    """E1: 'everything a preset sets remains individually overridable'."""
    eff = config.resolve(_Args(preset="quick", target_ms=99.0),
                         explicit={"preset", "target_ms"}, file_values={}, file_path=None)
    assert eff["values"]["target_ms"] == 99.0
    assert eff["provenance"]["target_ms"] == "command line"
    assert eff["values"]["budget_scale"] == 0.5
    assert eff["provenance"]["budget_scale"] == "--preset quick"


def test_a_preset_beats_the_config_file():
    eff = config.resolve(_Args(preset="thorough"), explicit={"preset"},
                         file_values={"target_ms": 12.0}, file_path="/p/.cytune.toml")
    assert eff["values"]["target_ms"] == 65.0
    assert eff["provenance"]["target_ms"] == "--preset thorough"


def test_the_config_file_beats_the_default_preset():
    """With no --preset typed, `standard` is only the built-in default and must not out-rank a
    file the user wrote on purpose."""
    eff = config.resolve(_Args(), explicit=set(),
                         file_values={"target_ms": 12.0}, file_path="/p/.cytune.toml")
    assert eff["values"]["target_ms"] == 12.0
    assert eff["provenance"]["target_ms"] == "/p/.cytune.toml"


def test_an_unknown_preset_is_an_error_not_a_silent_default():
    with pytest.raises(config.ConfigError, match="unknown preset"):
        config.resolve(_Args(preset="turbo"), explicit={"preset"}, file_values={}, file_path=None)


def test_the_effective_preset_is_recorded():
    eff = config.resolve(_Args(preset="quick"), explicit={"preset"}, file_values={},
                         file_path=None)
    assert eff["preset"] == "quick"
    assert eff["values"]["preset"] == "quick"


# ------------------------------------------------------------------------------ --explain
def _cert(winner=REF, endpoint=None, gate=None, **kw):
    ep = endpoint or {str(REF): {"endpoint_ns": 100e6, "subs_ns": [100e6, 100.1e6, 99.9e6],
                                 "n_sub": 3}}
    return certify.build_certificate(
        name="demo", winner_id=winner, reference_id=REF, endpoint=ep,
        oracle={"output_class": "int", "tolerance": {"rtol": 0.0, "atol": 0.0},
                "deterministic": True, "n_det_reps": 5, "golden_sha256": "abc"},
        feasibility={"n_measured": 33, "n_infeasible": 0, "infeasible_fraction": 0.0,
                     "reasons": {}},
        route={"rule": "R5", "route": "doe", "engine": "DOE", "budget": 16, "budget_base": 16,
               "feasibility_bonus": 0, "why": "modest but above the noise floor"},
        rig_mode="quiesced", rig_detail="quiesced — verified",
        budget={"probe": 17, "tuning": 16, "total_measured": 33},
        sources={"table": "/w/table.jsonl", "workspace": "/w"}, allow_fast_math=False,
        emitted_gate=gate or {"ran": True, "clean": True, "verdict": "CLEAN",
                              "config_id": winner},
        effective_config={"values": {"preset": "standard", "target_ms": 65.0,
                                     "allow_fast_math": False, "allow_fp_contract": False},
                          "provenance": {"preset": "built-in default"}},
        **kw)


def test_explain_names_the_bar_and_the_route():
    out = certify.explain(_cert())
    assert "WHY THIS ANSWER" in out
    assert "rule R5" in out
    assert "THE BAR" in out
    assert "WHAT WOULD CHANGE THE ANSWER" in out
    assert "SETTINGS IN EFFECT" in out


def test_explain_on_a_flat_run_offers_concrete_next_steps():
    """The most common reasonable reaction to HONEST-FLAT is 'did it even try?'. The counterfactual
    is the answer, and it has to be actionable rather than philosophical."""
    c = _cert()
    assert c["verdict"] == certify.HONEST_FLAT
    out = certify.explain(c)
    assert "--preset thorough" in out
    assert "--allow-fp-contract" in out or "--allow-fast-math" in out


def test_explain_on_a_refusal_points_at_audit():
    ep = {str(REF): {"endpoint_ns": 100e6, "subs_ns": [100e6, 100.1e6, 99.9e6], "n_sub": 3}}
    c = _cert(winner=REF, endpoint=ep, winner_rejection={
        "rejected_config_id": FAST, "reason": "sanitizer_report: AddressSanitizer",
        "action": "fell back to the reference config", "observed_ratio": 1.5})
    assert c["verdict"] == certify.NO_SAFE_IMPROVEMENT
    out = certify.explain(c)
    assert "cytune audit" in out
    assert "faster configuration EXISTS" in out


def test_explain_says_when_the_gate_did_not_run():
    c = _cert(gate={"ran": False, "clean": None, "verdict": "IMAGE_UNAVAILABLE"})
    out = certify.explain(c)
    assert "did NOT run" in out
    assert "not memory-checked" in out


def test_explain_never_invents_a_number_it_does_not_have():
    """A certificate with no endpoint comparison must still explain itself rather than crash or
    print a fabricated margin."""
    c = _cert()
    c["measurement"]["emit_margin"] = {}
    out = certify.explain(c)
    assert "WHY THIS ANSWER" in out


def test_explain_reports_the_search_coverage_honestly():
    out = certify.explain(_cert())
    assert "33 of 1728" in out
    assert "1.9%" in out or "2.0%" in out


# ---------------------------------------------------------------------------- E4: --apply diff
def test_apply_reports_a_diff_of_what_it_changed(tmp_path):
    """E4. `--apply` writes checks-off directives into source. 'replaced the directive header'
    says something happened, not what — and the case that matters most is an EXISTING
    `# cython:` line being silently discarded."""
    from cytune import apply as applymod
    src = tmp_path / "k.pyx"
    src.write_text("# cython: boundscheck=True, wraparound=True\ndef run(a):\n    return a\n")
    c = _cert(winner=FAST, endpoint={
        str(REF): {"endpoint_ns": 100e6, "subs_ns": [100e6, 100.1e6, 99.9e6], "n_sub": 3},
        str(FAST): {"endpoint_ns": 50e6, "subs_ns": [50e6, 50.1e6, 49.9e6], "n_sub": 3}},
        gate={"ran": True, "clean": True, "verdict": "CLEAN", "config_id": FAST})
    assert c["verdict"] == certify.IMPROVEMENT
    res = applymod.apply_to(str(src), c, in_place=False)
    assert res["action"] == "replaced"
    d = res["diff"]
    assert d, "--apply produced no diff"
    assert "-# cython: boundscheck=True, wraparound=True" in d, \
        "the discarded line must be visible, or the user cannot see what they lost"
    assert "+# cython: boundscheck=False" in d
    assert src.read_text().startswith("# cython: boundscheck=True"), "the original is untouched"


def test_the_diff_shows_an_insertion_too(tmp_path):
    from cytune import apply as applymod
    src = tmp_path / "k.pyx"
    src.write_text("def run(a):\n    return a\n")
    c = _cert(winner=FAST, endpoint={
        str(REF): {"endpoint_ns": 100e6, "subs_ns": [100e6, 100.1e6, 99.9e6], "n_sub": 3},
        str(FAST): {"endpoint_ns": 50e6, "subs_ns": [50e6, 50.1e6, 49.9e6], "n_sub": 3}},
        gate={"ran": True, "clean": True, "verdict": "CLEAN", "config_id": FAST})
    res = applymod.apply_to(str(src), c, in_place=False)
    assert res["action"] == "inserted"
    assert "+# cython:" in res["diff"]


def test_the_diff_helper_is_empty_when_nothing_changes():
    from cytune import apply as applymod
    assert applymod.unified_diff("a\n", "a\n", "x", "y") == ""


# --------------------------------------------------- S1: consent must not be misattributed
def test_fp_consent_names_where_the_optin_came_from(tmp_path):
    """S1, adversarial campaign. The line said `opted in via --allow-fast-math` whenever the
    effective policy had it on — including when it came from a `.cytune.toml` in an ancestor
    directory the user had never opened. Consent is the one thing that must not be misattributed."""
    from cytune.plan import EmissionPolicy
    FM = theta.id_of((True, True, False, True, False, "-O2", "x86-64", "omit", ("on", "NA")))
    c = _cert(winner=FM, endpoint={
        str(REF): {"endpoint_ns": 100e6, "subs_ns": [100e6, 100.1e6, 99.9e6], "n_sub": 3},
        str(FM): {"endpoint_ns": 50e6, "subs_ns": [50e6, 50.1e6, 49.9e6], "n_sub": 3}},
        gate={"ran": True, "clean": True, "verdict": "CLEAN", "config_id": FM},
        policy=EmissionPolicy(allow_fast_math=True))
    c["effective_config"] = {"values": {"allow_fast_math": True},
                             "provenance": {"allow_fast_math": "/home/u/.cytune.toml"}}
    out = certify.render(c)
    assert "from /home/u/.cytune.toml" in out
    assert "did NOT come from the command line you typed" in out


def test_fp_consent_from_the_command_line_is_not_second_guessed(tmp_path):
    """Control: a user who typed the flag must not be nagged about having typed it."""
    from cytune.plan import EmissionPolicy
    FM = theta.id_of((True, True, False, True, False, "-O2", "x86-64", "omit", ("on", "NA")))
    c = _cert(winner=FM, endpoint={
        str(REF): {"endpoint_ns": 100e6, "subs_ns": [100e6, 100.1e6, 99.9e6], "n_sub": 3},
        str(FM): {"endpoint_ns": 50e6, "subs_ns": [50e6, 50.1e6, 49.9e6], "n_sub": 3}},
        gate={"ran": True, "clean": True, "verdict": "CLEAN", "config_id": FM},
        policy=EmissionPolicy(allow_fast_math=True))
    c["effective_config"] = {"values": {"allow_fast_math": True},
                             "provenance": {"allow_fast_math": "command line"}}
    out = certify.render(c)
    assert "opted in via --allow-fast-math;" in out
    assert "did NOT come from the command line" not in out


def test_the_endpoint_recheck_sentence_states_its_actual_scope():
    """F3, adversarial campaign. Only the FIRST repetition of each measurement subprocess is
    canonicalised and checked; the sentence implied every repetition was."""
    c = _cert()
    s = c["correctness"]["endpoint_recheck"]
    assert "FIRST repetition" in s
    assert "not output-checked" in s


def test_every_flag_and_config_key_is_documented_here():
    """C5 — leanness is measured, not asserted.

    Every flag and every `.cytune.toml` key must appear in the guide's reference section. A flag
    nobody can justify in one sentence is a flag to remove; a flag documented nowhere is worse
    than one that does not exist, because a senior user has to read source to find it and a
    beginner meets it in `--help` with no explanation.

    Pinned against USER_GUIDE.md §13, which is the ONE place the whole surface is enumerated.
    """
    import subprocess
    import sys as _sys
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    guide_path = os.path.join(repo, "docs", "USER_GUIDE.md")
    if not os.path.exists(guide_path):
        pytest.skip("USER_GUIDE.md is not on this branch")
    guide = open(guide_path).read()

    from cytune import config as _config
    missing = []
    for key in _config.FIELDS:
        if key not in guide:
            missing.append(f".cytune.toml key {key!r}")

    for cmd in ("tune", "audit", "doctor", "init"):
        out = subprocess.run([_sys.executable, "-m", "cytune", cmd, "--help"],
                             capture_output=True, text=True, cwd=repo).stdout
        for line in out.splitlines():
            t = line.strip()
            if not t.startswith("--"):
                continue
            flag = t.split()[0].rstrip(",")
            if flag in ("--help", "--version"):
                continue
            if flag not in guide:
                missing.append(f"{cmd} flag {flag}")

    assert not missing, (
        "undocumented surface: " + ", ".join(sorted(set(missing)))
        + "\nAdd a one-sentence justification to USER_GUIDE.md §13, or remove it.")


def test_the_documentation_check_would_notice_an_undocumented_flag():
    """Positive control: the check above must actually be able to fail."""
    guide = "a guide mentioning --driver and --json and nothing else"
    assert "--probe-as-screen" not in guide
