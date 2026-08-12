# §4.2 admissibility checklist — `sklearn.linear_model._cd_fast`

| # | §4.2 criterion | verdict | evidence |
|---|---|---|---|
| 1 | **Non-templated** (NOT Tempita `.pyx.tp`) | PASS | Source is `sklearn/linear_model/_cd_fast.pyx`; no `_cd_fast.pyx.tp` exists in the sdist. Cython `fused floating` (compile-time generic) is NOT Tempita templating. |
| 2 | **Stable upstream** | PASS | scikit-learn 1.5.2 pinned sdist (sha256 `b4237ed7…ad8f94d`); `_cd_fast` is a long-stable coordinate-descent kernel (Lasso/ElasticNet), present and API-stable across many releases. |
| 3 | **Isolatable hot loop** (import-confirm evidence) | PASS | Vendored-closure standalone IMPORT succeeded: `IMPORT-OK sklearn.linear_model._cd_fast`, all 4 CD entry points exported, built from the closure ALONE. Negative control (hide `_cython_blas.pxd`) fails the cythonize as required. Hot loop = the per-feature coordinate-descent sweep inside `enet_coordinate_descent`. Log: `logs/corpus/STEP_1.1.1_vendor__cd_fast_build.log`. |
| 4 | **Oracle-classifiable per §3.1** | PASS | Pure-numeric BLAS-1/2 + soft-thresholding; no unsafe flags, no I/O, deterministic given `rng` seed (and fully deterministic with `random=0`). Tiered float-comparison oracle on returned `w`/gap vs as-shipped golden within §3.1 tolerance. |
| 5 | **Golden 50–500 ms** | PENDING-1.1.5 | Input-scale design biased to ~500 ms (n_samples~2000, n_features~4000, float64) is a DESIGN target only; golden is measured at Step 1.1.5. No runtime number claimed. |

**Provisional verdict:** criteria 1–4 PASS + standalone IMPORT-OK -> **provisionally admissible**
(criterion 5 golden timing PENDING-1.1.5).

Note: C unit -> no CF-5 per-unit sanitizer obligation at 1.2 (C++-only clause).
