# MANIFEST — corpus unit `sklearn.linear_model._cd_fast`

## Identity
- fold / codebase / unit: `sklearn.linear_model` / `sklearn` / `_cd_fast`
- target import module: `sklearn.linear_model._cd_fast`
- language: C (cythonized -> gcc-13)
- pyx (sdist-relative): `sklearn/linear_model/_cd_fast.pyx`
- role: Cython coordinate-descent kernels for Elastic-Net / Lasso (dense, sparse, gram,
  multi-task). The §4.2 isolatable hot loop.

## sdist provenance pin
- sdist: `scikit_learn-1.5.2` (read-only at `~/.cache/mbo/scikit_learn-1.5.2`)
- sdist sha256 (pinned): `b4237ed7b3fdd0a4882792e68ef2545d5baa50aca3bb45aa7df468138ad8f94d`
- every vendored source file below is copied **verbatim**; its sha256 == the sdist file's
  sha256 (provenance verified in the build log and at vendor time).

## FULL vendored closure (closure/ tree) — per-file sha256 == sdist
| closure path | kind | sha256 | builds .so? |
|---|---|---|---|
| `sklearn/linear_model/_cd_fast.pyx`   | unit pyx        | `246d423a2d6cd31de55ea6cda583987ffaea8a35fc45abd17fe4d56f3dae94dc` | YES (unit) |
| `sklearn/utils/_cython_blas.pyx`      | dep pyx         | `c4dff7af5decd8f8ac34e67c57cc575f97d3692f2f13e670dbbd36837ade06d3` | YES |
| `sklearn/utils/_cython_blas.pxd`      | dep pxd         | `2b1f9357e5b2dc90fc24044e99c001dfadb7b66934d569df7c28852d17ac5192` | (decl) |
| `sklearn/utils/_random.pyx`           | dep pyx         | `6d7173c41b783c9ab3364a4a34a99f8fe7e5317c11347e184ea5558e575a9dbf` | YES |
| `sklearn/utils/_random.pxd`           | dep pxd         | `eede689ba7500b95cce09aab8bcbc3ecfdf9e9474e7652ac141bc85a91605fba` | (decl) |
| `sklearn/utils/_typedefs.pxd`         | dep pxd         | `81ec3b62e0995b0a68f8959718322bc09dbe2bfea607e0b81a177f66ef4677ea` | NO (ctypedefs only) |

Non-source closure files (NOT sdist-verbatim — package context / faithful minimal shims):
| closure path | purpose |
|---|---|
| `sklearn/__init__.py`               | empty package marker |
| `sklearn/linear_model/__init__.py`  | empty package marker |
| `sklearn/utils/__init__.py`         | faithful-minimal `check_random_state` (see Python-level stubs) |
| `sklearn/exceptions.py`             | faithful-minimal `ConvergenceWarning(UserWarning)` |

## Closure-walk derivation (how the closure was resolved)
`_cd_fast.pyx` cimports / imports:
- `from libc.math cimport fabs`, `from cython cimport floating`, `import numpy as np`,
  `import warnings` -> Cython/stdlib/image builtins, NO vendoring.
- `from ..utils._cython_blas cimport (_axpy,_dot,_asum,_gemv,_nrm2,_copy,_scal)` and
  `cimport ColMajor,Trans,NoTrans` -> these are **non-inline `cdef`** BLAS wrappers +
  `cpdef enum` -> their symbols live in `_cython_blas`'s runtime `__pyx_capi__`
  => `_cython_blas.so` MUST be co-built and importable as `sklearn.utils._cython_blas`.
  `_cython_blas.pyx` in turn cimports only `from scipy.linalg.cython_blas cimport ...`
  (sdot/ddot/...): scipy is a builtin provided by the image's scipy -> no further vendoring.
- `from ..utils._typedefs cimport uint32_t` -> `uint32_t` is a `ctypedef` -> compile-time
  only -> `_typedefs.pxd` suffices, NO `.so`.
- `from ..utils._random cimport our_rand_r` -> `our_rand_r` is `cdef inline` (code inlines
  into `_cd_fast`), BUT `_random.pxd` declares a module-level `cdef uint32_t DEFAULT_SEED`,
  so Cython 3.x emits a **runtime `import sklearn.utils._random`** at `_cd_fast` module init.
  Empirically confirmed (build iteration 1): `ModuleNotFoundError: No module named
  'sklearn.utils._random'`. => `_random.so` IS in the runtime closure and is co-built.
  `_random.pyx` does `from . import check_random_state` (-> vendored utils `__init__`) and
  `from ._typedefs cimport intp_t` (-> `_typedefs.pxd`, already vendored).
