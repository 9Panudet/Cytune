"""`.cytune.toml` — project defaults, with provenance for every value.

WHY THIS EXISTS AND WHY IT IS THIS SMALL. A user who tunes the same module repeatedly retypes the
same four flags, and the flags that matter most (`--allow-fp-contract`, `--rig`) are exactly the
ones you do not want to retype-and-typo. So: a flat table of the same names the CLI already has,
no new concepts, no nesting, no include mechanism.

PRECEDENCE, and why the certificate records it. CLI flag > .cytune.toml > built-in default. The
certificate carries the EFFECTIVE value *and where it came from*, because "the run was configured
somewhere I cannot see" is the same class of problem as "a check that never runs leaves no trace"
— the defect this project is a record of. A reader of a certificate must never have to guess
whether --allow-fp-contract was on.

No setting here can loosen a guarantee that a flag could not already loosen: the file sets the
same values argparse does, and the emission policy narrows candidates only.
"""
from __future__ import annotations
import os

FILENAME = ".cytune.toml"
SECTION = "cytune"

# name -> (type, built-in default). The single source of truth for what may appear in the file.
FIELDS = {
    "workspace": (str, ".cytune"),
    "rig": (str, "auto"),
    "target_ms": (float, 65.0),
    "allow_fast_math": (bool, False),
    "allow_fp_contract": (bool, False),
    "portable_flags": (bool, False),
    "probe_as_screen": (bool, False),
    "budget_scale": (float, 1.0),
    "preset": (str, "standard"),
}

# PRESETS — one name for "how much measurement am I willing to pay for".
#
# A preset scales the budget the ROUTING RULE chose; it does not replace the rule. The rule is
# frozen policy (results/prereg/CYTUNE_V0_ROUTING_INTERIM.md) and a preset that overrode it would be
# a second, undocumented router. So `thorough` searches twice as far along the same ranking that
# `standard` would have walked, and `quick` half as far.
#
# A preset can only change HOW MUCH IS MEASURED and HOW BIG THE WORKLOAD IS. It cannot touch the
# emission policy, the oracle, the sanitizer gate or the emit margin — G5 forbids any flag from
# loosening G1/G2/G3, and a preset is a flag.
PRESETS = {
    "quick": {"budget_scale": 0.5, "target_ms": 30.0},
    "standard": {"budget_scale": 1.0, "target_ms": 65.0},
    "thorough": {"budget_scale": 2.0, "target_ms": 65.0},
}

PRESET_HELP = {
    "quick": "half the routed search budget on a ~30 ms workload — fastest answer, widest margin",
    "standard": "the routed budget on a ~65 ms workload (default)",
    "thorough": "twice the routed search budget — searches further along the same ranking",
}

# Nothing a preset sets may weaken a guarantee. Asserted by
# test_cytune_preset.py::test_no_preset_can_touch_a_guarantee.
PRESET_SETTABLE = {"budget_scale", "target_ms"}


class ConfigError(RuntimeError):
    pass


def _load_toml(path):
    """Any failure here becomes a ConfigError. T5 (systematic-tester agent): a malformed file and
    an unreadable one both escaped as raw Python tracebacks — `tomllib.TOMLDecodeError` and
    `IsADirectoryError` are not ConfigError, so `main`'s handler never saw them."""
    parser = None
    try:
        import tomllib as parser                              # py3.11+
    except ImportError:
        try:
            import tomli as parser                            # py3.9/3.10 with tomli installed
        except ImportError:
            parser = None
    if parser is None:
        return _minimal_parse(path)
    try:
        with open(path, "rb") as f:
            return parser.load(f)
    except OSError as e:
        raise ConfigError(f"{path}: cannot be read ({e.strerror or e})")
    except Exception as e:                                    # noqa: BLE001 - any TOML error
        raise ConfigError(f"{path}: is not valid TOML ({e})")


