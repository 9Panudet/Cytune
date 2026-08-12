# Corpus unit manifest — `scipy.optimize._group_columns`

Step 1.1.1. Part of the `scipy.optimize` fold.

| field | value |
|---|---|
| fold | `scipy.optimize` (C) |
| unit | `_group_columns.pyx` (numerical-Jacobian column grouping; `group_dense`, `group_sparse`) |
| upstream | scipy **1.13.1**; sdist sha256 `095a87a0312b08dfd6a6155cbbd310a8c51800fc931b8c0b84003014b874ed3c` |
| build image | X′ `localhost/motifbo-env:phase1` |
| oracle class (§3.1) | grouping/column indices → bit-exact (integer partition) |

**Closure:** `closure/_group_columns.pyx` (sha256 == sdist) — **self-contained** (cimports only `cython` +
`numpy`, both builtins). No sibling `.so`, no scipy.linalg binding. Imported **by file** (uniform with the
scipy batch). **Build-confirm (IMPORT, §4):** `build_from_closure.sh` in X′ → IMPORT-OK + negative control.
Raw: `logs/corpus/STEP_1.1.1_vendor__group_columns_build.log`.

**§4.2:** 1 non-templated ☑; 2 stable upstream ☑; 3 isolatable + IMPORT-OK ☑; 4 oracle-classifiable
(bit-exact grouping) ☑; 5 golden 50–500 ms **PENDING-1.1.5**. Provisionally admissible.

**β note (C-β1):** pins `boundscheck`,`wraparound` at function level (pure-speed; never correctness-bearing);
no `cdivision` pin. Reference build = bare `cython -3` (as-shipped). β strips these decorators at 1.2 →
uniform Θ=1728; both directive values feasible. Driver/golden + input-scale (~500 ms, CF-4) at 1.2/1.1.5.
