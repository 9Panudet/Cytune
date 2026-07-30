"""oracle.json manifest schema + validator (Step 0.3.1, roadmap §3.1).

Schema "motifbo-oracle-v1" — declared per unit at /data/<unit>/oracle.json,
frozen before any search:

    {
      "schema": "motifbo-oracle-v1",
      "unit": "<unit-name>",
      "outputs": [
        {"name": "<output>", "class": "correctness-critical"},
        {"name": "<output>", "class": "numerically-approximate",
         "tolerance": {"mode": "atol_rtol", "atol": <num >= 0>, "rtol": <num >= 0>}
                    | {"mode": "ulp", "max_ulp": <int >= 1>}}
      ],
      "expected_exceptions": [                    # optional; 0.3.4 edge-suite
        {"case": "<probe-case>", "type": "<Name | dotted.path.Name>"}
      ]
    }

§3.1 rules enforced here:
- correctness-critical is bitwise — a tolerance there is a contradiction.
- numerically-approximate requires exactly one tolerance mode; degenerate
  tolerances (atol=rtol=0, max_ulp=0) are bitwise in disguise and rejected —
  declare the output correctness-critical instead.
- Raised-exception type is correctness-critical ground truth: a bare type name
  must resolve to a builtin BaseException subclass (kills misspellings that
  could never match at runtime); dotted names are checked structurally here
  and by identity in the 0.3.2 comparator.
- Unknown keys anywhere are errors: a frozen ground-truth manifest fails
  loudly on typos, never silently ignores a field (§6.1).

Tolerance provenance (the §3.1 setting procedure's inputs) is deliberately not
in v1 — the procedure runs at Step 1.1.3, which bumps the schema if it needs
manifest fields.
"""
import builtins
import json
import math
import re
from pathlib import Path

SCHEMA = "motifbo-oracle-v1"
OUTPUT_CLASSES = ("correctness-critical", "numerically-approximate")
TOLERANCE_MODES = ("atol_rtol", "ulp")

_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_BARE_RE = re.compile(rf"^{_NAME}$")
_DOTTED_RE = re.compile(rf"^{_NAME}(\.{_NAME})+$")


class ManifestError(ValueError):
    """Raised by load_manifest; carries ALL validation errors, not the first."""

    def __init__(self, source, errors):
        self.errors = list(errors)
        super().__init__(f"{source}: invalid oracle manifest:\n"
                         + "\n".join(f"  - {e}" for e in self.errors))


def validate_manifest(doc):
    """Validate a parsed oracle.json document; return a list of error strings.

    An empty list means valid. Never raises on bad input — callers that want
    an exception use load_manifest.
    """
    if not isinstance(doc, dict):
        return [f"manifest: must be a JSON object, got {type(doc).__name__}"]
    errors = []
    _check_keys(doc, ("schema", "unit", "outputs", "expected_exceptions"),
                "manifest", errors)

    if doc.get("schema") != SCHEMA:
        errors.append(f"schema: must be {SCHEMA!r}, got {doc.get('schema')!r}")
    if not _nonempty_str(doc.get("unit")):
        errors.append("unit: must be a non-empty string")

    outputs = doc.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        errors.append("outputs: must be a non-empty list")
    else:
        seen = set()
        for i, out in enumerate(outputs):
            _validate_output(out, f"outputs[{i}]", seen, errors)

    cases = doc.get("expected_exceptions", [])
    if not isinstance(cases, list):
        errors.append("expected_exceptions: must be a list")
    else:
        seen = set()
        for i, entry in enumerate(cases):
            _validate_exception(entry, f"expected_exceptions[{i}]", seen, errors)
    return errors


def load_manifest(path):
    """Read + validate an oracle.json file; return the document dict.

    Raises ManifestError (with .errors listing every problem) on unreadable
    or unparseable files and on any validation failure.
    """
    path = Path(path)
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise ManifestError(path, [f"unreadable JSON: {e}"]) from e
    errors = validate_manifest(doc)
    if errors:
        raise ManifestError(path, errors)
    return doc


