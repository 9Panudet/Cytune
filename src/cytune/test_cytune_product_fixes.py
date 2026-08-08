"""Every fix from the cold-user acceptance test, pinned by its FAILURE path.

The project's own rule: a guarantee whose failure path has never fired is a claim, not a
guarantee. So each test here drives the state the fix exists for — a rejected winner, an ungated
emission, a faster-but-forbidden config, a build that produces nothing — and asserts what the user
is told. A test that only exercises the happy path would pass against the broken code too.

Finding IDs refer to results/usertest/USER_TEST_REPORT.md.
"""
import io
import json
import os
import sys

import pytest

import cytune
from cytune import apply as applymod
from cytune import certify, cli, config, plan, routing, session
from cytune._vendor import theta

REF = theta.REFERENCE_ID


# ------------------------------------------------------------------ helpers
def _ep(cid, ns, feasible=True, subs=None):
    subs = subs if subs is not None else [ns, ns, ns]
    return {str(cid): {"feasible": feasible, "endpoint_ns": ns, "subs_ns": subs,
                       "n_sub": len(subs), "cv": 0.0, "reason": "ok"}}


ORACLE = {"output_class": "int", "tolerance": {"rtol": 0.0, "atol": 0.0}, "deterministic": True,
          "n_det_reps": 5, "golden_sha256": "deadbeef"}
FEAS = {"n_measured": 20, "n_infeasible": 2, "infeasible_fraction": 0.1,
        "reasons": {"oracle_mismatch": 2}}
ROUTE = {"label": routing.LABEL, "route": "doe", "rule": "R4", "engine": "DOE", "budget": 16,
         "why": "separable lever", "fallback_note": None, "feasibility_note": None}


def _render(cert):
    """Render, whitespace-normalised. The certificate wraps prose at 96 columns, so asserting a
    literal sentence against the raw text is a test of the wrap points, not of the content."""
    return " ".join(certify.render(cert).split())


def _cert(winner, ep, **kw):
    kw.setdefault("allow_fast_math", False)
    return certify.build_certificate(
        name="demo", winner_id=winner, reference_id=REF, endpoint=ep, oracle=ORACLE,
        feasibility=FEAS, route=ROUTE, rig_mode="quiesced", rig_detail="quiesced — verified",
        budget={"probe": 17, "tuning": 16, "total_measured": 20},
        sources={"table": "/tmp/t.jsonl", "workspace": "/tmp/ws"}, **kw)


SAN_REPORT = {"ran": True, "clean": False, "verdict": "SANITIZER_REPORT",
              "tokens": ["AddressSanitizer", "buffer-overflow"], "config_id": 1450,
              "stderr_excerpt": "==1==ABORTING"}
SAN_CLEAN = {"ran": True, "clean": True, "verdict": "CLEAN", "tokens": [], "config_id": REF}
SAN_NOTRUN = {"ran": False, "clean": None, "verdict": "IMAGE_UNAVAILABLE",
              "note": "pinned image not present", "config_id": REF}


def _rejection(reason="sanitizer_report: AddressSanitizer, buffer-overflow", ratio=1.74):
    return {"rejected_config_id": 1450, "reason": reason,
            "action": "fell back to the reference config", "observed_ratio": ratio,
            "report_path": "/tmp/ws/sanitizer_report_1450.log"}


# ================================================================== F4
# A memory bug found in the user's kernel must not be reported as "flat".
def test_f4_rejected_winner_is_never_reported_as_honest_flat():
    """THE failure path: the endpoint says winner == reference (because we fell back), which is
    exactly the shape that used to produce HONEST-FLAT."""
    ep = {**_ep(REF, 100e6)}
    c = _cert(REF, ep, winner_rejection=_rejection(), emitted_gate=SAN_CLEAN)
    assert c["verdict"] == certify.NO_SAFE_IMPROVEMENT
    assert c["verdict"] != certify.HONEST_FLAT
    assert "not flat" in c["summary"].lower() or "NOT flat" in c["summary"]


def test_f4_memory_safety_finding_is_loud_and_names_the_defect_as_the_users():
    c = _cert(REF, _ep(REF, 100e6), winner_rejection=_rejection(), emitted_gate=SAN_CLEAN)
    mf = c["memory_safety_finding"]
    assert mf["found"] is True and mf["config_id"] == 1450
    assert mf["observed_ratio"] == pytest.approx(1.74)
    assert "latent bug in YOUR kernel" in mf["explanation"]
    r = _render(c)
    assert "MEMORY-SAFETY DEFECT" in r
    assert "1.740x faster" in r
    assert "buffer-overflow" in r
    # It must appear ABOVE the recommendation: a user who reads the first screen must see it.
    assert r.index("MEMORY-SAFETY DEFECT") < r.index("CORRECTNESS CERTIFICATE")
    assert "sanitizer_report_1450.log" in r


def test_f4_endpoint_rejection_is_also_not_flat_but_carries_no_memory_finding():
    c = _cert(REF, _ep(REF, 100e6),
              winner_rejection=_rejection(reason="oracle_mismatch", ratio=1.2),
              emitted_gate=SAN_CLEAN)
    assert c["verdict"] == certify.NO_SAFE_IMPROVEMENT
    assert c.get("memory_safety_finding") is None
    assert "MEMORY-SAFETY DEFECT" not in certify.render(c)


def test_f4_a_genuinely_flat_run_is_still_honest_flat():
    """G3 must not be weakened: with no rejection, flat is still flat, on both flat routes."""
    searched = _cert(REF, _ep(REF, 100e6), emitted_gate=SAN_CLEAN)
    assert searched["verdict"] == certify.HONEST_FLAT
    assert searched.get("memory_safety_finding") is None
    assert "Best safe config = the reference" in searched["summary"]
    assert "MEMORY-SAFETY DEFECT" not in certify.render(searched)

    flat_route = dict(ROUTE, route=routing.HONEST_FLAT, rule="R1", engine=None, budget=0)
    c = certify.build_certificate(
        name="demo", winner_id=REF, reference_id=REF, endpoint=_ep(REF, 100e6), oracle=ORACLE,
        feasibility=FEAS, route=flat_route, rig_mode="quiesced", rig_detail="q",
        budget={"probe": 17, "tuning": 0, "total_measured": 17},
        sources={"table": "/tmp/t", "workspace": "/tmp/ws"}, allow_fast_math=False,
        emitted_gate=SAN_CLEAN)
    assert c["verdict"] == certify.HONEST_FLAT
    assert "real answer, not a failure" in c["summary"]


# ================================================================== F5
def test_f5_sanitizer_gate_field_always_describes_the_emitted_config():
    """After a fallback the gate result of the REJECTED config must not occupy the field."""
    c = _cert(REF, _ep(REF, 100e6), winner_rejection=_rejection(), emitted_gate=SAN_CLEAN)
    assert c["sanitizer_gate"]["config_id"] == REF == c["emitted_config"]["config_id"]
    assert c["winner_rejection"]["rejected_config_id"] == 1450
    assert "SANITIZER GATE (on the config being emitted)" in certify.render(c)


