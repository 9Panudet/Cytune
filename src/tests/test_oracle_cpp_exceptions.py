"""Step 1.1.1 cond 3 (ii) — oracle §3.1 exception-identity on C++ corpus units.

A C++ Cython unit's `except +` translates a thrown C++ exception into a Python
exception; the oracle compares the TRANSLATED Python type by canonical identity.
This builds a REAL C++ unit (image X' g++-13), captures the actual translated
exception, asserts the deterministic mapping, and feeds it through the oracle's
exception-identity comparator — so the I-3 rig is validated on C++ exception
semantics, not assumed. (Evidence basis: logs/env/STEP_1.1.1_cpp_sanitizer.log.)
"""
import importlib.util
import shutil
import subprocess
import sysconfig

import pytest

from motifbo.build.profiles import performance_argv
from motifbo.oracle.bitwise import Outcome, compare_outcomes

PYINC = sysconfig.get_paths()["include"]

CPP_RAISERS_PYX = """\
# distutils: language = c++
# cython: language_level=3
cdef extern from * nogil:
    '''
    #include <stdexcept>
    static void _oor(){ throw std::out_of_range("x"); }
    static void _len(){ throw std::length_error("x"); }
    static void _inv(){ throw std::invalid_argument("x"); }
    '''
    void _oor() except +
    void _len() except +
    void _inv() except +
def raise_out_of_range():     _oor()
def raise_length_error():     _len()
def raise_invalid_argument(): _inv()
"""

# Cython's default `except +` map (confirmed empirically, cpp_probe):
EXPECTED = {
    "raise_out_of_range": IndexError,
    "raise_length_error": RuntimeError,      # no specific map -> catch-all RuntimeError
    "raise_invalid_argument": ValueError,
}


@pytest.fixture(scope="module")
def cpp_raisers(tmp_path_factory):
    if shutil.which("cython") is None or shutil.which("g++-13") is None:
        pytest.fail("image X' (:phase1) must provide cython + g++-13 for C++ units")
    d = tmp_path_factory.mktemp("cppexc")
    (d / "raisers.pyx").write_text(CPP_RAISERS_PYX)
    subprocess.run(["cython", "-3", "--cplus", str(d / "raisers.pyx")], check=True)
    so = d / "raisers.so"
    subprocess.run(performance_argv(["-O1"], ffp_contract="fast",
                                    c_path=str(d / "raisers.cpp"), so_path=str(so),
                                    py_include=PYINC, language="c++"), check=True)
    spec = importlib.util.spec_from_file_location("raisers", so)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _capture(m, fn):
    try:
        getattr(m, fn)()
    except BaseException as e:  # noqa: BLE001 — we want the exact translated type
        return e
    pytest.fail(f"{fn} did not raise")


def test_cpp_exceptions_map_to_stable_python_types(cpp_raisers):
    for fn, exp in EXPECTED.items():
        got = _capture(cpp_raisers, fn)
        assert type(got) is exp, f"{fn} -> {type(got)} (expected {exp})"


def test_oracle_identity_match_on_cpp_translated_exceptions(cpp_raisers):
    # Same C++-translated type on both sides -> identity match (None).
    for fn, exp in EXPECTED.items():
        got = _capture(cpp_raisers, fn)
        assert compare_outcomes(Outcome.exception(exp), Outcome.exception(got)) is None


def test_oracle_catches_wrong_cpp_exception(cpp_raisers):
    # Different type -> §3.5 wrong-exception mismatch (feasibility 0).
    got = _capture(cpp_raisers, "raise_out_of_range")  # -> IndexError
    reason = compare_outcomes(Outcome.exception(ValueError), Outcome.exception(got))
    assert reason is not None and "wrong exception" in reason


def test_cpp_exception_subclass_does_not_satisfy_identity(cpp_raisers):
    # §3.1: a subclass of the mapped type never satisfies exception identity —
    # the oracle requires the exact canonical name, not isinstance.
    class SubIndexError(IndexError):
        pass

    got = _capture(cpp_raisers, "raise_out_of_range")  # -> builtins.IndexError
    assert compare_outcomes(Outcome.exception(SubIndexError),
                            Outcome.exception(got)) is not None
