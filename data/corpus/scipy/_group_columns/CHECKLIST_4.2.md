# §4.2 checklist — `scipy.optimize._group_columns`

| # | criterion | verdict | evidence |
|---|---|---|---|
| 1 | Non-templated `.pyx` | ☑ | `.pyx`, sha256 == sdist `095a87a0…` |
| 2 | Stable upstream (not `scipy.special`) | ☑ | `scipy.optimize` |
| 3 | Isolatable hot loop, public-API inputs | ☑ | self-contained closure, **IMPORT-OK** (`…vendor__group_columns_build.log`) |
| 4 | Oracle-classifiable per §3.1 | ☑ | grouping indices → bit-exact |
| 5 | Golden 50–500 ms | ☐ PENDING-1.1.5 | rig; no number claimed |

Provisionally admissible (1–4 PASS). β (C-β1): boundscheck/wraparound function-pins (pure-speed), no cdivision.
