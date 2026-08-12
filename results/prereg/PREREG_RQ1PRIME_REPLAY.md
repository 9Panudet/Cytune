# PREREG — RQ1′ offline-replay: Random Search vs deterministic DOE screening on the measured Δ-probe grids

**Pre-registered BEFORE any replay outcome was computed.** This file fixes the entire analysis
(tables in scope, near-optimum rule, both protocols, the paired test, the flat-unit rule, and the
pre-committed interpretation of *either* outcome). The frozen protocol is
`scripts/corpus/rq1prime_replay.py` (committed in the same commit as this file). Only the per-unit **τ
inputs** (measurement-noise parameters) and the **fixed DOE screen set** appear below — **no RS/DOE
outcome, no near-optimum set size, no winner** is stated here. Outcomes are computed and committed
*after* this commit; git timestamps make the order provable.

## Classification (scope guard)
- This is a **document-revision-class pre-registered *addendum*** — a **secondary analysis on already-measured
  data**. It is **NOT** the roadmap's RQ1: no BO surrogate is built, no new corpus is added, no new flag
  space is opened, no new timing is run. It therefore **does NOT consume the §1.3.3 / B-12 extended-flag
  amendment** and does not alter any hard gate.
- New epistemic label introduced: **MEASURED-REPLAY** = *computed on the measured endpoint tables;
  grid-scoped*. Conclusions hold **only on the measured grids (16-config Δ-probe / 12-config strict
  factorial)**, **NOT** on full Θ = 1728. The full-Θ BO≤RS statement remains **INFERRED** (report §7).
- If any new timing run ever becomes necessary (none is expected — this is pure computation on committed
  raw), it must go through the full v1.4 rig + `measure_wrap.sh` + CF-1..CF-5. This analysis performs **no
  new timing**.

## (a) Measured tables in scope
- **Primary (paired test):** each unit's **16-config endpoint Δ-probe grid** — all **9** surviving units.
  Raw: `results/characterization/delta_probe/<unit>__endpoint.json` (each carries all 16 `configs` with
  `median_ns` + `subproc_medians_ns`). Grid = full 2⁴ factorial over **CHK** (boundscheck+wraparound+
  initializedcheck+nonecheck toggled together; S=on / U=off), **DIV** (cdivision; P=False / C=True), **OPT**
  (P-bundle L = `-O1 -march=x86-64` / H = `-O3 -march=native -funroll-loops`), **FP** (T=strict / A=fast-math).
- **Secondary (descriptive corroboration, NOT in the paired test):** csr & elkan **12-config strict
  factorials** (2 boundscheck × 3 opt_level × 2 march, FP=strict). Raw:
  `results/characterization/separability/<unit>__separability.json`.

## (b) Near-optimum definition — τ fixed per unit from committed raw
A config *c* is **near-optimum** iff `median_ns(c) ≤ t_best · (1 + τ_unit)`, where `t_best` = the grid
minimum median. **K** = size of the near-optimum set.

`τ_unit = max( endpoint_CI_unit , 0.02 )`, where `endpoint_CI_unit` = the **median over the grid's configs
of each config's relative subprocess range** `(max − min)/median` of that config's 3 subprocess medians (a
from-raw measured noise floor). Conservative floor 2% dominates because the rig is tight.

**Per-unit τ INPUTS (from committed raw, `rq1prime_replay.py --emit-tau`):**

| module | unit | endpoint_CI | τ (used) | floor governs |
|---|---|---|---|---|
| _k_means_elkan | elkan_iter_chunked_dense | 0.00693 | **0.02000** | yes |
| sparsefuncs_fast | csr_mean_variance_axis0 | 0.00892 | **0.02000** | yes |
| _binning | _map_to_bins | 0.00316 | **0.02000** | yes |
| _predictor | _predict_from_raw_data | 0.01260 | **0.02000** | yes |
| _shortest_path | floyd_warshall | 0.00956 | **0.02000** | yes |
| _online_lda_fast | _dirichlet_expectation_2d | 0.00533 | **0.02000** | yes |
| _traversal | connected_components | 0.00268 | **0.02000** | yes |
| _isotonic | _inplace_contiguous_isotonic_regression | 0.00202 | **0.02000** | yes |
| _ppoly | ppoly_evaluate | 0.00168 | **0.02000** | yes |

