# Corpus unit manifest — `sklearn._isotonic`

Step 1.1.1 vendoring. Per-unit provenance + admissibility record. `_isotonic` is the
**isotonic.PAVA** kernel: Pool Adjacent Violators (with longest-decreasing-subsequence pooling) for
isotonic regression, plus the duplicate-X averaging helper. It is the **lowest-coupling kind** of
sklearn unit — its cimport closure is **empty**.

## 1. Identity & upstream pin
| field | value |
|---|---|
| codebase (LOMO fold) | `sklearn.isotonic` |
| unit | `_isotonic.pyx` |
| target import module | `sklearn._isotonic` |
| language | **C** (cythonize `-3` + reference `-X`; gcc-13) |
| upstream version | scikit-learn **1.5.2** |
| sdist | `scikit_learn-1.5.2.tar.gz` |
| **sdist sha256 (upstream pin)** | `b4237ed7b3fdd0a4882792e68ef2545d5baa50aca3bb45aa7df468138ad8f94d` |
| build image | X′ = `localhost/motifbo-env:phase1`; Python 3.12.3 / numpy 2.4.6 / Cython 3.2.5 / gcc-13 (13.3.0) |
| kernel | PAVA isotonic regression (`_inplace_contiguous_isotonic_regression`) + duplicate-X average (`_make_unique`) |
| §3.1 oracle classes | result floats → tolerance; output shapes / unique-count / block indices → bit-exact |

## 2. Vendored cimport closure (FULL) — EMPTY beyond the unit itself
Closure-walk on `sklearn/_isotonic.pyx`:
- `import numpy as np` — Python-level import, **image-provided** (numpy 2.4.6). No vendoring.
- `from cython cimport floating` — **Cython builtin** fused type. No vendoring.

There is **no repo `cimport`**, **no sibling `.pxd`**, **no `include`**, **no `from . import` helper**,
and **no co-built `.so` cluster** (no cimported `cdef class` / non-inline `cdef`/`cpdef` from another
module). The transitive closure is therefore **just the unit `.pyx`** plus one empty `sklearn/__init__.py`
package marker (establishes the `sklearn.*` package depth so `import sklearn._isotonic` resolves to the
vendored package, NOT the heavyweight upstream `__init__`).

| vendored path (under `closure/`) | role | sha256 | == sdist? |
|---|---|---|---|
| `sklearn/_isotonic.pyx` | the unit (PAVA kernel) | `600f2b010a99e00fec93f811b90c1ffb092bade3ffc4b8b718fc8a98e03784b7` | yes (verbatim) |
| `sklearn/__init__.py` | empty pkg marker (NOT upstream `__init__`) | — | n/a (stub) |

**Package-context stubs:** none. No `from . import <helper>` in the unit, so the empty `__init__.py`
needs no faithful Python helper (contrast `_random.pyx` → `check_random_state`). The marker is empty.

## 3. Build-confirm — STANDALONE IMPORT (binding, §4); vendored-closure isolatability gate (criterion 3)
`build_from_closure.sh`, run in X′. Compiles from the vendored closure **alone** with the sklearn
**as-shipped reference directives** (`-X language_level=3 -X boundscheck=False -X wraparound=False
-X initializedcheck=False -X nonecheck=False -X cdivision=True`), then **standalone-IMPORTs the real
module path `sklearn._isotonic`** with `OMP_NUM_THREADS=1`. cythonize-OK / compile-OK do NOT count — the
gate is the import. Raw evidence: `logs/corpus/STEP_1.1.1_vendor__isotonic_build.log`.
- **POSITIVE:** cythonize → `gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp` →
  `sklearn/_isotonic.so` (**287 872 bytes**) → `PYTHONPATH=<closure>` `import sklearn._isotonic`
  **succeeds**. The import asserts the resolved `sklearn` is the **vendored** empty-marker package
  (`…/closure/sklearn/__init__.py`), not installed sklearn, and that both kernel callables are present:
  `_inplace_contiguous_isotonic_regression`, `_make_unique`. → **`IMPORT-OK sklearn._isotonic`**.
