"""A-4d data firewall — cytune must never reach for fleet / holdout H / R-anchor data.

This is the amendment clause that keeps §3.5 evaluable: RQ-P2 is evaluated at P4 on H + R against a
router those datasets never informed. A stray path in the product would quietly destroy that, and
would be very hard to notice by reading a diff.

The check is AST-based over string literals, EXCLUDING docstrings — the modules legitimately
discuss the firewall in prose, and a substring scan would either flag that prose or be softened
until it flagged nothing.
"""
import ast
import glob
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))

FORBIDDEN = ("results/fleet", "fleet_ledger", "holdout", "r_anchor", "anchors",
             "FREEZE_MANIFEST", "class_v2")


def _docstring_nodes(tree):
    """Every string node that is a docstring, by identity."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def scan_source(src):
    """Return the forbidden fragments appearing in non-docstring string literals."""
    tree = ast.parse(src)
    docs = _docstring_nodes(tree)
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            low = node.value.lower()
            for frag in FORBIDDEN:
                if frag.lower() in low:
                    hits.append((frag, node.value))
    return hits


def _product_sources():
    """Every shipped .py in the package, INCLUDING `_vendor/`.

    This used to glob `HERE/*.py` only. That was correct while the measurement rig was imported
    from `scripts/phasep` at runtime, and became a hole the moment the rig was vendored into the
    package: `_vendor/campaign.py` and friends are product code now, they came from the study
    tree, and they are exactly the files most likely to carry a stray study path. A firewall that
    does not scan the newest half of the package is not a firewall.
    """
    return sorted(p for p in glob.glob(os.path.join(HERE, "**", "*.py"), recursive=True)
                  if not os.path.basename(p).startswith("test_"))


@pytest.mark.parametrize("path", _product_sources(), ids=os.path.basename)
def test_no_cytune_module_references_study_data(path):
    hits = scan_source(open(path).read())
    assert not hits, (f"{os.path.basename(path)} references study data (A-4d forbids it): {hits}")


def test_the_firewall_check_actually_catches_a_violation():
    """Positive control. Without this, a checker that silently matched nothing would 'pass'."""
    planted = 'import json\nrows = open("results/fleet/fleet_ledger.jsonl").read()\n'
    hits = scan_source(planted)
    assert hits, "the firewall scanner failed to flag a planted violation — it is vacuous"
    assert any(f == "results/fleet" for f, _ in hits)


def test_the_firewall_check_does_not_flag_prose_about_the_firewall():
    """Negative control: docstrings may discuss fleet/holdout without tripping the check."""
    prose = '"""cytune never reads results/fleet, the holdout, or the r_anchor tables."""\nx = 1\n'
    assert scan_source(prose) == []
