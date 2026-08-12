# Corpus unit manifest — `sklearn.ensemble._hist_gradient_boosting._predictor`

Step 1.1.1 vendoring. Per-unit provenance + admissibility record. This unit is the HistGradientBoosting
**tree-traversal predictor kernel** (raw + binned prediction, partial dependence). Unlike the
low-coupling `sparsefuncs_fast`, it carries a **runtime `.so` cluster** (`common`, `_bitset`).

## 1. Identity & upstream pin
| field | value |
|---|---|
| codebase (LOMO fold) | `sklearn.ensemble` |
| unit | `_predictor.pyx` |
| target import module | `sklearn.ensemble._hist_gradient_boosting._predictor` |
| upstream version | scikit-learn **1.5.2** |
| sdist | `scikit_learn-1.5.2.tar.gz` |
| **sdist sha256 (upstream pin)** | `b4237ed7b3fdd0a4882792e68ef2545d5baa50aca3bb45aa7df468138ad8f94d` |
| language | **C** (gcc-13; not C++) |
| build image | X′ = `localhost/motifbo-env:phase1` (`d45e33b0`); Python 3.12.3 / Cython 3.2.5 / numpy 2.4.6 / gcc-13 13.3.0 |
| kernel | predictor-tree traversal: raw-data predict, binned-data predict, partial-dependence weighting |
| oracle classes (§3.1) | prediction/PD outputs are `float64` → tolerance; tree topology fixed by input |

## 2. Vendored cimport + runtime closure (FULL)
Closure-walk from `_predictor.pyx`:
- `from cython.parallel import prange`, `from libc.math cimport isnan`, `import numpy as np`
  → Cython/stdlib/image builtins — **no vendoring**.
- `from ...utils._typedefs cimport intp_t` → relative → `sklearn/utils/_typedefs.pxd` (pure `ctypedef`,
  no cimport, no numpy header → **no runtime `.so`**). RECURSE terminates.
- `from .common cimport X_DTYPE_C, Y_DTYPE_C, X_BINNED_DTYPE_C, BITSET_INNER_DTYPE_C, node_struct`
  → `sklearn/ensemble/_hist_gradient_boosting/common.pxd`. Those symbols are all `ctypedef` /
  `packed struct` (compile-time). `common.pxd` cimports `…utils._typedefs` (already vendored).
- `from .common import Y_DTYPE` → **Python-level** import of a module attribute defined in `common.pyx`
  → **`common.so` MUST be co-built and importable at runtime**.
- `from ._bitset cimport in_bitset_2d_memoryview` → `_bitset.pxd` declares it `cdef … noexcept nogil`
  (non-inline at the `.pxd` boundary; defined `cdef inline` in `_bitset.pyx`). The cross-module `cdef`
  symbol is satisfied by co-building **`_bitset.so`**. `_bitset.pxd` cimports only `common` (vendored).

Runtime `.so` cluster (built in dep order): **`common` → `_bitset` → `_predictor`**.

| vendored path (under `closure/`) | role | sha256 | == sdist? | runtime `.so`? |
|---|---|---|---|---|
| `sklearn/ensemble/_hist_gradient_boosting/_predictor.pyx` | the unit | `e8a1cc6beb1e2725d9575d73144779bcecf0107c32e25ba083495258863ffa36` | yes | yes (the unit) |
| `sklearn/ensemble/_hist_gradient_boosting/common.pxd` | cimported structs/types (`node_struct`, `X_DTYPE_C`, …) | `d635ecc852d904185fbaf63cf665dcbf9c7e5ef9bf6055aad3c5dba2ca0069d5` | yes | (pxd) |
| `sklearn/ensemble/_hist_gradient_boosting/common.pyx` | runtime module for `Y_DTYPE` (Python import) | `152bd476c04c88b2009af9357a47b70b43c1a3475c994209d6898dedaf81d246` | yes | **yes** |
| `sklearn/ensemble/_hist_gradient_boosting/_bitset.pxd` | declares cimported `in_bitset_2d_memoryview` | `9f310663247ade00109976cca0dc2abbf7abc39d5edd3bde03dad371f3427ee3` | yes | (pxd) |
| `sklearn/ensemble/_hist_gradient_boosting/_bitset.pyx` | defn of the cdef bitset symbol | `90901c4e0be6e9fa849cdece3f59c2216b0d45cd9c26018857bc595cbd01551f` | yes | **yes** |
| `sklearn/utils/_typedefs.pxd` | `intp_t` et al. (pure ctypedef) | `81ec3b62e0995b0a68f8959718322bc09dbe2bfea607e0b81a177f66ef4677ea` | yes | no |
| `sklearn/__init__.py` | empty pkg marker (NOT upstream) | — | n/a (stub) | — |
| `sklearn/ensemble/__init__.py` | empty pkg marker (NOT upstream) | — | n/a (stub) | — |
| `sklearn/ensemble/_hist_gradient_boosting/__init__.py` | empty pkg marker (NOT upstream) | — | n/a (stub) | — |
| `sklearn/utils/__init__.py` | empty pkg marker (NOT upstream) | — | n/a (stub) | — |

