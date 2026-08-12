"""The vendored rig may not drift from the study rig it was copied from.

`cytune/_vendor/` exists so the product ships standalone (A2). The cost of a copy is drift: someone
fixes a bug in `scripts/phasep/campaign.py` and the product keeps the bug, or someone "tidies" the
vendored copy and the product silently stops measuring the way every number in `results/` was
measured. Either direction breaks the ground-truth dogfood in the release report, which compares
cytune's answer against frozen tables produced by exactly this code.

THREE PINS, because the files come in three kinds:

  whole-file   sha256 of the vendored file == sha256 of the study original.
  per-function source text of each named function == the study's, for the three files that were
               deliberately trimmed to what the product reaches (A3).
  constants    the module-scope constants a trimmed file exports, compared by their evaluated
               value, because a trimmed file's constants are not covered by either pin above.

TWO TIERS, AND WHY THE MANIFEST EXISTS (B2).

Until the launch pass, every one of these comparisons went straight to `scripts/phasep/*` and
called `pytest.skip` when it was absent. On a product-only branch that is EVERY comparison,
forever — 12 of 14 collected items skipped, and the two that still ran tested nothing about drift.
This project named that failure mode itself, in D23: *a check that never runs leaves no trace*. The
manifest points that lesson at the check.

  TIER 1 — runs everywhere, no study tree needed. `_vendor/*` is compared against
           `_vendor/VENDOR_MANIFEST.json`, which ships inside the package.
  TIER 2 — runs only where the study tree is present (dev / research). The MANIFEST is compared
           against the study source, so the manifest cannot silently drift from the thing it
           claims to represent either.

A wheel therefore verifies that the vendored rig is the one that was audited; a full checkout
additionally verifies that the audit record still matches the study. Neither tier can go quiet:
`test_the_manifest_covers_every_vendored_module` fails if a new vendored file is unpinned, and
`test_tier_1_is_not_vacuous` fails if the manifest is empty or truncated.
"""
from __future__ import annotations

import ast
import hashlib
import json
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

# Module-scope constants of the TRIMMED files. These are the gap the launch pass found: the
# whole-file pin does not cover a trimmed file, and the per-function pin only covers `def`s, so
# `sanitizer_build.py`'s own docstring claimed a test asserted `SAN_TOKENS` and `CORNERS` were
# equal to the study's when no such assertion existed anywhere. `SAN_TOKENS` is the token set the
# §1.4 sanitizer gate matches on (`sanitize_gate.py`); silently losing one token turns a real
# AddressSanitizer report into a CLEAN verdict. That is the highest-consequence unpinned surface in
# the package, so it is pinned rather than the claim deleted.
CONSTANTS = {
    "sanitizer_build.py": ["SAN_TOKENS", "CORNERS"],
}

MANIFEST = os.path.join(VENDOR, "VENDOR_MANIFEST.json")


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


def _const_sha(path, name):
    """sha256 of a module-scope constant's VALUE, canonicalised.

    By value rather than by source text, so reformatting a literal is not a false alarm while
    changing a single token is a real one. `ast.literal_eval` keeps this a pure parse: the module
    is never imported, so a constant pin cannot execute study code.
    """
    src = open(path).read()
    for node in ast.parse(src).body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for t in targets:
            if isinstance(t, ast.Name) and t.id == name and node.value is not None:
                try:
                    val = ast.literal_eval(node.value)
                except ValueError:
                    return None
                canon = json.dumps(sorted(val) if isinstance(val, (set, frozenset)) else val,
                                   sort_keys=True, default=str)
                return hashlib.sha256(canon.encode()).hexdigest()
    return None


def _manifest():
    if not os.path.exists(MANIFEST):
        pytest.fail(f"no vendor manifest at {MANIFEST} — regenerate it with "
                    f"scripts/release/build_vendor_manifest.py. Without it the drift check is "
                    f"vacuous on any branch that does not carry the study tree.")
    return json.load(open(MANIFEST))