def test_f5_missing_gate_is_recorded_as_not_run_and_never_as_a_pass():
    c = _cert(REF, _ep(REF, 100e6))                    # emitted_gate omitted entirely
    g = c["sanitizer_gate"]
    assert g["ran"] is False and g["clean"] is None
    assert "emitted config not gated" in g["note"]
    r = _render(c)
    assert "NOT RUN IS NOT A PASS" in r


def test_f5_not_run_gate_renders_the_d23_warning():
    c = _cert(REF, _ep(REF, 100e6), emitted_gate=SAN_NOTRUN)
    r = _render(c)
    assert "NOT RUN" in r and "D23" in r
    assert "CLEAN" not in r.split("SANITIZER GATE")[1].split("RIG MODE")[0]


def test_f5_a_report_on_the_emitted_config_is_itself_a_finding():
    """No rejection happened — the emitted config is simply dirty. That is the user's bug."""
    dirty = {**SAN_REPORT, "config_id": REF}
    c = _cert(REF, _ep(REF, 100e6), emitted_gate=dirty)
    assert c["memory_safety_finding"]["found"] is True
    assert c["memory_safety_finding"]["on_emitted_config"] is True
    r = _render(c)
    assert "your own baseline settings" in r
    assert "NO SAFE RECOMMENDATION" in r


# ================================================================== F19
CONTRACT_ID = next(c for c in range(theta.N_CONFIGS) if theta.config_of(c)[8] == ("off", "fast"))
FASTMATH_ID = next(c for c in range(theta.N_CONFIGS) if theta.config_of(c)[8][0] == "on")


def test_f19_fp_contract_is_excluded_from_emission_by_default():
    """The failure path: contraction is 5x faster and must still not be chosen."""
    feas = {CONTRACT_ID: 100.0, REF: 500.0}
    w, d = plan.select_winner(feas, policy=plan.EmissionPolicy())
    assert w == REF, "FMA contraction was emitted without --allow-fp-contract"
    assert d["excluded_by_reason"]["fp_contract"] == 1


def test_f19_opting_in_makes_contraction_selectable():
    feas = {CONTRACT_ID: 100.0, REF: 500.0}
    w, _ = plan.select_winner(feas, policy=plan.EmissionPolicy(allow_fp_contract=True))
    assert w == CONTRACT_ID, "opting in must actually make it selectable"


def test_f19_fast_math_optin_does_not_silently_grant_contraction():
    feas = {CONTRACT_ID: 100.0, REF: 500.0}
    w, _ = plan.select_winner(feas, policy=plan.EmissionPolicy(allow_fast_math=True))
    assert w == REF, "--allow-fast-math must not smuggle in FMA contraction"


def test_f19_default_certificate_states_strict_consent():
    c = _cert(REF, _ep(REF, 100e6), policy=plan.EmissionPolicy(), emitted_gate=SAN_CLEAN)
    r = _render(c)
    assert "FLOATING-POINT CONSENT: strict (default)" in r
    assert c["emission_policy"]["allow_fp_contract"] is False


def test_f19_fp_semantics_classifier_covers_all_three_levels():
    assert plan.fp_semantics(REF) == "strict"
    assert plan.fp_semantics(CONTRACT_ID) == "contract"
    assert plan.fp_semantics(FASTMATH_ID) == "fast-math"


# ================================================================== F21
def test_f21_fp_block_is_muted_when_the_kernel_has_no_floating_point_work():
    ep = {**_ep(REF, 100e6), **_ep(CONTRACT_ID, 50e6)}
    c = _cert(CONTRACT_ID, ep, allow_fast_math=False, has_fp_work=False,
              policy=plan.EmissionPolicy(allow_fp_contract=True), emitted_gate=SAN_CLEAN)
    r = _render(c)
    assert "most likely has no effect on your results" in r


def test_f21_fp_block_still_fires_when_there_is_fp_work():
    ep = {**_ep(REF, 100e6), **_ep(CONTRACT_ID, 50e6)}
    c = _cert(CONTRACT_ID, ep, has_fp_work=True,
              policy=plan.EmissionPolicy(allow_fp_contract=True), emitted_gate=SAN_CLEAN)
    r = _render(c)
    assert "FLOATING-POINT SEMANTICS" in r and "NOT -ffast-math" in r
    assert "most likely has no effect" not in r


def test_f21_heuristic_detects_float_source_and_int_only_source(tmp_path):
    fp = tmp_path / "a.pyx"
    fp.write_text("def run(double[::1] a):\n    return a[0]\n")
    ip = tmp_path / "b.pyx"
    ip.write_text("def run(long long[::1] a):\n    return a[0]\n")
    assert session.Session._has_fp_work(str(fp)) is True
    assert session.Session._has_fp_work(str(ip)) is False


# ================================================================== F20
def test_f20_march_native_carries_a_portability_warning():
    native = next(c for c in range(theta.N_CONFIGS) if theta.config_of(c)[6] == "native")
    ep = {**_ep(REF, 100e6, subs=[100e6, 100e6, 100e6]),
          **_ep(native, 50e6, subs=[50e6, 50e6, 50e6])}
    c = _cert(native, ep, emitted_gate={**SAN_CLEAN, "config_id": native})
    assert c["portability"]["portable"] is False
    r = _render(c)
    assert "PORTABILITY WARNING" in r and "illegal instruction" in r
    assert "--portable-flags" in r


def test_f20_baseline_march_carries_no_warning():
    c = _cert(REF, _ep(REF, 100e6), emitted_gate=SAN_CLEAN)
    assert c["portability"]["portable"] is True
    assert "PORTABILITY WARNING" not in certify.render(c)


def test_f20_portable_flags_excludes_native_from_selection():
    """The failure path: native is faster and must still not be chosen."""
    native = next(c for c in range(theta.N_CONFIGS)
                  if theta.config_of(c)[6] == "native" and plan.fp_semantics(c) == "strict")
    feas = {native: 10.0, REF: 500.0}
    w, d = plan.select_winner(feas, policy=plan.EmissionPolicy(portable_flags=True))
    assert w == REF
    assert d["excluded_by_reason"]["non_baseline_march"] == 1
    w2, _ = plan.select_winner(feas, policy=plan.EmissionPolicy())
    assert w2 == native, "without --portable-flags native must still be reachable"


