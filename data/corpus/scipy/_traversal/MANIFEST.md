# Corpus unit manifest — `scipy.sparse.csgraph._traversal`

Step 1.1.1. Part of the `scipy.sparse.csgraph` fold (vendored by the fan-out Workflow; import re-verified
inline).

| field | value |
|---|---|
| fold | `scipy.sparse.csgraph` (C) |
| unit | `_traversal.pyx` (BFS/DFS / connected components graph traversal) |
| upstream | scipy **1.13.1**; sdist sha256 `095a87a0312b08dfd6a6155cbbd310a8c51800fc931b8c0b84003014b874ed3c` |
| build image | X′ `localhost/motifbo-env:phase1` |
| oracle class (§3.1) | traversal orderings / component labels → bit-exact; distances → tolerance (§4.3) |

**Closure:** `closure/` = `scipy/sparse/csgraph/{_traversal.pyx, _tools.pyx, parameters.pxi, _validation.py}`
+ package markers (all `.pyx`/`.pxi` sha256 == sdist). `_traversal` `include`s `parameters.pxi`, cimports
`_tools` (co-built), and uses `_validation` (Python) at runtime — imported by the **dotted** package path
`scipy.sparse.csgraph._traversal`. **Build-confirm (IMPORT, §4):** IMPORT-OK + negative control. Raw:
`logs/corpus/STEP_1.1.1_vendor__traversal_build.log`. (Re-verified inline this session.)

**§4.2:** 1 ☑ non-templated; 2 ☑ stable upstream; 3 ☑ isolatable + IMPORT-OK; 4 ☑ oracle-classifiable
(orderings bit-exact); 5 ☐ golden 50–500 ms **PENDING-1.1.5**. Provisionally admissible.

**β note (C-β1):** function-pins `boundscheck` (local `with` block; pure-speed, no cdivision). Reference
build = bare `cython -3`; β strips at 1.2 → uniform Θ=1728. Driver/golden + input-scale (~500 ms) at 1.2/1.1.5.
