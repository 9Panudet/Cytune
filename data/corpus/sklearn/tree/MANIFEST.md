# Corpus FOLD manifest — `sklearn.tree` (units: `_tree`, `_criterion`, `_splitter`)

Step 1.1.1. The 3 tree corpus units share ONE runtime `.so` cluster and cannot be built independently, so
they are vendored as a **fold-level closure** with this shared manifest + per-unit §4.2 checklist rows.

## 1. Identity & upstream pin
| field | value |
|---|---|
| codebase (LOMO fold) | `sklearn.tree` (fold; **C++**, image X′ g++-13) |
| units | `_tree.pyx`, `_criterion.pyx`, `_splitter.pyx` |
| upstream | scikit-learn **1.5.2**; sdist sha256 `b4237ed7b3fdd0a4882792e68ef2545d5baa50aca3bb45aa7df468138ad8f94d` |
| build image | X′ = `localhost/motifbo-env:phase1` (`d45e33b0`); numpy 2.4.6 / Cython 3.2.5 / gcc-13 + g++-13 |
| §4.3 kernels | tree build / split search / impurity |
| §4.3 oracle classes | split indices/structure → bit-exact; impurity → tolerance |

## 2. Vendored cimport closure (shared runtime `.so` cluster)
`closure/` (all `.pyx`/`.pxd` sha256 == sdist). Runtime `.so` chain (built in dep order by
`build_from_closure.sh`): `_random` → `_utils` → `_quad_tree` → `_criterion` → `_splitter` → `_tree`.
- `sklearn/tree/{_tree,_criterion,_splitter,_utils}.{pyx,pxd}` — the units + the `_utils` helper (safe_realloc,
  WeightedMedianCalculator, log).
- `sklearn/neighbors/_quad_tree.{pyx,pxd}` — `_QuadTree` (cdef class) + `Cell` struct cimported by `_utils.pxd`.
- `sklearn/utils/{_typedefs.pxd,_random.{pyx,pxd}}` — types + `our_rand_r`.
- **Package context:** `sklearn/utils/__init__.py` provides the verbatim `check_random_state` (`_random.pyx:14`
  does `from . import check_random_state`); other `__init__.py` are empty markers.

## 3. Build-confirm — standalone IMPORT (§4), REFERENCE directives (`cdivision=True`)
`build_from_closure.sh` in X′. Raw: `logs/corpus/STEP_1.1.1_cdivision_rootcause_import_confirm.log` (diagnosis)
+ re-verified this session. **All 3 units IMPORT-OK** (`sklearn.tree._tree/_criterion/_splitter`). Built under
the sklearn as-shipped reference directives `-X cdivision=True -X boundscheck=False -X wraparound=False
-X initializedcheck=False -X nonecheck=False -X language_level=3` (sklearn/meson.build:184-185).
**`cdivision=True` is REQUIRED** — the kernels index with integer division; `cdivision=False` is a genuine
§3.5 feasibility-0 of the real kernel (NOT patched; recorded in `THETA_DIRECTIVE_POLICY.md` C-β1).

## 4. §4.2 admissibility (per unit; full table in `CHECKLIST_4.2.md`)
Criteria 1–4 PASS for all 3 (non-templated `.pyx`; stable upstream; isolatable [fold-cluster import-OK];
oracle-classifiable per §4.3). Criterion 5 (golden 50–500 ms) **PENDING-1.1.5** (no runtime number claimed).
**Provisionally admissible (3 units).**

## 5. CF-5 (binding, at 1.2/preflight): these are **C++** units → per-unit C++ sanitizer-clean
(STL/RTTI/iterator surface) **+** per-unit `detect_leaks=1` leak-audit BEFORE each counts at 1.2. The
mini-I-3 RIG signature did NOT discharge this. Driver/golden + input-scale (~500 ms, CF-4) at 1.2/1.1.5.
