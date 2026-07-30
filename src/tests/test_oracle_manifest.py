"""Step 0.3.1 — oracle.json manifest schema + validator tests (TDD, red first).

Grounding (roadmap §3.1): every output of every unit is classified in the unit's
frozen manifest as correctness-critical (bitwise, incl. raised-exception type)
or numerically-approximate (declared (atol, rtol) or max-ULP tolerance). The
validator must reject contradictions (tolerance on a bitwise output, degenerate
zero tolerances) and typos (unknown keys, misspelled exception names) loudly —
a manifest that silently passes with a wrong declaration corrupts gate I-3.
"""
import copy
import json

import pytest

from motifbo.oracle.manifest import (
    SCHEMA,
    ManifestError,
    load_manifest,
    validate_manifest,
)

# Mixed-class unit per the §3.1 Dijkstra example: one bit-exact output, one
# atol/rtol output, one ULP output, plus edge-suite exception expectations.
VALID = {
    "schema": "motifbo-oracle-v1",
    "unit": "csr_scale",
    "outputs": [
        {"name": "indptr", "class": "correctness-critical"},
        {"name": "data", "class": "numerically-approximate",
         "tolerance": {"mode": "atol_rtol", "atol": 1e-12, "rtol": 1e-9}},
        {"name": "row_norm", "class": "numerically-approximate",
         "tolerance": {"mode": "ulp", "max_ulp": 4}},
    ],
    "expected_exceptions": [
        {"case": "zero_divisor", "type": "ZeroDivisionError"},
        {"case": "singular_input", "type": "numpy.linalg.LinAlgError"},
    ],
}


def doc(**overrides):
    d = copy.deepcopy(VALID)
    d.update(overrides)
    return d


def assert_error(errors, fragment):
    assert any(fragment in e for e in errors), (
        f"expected an error containing {fragment!r}, got {errors!r}")


# --- acceptance -------------------------------------------------------------

def test_valid_manifest_passes():
    assert validate_manifest(VALID) == []


def test_schema_constant_matches_valid_fixture():
    assert SCHEMA == VALID["schema"]


def test_expected_exceptions_are_optional():
    d = doc()
    del d["expected_exceptions"]
    assert validate_manifest(d) == []


# --- document shape ---------------------------------------------------------

def test_rejects_non_object_document():
    for bad in ([], "oracle", None, 7):
        errors = validate_manifest(bad)
        assert errors, f"accepted non-object document {bad!r}"
        assert_error(errors, "object")


def test_rejects_wrong_schema_string():
    errors = validate_manifest(doc(schema="motifbo-oracle-v2"))
    assert_error(errors, "schema")
    assert_error(errors, "motifbo-oracle-v1")


def test_rejects_missing_required_fields():
    for field in ("schema", "unit", "outputs"):
        d = doc()
        del d[field]
        assert_error(validate_manifest(d), field)


def test_rejects_unknown_top_level_key():
    errors = validate_manifest(doc(tolerances=[]))
    assert_error(errors, "unknown key")
    assert_error(errors, "tolerances")


def test_rejects_empty_or_non_list_outputs():
    assert_error(validate_manifest(doc(outputs=[])), "outputs")
    assert_error(validate_manifest(doc(outputs="indptr")), "outputs")


def test_rejects_blank_unit():
    assert_error(validate_manifest(doc(unit="")), "unit")


# --- outputs: names and classes ---------------------------------------------

def test_rejects_duplicate_output_names():
    d = doc()
    d["outputs"].append({"name": "indptr", "class": "correctness-critical"})
    assert_error(validate_manifest(d), "duplicate")


def test_rejects_unknown_output_class():
    d = doc()
    d["outputs"][0]["class"] = "approximate"
    errors = validate_manifest(d)
    assert_error(errors, "outputs[0].class")
    assert_error(errors, "approximate")


def test_rejects_unknown_output_key_typo():
    d = doc()
    out = d["outputs"][1]
    out["tolerence"] = out.pop("tolerance")  # the §6.1 failure mode: silent typo
    errors = validate_manifest(d)
    assert_error(errors, "unknown key")
    assert_error(errors, "tolerence")
    assert_error(errors, "tolerance")  # ...and the real field is now missing


def test_rejects_non_object_output_entry():
    d = doc()
    d["outputs"][0] = "indptr"
    assert_error(validate_manifest(d), "outputs[0]")


# --- §3.1 class/tolerance coupling ------------------------------------------

