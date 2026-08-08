"""E1/E2 — the two remaining setup frictions, and the failure paths that keep them honest.

`init` scaffolds a driver. The danger of a scaffold is not that it fails, it is that it succeeds
WRONGLY: an input cytune invented becomes the workload the oracle is derived from and every number
downstream is about a run the user never asked for. So most of what is tested here is the refusal
to guess.
"""
from __future__ import annotations

import os
import types

import pytest

from cytune import doctor as doctormod
from cytune import init as initmod
from cytune import rig
from cytune.session import Session


def _pyx(tmp_path, body, name="k.pyx"):
    p = tmp_path / name
    p.write_text(body)
    return str(p)


def _args(module, driver=None, force=False):
    return types.SimpleNamespace(module=module, driver=driver, force=force)


# ------------------------------------------------------------------ signature parsing
@pytest.mark.parametrize("decl,ndim", [
    ("double[::1] a", 1),
    ("double[:] a", 1),
    ("double[:, ::1] a", 2),
    ("long[:, :, ::1] a", 3),
    ("Py_ssize_t n", 0),
])
def test_dimensions_are_commas_plus_one_not_colons(decl, ndim):
    """FAILURE PATH of a bug this test was written after finding.

    Counting the colons in `[::1]` gives two, so a 1-D memoryview scaffolded a 4096x4096 array —
    134 MB — and `[:, ::1]` scaffolded 4096^3, which is 549 GB and would have taken out the
    container before calibration could shrink it.
    """
    assert initmod.parse_arguments(decl)[0]["ndim"] == ndim


def test_an_untyped_argument_becomes_a_todo_and_not_a_guess():
    """The refusal that matters. `obj` used to parse as an argument named `bj` of type `o`, which
    is a wrong guess wearing the costume of a confident one."""
    args = initmod.parse_arguments("double[::1] a, obj")
    assert [a["name"] for a in args] == ["a", "obj"]
    assert args[0]["known"] is True
    assert args[1]["known"] is False


def test_an_object_argument_is_not_invented(tmp_path):
    pyx = _pyx(tmp_path, "def run(double[::1] a, object payload):\n    return 0\n")
    text, notes = initmod.scaffold_driver(pyx)
    assert "payload = None   # TODO" in text
    assert any("payload" in n for n in notes)
    assert "cytune could not infer 1" in text, "the TODO must be visible at the top of the file"


def test_a_cdef_function_is_not_offered_as_an_entry_point(tmp_path):
    """`cdef` is not callable from Python; a driver pointed at one could never run."""
    pyx = _pyx(tmp_path, "cdef double helper(double x):\n    return x\n\n"
                         "def run(double[::1] a):\n    return 0\n")
    text, _notes = initmod.scaffold_driver(pyx)
    assert "mod.run(" in text and "mod.helper(" not in text


def test_the_workload_shrinks_with_dimensionality(tmp_path):
    one = initmod.scaffold_driver(_pyx(tmp_path, "def run(double[::1] a):\n    return 0\n"))[0]
    two = initmod.scaffold_driver(
        _pyx(tmp_path, "def run(double[:, ::1] a):\n    return 0\n", "k2.pyx"))[0]
    assert "SCALE = 4096" in one
    assert "SCALE = 512" in two


# ------------------------------------------------------------------------ the command
def test_the_scaffolded_driver_satisfies_the_real_contract_check(tmp_path, monkeypatch):
    """The scaffold is checked by the SAME function `tune` uses at ingest. A scaffold that
    produced a driver `tune` then rejected would be worse than no scaffold."""
    monkeypatch.chdir(tmp_path)
    pyx = _pyx(tmp_path, "def run(double[::1] a, long reps):\n    return 0\n")
    assert initmod.init(_args(pyx)) == 0
    driver = os.path.join(str(tmp_path), "driver.py")
    assert Session._driver_contract_gaps(driver) == []


def test_the_scaffolded_driver_is_valid_python_and_makes_real_inputs(tmp_path, monkeypatch):
    """Executed, not just parsed: `make_inputs` must produce arrays of the declared dtype."""
    numpy = pytest.importorskip("numpy")
    monkeypatch.chdir(tmp_path)
    pyx = _pyx(tmp_path, "def run(double[::1] a, long[::1] idx, Py_ssize_t n):\n    return 0\n")
    initmod.init(_args(pyx))
    ns = {}
    exec(compile(open(os.path.join(str(tmp_path), "driver.py")).read(), "driver.py", "exec"), ns)
    a, idx, n = ns["make_inputs"](1234)
    assert a.dtype == numpy.float64 and a.ndim == 1
    assert idx.dtype == numpy.int64 and idx.ndim == 1
    assert isinstance(n, int)
    # deterministic in the seed, which the measurement protocol requires
    assert numpy.array_equal(ns["make_inputs"](1234)[0], a)