Every measured CI < 1.3% ⇒ τ = 2% for all 9 units. τ is **fixed here**; **no τ tuning after outcomes**.

## (c) RS protocol
Uniform sampling **without replacement** over the unit's grid (N configs). Metric =
**evals-to-first-near-optimum**. Expected value computed **EXACTLY** as the first-success position under
sampling without replacement: **E[evals] = (N + 1)/(K + 1)**. Plus a **10,000-seed Monte-Carlo check**
(seed 20260706) reproducing E and the distribution.

## (d) DOE protocol (fixed)
Balanced **main-effects screening → additive predicted-best → +1 confirmation**. For the 2⁴ grid the screen
is the **resolution-IV 8-run half fraction** with defining relation **I = CHK·DIV·OPT·FP** (main effects
clear of 2-factor interactions; the minimal *orthogonal/balanced* main-effect design for 4 two-level
factors — smaller orthogonal designs do not exist for 4 factors). **Fixed screen set (8 of 16):**
`{SPLT, SPHA, SCLA, SCHT, UPLA, UPHT, UCLT, UCHA}`. From the 8 screen runtimes, each factor's main effect =
`mean(+) − mean(−)`; the predicted-best config takes the faster level of each factor. Then **1 confirmation
eval** at the predicted-best. **DOE cost = 8 + 1 = 9 evals** (primary). **Pre-registered sensitivity:**
DOE cost = 8 (no separate confirmation, when the predicted-best already lies in the screen). DOE **succeeds**
iff the predicted-best config ∈ the near-optimum set.

For the secondary 12-config factorial the DOE screen is the **full 12-run factorial itself** (this is
exactly what `motifbo characterize` / the §5 separability decomposition does) → additive predicted-best
(best boundscheck × best opt_level × best march) → confirmation; reported descriptively only.

## (e) Per-unit paired metric + across-units summary
- Per non-flat unit: pair **(RS_expected_evals, DOE_cost)**. If DOE fails to reach near-opt within its fixed
  protocol, RS wins that unit (RS is guaranteed to reach near-opt in ≤ N draws; DOE has no more evals).
- Across the non-flat units: **paired sign test** (primary) and **Wilcoxon signed-rank** (secondary) on the
  per-unit winner / (RS_E − DOE_cost), **α = 0.05, two-sided**.
- If the number of non-flat units is small (expected), the paired test may be **underpowered for
  significance** — this is pre-registered as an *informative* outcome (few non-trivial units ⇒ evidence of
  flatness), reported honestly with the direction and the n.

## (f) Flat-unit rule
A unit whose near-optimum set covers **≥ half the grid (K ≥ N/2)** is a **flatness certificate**: both
methods trivially succeed (near-opt on essentially the first eval). Such units are **excluded from the
paired test** and reported **descriptively** ("no method needed"). This is fixed here; **no unit exclusion
beyond this rule** after outcomes are seen.

## Pre-committed interpretation (BOTH directions are valid results — fixed before computation)
- **RS ties or wins on the dense measured grids** → measured-trajectory evidence that **RS is genuinely hard
  to beat** on these landscapes; this **strengthens report §7 with data** (not only inference) — a
  structure-exploiting screen's fixed overhead is not repaid on a small, flat/separable grid.
- **DOE wins** → measured evidence that **structure-exploitation pays even on small grids**, which would
  *qualify* the INFERRED BO≤RS (a model-based sequential optimizer could add value on the measured grids).

## Locked rules (deviations, if any, recorded prominently in the output + resultNew.md)
1. No protocol change, no τ change, no unit exclusion beyond rule (f), after any outcome is seen.
2. The outcome is reported **whichever way it lands**; neither forced nor softened.
3. Every replay number traces to committed raw + this frozen script + the stats-auditor's zero-diff recompute.
4. MEASURED-REPLAY is **grid-scoped** and is **never** presented as a full-Θ result.
