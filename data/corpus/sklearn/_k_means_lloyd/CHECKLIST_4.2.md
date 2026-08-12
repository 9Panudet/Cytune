# CHECKLIST §4.2 — sklearn.cluster._k_means_lloyd

Unit: `sklearn/cluster/_k_means_lloyd.pyx` (C) -> module `sklearn.cluster._k_means_lloyd`.
Provisionally admissible **iff criteria 1-4 PASS and the unit standalone-IMPORTs from its vendored
closure** (criterion 5 is golden timing, deferred to 1.1.5).

| # | §4.2 criterion | verdict | evidence |
|---|---|---|---|
| 1 | **Non-templated** (NOT Tempita `.pyx.tp`) | **PASS** | source is `_k_means_lloyd.pyx` (plain). No `_k_means_lloyd.pyx.tp` in the sdist. Uses Cython fused `floating` (compile-time fusion), not Tempita codegen. Closure deps `_k_means_common.pyx`, `_cython_blas.pyx` are also plain `.pyx` (not `.tp`). |
| 2 | **Stable upstream** | **PASS** | scikit-learn 1.5.2, pinned sdist sha256 `b4237ed7…ad8f94d`. K-means Lloyd kernel is long-stable; chunked-EM structure (`lloyd_iter_chunked_dense/sparse`) and the `_k_means_common` helper split are established API-internal kernels. |
| 3 | **Isolatable hot loop** (import-confirm) | **PASS** | the chunked Lloyd E/M step is the isolatable hot loop (parallel `prange` over data chunks, BLAS Level-3 `_gemm` per chunk). **Build-confirm == standalone IMPORT** from the VENDORED closure alone: full `.so` closure built in dep order (`_cython_blas.so` -> `_k_means_common.so` -> `_k_means_lloyd.so`); `import sklearn.cluster._k_means_lloyd` => **IMPORT-OK** with runtime cascade verified (`CHUNK_SIZE==256`, `row_norms` smoke). Negative control: hiding vendored `_k_means_common.pxd` makes the unit cythonize FAIL => closure is the real source, not installed sklearn. Log: `logs/corpus/STEP_1.1.1_vendor__k_means_lloyd_build.log`. |
| 4 | **Oracle-classifiable** per §3.1 | **PASS** | deterministic numeric kernel: fixed inputs + `n_threads=1` => bitwise-reproducible (`labels`, `centers_new`, `weight_in_clusters`, `center_shift`) -> tier-1 exact-equality on a golden snapshot. Tier-2 invariants: `labels[i] in [0,n_clusters)`, argmin consistency, `center_shift >= 0`. Multi-thread reduction (omp lock) may perturb last-ULP float accumulation -> tier-2 tight-allclose if a multi-thread golden is used. |
| 5 | **Golden 50-500 ms** | **PENDING-1.1.5** | input-scale DESIGN biased toward ~500 ms/iteration (see MANIFEST driver). Golden measured at 1.1.5 (CF-4). NO runtime number claimed now. |

**Status: provisionally ADMISSIBLE** — criteria 1-4 PASS and the unit standalone-IMPORTs from its
vendored closure in X'. Criterion 5 (golden timing) PENDING at Step 1.1.5.