# ------------------------------------------------------------------ TIER 1: runs on every branch
@pytest.mark.parametrize("vend", sorted(WHOLE_FILE))
def test_tier1_vendored_file_matches_the_manifest(vend):
    man = _manifest()
    assert vend in man["whole_file"], (
        f"{vend} is vendored but not pinned in VENDOR_MANIFEST.json — it can drift undetected on "
        f"any branch without the study tree.")
    assert _sha(os.path.join(VENDOR, vend)) == man["whole_file"][vend]["sha256"], (
        f"cytune/_vendor/{vend} does not match the committed manifest. Either the file was edited "
        f"in place, or it was re-synced from the study without regenerating the manifest "
        f"(scripts/release/build_vendor_manifest.py).")


@pytest.mark.parametrize("vend", sorted(PER_FUNCTION))
def test_tier1_vendored_functions_match_the_manifest(vend):
    man = _manifest()
    pinned = man["per_function"][vend]["functions"]
    path = os.path.join(VENDOR, vend)
    bad = []
    for fn, want in sorted(pinned.items()):
        src = _func_source(path, fn)
        assert src is not None, f"{vend} no longer defines {fn}"
        if hashlib.sha256(src.encode()).hexdigest() != want:
            bad.append(fn)
    assert not bad, f"cytune/_vendor/{vend}: {bad} differ from the committed manifest"


@pytest.mark.parametrize("vend", sorted(CONSTANTS))
def test_tier1_vendored_constants_match_the_manifest(vend):
    """The gap the launch pass found: a trimmed file's constants were pinned by nothing.

    `sanitizer_build.SAN_TOKENS` is what `sanitize_gate` matches an AddressSanitizer report
    against. Dropping a token would turn a real memory-safety report into a CLEAN verdict, and
    every pin in this file would have stayed green.
    """
    man = _manifest()
    pinned = man["constants"][vend]
    path = os.path.join(VENDOR, vend)
    bad = [n for n, want in sorted(pinned.items()) if _const_sha(path, n) != want]
    assert not bad, f"cytune/_vendor/{vend}: constants {bad} differ from the committed manifest"


@pytest.mark.parametrize("rel_in_pkg", sorted(DATA_FILES))
def test_tier1_vendored_data_file_matches_the_manifest(rel_in_pkg):
    man = _manifest()
    assert _sha(os.path.join(HERE, rel_in_pkg)) == man["data_files"][rel_in_pkg]["sha256"]


def test_the_manifest_covers_every_vendored_module():
    """Anti-vacuity: a NEW vendored file must be pinned, or this fails.

    Without this, B2 closes the hole for today's files and reopens it for tomorrow's.
    """
    man = _manifest()
    covered = set(man["whole_file"]) | set(man["per_function"])
    # `__init__.py` is product-authored packaging glue (sys.path + designs_path), not a copy of
    # anything in the study, so there is nothing to pin it against. It is the ONLY exemption.
    exempt = {"__init__.py"}
    present = {f for f in os.listdir(VENDOR) if f.endswith(".py")}
    unpinned = sorted(present - covered - exempt)
    assert not unpinned, (
        f"vendored modules with no manifest entry: {unpinned}. Add them to WHOLE_FILE or "
        f"PER_FUNCTION and regenerate the manifest, or the drift check silently does not cover "
        f"them.")


def test_tier_1_is_not_vacuous():
    """A manifest that is empty, truncated, or stale-by-count protects nothing."""
    man = _manifest()
    assert man.get("schema") == "cytune-vendor-manifest/1"
    assert len(man["whole_file"]) == len(WHOLE_FILE)
    assert len(man["per_function"]) == len(PER_FUNCTION)
    for vend, (_rel, funcs) in PER_FUNCTION.items():
        assert sorted(man["per_function"][vend]["functions"]) == sorted(funcs), (
            f"the manifest pins a different function set for {vend} than PER_FUNCTION declares")
    for vend, names in CONSTANTS.items():
        assert sorted(man["constants"][vend]) == sorted(names)
    assert len(man["data_files"]) == len(DATA_FILES)