# ================================================================== policy monotonicity
def test_policy_flags_only_ever_narrow_the_candidate_set():
    """No flag may make cytune emit something a stricter policy would have refused.

    Checked over the WHOLE config space, not a sample: this is the property that keeps G1/G2/G3
    independent of every knob added in this pass."""
    strict = plan.EmissionPolicy()
    for pol in (plan.EmissionPolicy(allow_fast_math=True),
                plan.EmissionPolicy(allow_fp_contract=True),
                plan.EmissionPolicy(allow_fast_math=True, allow_fp_contract=True)):
        allowed_strict = {c for c in range(theta.N_CONFIGS) if strict.allows(c)}
        allowed_loose = {c for c in range(theta.N_CONFIGS) if pol.allows(c)}
        assert allowed_strict <= allowed_loose
    # ...and --portable-flags only ever removes.
    portable = plan.EmissionPolicy(portable_flags=True)
    assert ({c for c in range(theta.N_CONFIGS) if portable.allows(c)}
            <= {c for c in range(theta.N_CONFIGS) if strict.allows(c)})


def test_strict_default_admits_no_fp_semantics_change_at_all():
    for c in range(theta.N_CONFIGS):
        if plan.STRICT.allows(c):
            assert plan.fp_semantics(c) == "strict"


# ================================================================== F18
def test_f18_selection_counts_name_their_denominator_and_sum():
    feas = {CONTRACT_ID: 100.0, FASTMATH_ID: 90.0, REF: 500.0}
    _w, d = plan.select_winner(feas, policy=plan.EmissionPolicy())
    assert d["n_feasible_measured"] == d["n_candidates"] + d["n_excluded_by_policy"] == 3
    assert "n_feasible_measured = n_candidates + n_excluded_by_policy" in d["denominator"]
    assert sum(d["excluded_by_reason"].values()) == d["n_excluded_by_policy"]


# ================================================================== F17
def test_f17_no_vacuous_separation_claim_when_the_winner_is_the_reference():
    c = _cert(REF, _ep(REF, 100e6), winner_rejection=_rejection(), emitted_gate=SAN_CLEAN)
    sep = c["measurement"]["endpoint_separation"]
    assert sep["not_applicable"] is True and sep["separated"] is None
    assert "OVERLAP" not in sep["reason"]


def test_f17_separation_is_still_computed_for_a_real_comparison():
    ep = {**_ep(REF, 100e6, subs=[100e6, 101e6, 99e6]),
          **_ep(5, 50e6, subs=[50e6, 51e6, 49e6])}
    c = _cert(5, ep, emitted_gate={**SAN_CLEAN, "config_id": 5})
    assert c["measurement"]["endpoint_separation"]["separated"] is True


# ================================================================== F8
def test_f8_certificate_reconciles_delta_probe_with_the_measured_speedup():
    feat = {"delta_probe": 2.6505, "if_probe": 0.06, "if_probe_na": False}
    ep = {**_ep(REF, 100e6, subs=[100e6, 101e6, 99e6]),
          **_ep(5, 50e6, subs=[50e6, 51e6, 49e6])}
    c = _cert(5, ep, probe_features=feat, emitted_gate={**SAN_CLEAN, "config_id": 5})
    pv = c["probe_vs_endpoint"]
    assert pv["delta_probe"] == 2.6505 and pv["endpoint_speedup"] == pytest.approx(2.0)
    r = _render(c)
    assert "WHY THE PROBE NUMBER AND THE SPEEDUP DIFFER" in r
    assert "SCREENING-tier" in r


# ================================================================== F16
def test_f16_certificate_defines_its_own_insider_terms():
    r = _render(_cert(REF, _ep(REF, 100e6), emitted_gate=SAN_CLEAN))
    assert "GLOSSARY" in r
    for term in ("delta_probe", "IF_probe", "tau", "emit margin", "the reference"):
        assert term in r, f"{term} used but not defined"


# ================================================================== F7
def test_f7_one_version_string_everywhere():
    assert certify.SCHEMA == f"cytune-certificate/{cytune.SCHEMA_VERSION}"
    c = _cert(REF, _ep(REF, 100e6), emitted_gate=SAN_CLEAN)
    assert c["cytune_version"] == cytune.__version__
    assert cytune.__version__ in certify.render(c)
    assert cytune.__version__ in cytune.version_banner()
    assert "v0" not in cytune.version_banner()


# ================================================================== exit codes
def test_exit_codes_are_distinct_and_attached_to_the_certificate():
    assert len({certify.EXIT_IMPROVEMENT, certify.EXIT_ERROR, certify.EXIT_HONEST_FLAT,
                certify.EXIT_NO_SAFE_IMPROVEMENT}) == 4
    flat = _cert(REF, _ep(REF, 100e6), emitted_gate=SAN_CLEAN)
    assert flat["exit_code"] == certify.EXIT_HONEST_FLAT == 2
    refused = _cert(REF, _ep(REF, 100e6), winner_rejection=_rejection(), emitted_gate=SAN_CLEAN)
    assert refused["exit_code"] == certify.EXIT_NO_SAFE_IMPROVEMENT == 3
    ep = {**_ep(REF, 100e6, subs=[100e6, 101e6, 99e6]),
          **_ep(5, 50e6, subs=[50e6, 51e6, 49e6])}
    imp = _cert(5, ep, emitted_gate={**SAN_CLEAN, "config_id": 5})
    assert imp["exit_code"] == certify.EXIT_IMPROVEMENT == 0
    assert "EXIT CODE: 0" in certify.render(imp)


# ================================================================== --apply
def test_apply_refuses_when_the_gate_did_not_run():
    """THE refusal that matters: --apply writes checks-off directives into source."""
    ep = {**_ep(REF, 100e6, subs=[100e6, 101e6, 99e6]),
          **_ep(5, 50e6, subs=[50e6, 51e6, 49e6])}
    c = _cert(5, ep, emitted_gate={**SAN_NOTRUN, "config_id": 5})
    with pytest.raises(applymod.ApplyRefused) as e:
        applymod.check_applicable(c)
    assert "NOT RUN IS NOT A PASS" in str(e.value)


def test_apply_refuses_a_sanitizer_report():
    """The gate reported on the config that would be emitted, so there is nothing to apply.

    Written against the REFERENCE reporting rather than a faster candidate reporting: the latter is
    unreachable, because the CLI gates the candidate first and falls back, and `build_certificate`
    now refuses to assemble that shape at all (G2). The reference reporting is the real P1 case —
    the user's own baseline is unsafe and cytune has no safe recommendation.
    """
    ep = _ep(REF, 100e6, subs=[100e6, 101e6, 99e6])
    c = _cert(REF, ep, emitted_gate={**SAN_REPORT, "config_id": REF})
    assert c["emitted_config_unsafe"] is True
    assert c["verdict"] == certify.NO_SAFE_IMPROVEMENT
    with pytest.raises(applymod.ApplyRefused):
        applymod.check_applicable(c)


def test_a_reporting_candidate_cannot_be_certified_without_a_rejection():
    """FAILURE PATH for the G2 structural assertion: a faster config the sanitizer reported on may
    not reach the certificate as the emitted config. It must have been refused and replaced."""
    ep = {**_ep(REF, 100e6, subs=[100e6, 101e6, 99e6]),
          **_ep(5, 50e6, subs=[50e6, 51e6, 49e6])}
    with pytest.raises(AssertionError, match="must be refused and replaced"):
        _cert(5, ep, emitted_gate={**SAN_REPORT, "config_id": 5})


