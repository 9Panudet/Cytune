"""D27 — the gate's CHECKS and the gate's LICENCE keyed on different fields.

Found by an adversarial agent whose only instruction was to produce a false certificate.

    binding.assert_gate_bound  ->  `if gate.get("ran") and ...`   (config id, source tree)
    coherence I1.4             ->  `if gate.get("ran") and ...`
    safety_wording_earned      ->  `clean is True` alone
    apply.check_applicable     ->  `clean is True` alone

A gate carrying **`ran=False, clean=True`** fell in the hole between them: nothing checked which
configuration it described, and everything licensed it. The adversary used it twice —

  * to render `CLEAN — config 7 was rebuilt under ASan+UBSan and ran with no report` on a
    certificate emitting config 0;
  * to reproduce **D-3 exactly**: the reference emitted while carrying the demoted candidate's
    sanitizer verdict, under the words "best safe choice".

The same pass found `gate["authoritative"]` written in three places and read in **none**, so the
warning string `binding.py` embeds in the certificate — *"the 'safe' wording is withheld and
--apply refuses"* — was false in the same document that carried it.

Both are now answered by ONE predicate, `certify.gate_is_trustworthy`, used by
`safety_wording_earned`, by I1.6, and by `--apply`.
"""
from __future__ import annotations

import pytest

from cytune import apply as applymod
from cytune import certify

CLEAN = {"ran": True, "clean": True, "verdict": "CLEAN", "config_id": 288}


def _g(**kw):
    return {**CLEAN, **kw}


# ------------------------------------------------------------------ the predicate, case by case
def test_a_clean_gate_from_the_pinned_image_is_trustworthy():
    assert certify.gate_is_trustworthy(_g()) is True


def test_a_gate_that_did_not_run_cannot_be_clean():
    """THE HOLE. `ran=False, clean=True` is a contradiction, and it used to license everything."""
    assert certify.gate_is_trustworthy(_g(ran=False)) is False


def test_a_not_run_gate_is_still_not_trustworthy():
    """D23's ordinary case, unchanged: not-run is never a pass."""
    assert certify.gate_is_trustworthy(_g(ran=False, clean=None, verdict="IMAGE_UNAVAILABLE")) \
        is False


def test_an_unpinned_image_cannot_buy_the_wording():
    """H6, unchanged."""
    assert certify.gate_is_trustworthy(_g(image_overridden=True)) is False


def test_a_gate_that_did_not_attest_its_source_tree_is_not_trustworthy():
    """`authoritative` was written by binding.py and read by nothing. Its own warning string said
    the safe wording would be withheld; it was not."""
    assert certify.gate_is_trustworthy(_g(authoritative=False)) is False


def test_an_absent_authoritative_flag_is_not_treated_as_false():
    """`is not False`, not `truthy`: gates from the ordinary path never set the key at all, and
    treating absence as failure would refuse every clean run."""
    g = _g()
    g.pop("authoritative", None)
    assert certify.gate_is_trustworthy(g) is True


def test_the_predicate_is_total_over_none_and_empty():
    assert certify.gate_is_trustworthy(None) is False
    assert certify.gate_is_trustworthy({}) is False


# ------------------------------------------------------ every consumer uses the same predicate
def test_safety_wording_agrees_with_the_predicate():
    for g in (_g(), _g(ran=False), _g(image_overridden=True), _g(authoritative=False),
              _g(clean=None, ran=False)):
        assert certify.safety_wording_earned(g) == certify.gate_is_trustworthy(g), g


@pytest.mark.parametrize("bad", [
    {"ran": False, "clean": True},                 # the hole
    {"authoritative": False},                      # the inert flag
])
def test_apply_refuses_what_the_predicate_refuses(bad):
    cert = {"verdict": "improvement", "sanitizer_gate": _g(**bad),
            "emitted_config": {"config_id": 1392}}
    with pytest.raises(applymod.ApplyRefused):
        applymod.check_applicable(cert)


def test_apply_still_accepts_an_honest_clean_run():
    """The negative control. A tightening that refused everything would also pass every test
    above, and would be worthless."""
    cert = {"verdict": "improvement", "sanitizer_gate": _g(),
            "emitted_config": {"config_id": 1392}}
    assert applymod.check_applicable(cert) is None


def test_the_ordinary_not_run_refusal_still_says_not_run_is_not_a_pass():
    """The new check must not swallow D23's message for the ordinary `ran=False, clean=None` case
    — that message is the one users actually see, and it earned its wording."""
    cert = {"verdict": "improvement",
            "sanitizer_gate": _g(ran=False, clean=None, verdict="IMAGE_UNAVAILABLE"),
            "emitted_config": {"config_id": 1392}}
    with pytest.raises(applymod.ApplyRefused, match="NOT RUN IS NOT A PASS"):
        applymod.check_applicable(cert)


# ------------------------------------------------------------------------ the D-3 replay itself
def test_the_d3_replay_through_the_ran_false_hole_is_refused():
    """The adversary's exact construction: the reference is emitted while the gate still describes
    the rejected candidate, and `ran=False` means none of the binding checks look at it."""
    stale = {"ran": False, "clean": True, "verdict": "CLEAN", "config_id": 1392}
    assert certify.gate_is_trustworthy(stale) is False
    cert = {"verdict": "honest-flat", "sanitizer_gate": stale,
            "emitted_config": {"config_id": 288}}
    with pytest.raises(applymod.ApplyRefused):
        applymod.check_applicable(cert)


def test_there_is_exactly_one_licensing_predicate():
    """Anti-recurrence. The defect WAS two predicates for one question; this asserts the consumers
    call the shared one rather than re-implementing it."""
    import ast
    import inspect
    for fn in (certify.safety_wording_earned,):
        src = inspect.getsource(fn)
        assert "gate_is_trustworthy" in src
    coh = inspect.getsource(__import__("cytune.coherence", fromlist=["x"]))
    tree = ast.parse(coh)
    hits = [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "gate_is_trustworthy"]
    assert hits, "coherence I1.6 no longer routes through the shared predicate"
