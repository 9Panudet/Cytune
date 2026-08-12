# CHECKLIST §4.2 — sklearn `_binning`

Target module: `sklearn.ensemble._hist_gradient_boosting._binning`
Build-confirm = STANDALONE IMPORT (§4). Provisionally admissible **iff** criteria 1–4 pass AND import-OK.

| # | §4.2 criterion | verdict | evidence |
|---|---|---|---|
| 1 | **Non-templated** (not Tempita `.pyx.tp`) | **PASS** | Source is `_binning.pyx`; no `_binning.pyx.tp` exists in the sdist dir. Plain `.pyx`, no Tempita `{{...}}` codegen. |
| 2 | **Stable upstream** | **PASS** | Pinned scikit-learn 1.5.2 sdist (sha256 `b4237ed7...`); kernel `_map_to_bins` is the long-stable HGBT binning entry (author N. Hug); no churny/experimental API. |
| 3 | **Isolatable hot loop** (import-confirm evidence) | **PASS** | Vendored-closure-ALONE cythonize+compile → `.so` (229688 B) and **STANDALONE IMPORT** of `sklearn.ensemble._hist_gradient_boosting._binning` succeeds (`m.__file__` ends `.so`, exports `['_map_to_bins']`). Negative control: hiding `common.pxd` FAILS the build — proves resolution against the vendored closure, not installed sklearn. Log: `logs/corpus/STEP_1.1.1_vendor__binning_build.log`. |
| 4 | **Oracle-classifiable per §3.1** | **PASS** | Deterministic pure numeric kernel: no RNG / no I/O; same inputs → bit-identical `uint8` `binned` output. Oracle class = exact-equality (array-equal comparator); golden recompute is bit-exact. |
| 5 | **Golden 50–500ms** | **PENDING-1.1.5** | Input-scale design biased toward ~500ms (levers: `n_samples`, `n_features`, `max_bins`≈255, `n_threads=1`). DESIGN target only — actual golden measured at Step 1.1.5; **no runtime number claimed here**. |

**Provisional verdict:** criteria 1–4 PASS + STANDALONE-IMPORT-OK → **provisionally admissible** (criterion 5 pending golden at 1.1.5).
