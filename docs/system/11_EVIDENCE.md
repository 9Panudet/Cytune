# Evidence — every published number, its conditions, and how to recompute it

**The rule this project runs on: a number without a raw pointer and a recompute command does not
exist.** This file is the index.

## The flagship: regret against known optima

| statistic | value | conditions |
|---|---|---|
| median regret | **1.409 %**, range 1.409–1.719 % | 9 real-code kernels, 5 runs, one quiesced machine, FP-strict |
| worst kernel | **5.412 %**, range 5.412–9.791 % | same |
| configurations measured | 313 per pass, identical in every replicate | ~35 per kernel of 1,728 |

Raw: `results/release/dogfood_repeat/` · summarised: `evidence/repeated_dogfood.json` (main branch).
Recompute: `scripts/release/run_repeat.py` then `scripts/release/analyse_repeat.py`.

**Regret is measured against a KNOWN optimum.** All 1,728 configurations were measured exhaustively
for each of these kernels, so this is not an estimate.

**Regret is discrete.** It changes only when the search emits a different configuration. Five of
nine kernels emitted the same configuration in all five runs; the dispersion is concentrated in two.
This is why the per-anchor **emitted-config multiset** is reported beside the range.

## The instrument's own reproducibility

| statistic | value |
|---|---|
| worst per-anchor spread, `S` | **6.711 pp** |
| median per-anchor spread | 0.000 pp |
| fleet-median spread, `S_fleet` | 0.310 pp |
| **`B_anchor` = max(S, 1.0)** | **6.711 pp** |

The previous per-anchor ship bound was **1.0 pp** — 6.7× tighter than the instrument it judged
changes with. Which side of it a variant landed on was decided by which configuration the search
happened to land on. Pre-registration: `results/prereg/PREREG_LAUNCH.md` §3.

## The fleet gate

149 frozen tables × 9 budgets, offline, ~9 s. Baseline:
`scripts/release/FLEET_GATE_BASELINE.json`. Recompute: `scripts/release/fleet_gate.py`.

Controls (`fleet_gate_controls.py`): the unmodified engine reproduces its baseline with **zero
diff**; D-2 reintroduced produces **106 findings**, of which **0 are on a real-code anchor**. That
second number is the measured form of *nine anchors are validation, not coverage*.

## The study

| finding | where |
|---|---|
| DOE beats BO in 18 of 20 cells; BO is worse than random search on flat landscapes | `results/PHASEP_REPORT.md` (research) |
| Motif+BO passes its gate (p=3.46e-17, δ=0.772) and is **not shipped** — 9.7× sibling enrichment | same |
| routing adds nothing on held-out kernels (RQ-P2) | same |
| INT does not occur in real code (0 of 9 anchors), while the generator produced 42 | same |
| 1,296 cells recorded feasible while reading out of bounds (D23) | `logs/defects/D23.md` |
| all six DOE-v2 Tier-1 variants fail on real code | `results/release/DOE_V2_REPORT.md` |
| `--probe-as-screen`: better median, worse tail, 0 anchors affected | `results/release/LAUNCH_REPORT.md` |

## Numbers this project has had to correct

Listed because the correction record is itself evidence about the process.

| was | is | how it was caught |
|---|---|---|
| the DOE-v2 report's C6 control agreed 7/9 | **6/9**; one anchor off by 3.60 pp | an independent audit found it validated against the wrong baseline |
| a W2 variant row: 0.99 %, 24 configs | **0.84 %, 32 configs** — same cost as V0 | stale, from a run whose bug had been fixed and not re-run |
| "wins at every budget" | **false** — 4-better/5-worse at B=32 | the same audit |
| the ">10 % / B_02" rule cited as pre-registered | it was a **decision-memo string** governing nothing | `stats-auditor`, verdict FAIL (D22) |
| a 1.0 pp per-anchor ship bound | **6.711 pp**, from measurement | the repeated campaign this file documents |

All five made a conclusion weaker. That is the expected direction when the checking is real.

## The standing rules behind all of it

* Raw measurements are committed **before** any aggregate is quoted.
* Statistics are recomputed from raw by an independent auditor, never transcribed.
* Worst case, not representative; count before "all"; partials stated as partials.
* New instruments get **positive and negative controls** before their readings count.
* **Favourable surprises are alarms.** The two largest findings in this project's history — D23 and
  D25 — both began with someone asking why something looked better than it should.
