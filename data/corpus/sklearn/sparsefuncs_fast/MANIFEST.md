# Corpus unit manifest — `sklearn.utils.sparsefuncs_fast`

Step 1.1.1 vendoring. This file is the per-unit provenance + admissibility record. The unit is
the **mechanism reference** for corpus vendoring (lowest-coupling unit; the Phase-0 csr origin).

## 1. Identity & upstream pin
| field | value |
|---|---|
| codebase (LOMO fold) | `sklearn.utils` (fold 1) |
| unit | `sparsefuncs_fast.pyx` |
| upstream version | scikit-learn **1.5.2** |
| sdist | `scikit_learn-1.5.2.tar.gz` |
| **sdist sha256 (upstream pin)** | `b4237ed7b3fdd0a4882792e68ef2545d5baa50aca3bb45aa7df468138ad8f94d` |
| sdist URL | `https://files.pythonhosted.org/packages/37/59/44985a2bdc95c74e34fef3d10cb5d93ce13b0e2a7baefffe1b53853b502d/scikit_learn-1.5.2.tar.gz` |
| build image | X′ = `localhost/motifbo-env:phase1` (`d45e33b0`); numpy 2.4.6 / Cython 3.2.5 / gcc-13 |
| §4.3 kernel | CSR/CSC mean–variance, in-place scaling |
| §4.3 oracle classes | floats → tolerance; shapes/indices → bit-exact |

## 2. Vendored cimport closure (FULL)
The unit's compile-time closure is **two source files** + package markers. `_typedefs.pxd` is pure
compile-time C typedefs (no cimport, no `include`, no numpy header, **no runtime `.so` to co-build**):
genuinely low-coupling.

| vendored path (under `closure/`) | role | sha256 | == sdist? |
|---|---|---|---|
| `sklearn/utils/sparsefuncs_fast.pyx` | the unit | `28fbe8376236ffeb2e400fe819a70ff0b3485c3643cc23023c065c81d71bd381` | yes |
| `sklearn/utils/_typedefs.pxd` | cimported types (`float64_t,int32_t,int64_t,intp_t,uint64_t`) | `81ec3b62e0995b0a68f8959718322bc09dbe2bfea607e0b81a177f66ef4677ea` | yes |
| `sklearn/__init__.py` | empty pkg marker (NOT upstream `__init__`) | — | n/a (stub) |
| `sklearn/utils/__init__.py` | empty pkg marker (NOT upstream `__init__`) | — | n/a (stub) |

Closure-walk: `sparsefuncs_fast.pyx` cimports `libc.math`, `libc.stdint`, `cython` (all Cython/stdlib
builtins — no vendoring) and `from ..utils._typedefs cimport …` (relative → `sklearn/utils/_typedefs.pxd`).
`_typedefs.pxd` cimports nothing. Closure is **complete and minimal**. The two package-marker stubs are
empty (not the heavyweight upstream `__init__.py`) so they establish the `sklearn.utils.*` package depth
for the relative cimport without dragging in the runtime `__check_build` guard.

## 3. Build-confirm — VENDORED-CLOSURE isolatability gate (criterion 3)
`build_from_closure.sh`, run in X′. Compiles from the vendored closure **alone** — NOT the extracted
sdist tree, NOT installed sklearn. **This is stronger than the earlier `build_probe.sh` sweep**, which
cythonized inside the full extracted sdist (`cd /dl/<sdist>; cython -I .`) so cimports could resolve
against any sibling present — i.e. the earlier "14 build-OK" was **sdist-root-based, not
vendored-closure-based**. Evidence (raw): `logs/corpus/STEP_1.1.1_vendor_sparsefuncs_fast_build.log`.
- **POSITIVE:** cythonize → `gcc-13 -O3 -march=native -ffp-contract=fast -fopenmp` → `.so` (790 064 bytes)
  → bare-loader import OK; 7 public callables present (`csr_mean_variance_axis0`, `csc_mean_variance_axis0`,
  `incr_mean_variance_axis0`, `inplace_csr_row_normalize_l1`, `inplace_csr_row_normalize_l2`,
  `csr_row_norms`, `assign_rows_csr`).
- **NEGATIVE CONTROL (non-vacuity):** hide the vendored `_typedefs.pxd` → cythonize **fails**
  (unresolved cimported types). Proves the build resolves the cimport from the **vendored closure**, not
  installed sklearn. EXIT=0 overall (positive passes, negative fails as required).

## 4. §4.2 admissibility (all 5 criteria — see `CHECKLIST_4.2.md` for the committed checklist)
| # | §4.2 criterion | determination | evidence |
|---|---|---|---|
| 1 | Non-templated `.pyx` | **PASS** | vendored file is `.pyx` (not `.pyx.tp`); no Tempita |
| 2 | Stable upstream (not `scipy.special`) | **PASS** | `sklearn.utils`; pinned sdist sha256 |
| 3 | Isolatable hot loop, public-API inputs | **PASS** | vendored-closure build+import (§3); inputs via `scipy.sparse` public API |
| 4 | Oracle-classifiable per §3.1 | **PASS (classifiable)** | floats→tolerance, indices/shapes→bit-exact (§4.3). Exact tolerance **derived+frozen at 1.1.3** (oracle.json) |
| 5 | Golden runtime 50–500 ms | **PENDING-1.1.5** | input-scale design recorded (§5 below); golden **measured under the timing rig at 1.1.5** (raw pointer there). No runtime number is claimed here — empirical-honesty. |

**Admissibility status: 4/5 confirmed; criterion 5 (golden timing) pending the rig at 1.1.5.** A unit is
admissible iff ALL 5 (§4.2) — so this unit is **provisionally admissible**; final seal at 1.1.5.

## 5. Hot-loop driver calls + input-scale design (criterion 3 inputs; CF-4 ~500 ms bias)
Representative inputs are constructible from the `scipy.sparse` public API (CSR/CSC). Candidate hot-loop
driver calls (the public exported kernels; a subset is promoted to the §4.4 driver at 1.2):
1. `csr_mean_variance_axis0(X_csr)` — column mean/variance over CSR
2. `csc_mean_variance_axis0(X_csc)` — column mean/variance over CSC
3. `incr_mean_variance_axis0(X_csr, last_mean, last_var, last_n)` — streaming update
4. `csr_row_norms(X_csr)` — squared L2 row norms
5. `inplace_csr_row_normalize_l2(X_csr)` — in-place row scaling (also `_l1`, `assign_rows_csr`)

**Input-scale design (CF-4):** bias the input toward the ~500 ms band-upper to dilute the unresolved
~8 ms CF-4 offset (≈1.6 % at 500 ms vs ≈16 % at 50 ms) and keep CF-3 CI@30 ≤ 1 % reachable. Construction
recipe: a fixed-seed CSR `float64` matrix `X` of shape `(n_samples, n_features)` with controlled `nnz`
(via `scipy.sparse.random(..., random_state=<fixed>)` or a deterministic generator), `OMP_NUM_THREADS=1`.
The **exact `nnz`/shape that lands ~500 ms is calibrated at 1.1.5** under the timing rig (watch the 12 GB
container ceiling); recorded here as a design target, not a measurement.

## 6. Carried obligations
- Criterion 5 golden + SHA-256 sealed at **1.1.5**; per-unit oracle.json + §3.1 tolerance at **1.1.3**.
- Per-unit timing precision (CF-3 band, CI@30 ≤ 1 %) re-established at **1.2** under quiesce-all (CF-1).
- This unit is **C** (no C++) → CF-5 (per-unit C++ sanitizer-clean) does not apply.
