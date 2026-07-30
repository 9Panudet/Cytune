# Sanitizer policy — CPython suppressions & runtime options (Step 0.4.1)

Roadmap basis: §3.3 (memory-safety verification: ASan+UBSan run the full validation
set clean), §1.5 item 1 (sanitizer builds keep `-g`), §3.5 (a sanitizer report ⇒
feasibility 0). Step 0.4.1 requires this file with **line-by-line justification** of
every suppression and option, reviewed by `validation-auditor`.

All claims below are grounded in `scripts/sanitizer_probe.sh`, captured at
`logs/env/STEP_0.4.1_sanitizer_probe.log` (sections A–H referenced inline). The
build flags are defined in `src/motifbo/build/profiles.py`.

## Build profile (ASan+UBSan candidate build)

`-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -shared -fPIC`
plus the explicit `-ffp-contract=<state>` invariant (§3.2 item 3).

- `-O1` — readable reports, far faster than instrumented `-O0`. `-O` is **not** in
  the safety-class key (§3.3 / §1.5 item 3): optimization level does not add or
  remove source-level memory accesses, so one `-O1` build represents the class.
- `-g` — symbolized reports (§1.5 item 1). The performance profile uses `-g0`.
- `-fsanitize=address,undefined` — ASan (heap/stack/global overflow, use-after-free)
  + UBSan (signed overflow, alignment, OOB shifts, null deref) on the candidate's
  Cython-generated C. The stock `python3.12` binary is **not** instrumented, so the
  only CPython-origin signal ASan sees is leaks (via the allocator interceptors);
  UBSan only ever sees the candidate's own C.
- `-fno-omit-frame-pointer` — reliable stack traces.

## Runtime options (operational = feasibility gate)

`sanitizer_runtime_env()` →
`ASAN_OPTIONS=detect_leaks=0:halt_on_error=1:exitcode=1`,
`UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1`,
`LD_PRELOAD=<libasan.so>`.

- **`detect_leaks=0`** — THE principal CPython suppression. Justification:
  - CPython does not free interned strings, type/module objects, or the
    pymalloc arenas at interpreter teardown **by design**. Probe section A shows
    ~940 KB in ~840 allocations from `PyUnicode_FromKindAndData` /
    `PyImport_ImportModuleLevelObject` / `_PyEval_EvalFrameDefault` on a trivial
    kernel load — i.e. pure interpreter overhead, nothing the candidate controls.
  - File-based LSan suppressions cannot cleanly remove only those: a module-level
    `leak:python3.12` **over-suppresses** genuine candidate leaks (probe F: the
    candidate's own `malloc` leak whose stack runs through the eval loop is hidden),
    while function-level allocator patterns **under-suppress** CPython (probe H:
    ~699 B / 56 allocs residual). Robust CPython-vs-candidate discrimination is not
    achievable for embedded CPython.
  - Turning leak detection off does **not** weaken the §3.3 gate. Leak detection is
    orthogonal to the memory-safety checks that gate cares about: probe section G
    shows a deliberate heap-buffer-overflow is caught and the process exits non-zero
    with `detect_leaks=0`. §3.3's concern ("unsafe on *other* inputs" — overflow,
    use-after-free, corruption) is fully covered.
- **`halt_on_error=1` / UBSan `halt_on_error=1`** — the first report is decisive:
  the run stops and exits non-zero, which the containment wrapper (0.4.3) maps to
  feasibility 0 (§3.5). No report-and-continue that could mask a second fault.
- **`exitcode=1`** — explicit non-zero exit on an ASan report (the wrapper keys on it).
- **UBSan `print_stacktrace=1`** — symbolized UBSan traces for the defect path.

UBSan needs **no** file-based suppressions at this point: probe section C shows zero
UBSan reports on the candidate C. Entries will be added **only** if the 0.4.2 /
Phase-1 validation set produces real reports from CPython/numpy header code included
in the generated C — never speculatively.

## Leak-audit mode (investigative, NOT the gate)

`sanitizer_runtime_env(leak_audit=True, lsan_suppressions=data/env/sanitizer/lsan_cpython.supp)`
flips leak detection on with the suppression file (`leak:PyUnicode_`,
`leak:PyObject_Malloc`, `leak:PyMem_`, `leak:_PyObject_GC` — each justified in that
file by the probe-A allocators). Use only to hunt a suspected candidate leak; it does
not achieve perfect discrimination (probe H residual) and never feeds feasibility.