def test_an_existing_driver_is_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pyx = _pyx(tmp_path, "def run(double[::1] a):\n    return 0\n")
    driver = tmp_path / "driver.py"
    driver.write_text("# mine\n")
    assert initmod.init(_args(pyx)) == 1
    assert driver.read_text() == "# mine\n"
    assert initmod.init(_args(pyx, force=True)) == 0
    assert "scaffolded by `cytune init`" in driver.read_text()


def test_an_existing_config_is_not_clobbered(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".cytune.toml").write_text("[cytune]\ntarget_ms = 12\n")
    initmod.init(_args(_pyx(tmp_path, "def run(double[::1] a):\n    return 0\n")))
    assert (tmp_path / ".cytune.toml").read_text() == "[cytune]\ntarget_ms = 12\n"


def test_the_written_config_is_one_cytune_accepts(tmp_path, monkeypatch):
    """A scaffolded config file that the config loader then rejects would be a first-run failure
    manufactured by the tool meant to prevent one."""
    from cytune import config as configmod
    monkeypatch.chdir(tmp_path)
    initmod.init(_args(_pyx(tmp_path, "def run(double[::1] a):\n    return 0\n")))
    values, path = configmod.load(str(tmp_path / ".cytune.toml"))
    assert path and values["target_ms"] == 65.0


def test_a_module_tree_is_scaffolded_from_its_main_pyx(tmp_path, monkeypatch):
    import json
    monkeypatch.chdir(tmp_path)
    tree = tmp_path / "mod"
    (tree / "closure" / "pkg").mkdir(parents=True)
    (tree / "closure" / "pkg" / "core.pyx").write_text("def compute(double[::1] a):\n    return 0\n")
    (tree / "kernel_meta.json").write_text(json.dumps(
        {"module": "core", "pyx_relpath": "pkg/core.pyx"}))
    assert initmod.init(_args(str(tree))) == 0
    assert "mod.compute(" in (tree / "driver.py").read_text()


# --------------------------------------------------------------- E2  doctor --build-image
def test_build_image_refuses_a_digest_that_is_not_the_pinned_one(monkeypatch, capsys):
    """FAILURE PATH. A build that succeeds and produces a DIFFERENT image is not a success — it is
    an unpinned toolchain, and reporting it green is exactly the H6 shape one layer down."""
    monkeypatch.setattr(doctormod, "CONTAINERFILE", __file__)      # any existing path
    monkeypatch.setattr(doctormod.subprocess, "call", lambda *a, **k: 0)
    monkeypatch.setattr(rig, "image_digest", lambda *a, **k: "sha256:" + "f" * 64)
    rc = doctormod.build_image()
    assert rc == 1
    err = capsys.readouterr().err
    assert "produced a different image" in err
    assert "not a pass" in err
    assert "--apply refuses" in err


def test_build_image_accepts_the_pinned_digest(monkeypatch, capsys):
    """The control. Without it the check could be 'always refuse', which would make the command
    useless and would still pass the test above."""
    monkeypatch.setattr(doctormod, "CONTAINERFILE", __file__)
    monkeypatch.setattr(doctormod.subprocess, "call", lambda *a, **k: 0)
    monkeypatch.setattr(rig, "image_digest", lambda *a, **k: rig.PINNED_IMAGE_DIGEST)
    assert doctormod.build_image() == 0
    assert "is the pinned toolchain" in capsys.readouterr().out


def test_build_image_reports_a_failed_build_without_claiming_verification(monkeypatch, capsys):
    monkeypatch.setattr(doctormod, "CONTAINERFILE", __file__)
    monkeypatch.setattr(doctormod.subprocess, "call", lambda *a, **k: 2)
    assert doctormod.build_image() == 1
    assert "Nothing was verified" in capsys.readouterr().err


def test_build_image_says_so_when_there_is_no_containerfile(monkeypatch, capsys):
    monkeypatch.setattr(doctormod, "CONTAINERFILE", "/nonexistent/Containerfile")
    assert doctormod.build_image() == 1
    assert "missing" in capsys.readouterr().err
