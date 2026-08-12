# Corpus unit manifest — `sklearn.cluster._k_means_elkan`

Step 1.1.1 vendoring. Per-unit provenance + admissibility record. The unit is the Elkan-algorithm
K-means EM-step kernel (chunked, OpenMP-parallel dense + sparse iterations + bound initialisation).

## 1. Identity & upstream pin
| field | value |
|---|---|
| codebase (LOMO fold) | `sklearn.cluster` |
| unit | `_k_means_elkan.pyx` |
| target import module | `sklearn.cluster._k_means_elkan` |
| language | **C** (gcc-13; not C++) |
| upstream version | scikit-learn **1.5.2** |
| sdist | `scikit_learn-1.5.2.tar.gz` |
| **sdist sha256 (upstream pin)** | `b4237ed7b3fdd0a4882792e68ef2545d5baa50aca3bb45aa7df468138ad8f94d` |
| build image | X′ = `localhost/motifbo-env:phase1` (`d45e33b0`); Python 3.12.3 / Cython 3.2.5 / numpy 2.4.6 / gcc-13 13.3.0 |
| kernel | Elkan K-means: `elkan_iter_chunked_dense/sparse` (combined E+M step over data chunks, triangle-inequality bound pruning), `init_bounds_dense/sparse` |
| oracle classes (§3.1) | centers/bounds (floats) → tolerance; `labels` (int assignment) → bit-exact |

## 2. Vendored cimport/import closure (FULL) — resolved from the sdist `.pyx`/`.pxd`

Closure-walk from `_k_means_elkan.pyx`:
- Cython/stdlib builtins (NO vendoring): `cython.floating`, `cython.parallel` (`prange`, `parallel`),
  `libc.stdlib` (`calloc`, `free`), `libc.string` (`memset`).
- `from ..utils._openmp_helpers cimport omp_lock_t, omp_init_lock, omp_destroy_lock, omp_set_lock,
  omp_unset_lock` → `sklearn/utils/_openmp_helpers.pxd`. That `.pxd` is a pure `cdef extern from *`
  block (C `omp_*` macros under `#ifdef _OPENMP`, libgomp at link with `-fopenmp`). **No Python
  cdef/cpdef symbol → NO `.so` co-build**; the `.pxd` alone resolves the cimport.
- `from ._k_means_common cimport _relocate_empty_clusters_dense, _relocate_empty_clusters_sparse,
  _euclidean_dense_dense, _euclidean_sparse_dense, _average_centers, _center_shift` →
  `sklearn/cluster/_k_means_common.pxd`. These are `cdef`/`cpdef` functions **defined in
  `_k_means_common.pyx`** → per rule 4 the module's `.so` MUST be co-built (vendor `.pyx` + `.pxd`).
  `_k_means_common.pyx` cimports only builtins (`cython.floating`, `cython.parallel.prange`,
  `libc.math.sqrt`) and Python-imports `numpy` (image) + `from ..utils.extmath import row_norms`.
  Closure terminates — no further repo `.pxd`.
- Python-level module-scope imports (rule 5): `from ..utils.extmath import row_norms` (in BOTH
  `_k_means_elkan.pyx` and `_k_means_common.pyx`) and `from ._k_means_common import CHUNK_SIZE`
  (resolved by the co-built `_k_means_common.so` at runtime). `row_norms` is provided by a **faithful
  minimal `extmath.py` stub** (see §2.1) to avoid the heavyweight upstream extmath cascade.