def test_rejects_tolerance_on_correctness_critical():
    d = doc()
    d["outputs"][0]["tolerance"] = {"mode": "ulp", "max_ulp": 1}
    errors = validate_manifest(d)
    assert_error(errors, "correctness-critical")
    assert_error(errors, "contradiction")


def test_rejects_missing_tolerance_on_approximate():
    d = doc()
    del d["outputs"][1]["tolerance"]
    assert_error(validate_manifest(d), "outputs[1].tolerance")


# --- atol/rtol mode ----------------------------------------------------------

@pytest.mark.parametrize("field,value", [
    ("atol", -1e-12), ("rtol", -1.0),
    ("atol", float("nan")), ("rtol", float("inf")),
    ("atol", "1e-12"), ("rtol", True),
])
def test_rejects_bad_atol_rtol_values(field, value):
    d = doc()
    d["outputs"][1]["tolerance"][field] = value
    assert_error(validate_manifest(d), f"tolerance.{field}")


def test_rejects_both_zero_atol_rtol_as_bitwise_in_disguise():
    d = doc()
    d["outputs"][1]["tolerance"].update(atol=0.0, rtol=0.0)
    assert_error(validate_manifest(d), "correctness-critical")


def test_rejects_missing_rtol():
    d = doc()
    del d["outputs"][1]["tolerance"]["rtol"]
    assert_error(validate_manifest(d), "rtol")


# --- ULP mode -----------------------------------------------------------------

@pytest.mark.parametrize("value", [0, -3, 2.5, True, "4", None])
def test_rejects_bad_max_ulp(value):
    d = doc()
    d["outputs"][2]["tolerance"]["max_ulp"] = value
    assert_error(validate_manifest(d), "max_ulp")


def test_rejects_cross_mode_keys():
    d = doc()
    d["outputs"][2]["tolerance"]["atol"] = 1e-12  # atol in ulp mode = confusion
    errors = validate_manifest(d)
    assert_error(errors, "unknown key")
    assert_error(errors, "atol")


def test_rejects_unknown_tolerance_mode():
    d = doc()
    d["outputs"][2]["tolerance"] = {"mode": "relative", "max_ulp": 4}
    errors = validate_manifest(d)
    assert_error(errors, "mode")
    assert_error(errors, "relative")


# --- expected exceptions ------------------------------------------------------

def test_rejects_bare_name_that_is_not_a_builtin_exception():
    for bad in ("ZeroDivisonError",  # typo: would never match at runtime
                "len"):              # resolves in builtins, but not an exception
        d = doc()
        d["expected_exceptions"][0]["type"] = bad
        errors = validate_manifest(d)
        assert_error(errors, bad)
        assert_error(errors, "builtin exception")


def test_rejects_malformed_exception_type_string():
    for bad in ("", "not an identifier!", "trailing.dot.", "1numpy.Error"):
        d = doc()
        d["expected_exceptions"][1]["type"] = bad
        assert_error(validate_manifest(d), "expected_exceptions[1].type")


def test_rejects_duplicate_case_names():
    d = doc()
    d["expected_exceptions"].append(
        {"case": "zero_divisor", "type": "OverflowError"})
    assert_error(validate_manifest(d), "duplicate")


def test_rejects_blank_case_and_unknown_entry_key():
    d = doc()
    d["expected_exceptions"][0] = {"case": "", "type": "ValueError", "when": "x"}
    errors = validate_manifest(d)
    assert_error(errors, "expected_exceptions[0].case")
    assert_error(errors, "unknown key")


# --- load_manifest ------------------------------------------------------------

def test_load_manifest_roundtrip(tmp_path):
    p = tmp_path / "oracle.json"
    p.write_text(json.dumps(VALID))
    assert load_manifest(p) == VALID


def test_load_manifest_raises_with_all_errors(tmp_path):
    d = doc()
    d["outputs"][0]["tolerance"] = {"mode": "ulp", "max_ulp": 1}  # contradiction
    d["outputs"][1]["tolerance"]["atol"] = -1.0                   # bad value
    p = tmp_path / "oracle.json"
    p.write_text(json.dumps(d))
    with pytest.raises(ManifestError) as exc:
        load_manifest(p)
    assert len(exc.value.errors) == 2  # ALL errors reported, not first-only
    assert str(p) in str(exc.value)


def test_load_manifest_rejects_unparseable_json(tmp_path):
    p = tmp_path / "oracle.json"
    p.write_text("{not json")
    with pytest.raises(ManifestError) as exc:
        load_manifest(p)
    assert_error(exc.value.errors, "JSON")