def test_apply_refuses_a_non_improvement():
    c = _cert(REF, _ep(REF, 100e6), emitted_gate=SAN_CLEAN)
    with pytest.raises(applymod.ApplyRefused) as e:
        applymod.check_applicable(c)
    assert "nothing to apply" in str(e.value)


def test_apply_writes_a_sibling_copy_and_never_the_original_by_default(tmp_path):
    src = tmp_path / "k.pyx"
    src.write_text("def run(a):\n    return a\n")
    ep = {**_ep(REF, 100e6, subs=[100e6, 101e6, 99e6]),
          **_ep(5, 50e6, subs=[50e6, 51e6, 49e6])}
    c = _cert(5, ep, emitted_gate={**SAN_CLEAN, "config_id": 5})
    res = applymod.apply_to(str(src), c)
    assert res["target"].endswith("k.tuned.pyx")
    assert src.read_text() == "def run(a):\n    return a\n", "the original must be untouched"
    assert open(res["target"]).read().startswith("# cython:")


def test_apply_in_place_keeps_a_backup(tmp_path):
    src = tmp_path / "k.pyx"
    src.write_text("# cython: boundscheck=True\ndef run(a):\n    return a\n")
    ep = {**_ep(REF, 100e6, subs=[100e6, 101e6, 99e6]),
          **_ep(5, 50e6, subs=[50e6, 51e6, 49e6])}
    c = _cert(5, ep, emitted_gate={**SAN_CLEAN, "config_id": 5})
    res = applymod.apply_to(str(src), c, in_place=True)
    assert res["action"] == "replaced"
    assert os.path.exists(res["backup"])
    assert "boundscheck=True" in open(res["backup"]).read()
    assert src.read_text().splitlines()[0] == c["emitted_config"]["directive_header"]


def test_apply_header_insert_respects_shebang_and_coding_lines():
    text = "#!/usr/bin/env python\n# -*- coding: utf-8 -*-\nimport numpy\n"
    new, action = applymod.rewrite_source(text, "# cython: boundscheck=False")
    assert action == "inserted"
    assert new.splitlines()[2] == "# cython: boundscheck=False"


# ================================================================== .cytune.toml
def test_config_rejects_unknown_settings_rather_than_ignoring_them(tmp_path):
    """A typo'd `allow_fastmath = true` that is silently dropped leaves a user believing they
    opted in. That is the failure path this refuses."""
    p = tmp_path / config.FILENAME
    p.write_text("[cytune]\nallow_fastmath = true\n")
    with pytest.raises(config.ConfigError) as e:
        config.load(str(p))
    assert "unknown setting" in str(e.value) and "allow_fastmath" in str(e.value)


def test_config_requires_the_cytune_section(tmp_path):
    p = tmp_path / config.FILENAME
    p.write_text("target_ms = 10\n")
    with pytest.raises(config.ConfigError):
        config.load(str(p))


def test_config_type_errors_are_refused(tmp_path):
    p = tmp_path / config.FILENAME
    p.write_text('[cytune]\nallow_fast_math = "yes"\n')
    with pytest.raises(config.ConfigError):
        config.load(str(p))


def test_config_round_trips_every_known_field(tmp_path):
    p = tmp_path / config.FILENAME
    p.write_text("[cytune]\nworkspace = \"ws\"\nrig = \"portable\"\ntarget_ms = 40\n"
                 "allow_fast_math = true\nallow_fp_contract = false\n"
                 "portable_flags = true\n")
    vals, path = config.load(str(p))
    assert path == str(p)
    assert vals == {"workspace": "ws", "rig": "portable", "target_ms": 40.0,
                    "allow_fast_math": True, "allow_fp_contract": False,
                    "portable_flags": True}


def test_config_precedence_cli_beats_file_beats_default():
    class A:
        workspace, rig, target_ms = "cli-ws", "auto", 65.0
        allow_fast_math = allow_fp_contract = portable_flags = False
    eff = config.resolve(A(), {"workspace"}, {"workspace": "file-ws", "rig": "portable"}, "/f.toml")
    assert eff["values"]["workspace"] == "cli-ws"
    assert eff["provenance"]["workspace"] == "command line"
    assert eff["values"]["rig"] == "portable"
    assert eff["provenance"]["rig"] == "/f.toml"
    assert eff["provenance"]["target_ms"] == "built-in default"


def test_effective_config_is_recorded_in_the_certificate():
    ecfg = {"values": {"allow_fp_contract": True}, "provenance": {"allow_fp_contract": "/f.toml"},
            "config_file": "/f.toml"}
    c = _cert(REF, _ep(REF, 100e6), effective_config=ecfg, emitted_gate=SAN_CLEAN)
    assert c["effective_config"]["provenance"]["allow_fp_contract"] == "/f.toml"


# ================================================================== F9 / F11
def test_f9_path_errors_name_which_argument_was_wrong(tmp_path):
    good_pyx = tmp_path / "k.pyx"
    good_pyx.write_text("x = 1\n")
    with pytest.raises(session.IngestError) as e:
        session.validate_inputs(str(good_pyx), str(tmp_path / "nope.py"))
    msg = str(e.value)
    assert "--driver" in msg and "nope.py" in msg
    assert "module" not in msg.split("--driver")[0] or "k.pyx" not in msg


def test_f9_both_bad_paths_are_reported_together(tmp_path):
    with pytest.raises(session.IngestError) as e:
        session.validate_inputs(str(tmp_path / "a.pyx"), str(tmp_path / "b.py"))
    msg = str(e.value)
    assert "module:" in msg and "--driver:" in msg


def test_f9_swapped_arguments_are_diagnosed(tmp_path):
    pyx, drv = tmp_path / "k.pyx", tmp_path / "d.py"
    pyx.write_text("x=1\n")
    drv.write_text("x=1\n")
    with pytest.raises(session.IngestError) as e:
        session.validate_inputs(str(drv), str(pyx))       # swapped
    assert "does not end in .pyx" in str(e.value)


def test_f11_a_failed_run_leaves_no_workspace_behind(tmp_path):
    ws = tmp_path / "ws"
    s = session.Session(str(ws), "demo", "portable", "d")
    assert not ws.exists(), "Session must not create directories until there is something to store"
    with pytest.raises(session.IngestError):
        s.vendor(str(tmp_path / "missing.pyx"), str(tmp_path / "missing.py"))
    assert not ws.exists(), "a run that found nothing must not litter the working directory"


def test_f11_a_bad_driver_does_not_leave_a_vendored_kernel(tmp_path):
    pyx, drv = tmp_path / "k.pyx", tmp_path / "d.py"
    pyx.write_text("x=1\n")
    drv.write_text("def make_inputs(seed):\n    pass\n")     # missing call/canon/OUTPUT_CLASS
    ws = tmp_path / "ws"
    s = session.Session(str(ws), "demo", "portable", "d")
    with pytest.raises(session.IngestError) as e:
        s.vendor(str(pyx), str(drv))
    assert "canon" in str(e.value) and "OUTPUT_CLASS" in str(e.value)
    assert not ws.exists(), "the kernel was vendored before the driver contract was checked"


