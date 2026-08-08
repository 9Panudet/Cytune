"""The vendored rig may not drift from the study rig it was copied from.

`cytune/_vendor/` exists so the product ships standalone (A2). The cost of a copy is drift: someone
fixes a bug in `scripts/phasep/campaign.py` and the product keeps the bug, or someone "tidies" the
vendored copy and the product silently stops measuring the way every number in `results/` was
measured. Either direction breaks the ground-truth dogfood in the release report, which compares
cytune's answer against frozen tables produced by exactly this code.

TWO PINS, because the files come in two kinds:

  whole-file   sha256 of the vendored file == sha256 of the study original.
  per-function source text of each named function == the study's, for the three files that were
               deliberately trimmed to what the product reaches (A3).

WHEN THE STUDY TREE IS ABSENT — an installed wheel, or a user's checkout of just the package — the
comparison is impossible. These tests then SKIP with the reason stated. A skip is not a pass, and
`test_the_drift_check_is_not_vacuously_skipping` fails loudly if the study tree is present but no
file was actually compared.
"""
from __future__ import annotations

import ast
import hashlib
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, "_vendor")
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
STUDY = os.path.join(REPO, "scripts", "phasep")

# vendored filename -> study source path (relative to the repo root)
WHOLE_FILE = {
    "theta.py": "scripts/phasep/theta.py",
    "build.py": "scripts/phasep/build.py",
    "seeds.py": "scripts/phasep/seeds.py",
    "measure_child.py": "scripts/phasep/measure_child.py",
    "san_child.py": "scripts/phasep/san_child.py",
    "classify.py": "scripts/phasep/classify.py",
    "profiles.py": "src/motifbo/build/profiles.py",
}

# vendored file -> (study source, the functions that must match character-for-character)
PER_FUNCTION = {
    "campaign.py": ("scripts/phasep/campaign.py",
                    ["_rig", "_module_of", "_knob_line", "build_all", "_manifest",
                     "_measure_one", "calibrate", "golden_and_oracle", "measure_all"]),
    "algorithms.py": ("scripts/phasep/algorithms.py",
                      ["_ridge_fit", "_fit", "_pred_rank"]),
    "sanitizer_build.py": ("scripts/phasep/sanitizer_spot_audit.py",
                           ["_sanitizer_build"]),
}

# Package data that must equal its frozen source.
#
# `measure_wrap.sh` and the `Containerfile` are deliberately NOT here. They are host/build
# infrastructure that a pip-installed cytune cannot use anyway, and vendoring measure_wrap.sh
# actively broke it — it resolves a sibling `scripts/thermal_log.sh` through
# `REPO_ROOT="$(dirname $0)/.."`, so the package copy died with rc=127 mid-run. See rig.py.
DATA_FILES = {
    os.path.join("_vendor", "data", "doe_designs_theta.json"):
        "results/prereg/doe_designs_theta.json",
}


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _study(rel):
    p = os.path.join(REPO, rel)
    if not os.path.exists(p):
        pytest.skip(f"study source absent (standalone install): {rel}")
    return p


def _func_source(path, name):
    """Exact source text of a top-level function, docstring and all."""
    src = open(path).read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(src, node)
    return None


@pytest.mark.parametrize("vend,rel", sorted(WHOLE_FILE.items()))
def test_vendored_file_is_byte_identical_to_the_study_source(vend, rel):
    study = _study(rel)
    got, want = os.path.join(VENDOR, vend), study
    assert _sha(got) == _sha(want), (
        f"cytune/_vendor/{vend} has drifted from {rel}.\n"
        f"These must stay byte-identical: the product measures through the study's audited rig, "
        f"and the release report's ground-truth dogfood compares cytune's answers against tables "
        f"produced by that exact code. Re-copy whichever side is correct — do not edit one of them "
        f"in place.")


@pytest.mark.parametrize("vend,rel", sorted(DATA_FILES.items()))
def test_vendored_data_file_is_byte_identical(vend, rel):
    study = _study(rel)
    assert _sha(os.path.join(HERE, vend)) == _sha(study), (
        f"cytune/{vend} has drifted from {rel}")


@pytest.mark.parametrize("vend", sorted(PER_FUNCTION))
def test_vendored_functions_match_the_study_source(vend):
    rel, funcs = PER_FUNCTION[vend]
    study = _study(rel)
    mine = os.path.join(VENDOR, vend)
    diffs = []
    for fn in funcs:
        a, b = _func_source(mine, fn), _func_source(study, fn)
        assert a is not None, f"{vend} no longer defines {fn}"
        assert b is not None, f"{rel} no longer defines {fn} — the study source moved or renamed it"
        if a != b:
            diffs.append(fn)
    assert not diffs, (
        f"cytune/_vendor/{vend}: {diffs} differ from {rel}. The file is trimmed to the functions "
        f"the product reaches, but the functions it keeps must be the study's verbatim.")


def test_the_drift_check_is_not_vacuously_skipping():
    """A pin that skips everywhere protects nothing.

    In a full checkout every comparison above must actually run. This asserts the study tree is
    reachable and that each mapped source really exists, so a renamed or deleted study file
    surfaces as a failure here rather than as fourteen silent skips.
    """
    if not os.path.isdir(STUDY):
        pytest.skip("study tree absent (standalone install) — drift cannot be checked here")
    missing = [rel for rel in list(WHOLE_FILE.values()) + list(DATA_FILES.values())
               + [v[0] for v in PER_FUNCTION.values()]
               if not os.path.exists(os.path.join(REPO, rel))]
    assert not missing, (
        f"the study tree is present but these mapped sources are gone: {missing}. The vendored "
        f"copies are now unpinned — update the mapping or restore the sources.")


def test_the_function_comparison_would_catch_an_edit():
    """Positive control for the per-function pin: a one-character change must be detected."""
    import tempfile
    a = "def f(x):\n    return x + 1\n"
    b = "def f(x):\n    return x + 2\n"
    with tempfile.TemporaryDirectory() as d:
        pa, pb = os.path.join(d, "a.py"), os.path.join(d, "b.py")
        open(pa, "w").write(a)
        open(pb, "w").write(b)
        assert _func_source(pa, "f") != _func_source(pb, "f")
        assert _func_source(pa, "f") == _func_source(pa, "f")
        assert _func_source(pa, "missing") is None


def test_the_vendored_designs_are_the_frozen_prereg_designs():
    """The DOE/probe design file is a pre-registered input to the search (PREREG §8.2). Shipping a
    different one would change which configs are measured while every document still claimed the
    pre-registered design."""
    import json
    from cytune._vendor import designs_path
    d = json.load(open(designs_path()))["designs"]
    assert "probe_16" in d and "doe_24" in d
    assert len(d["probe_16"]["config_ids"]) == 16
