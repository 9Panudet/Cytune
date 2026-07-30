# Corpus unit manifest — `scipy.optimize._bglu_dense`

Step 1.1.1. Part of the `scipy.optimize` fold.

| field | value |
|---|---|
| fold | `scipy.optimize` (C) |
| unit | `_bglu_dense.pyx` (LU / BGLU updates, revised simplex; `BGLU`, `LU`, `lu_factor`, `lu_solve`) |
| upstream | scipy **1.13.1**; sdist sha256 `095a87a0312b08dfd6a6155cbbd310a8c51800fc931b8c0b84003014b874ed3c` |
| build image | X′ `localhost/motifbo-env:phase1` |
| oracle class (§3.1) | pivot indices → bit-exact; LU factors → tolerance (§4.3) |

**Closure:** `closure/_bglu_dense.pyx` (sha256 == sdist). cimports `from scipy.linalg.cython_blas cimport
daxpy, dswap` — a **stable image-provided BLAS binding** (not in the sdist; analogous to numpy headers), and
`from scipy.linalg import solve, lu_solve, …` (runtime Python, image scipy). The corpus UNIT is vendored;
the stable BLAS binding is image-provided → imported **by file**. **Build-confirm (IMPORT, §4):** IMPORT-OK +
negative control (hide unit `.pyx` → fail). Raw: `logs/corpus/STEP_1.1.1_vendor__bglu_dense_build.log`.

**§4.2:** 1 ☑ non-templated; 2 ☑ stable upstream; 3 ☑ isolatable + IMPORT-OK; 4 ☑ oracle-classifiable
(pivot bit-exact / factors tolerance); 5 ☐ golden 50–500 ms **PENDING-1.1.5**. Provisionally admissible.

**β note (C-β1):** function-pins `boundscheck`,`wraparound`,`cdivision` (the cdivision is on **float**
division `H[i+1,i]/H[i,i]`, upstream-tagged `# not really important` → `cdivision=False` is
**feasible-but-slower**, a real zero-check signal, NOT infeasible). Reference build = bare `cython -3`;
β strips decorators at 1.2 → uniform Θ=1728. Driver/golden + input-scale (~500 ms, CF-4) at 1.2/1.1.5.
Note: upstream public driver `linprog(method='revised simplex')` is deprecated → `_group_columns` is the
optimize-fold primary; both retained.