def test_tier1_would_catch_a_one_byte_edit():
    """Positive control for the manifest pin itself, on a scratch copy — the real files are not
    touched. Without this, `test_tier1_*` passing proves only that sha256 is deterministic."""
    import shutil
    import tempfile
    vend = sorted(WHOLE_FILE)[0]
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, vend)
        shutil.copy(os.path.join(VENDOR, vend), p)
        assert _sha(p) == _manifest()["whole_file"][vend]["sha256"]
        with open(p, "a") as f:
            f.write("\n")
        assert _sha(p) != _manifest()["whole_file"][vend]["sha256"]


def test_the_constant_pin_would_catch_a_dropped_token():
    """Positive control for the constants pin, the one that guards the sanitizer verdict."""
    import tempfile
    a = 'SAN_TOKENS = ("AddressSanitizer", "runtime error")\n'
    b = 'SAN_TOKENS = ("AddressSanitizer",)\n'
    c = 'SAN_TOKENS = (\n    "AddressSanitizer",\n    "runtime error",\n)\n'
    with tempfile.TemporaryDirectory() as d:
        pa, pb, pc = (os.path.join(d, n) for n in ("a.py", "b.py", "c.py"))
        for p, s in ((pa, a), (pb, b), (pc, c)):
            open(p, "w").write(s)
        assert _const_sha(pa, "SAN_TOKENS") != _const_sha(pb, "SAN_TOKENS")   # dropped token: caught
        assert _const_sha(pa, "SAN_TOKENS") == _const_sha(pc, "SAN_TOKENS")   # reformat: not a hit
        assert _const_sha(pa, "MISSING") is None


# ------------------------------------- TIER 2: only where the study tree is present (dev/research)
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


@pytest.mark.parametrize("vend", sorted(CONSTANTS))
def test_the_manifests_constants_still_match_the_study(vend):
    """Tier 2 for the constants pin: the manifest must not drift from the study either."""
    rel = PER_FUNCTION[vend][0]
    study = _study(rel)
    man = _manifest()["constants"][vend]
    bad = [n for n, want in sorted(man.items())
           if _const_sha(study, n) is not None and _const_sha(study, n) != want]
    assert not bad, (
        f"the manifest pins {bad} for {vend}, but the study source now has different values. "
        f"Re-sync the vendored file and regenerate the manifest.")


def test_the_drift_check_is_not_vacuously_skipping():
    """A pin that skips everywhere protects nothing.

    In a full checkout every TIER 2 comparison above must actually run. This asserts the study tree
    is reachable and that each mapped source really exists, so a renamed or deleted study file
    surfaces as a failure here rather than as twelve silent skips.

    Note what this test can and cannot do: it guards TIER 2 only. Tier 1 needs no such guard
    because it cannot skip — that is the entire point of the manifest.
    """
    if not os.path.isdir(STUDY):
        pytest.skip("study tree absent (standalone install) — TIER 2 cannot be checked here; "
                    "TIER 1 has already compared every vendored file against the manifest")
    # The study CODE tree (`scripts/phasep`, `src/motifbo`) is on `dev` and `research`; the study
    # DATA (`results/`) is on `research` only. Lumping them made this test fail on `dev` for a
    # file that is not supposed to be there — found by running the suite from a clean clone of each
    # branch, which is the only way that distinction shows up.
    sources = list(WHOLE_FILE.values()) + [v[0] for v in PER_FUNCTION.values()]
    # Include the DATA pins only when the study DATA tree is actually POPULATED on this branch.
    # Keying on `os.path.isdir("results")` was not enough: a working tree switched from `research`
    # to `dev` keeps an empty-ish `results/` full of untracked leftovers while the one tracked file
    # this pin needs has been deleted by the branch switch. That is the branch hazard in
    # docs/system/15_BRANCH_HAZARD.md, and it made the guard demand a file that is not supposed to
    # be on this branch at all.
    if any(os.path.exists(os.path.join(REPO, rel)) for rel in DATA_FILES.values()):
        sources += list(DATA_FILES.values())
    missing = [rel for rel in sources if not os.path.exists(os.path.join(REPO, rel))]
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
