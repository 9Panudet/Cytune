"""D1 — the frozen public API surface: what cytune's machine-readable outputs promise.

THREE ARTIFACTS ARE PUBLIC, and within 1.x they are contracts:

    cytune-certificate/1.0   `cytune tune --json`, and <workspace>/<name>/certificate.json
    cytune-dry-run/1.0       `cytune tune --dry-run --json`
    cytune-audit/1.0         `cytune audit --json`, and <workspace>/<name>/audit.json
    cytune-doctor/1.0        `cytune doctor --json`

THE PROMISE (docs/COMPATIBILITY.md is the human-readable copy):
  - a field that exists in 1.0 still exists, with the same type and the same meaning, in every 1.x;
  - new fields may be ADDED, so a consumer must ignore unknown keys;
  - exit codes do not change meaning;
  - flag names are not repurposed;
  - a deprecation warns for one minor release before anything is removed, and removal waits for 2.0.

WHY A HAND-WRITTEN VALIDATOR. The product declares `dependencies = []` — the host side is pure
stdlib, which is what lets `cytune doctor` run on a machine with nothing installed but Python. That
property is worth more than the convenience of `jsonschema`, and the subset of JSON Schema needed
to pin these artifacts is about sixty lines. The validator is deliberately strict about the things
a consumer would break on (missing key, wrong type, value outside an enum) and silent about extra
keys, which the promise explicitly permits.
"""
from __future__ import annotations

from . import SCHEMA_VERSION

# ------------------------------------------------------------------------------- type language
#
# "str" | "int" | "float" | "bool" | "null" | "object" | "array"
# A tuple means "any of these". A dict value means a nested spec. `enum(...)` pins the values.


def enum(*values):
    return {"__enum__": set(values)}


NUM = ("int", "float")
MAYBE_NUM = ("int", "float", "null")
MAYBE_STR = ("str", "null")
MAYBE_BOOL = ("bool", "null")

VERDICTS = enum("improvement", "honest-flat", "no-safe-improvement")
AUDIT_VERDICTS = enum("clean", "defects-found", "incomplete")
AUDIT_OUTCOMES = enum("clean", "reported", "raised", "not-run", "build-fail")
RIG_MODES = enum("quiesced", "portable")

CERTIFICATE = {
    "schema": enum(f"cytune-certificate/{SCHEMA_VERSION}"),
    "cytune_version": "str",
    "module": "str",
    "verdict": VERDICTS,
    "exit_code": "int",
    "summary": "str",
    "routing_label": "str",
    "speedup": MAYBE_NUM,
    "emitted_config": {
        "__optional__": True, "__nullable__": True,
        "config_id": "int",
        "factors": "object",
        "directive_header": "str",
        "cython_x_flags": "str",
        "gcc_flags": "str",
    },
    "emitted_config_unsafe": {"__optional__": True, "__type__": "bool"},
    "sanitizer_gate": {
        "clean": MAYBE_BOOL,
        "verdict": {"__optional__": True, "__type__": MAYBE_STR},
        "ran": {"__optional__": True, "__type__": "bool"},
    },
    "sanitizer_gate_ran": {"__optional__": True, "__type__": "bool"},
    "correctness": {
        "oracle_class": MAYBE_STR,
        "tolerance": ("object", "null"),
        "configs_measured": MAYBE_NUM,
        "configs_rejected_infeasible": MAYBE_NUM,
        "golden_sha256": MAYBE_STR,
    },
    "measurement": {
        "rig_mode": RIG_MODES,
        "rig_statement": "str",
        "endpoint_protocol": "str",
        "winner_endpoint_ns": MAYBE_NUM,
        "reference_endpoint_ns": MAYBE_NUM,
    },
    "emission_policy": {
        "allow_fast_math": "bool",
        "allow_fp_contract": "bool",
        "portable_flags": "bool",
    },
    "fp_semantics": {
        "fast_math_permitted": "bool",
        "fma_contraction_permitted": "bool",
        "fma_contraction_implied_by_fast_math": "bool",
    },
    "routing": "object",
    "budget": "object",
    "sources": "object",
    "glossary": "object",
    # ---- 1.0.0 additions (I4/C2). OPTIONAL by contract, not by oversight.
    #
    # The compatibility promise permits ADDING fields and requires consumers to tolerate unknown
    # ones; it does not permit a new release to invalidate documents an older one emitted. Every
    # certificate under results/ was written before these existed, and
    # `test_cytune_api.py::test_every_archived_certificate_validates` checks them all against this
    # schema on every run. Marking these required would have failed that test — which is the test
    # doing its job, and the reason they are marked this way rather than the schema being relaxed.
    "provenance": {
        "__optional__": True, "__nullable__": True,
        "emitted_artifact_sha256": MAYBE_STR,
        "endpoint_artifact_sha256": MAYBE_STR,
        "toolchain_image_digest": MAYBE_STR,
        "configs_measured": MAYBE_NUM,
    },
    "factor_degeneracy": {
        "__optional__": True, "__nullable__": True,
        "n_distinct_artifacts": MAYBE_NUM,
        "n_directive_combos_built": "int",
        "n_distinct_generated_sources": "int",
        "directives_inert": "array",
        "total_collapse": "bool",
    },
    "attestation": {
        "__optional__": True, "__nullable__": True,
        "attests": "str",
        "does_not_attest": "str",
        "audience": "str",
    },
}

