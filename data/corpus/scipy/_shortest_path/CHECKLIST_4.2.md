# §4.2 checklist — `scipy.sparse.csgraph._shortest_path`

| # | criterion | verdict | evidence |
|---|---|---|---|
| 1 | Non-templated `.pyx` | ☑ | `.pyx`, sha256 == sdist `095a87a0…` |
| 2 | Stable upstream (not `scipy.special`) | ☑ | `scipy.sparse.csgraph` |
| 3 | Isolatable hot loop, public-API inputs | ☑ | closure (+`parameters.pxi`) **IMPORT-OK** (`…vendor__shortest_path_build.log`) |
| 4 | Oracle-classifiable per §3.1 | ☑ | predecessors → bit-exact; distances → tolerance (§4.3). Bellman–Ford = CF-2 low-Δ watch-list |
| 5 | Golden 50–500 ms | ☐ PENDING-1.1.5 | rig; no number claimed |

Provisionally admissible (1–4 PASS). β (C-β1): `boundscheck` function-pins ×8 (pure-speed), no cdivision.
See `MANIFEST.md` (subagent-authored). CF-2: Bellman–Ford is sequential/low-Δ — downward median-Δ pressure.
