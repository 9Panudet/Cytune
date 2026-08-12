# MANIFEST — sklearn `_binning` (Step 1.1.1 vendored unit)

## Identity
- **fold:** sklearn.ensemble
- **codebase:** sklearn
- **unit:** `_binning`
- **target import module:** `sklearn.ensemble._hist_gradient_boosting._binning`
- **unit .pyx (sdist-relative):** `sklearn/ensemble/_hist_gradient_boosting/_binning.pyx`
- **language:** C (gcc-13)
- **exported callable:** `_map_to_bins` (public `def`); plus `cdef void _map_col_to_bins` (internal, nogil binary-search kernel)

## sdist provenance pin
- **scikit-learn 1.5.2 sdist sha256:** `b4237ed7b3fdd0a4882792e68ef2545d5baa50aca3bb45aa7df468138ad8f94d`
- Source root (read-only): `~/.cache/mbo/scikit_learn-1.5.2`

## FULL vendored closure (per-file sha256 == sdist; copied verbatim, no edits)
| closure path | role | sha256 | needs .so? |
|---|---|---|---|
| `sklearn/ensemble/_hist_gradient_boosting/_binning.pyx` | THE unit (built to .so) | `dbe0d54967efbef855fb768ff4e77e573390ebb34471bdc608f134aa8e26353a` | yes (this unit) |
| `sklearn/ensemble/_hist_gradient_boosting/common.pxd` | ctypedefs `X_DTYPE_C`(float64), `X_BINNED_DTYPE_C`(uint8) — compile-time | `d635ecc852d904185fbaf63cf665dcbf9c7e5ef9bf6055aad3c5dba2ca0069d5` | no (.pxd-only) |
| `sklearn/utils/_typedefs.pxd` | ctypedefs `float32_t/float64_t/intp_t/uint8_t/uint32_t` — compile-time | `81ec3b62e0995b0a68f8959718322bc09dbe2bfea607e0b81a177f66ef4677ea` | no (.pxd-only) |

Package markers (empty `__init__.py`, NOT upstream): `sklearn/`, `sklearn/ensemble/`,
`sklearn/ensemble/_hist_gradient_boosting/`, `sklearn/utils/`.

## Closure-walk derivation
1. `_binning.pyx` cimports: `from cython.parallel import prange` (builtin),
   `from libc.math cimport isnan` (builtin), `from .common cimport X_DTYPE_C, X_BINNED_DTYPE_C`.
2. `X_DTYPE_C` / `X_BINNED_DTYPE_C` are **`ctypedef`** in `common.pxd` → compile-time only → vendor
   `common.pxd`, **no `.so`** for common (no cdef class / non-inline cdef/cpdef of common is cimported).
   The `MonotonicConstraint` enum, `hist_struct`/`node_struct` packed structs in `common.pxd` are NOT
   cimported by `_binning` and are compile-time anyway.
3. `common.pxd` cimports `from ...utils._typedefs cimport float32_t, float64_t, intp_t, uint8_t, uint32_t`
   — all **`ctypedef`** → vendor `_typedefs.pxd`, **no `.so`**. `_typedefs.pxd` cimports nothing.
4. Module-scope Python `import`: none beyond the two builtin cimports above. No `from . import <helper>`
   → **no package-context stubs required** (no `__init__` Python helpers needed).
5. Closure is therefore: 1 built `.so` (the unit) + 2 pure-header `.pxd` + 4 empty package markers.

## Reference directive set (sklearn as-shipped; used for cythonize)
`-X language_level=3 -X boundscheck=False -X wraparound=False -X initializedcheck=False -X nonecheck=False -X cdivision=True`

## Compile flags (C)
`gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp -I<pyinclude> -I<numpy-include>`

## Build-confirm = STANDALONE IMPORT (§4, binding)
In-container `localhost/motifbo-env:phase1` via `build_from_closure.sh`:
- POSITIVE: cythonize+compile from the vendored closure ALONE → `.so` (229688 bytes); then
  `importlib.import_module('sklearn.ensemble._hist_gradient_boosting._binning')` with the built `.so`
  installed at its true package path and `OMP_NUM_THREADS=1` → **IMPORT-OK**, `m.__file__` ends in `.so`,
  exports `['_map_to_bins']`.
- NEGATIVE CONTROL: hiding `common.pxd` makes cythonize FAIL (`X_DTYPE_C`/`X_BINNED_DTYPE_C` degrade to
  Python objects → "Accessing Python attribute not allowed without gil" inside the nogil prange),
  proving the closure resolves against vendored files, not the container's installed sklearn (which has
  no usable `__version__` and is irrelevant to this build).
- Log: `logs/corpus/STEP_1.1.1_vendor__binning_build.log`.

## Hot-loop driver call (§4 — input-scale design only; NO runtime number claimed here)
- Driver: `_BinMapper.transform()` in `sklearn/ensemble/_hist_gradient_boosting/binning.py:279`:
  ```
  _map_to_bins(X, self.bin_thresholds_, self.is_categorical_,
               self.missing_values_bin_idx_, n_threads, binned)
  ```
  where `X` is `float64` C-contig `(n_samples, n_features)`, `binned` is `uint8` Fortran-order
  `np.zeros_like(X, order="F")`, `bin_thresholds_` is a `list` of increasing `float64` arrays
  (one per feature), `is_categorical_` is `uint8 (n_features,)`, `missing_values_bin_idx_` is
  `uint8` (= `n_bins - 1`). The kernel `_map_col_to_bins` runs a nogil `prange` over samples doing a
  per-value binary search across thresholds.
- **Input-scale design (DESIGN target only; golden measured at 1.1.5 — NO runtime number claimed):**
  bias toward ~500ms per CF-4. Levers: `n_samples` (prange extent), `n_features` (outer loop),
  `max_bins` ≈ 255 (binary-search depth ≈ log2(255) ≈ 8 cmp/value), `n_threads=1` for golden timing.
  A single-thread design near ~5e7–1e8 binary-searched values is the scaling knob; exact size frozen at 1.1.5.

## Oracle classification (§3.1)
- `_map_to_bins` is a **deterministic pure numeric kernel** (no RNG, no I/O). Same inputs → bitwise-identical
  `binned` output. Oracle class: **exact-equality / deterministic** (golden recompute is bit-exact; allowed
  comparator is array-equal on the `uint8` output). No fp-tolerance class needed — output is integer-coded.

## C++ / sanitizer note
- This unit is **C** (not C++) → no CF-5 C++-specific per-unit sanitizer obligation at 1.2.

## §4.2 criteria
See `CHECKLIST_4.2.md`. Criteria 1–4 PASS; criterion 5 (golden 50–500ms) = PENDING-1.1.5.
Provisionally admissible (1–4 pass + STANDALONE-IMPORT-OK).
