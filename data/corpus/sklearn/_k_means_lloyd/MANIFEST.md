# MANIFEST — sklearn.cluster._k_means_lloyd  (corpus unit, Step 1.1.1)

## Identity
- codebase: **scikit-learn 1.5.2**
- fold: `sklearn.cluster`
- unit (kernel module): `sklearn.cluster._k_means_lloyd`
- pyx (sdist-relative): `sklearn/cluster/_k_means_lloyd.pyx`
- language: **C** (gcc-13). Not C++ — no CF-5 per-unit sanitizer obligation at 1.2.
- target import module: `sklearn.cluster._k_means_lloyd`
- exported callables: `lloyd_iter_chunked_dense`, `lloyd_iter_chunked_sparse`
  (single Lloyd-iteration E/M step over data chunks; dense + CSR-sparse paths).

## Sdist provenance pin
- sdist: `scikit_learn-1.5.2.tar.gz`
- sdist sha256: `b4237ed7b3fdd0a4882792e68ef2545d5baa50aca3bb45aa7df468138ad8f94d`  (VERIFIED == pin)

## FULL vendored closure (per-file sha256 == sdist; copied verbatim, no edits)
Files copied VERBATIM from the sdist (sha256 identical to the sdist file):

| closure path | role | sha256 | .so co-built? |
|---|---|---|---|
| `sklearn/cluster/_k_means_lloyd.pyx`  | the UNIT kernel | `bb62d8f46cbae469582edca0c1ff392d5d1a599591d30838271d0b652cff0447` | yes (the unit) |
| `sklearn/cluster/_k_means_common.pxd` | cimported decls (`_relocate_*`, `_average_centers`, `_center_shift`) | `e905b5f13b42d701a9c9377471d1bd3f14984e23f864dde18fa96d256add6a27` | (decl) |
| `sklearn/cluster/_k_means_common.pyx` | defines the above non-inline cdef/cpdef + `CHUNK_SIZE` | `3aa9b4f3cebd60bb5f6d69a67068b473ad84b8c816d8f3e86e430fc6955e8470` | **yes** |
| `sklearn/utils/_cython_blas.pxd`      | cimported decls (`_gemm`, `RowMajor`, `NoTrans`, `Trans`) | `2b1f9357e5b2dc90fc24044e99c001dfadb7b66934d569df7c28852d17ac5192` | (decl) |
| `sklearn/utils/_cython_blas.pyx`      | defines `_gemm` (non-inline cdef; BLAS Level-3) | `c4dff7af5decd8f8ac34e67c57cc575f97d3692f2f13e670dbbd36837ade06d3` | **yes** |
| `sklearn/utils/_openmp_helpers.pxd`   | `cdef extern from *` omp lock decls — header-only | `391b4d5e33d70c13a6a075bafbee78c30acc108669b42019e93f0224f0ae27ed` | no (.pxd suffices) |

Closure non-source files (NOT from sdist):
- `sklearn/__init__.py`, `sklearn/cluster/__init__.py`, `sklearn/utils/__init__.py` — empty package markers (§ closure-walk rule 6; NOT the heavyweight upstream `__init__`).
- `sklearn/utils/extmath.py` — FAITHFUL MINIMAL stub providing ONLY `row_norms` (see Package context).

## Closure-walk (full transitive resolution from the .pyx)
From `_k_means_lloyd.pyx`:
- `cython`, `cython.parallel`, `libc.stdlib/string/float` -> Cython/stdlib builtins -> NO vendoring.
- `..utils._openmp_helpers cimport omp_lock_t, omp_init_lock, omp_destroy_lock, omp_set_lock, omp_unset_lock`
  -> `_openmp_helpers.pxd` is pure `cdef extern from *` (header-embedded omp.h) -> **.pxd only, no .so**.
- `..utils._cython_blas cimport _gemm, RowMajor, Trans, NoTrans`
  -> `_gemm` is a non-inline `cdef` (defined in `_cython_blas.pyx`) -> **co-build `_cython_blas.so`**.
     `RowMajor/Trans/NoTrans` are `cpdef enum` members (compile-time). `_cython_blas.pyx` cimports only
     `scipy.linalg.cython_blas` (scipy Cython builtin, present in the image as `cython_blas.pxd`) and
     `cython` -> no further repo vendoring.
- `..utils.extmath import row_norms` -> Python runtime import -> vendored `extmath.py` stub (below).
- `._k_means_common import CHUNK_SIZE` -> Python runtime import (module-level int 256, exported by the
  `_k_means_common.so`).
- `._k_means_common cimport _relocate_empty_clusters_dense, _relocate_empty_clusters_sparse,
  _average_centers, _center_shift` -> non-inline cdef/cpdef (defined in `_k_means_common.pyx`)
  -> **co-build `_k_means_common.so`**. Recurse on `_k_means_common.pyx`: imports numpy, cython,
  cython.parallel, libc.math (all builtins) + `..utils.extmath import row_norms` (same stub).
