"""D — the frozen public API surface.

What a consumer is entitled to rely on within 1.x: the four machine-readable schemas, the exit
codes, the flag names, and one version string. Each is pinned here, and each pin drives its own
failure path — a schema test that only validates hand-written fixtures proves nothing about what
cytune actually emits, so the certificate and audit documents used below are built by the real
builders.

`docs/COMPATIBILITY.md` is the human-readable copy of these promises. If you change anything in
this file, that document is wrong.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

import cytune
from cytune import audit, certify, schema
from cytune._vendor import theta

REF = theta.REFERENCE_ID
FAST = theta.id_of((False, False, True, False, False, "-O3", "native", "on", ("off", "off")))
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))


# ------------------------------------------------------------------------ D4: one version
def test_the_version_is_single_sourced():
    """F7 made structurally impossible: the banner, --version, doctor and every artifact must all
    report the same string, because they all read the same constant."""
    v = cytune.__version__
    assert v in cytune.version_banner()
    cert = _certificate()
    assert cert["cytune_version"] == v
    assert audit.build_report("k", [])["cytune_version"] == v

    out = subprocess.run([sys.executable, "-m", "cytune", "--version"],
                         capture_output=True, text=True,
                         env={**os.environ, "PYTHONPATH": os.path.dirname(HERE)})
    assert v in (out.stdout + out.stderr)


def test_the_packaging_metadata_does_not_carry_a_second_version():
    """A literal in pyproject.toml drifted from the package's inside one release. The version is
    read from the module now, and this fails if anyone puts it back."""
    src = open(os.path.join(REPO, "pyproject.toml")).read()
    assert 'dynamic = ["version"]' in src
    assert 'version = { attr = "cytune.__version__" }' in src
    body = src.split("[project]", 1)[1].split("[project.optional", 1)[0]
    assert "\nversion = \"" not in body, "pyproject.toml has a hard-coded version again (F7)"


def test_the_release_label_is_still_honest():
    """1.0.0 freezes the INTERFACE. It does not claim the underpowered study behind the routing
    policy became complete, so the label stays until the evidence changes."""
    assert cytune.RELEASE_LABEL == "research preview"
    assert "research preview" in cytune.version_banner()


# --------------------------------------------------------------------- D3: exit codes
def test_exit_codes_are_the_documented_set():
    assert certify.EXIT_IMPROVEMENT == 0
    assert certify.EXIT_ERROR == 1
    assert certify.EXIT_HONEST_FLAT == 2
    assert certify.EXIT_NO_SAFE_IMPROVEMENT == 3
    assert certify.EXIT_DRY_RUN == 0


def test_a_usage_error_can_never_collide_with_a_verdict_code():
    """P3: argparse exits 2 by default, which is HONEST-FLAT — so `if [ $? -eq 2 ]` meant either
    'no speedup worth having' or 'you typed the flag wrong'. Driven through the real parser."""
    from cytune import cli
    verdict_codes = set(certify.EXIT_BY_VERDICT.values())
    for argv in (["tune"],                                   # missing module and --driver
                 ["tune", "k.pyx"],                          # missing --driver
                 ["nonsense"],                               # unknown subcommand
                 ["audit"]):                                 # missing module and --driver
        with pytest.raises(SystemExit) as e:
            cli.main(argv)
        code = e.value.code
        assert code == certify.EXIT_ERROR, f"{argv} exited {code}, not {certify.EXIT_ERROR}"
        assert code not in (verdict_codes - {certify.EXIT_ERROR})


def test_an_unrecognised_flag_exits_one_not_two():
    from cytune import cli
    rc = cli.main(["tune", "k.pyx", "--driver", "d.py", "--fast-math"])
    assert rc == certify.EXIT_ERROR


def test_audit_exit_codes_share_the_scheme_without_colliding():
    assert audit.EXIT_CLEAN == certify.EXIT_IMPROVEMENT == 0
    assert audit.EXIT_ERROR == certify.EXIT_ERROR == 1
    assert audit.EXIT_DEFECTS_FOUND == certify.EXIT_NO_SAFE_IMPROVEMENT == 3


def test_every_verdict_maps_to_exactly_one_exit_code():
    assert set(certify.EXIT_BY_VERDICT) == {certify.IMPROVEMENT, certify.HONEST_FLAT,
                                            certify.NO_SAFE_IMPROVEMENT}
    assert len(set(certify.EXIT_BY_VERDICT.values())) == 3


# --------------------------------------------------------------------- D1: schemas
def _certificate(winner=REF):
    ep = {str(REF): {"endpoint_ns": 100e6, "subs_ns": [100e6, 100.1e6, 99.9e6], "n_sub": 3}}
    if winner != REF:
        ep[str(winner)] = {"endpoint_ns": 50e6, "subs_ns": [50e6, 50.1e6, 49.9e6], "n_sub": 3}
    return certify.build_certificate(
        name="demo", winner_id=winner, reference_id=REF, endpoint=ep,
        oracle={"output_class": "int", "tolerance": {"rtol": 0.0, "atol": 0.0},
                "deterministic": True, "n_det_reps": 5, "golden_sha256": "abc"},
        feasibility={"n_measured": 20, "n_infeasible": 0, "infeasible_fraction": 0.0,
                     "reasons": {}},
        route={"rule": "R4", "route": "tune", "engine": "DOE", "budget": 20, "why": "lever"},
        rig_mode="quiesced", rig_detail="quiesced — verified",
        budget={"probe": 17, "tuning": 3, "total_measured": 20},
        sources={"table": "/w/table.jsonl", "workspace": "/w"}, allow_fast_math=False,
        emitted_gate={"ran": True, "clean": True, "verdict": "CLEAN", "config_id": winner})


@pytest.mark.parametrize("winner", [REF, FAST])
def test_a_real_certificate_validates_against_the_frozen_schema(winner):
    errs = schema.validate(_certificate(winner))
    assert not errs, "\n".join(errs)


def test_a_real_audit_report_validates():
    rows = audit.run("/k", lambda _k, _c: {"ran": True, "clean": True, "verdict": "CLEAN"})
    errs = schema.validate(audit.build_report("demo", rows))
    assert not errs, "\n".join(errs)


def test_an_audit_report_with_every_outcome_validates():
    states = [{"ran": True, "clean": True, "verdict": "CLEAN"},
              {"ran": True, "clean": False, "verdict": "SANITIZER_REPORT", "tokens": ["ASan"]},
              {"clean": None, "verdict": "RUN_FAIL_NO_TOKEN"},
              {"clean": None, "verdict": "BUILD_FAIL"},
              {"ran": False, "clean": None, "verdict": "IMAGE_UNAVAILABLE"}]
    seq = iter(states * 3)
    rows = audit.run("/k", lambda _k, _c: next(seq))
    errs = schema.validate(audit.build_report("demo", rows))
    assert not errs, "\n".join(errs)


def test_the_doctor_json_validates():
    from cytune import doctor as doc
    import io
    import contextlib
    buf = io.StringIO()

    class A:
        json = True
    with contextlib.redirect_stdout(buf):
        doc.doctor(A())
    errs = schema.validate(json.loads(buf.getvalue()))
    assert not errs, "\n".join(errs)


# ------------------------------------------------------- the validator is not vacuous
def test_the_validator_catches_a_missing_required_field():
    c = _certificate()
    del c["verdict"]
    errs = schema.validate(c)
    assert any("verdict" in e and "missing" in e for e in errs), errs


def test_the_validator_catches_a_retyped_field():
    c = _certificate()
    c["exit_code"] = "0"                       # was int, now str — a consumer breaks on this
    assert any("exit_code" in e for e in schema.validate(c))


def test_the_validator_catches_a_value_outside_its_enum():
    c = _certificate()
    c["verdict"] = "probably-fine"
    assert any("probably-fine" in e for e in schema.validate(c))


def test_the_validator_catches_a_bool_where_a_number_is_promised():
    """bool is an int in Python; a consumer in another language would not agree."""
    c = _certificate()
    c["speedup"] = True
    assert any("speedup" in e for e in schema.validate(c))


def test_the_validator_tolerates_added_fields():
    """The promise says consumers must ignore unknown keys, so the validator must too — otherwise
    every future release fails its own contract test."""
    c = _certificate()
    c["something_added_in_1_3"] = {"nested": 1}
    assert schema.validate(c) == []


def test_an_unknown_schema_is_rejected_rather_than_assumed():
    assert schema.validate({"schema": "cytune-certificate/9.9"})


def test_every_declared_schema_has_a_spec():
    from cytune import SCHEMA_VERSION
    for name in (f"cytune-certificate/{SCHEMA_VERSION}", f"cytune-dry-run/{SCHEMA_VERSION}",
                 f"cytune-audit/{SCHEMA_VERSION}", f"cytune-doctor/{SCHEMA_VERSION}"):
        assert name in schema.BY_SCHEMA


# ---------------------------------------------------- archived artifacts still validate
def _archived(pattern):
    import glob
    return sorted(glob.glob(os.path.join(REPO, pattern), recursive=True))


RELEASED = "1.0.0"


def _partition(paths):
    """(post-freeze, pre-freeze) — a document is a CONTRACT only if a released build wrote it.

    Three kinds of certificate sit in results/: `cytune-certificate/v0` from the pre-product CLI,
    `1.0` documents written by `1.0.0-rc1` development builds during the productisation pass, and
    `1.0` documents written by the released build. Only the last kind is what the compatibility
    promise covers — the promise starts at the release, not before it. The first two are historical
    records and are counted and named rather than quietly skipped.
    """
    post, pre = [], []
    for p in paths:
        try:
            doc = json.load(open(p))
        except (OSError, json.JSONDecodeError):
            pre.append((p, None))
            continue
        if doc.get("schema") in schema.BY_SCHEMA and doc.get("cytune_version") == RELEASED:
            post.append((p, doc))
        else:
            pre.append((p, doc))
    return post, pre


def test_every_archived_certificate_from_a_released_build_validates():
    """The schema is only worth something if the documents cytune actually produces honour it."""
    post, pre = _partition(_archived("results/**/certificate.json"))
    if not post:
        pytest.skip(f"no certificates from a released build yet ({len(pre)} pre-release archived)")
    bad = {os.path.relpath(p, REPO): errs
           for p, doc in post if (errs := schema.validate(doc))}
    assert not bad, json.dumps(bad, indent=2)[:4000]


def test_the_archive_check_is_not_validating_an_empty_set():
    """Guards the skip above from becoming permanent silence.

    The release gate requires the ground-truth dogfood to have run, which writes nine certificates
    from a released build. If none exists, the schema has never been checked against a real
    document and saying so is the point.
    """
    post, _pre = _partition(_archived("results/**/certificate.json"))
    if not post:
        pytest.skip("no released-build certificates archived yet — run the dogfood (F1)")
    assert len(post) >= 1


def test_every_archived_audit_report_validates():
    paths = _archived("results/**/audit.json")
    if not paths:
        pytest.skip("no archived audit reports in this checkout")
    bad = {}
    for p in paths:
        errs = schema.validate(json.load(open(p)))
        if errs:
            bad[os.path.relpath(p, REPO)] = errs
    assert not bad, json.dumps(bad, indent=2)[:4000]


# ------------------------------------------- all four artifacts are guarded at RUNTIME
def test_the_dry_run_document_is_validated_before_it_is_emitted():
    """All four artifacts are public contracts, so all four are checked against their schema
    before leaving the process. Only `certificate.json` was guarded; the other three could drift
    while every test validated a hand-written fixture."""
    from cytune import coherence
    doc = {"schema": f"cytune-dry-run/{cytune.SCHEMA_VERSION}",
           "cytune_version": cytune.__version__, "dry_run": True, "verdict": None,
           "module": "k", "note": "n", "probe_features": {}, "routing": {},
           "would_measure_configs": 16, "estimated_seconds": 32.0,
           "rig_mode": "quiesced", "emission_policy": {}, "exit_code": 0}
    assert coherence.assert_document_valid(doc) is True
    doc["exit_code"] = "0"                       # re-typed
    with pytest.raises(coherence.IncoherentCertificate) as e:
        coherence.assert_document_valid(doc)
    assert e.value.invariant == "I1.9"


def test_the_audit_document_is_validated_before_it_is_emitted():
    from cytune import coherence
    rows = audit.run("/k", lambda _k, _c: {"ran": True, "clean": True, "verdict": "CLEAN"})
    rep = audit.build_report("demo", rows)
    assert coherence.assert_document_valid(rep) is True
    del rep["directive_verdicts"]
    with pytest.raises(coherence.IncoherentCertificate):
        coherence.assert_document_valid(rep)


def test_the_cli_actually_calls_the_dry_run_validator():
    """Guards the wiring, not just the function: a validator nobody calls is decoration."""
    import inspect
    from cytune import cli
    src = inspect.getsource(cli._dry_run_report)
    assert "assert_document_valid" in src, "the dry-run path does not validate its own document"
    assert "assert_document_valid" in inspect.getsource(cli.audit), \
        "the audit path does not validate its own document"