- `from ..exceptions import ConvergenceWarning` -> module-scope python import -> faithful
  minimal `sklearn/exceptions.py`.

Runtime `.so` cluster built in dep order: `_cython_blas` -> `_random` -> `_cd_fast`.

## Python-level package-context stubs (faithful minimal impls)
- `sklearn.utils.check_random_state` (in `sklearn/utils/__init__.py`): verbatim semantics of
  `sklearn/utils/validation.py:check_random_state` (1.5.2): `numbers.Integral -> RandomState(seed)`;
  `RandomState -> as-is`; `None / np.random -> np.random.mtrand._rand`; else `ValueError`.
- `sklearn.exceptions.ConvergenceWarning` (in `sklearn/exceptions.py`): verbatim
  `class ConvergenceWarning(UserWarning)` leaf class (no body logic).

## Reference directive set (as-shipped, used for cythonize)
sklearn units: `-X language_level=3 -X boundscheck=False -X wraparound=False
-X initializedcheck=False -X nonecheck=False -X cdivision=True`
Compile (C): `gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp
-I<pyinclude> -I<numpy-include>`.

## Build-confirm (= STANDALONE IMPORT, binding §4)
In-container only (`localhost/motifbo-env:phase1`, X'). `build_from_closure.sh` copies the
closure to /tmp, builds the full runtime `.so` closure in dep order with the reference -X
directives, then standalone-IMPORTs `sklearn.linear_model._cd_fast` as a real package
submodule (OMP_NUM_THREADS=1). Result: **IMPORT-OK** — exported entry points
`enet_coordinate_descent`, `sparse_enet_coordinate_descent`, `enet_coordinate_descent_gram`,
`enet_coordinate_descent_multi_task`. Negative control (hide `_cython_blas.pxd`) fails the
`_cd_fast` cythonize as required (`'sklearn/utils/_cython_blas.pxd' not found`), proving the
compile resolves against the VENDORED closure, not installed sklearn. Raw log:
`logs/corpus/STEP_1.1.1_vendor__cd_fast_build.log`. unit .so = 452352 bytes;
`_cython_blas.so` = 390160; `_random.so` = 329032.

## Hot-loop driver calls (§4 — design intent; NO runtime number claimed here)
Primary driver = `enet_coordinate_descent` (dense Elastic-Net coordinate descent; inner loop
sweeps `n_features` per outer iteration up to `max_iter`). Faithful call shape:
```
enet_coordinate_descent(
    w,                       # float64[::1]  (n_features,)   coefficient vector (in/out)
    alpha, beta,             # float64        l1, l2 penalties
    X,                       # float64[::1,:] (n_samples,n_features) Fortran-contiguous
    y,                       # float64[::1]  (n_samples,)
    max_iter,                # unsigned int
    tol,                     # float64
    rng,                     # object: np.random.RandomState(0)
    random=0, positive=0,
)
```
Companion drivers (same kernel family, exercised for coverage):
`sparse_enet_coordinate_descent` (CSC X_data/X_indices/X_indptr), `enet_coordinate_descent_gram`
(precomputed Gram Q,q), `enet_coordinate_descent_multi_task` (W,Y multi-output).
**Input-scale design** biased toward ~500 ms wall per CF-4 (DESIGN TARGET ONLY): e.g.
n_samples ~ 2000, n_features ~ 4000, max_iter large enough that the CD sweep dominates,
dtype float64. Golden timing is measured at Step 1.1.5 — **NO runtime number is claimed here.**

## Oracle classes (§3.1)
`_cd_fast` is pure-numeric (BLAS Level-1/2 + elementwise soft-thresholding), no unsafe flags,
no I/O, deterministic given `rng` seed -> tiered oracle: exact/near-exact float comparison of
returned `w` (and gap/tol outputs) against the as-shipped golden, within the §3.1 numeric
tolerance band. Deterministic seeding via `rng = np.random.RandomState(0)` (consumed only when
`random=1`); with `random=0` the sweep is index-ordered and fully deterministic.

## Carried obligations
- This is a **C** unit (not C++): no CF-5 per-unit sanitizer obligation at 1.2 (that clause is
  C++-only). `-ffp-contract=fast` passed explicitly per §3.2.
- §4.2 criterion 5 (golden 50–500 ms) is **PENDING-1.1.5**; criteria 1–4 + import-OK pass now.