- Recursion terminates: no further repo `.pxd` cimports remain.

## Package context (rule 5 stubs — recorded)
- `sklearn/utils/extmath.py :: row_norms(X, squared=False)` — FAITHFUL MINIMAL impl.
  - dense path: `np.einsum("ij,ij->i", X, X)` then optional `np.sqrt` (identical to upstream numpy path).
  - CSR-sparse path: per-row sum of squares of `X.data` (== upstream `csr_row_norms`), optional sqrt.
  - Rationale: upstream `extmath` drags array-api dispatch + `sparsefuncs_fast.csr_row_norms` +
    validation, none of which the closure import needs. Only `row_norms` is imported by the closure
    (by BOTH `_k_means_lloyd.pyx` and `_k_means_common.pyx`). No input validation (upstream
    `row_norms` also performs none). Used to seed `centers_squared_norms`; mathematically faithful.

## Reference directive set (sklearn, as-shipped) — used for cythonize
`-X language_level=3 -X boundscheck=False -X wraparound=False -X initializedcheck=False -X nonecheck=False -X cdivision=True`
COMPILE (C): `gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp -I<pyinclude> -I<numpy-include>`.

## Build-confirm == STANDALONE IMPORT (binding, §4)
Built FROM THE VENDORED CLOSURE ALONE, in dependency order:
`_cython_blas.so` -> `_k_means_common.so` -> `_k_means_lloyd.so`, then
`import sklearn.cluster._k_means_lloyd` (full package import; runtime cascade resolves
`._k_means_common` and `..utils.extmath`). Result: **IMPORT-OK** (`OMP_NUM_THREADS=1`).
Negative control: hiding the vendored `_k_means_common.pxd` makes the unit cythonize FAIL
(`'_center_shift' is not a constant, variable or function identifier`) — proving the cimport
resolves against the VENDORED closure, not the container's installed sklearn.
Log: `logs/corpus/STEP_1.1.1_vendor__k_means_lloyd_build.log`.
Unit `.so`: 335200 bytes (within the package build). `_cython_blas.so` 390160, `_k_means_common.so` 423512.

## Hot-loop driver calls (CF-4) — input-scale DESIGN target only; NO runtime number claimed here
Golden measured at 1.1.5 (CF-4). Driver exercises the dense + sparse Lloyd iteration kernels:
```
import numpy as np, scipy.sparse as sp
from sklearn.cluster._k_means_lloyd import lloyd_iter_chunked_dense, lloyd_iter_chunked_sparse

rng = np.random.RandomState(0)
# DENSE driver — sizes below are a DESIGN bias toward ~500ms/iteration per CF-4 (NOT a measurement):
n_samples, n_features, n_clusters = 200_000, 50, 256
X            = rng.random_sample((n_samples, n_features)).astype(np.float64)   # C-contiguous
sample_weight= np.ones(n_samples, dtype=np.float64)
centers_old  = rng.random_sample((n_clusters, n_features)).astype(np.float64)
centers_new  = np.zeros_like(centers_old)
weight_in    = np.zeros(n_clusters, dtype=np.float64)
labels       = np.zeros(n_samples, dtype=np.int32)
center_shift = np.zeros(n_clusters, dtype=np.float64)
lloyd_iter_chunked_dense(X, sample_weight, centers_old, centers_new,
                         weight_in, labels, center_shift, n_threads=1, update_centers=True)

# SPARSE driver (CSR) — same kernel, sparse path:
Xs = sp.random(n_samples, n_features, density=0.1, format='csr',
               dtype=np.float64, random_state=0)
lloyd_iter_chunked_sparse(Xs, sample_weight, centers_old, centers_new,
                          weight_in, labels, center_shift, n_threads=1, update_centers=True)
```
Input-scale biased toward ~500 ms / iteration per CF-4. **DESIGN target only — golden measured at
1.1.5; this manifest claims NO runtime number.**

## Oracle classes (§3.1)
- Deterministic numeric kernel: given fixed inputs and `n_threads=1`, outputs (`labels`, `centers_new`,
  `weight_in_clusters`, `center_shift`) are bitwise-reproducible -> tier-1 exact-equality oracle on a
  golden snapshot. (Multi-thread reduction order under the omp lock can perturb the last ULPs of the
  float accumulation -> if multi-threaded golden is used, tier-2 tight-tolerance allclose; the
  single-thread golden is the tier-1 anchor.)
- Correctness invariants (tier-2): each `labels[i] in [0, n_clusters)`; argmin consistency of the
  assigned label against `centers_squared_norms - 2 X.C^T`; `center_shift >= 0`.

## §4.2 criteria — see CHECKLIST_4.2.md
1 non-templated, 2 stable upstream, 3 isolatable hot loop (import-confirm evidence), 4 oracle-classifiable
per §3.1 — all PASS. 5 golden 50-500 ms = PENDING-1.1.5. Provisionally admissible (1-4 pass + IMPORT-OK).
