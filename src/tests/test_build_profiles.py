"""Step 0.4.1 — build-profile smoke/golden tests (infrastructure; §6.3 item: smoke).

Two layers: (1) pure argv-shape assertions for the performance/sanitizer profiles,
including the §3.2(3) always-explicit-`-ffp-contract` invariant; (2) real in-container
builds proving the performance build loads & runs, the sanitizer build runs clean,
and — non-vacuity — the sanitizer build CATCHES a deliberate heap-buffer-overflow.
"""
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest

from motifbo.build.profiles import (
    performance_argv,
    sanitizer_argv,
    sanitizer_runtime_env,
)

PYINC = sysconfig.get_paths()["include"]


# --- argv shape (pure) -------------------------------------------------------

def test_performance_argv_shape():
    argv = performance_argv(["-O3", "-march=native", "-funroll-loops"],
                            ffp_contract="off", c_path="k.c", so_path="k.so",
                            py_include=PYINC)
    assert argv[0] == "gcc"
    assert argv[-3:] == ["k.c", "-o", "k.so"]
    for f in ("-O3", "-march=native", "-funroll-loops", "-g0", "-pipe",
              "-shared", "-fPIC", "-ffp-contract=off"):
        assert f in argv, f"missing {f}"
    assert "-g" not in argv and "-fsanitize=address,undefined" not in argv


def test_sanitizer_argv_shape():
    argv = sanitizer_argv(ffp_contract="off", c_path="k.c", so_path="k.so",
                          py_include=PYINC)
    for f in ("-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
              "-O1", "-shared", "-fPIC", "-ffp-contract=off"):
        assert f in argv, f"missing {f}"
    assert "-g0" not in argv  # sanitizer keeps debug symbols (§1.5 item 1)


def test_fast_math_class_dimension_adds_flag():
    assert "-ffast-math" in sanitizer_argv(ffp_contract="fast", c_path="k.c",
                                           so_path="k.so", py_include=PYINC,
                                           fast_math=True)
    assert "-ffast-math" not in sanitizer_argv(ffp_contract="off", c_path="k.c",
                                               so_path="k.so", py_include=PYINC)


# --- §3.2(3): -ffp-contract always explicit ----------------------------------

def test_contract_always_present_and_unique():
    for argv in (performance_argv([], ffp_contract="on", c_path="k.c",
                                  so_path="k.so", py_include=PYINC),
                 sanitizer_argv(ffp_contract="on", c_path="k.c", so_path="k.so",
                                py_include=PYINC)):
        contract = [f for f in argv if f.startswith("-ffp-contract=")]
        assert contract == ["-ffp-contract=on"], argv


def test_contract_is_required():
    with pytest.raises(TypeError):
        performance_argv([], c_path="k.c", so_path="k.so", py_include=PYINC)
    with pytest.raises(TypeError):
        sanitizer_argv(c_path="k.c", so_path="k.so", py_include=PYINC)


def test_invalid_contract_rejected():
    for bad in ("default", "", None, "FAST"):
        with pytest.raises(ValueError):
            performance_argv([], ffp_contract=bad, c_path="k.c", so_path="k.so",
                             py_include=PYINC)


def test_performance_rejects_caller_owned_flags():
    for smuggled in ("-ffp-contract=fast", "-g", "-g0", "-fsanitize=address"):
        with pytest.raises(ValueError):
            performance_argv([smuggled], ffp_contract="off", c_path="k.c",
                             so_path="k.so", py_include=PYINC)


# --- runtime env -------------------------------------------------------------

def test_runtime_env_gate_disables_leaks_and_halts():
    env = sanitizer_runtime_env("/x/libasan.so")
    assert "detect_leaks=0" in env["ASAN_OPTIONS"]
    assert "halt_on_error=1" in env["ASAN_OPTIONS"]
    assert "halt_on_error=1" in env["UBSAN_OPTIONS"]
    assert env["LD_PRELOAD"] == "/x/libasan.so"
    assert "LSAN_OPTIONS" not in env


def test_runtime_env_audit_enables_leaks_with_suppressions():
    env = sanitizer_runtime_env("/x/libasan.so", leak_audit=True,
                                lsan_suppressions="/s.supp")
    assert "detect_leaks=1" in env["ASAN_OPTIONS"]
    assert env["LSAN_OPTIONS"] == "suppressions=/s.supp"


# --- C++ profile (Step 1.1.1; §4.3 C++ corpus units) -------------------------