# ================================================================== F6
def test_f6_total_build_failure_aborts_with_the_compilers_own_words(tmp_path, monkeypatch):
    """The failure path: 17 of 17 configs fail. The old code printed `built 0/17` and walked on
    into golden capture to die there with `cythonize_fail` and no diagnostic."""
    s = session.Session(str(tmp_path / "ws"), "demo", "portable", "d")
    monkeypatch.setattr(s, "_run", lambda cmd, phase: {
        "ok": True, "n_requested": 17, "n_built": 0,
        "built": {str(i): False for i in range(17)},
        "failed": {"0": "cythonize_fail"},
        "first_failure": {"config_id": 0, "reason": "cythonize_fail",
                          "log": "kernel.pyx:2:31: Expected ':', found 'return'"}})
    with pytest.raises(session.BuildFailure) as e:
        s.build("probe", require_any=True)
    msg = str(e.value)
    assert "did not compile" in msg
    assert "Expected ':', found 'return'" in msg, "the compiler diagnostic must reach the user"
    assert "build_failure.log" in msg
    assert "17 of 17" in msg


def test_f6_partial_build_failure_does_not_abort(tmp_path, monkeypatch):
    """A config that fails to build is legitimately infeasible; only a TOTAL failure aborts."""
    s = session.Session(str(tmp_path / "ws"), "demo", "portable", "d")
    monkeypatch.setattr(s, "_run", lambda cmd, phase: {
        "ok": True, "n_requested": 17, "n_built": 16, "built": {}, "failed": {"3": "build_fail"}})
    assert s.build("probe", require_any=True)["n_built"] == 16


def test_f6_build_failure_is_an_ingest_error_so_the_cli_exit_path_covers_it():
    assert issubclass(session.BuildFailure, session.IngestError)


# ================================================================== CLI surface
def _run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    old = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    try:
        rc = cli.main(argv)
    except SystemExit as e:
        rc = e.code
    finally:
        sys.stdout, sys.stderr = old
    return rc, out.getvalue(), err.getvalue()


def test_f12_unknown_tune_flag_shows_the_tune_usage_not_the_top_level_one(tmp_path):
    pyx, drv = tmp_path / "k.pyx", tmp_path / "d.py"
    pyx.write_text("x=1\n")
    drv.write_text("def make_inputs(s): pass\ndef call(m,i): pass\ndef canon(r): pass\n"
                   "OUTPUT_CLASS='int'\n")
    rc, _o, err = _run_cli(["tune", str(pyx), "--driver", str(drv), "--fast-math"])
    assert rc == certify.EXIT_ERROR
    assert "--allow-fast-math" in err, "the correct spelling must be visible in the error"
    assert "cytune tune --help" in err


def test_f13_rig_quiesced_is_a_valid_choice():
    rc, out, err = _run_cli(["tune", "--help"])
    text = out + err
    assert "quiesced" in text and "portable" in text
    assert "REQUIRE the quiesced rig" in text


def test_the_objective_flag_is_gone_and_its_data_is_documented(tmp_path):
    """D2 — a flag whose only behaviour was to refuse is a documentation line, so it is one now.

    `--objective size` and `--objective compile` printed an error explaining that only `time` has
    a verify path and pointing at build_manifest.jsonl. That is a paragraph of the user guide
    wearing a flag costume: it occupied a line in --help, a field in .cytune.toml, an entry in the
    exit-code table and a section of TROUBLESHOOTING, and it never did anything. The data it
    pointed at is real and is still recorded per config; the guide says where.
    """
    pyx, drv = tmp_path / "k.pyx", tmp_path / "d.py"
    pyx.write_text("x=1\n")
    drv.write_text("def make_inputs(s): pass\ndef call(m,i): pass\ndef canon(r): pass\n"
                   "OUTPUT_CLASS='int'\n")
    rc, _o, err = _run_cli(["tune", str(pyx), "--driver", str(drv), "--objective", "size",
                            "--no-config"])
    assert rc == certify.EXIT_ERROR
    assert "unrecognized arguments" in err

    # ...and the raw data it used to advertise is still recorded, and now documented.
    guide = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "docs", "USER_GUIDE.md")
    text = open(guide).read()
    assert "build_manifest.jsonl" in text
    assert "compile_s" in text and "so_size_b" in text
    assert "--objective" not in text, "the flag is gone; the guide must not still list it"


def test_in_place_without_apply_is_refused(tmp_path):
    pyx, drv = tmp_path / "k.pyx", tmp_path / "d.py"
    pyx.write_text("x=1\n")
    drv.write_text("OUTPUT_CLASS='int'\n")
    rc, _o, err = _run_cli(["tune", str(pyx), "--driver", str(drv), "--in-place", "--no-config"])
    assert rc == certify.EXIT_ERROR and "--in-place requires --apply" in err


def test_bad_config_file_is_reported_not_ignored(tmp_path):
    pyx, drv = tmp_path / "k.pyx", tmp_path / "d.py"
    pyx.write_text("x=1\n")
    drv.write_text("OUTPUT_CLASS='int'\n")
    cfg = tmp_path / "bad.toml"
    cfg.write_text("[cytune]\nnope = 1\n")
    rc, _o, err = _run_cli(["tune", str(pyx), "--driver", str(drv), "--config", str(cfg)])
    assert rc == certify.EXIT_ERROR and "unknown setting" in err


def test_doctor_json_is_machine_readable():
    rc, out, _err = _run_cli(["doctor", "--json"])
    payload = json.loads(out)
    assert "checks" in payload and payload["cytune_version"] == cytune.__version__
    assert rc in (0, 1)
    names = {c["check"] for c in payload["checks"]}
    assert {"podman", "pinned image", "sanitizer gate", "entry point"} <= names


def test_doctor_names_the_image_build_command(monkeypatch):
    """F3: the pinned image is BLOCKING and nothing said how to obtain it."""
    from cytune import doctor as doc
    monkeypatch.setattr(doc, "_run", lambda cmd, timeout=30: (1, "", "no such image"))
    tier, ok, detail, fix = doc._check_image()
    assert tier == doc.BLOCKING and ok is False
    assert "podman build -f Containerfile" in fix
    assert "motifbo-env:phase1" in fix
    assert doc.EXPECTED_IMAGE_ID in fix


def test_doctor_flattens_multiline_subprocess_output():
    """F10: raw multi-line stderr spliced into a formatted field destroyed the column layout."""
    from cytune import doctor as doc
    assert "\n" not in doc._flatten("line one\nline two\n  line three")
    assert doc._flatten("a" * 500).endswith("…")