**Package-context stubs:** none required. The only Python-level cross-module name the unit imports,
`Y_DTYPE`, is supplied by the co-built `common.so` — not by any `__init__` helper. All four `__init__.py`
are empty markers (NOT the heavyweight upstream `__init__`, to avoid the `__check_build` guard) and exist
only to establish the `sklearn.ensemble._hist_gradient_boosting.*` package depth for the relative
cimport/import to resolve.

## 3. Build-confirm — STANDALONE IMPORT (binding §4 gate)
`build_from_closure.sh`, run in X′. BUILD-CONFIRM = standalone IMPORT: cythonize+compile is NOT enough.
Evidence (raw): `logs/corpus/STEP_1.1.1_vendor__predictor_build.log`.
- **POSITIVE:** built the full runtime `.so` cluster from the vendored closure ALONE (dep order
  `common` → `_bitset` → `_predictor`; reference `-X` directives), then
  `importlib.import_module('sklearn.ensemble._hist_gradient_boosting._predictor')` with `PYTHONPATH`=
  closure-root, `OMP_NUM_THREADS=1` → **`IMPORT-OK`**. Exported names:
  `_predict_from_raw_data`, `_predict_from_binned_data`, `_compute_partial_dependence`, `Y_DTYPE`, `np`.
  `.so` sizes: `common` 45 896 B, `_bitset` 230 440 B, `_predictor` 257 008 B.
- **NEGATIVE CONTROL (non-vacuity):** hide vendored `common.pxd` → cythonize of `_predictor` **fails**
  (`'…/common.pxd' not found`). Proves the cimported `node_struct`/`X_DTYPE_C`/… resolve from the
  **vendored closure**, not the image's installed scikit-learn. Overall EXIT=0.

## 4. §4.2 admissibility (all 5 criteria — see `CHECKLIST_4.2.md`)
| # | §4.2 criterion | determination | evidence |
|---|---|---|---|
| 1 | Non-templated `.pyx` | **PASS** | vendored file is `_predictor.pyx` (not `.pyx.tp`); no Tempita. Cluster members `common.pyx`/`_bitset.pyx` also plain `.pyx`. |
| 2 | Stable upstream (not `scipy.special`) | **PASS** | `sklearn.ensemble._hist_gradient_boosting`; pinned sdist sha256 `b4237ed7…`. |
| 3 | Isolatable hot loop, public-API inputs | **PASS** | standalone-IMPORT in X′ (§3) incl. negative control. Inputs constructible via numpy public arrays of `PREDICTOR_RECORD_DTYPE` nodes + data matrices. |
| 4 | Oracle-classifiable per §3.1 | **PASS (classifiable)** | float64 prediction/PD → tolerance; tree topology deterministic. Exact tolerance **derived+frozen at 1.1.3** (oracle.json). |
| 5 | Golden runtime 50–500 ms | **PENDING-1.1.5** | input-scale design recorded (§5); golden **measured under the timing rig at 1.1.5**. No runtime number claimed here (empirical-honesty). |

**Admissibility status: 4/5 confirmed; criterion 5 pending the rig at 1.1.5.** Provisionally admissible.

## 5. Hot-loop driver calls + input-scale design (criterion 3 inputs; CF-4 ~500 ms bias)
The three exported kernels are the candidate hot-loop driver calls (a subset is promoted to the §4.4
driver at 1.2). Inputs are plain numpy arrays — no sklearn estimator needed:
1. `_predict_from_raw_data(nodes, numeric_data, raw_left_cat_bitsets, known_cat_bitsets, f_idx_map, n_threads, out)`
   — per-row raw-data tree traversal over `nodes` (`PREDICTOR_RECORD_DTYPE`) and `numeric_data` (float64).
2. `_predict_from_binned_data(nodes, binned_data, binned_left_cat_bitsets, missing_values_bin_idx, n_threads, out)`
   — per-row binned-data (`uint8`) tree traversal.
3. `_compute_partial_dependence(nodes, X, target_features, out)` — weighted partial-dependence traversal.

**Input-scale design (CF-4):** bias the input toward the ~500 ms band-upper to dilute the unresolved
~8 ms CF-4 offset (≈1.6 % at 500 ms vs ≈16 % at 50 ms) and keep CF-3 CI@30 ≤ 1 % reachable. Construction
recipe (fixed seed, `OMP_NUM_THREADS=1`): a deterministic predictor-tree `nodes` array
(`PREDICTOR_RECORD_DTYPE`, depth/`n_nodes` controlled) and a large `numeric_data`/`binned_data` matrix of
shape `(n_samples, n_features)`; `n_samples` (and tree depth) drive runtime. The **exact n_samples/depth
that lands ~500 ms is calibrated at 1.1.5** under the timing rig (watch the 12 GB ceiling); recorded here
as a DESIGN target, not a measurement.

## 6. Carried obligations
- Criterion 5 golden + SHA-256 sealed at **1.1.5**; per-unit oracle.json + §3.1 tolerance at **1.1.3**.
- Per-unit timing precision (CF-3 band, CI@30 ≤ 1 %) re-established at **1.2** under quiesce-all (CF-1).
- This unit is **C** (no C++) → CF-5 (per-unit C++ sanitizer-clean obligation at 1.2) does **not** apply.
