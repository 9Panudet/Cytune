# Corpus unit manifest — `sklearn.manifold._barnes_hut_tsne` (CONTINGENT on 1.1.3 determinism)

Step 1.1.1. Most-coupled unit. Vendored + IMPORT-confirmed, but **fold membership is contingent on the
1.1.3 t-SNE determinism proof** (criterion 4) — until then it is NOT counted toward §4.1b (the corpus
already meets ≥10 without it).

## 1. Identity & pin
| field | value |
|---|---|
| fold | `sklearn.manifold` (C) | 
| unit | `_barnes_hut_tsne.pyx` (Barnes–Hut t-SNE gradient) |
| upstream | scikit-learn **1.5.2**; sdist sha256 `b4237ed7…` |
| build image | X′ `localhost/motifbo-env:phase1` |
| §4.3 oracle class | floats → tolerance |

## 2. Vendored closure (= the full tree cluster + `_quad_tree` + the unit)
`_barnes_hut_tsne` → `_quad_tree` (cdef class `_QuadTree`) → `tree/_utils` (safe_realloc), with the tree
cluster (`_criterion`/`_splitter`/`_tree`) reachable via the cimport graph → the runtime `.so` closure is
the full tree cluster + `_quad_tree` + `_random` + `_typedefs` + the unit (all sha256 == sdist). Package
context: `check_random_state` in `sklearn/utils/__init__.py`.

## 3. Build-confirm — IMPORT (§4)
`build_from_closure.sh` in X′ (reference `cdivision=True` directives). **IMPORT-OK
`sklearn.manifold._barnes_hut_tsne`; `gradient` callable.** Raw:
`logs/corpus/STEP_1.1.1_vendor_barnes_hut_tsne_build.log`. so-bytes 243808.

## 4. §4.2 — criterion 4 is the contingency
- 1 non-templated ☑; 2 stable upstream ☑; 3 isolatable+IMPORT-OK ☑; **4 oracle-classifiable: CONTINGENT** —
  t-SNE has embedding-init randomness; **determinism established at 1.1.3** by **kernel-level driving**: call
  `gradient()` with a FIXED input embedding + FIXED `val_P` + a `_QuadTree` built from the fixed embedding,
  `OMP_NUM_THREADS=1` (kills prange reduction non-determinism); init randomness sidestepped via `init='pca'`
  OR direct kernel driving. If determinism cannot be shown at 1.1.3, **drop manifold honestly** (corpus stays
  ≥10). 5 golden 50–500 ms PENDING-1.1.5.
- **Status: vendored + IMPORT-confirmed; fold membership PENDING the 1.1.3 determinism proof.**
