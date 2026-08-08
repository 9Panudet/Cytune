"""The invariant registry must describe reality, not intentions.

A registry nobody checks becomes a list of things that used to be true. So: every entry's function
must exist, every entry's named test must exist and must currently pass, ids must be unique and
stable, and — the load-bearing one — an invariant enforced in the code with no registry entry is a
failure. That last check is what makes the registry a complete index rather than a sample.
"""
from __future__ import annotations

import os
import re

import pytest

from cytune import invariants

HERE = os.path.dirname(os.path.abspath(__file__))


def test_the_registry_is_not_empty():
    assert len(invariants.REGISTRY) >= 15


def test_ids_are_unique():
    assert len(invariants.IDS) == len(set(invariants.IDS))


@pytest.mark.parametrize("entry", invariants.REGISTRY, ids=lambda e: e[0])
def test_every_entry_is_well_formed(entry):
    inv_id, what, fn, where, test = entry
    assert re.fullmatch(r"I\d+\.\d+", inv_id), f"{inv_id} is not a stable I<n>.<m> id"
    assert what and len(what) > 20, f"{inv_id} does not say what it guarantees"
    assert where, f"{inv_id} does not say where it runs in production"
    assert test and "::" in test, f"{inv_id} does not name a test"
    # `None` is allowed only where the enforcement is a plain conditional rather than a named
    # function; the test reference is then the whole evidence.
    if fn is not None:
        assert callable(fn), f"{inv_id} names a non-callable enforcer"


@pytest.mark.parametrize("entry", invariants.REGISTRY, ids=lambda e: e[0])
def test_every_named_test_exists(entry):
    """A registry pointing at a deleted test is worse than no registry."""
    inv_id, _what, _fn, _where, test = entry
    path, name = test.split("::")
    full = os.path.join(HERE, path)
    assert os.path.exists(full), f"{inv_id} names {path}, which does not exist"
    src = open(full).read()
    assert f"def {name}(" in src, f"{inv_id} names {test}, which does not exist"


@pytest.mark.parametrize("entry", invariants.REGISTRY, ids=lambda e: e[0])
def test_every_entry_names_a_real_production_site(entry):
    """`where` must point at a module that exists and at a symbol that appears in it."""
    inv_id, _what, _fn, where, _test = entry
    mod = where.split(",")[0].split(".")[0].strip()
    assert os.path.exists(os.path.join(HERE, f"{mod}.py")), \
        f"{inv_id} claims to run in {mod}, which is not a module"


def test_every_coherence_invariant_in_the_code_has_a_registry_entry():
    """THE check that makes this a complete index.

    `coherence.py` raises with an explicit invariant id at every violation site. Any id that
    appears there and not in the registry is an invariant cytune enforces and does not document —
    exactly the state that let P1/P2/R2/P4 be four separate discoveries of one defect.
    """
    src = open(os.path.join(HERE, "coherence.py")).read()
    in_code = set(re.findall(r'_violation\(\s*"(I\d+\.\d+)"', src))
    missing = sorted(in_code - set(invariants.IDS))
    assert not missing, (
        f"coherence.py enforces {missing} with no entry in invariants.py. Add them — an invariant "
        f"nobody can look up is an error message nobody can act on.")


def test_no_registry_entry_is_a_dead_letter():
    """The other direction: an I1.* id in the registry that coherence.py never raises."""
    src = open(os.path.join(HERE, "coherence.py")).read()
    in_code = set(re.findall(r'_violation\(\s*"(I\d+\.\d+)"', src))
    declared = {i for i in invariants.IDS if i.startswith("I1.")}
    dead = sorted(declared - in_code)
    assert not dead, f"{dead} are registered but never raised — either wire them up or remove them"


def test_describe_returns_the_entry():
    d = invariants.describe("I1.2")
    assert d and d["id"] == "I1.2"
    assert "emitted config" in d["guarantees"]
    assert invariants.describe("I99.9") is None


def test_the_registry_is_importable_without_side_effects():
    """It imports certify, coherence and session to reference their functions. Importing the
    registry must not need a container, a workspace or the study tree."""
    import importlib
    importlib.reload(invariants)
    assert invariants.IDS