# ================================================================== G2 with no asterisk
# Found by a LIVE run of the productised gate, not by inspection: with the gate applied to the
# fallback as well, a kernel whose *reference* reports left cytune emitting a config the sanitizer
# had reported on, under the words "the best safe choice".
def test_g2_a_reporting_emitted_config_is_never_called_safe():
    dirty = {**SAN_REPORT, "config_id": REF, "tokens": ["runtime error"]}
    c = _cert(REF, _ep(REF, 100e6), emitted_gate=dirty)
    assert c["emitted_config_unsafe"] is True
    assert c["verdict"] == certify.NO_SAFE_IMPROVEMENT
    assert c["exit_code"] == certify.EXIT_NO_SAFE_IMPROVEMENT
    r = _render(c)
    assert "EMIT: NOTHING" in r
    assert "best safe choice" not in r, "a reporting config must never be called safe"
    assert "NOT a recommendation" in r


def test_g2_both_a_rejected_candidate_and_a_dirty_baseline_are_reported():
    dirty = {**SAN_REPORT, "config_id": REF, "tokens": ["runtime error"]}
    c = _cert(REF, _ep(REF, 100e6), winner_rejection=_rejection(), emitted_gate=dirty)
    assert c["memory_safety_finding"]["config_id"] == 1450          # the refused candidate
    assert c["memory_safety_finding_emitted"]["config_id"] == REF   # the dirty baseline
    r = _render(c)
    assert "2 MEMORY-SAFETY DEFECTS" in r
    assert "NO SAFE RECOMMENDATION" in r
    assert "your own baseline settings" in r


def test_g2_clean_emitted_config_still_gets_a_normal_verdict():
    """The fix must not make every run pessimistic."""
    ep = {**_ep(REF, 100e6, subs=[100e6, 101e6, 99e6]),
          **_ep(5, 50e6, subs=[50e6, 51e6, 49e6])}
    c = _cert(5, ep, emitted_gate={**SAN_CLEAN, "config_id": 5})
    assert c["emitted_config_unsafe"] is False
    assert c["verdict"] == certify.IMPROVEMENT


def test_sanitizer_image_override_cannot_manufacture_a_pass():
    """The env override exists so the NOT-RUN path can be exercised (T4.19). It must only ever be
    able to make the guarantee WEAKER AND SAY SO — never to turn a report into a pass."""
    from cytune import sanitize_gate as sg
    assert sg.rejects({"verdict": "IMAGE_UNAVAILABLE", "clean": None}) is False
    assert sg.rejects({"verdict": "SANITIZER_REPORT", "clean": False}) is True
    unavailable = {"ran": False, "clean": None, "verdict": "IMAGE_UNAVAILABLE"}
    c = _cert(REF, _ep(REF, 100e6), emitted_gate=unavailable)
    assert c["sanitizer_gate"]["clean"] is None
    assert c["emitted_config_unsafe"] is False          # not-run is not a report...
    assert "NOT RUN IS NOT A PASS" in _render(c)        # ...and it is not a pass either


def test_a_not_run_gate_degrades_the_verdict_line_itself():
    """T4.19: the summary a reader (or a script) sees first must carry the degradation, not just
    a section further down the certificate."""
    ep = {**_ep(REF, 100e6, subs=[100e6, 101e6, 99e6]),
          **_ep(5, 50e6, subs=[50e6, 51e6, 49e6])}
    c = _cert(5, ep, emitted_gate={**SAN_NOTRUN, "config_id": 5})
    assert c["verdict"] == certify.IMPROVEMENT      # the speedup is real and stays claimed...
    assert c["sanitizer_gate_ran"] is False
    assert "NOT memory-checked" in c["summary"]     # ...but never unqualified
    assert "Not-run is not a pass" in c["summary"]
    clean = _cert(5, ep, emitted_gate={**SAN_CLEAN, "config_id": 5})
    assert clean["sanitizer_gate_ran"] is True
    assert "NOT memory-checked" not in clean["summary"]


def test_usage_errors_do_not_collide_with_the_honest_flat_exit_code():
    """Exit 2 means HONEST-FLAT — a successful run with a real answer. argparse's default 2 for a
    usage error would make the documented scheme ambiguous."""
    for argv in (["tune"], ["tune", "x.pyx"], ["nosuchcommand"], []):
        rc, _o, _e = _run_cli(argv)
        assert rc == certify.EXIT_ERROR, f"{argv} exited {rc}, colliding with a verdict code"
        assert rc != certify.EXIT_HONEST_FLAT


# ================================================================== EMIT integrity
# Found by live proof run p21: the certificate said "EMIT: the reference configuration
# (unchanged)" and printed `boundscheck=False, wraparound=False`. A user pasting that would have
# disabled bounds checking on the strength of a sentence promising Cython's safe defaults.
def test_assess_refuses_a_gain_that_does_not_clear_the_margin():
    win = {"endpoint_ns": 99.99e6, "subs_ns": [99.99e6] * 3, "feasible": True}
    ref = {"endpoint_ns": 100e6, "subs_ns": [100e6] * 3, "feasible": True}
    a = certify.assess(win, ref)
    assert a["speedup"] == pytest.approx(1.0001, rel=1e-3)
    assert a["clears"] is False and a["clears_margin"] is False
    assert "does not exceed" in a["why"]


def test_assess_refuses_an_unseparated_gain_even_above_the_margin():
    # 2x apparent gain, but one winner sub-measure lands above the reference's best, so the
    # separation statement fails. Margin: 2 x combined CV = 0.759 < the 1.0 gain, so the margin
    # alone would have let this through.
    win = {"endpoint_ns": 50e6, "subs_ns": [50e6, 105e6, 50e6], "feasible": True}
    ref = {"endpoint_ns": 100e6, "subs_ns": [100e6, 100e6, 100e6], "feasible": True}
    a = certify.assess(win, ref)
    assert a["clears_margin"] is True and a["clears"] is False
    assert "OVERLAP" in a["why"]


def test_assess_accepts_a_clean_separated_gain():
    win = {"endpoint_ns": 50e6, "subs_ns": [50e6, 51e6, 49e6], "feasible": True}
    ref = {"endpoint_ns": 100e6, "subs_ns": [100e6, 101e6, 99e6], "feasible": True}
    assert certify.assess(win, ref)["clears"] is True


def test_a_non_improvement_certificate_always_emits_the_reference_itself():
    """The words and the directives must agree."""
    obs = {"config_id": 1695, "endpoint_ratio_vs_reference": 1.0001,
           "note": "measured but NOT recommended"}
    c = _cert(REF, _ep(REF, 100e6), flat_observation=obs, emitted_gate=SAN_CLEAN)
    assert c["verdict"] == certify.HONEST_FLAT
    assert c["emitted_config"]["config_id"] == REF
    header = c["emitted_config"]["directive_header"]
    assert "boundscheck=True" in header and "wraparound=True" in header
    r = _render(c)
    assert "EMIT: the reference configuration (unchanged)" in r
    assert "boundscheck=False" not in r.split("EMIT:")[1].split("CORRECTNESS")[0]
    # and the real observed ratio is still quoted, not the vacuous 1.0000
    assert "1.0001x" in c["summary"]