| vendored path (under `closure/`) | role | sha256 | == sdist? | `.so` co-built? |
|---|---|---|---|---|
| `sklearn/cluster/_k_means_elkan.pyx`   | the unit | `b4c86968d1d565fdd31b4c41e3ae8603951f4eb693180c41bce86fc9b738f916` | yes | yes (the unit) |
| `sklearn/cluster/_k_means_common.pyx`  | cimported cdef/cpdef kernels (`_euclidean_*`, `_relocate_*`, `_average_centers`, `_center_shift`) | `3aa9b4f3cebd60bb5f6d69a67068b473ad84b8c816d8f3e86e430fc6955e8470` | yes | **yes** (runtime dep) |
| `sklearn/cluster/_k_means_common.pxd`  | declares the cimported kernels | `e905b5f13b42d701a9c9377471d1bd3f14984e23f864dde18fa96d256add6a27` | yes | n/a (decl) |
| `sklearn/utils/_openmp_helpers.pxd`    | `cdef extern from *` omp_* decls (libgomp at link) | `391b4d5e33d70c13a6a075bafbee78c30acc108669b42019e93f0224f0ae27ed` | yes | no (extern only) |
| `sklearn/utils/extmath.py`             | **faithful minimal `row_norms` stub** (rule 5) | — | n/a (stub) | n/a |
| `sklearn/__init__.py`                  | empty pkg marker (NOT upstream) | — | n/a (stub) | n/a |
| `sklearn/cluster/__init__.py`          | empty pkg marker (NOT upstream) | — | n/a (stub) | n/a |
| `sklearn/utils/__init__.py`            | empty pkg marker (NOT upstream) | — | n/a (stub) | n/a |

### 2.1 Python-context stubs recorded (rule 5)
- **`row_norms`** (in `sklearn/utils/extmath.py`): faithful minimal reimplementation. Upstream
  `row_norms(X, squared)` returns the row-wise (squared) Euclidean norm — for a numpy array
  `np.einsum("ij,ij->i", X, X)` (sqrt unless `squared`); for a sparse matrix `tocsr()` then
  `csr_row_norms` (row-wise sum of squared CSR data, sqrt unless `squared`). The stub reproduces both
  with numpy/scipy.sparse only (sparse squared norm computed directly from CSR data via numpy,
  mathematically identical to `csr_row_norms`), avoiding the upstream `get_namespace` /
  `sparsefuncs_fast` / `_param_validation` / `validation` cascade. Only `row_norms` is used by the
  kernel (in `init_bounds_sparse` and `elkan_iter_chunked_sparse`, both sparse paths).
- **`CHUNK_SIZE`**: NOT a stub — provided by the co-built `_k_means_common.so` (`from ._k_means_common
  import CHUNK_SIZE` resolves at runtime against the vendored module).

## 3. Build-confirm — STANDALONE IMPORT (binding §4 criterion; the §4.2 criterion-3 isolatability gate)
`build_from_closure.sh`, run in X′. Builds the full runtime `.so` closure in dep order
(`_k_means_common.so` → `_k_means_elkan.so`) from the vendored closure **alone** (NOT the extracted
sdist tree, NOT installed sklearn), with the sklearn reference `-X` directives, then
**standalone-IMPORTs** `sklearn.cluster._k_means_elkan` as a package import (full cimport +
runtime-import cascade) under `OMP_NUM_THREADS=1`. Evidence (raw):
`logs/corpus/STEP_1.1.1_vendor__k_means_elkan_build.log`.
- **POSITIVE:** cythonize+compile `_k_means_common` (.so 423 512 B) → cythonize+compile `_k_means_elkan`
  (.so 420 648 B) → `import sklearn.cluster._k_means_elkan` → **`IMPORT-OK`**. Exported kernels present:
  `init_bounds_dense`, `init_bounds_sparse`, `elkan_iter_chunked_dense`, `elkan_iter_chunked_sparse`
  (`CHUNK_SIZE`, `row_norms` also visible as module-level names pulled in by the runtime imports).
