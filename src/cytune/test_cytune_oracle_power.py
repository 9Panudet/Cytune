"""D26 — the correctness oracle must be able to fail.

G1 is "it will not recommend a configuration that produces wrong output". It rests entirely on
comparing each build's canonical output against a golden. If the golden is a constant array, that
comparison **cannot fail**: every build matches, correct or not. The certificate then reports
`rejected as incorrect: 0 (0.0% of measured)`, which reads as evidence and is arithmetically
forced.

FOUND BY A FIRST-TIME USER, on the first kernel they wrote, with no prompting. Their
`clip(x, lo, hi)` took two `double` scalars; `cytune init` invented `1.0` for both, so `lo == hi`,
so every output element was exactly `1.0`. Same kernel, same machine, same flags:

    driver exactly as `cytune init` wrote it   ->  IMPROVEMENT 1.0790x, exit 0
    one line fixed (lo=-2.0, hi=2.0)           ->  HONEST-FLAT  1.0000x, exit 2

and `--apply` accepted the first one and wrote a `boundscheck=False` header into their source —
the exact header the README warns can turn a latent off-by-one into an out-of-bounds read.

Every other instrument in this project is required to have a positive control: a planted 2x lever
must be detected, a known-flat kernel must read flat. The oracle — the instrument G1 is made of —
had none. These tests are it.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

from cytune import init as initmod
from cytune.session import Session


def _sess(tmp_path, golden):
    s = Session(str(tmp_path / "ws"), "k", "portable", "test", target_ms=0)
    os.makedirs(s.odir, exist_ok=True)
    np.save(os.path.join(s.odir, "golden.npy"), golden)
    return s


def test_a_constant_multi_element_golden_is_degenerate(tmp_path):
    """The exact shape the user hit: every element identical."""
    p = _sess(tmp_path, np.full(4096, 1.0)).oracle_power()
    assert p["checked"] and p["degenerate"] is True
    assert p["n"] == 4096 and p["n_distinct"] == 1


def test_a_varying_golden_has_power(tmp_path):
    p = _sess(tmp_path, np.arange(4096, dtype=float)).oracle_power()
    assert p["checked"] and p["degenerate"] is False
    assert p["n_distinct"] == 4096


def test_a_reduction_is_not_degenerate(tmp_path):
    """A sum returns one number. Refusing those would refuse a whole class of real kernels, and
    constancy is not degeneracy when there is only one value to be constant."""
    p = _sess(tmp_path, np.array([42.0])).oracle_power()
    assert p["checked"] and p["degenerate"] is False
    assert p["n"] == 1


def test_nearly_constant_is_not_degenerate(tmp_path):
    """The check is `can it fail at all`, not `does it discriminate well`. One differing element
    is enough for a wrong build to be caught, and claiming more than that would be overreach."""
    g = np.full(1000, 1.0)
    g[500] = 2.0
    p = _sess(tmp_path, g).oracle_power()
    assert p["degenerate"] is False and p["n_distinct"] == 2


def test_a_missing_or_unreadable_golden_is_reported_not_guessed(tmp_path):
    """`checked: False` must never be read as `degenerate: False`. A control that could not run
    is not a control that passed — the same rule the sanitizer gate follows."""
    s = Session(str(tmp_path / "ws2"), "k", "portable", "test", target_ms=0)
    os.makedirs(s.odir, exist_ok=True)
    p = s.oracle_power()
    assert p["checked"] is False and "degenerate" not in p

    with open(os.path.join(s.odir, "golden.npy"), "w") as f:
        f.write("not a numpy file")
    p = s.oracle_power()
    assert p["checked"] is False and "degenerate" not in p


def test_the_control_does_not_touch_the_vendored_rig():
    """`_vendor/campaign.py` is hash-pinned to the study source and may not diverge from it, so
    this control reads the golden the vendored rig already wrote instead of changing how it is
    produced. If that ever stops being true, the vendor manifest will say so."""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(Session.oracle_power).strip())
    fn = tree.body[0]
    body = fn.body[1:] if ast.get_docstring(fn) else fn.body      # skip the docstring itself
    code = "\n".join(ast.dump(n) for n in body)
    assert "golden.npy" in code
    assert "campaign" not in code, "the control reaches into the hash-pinned vendored rig"


# ------------------------------------------------------------------- the cause, not the symptom
def test_two_scalars_of_the_same_type_no_longer_collide():
    """`clip(x, lo, hi)` must not scaffold `lo == hi`. This is the defect at its source."""
    args = [{"name": "x", "type": "double", "ndim": 1, "dtype": "np.float64", "known": True},
            {"name": "lo", "type": "double", "ndim": 0, "dtype": "np.float64", "known": True},
            {"name": "hi", "type": "double", "ndim": 0, "dtype": "np.float64", "known": True}]
    vals = []
    n = 0
    for a in args:
        e = initmod._make_input_expr(a, scalar_ordinal=n)
        if a["ndim"] == 0:
            vals.append(e)
            n += 1
    assert len(set(vals)) == len(vals), f"scaffolded scalars collide: {vals}"


def test_three_scalars_are_all_distinct():
    a = {"name": "s", "type": "double", "ndim": 0, "dtype": "np.float64", "known": True}
    vals = [initmod._make_input_expr(a, scalar_ordinal=i) for i in range(3)]
    assert len(set(vals)) == 3, vals


def test_integer_scalars_are_also_distinct():
    a = {"name": "n", "type": "long", "ndim": 0, "dtype": "np.int64", "known": True}
    vals = [initmod._make_input_expr(a, scalar_ordinal=i) for i in range(3)]
    assert len(set(vals)) == 3, vals


def test_the_first_scalar_keeps_its_documented_default():
    """USER_GUIDE §0 documents the scaffolded defaults. Only REPEATS are perturbed, so a
    single-scalar kernel scaffolds exactly what the guide says it will."""
    a = {"name": "n", "type": "long", "ndim": 0, "dtype": "np.int64", "known": True}
    assert initmod._make_input_expr(a, scalar_ordinal=0) == "128"
    b = {"name": "x", "type": "double", "ndim": 0, "dtype": "np.float64", "known": True}
    assert initmod._make_input_expr(b, scalar_ordinal=0) == "1.0"


def test_a_clip_kernel_scaffolds_a_driver_whose_output_varies():
    """End to end at the level that matters: simulate what the scaffolded driver would compute for
    a clip, and assert the result is not constant. This is the user's kernel."""
    x = np.linspace(-3, 3, 256)
    lo = float(initmod._make_input_expr(
        {"name": "lo", "type": "double", "ndim": 0, "dtype": "np.float64", "known": True},
        scalar_ordinal=0))
    hi = float(initmod._make_input_expr(
        {"name": "hi", "type": "double", "ndim": 0, "dtype": "np.float64", "known": True},
        scalar_ordinal=1))
    assert lo != hi
    out = np.clip(x, min(lo, hi), max(lo, hi))
    assert np.unique(out).size > 1, (
        f"with lo={lo} hi={hi} a clip still returns a constant — the oracle would be blind")