def test_sanitizer_cpp_uses_gpp_and_std():
    argv = sanitizer_argv(ffp_contract="fast", c_path="k.cpp", so_path="k.so",
                          py_include=PYINC, language="c++")
    assert argv[0] == "g++-13"
    assert "-std=c++14" in argv
    for f in ("-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
              "-O1", "-shared", "-fPIC", "-ffp-contract=fast"):
        assert f in argv, f"missing {f}"


def test_sanitizer_c_default_is_gcc_no_cpp_std():
    argv = sanitizer_argv(ffp_contract="off", c_path="k.c", so_path="k.so",
                          py_include=PYINC)
    assert argv[0] == "gcc"
    assert "-std=c++14" not in argv


def test_performance_cpp_uses_gpp_and_std():
    argv = performance_argv(["-O3", "-march=native"], ffp_contract="fast",
                            c_path="k.cpp", so_path="k.so", py_include=PYINC,
                            language="c++")
    assert argv[0] == "g++-13"
    assert "-std=c++14" in argv and "-O3" in argv and "-ffp-contract=fast" in argv


def test_invalid_language_rejected():
    for bad in ("rust", "cpp", "C++", "", None):
        with pytest.raises(ValueError):
            sanitizer_argv(ffp_contract="off", c_path="k", so_path="k.so",
                           py_include=PYINC, language=bad)
        with pytest.raises(ValueError):
            performance_argv([], ffp_contract="off", c_path="k", so_path="k.so",
                             py_include=PYINC, language=bad)


def test_runtime_env_cpp_preloads_libstdcpp():
    # libstdc++ preloaded AHEAD-resolvable so ASan binds __cxa_throw at init.
    env = sanitizer_runtime_env("/x/libasan.so", libstdcpp="/y/libstdc++.so.6")
    assert env["LD_PRELOAD"] == "/x/libasan.so:/y/libstdc++.so.6"


def test_runtime_env_c_has_no_libstdcpp_by_default():
    assert sanitizer_runtime_env("/x/libasan.so")["LD_PRELOAD"] == "/x/libasan.so"


# --- real in-container builds ------------------------------------------------

CLEAN_PYX = """\
# cython: language_level=3
cimport cython
@cython.boundscheck(False)
@cython.wraparound(False)
def kernel(double[::1] x):
    cdef Py_ssize_t i
    cdef double s = 0.0
    for i in range(x.shape[0]):
        s += x[i] * 2.0
    return s
"""

OOB_PYX = """\
# cython: language_level=3
cimport cython
@cython.boundscheck(False)
@cython.wraparound(False)
def kernel(double[::1] x):
    x[x.shape[0] + 3] = 1.0
    return 0
"""

LOADER = """\
import importlib.util, sys
import numpy as np
spec = importlib.util.spec_from_file_location(sys.argv[1].split("/")[-1][:-3], sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print("result:", m.kernel(np.zeros(8, dtype=np.float64)))
"""


def _cythonize(d, stem, src):
    (d / f"{stem}.pyx").write_text(src)
    subprocess.run(["cython", "-3", str(d / f"{stem}.pyx")], check=True)
    return d / f"{stem}.c"


@pytest.fixture(scope="session")
def toolchain():
    if shutil.which("cython") is None or shutil.which("gcc") is None:
        pytest.fail("pinned container must provide cython + gcc")
    asan = subprocess.run(["gcc", "-print-file-name=libasan.so"],
                          capture_output=True, text=True, check=True).stdout.strip()
    return asan