def _nonempty_str(v):
    return isinstance(v, str) and bool(v)


def _finite_number(v):
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v))


def _check_keys(obj, allowed, where, errors):
    for k in sorted(set(obj) - set(allowed)):
        errors.append(f"{where}: unknown key {k!r} (allowed: {allowed})")


def _validate_output(out, where, seen, errors):
    if not isinstance(out, dict):
        errors.append(f"{where}: must be an object, got {type(out).__name__}")
        return
    _check_keys(out, ("name", "class", "tolerance"), where, errors)

    name = out.get("name")
    if not _nonempty_str(name):
        errors.append(f"{where}.name: must be a non-empty string")
    elif name in seen:
        errors.append(f"{where}.name: duplicate output name {name!r}")
    else:
        seen.add(name)

    cls = out.get("class")
    if cls not in OUTPUT_CLASSES:
        errors.append(f"{where}.class: must be one of {OUTPUT_CLASSES}, "
                      f"got {cls!r}")
    elif cls == "correctness-critical":
        if "tolerance" in out:
            errors.append(
                f"{where}: correctness-critical outputs are bitwise (§3.1) — "
                f"declaring a tolerance is a contradiction")
    elif "tolerance" not in out:
        errors.append(f"{where}.tolerance: required for "
                      f"numerically-approximate outputs")
    else:
        _validate_tolerance(out["tolerance"], f"{where}.tolerance", errors)


def _validate_tolerance(tol, where, errors):
    if not isinstance(tol, dict):
        errors.append(f"{where}: must be an object, got {type(tol).__name__}")
        return
    mode = tol.get("mode")
    if mode == "atol_rtol":
        _check_keys(tol, ("mode", "atol", "rtol"), where, errors)
        ok = True
        for k in ("atol", "rtol"):
            v = tol.get(k)
            if not (_finite_number(v) and v >= 0):
                errors.append(f"{where}.{k}: must be a finite number >= 0, "
                              f"got {v!r}")
                ok = False
        if ok and tol["atol"] == 0 and tol["rtol"] == 0:
            errors.append(f"{where}: atol=rtol=0 is bitwise in disguise — "
                          f"declare the output correctness-critical instead")
    elif mode == "ulp":
        _check_keys(tol, ("mode", "max_ulp"), where, errors)
        v = tol.get("max_ulp")
        if not (isinstance(v, int) and not isinstance(v, bool) and v >= 1):
            errors.append(f"{where}.max_ulp: must be an integer >= 1 "
                          f"(0 is bitwise in disguise), got {v!r}")
    else:
        errors.append(f"{where}.mode: must be one of {TOLERANCE_MODES}, "
                      f"got {mode!r}")


def _validate_exception(entry, where, seen, errors):
    if not isinstance(entry, dict):
        errors.append(f"{where}: must be an object, got {type(entry).__name__}")
        return
    _check_keys(entry, ("case", "type"), where, errors)

    case = entry.get("case")
    if not _nonempty_str(case):
        errors.append(f"{where}.case: must be a non-empty string")
    elif case in seen:
        errors.append(f"{where}.case: duplicate case name {case!r}")
    else:
        seen.add(case)

    typ = entry.get("type")
    if not _nonempty_str(typ):
        errors.append(f"{where}.type: must be a non-empty string")
    elif _BARE_RE.match(typ):
        obj = getattr(builtins, typ, None)
        if not (isinstance(obj, type) and issubclass(obj, BaseException)):
            errors.append(f"{where}.type: bare name {typ!r} does not resolve "
                          f"to a builtin exception type")
    elif not _DOTTED_RE.match(typ):
        errors.append(f"{where}.type: {typ!r} is not an exception identifier "
                      f"(Name or dotted.path.Name)")