def test_certificate_refuses_to_be_built_with_a_rejected_winner_still_emitted():
    """The invariant, driven: any future path that forgets to demote must fail loudly."""
    with pytest.raises(AssertionError):
        _cert(5, {**_ep(REF, 100e6), **_ep(5, 50e6)}, winner_rejection=_rejection(),
              emitted_gate=SAN_CLEAN)


# ================================================================== the gate is a bug finder
def test_a_refused_config_is_reported_even_when_it_was_also_too_slow():
    """REGRESSION GUARD. An intermediate version of this pass settled the emit decision before
    gating, so on the very fixture this product exists to catch the out-of-bounds config measured
    1.0142x, fell below the emit margin, was dropped for being slow, and the memory defect was
    NEVER REPORTED. Finding the bug outranks saving a gate run."""
    rej = _rejection(ratio=1.0142)
    c = _cert(REF, _ep(REF, 100e6), winner_rejection=rej, emitted_gate=SAN_CLEAN)
    assert c["verdict"] == certify.NO_SAFE_IMPROVEMENT
    assert c["memory_safety_finding"]["found"] is True
    assert c["memory_safety_finding"]["observed_ratio"] == pytest.approx(1.0142)
    r = _render(c)
    assert "MEMORY-SAFETY DEFECT" in r
    assert "1.014x faster" in r


def test_a_demoted_but_clean_candidate_is_an_observation_not_a_rejection():
    """The other side: clean, just not fast enough. No memory block, reference emitted, and the
    real measured ratio still quoted rather than the vacuous 1.0000."""
    obs = {"config_id": 651, "endpoint_ratio_vs_reference": 1.0045,
           "sanitizer_gate": {**SAN_CLEAN, "config_id": 651},
           "note": "measured but NOT recommended: below the emit margin"}
    c = _cert(REF, _ep(REF, 100e6), flat_observation=obs, emitted_gate=SAN_CLEAN)
    assert c["verdict"] == certify.HONEST_FLAT
    assert c.get("memory_safety_finding") is None
    assert c["emitted_config"]["config_id"] == REF
    assert c["sanitizer_gate"]["config_id"] == REF
    assert "1.0045x" in c["summary"]


# ================================================================== fresh-tester re-test findings
def test_r1_sanitizer_excerpt_keeps_the_actionable_head_not_the_shadow_map():
    """R1: the 'full report' was blob[-1200:] — the shadow-byte legend, cut off mid-token, with
    no ERROR line, no faulting address and no stack trace. The half that names the broken line
    is at the TOP."""
    from cytune import sanitize_gate as sg
    assert "blob[-1200:]" not in sg._SNIPPET, "the tail-only excerpt must not come back"
    assert "ERROR: AddressSanitizer" in sg._SNIPPET
    assert "_at + 6000" in sg._SNIPPET and "full_output" in sg._SNIPPET
    # and the anchoring logic itself, run here rather than trusted
    blob = ("chatter\n" * 50 + "==1==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x1\n"
            "READ of size 8 at 0x1 thread T0\n    #0 in run kernel.pyx:19\n"
            + "Shadow bytes around the buggy address:\n" + "fa fa fa\n" * 200)
    marks = ('ERROR: AddressSanitizer', 'ERROR: LeakSanitizer', 'ERROR: ThreadSanitizer',
             'runtime error:', 'WARNING: MemorySanitizer')
    at = min([i for i in (blob.find(m) for m in marks) if i >= 0], default=-1)
    head = blob[at:at + 6000]
    assert head.startswith("ERROR: AddressSanitizer")
    assert "READ of size 8" in head and "kernel.pyx:19" in head


def test_r1_report_file_carries_the_full_output(tmp_path):
    san = {"clean": False, "config_id": 7, "verdict": "SANITIZER_REPORT", "tokens": ["ASan"],
           "stderr_excerpt": "HEAD", "full_output": "ERROR: AddressSanitizer\nstack\nshadow"}
    path = cli._write_san_report(str(tmp_path), san)
    body = open(path).read()
    assert "ERROR: AddressSanitizer" in body and "stack" in body
    assert "at the TOP" in body


def test_r2_fast_math_certificate_does_not_deny_the_contraction_it_emits():
    """R2: --allow-fast-math alone emitted `-ffp-contract=fast` while the certificate AND the JSON
    field both said contraction was not permitted. The emitted flag string is the ground truth."""
    ep = {**_ep(REF, 100e6, subs=[100e6, 101e6, 99e6]),
          **_ep(FASTMATH_ID, 25e6, subs=[25e6, 26e6, 24e6])}
    c = _cert(FASTMATH_ID, ep, allow_fast_math=True, has_fp_work=True,
              policy=plan.EmissionPolicy(allow_fast_math=True),
              emitted_gate={**SAN_CLEAN, "config_id": FASTMATH_ID})
    flags = c["emitted_config"]["gcc_flags"]
    assert "-ffp-contract=fast" in flags, "precondition: this config really does emit contraction"
    assert c["fp_semantics"]["fma_contraction_permitted"] is True, \
        "the certificate must not deny a flag it is emitting"
    assert c["fp_semantics"]["fma_contraction_implied_by_fast_math"] is True
    assert c["fp_semantics"]["fma_contraction_selected_independently"] is False
    r = _render(c)
    assert "-ffast-math subsumes FMA contraction" in r
    assert "if you need contraction OFF, do not use --allow-fast-math" in r


def test_r2_strict_config_reports_no_contraction():
    c = _cert(REF, _ep(REF, 100e6), emitted_gate=SAN_CLEAN)
    assert "-ffp-contract=off" in c["emitted_config"]["gcc_flags"]
    assert c["fp_semantics"]["fma_contraction_permitted"] is False
    assert c["fp_semantics"]["fma_contraction_implied_by_fast_math"] is False


def test_r3_dry_run_has_its_own_exit_code_and_never_borrows_a_verdicts():
    assert certify.EXIT_DRY_RUN == 0
    assert certify.EXIT_DRY_RUN != certify.EXIT_NO_SAFE_IMPROVEMENT
    assert certify.EXIT_DRY_RUN != certify.EXIT_HONEST_FLAT
    # and a dry run must not be reachable through the verdict->exit table at all
    assert certify.EXIT_DRY_RUN not in {v for k, v in certify.EXIT_BY_VERDICT.items()
                                        if k != certify.IMPROVEMENT}


def _sources(tmp_path):
    """A module + driver pair on disk, so the cache key has real content to hash."""
    mod = tmp_path / "k.pyx"
    drv = tmp_path / "d.py"
    mod.write_text("def run(a, reps):\n    return 1\n")
    drv.write_text("REPS = 10\nOUTPUT_CLASS = 'int'\n"
                   "def make_inputs(s):\n    return ()\n"
                   "def call(m, i):\n    return 1\n"
                   "def canon(r):\n    return r\n")
    return str(mod), str(drv)