- **NEGATIVE CONTROL (non-vacuity):** hide the vendored `_k_means_common.pxd` → cythonize of
  `_k_means_elkan` **fails** (`_euclidean_sparse_dense` unresolved → "Converting to Python object not
  allowed without gil", `_k_means_elkan.pyx:675`). Proves the build resolves the cimport from the
  **vendored closure**, not installed sklearn. Overall EXIT=0 (positive passes, negative fails as required).

The standalone IMPORT is the binding build-confirm: it exercises the cimported cdef/cpdef link to
`_k_means_common.so` AND the runtime `from ._k_means_common import CHUNK_SIZE` / `from ..utils.extmath
import row_norms` cascade. Compiles-but-not-importable would be inadmissible; this unit **imports**.

## 4. §4.2 admissibility (all 5 criteria — see `CHECKLIST_4.2.md`)
| # | §4.2 criterion | determination | evidence |
|---|---|---|---|
| 1 | Non-templated `.pyx` (not Tempita `.pyx.tp`) | **PASS** | vendored file is `_k_means_elkan.pyx` (not `.pyx.tp`); no Tempita |
| 2 | Stable upstream (not `scipy.special`) | **PASS** | `sklearn.cluster`; pinned sdist sha256 `b4237ed7…` (1.5.2) |
| 3 | Isolatable hot loop, public-API inputs | **PASS** | vendored-closure build + **standalone IMPORT** in X′ (§3) incl. negative control. Inputs are dense `float64` ndarrays + CSR `scipy.sparse` (public API) |
| 4 | Oracle-classifiable per §3.1 | **PASS (classifiable)** | centers/bounds floats → tolerance; int `labels` → bit-exact (§1). Exact tolerance **derived+frozen at 1.1.3** (oracle.json) |
| 5 | Golden runtime 50–500 ms | **PENDING-1.1.5** | input-scale design recorded (§5, CF-4 ~500 ms bias). Golden **measured under the timing rig at 1.1.5**; no runtime number claimed here (empirical-honesty) |

**Admissibility status: 4/5 confirmed (import-OK); criterion 5 (golden timing) pending the rig at
1.1.5.** Provisionally admissible; sealed at 1.1.5.

## 5. Hot-loop driver calls + input-scale design (criterion 3 inputs; CF-4 ~500 ms bias) — DESIGN ONLY
Representative inputs are constructible from public NumPy / `scipy.sparse` APIs. Candidate hot-loop
driver calls (a subset promoted to the §4.4 driver at 1.2):
1. `init_bounds_dense(X, centers, center_half_distances, labels, upper_bounds, lower_bounds, n_threads)`
   — initialise Elkan upper/lower bounds for dense input.
2. `elkan_iter_chunked_dense(X, sample_weight, centers_old, centers_new, weight_in_clusters,
   center_half_distances, distance_next_center, upper_bounds, lower_bounds, labels, center_shift,
   n_threads, update_centers=True)` — one chunked dense Elkan EM iteration (the primary hot loop).
3. `init_bounds_sparse(X_csr, centers, center_half_distances, labels, upper_bounds, lower_bounds,
   n_threads)` — sparse bound init (exercises vendored `row_norms`).
4. `elkan_iter_chunked_sparse(X_csr, sample_weight, centers_old, centers_new, weight_in_clusters,
   center_half_distances, distance_next_center, upper_bounds, lower_bounds, labels, center_shift,
   n_threads, update_centers=True)` — one chunked sparse Elkan EM iteration.

Driver pre-conditions the geometry from the data (compute `centers` via a fixed-seed init,
`center_half_distances` = 0.5·pairwise center distances, `distance_next_center` = nearest-other-center
distance) to drive the kernels as the upstream `_kmeans.py` would.

**Input-scale design (CF-4):** fixed-seed dense `float64` `X` of shape `(n_samples, n_features)` with
`n_clusters` centers, `OMP_NUM_THREADS=1`. Bias `n_samples · n_clusters · n_features · n_iter` toward
the ~500 ms band-upper to dilute the unresolved ~8 ms CF-4 offset (≈1.6 % at 500 ms vs ≈16 % at 50 ms)
and keep CF-3 CI@30 ≤ 1 % reachable. The **exact shape that lands ~500 ms is calibrated at 1.1.5**
under the timing rig (watch the 12 GB container ceiling). Recorded here as a DESIGN target only — NO
runtime number is claimed (golden measured + SHA-256 sealed at 1.1.5).

## 6. Carried obligations
- Criterion 5 golden + SHA-256 sealed at **1.1.5**; per-unit oracle.json + §3.1 tolerance at **1.1.3**.
- Per-unit timing precision (CF-3 band, CI@30 ≤ 1 %) re-established at **1.2** under quiesce-all (CF-1).
- This unit is **C** (no C++) → CF-5 (per-unit C++ sanitizer-clean) does **not** apply.
