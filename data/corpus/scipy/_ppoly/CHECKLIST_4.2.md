# §4.2 checklist — `scipy.interpolate._ppoly`

| # | criterion | verdict | evidence |
|---|---|---|---|
| 1 | Non-templated `.pyx` | ☑ | `.pyx` + `_poly_common.pxi`, sha256 == sdist `095a87a0…` |
| 2 | Stable upstream (not `scipy.special`) | ☑ | `scipy.interpolate` |
| 3 | Isolatable hot loop, public-API inputs | ☑ | unit + `.pxi` vendored, LAPACK binding image-provided, **IMPORT-OK** (`…vendor__ppoly_build.log`) |
| 4 | Oracle-classifiable per §3.1 | ☑ | floats → tolerance |
| 5 | Golden 50–500 ms | ☐ PENDING-1.1.5 | rig; no number claimed |

Provisionally admissible (1–4 PASS). β (C-β1): boundscheck/wraparound/cdivision function-pins; cdivision on
FLOAT division (`cdivision=False` feasible-but-slower).
