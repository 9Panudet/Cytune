# Corpus unit manifest — `scipy.interpolate._ppoly`

Step 1.1.1. The `scipy.interpolate` fold.

| field | value |
|---|---|
| fold | `scipy.interpolate` (C) |
| unit | `_ppoly.pyx` (piecewise-polynomial evaluation; `evaluate`, `evaluate_bernstein`, `integrate`, …) |
| upstream | scipy **1.13.1**; sdist sha256 `095a87a0312b08dfd6a6155cbbd310a8c51800fc931b8c0b84003014b874ed3c` |
| build image | X′ `localhost/motifbo-env:phase1` |
| oracle class (§3.1) | floats → tolerance (§4.3) |

**Closure:** `closure/_ppoly.pyx` + `closure/_poly_common.pxi` (the `include`d helper; both sha256 == sdist).
cimports `from scipy.linalg.cython_lapack cimport dgeev` — a **stable image-provided LAPACK binding** (not in
the sdist). UNIT vendored, LAPACK binding image-provided → imported **by file**. **Build-confirm (IMPORT,
§4):** IMPORT-OK + negative control. Raw: `logs/corpus/STEP_1.1.1_vendor__ppoly_build.log`.

**§4.2:** 1 ☑ non-templated; 2 ☑ stable upstream (not `scipy.special`); 3 ☑ isolatable + IMPORT-OK;
4 ☑ oracle-classifiable (floats→tolerance); 5 ☐ golden 50–500 ms **PENDING-1.1.5**. Provisionally admissible.

**β note (C-β1):** pervasive function-pins `boundscheck`,`wraparound`,`cdivision` (every function). cdivision is
on **float** division (`f/df`, `(xval-x[i])/ds`, …) → `cdivision=False` **feasible-but-slower** (zero-check),
NOT infeasible. Reference build = bare `cython -3`; β strips decorators at 1.2 → uniform Θ=1728. Driver/golden
+ input-scale (~500 ms, CF-4) at 1.2/1.1.5.