## C++ corpus units (Step 1.1.1 — mini-I-3 C++ extension)

Phase-1 §4.3 includes C++ Cython units (sklearn `tree/_tree`,`_splitter`,`_criterion`;
`cluster/_dbscan_inner`,`_hierarchical_fast`). They build in image **X′** (`:phase1`, the
additive g++-13 + libstdc++-13-dev layer — data/env/IMAGE_TRANSITION.md). Evidence for
everything below: `logs/env/STEP_1.1.1_cpp_sanitizer.log` (sections [A]–[D]) + tests
`src/tests/test_build_profiles.py` (real C++ clean build + heap-OOB catch) and
`src/tests/test_oracle_cpp_exceptions.py`.

- **Build profile.** `sanitizer_argv(language="c++")` → **g++-13** + `-std=c++14` + the SAME
  ASan+UBSan flags (`-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer`) + the
  explicit `-ffp-contract` invariant. The artifact is the Cython `--cplus` `.cpp`. (C is
  unchanged: `gcc`, no `-std`.)
- **Runtime — the one required C++-specific change.** `sanitizer_runtime_env(..., libstdcpp=
  <libstdc++.so.6>)` preloads libstdc++ ahead of libasan so ASan's `__cxa_throw` interceptor
  binds the real symbol at init. WITHOUT it, the first C++ `throw` aborts ASan with
  `CHECK failed: real___cxa_throw != 0` (evidence [A]/[B]) — i.e. **exception unwinding**, not
  allocation, is the hazard. This is a runtime-env change, **not** a suppression-file line.
- **Non-vacuity ([D]).** The C++ ASan+UBSan rig catches real C++ bugs: **heap-buffer-overflow**
  (STL `vector` bounds), **heap-use-after-free** (iterator invalidation via realloc), and
  **UBSan vptr** (wrong dynamic type / RTTI) — not just throws.
- **Exception identity (§3.1).** Cython `except +` maps C++ exceptions to stable Python types
  deterministically: `std::out_of_range`→`IndexError`, `std::length_error`→`RuntimeError`,
  `std::invalid_argument`→`ValueError`. The oracle compares the TRANSLATED Python type by
  canonical identity (a subclass never matches) — so the §3.1 comparator works unchanged on
  C++ units (`test_oracle_cpp_exceptions.py`).
- **Leak policy for C++.** The feasibility GATE keeps `detect_leaks=0` (Phase-0 invariant,
  above) for C and C++ alike. A **dedicated C++ leak-audit pass** (`leak_audit=True` +
  `lsan_cpython.supp`) DOES robustly surface STL container leaks: on the C++ probe the CPython
  teardown was fully suppressed (0 residual) and an STL `operator new` leak was detected
  ([D]). So STL leaks are actively caught in the leak-audit (not only via the §3.4 memory-cap
  kill). This pass runs at preflight / per-unit, never as the gate.
- **No speculative suppressions.** No libstdc++ `leak:`/UBSan lines were added — the tested
  archetype produced none. Per-unit `leak:` lines are added ONLY on a demonstrated report from
  a specific unit (same discipline as the CPython entries).
- **Scope.** The mini-I-3 sign-off attests this RIG. **Per-unit C++ sanitizer-clean is a
  CONTINUING mandatory obligation at 1.2/preflight** (analogous to the §3.3 endpoint
  full-config guard) — it is not covered by the rig sign-off and must not be skipped.

## Files
- `src/motifbo/build/profiles.py` — the profiles + runtime env (incl. the C++ `language` +
  `libstdcpp` parameters).
- `data/env/sanitizer/lsan_cpython.supp` — leak-audit suppression entries (CPython only).
- `scripts/sanitizer_probe.sh` / `logs/env/STEP_0.4.1_sanitizer_probe.log` — C-rig evidence.
- `scripts/corpus/sanitizer/{cpp_probe.pyx,cpp_rig_probe.pyx,rig_audit.sh}` /
  `logs/env/STEP_1.1.1_cpp_sanitizer.log` — C++-rig evidence.