def test_performance_build_loads_and_runs(tmp_path, toolchain):
    c = _cythonize(tmp_path, "perf_clean", CLEAN_PYX)
    so = tmp_path / "perf_clean.so"
    subprocess.run(performance_argv(["-O2", "-march=x86-64"], ffp_contract="off",
                                    c_path=str(c), so_path=str(so),
                                    py_include=PYINC), check=True)
    p = subprocess.run([sys.executable, "-c", LOADER, str(so)],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    assert "result: 0.0" in p.stdout


def test_sanitizer_build_runs_clean(tmp_path, toolchain):
    c = _cythonize(tmp_path, "san_clean", CLEAN_PYX)
    so = tmp_path / "san_clean.so"
    subprocess.run(sanitizer_argv(ffp_contract="off", c_path=str(c),
                                  so_path=str(so), py_include=PYINC), check=True)
    env = sanitizer_runtime_env(toolchain)
    p = subprocess.run([sys.executable, "-c", LOADER, str(so)],
                       capture_output=True, text=True, timeout=120, env=env)
    assert p.returncode == 0, p.stderr
    for token in ("AddressSanitizer", "runtime error", "heap-buffer-overflow"):
        assert token not in p.stderr, f"unexpected sanitizer report: {p.stderr}"


def test_sanitizer_catches_heap_overflow(tmp_path, toolchain):
    # Non-vacuity: the profile must actually sanitize. A boundscheck-off OOB write
    # is the §3.3 "unsafe on others" failure — it must be caught, process non-zero.
    c = _cythonize(tmp_path, "san_oob", OOB_PYX)
    so = tmp_path / "san_oob.so"
    subprocess.run(sanitizer_argv(ffp_contract="off", c_path=str(c),
                                  so_path=str(so), py_include=PYINC), check=True)
    env = sanitizer_runtime_env(toolchain)
    p = subprocess.run([sys.executable, "-c", LOADER, str(so)],
                       capture_output=True, text=True, timeout=120, env=env)
    assert p.returncode != 0, "sanitizer profile failed to catch the OOB write"
    assert "heap-buffer-overflow" in p.stderr


# --- real in-container C++ builds (Step 1.1.1; image X' g++-13) ---------------

CPP_CLEAN_PYX = """\
# distutils: language = c++
# cython: language_level=3
cdef extern from * nogil:
    '''
    #include <vector>
    #include <algorithm>
    static long _k(){ std::vector<int> v; for(int i=0;i<1000;i++) v.push_back(i);
                      std::sort(v.begin(),v.end()); long s=0;
                      for(size_t i=0;i<v.size();++i) s+=v[i]; return s; }
    '''
    long _k()
def kernel(): return _k()
"""

CPP_OOB_PYX = """\
# distutils: language = c++
# cython: language_level=3
cdef extern from * nogil:
    '''
    #include <vector>
    static int _k(){ std::vector<int> v(10,7); volatile int* p=v.data(); return p[64]; }
    '''
    int _k()
def kernel(): return _k()
"""

CPP_LOADER = """\
import importlib.util, sys
stem = sys.argv[1].split("/")[-1][:-3]
spec = importlib.util.spec_from_file_location(stem, sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print("result:", m.kernel())
"""


def _cythonize_cpp(d, stem, src):
    (d / f"{stem}.pyx").write_text(src)
    subprocess.run(["cython", "-3", "--cplus", str(d / f"{stem}.pyx")], check=True)
    return d / f"{stem}.cpp"


@pytest.fixture(scope="session")
def cpp_toolchain():
    if shutil.which("g++-13") is None:
        pytest.fail("image X' (:phase1) must provide g++-13 for C++ corpus units")
    libstdcpp = subprocess.run(["g++-13", "-print-file-name=libstdc++.so.6"],
                               capture_output=True, text=True, check=True).stdout.strip()
    return libstdcpp


def test_sanitizer_cpp_build_runs_clean(tmp_path, toolchain, cpp_toolchain):
    c = _cythonize_cpp(tmp_path, "san_cpp_clean", CPP_CLEAN_PYX)
    so = tmp_path / "san_cpp_clean.so"
    subprocess.run(sanitizer_argv(ffp_contract="fast", c_path=str(c), so_path=str(so),
                                  py_include=PYINC, language="c++"), check=True)
    env = sanitizer_runtime_env(toolchain, libstdcpp=cpp_toolchain)
    p = subprocess.run([sys.executable, "-c", CPP_LOADER, str(so)],
                       capture_output=True, text=True, timeout=120, env=env)
    assert p.returncode == 0, p.stderr
    for token in ("AddressSanitizer", "runtime error", "heap-buffer-overflow"):
        assert token not in p.stderr, f"unexpected sanitizer report: {p.stderr}"


def test_sanitizer_cpp_catches_heap_overflow(tmp_path, toolchain, cpp_toolchain):
    # Non-vacuity for the C++ path: an STL heap-OOB read must be caught. Also proves the
    # libstdcpp preload lets ASan run a C++ unit at all (no __cxa_throw abort on clean exit).
    c = _cythonize_cpp(tmp_path, "san_cpp_oob", CPP_OOB_PYX)
    so = tmp_path / "san_cpp_oob.so"
    subprocess.run(sanitizer_argv(ffp_contract="fast", c_path=str(c), so_path=str(so),
                                  py_include=PYINC, language="c++"), check=True)
    env = sanitizer_runtime_env(toolchain, libstdcpp=cpp_toolchain)
    p = subprocess.run([sys.executable, "-c", CPP_LOADER, str(so)],
                       capture_output=True, text=True, timeout=120, env=env)
    assert p.returncode != 0, "C++ sanitizer profile failed to catch the STL heap-OOB"
    assert "heap-buffer-overflow" in p.stderr