def _minimal_parse(path):
    """A flat-table subset of TOML, so `.cytune.toml` works on 3.9/3.10 with no dependency.

    Handles exactly what FIELDS needs: `[section]`, `key = "str" | number | true | false`, and
    `#` comments. Anything else raises rather than being silently misread — a config parser that
    guesses is worse than one that refuses.
    """
    data, section = {}, None
    for lineno, raw in enumerate(open(path), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            data.setdefault(section, {})
            continue
        if "=" not in line:
            raise ConfigError(f"{path}:{lineno}: cannot parse `{raw.strip()}` — this build has no "
                              f"TOML parser (python < 3.11 and `tomli` not installed), so only "
                              f"simple `key = value` lines are supported. `pip install tomli` for "
                              f"full TOML.")
        key, val = (x.strip() for x in line.split("=", 1))
        if val in ("true", "false"):
            parsed = (val == "true")
        elif len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            parsed = val[1:-1]
        else:
            try:
                parsed = float(val) if ("." in val or "e" in val.lower()) else int(val)
            except ValueError:
                raise ConfigError(f"{path}:{lineno}: cannot parse value `{val}`")
        if section is None:
            raise ConfigError(f"{path}:{lineno}: `{key}` is outside any [section]; "
                              f"put settings under [{SECTION}]")
        data[section][key] = parsed
    return data


def find(start=None):
    """Nearest `.cytune.toml` at or above `start` (default: CWD). Returns a path or None."""
    d = os.path.abspath(start or os.getcwd())
    while True:
        cand = os.path.join(d, FILENAME)
        if os.path.exists(cand):
            return cand
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def load(path=None, start=None):
    """Return (values, path). Unknown keys are an ERROR, not a warning: a typo'd
    `allow_fastmath = true` that is silently ignored would leave a user believing they opted in."""
    path = path or find(start)
    if not path:
        return {}, None
    raw = _load_toml(path)
    table = raw.get(SECTION)
    if table is None:
        raise ConfigError(f"{path}: no [{SECTION}] section — cytune settings go under "
                          f"[{SECTION}], e.g.\n\n  [{SECTION}]\n  target_ms = 65\n")
    unknown = sorted(set(table) - set(FIELDS))
    if unknown:
        raise ConfigError(
            f"{path}: unknown setting(s) under [{SECTION}]: {', '.join(unknown)}\n"
            f"  known settings: {', '.join(sorted(FIELDS))}")
    # T7: unknown KEYS were an error, but a bad VALUE for an enum-like setting was silently
    # accepted and then quietly ignored downstream, which is the same defect the unknown-key
    # check exists to prevent — a user believing they configured something they did not.
    enums = {"rig": ("auto", "quiesced", "portable"),
             "preset": tuple(sorted(PRESETS))}
    out = {}
    for k, v in table.items():
        if k in enums and v not in enums[k]:
            raise ConfigError(f"{path}: {k} must be one of {', '.join(enums[k])}, got {v!r}")
        if k in ("target_ms", "budget_scale") and isinstance(v, (int, float)) and v < 0:
            raise ConfigError(f"{path}: {k} must not be negative, got {v!r}")
        typ, _default = FIELDS[k]
        if typ is bool and not isinstance(v, bool):
            raise ConfigError(f"{path}: {k} must be true or false, got {v!r}")
        if typ is float and isinstance(v, bool):
            raise ConfigError(f"{path}: {k} must be a number, got {v!r}")
        try:
            out[k] = typ(v)
        except (TypeError, ValueError):
            raise ConfigError(f"{path}: {k} must be {typ.__name__}, got {v!r}")
    return out, path


def resolve(args, explicit, file_values, file_path):
    """Merge CLI > preset > file > default and record where every value came from.

    `explicit` is the set of option names the user actually typed, so a flag left at its argparse
    default does not masquerade as a deliberate choice — and so an explicit `--target-ms 40` still
    beats the preset that would have set 65. That ordering is the whole point of E1's "everything a
    preset sets remains individually overridable".
    """
    preset_name = (getattr(args, "preset", None) if "preset" in explicit
                   else file_values.get("preset", FIELDS["preset"][1]))
    if preset_name not in PRESETS:
        raise ConfigError(f"unknown preset {preset_name!r}; known presets: "
                          f"{', '.join(sorted(PRESETS))}")
    preset_values = PRESETS[preset_name]
    # Structural, not a comment: a preset that could set allow_fast_math would be a guarantee
    # loosened by a flag, which G5 forbids.
    assert set(preset_values) <= PRESET_SETTABLE, \
        f"preset {preset_name} sets {sorted(set(preset_values) - PRESET_SETTABLE)}, which no " \
        f"preset may touch"

    effective, provenance = {}, {}
    for name, (_typ, default) in FIELDS.items():
        if name in explicit:
            effective[name] = getattr(args, name)
            provenance[name] = "command line"
        elif name in preset_values and preset_name != FIELDS["preset"][1]:
            effective[name] = preset_values[name]
            provenance[name] = f"--preset {preset_name}"
        elif name in file_values:
            effective[name] = file_values[name]
            provenance[name] = file_path
        elif name in preset_values:
            effective[name] = preset_values[name]
            provenance[name] = "built-in default"
        else:
            effective[name] = getattr(args, name, default)
            provenance[name] = "built-in default"
    effective["preset"] = preset_name
    return {"values": effective, "provenance": provenance, "config_file": file_path,
            "preset": preset_name}
