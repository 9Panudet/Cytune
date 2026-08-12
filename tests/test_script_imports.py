"""Every committed script's `cytune.*` imports must still resolve.

D25's general defence. `scripts/cytune_e2e_composition_check.py` imported `cytune._phasep`, a
subpackage renamed to `_vendor` at 1.0.0, so it died on import and had not run once since. It is
the host-side check for the composition class (D13/D14/D18) — the same class the B4 path registry
defends — and four separate mechanisms all failed to notice it was gone:

  * pytest does not collect it (by design: it spawns podman);
  * `smoke.sh` did not run it;
  * the package reachability walk covers `src/cytune/`, not `scripts/`;
  * nothing anywhere asserted that a committed script can be imported.

A skipped test prints `s`. A script nobody invokes prints nothing, and its absence is
indistinguishable from its success.

WHY STATIC RATHER THAN ACTUALLY IMPORTING. Most scripts here import numpy, sklearn, or the study
tree, and several execute work at module scope. Importing them all would be slow, fragile, and
would fail for reasons that are not drift. What D25 actually was is narrower and fully decidable
by parsing: a script naming a `cytune` submodule that no longer exists. This checks exactly that,
which is what makes it cheap enough to keep green.
"""
from __future__ import annotations

import ast
import importlib.util
import os

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPTS = os.path.join(REPO, "scripts")
PKG = os.path.join(REPO, "src", "cytune")


def _scripts():
    out = []
    for dirpath, dirnames, filenames in os.walk(SCRIPTS):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def _cytune_targets(path):
    """Every `cytune.<sub>` a file names at module scope, as dotted submodule paths."""
    try:
        tree = ast.parse(open(path).read())
    except SyntaxError as e:                       # a script that will not even parse is a defect
        pytest.fail(f"{os.path.relpath(path, REPO)} does not parse: {e}")
    targets = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "cytune" or a.name.startswith("cytune."):
                    targets.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:                          # relative import inside scripts/: not ours
                continue
            mod = node.module or ""
            if mod == "cytune" or mod.startswith("cytune."):
                targets.add(mod)
                for a in node.names:
                    targets.add(f"{mod}.{a.name}")
    return targets


def _exists(dotted):
    """Does `cytune.a.b` name a real module, package, or attribute of one?"""
    parts = dotted.split(".")
    assert parts[0] == "cytune"
    cur = PKG
    for i, p in enumerate(parts[1:], start=1):
        as_mod = os.path.join(cur, p + ".py")
        as_pkg = os.path.join(cur, p, "__init__.py")
        if os.path.exists(as_pkg):
            cur = os.path.join(cur, p)
            continue
        if os.path.exists(as_mod):
            # anything after a module name is an attribute, not a path we can check statically
            return True
        # `from cytune._vendor import designs_path` — the last component may be a NAME defined in
        # the package's own __init__.py rather than a submodule. Checked by parsing, so a real
        # typo is still caught while a legitimate re-export is not a false alarm.
        if i == len(parts) - 1 and _defines(os.path.join(cur, "__init__.py"), p):
            return True
        return False
    return True


def _defines(init_path, name):
    if not os.path.exists(init_path):
        return False
    try:
        tree = ast.parse(open(init_path).read())
    except SyntaxError:
        return False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                return True
        elif isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                return True
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                return True
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if any((a.asname or a.name.split(".")[0]) == name for a in node.names):
                return True
    return False


SCRIPT_FILES = _scripts()


def test_there_are_scripts_to_check():
    """Anti-vacuity: an empty file list would make every assertion below trivially true."""
    assert len(SCRIPT_FILES) >= 10, SCRIPT_FILES


@pytest.mark.parametrize("path", SCRIPT_FILES, ids=lambda p: os.path.relpath(p, SCRIPTS))
def test_every_script_names_only_cytune_modules_that_exist(path):
    bad = sorted(t for t in _cytune_targets(path) if not _exists(t))
    assert not bad, (
        f"{os.path.relpath(path, REPO)} imports {bad}, which the package no longer provides.\n"
        f"This is D25 exactly: `cytune._phasep` outlived the rename to `_vendor` and the script "
        f"died on import, unnoticed, for an entire release. Update the import, or delete the "
        f"script — a committed script that cannot import is worse than no script, because its "
        f"silence reads as success.")


def test_the_check_would_have_caught_d25(tmp_path):
    """Positive control, using the real defect. Without this, the test above proves only that
    every current import happens to be spelled correctly."""
    p = tmp_path / "d25.py"
    p.write_text("from cytune._phasep import theta\n")
    assert _cytune_targets(str(p)) == {"cytune._phasep", "cytune._phasep.theta"}
    assert not _exists("cytune._phasep")
    assert _exists("cytune._vendor")
    assert _exists("cytune._vendor.theta")
    assert _exists("cytune.certify")


def test_the_check_does_not_fire_on_an_attribute_of_a_real_module(tmp_path):
    """Negative control: `from cytune.certify import render` names an attribute, not a module, and
    must not be reported as missing."""
    p = tmp_path / "ok.py"
    p.write_text("from cytune.certify import render, EXIT_ERROR\nimport cytune.plan\n")
    assert all(_exists(t) for t in _cytune_targets(str(p)))