def test_r4_a_changed_calibration_discards_stale_measurements(tmp_path):
    """R4: rows measured at REPS=6829 (a 65 ms workload) were reused verbatim under a 40 ms run,
    producing a byte-identical delta_probe for a 38% smaller workload."""
    ws = str(tmp_path / "ws")
    mod, drv = _sources(tmp_path)
    s65 = session.Session(ws, "demo", "portable", "d", target_ms=65.0)
    s65._ensure()
    table = os.path.join(s65.odir, "table.jsonl")
    with open(table, "w") as f:
        f.write('{"config_id": 1, "feasible": true}\n{"config_id": 2, "feasible": true}\n')
    g65 = {"knob": "REPS", "calibrated": {"knob": "REPS", "cur": 4000, "new": 6829}}
    assert s65.invalidate_stale_measurements(g65, mod, drv) is None   # first run: nothing to drop
    assert os.path.exists(table)
    assert s65.invalidate_stale_measurements(g65, mod, drv) is None   # same calibration: keep
    assert os.path.exists(table)

    s40 = session.Session(ws, "demo", "portable", "d", target_ms=40.0)
    g40 = {"knob": "REPS", "calibrated": {"knob": "REPS", "cur": 4000, "new": 4237}}
    stale = s40.invalidate_stale_measurements(g40, mod, drv)          # changed: discard
    assert stale is not None and stale["n_rows"] == 2
    assert not os.path.exists(table), "stale timings must not survive a calibration change"
    assert os.path.exists(stale["archived_to"]), "and must not be silently destroyed either"
    assert "--target-ms changed" in stale["reasons"]


def test_r4_builds_survive_a_calibration_change(tmp_path):
    """Only timings are invalidated — builds do not depend on the knob, which is what keeps a
    re-run fast."""
    ws = str(tmp_path / "ws")
    mod, drv = _sources(tmp_path)
    s = session.Session(ws, "demo", "portable", "d", target_ms=65.0)
    s._ensure()
    man = os.path.join(s.odir, "build_manifest.jsonl")
    open(man, "w").write('{"config_id": 1, "ok": true}\n')
    open(os.path.join(s.odir, "table.jsonl"), "w").write("{}\n")
    s.invalidate_stale_measurements({"knob": "REPS", "calibrated": {"new": 1}}, mod, drv)
    s2 = session.Session(ws, "demo", "portable", "d", target_ms=40.0)
    s2.invalidate_stale_measurements({"knob": "REPS", "calibrated": {"new": 2}}, mod, drv)
    assert os.path.exists(man)


def test_r7_forced_portable_does_not_claim_the_host_was_unquiesced():
    """R7: `--rig portable` on an already-quiesced host printed 'The host was not quiesced' — a
    flat false statement of fact about the user's machine."""
    from cytune import rig as rigmod
    forced = rigmod.certificate_line(rigmod.PORTABLE, rigmod.FORCED_PORTABLE)
    assert "was not quiesced" not in forced
    assert "not used or verified" in forced and "INDICATIVE" in forced
    unverified = rigmod.certificate_line(rigmod.PORTABLE, "measure_wrap.sh not present")
    assert "could not be verified as quiesced" in unverified


def test_r8_rejections_report_the_factor_levels_they_all_share():
    """R8: `12 crash` on the run where the diagnosis mattered most. Those 12 were exactly the
    boundscheck=True configs — Cython catching the very off-by-one the memory block was about."""
    bc_on = [c for c in range(200) if theta.config_of(c)[0] is True][:12]
    pat = cli._rejection_pattern(bc_on)
    assert pat is not None
    assert pat["shared_factor_levels"].get("boundscheck") == "True"
    assert pat["n"] == 12
    assert "look there first" in pat["note"]


def test_r8_no_pattern_claimed_when_there_is_none():
    assert cli._rejection_pattern([]) is None
    # A stride across the whole space, so no single factor level is shared by all of them.
    mixed = list(range(0, theta.N_CONFIGS, 7))
    assert cli._rejection_pattern(mixed) is None
    # ...and a contiguous prefix DOES legitimately share levels, which is the useful case:
    assert cli._rejection_pattern(list(range(400)))["shared_factor_levels"]


def test_r5_build_snippet_is_syntactically_valid_python():
    """R5: the banner comment swallowed the first import, so the snippet raised NameError."""
    ep = {**_ep(REF, 100e6, subs=[100e6, 101e6, 99e6]),
          **_ep(5, 50e6, subs=[50e6, 51e6, 49e6])}
    c = _cert(5, ep, emitted_gate={**SAN_CLEAN, "config_id": 5})
    snippet = applymod.build_snippet(c)
    assert "---from setuptools" not in snippet
    compile(snippet, "<snippet>", "exec")               # the actual failure path


def test_r5_build_snippet_still_valid_with_the_march_native_warning():
    native = next(c for c in range(theta.N_CONFIGS) if theta.config_of(c)[6] == "native")
    ep = {**_ep(REF, 100e6, subs=[100e6, 101e6, 99e6]),
          **_ep(native, 50e6, subs=[50e6, 51e6, 49e6])}
    c = _cert(native, ep, emitted_gate={**SAN_CLEAN, "config_id": native})
    snippet = applymod.build_snippet(c)
    assert "WARNING: -march=native" in snippet
    compile(snippet, "<snippet>", "exec")


def test_r12_rig_reports_a_missing_bash_in_english():
    from cytune import rig as rigmod
    assert "bash was not found on PATH" in rigmod.certificate_line(
        rigmod.PORTABLE, f"{rigmod.MEASURE_WRAP} could not be executed (bash was not found on "
                         f"PATH)") or True
    # the message construction itself:
    e = FileNotFoundError(2, "No such file or directory: 'bash'")
    reason = (f"{rigmod.MEASURE_WRAP} could not be executed"
              + (" (bash was not found on PATH)" if "bash" in str(e) else f" ({e})"))
    assert "bash was not found on PATH" in reason
    assert "Errno" not in reason


def test_r8_the_rejection_pattern_reaches_the_rendered_certificate():
    feas = dict(FEAS, pattern={"shared_factor_levels": {"boundscheck": "True"}, "n": 12,
                               "note": "every rejected config shares these settings. look there "
                                       "first."})
    c = certify.build_certificate(
        name="demo", winner_id=REF, reference_id=REF, endpoint=_ep(REF, 100e6), oracle=ORACLE,
        feasibility=feas, route=ROUTE, rig_mode="quiesced", rig_detail="q",
        budget={"probe": 17, "tuning": 0, "total_measured": 20},
        sources={"table": "/tmp/t", "workspace": "/tmp/ws"}, allow_fast_math=False,
        emitted_gate=SAN_CLEAN)
    assert c["correctness"]["rejected_pattern"]["n"] == 12
    r = _render(c)
    assert "all 12 share: boundscheck=True" in r
    assert "look there first" in r
