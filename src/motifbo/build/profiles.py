"""Candidate build profiles (Step 0.4.1; roadmap §1.5 item 1, §3.2 item 3, §3.3).

Two gcc back-end profiles share the Cython front-end (cythonize once per directive
combination, §1.5 item 1) and differ only in flags + runtime:

- PERFORMANCE — the config's optimization flags PLUS fixed `-g0 -pipe` (no debug
  info, no temp files: faster compile on the tmpfs /sandbox, §1.5 item 1). Used
  for every timing build.
- SANITIZER  — `-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer`
  (keeps `-g`: reports need symbols, §1.5 item 1). One build per safety class
  (§3.3), executed under the sanitizer runtime env below. `-O` is NOT part of the
  safety-class key (§3.3 / §1.5 item 3), so the sanitizer build pins `-O1` (good
  report fidelity, far faster than `-O0` instrumented) regardless of the config.

HARD INVARIANT — §3.2 item 3: `-ffp-contract` is ALWAYS emitted explicitly. GCC's
default is `fast`, which silently contracts a*b+c into an FMA and can change a
bit-exact output. Both builders OWN the `-ffp-contract` token and refuse to emit a
command without it; callers must not smuggle their own.

Sanitizer runtime (grounded by scripts/sanitizer_probe.sh, evidence in
logs/env/STEP_0.4.1_sanitizer_probe.log; policy in
data/env/sanitizer/SANITIZER_POLICY.md): leak detection is OFF
(`detect_leaks=0`) — CPython leaks ~840 allocations at teardown by design, and
LSan suppressions cannot robustly separate those from candidate leaks in embedded
mode. The memory-SAFETY checks §3.3 requires (heap/stack overflow, use-after-free)
fire regardless of leak detection (probe section G). `halt_on_error=1` makes the
first report decisive — the candidate is feasibility=0 (§3.5).
"""

CONTRACT_STATES = ("off", "on", "fast")

PERF_FIXED = ("-g0", "-pipe")
SAN_FIXED = ("-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer")
LINK_FIXED = ("-shared", "-fPIC")

# C++ corpus units (roadmap §4.3 tree + cluster/_dbscan_inner/_hierarchical_fast) build
# with g++-13 (cc1plus) — added to the pinned image at Step 1.1.1 (X->X'). `-std=c++14`
# covers the sklearn/scipy Cython C++ output. C keeps the `gcc` meta (= gcc-13); both are
# the same pinned gcc-13 family. The SANITIZER flags (ASan+UBSan) are language-agnostic.
CC_BY_LANGUAGE = {"c": "gcc", "c++": "g++-13"}
CPP_STD = ("-std=c++14",)


def _compiler(language):
    if language not in CC_BY_LANGUAGE:
        raise ValueError(
            f"language must be one of {tuple(CC_BY_LANGUAGE)}; got {language!r}")
    return CC_BY_LANGUAGE[language]


def _contract_flag(ffp_contract):
    if ffp_contract not in CONTRACT_STATES:
        raise ValueError(
            f"ffp_contract must be one of {CONTRACT_STATES} and is required "
            f"(§3.2 item 3: never let GCC default to fast); got {ffp_contract!r}")
    return f"-ffp-contract={ffp_contract}"


def performance_argv(opt_flags, *, ffp_contract, c_path, so_path, py_include,
                     language="c"):
    """gcc/g++ argv for a timing build. `opt_flags` carries the config's optimization
    choices (e.g. ['-O3', '-march=native', '-funroll-loops']) — but NOT debug or
    contract flags, which this profile owns. `language='c++'` selects g++-13 + the C++
    std (for §4.3 C++ corpus units); the compiled artifact is the Cython `--cplus` .cpp."""
    cc = _compiler(language)
    opt_flags = list(opt_flags)
    for f in opt_flags:
        if f.startswith("-ffp-contract"):
            raise ValueError("the profile owns -ffp-contract; do not pass it in "
                             "opt_flags (§3.2 item 3)")
        if f in ("-g", "-g0") or f.startswith("-fsanitize"):
            raise ValueError(f"the profile owns debug/sanitizer flags; {f!r} "
                             "must not be in opt_flags")
    std = CPP_STD if language == "c++" else ()
    return [cc, *opt_flags, _contract_flag(ffp_contract), *std, *PERF_FIXED,
            *LINK_FIXED, f"-I{py_include}", c_path, "-o", so_path]


def sanitizer_argv(*, ffp_contract, c_path, so_path, py_include, fast_math=False,
                   language="c"):
    """gcc/g++ argv for an ASan+UBSan candidate build (one per safety class, §3.3).
    `fast_math` is part of the class key (§3.3); when set, `-ffast-math` is added
    and the contraction state it implies is still recorded explicitly. `language='c++'`
    selects g++-13 + `-std=c++14` (Step 1.1.1); ASan+UBSan flags are language-agnostic.
    NOTE: a C++ sanitizer build MUST be run with `sanitizer_runtime_env(..., libstdcpp=)`
    so ASan's __cxa_throw interceptor binds at init (else the first C++ throw aborts ASan)."""
    cc = _compiler(language)
    extra = ("-ffast-math",) if fast_math else ()
    std = CPP_STD if language == "c++" else ()
    return [cc, *SAN_FIXED, *std, *extra, _contract_flag(ffp_contract),
            *LINK_FIXED, f"-I{py_include}", c_path, "-o", so_path]


def sanitizer_runtime_env(asan_lib, *, leak_audit=False, lsan_suppressions=None,
                          libstdcpp=None):
    """Environment for running a sanitizer build inside CPython.

    Default (feasibility gate): leak detection OFF, first report fatal.
    leak_audit=True flips leak detection ON with an LSan suppression file — an
    investigative aid only (discrimination is imperfect; see the policy), never
    the feasibility gate. For C++ units (Step 1.1.1) a dedicated leak-audit pass
    (leak_audit=True + lsan_suppressions=lsan_cpython.supp) DOES robustly surface STL
    container leaks (CPython teardown fully suppressed in the C++ probe — evidence
    logs/env/STEP_1.1.1_cpp_sanitizer.log [D]).

    `libstdcpp` (path to libstdc++.so.6) is REQUIRED for C++ units: it is preloaded
    AHEAD of the first C++ throw so ASan's __cxa_throw interceptor binds the real symbol
    at init. Without it, the first C++ exception aborts ASan with
    `CHECK failed: real___cxa_throw != 0` (evidence [A]/[B] in the log above). It is a
    no-op for C units (omit it).
    """
    asan_opts = ["halt_on_error=1", "exitcode=1"]
    preload = asan_lib if libstdcpp is None else f"{asan_lib}:{libstdcpp}"
    env = {
        "LD_PRELOAD": preload,
        "UBSAN_OPTIONS": "print_stacktrace=1:halt_on_error=1",
    }
    if leak_audit:
        asan_opts.insert(0, "detect_leaks=1")
        if lsan_suppressions is not None:
            env["LSAN_OPTIONS"] = f"suppressions={lsan_suppressions}"
    else:
        asan_opts.insert(0, "detect_leaks=0")
    env["ASAN_OPTIONS"] = ":".join(asan_opts)
    return env