DRY_RUN = {
    "schema": enum(f"cytune-dry-run/{SCHEMA_VERSION}"),
    "cytune_version": "str",
    "dry_run": enum(True),
    "verdict": enum(None),
    "module": "str",
    "exit_code": "int",
    "would_measure_configs": "int",
    "estimated_seconds": MAYBE_NUM,
    "rig_mode": RIG_MODES,
    "emission_policy": "object",
    "probe_features": "object",
    "routing": "object",
    "note": "str",
}

AUDIT = {
    "schema": enum(f"cytune-audit/{SCHEMA_VERSION}"),
    "cytune_version": "str",
    "command": enum("audit"),
    "module": "str",
    "verdict": AUDIT_VERDICTS,
    "exit_code": "int",
    "summary": "str",
    "scope": "str",
    "risk_set_size": "int",
    "n_reported": "int",
    "n_clean": "int",
    "n_not_run": "int",
    "directive_verdicts": "object",
    "results": {"__array_of__": {
        "name": "str",
        "config_id": "int",
        "outcome": AUDIT_OUTCOMES,
        "why": "str",
        "directives": "object",
        "clean": MAYBE_BOOL,
        "verdict": MAYBE_STR,
        "tokens": "array",
    }},
}

DOCTOR = {
    "schema": enum(f"cytune-doctor/{SCHEMA_VERSION}"),
    "cytune_version": "str",
    "ok": "bool",
    "exit_code": "int",
    "checks": {"__array_of__": {
        "name": "str",
        "ok": MAYBE_BOOL,
        "tier": "str",
        "detail": "str",
    }},
}

BY_SCHEMA = {
    f"cytune-certificate/{SCHEMA_VERSION}": CERTIFICATE,
    f"cytune-dry-run/{SCHEMA_VERSION}": DRY_RUN,
    f"cytune-audit/{SCHEMA_VERSION}": AUDIT,
    f"cytune-doctor/{SCHEMA_VERSION}": DOCTOR,
}


# ---------------------------------------------------------------------------------- validator
_PY = {"str": str, "int": int, "float": float, "bool": bool, "object": dict, "array": list}


def _type_ok(value, spec):
    if isinstance(spec, str):
        spec = (spec,)
    for t in spec:
        if t == "null":
            if value is None:
                return True
        elif t == "float":
            # bool is an int in Python; a bool where a number is promised is a real type error.
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return True
        elif t == "int":
            if isinstance(value, int) and not isinstance(value, bool):
                return True
        elif isinstance(value, _PY[t]) and not (t != "bool" and isinstance(value, bool)):
            return True
    return False


def validate(doc, spec=None, path="$"):
    """Return a list of human-readable violations. Empty means the document honours the contract.

    Extra keys are NOT violations: the compatibility promise says consumers must tolerate added
    fields, so the validator has to as well, or every future release would fail its own tests.
    """
    errs = []
    if spec is None:
        s = (doc or {}).get("schema")
        spec = BY_SCHEMA.get(s)
        if spec is None:
            return [f"{path}: unknown schema {s!r}; expected one of {sorted(BY_SCHEMA)}"]
    if not isinstance(doc, dict):
        return [f"{path}: expected an object, got {type(doc).__name__}"]

    for key, rule in spec.items():
        if key.startswith("__"):
            continue
        here = f"{path}.{key}"
        optional = isinstance(rule, dict) and rule.get("__optional__")
        if key not in doc:
            if not optional:
                errs.append(f"{here}: required field is missing")
            continue
        value = doc[key]
        errs.extend(_check(value, rule, here))
    return errs


def _check(value, rule, here):
    errs = []
    if isinstance(rule, dict) and "__enum__" in rule:
        if value not in rule["__enum__"]:
            errs.append(f"{here}: {value!r} is not one of {sorted(map(str, rule['__enum__']))}")
        return errs
    if isinstance(rule, dict) and "__array_of__" in rule:
        if not isinstance(value, list):
            return [f"{here}: expected an array, got {type(value).__name__}"]
        for i, item in enumerate(value):
            errs.extend(validate(item, rule["__array_of__"], f"{here}[{i}]"))
        return errs
    if isinstance(rule, dict) and "__type__" in rule:
        if not _type_ok(value, rule["__type__"]):
            errs.append(f"{here}: expected {rule['__type__']}, got {type(value).__name__}")
        return errs
    if isinstance(rule, dict):
        if value is None and rule.get("__nullable__"):
            return errs
        return validate(value, rule, here)
    if not _type_ok(value, rule):
        errs.append(f"{here}: expected {rule}, got {type(value).__name__}")
    return errs
