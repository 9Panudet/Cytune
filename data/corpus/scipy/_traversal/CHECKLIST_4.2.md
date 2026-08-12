# §4.2 checklist — `scipy.sparse.csgraph._traversal`

| # | criterion | verdict | evidence |
|---|---|---|---|
| 1 | Non-templated `.pyx` | ☑ | `.pyx`, sha256 == sdist `095a87a0…` |
| 2 | Stable upstream (not `scipy.special`) | ☑ | `scipy.sparse.csgraph` |
| 3 | Isolatable hot loop, public-API inputs | ☑ | closure (+`_tools`,`parameters.pxi`,`_validation`) **IMPORT-OK** (`…vendor__traversal_build.log`) |
| 4 | Oracle-classifiable per §3.1 | ☑ | traversal orderings / labels → bit-exact |
| 5 | Golden 50–500 ms | ☐ PENDING-1.1.5 | rig; no number claimed |

Provisionally admissible (1–4 PASS). β (C-β1): boundscheck local pin (pure-speed), no cdivision.