- **NEGATIVE CONTROL (non-vacuity):** with the empty closure the unit `.pyx` is the **sole** source.
  Hiding it → cythonize **fails** (`No such file: sklearn/_isotonic.pyx`). Proves the `.so` is built
  FROM the vendored closure, not the container's installed scikit-learn. (No cimported `.pxd` exists to
  hide here, so the unit `.pyx` is the correct negative-control target for an empty-closure unit.)
- Overall: positive PASS + negative fails-as-required → **PASS**.

> Note: the cosmetic `installed sklearn` probe line in the log raises `AttributeError: no attribute
> __version__` because that diagnostic echo runs with CWD inside the closure dir (the local `sklearn/`
> marker shadows the installed package for that one `python3 -c` line). It is **not** part of the gate;
> the gated import sets `PYTHONPATH` explicitly and asserts the vendored path. No effect on admissibility.

## 4. §4.2 admissibility (all 5 criteria — see `CHECKLIST_4.2.md`)
| # | §4.2 criterion | determination | evidence |
|---|---|---|---|
| 1 | Non-templated `.pyx` | **PASS** | vendored file is `_isotonic.pyx` (not `.pyx.tp`); no Tempita; no `include` |
| 2 | Stable upstream (not `scipy.special`) | **PASS** | `sklearn.isotonic`; pinned sdist sha256 `b4237ed7…` |
| 3 | Isolatable hot loop, public-API inputs | **PASS** | vendored-closure build + **STANDALONE IMPORT** in X′ (§3) incl. negative control; inputs are plain contiguous numpy `float32`/`float64` 1-D arrays |
| 4 | Oracle-classifiable per §3.1 | **PASS (classifiable)** | floats→tolerance; shapes / unique-count / block indices→bit-exact. Exact tolerance **derived+frozen at 1.1.3** (per-unit oracle.json) |
| 5 | Golden runtime 50–500 ms | **PENDING-1.1.5** | input-scale design recorded (§5); golden **measured under the timing rig at 1.1.5** (raw pointer there). No runtime number claimed here — empirical-honesty. |

**Admissibility status: 4/5 confirmed; criterion 5 (golden timing) pending the rig at 1.1.5.** A unit is
admissible iff ALL 5 (§4.2) — so this unit is **provisionally admissible**; final seal at 1.1.5.

## 5. Hot-loop driver calls + input-scale design (criterion 3 inputs; CF-4 ~500 ms bias)
Inputs are constructible from the **public numpy API** — contiguous 1-D `float64`/`float32` arrays; no
sparse, no special structure. The PAVA kernel is the hot loop (`nogil`, single-pass O(n)).
Candidate hot-loop driver calls (a subset promoted to the §4.4 driver at 1.2):
1. `_inplace_contiguous_isotonic_regression(y, w)` — in-place PAVA on `y` (target), `w` (weights);
   `y`,`w` are `float64[::1]` (or `float32[::1]`) contiguous, same length `n`.
2. `_make_unique(X, y, sample_weights)` — duplicate-X averaging; `X` ascending-sorted `float64[::1]`,
   `y`,`sample_weights` matching length.

**Input-scale design (CF-4):** bias toward the ~500 ms band-upper to dilute the unresolved ~8 ms CF-4
offset (≈1.6 % at 500 ms vs ≈16 % at 50 ms) and keep CF-3 CI@30 ≤ 1 % reachable. Construction recipe:
a fixed-seed length-`n` `float64` array (e.g. a noisy descending/zig-zag sequence to exercise the pooling
+ backtrack branches, since a monotone input short-circuits) with matching unit weights; `OMP_NUM_THREADS=1`.
The **exact `n` that lands ~500 ms is calibrated at 1.1.5** under the timing rig (watch the 12 GB
container ceiling); recorded here as a **design target, not a measurement** (claim no runtime number).

## 6. Carried obligations
- Criterion 5 golden + SHA-256 sealed at **1.1.5**; per-unit oracle.json + §3.1 tolerance at **1.1.3**.
- Per-unit timing precision (CF-3 band, CI@30 ≤ 1 %) re-established at **1.2** under quiesce-all (CF-1).
- This unit is **C** (no C++) → CF-5 (per-unit C++ sanitizer-clean) **does not apply**.
