# §4.2 checklist — `scipy.optimize._bglu_dense`

| # | criterion | verdict | evidence |
|---|---|---|---|
| 1 | Non-templated `.pyx` | ☑ | `.pyx`, sha256 == sdist `095a87a0…` |
| 2 | Stable upstream (not `scipy.special`) | ☑ | `scipy.optimize` |
| 3 | Isolatable hot loop, public-API inputs | ☑ | unit vendored, BLAS binding image-provided, **IMPORT-OK** (`…vendor__bglu_dense_build.log`) |
| 4 | Oracle-classifiable per §3.1 | ☑ | pivot indices → bit-exact; LU factors → tolerance |
| 5 | Golden 50–500 ms | ☐ PENDING-1.1.5 | rig; no number claimed |

Provisionally admissible (1–4 PASS). β (C-β1): boundscheck/wraparound (pure-speed) + cdivision on FLOAT
division (`cdivision=False` feasible-but-slower, not infeasible).
