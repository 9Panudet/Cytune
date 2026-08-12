# cytune — the development branch

Everything on `main`, plus the machinery that produced it: the harnesses, the release tooling, the
study-equivalence tests, and the deep system documentation.

| branch | what is on it |
|---|---|
| **`main`** | the product, its user docs, and a self-contained `evidence/` |
| **`dev`** | you are here |
| **`research`** | the study: pre-registrations, reports, manifests, and the negative results |

**Start with [`docs/system/00_SUMMARY.md`](docs/system/00_SUMMARY.md).** Three pages: what the
system is, the six stages, the four guarantees, where the numbers come from, and what to look at
when something breaks. Then [`docs/system/12_HISTORY.md`](docs/system/12_HISTORY.md), which is the
defect ledger and the most useful document here for anyone inheriting this.

---

## Working here

```bash
.venv/bin/python -m pytest src/cytune tests -q          # 922 tests, ~70 s
.venv/bin/python scripts/release/fleet_gate.py          # B1 — 149 tables x 9 budgets, ~9 s
.venv/bin/python scripts/release/fleet_gate_controls.py # the gate must be able to fail
bash scripts/release/smoke.sh                           # the live pre-tag ritual, ~6 min
```

`CLAUDE.md` is the working discipline. `docs/CONTRIBUTING.md` has the bar an engine change must
clear. `docs/ARCHITECTURE.md` is on `main` too, because shipped error messages cite it.

## What is here that is not on main

| | |
|---|---|
| `scripts/release/` | the pre-tag gate, the fleet replay gate and its controls, the repeated-dogfood campaign and its analyser, the vendor manifest builder |
| `scripts/doe_v2/` | the offline replay harness: the sealed ask–tell interface, the fleet loader, the engine variants, the controls |
| `scripts/phasep/` | the study harness — and the source `src/cytune/_vendor/` is hash-pinned against |
| `scripts/measure_wrap.sh` | the host rig gate. Deliberately not vendored: vendoring it broke it |
| `tests/` | study-equivalence, and the script-import gate that closes D25 |
| `docs/system/` | fifteen documents explaining the repo as it actually is |
| `logs/defects/` | D3–D26 |

## The four standing gates, and why each exists

| gate | closes |
|---|---|
| **B1** `fleet_gate.py` | nine live anchors are validation, not coverage. D-2 moved 58 of 149 kernels and **0 of 9 anchors** |
| **B2** `_vendor/VENDOR_MANIFEST.json` | the drift check skipped forever on a product-only branch — 12 of 14 items |
| **B3** `lock.py` | two concurrent runs produce wrong numbers with no warning. 626 rows were discarded to exactly that |
| **B4** `paths.py` | four defects of the shape "the unit is tested, the composition models fewer cases than production has" |

Each has a positive control proving it can fail. B1's is the real D-2 defect rather than a planted
one, so it also proves the gate would have caught what the anchors missed.

## Two rules that are not negotiable here

**No multi-agent work and no sustained CPU during a timed phase.** On 2026-07-24 a review workflow
and an abandoned container overlapped a measurement and 626 rows had to be discarded. Config id
order correlates with the `-O1`/`-O3` factor, so a time-correlated slowdown can alias onto a factor
and look like a result.

**A number without a raw pointer and a recompute command does not exist.** Statistics are recomputed
from raw by an independent auditor, never transcribed. `docs/system/11_EVIDENCE.md` carries the
index — including a table of five numbers this project has had to correct, and how each was caught.
