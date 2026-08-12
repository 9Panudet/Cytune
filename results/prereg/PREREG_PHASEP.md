# PREREG_PHASEP.md — Phase-P pre-registration register (v1, P0.3)

**Status:** NORMATIVE. Committed before any Phase-P kernel is measured (roadmap §0.3-3).
Governs: class thresholds, sample sizes, metrics, tests, budgets, seeds, measurement tiers,
golden-scale policy, suspicious-config rule, DOE design, BO fixtures, Motif transfer protocol,
probe set, instrument controls, holdout selection, tie-breaking, compute envelope, amendments.
Any change **after this file is committed** is a **numbered, human-approved amendment** appended
to §12 — never silent (roadmap §6). The single permitted P-1 recalibration (§1.6; roadmap §3.4 /
P1.3) is itself pre-registered here. This file was adversarially reviewed (4-lens panel,
wf_14518dee-4f5) **before its first commit**; the revisions folded from that review are logged in
§13 and are part of the committed v1 (they are not §12 amendments — the amendment bar applies only
post-commit).

Spec: `PRODUCT_ROADMAP.md` (v2.0). v1 citations resolve at `git show v1-final:Motif+BO-Roadmap.md`.
Date: 2026-07-08. Hardware: i3-10100F (4C/8T), 16 GB, container image X′ `motifbo-env:phase1`
(`d45e33b0…`, `data/env/IMAGE_DIGEST`). Rig constants: `data/env/MEASUREMENT_CONSTANTS.json`
(K_final=30, warmup=5, K_search ∈ [5,10], thermal/throttle discard rules) — unchanged from v1
**except** `bootstrap.seed` (see §0.4).

---

## §0 Objects, factor coding, seeds, neighborhood (all normative)

### §0.1 The 9-dimensional factor space (composite fast-math/contraction dimension)
Θ (roadmap Appendix A, |Θ| = 1,728) is coded as **9 factors** by merging the conditional
`fast_math`×`ffp_contract` pair into one **3-level composite factor** `fmffp`:

| # | factor | levels (canonical order) |
|---|---|---|
| 1 | boundscheck | True, False |
| 2 | wraparound | True, False |
| 3 | cdivision | True, False |
| 4 | initializedcheck | True, False |
| 5 | nonecheck | True, False |
| 6 | opt_level | -O1, -O2, -O3 |
| 7 | march | x86-64, native |
| 8 | funroll | omit, on, off |
| 9 | fmffp | (fast_math=off, ffp_contract=off), (off, fast), (on, NA) |

`fmffp` has exactly 3 levels and reproduces the 54 GCC combinations: 3(opt)·2(march)·3(funroll)·
3(fmffp) = 54; with 2⁵ = 32 directive combos ⇒ |Θ| = 1,728 (self-checked at P1.0). This coding is
**full rank**: the v1 "NA is its own level" coding made `ffp_contract=NA` perfectly collinear with
`fast_math=on` (rank-deficient; det(X'X)≡0 — it made every OLS non-unique and every D-optimal design
unconstructible). The composite dimension removes that collinearity by construction.
- **config_id** = the canonical lexicographic index of roadmap Appendix A (unchanged; the |Θ|=1,728
  enumeration and its self-check ship at P1.0 as the sole source of config_ids). The mapping
  config_id ↔ (9-factor tuple) is bijective and committed with that script.
- **Main-effects design matrix X** (used identically for IF classification §1.1, DOE §8.2, probe
  §9.2): intercept + drop-first one-hot over the 9 factors = 1 + (1+1+1+1+1+2+1+2+2) = **13
  parameters**, full column rank on any design that exercises every level of every factor.

### §0.2 Reference config and core scalars
- **Reference config** (= golden config, one point of Θ): as-shipped Cython directives (all five at
  Cython defaults — boundscheck True, wraparound True, cdivision False, initializedcheck True,
  nonecheck False), `-O2`, `march=x86-64`, `funroll=omit`, `fmffp=(off,off)` (i.e.
  `-ffp-contract=off`) (roadmap §0.4). It is the build that produces the golden output and the
  product's fallback. Its funroll level is `omit` (no `-funroll-loops`/`-fno-unroll-loops` passed).
- Screen median **m(c)** — the screening-tier median runtime of config c (§4). **Feasible** — the
  row's feasibility bit (§5). **F** = the feasible set. **t\*** = min_{c∈F} m(c) (true feasible
  optimum). **t_ref** = m(reference config). **τ = 0.02** — the near-optimum tolerance (used
  identically for evals-to-τ, local-optimum prominence, and the product's "flat" wording).
- **log-runtime** = natural log of m(c) in ns (all variance decompositions and BO modeling act on
  log-runtime; multiplicative noise, v1 §2.2).

### §0.3 1-flip neighborhood (symmetric by construction)
N(c) = all configs differing from c in **exactly one of the 9 factors** of §0.1, that factor taking
any of its other levels. Because `fmffp` is a single 3-level dimension, `(on,NA)` has **both**
`(off,off)` and `(off,fast)` as neighbors and the relation is symmetric (the v1 asymmetry — where
flipping fast_math re-mapped ffp_contract with no inverse — is gone). |N(c)| = (2−1)·5 +
(3−1)+(2−1)+(3−1)+(3−1) = 5 + 7 = 12 for every c. N(c) is used by the greedy hill-climb (§1.1-3),
the τ-prominent local-optimum count (§1.1-4), and the suspicious-config M_N (§7).

### §0.4 Seeds (fully executable)
- Every random operation derives from **base seed 20260708** via
  `numpy.random.SeedSequence(entropy=[20260708, k1, k2, …])`, where each spawn-key element kᵢ is an
  integer obtained as follows (the **only** permitted encoding): an integer element is used as-is;
  a **string** element s is replaced by `fnv1a64(s.encode('utf-8'))` (64-bit FNV-1a, offset basis
  14695981039346656037, prime 1099511628211); a kernel_id is the string encoding of its stable id.
  Worked fixtures committed at P1.0 in `results/prereg/seed_fixtures.json` (e.g.
  `fnv1a64("screen") = 10080399746057843313` — the exact value is emitted and committed by the seed
  module; the auditor recomputes it). `pair` keys = `10·min(a,b)+max(a,b)` over the two alg_ids; `class`
  keys = A→1, B→2, C→3; `budget` keys = the literal budget integer.
- **Shorthand:** a spawn key written `['k1', k2, …]` anywhere in this file denotes
  `numpy.random.SeedSequence(entropy=[20260708, enc('k1'), enc(k2), …])` with the base seed always
  prepended and `enc` the encoding above (strings→fnv1a64, integers as-is). Distinct keys ⇒
  independent streams even when they share an integer element (e.g. seed_i appears in both
  `['bo-init', …]` and `['bo-rf', …]`).
- **alg_id:** RS→1, DOE→2, BO→3, Motif+BO→4.
- **Bootstrap seed precedence:** for Phase P the SeedSequence scheme above **supersedes**
  `MEASUREMENT_CONSTANTS.json`'s `bootstrap.seed` field (12648430); all its other fields remain
  binding. The constants file is annotated at P1.0 with this carve-out (recorded, not silent).
- No entropy source other than the base seed is permitted anywhere in Phase P.

## §1 Class thresholds — MEASURED assignment (roadmap §3.4 / Appendix B, operationalized)

Assignment happens once per kernel, at P2.2 (fleet) from the kernel's own frozen full table, by
`classify_kernel()` (committed at P1.0, unit-tested on synthetic fixtures including the degenerate
cases in §1.5):

1. **Interaction fraction IF** = 1 − R², where R² is from the least-squares fit of log(m(c)) on the
   §0.1 main-effects design X, over all feasible rows. **Degenerate-fit rules (normative):**
   columns that are constant over the feasible rows are dropped before fitting (the dropped set is
   recorded per kernel); the remaining system is solved by minimum-norm least squares
   (`numpy.linalg.lstsq`, rcond=1e-12) so R² is unique even under residual rank deficiency; if
   SS_tot = 0 (all feasible medians identical) then IF ≝ 0. R² = 1 − SS_res/SS_tot.
2. **Δ_all** = t_ref / t\*. **Δ_strict** = t_ref / min m(c) over feasible configs with
   `fmffp=(off,off)` or `(off,fast)` (the bit-preserving axis: fast_math=off; v1 semantics
   preserved). [Δ_strict is reported alongside Δ_all everywhere but is not a class-threshold input.]
3. **Greedy gap:** best-improvement 1-flip hill-climb from the reference config over feasible rows:
   at each step move to the feasible neighbor n∈N(current) with the smallest m; stop when no
   feasible neighbor has m strictly < current m; gap = m(end)/t\* − 1. Infeasible neighbors skipped.
   Deterministic (ties inside a step: lowest config_id). If the reference config is infeasible the
   kernel is dropped (§1.7).
4. **τ-prominent local optimum:** a feasible c with m(c) < (1 − τ)·m(n) for **every** feasible
   n ∈ N(c) (strictly better than all feasible neighbors by more than τ = 2%). The prominence
   requirement is the degeneracy guard: on a flat table no config beats all neighbors by 2%.
5. **Class rules (Appendix B v2, Amendment A-1b — IF Δ-floor):** IF is computed/evaluated ONLY when
   Δ_all ≥ **1.10** (5× the 2% noise floor); below it IF = 1−R² degenerates to noise/noise and is
   meaningless, so a sub-1.10-Δ kernel is class A directly (flat-by-Δ). This is a correctness fix to
   the estimator, not a loosening of A (recorded amendment §12 A-1b).
   - **A ⇔ Δ_all < 1.10  OR  IF < 0.10**
   - B ⇔ IF ≥ 0.25 AND Δ_all ≥ 1.5   (Δ ≥ 1.5 already clears the 1.10 IF-floor)
   - C ⇔ greedy gap ≥ 0.15 OR (≥ 2 τ-prominent local optima AND ≥ 1 of them has m ≥ 1.15·t\*)
   - matching zero or ≥ 2 of {A, B, C} → **boundary set** (reported, excluded from per-class tests,
     usable descriptively per §3.4).
6. **Anticipated B∩C collision, declared now:** genuinely rugged kernels may satisfy B and C and
   land in the boundary set. If the pilot confusion table shows this drains a class, the **single
   permitted P-1 amendment** (roadmap §3.4) may introduce a precedence rule (expected candidate:
   C ≻ B). Decided by the human at P-1; never applied without re-running assignment for **all**
   kernels uniformly.
7. Eligibility floor: a kernel with < 32 feasible configs, or an infeasible reference config, is
   dropped to the survival ledger (reason `table_degenerate` / `reference_infeasible`) and never
   classified. Such a drop **is** an attrition event and draws a spare (§2).

## §2 Sample sizes, attrition, top-up (derived, mandatory)

- Normative power source: `results/power/power_table.json` + `power_table_extended.json`
  (stats-auditor zero-diff; MC N=10,000/60,000; **one-sided** paired Cliff's-δ Wilcoxon model —
  see §3.3 for the sidedness reconciliation): power ≥ 0.8 requires **n = 12 (δ=0.6), 26 (δ=0.4),
  103 (δ=0.2)**.
- Pre-registered per-class MDE: **δ = 0.4** ⇒ n = 26; fleet target **30/class** = 26 + attrition
  margin. Pooled n = 90 sits between the δ=0.4 (26) and δ=0.2 (103) thresholds ⇒ pooled analyses
  are powered for δ ≈ 0.25–0.3 (stated as an interpolation, not an exact threshold). **Power caveat
  (binding):** the n = 26 figure is for a *one-sided, uncorrected* test; the RQ-P1 pairwise tests
  are two-sided and Holm-corrected (§3.3), which is strictly less powerful, so 30/class is the
  **floor**, and per-class power is reported as an honest lower-bounded estimate at P-3, not asserted
  at 0.8.
- **Fleet layout per intended class (generation indices, fixed before any measurement):** 1–5
  pilot, 6–35 fleet (30), 36–40 held-out H (5), 41+ spares (generated only on attrition).
- **Attrition events** (the *only* ledger reasons that draw a spare): construction failure,
  determinism-gate failure, oracle/golden failure, `table_degenerate`, `reference_infeasible`,
  `scale_band`. **Boundary-set classification is recorded in the ledger but is NOT an attrition
  event and never draws a spare.** An attrition event draws the lowest unused spare index for that
  intended class; the draw is recorded.
- **Mandatory, bounded top-up:** if a *measured* class's membership among fleet indices (6–35 +
  drawn spares) is < 26, pilot kernels **of the same measured class** are added in ascending pilot
  index until the class reaches exactly 26 **or** the pilots of that class are exhausted; no top-up
  otherwise. Whenever top-up fires, a **mandatory sensitivity re-run** of every per-class test for
  that class is reported with the topped-up pilots excluded (guards the mild double-dip against the
  P-1 threshold recalibration, which sees the pilot tables). Pilot kernels are otherwise not in the
  inference set.
- **Dataset R:** the 9 v1 endpoint-measured survivor kernels, extended to full 1,728 tables. R and
  H are excluded from P3 entirely; they are the P4 acceptance set. If any class lands < 26 after
  attrition + top-up, the §3.1 power consequence is presented at P-2 before P3 starts.

## §3 Study metrics, budgets, seeds, tests (RQ-P1, RQ-P3, RQ-P2)

### 3.1 Replay semantics (sealed; identical for all four algorithms)
- Replay landscape of a kernel = its frozen screening table: `query(config_id) → (feasible,
  m(c) if feasible else None, reason)`. Nothing else is accessible (conformance cheat-test §9.3).
- **Budget accounting (uniform across all four arms):** the **reference config is observation 0**,
  provided free at t=0 (config, feasible bit, m) — knowledge the product always has from golden
  capture — and it **counts as already-queried** for both budget memoization and warm-start/init
  dedup. Every *distinct* config queried thereafter consumes 1 unit of B (feasible or not);
  re-querying any already-queried config (including the reference) is free.
- **best_found(B)** = min(t_ref, min m over feasible configs queried within budget B). The t_ref
  floor mirrors the product guarantee (§8.2: emit reference when nothing better is found) and keeps
  regret defined even if all B queries are infeasible.
- **Primary metric: regret@B** = best_found(B)/t\* − 1, at **B ∈ {8, 16, 32, 64, 128}**.
  **Sensitivity column (descriptive):** regret_nofloor@B computed **without** the t_ref floor
  (best_found = min m over feasible queried, or +∞→reported as censored if none), reported alongside
  so the compression the floor induces on class-B kernels is visible. Tests run on the primary
  (floored) metric only.
- **Secondary (descriptive only, no hypothesis tests): evals-to-τ** = index of the first query
  (the free reference observation is index 0) whose feasible m ≤ (1+τ)·t\*; right-censored at 128
  (reported ">128"; medians use "≥ 129" and are flagged when censored).

### 3.2 Seeds
- **200 seeds** per (algorithm × kernel) for RS, BO, Motif+BO: seed_i =
  `SeedSequence([20260708, hash_k, alg_id, i])` for i ∈ {0..199}, hash_k per §0.4.
- **DOE is deterministic** (one trajectory per kernel×budget); its per-kernel "mean over seeds" is
  that single trajectory's value. Declared so the seed asymmetry is a recorded design property.
- Per-kernel summary for testing = **mean regret over seeds** at each (algorithm, budget).

### 3.3 Hypothesis tests (RQ-P1)
- Family = one (class × budget) cell: 3 classes × 5 budgets = 15 families.
- **Complete-block rule:** a kernel lacking a Motif+BO result (extractor hard-fail, §8.4) is
  excluded from the 4-algorithm Friedman and from any pairwise test **involving Motif+BO** in its
  family (n reduced, the excluded count reported); pairwise tests among {RS, DOE, BO} still use the
  full class. This is fixed now to forbid an ad-hoc incomplete-block choice.
- Within a family: **Friedman test** across the available algorithms on per-kernel mean regrets.
  Pairwise comparisons run **only if** Friedman p < 0.05: all pairwise **paired Wilcoxon
  signed-rank** tests, **alternative = 'two-sided'**, `zero_method='pratt'`, method = **exact iff
  n ≤ 25 AND there are no zero differences AND no tied absolute differences, else the normal
  approximation** (matches the pinned scipy's auto behavior deterministically), **Holm-corrected
  within the family**, α = 0.05.
- Effect sizes for every pair (reported regardless of significance): **paired Cliff's δ** defined
  as **δ = (#{i: dᵢ < 0} − #{i: dᵢ > 0}) / n** over per-kernel mean-regret differences
  dᵢ = regret(A)ᵢ − regret(B)ᵢ (zero differences count in n and contribute 0; **the same formula is
  used in §3.4's Motif gate**), oriented so δ > 0 means the first-named algorithm has lower regret;
  plus **BCa bootstrap 95% CI** (10,000 resamples, seed key `['bca', class, budget, pair]`) on the
  mean paired difference. If all dᵢ are equal the CI is the degenerate point interval [d, d],
  flagged.
- **Routing-matrix cell (class × budget):** names the algorithm with the lowest **median** per-
  kernel mean regret; ties in that median broken by lower **mean** of per-kernel mean regret, then
  by fixed order RS < DOE < BO < Motif+BO (tie-break firing is recorded). The cell is **DECISIVE**
  iff that algorithm is two-sided-significantly better (lower) than every other available algorithm
  in the family's Holm-corrected pairwise tests; else **TIED** (with the tied set). Honest ties are
  expected and reportable (roadmap §0.3-7).
- Time is the only tested objective; memory / .so size / compile time are characterized
  descriptively (roadmap §4.2) — declared to foreclose multiplicity games.

### 3.4 RQ-P3 (Motif transfer) decision rule
- **Analysis set (exact):** all fleet-index kernels (6–35 + drawn spares + any topped-up pilots)
  with a **non-boundary** measured class **and** a Motif+BO arm result; H and R excluded. Boundary
  kernels are excluded (RQ-P3 is a pooled product decision; boundary kernels are descriptive-only).
- Endpoint: paired (Motif+BO − BO) per-kernel mean regret at **B ∈ {8, 16}** only, LOKO (§8),
  pooled over classes (per-class shown descriptively).
- Motif enters the product **iff** at either budget: Holm-corrected (2 tests) paired Wilcoxon
  **alternative = 'less'** (Motif+BO regret < BO regret; matches the one-sided power model)
  p < 0.05 **AND** paired Cliff's δ ≥ 0.2 in Motif's favor (δ per §3.3 with dᵢ = regret(Motif) −
  regret(BO), so δ = (#{dᵢ<0} − #{dᵢ>0})/n ≥ 0.2). Anything else ⇒ Motif is dropped from the
  product and the negative ships (roadmap §5.5).
- If the extractor fails on ≥ 20% of the fleet, RQ-P3 is reported NOT EVALUABLE (with the failure
  ledger) rather than on the surviving subset (roadmap §5.5 / §8.4).

### 3.5 RQ-P2 (router efficacy) — evaluated at P4 on H + R only
- Per held-out kernel: probe (§9.2, replayed on its frozen table) → class guess → routed algorithm
  per the P-3 routing matrix at the class-default budget (fixed at P-3 by the human's routing
  decision) → routed regret. **All comparators are evaluated at the routed (guessed-class) budget**
  so "same kernels/budgets" is always satisfiable.
- Comparators: (a) oracle routing = the matrix applied to the kernel's **measured** class; (b) each
  fixed single algorithm at that budget.
- **Undefined-branch rules (fixed now):** a holdout whose measured class is boundary, or whose probe
  is degenerate (< 2 feasible probe rows, or Δ̂_probe undefined), routes to **class A** (the product's
  conservative default) for both the routed guess and, if its measured class is boundary, the oracle
  route; such kernels are flagged and counted.
- **Success criteria (both required):** mean routed regret ≤ 1.1 × mean oracle-routed regret, AND
  mean routed regret ≤ min over fixed algorithms of their mean regret (roadmap §0.2 verbatim; the
  margin is reported). n(H+R) ≈ 24 < 26 ⇒ formally underpowered at δ = 0.4; RQ-P2 is reported with
  CIs and this caveat, as acceptance evidence, not a powered hypothesis test.

## §4 Measurement tiers (roadmap §4.1; v1 constants)

- **Screening tier (all 1,728 configs/kernel):** 1 fresh subprocess per config; **warmup = 5**
  in-process iterations (untimed) then in-process K adaptive ∈ [5, 10] with early stop when the
  bootstrap 95% CI half-width of the median ≤ 2% of the median (v1 §1.5-4; bootstrap B=10,000, seed
  key `['screen', kernel_id, config_id]`); row records median_ns, ci_halfwidth, K. Timing =
  `perf_counter_ns` immediately around the kernel call only; input construction untimed; per-rep
  input regeneration for in-place kernels (v1.4 / D6); no bare imports timed (D2).
- **Endpoint tier:** median over N = 3 fresh subprocesses of the within-subprocess K = 30 median
  (v1.3/v1.4), for (a) the **top decile by screen median among feasible configs** (⌈|F|/10⌉ configs)
  of every kernel, and (b) **every algorithm-selected winner** during P4 verification. Never
  adaptive. **Endpoint re-measure policy (Phase-P pin, replaces v1's threshold_x knobs which were
  never numerically pinned):** if the between-subprocess rstd of the 3 medians > **0.05**, add one
  fresh subprocess at a time up to **2** additional (N ≤ 5 total) and report the median of all
  collected; record `remeasured_endpoint` count. This is the sole permitted endpoint re-measure and
  is explicitly carved out of §7's prohibition.
- **Screen-vs-endpoint agreement (standing D5 guard), per kernel:** Kendall τ_b between screen
  medians and endpoint values over the top-decile set, plus the binary check that the screen-argmin
  config's endpoint value is within τ of the endpoint-argmin config's. **Consequence, pre-registered
  at both stages:** a kernel failing the binary check is flagged `agreement_fail`; at **P-1** it
  triggers the pilot scale discussion; at **P-2/fleet** it is **excluded from per-class inference
  (moved to descriptive-only)** and the count is presented at the P-2 STOP (so the human approves a
  rule, not a case-by-case call).
- **CF-1 phase split:** per kernel, strictly build phase → measure phase → endpoint phase; no
  compilation during any measured run; measurement on the isolated core under
  `scripts/measure_wrap.sh` (CF-4 asserts: no_turbo, governor, cpu3+SMT isolation, THP — fail-loud).
  Thermal/throttle discard rules per MEASUREMENT_CONSTANTS.json.
- **Multi-objective capture per config (same runs, no extra measurement):** **peak RSS = the
  measurement child's own `getrusage(RUSAGE_SELF).ru_maxrss` (KB) reported by the child at exit**
  (never the parent's `RUSAGE_CHILDREN`, which is a running max over all reaped children and would
  corrupt per-config attribution); .so size (stat); compile wall seconds (gcc; cythonize wall logged
  once per directive combo). Table schema = roadmap §4.4.

## §5 Correctness / feasibility (absolute; roadmap §0.3-1)

- Oracle mechanism = v1 §3.1 unchanged: per-kernel `oracle.json` frozen before any search; bit-exact
  classes for integer/index/exception outputs (exception identity by canonical type); toleranced
  classes for float outputs with tolerance = max(10 × observed cross-repetition deviation under the
  reference config, domain floor). **Synthetic-fleet domain floors:** rtol 1e-9, atol 1e-12 (float64
  outputs; the generator emits only float64/int64/bool arrays and scalars). NaN compares equal to
  NaN in toleranced classes; ±0 distinguished only in bit-exact classes.
- Oracle runs **inline with every screening run**; the row records feasible ∈ {0,1} + reason ∈
  {cythonize_fail, build_fail, sanitizer, oracle_mismatch, crash, timeout}. Timeout = max(10 × golden
  reference runtime, 10 s) wall per subprocess.
- β policy: in-source directive pins stripped; cythonize failure ⇒ feasibility-0 for the whole
  directive combo, cached once, never retried per flag (roadmap §0.4).
- Sanitizer policy = v1 §3.3: ASan+UBSan per **safety class** (6-dim key: boundscheck, wraparound,
  initializedcheck, nonecheck, cdivision, fast_math ⇒ ≤ 64 classes/kernel), `detect_leaks=0`; every
  reported endpoint winner additionally gets a full-config sanitizer run; class/endpoint mismatch ⇒
  defect + strict per-config fallback for that kernel. **Phase-P `detect_leaks=1` leak audit (roadmap
  §1.4, restored):** one leak-audit run per kernel on the reference build, plus one per P4 endpoint
  winner; a detected leak ⇒ defect (debug-mantra) and the config is feasibility-gated on the leak.
  Synthetic kernels are C-Cython; CF-5 (C++ obligations) applies only if a C++ kernel ever enters.
- Fast-math configs are feasibility-gated on the toleranced comparison exactly as in v1; the
  Δ_strict axis (§1.2) is always reported alongside Δ_all.

## §6 Golden-scale policy (roadmap §4.5)

- Target band **50–80 ms** golden runtime under the reference config; **construction acceptance band
  [50, 100] ms** — the lower edge stays at the mandated 50 ms (below 50 ms is the worst slow-outlier
  regime, v1 CF-4); the upper edge is relaxed to 100 ms to absorb integer-knob granularity (a
  **recorded deviation** on the upper edge only, §12-D1; higher runtime is noise-favorable). Aim
  mid-band (50–80 ms) via the integer scale knob; the knob value is in spec.json and frozen with the
  kernel.
- A kernel that cannot enter [50, 100] ms at any knob value ⇒ survival ledger, reason `scale_band`
  (attrition, draws a spare).
- **Dataset R re-scale:** R kernels are re-scaled into the same band via their v1 driver scale knobs;
  fresh goldens + oracles are derived at the new scale under v1 §3.1 (v1 oracles at v1 scales are not
  reused). R tables are otherwise produced by the identical pipeline.
- Known cost, priced by the pilot: v1 CF-4 measured a ~3.6% slow-outlier subprocess population at
  ~74 ms that vanishes at ~500 ms. Mitigations (binding): 2%-CI screening tolerance, endpoint tier
  for all decisions, the §7 suspicious-config rule, and the per-kernel screen-vs-endpoint agreement
  stat.

## §7 Suspicious-config re-measure rule (pre-registered, single-pass, mechanical)

1. After a kernel's screening phase completes and **before its table freezes**: suspicion is computed
   **in a single simultaneous pass using only the as-completed (original) screening medians** for
   both m(c) and the neighbor median M_N(c) (replacements never feed back into M_N — the fixed point
   is fully determined). For each feasible c with ≥ 3 feasible 1-flip neighbors, M_N(c) = median of
   m(n) over feasible n∈N(c); c is *suspicious* iff m(c) > 3·M_N(c) or m(c) < M_N(c)/3.
2. Each suspicious config is re-run **once** in one fresh screening-tier subprocess.
   - If the re-run is feasible and |new − old|/old ≤ 0.20 ⇒ keep the original m(c) (transient not
     confirmed).
   - If the re-run is feasible and the delta > 0.20 ⇒ the table's m(c) becomes the re-run median,
     row flagged `remeasured=1` (original preserved in raw).
   - If the re-run **fails feasibility** (crash/oracle-mismatch/timeout) ⇒ treated as a transient:
     the original row is kept unchanged, event logged `rerun_failed=1`.
   No further re-rolls. **No other configs may be re-measured for any reason except under this rule
   and the §4 endpoint re-measure policy**, absent a §12 amendment.
3. Counts of suspicious / remeasured / replaced / rerun_failed configs per kernel are reported at
   P-2.

## §8 Algorithm arms (frozen protocols)

### 8.1 RS
Uniform without replacement over Θ per seed (v1 §1.4.1); determinism test: same seed ⇒ same
sequence, different seed ⇒ different sequence (§9.3). The free reference observation (§3.1) counts as
already-queried but does not otherwise alter RS's draw distribution over the remaining Θ.

### 8.2 DOE (budget-adaptive, deterministic; roadmap §5.3)
**Design construction** (kernel-independent; committed as `results/prereg/doe_designs_theta.json` at
**P1.0**, before any measurement, by `scripts/phasep/build_doe_designs.py`, auditor-checked against
the script and the §0.1 config_id map):
- For each needed size N_d, a D-optimal exact design over the candidate set = all 1,728 configs, on
  the §0.1 13-parameter main-effects coding, via **Fedorov exchange** with the **ε-regularized
  D-criterion det(XᵀX + εI), ε = 1e-6** (so supersaturated sizes N_d < 13, e.g. N_d = 7 at B = 8,
  are well-defined). Pinned Fedorov variant: initial design = N_d configs drawn uniform-without-
  replacement via seed key `['doe', N_d]`; repeat {for each design point i and each candidate config
  j∉design, compute the criterion delta of swapping i↔j; apply the single best improving swap}
  until no swap improves the criterion by > 1e-10; **50 restarts** (distinct sub-seeds spawned from
  `['doe', N_d]`), keep the highest-criterion design; ties by the lexicographically-lowest sorted
  config_id tuple. Augmentation designs (below) use key `['doe-aug', N_d]`.
- **Sizes:** primary screen size **N_d = min(24, B − 1)** (B = 8 → 7; 16 → 15; 32/64/128 → 24).
  *Deviation from roadmap §5.3's "16–32 runs" at B ∈ {8,16}, forced by the B−1 budget constraint;
  the range holds for B ≥ 32* (§12-D2).

**Per-kernel trajectory (explicit ordered pseudocode; the free reference is observation 0):**
1. Query the N_d design configs (each consuming budget; already-queried/reference are free).
2. **Fit** the main-effects model on log m over the design's **feasible** rows: OLS
   (`numpy.linalg.lstsq`, constant columns dropped and recorded) **iff** feasible rows ≥ 16 **and**
   the design matrix is full column rank after dropping constant columns; **else ridge** (λ = 1.0 on
   z-scored one-hot with **only nonzero-variance columns scaled**, constant columns passed through
   with coefficient 0, intercept unpenalized). If **zero** feasible design rows: the model is the
   all-zero-coefficient model ⇒ predicted ranking = ascending config_id.
3. **Escalation trigger** (evaluated **only on the OLS branch**; ridge fits never escalate): with
   per-factor effect = max over that factor's coefficients of |β_j| / SE_j (OLS SE from the
   lstsq residual covariance), trigger iff (the top-2 predicted configs' predicted log-times differ
   by < the fit's residual SD) OR (fewer than 3 factors have effect > 2). If triggered **and**
   remaining budget ≥ 13: augment with 12 D-optimal points (key `['doe-aug', N_d]`) for the model
   extended with all two-factor interactions among the top-3 |effect| factors; refit (same OLS/ridge
   rule); recompute the predicted ranking.
4. **Confirm walk:** query configs in predicted-best-first order (ties: lowest config_id), skipping
   already-queried, **stopping at the first feasible confirmation** (each query consumes budget).
5. **Leftover budget:** continue walking the final model's predicted ranking (best first, skipping
   queried), each query consuming budget; best_found tracks feasible results throughout.
DOE at B = 8 (ridge on ≤ 7 rows) is expected to be weak — an honest characterization of DOE at tiny
budgets, reported as such.

### 8.3 BO (v1 §2.1–2.2, finally built — TDD-gated; hyperparameters pinned NOW)
SMAC-style RF surrogate + feasibility-weighted EI, exactly per v1 §2.1–2.2: y = log m;
EI(θ) = (y\* − μ)Φ(z) + σφ(z), z = (y\* − μ)/σ; **σ floored at 10⁻³ log-units**; α = EI · P̂(feasible);
μ, σ = mean and population std (ddof=0) of the per-tree predictions over **feasible** observations
only; P̂ = (feasible-tree votes + 1)/(n_trees + 2) (add-one Laplace); infeasible runtimes never
imputed; **exhaustive α scoring over all 1,728 configs**; **1-in-4 random interleave** (proposals
4, 8, 12, … are uniform-random over not-yet-queried Θ); initial design per (kernel, seed) = **8
configs** in this order: [reference(=all-defaults), expert, known-bad, then 5 uniform-random from
seed key `['bo-init', hash_k, i]`]. **All-defaults = the reference config** (§0.2), observation 0,
free. **Expert** = boundscheck False, wraparound False, cdivision True, initializedcheck False,
nonecheck False, -O3, march native, funroll on, `fmffp=(off,fast)`. **Known-bad** = boundscheck True,
wraparound True, cdivision False, initializedcheck True, nonecheck True, -O1, march x86-64,
funroll off, `fmffp=(off,off)`.
- **RF pin (frozen here; any change is a §12 amendment):** `sklearn.ensemble.RandomForestRegressor`
  and `RandomForestClassifier` with `n_estimators=100, max_features=0.5, min_samples_leaf=3,
  min_samples_split=3, max_depth=None, bootstrap=True, n_jobs=1,
  random_state = seeds.state_int('bo-rf', hash_k, alg_id, seed_i)` (i.e.
  `int(SeedSequence([20260708, fnv1a64('bo-rf'), hash_k, alg_id, seed_i]).generate_state(1, dtype=uint64)[0])`
  — dtype=uint64 pinned to match the committed `seeds.state_int`; the uint32 default is NOT used).
  μ/σ come from `.estimators_` per-tree predictions (regressor) on feasible-only training; P̂ from
  per-tree feasible votes (classifier) on all observations. (Rationale: v1 §2.1 names "SMAC-style
  RF"; SMAC 2.4.0 here is sklearn-backed — `data/env/SMAC_RF_BACKEND.md`. A self-contained sklearn
  RF makes the EI/σ/P̂ math directly hand-fixture-testable.)
- **Gates before BO enters the study (recorded in STATE):** (a) TDD vs hand-computed fixtures,
  red→green, for: EI closed form (σ>0 improvement and no-improvement fixtures), σ-floor engagement,
  Laplace-smoothed P̂ bounds (never exactly 0/1), α product, feasible-only μ/σ (a fixture with an
  infeasible point proves exclusion), interleave schedule, 8-config init contents + reference-free
  budget, conditional-`fmffp` validity of every proposal; (b) a `bo-math-reviewer` pass on
  implementation + fixtures (vacuity check).

### 8.4 Motif+BO (LOKO transfer; total, deterministic warm-start)
- Features: motif/graphlet-orbit vector per v1 §2.4 (ORCA ≤ 5-node orbits on the per-edge-type
  undirected projections, mean+max readout; 13-triad directed census; scale covariates), extracted
  by the in-repo `motifbo-graph` extractor under the v1 §0.6 **hard-fail contract** (D1): extraction
  failure ⇒ the kernel is excluded from the Motif arm with a recorded reason, never a zero vector.
- **Standardization:** z-score with **ddof = 0** fit on the source set S; **zero-variance features
  (over S) are dropped and the dropped set recorded**; similarity = cosine on the standardized
  (surviving-feature) vectors.
- **Warm start (total procedure):** for target kernel k, S = fleet minus {k} minus H minus R (LOKO).
  Process source kernels in **descending cosine similarity to k** (ties by ascending source
  generation index). For each source, walk its feasible configs in **ascending screen-median order**
  (ties lowest config_id) and take the first config not already in the init set (including the
  reference); if a source is exhausted, skip it. Collect up to **8** configs; if fewer than 8 usable
  sources remain, fill the remaining slots from the §8.3 default init in its stated order. All other
  BO machinery identical to §8.3.
- If the extractor fails on ≥ 20% of the fleet, RQ-P3 is reported NOT EVALUABLE (§3.4).

## §9 New-instrument controls (before any reading counts; roadmap §6)

### 9.1 Generator/pipeline controls (P1.1 gate)
- **Planted-effect control kernel** (Amendment A-1a — re-targeted to the vectorization lever): a
  compute-bound elementwise kernel whose −O3+march SIMD vectorization is the planted lever (the
  strongest lever v1 measured on this machine, elkan-class ≥2×). Pass: the pipeline measures
  **Δ_all ≥ 1.6 with `opt_level` the largest main effect** and the pre-stated sign (−O3 faster than
  −O1). [Boundscheck is empirically ≤1.36× and never the single largest effect here — bc and
  −O3/march compete for the same instruction budget (§3.3-B coupling); recorded as characterization
  (A-1c, `results/pilot/CONTROLS_DEBUG.md`, 4-design ledger), NOT the control path.]
- **Known-flat control kernel** (latency-bound pointer chase `j = nxt[j]`): must measure
  **Δ_all ≤ 1.10** (Amendment A-1b: the IF sub-criterion is gated out below the 1.10 Δ-floor — at
  Δ→1, IF is noise/noise; Δ_all ≤ 1.10 alone establishes flatness). [Instrument-mechanism note
  (2026-07-09, NOT a criterion/threshold change; the ≤1.10 criterion is unchanged): the original
  bandwidth-bound streaming SUM measured Δ_all=2.96 — a float reduction is vectorized ~3× by the
  −O3×native×fast_math three-way interaction and is not flat. Replaced by a pointer chase (serial
  dependent integer loads, no FP, no vectorizable compute → genuinely flat). Recorded in
  `results/pilot/CONTROLS_DEBUG.md`.] Both run the full pipeline before any fleet kernel; failure ⇒
  debug-mantra, pipeline frozen. Controls are instruments, never fleet members.
- **Generation determinism:** a kernel's spec is seeded by `['gen', intended_class_int,
  generation_index]`; a kernel's spec seed is **fully determined by its (class, index)** —
  regenerating a kernel under any other seed requires a ledger entry (forecloses "regenerate until
  it looks right").

### 9.2 Probe (the product's router input; frozen design + control)
- 16-point D-optimal main-effects design (same construction as §8.2, key `['probe', 16]`, committed
  in the same `doe_designs_theta.json`). Probe features: Δ̂_probe = max/min feasible probe medians;
  ÎF_probe = 1 − R² of the §0.1 main-effects fit on the probe's feasible rows; feasible fraction.
  **Degenerate-probe rule:** if feasible probe rows ≤ (model rank after dropping constant columns)
  + 2, set **ÎF_probe = NA** (the classifier treats NA as its own feature value) and the per-kernel
  probe df is reported at P4. The probe is a **coarse** router input, validated empirically by RQ-P2,
  not a precise estimator.
- **Probe→class classifier:** any family, fit on the 3 probe features over **fleet tables only**
  (H, R never touched), with a pre-registered cross-validated fleet accuracy reported before it is
  frozen; the frozen classifier is committed **with a SHA-256 hash before P4 begins**; **RQ-P2 is
  evaluated exactly once against that hash**; any retrain is a §12 amendment reported as a second
  look.
- **Probe control (roadmap §6):** the §9.1 planted-effect kernel must yield Δ̂_probe ≥ 1.5 and the
  known-flat kernel Δ̂_probe ≤ 1.1 with low ÎF_probe — recorded before the probe is trusted.

### 9.3 Replay-harness control
- Conformance cheat-test: a stub algorithm that attempts to read the table beyond `query()`
  (direct attribute access, global state, file re-open) must be caught (positive control); RS under
  the same seed identical, under different seeds different (determinism control).

## §10 Compute envelope + de-scope levers (roadmap §4.6 — this supersedes its figures)

**Per-kernel measurement (recomputed honestly, warmup included):**
- Build ≈ 5–10 min (1,728 gcc on 3 compile cores, tmpfs, -g0 -pipe; 32 cythonize cached).
- Screen ≈ 1,728 × [≈0.4 s subprocess overhead + (5 warmup + 5–10 timed) × (50–80 ms) + oracle
  compare] ≈ **26–46 min** (plus the per-config timeout worst case: infeasible configs cost up to
  10 s each; a class-C kernel with a few hundred crash/timeout configs adds an unmodeled
  **~30–60 min** — reported per kernel, not amortized away).
- Endpoint ≈ ⌈|F|/10⌉ (~173) × 3 × [≈0.4 s + (5 + 30) × (50–80 ms)] ≈ **17–27 min**.
- Sanitizer ≈ ≤ 64 class builds+runs + the leak audit ≈ **8–15 min**.
⇒ **≈ 55–105 min/kernel** (worst case higher on cliff-heavy class-C kernels). Fleet ≈ 120 synthetic
+ 9 R ⇒ **≈ 5–9.5 days machine time**, resumable/overnight-capable. **This supersedes roadmap §4.6's
35–50 min / 3–4 days figures** (which omitted warmup and the sanitizer term); **P-1 wall-clock is
compared against THIS envelope** (§12-D3).

**P3 replay compute (was omitted; estimated now):** ≈ 200 seeds × ~90 kernels × up to 128 BO
iterations, each an RF-regressor + RF-classifier fit + exhaustive 1,728-point α scoring, × 2 BO arms
+ 10,000-resample BCa per (class,budget,pair). At ~20–100 ms/iteration this is **≈ tens of hours per
BO arm** on 4 cores — **not** "hours." P3 is pure computation on frozen tables (zero new
measurement); **checkpointed multi-day runtime is acceptable and pre-registered as such**, preserving
the ≥ 200-seed floor.

**De-scope levers (pre-registered, in order; never seeds/tiers/thresholds/budgets):**
(1) fleet 120 → 105: remove the **highest not-yet-measured** fleet indices **uniformly across
intended classes** (never a kernel whose measurement has started; H indices are never cut); the cut
list is committed to the ledger **before** any further measurement.
(2) overhead reduction via a forkserver measurement harness (amortizes the ≈0.4 s subprocess cost) —
a rig optimization, revalidated against the CF-4 baseline before use.

## §11 Freeze, audits, checkpoints

- P-2 freeze: per-kernel table SHA-256 + fleet manifest hash committed; P3 reads only frozen copies
  (verified by hash at load).
- **measurement-auditor** samples **⌈0.2·N⌉ kernels drawn without replacement via seed key
  `['audit', 1]` over kernel indices sorted by kernel_id** (pinned so the sample is not chooseable),
  re-deriving medians/feasibility from raw at P-2; **stats-auditor** recomputes the full P3 result
  matrix from frozen tables (zero-diff) before P-3; **validation-auditor** reviews oracle+sanitizer
  artifacts at each checkpoint; **bo-math-reviewer** gates BO entry (§8.3). `scrutinize` before any
  checkpoint report.
- STOP-for-human at P-1, P-2, P-3, P-4 (roadmap §0.3-6). The agent never self-passes.

## §12 Amendments (numbered; human-approved; append-only, POST-COMMIT only)

Recorded pre-registered **deviations** from the roadmap (folded into v1 before commit, not
amendments):
- **D1** — Golden acceptance band upper edge relaxed 80 → 100 ms (integer-knob granularity;
  lower edge stays 50 ms). (roadmap §3.2/§4.5)
- **D2** — DOE screen size N_d = min(24, B−1) yields 7/15-run designs at B ∈ {8,16}, below roadmap
  §5.3's "16–32 runs" range, forced by the B−1 budget; range holds for B ≥ 32.
- **D3** — Compute envelope restated to ≈55–105 min/kernel, ≈5–9.5 days fleet (roadmap §4.6 omitted
  warmup + sanitizer); P-1 compares against this envelope.

**Errata** (post-commit prose corrections with ZERO semantic effect — the committed code/fixtures
are authoritative and were already correct; recorded per §6, flagged by the P0-exit auditors):
- **E1** — §0.4 illustrative `fnv1a64("screen")` digits corrected `15602715…` → the true
  `10080399746057843313` (matches the committed `seed_fixtures.json` / `seeds.py`). No algorithm change.
- **E2** — §8.3 BO `random_state` prose pinned to `seeds.state_int(...)` = `generate_state(1,
  dtype=uint64)[0]` (the committed `seeds.py` already uses uint64; the earlier `[0]` prose defaulted
  to uint32). No BO has been built or run; this only makes the prose match the committed seed module.

Amendments (post-commit):
- **A-1 (2026-07-09) — THE single pre-registered P-1 recalibration (roadmap §3.4). NOW SPENT: any
  further threshold/spec change requires a separate human request.** Motivated by the failed first
  controls gate + the 4-design debug ledger (`results/pilot/CONTROLS_DEBUG.md`): on this hardware
  boundscheck is empirically unachievable as a ≥1.6× *dominant* lever (spec-vs-hardware, not a
  measurement bug — the instrument is proven sound). Committed BEFORE the gate re-run.
  - **A-1a** — §9.1 planted control re-targeted from the boundscheck lever to the −O3+march
    vectorization lever; pass = Δ_all ≥ 1.6 with `opt_level` the largest main effect (pre-stated
    sign: −O3 faster than −O1).
  - **A-1b** — §1.5 / Appendix B (v1→v2): IF is evaluated ONLY when Δ_all ≥ 1.10 (5× the 2% noise
    floor); Δ_all < 1.10 ⇒ class A directly (flat-by-Δ). Correctness fix to the IF estimator
    (IF = noise/noise at Δ→1), applies to the flat control AND the flattest fleet-A kernels.
  - **A-1c** — the histogram-scatter bc-ceiling probe is recorded as characterization
    (`results/pilot/CONTROLS_DEBUG.md`), NOT a gate.

- **A-2 (2026-07-16) — structural amendment: taxonomy v2 + generator v2 + INT probe + pilot
  demotion. Human-ruled at CHECKPOINT P-1 (P-1 report accepted as decision-grade); RATIFIED with
  riders R1–R3 (human directive, recorded in A2_DECISION_MEMO.md sign-off block). This commit IS
  the taxonomy freeze: any further threshold/scope change mid-fleet is a STOP-THE-FLEET human
  event.** Motivated by the pilot confusion table (10/17 boundary; families uniform on axes v1
  cannot express — fm wedge, feasibility structure). Supersedes §1.6's reserved precedence-rule
  option (unused). A-1 remains spent and untouched. Full spec + evidence:
  `results/pilot/A2_DECISION_MEMO.md`; recompute `scripts/phasep/a2_reclassify.py`.
  - **A-2a (§1 → §1-v2):** primary class on the STRICT axis — FLAT (Δ_strict < 1.10, A-1b floor) ·
    MID (1.10 ≤ Δ_strict < 1.5) · LEVER-SEP (Δ_strict ≥ 1.5 ∧ IF_strict < 0.25) · INT
    (Δ_strict ≥ 1.5 ∧ IF_strict ≥ 0.25); IF_strict = §1.1 OLS restricted to strict feasible rows
    (fmffp ∈ {(off,off),(off,fast)}), same degenerate rules, Δ_strict ≥ 1.10 gate. Orthogonal
    flags FM (Δ_all/Δ_strict ≥ 1.5) and FEAS (infeas_frac ≥ 0.25). greedy-gap/τ-optima retained
    as descriptors. No boundary class (total partition). v1 labels remain the pilot's record.
  - **A-2b (§2):** pilot data demoted to development — the pilot top-up clause is struck; attrition
    draws spares only; sub-26 regimes presented at P-2 with the power consequence. Fleet layout
    per fielded regime: 6–35 fleet (30), 36–40 H (5, regenerated under generator v2 post-freeze),
    41+ spares. R unchanged (9, P4 acceptance; stays in H).
  - **A-2c (§3.3):** confirmatory families = (regime × budget), regimes {FLAT+FM, MID, LEVER-SEP,
    INT — fielded per the probe verdict}; FLAT∧FM− is descriptive-only.
  - **A-2d (generator v2 diversity mandate):** ≥6 templates/regime; parameter ranges; anti-clone
    rejection at ε = 0.05 on (lnΔ_all, lnΔ_strict, IF_strict, infeas_frac, greedy_gap) within
    template; property-spread report is a P-2 deliverable.
  - **A-2e (INT probe, executed):** protocol + bars (Δ_strict_16 ≥ 1.3 ∧ S ≥ 1.15), kill
    criterion, ≥2-mechanism fielding rule — OUTCOME: 3/4 candidates passed (P1 2.35/5.29,
    P2 5.17/11.40, P4 1.80/5.22; P3 S=1.004 = separable cdivision lever → LEVER-SEP template);
    INT fielded. Probe data is development-grade (`results/probes/int/`), outside the fleet
    dataset.
  - **A-2f (schema, closes P-1 auditor N1):** every fleet table row / endpoint record carries the
    measure_wrap rig fingerprint; survival-ledger entries carry run_id + run_kind. Pilot artifacts
    are grandfathered (development) and not rewritten.
  - **A-2g (rider R1 — FEAS confirmatory design, option (a)):** FEAS is an exactly balanced flag —
    15 FEAS+ / 15 FEAS− within each confirmatory regime (the 10-kernel honest-null stratum
    exempt). Confirmatory: one-sided paired Wilcoxon BO < RS pooled over the 60 FEAS+ fleet
    kernels at B ∈ {16,32}, Holm over budgets; n = 60 ≥ 26 ⇒ powered at δ = 0.4 (one-sided,
    matching the §2 power model). The FEAS− contrast and the FEAS+/FEAS− delta are reported
    descriptively with CIs. FEAS+ inside FM+ regimes uses the directive-crash mechanism (an
    fm-cliff would kill the wedge); FEAS+ templates target infeas_frac ≥ 0.30.
  - **A-2h (rider R2 — knife-edge semantics):** every v2 threshold fires at its boundary value
    (closed lower bound, ≥), matching A-1b's orientation; flag fractions compared in integer
    arithmetic (FEAS+ ⇔ 4·n_infeasible ≥ n_total). The A-family boundary case (432/1728 = 0.25
    exactly) is MID+FEAS. Anti-clone rejects iff ALL five |Δp_i| < 0.05 (strict; exactly 0.05 =
    distinct). Greedy ties keep §1.3's lowest-config_id rule. Kernels within ±0.01 of a class
    boundary are ledger-flagged and reported at P-2.
  - **A-2i (rider R3 — INT membership measured):** fleet regime membership is each kernel's OWN
    full-table v2 classification; intended-INT measuring non-INT takes its measured class — no
    grandfathering (probe kernels are development artifacts, never fleet members). P-2 compares
    each INT kernel's full-table Δ_strict to its template's probe-screen figure; ≥ 2×
    screen-vs-table inflation is investigated before the freeze (D5 lesson).

- **A-3 (2026-07-24) — bounded wave-2 supply top-up for the missed confirmatory-cell floors.
  Human-ruled at the P-2 boundary (P-2 COMPLETION directive, recorded in
  `results/fleet/A3_TOPUP_AMENDMENT.md`). SUPPLY ONLY: no taxonomy threshold, classifier, rig,
  or protocol change — any threshold change remains a STOP-THE-FLEET human event. Structural
  uncontamination rationale on the record: NO algorithm has touched any measured table (replay
  has never run; the run_study.py freeze guard is structural), so this amendment cannot be
  outcome-driven — the only data visible to it is landscape properties. The wave-1 shortfall
  remains reported at P-2 as the pre-registered honest negative (§2 / A-2b), alongside the
  post-A-3 totals.**
  - **A-3a (scope — confirmatory CELLS, F2 discipline):** the §2 n=26 (δ=0.4) floor applies to
    the A-2c confirmatory cells verbatim — {FLAT+FM, MID, LEVER-SEP, INT}, where FLAT+FM means
    measured FLAT ∧ FM+ (FLAT∧FM− is descriptive-only). Measured wave-1 cell n (raw:
    `results/fleet/template_analysis_final.json`): FLAT+FM **11** · MID **18** · LEVER-SEP
    **23** · INT **37** (FEAS+ pool 50). Wave-2 targets: raise every sub-26 cell to ≥ 26 —
    FLAT+FM +15, MID +8, LEVER-SEP +3. This CORRECTS the synth-complete STATE entry's
    "FLAT 26 ✓" line, which counted the bare class where the confirmatory family is the
    flagged cell; no measurement is affected (labels untouched; a counting statement only).
  - **A-3b (wave labels + robustness slice, PRE-REGISTERED):** every kernel carries a `wave`
    field (1 = the 104 accepted synth kernels of the original campaign; 2 = every A-3 kernel)
    in spec.json, the survival ledger, and FREEZE_MANIFEST.json. P3 per-class results WILL be
    reported both with and without wave-2 kernels (robustness slice); H and R are wave-exempt
    (holdout). Wave-2 ledger rows carry run_kind `fleet-topup`.
  - **A-3c (template basis — producers only):** wave-2 draws ONLY on templates/parameter
    regions supported by the committed wave-1 producer/non-producer analysis
    (`template_analysis_final.json`; recompute `scripts/phasep/template_analysis.py`):
    FLAT+FM ← fm_sum/fm_dot/fm_sumsq restricted to dt=double (measured: double → FM+ 8/9,
    float → FM+ 0/6), new n values; MID ← mid_hist (MID 3/4) and mid_gatherpoly deg 2–3
    (corridor evidence: L2-tier → MID 6/6 across both; L1 overshoots INT, deg-3/L1
    undershoots FLAT), new (bins, deg, n) points including the previously-fixed bins
    dimension; LEVER-SEP ← lev_csr (6/6; row_nnz dimension opened, was fixed 16),
    lev_modconst (4/4, new divisors), lev_axpy (L1 3/3), and int_sum64 cross-listed as a
    measured LEVER-SEP producer (4/4). The three mis-designed LEVER-SEP templates
    (lev_clipmap, lev_sqrtmap, lev_strided — 0/10 combined) and the FM non-producers
    (fm_abssum 0/4→INT, fm_altsum, fm_runmean) are EXCLUDED from wave-2; their disposition
    for H is recorded in the memo. Template diversity (A-2d ≥ 6/regime) is evaluated POOLED
    across waves.
  - **A-3d (hard caps + allocation + stop):** wave-2 measure compute is capped at
    **172,800 s (2 days) of Σ(build_s + measure_s) over all wave-2 kernel cycles** (any
    status), checked before each new cycle; at/over cap the runner ledgers `TOPUP_CAP_STOP`
    and generation stops REGARDLESS of floors. Allocation: one slot per turn, cycling
    FLAT_FM → MID → LEVER_SEP, skipping any cell already at ≥ 26 (maximizes worst-case
    balance at a cap-stop). Stop when all three cells reach 26 or the cap fires. Every wave-2
    kernel: spec.json + compile/determinism smoke + anti-clone vs the ENTIRE fleet (the
    check keys on template across waves) + the D8 params-duplicate pre-guard; measured
    classification decides arrivals (A-2i, no grandfathering); anti-clone ε and all A-2h
    knife-edge semantics unchanged.
  - **A-3e (controls re-verify, HARD gate):** before any wave-2 measurement, the §9.1
    controls gate re-runs ONCE on the current rig into `results/fleet/controls_a3/`
    (fresh tables; wave-1 gate evidence in `results/fleet/controls/` is preserved
    untouched). Planted must be detected, flat must read flat; either failure is a HARD
    STOP (no top-up measurement). Gate wall-clock is reported but excluded from the A-3d cap
    (it is gate infrastructure, not top-up supply).
  - **A-3f (null disposition + negative-control transfer):** wave-2 adds NO null slots; the
    honest-null drift finding (half the accepted nulls measured MID/INT off-design) stands
    as measured. PRE-REGISTERED P3 check: the negative-control role transfers to the
    measured-FLAT class — any algorithm materially beating RS on measured-FLAT kernels in P3
    is a harness red flag to investigate, not a result.
  - **A-3g (exact power at achieved n):** report-time power per confirmatory cell is computed
    by the COMMITTED generator `scripts/power/clustered_power_preview.py::power(n, δ=0.4,
    rng)` at N_SIM=60,000 with the committed extended-scan stream (SEED_EXT=20260628), run
    in the pinned container — never hand-interpolated. Final per-cell n (per wave and
    pooled) + this exact power go in the P-2 report verbatim.

- **A-4 (2026-07-25) — SEQUENCING amendment: scope-ORDER ONLY. Human-directed re-ordering of
  phases (a P4-alpha `cytune` CLI build inserted BEFORE P-2 completion). NO scientific content
  changes.** Provenance: human directive "A-4 SEQUENCING: PAUSE A-3 → BUILD cytune v0 → SMOKE ON
  DEV DATA → RESUME FULL-THROTTLE", recorded verbatim in `results/fleet/A4_SEQUENCING_MEMO.md`.
  This amendment is deliberately narrow: it moves *when* work happens, never *what is measured or
  how it is judged*.
  - **A-4a (what changes — order only):** the standing order was A-3 top-up → freeze → H → R →
    audits → P2_REPORT → STOP. It becomes: A-3 top-up **paused at a kernel boundary** → cytune v0
    built and smoked on development data → `CLI_V0_REPORT.md` → **STOP for the human's resume
    call** → A-3 resumes full-throttle → the standing P-2 completion plan UNCHANGED (freeze → H
    ≥15 with ≥3/confirmatory cell incl. LEVER-SEP → all 9 R anchors → audit battery → P2_REPORT →
    STOP). CHECKPOINT P-2 is neither moved nor weakened and is never self-passed.
  - **A-4b (what explicitly does NOT change):** no class threshold (§1/§1-v2), no measurement tier
    (§4), no metric/test/budget/seed (§3, §8), no sample-size or floor (§2; n≥26 per confirmatory
    cell at δ=0.4 stands), no study design (§5/§3.5), no correctness rule (§5/§0.3). A-1, A-2 and
    A-3 remain in force verbatim; A-1 remains SPENT. The A-2 taxonomy freeze is untouched — A-4 is
    not a threshold/scope change and therefore not a STOP-THE-FLEET event.
  - **A-4c (cap accounting — the pause consumes none):** the A-3d cap remains **172,800 s of
    Σ(build_s + measure_s + orphan_s) over wave-2 kernel cycles (any status)**, unchanged in both
    value and definition. Wave-2 spend is frozen at the pause point and the pause interval charges
    **zero**, because the cap is defined over *wave-2 ledger cycles* and no wave-2 cycle runs
    during the pause. cytune's own development measurements are **not wave-2 rows**, are taken on
    development data only, and therefore never touch the cap — by the cap's existing definition,
    not by an exemption invented here. Spend at pause: **70,927.4 s / 172,800 s (41.0%)**,
    recomputed from the ledger by `run_fleet._topup_spend`.
  - **A-4d (data firewall — binding):** the CLI may read and measure ONLY development data: the
    demoted pilot kernels (A-2b) and fresh toy modules authored outside every dataset. The frozen
    and to-be-frozen study sets — `results/fleet/**` synth, holdout **H**, and the 9 **R** anchors
    — are untouchable by cytune: not read to tune it, not measured by it, not written by it. The
    interim routing policy (A-4e) is fixed and committed BEFORE the first CLI run and is never
    tuned against fleet/H/R at any point. This preserves §3.5: RQ-P2 (router efficacy) is still
    evaluated at P4 on H + R only, against a router the H/R data never informed.
  - **A-4e (INTERIM routing — labeled, non-evidentiary):** v0 routes by a FIXED heuristic derived
    only from v1 findings + pilot development data, committed before first use as
    `results/prereg/CYTUNE_V0_ROUTING_INTERIM.md`. Every cytune output labels it verbatim
    `routing: INTERIM heuristic — pending P3 study`. v0 makes NO P3-validated routing claim, and
    its routing decisions are **not evidence** for RQ-P2 or the P3 routing matrix.
  - **A-4f (engine gating):** the DOE engine (§8.2) is v0's default. The BO engine (§8.3) ships in
    v0 only if a `bo-math-reviewer` pass is run for this use and PASSES; the verdict is quoted
    verbatim in `CLI_V0_REPORT.md`. Motif+BO (§8.4) is EXCLUDED from v0 by design — RQ-P3 has not
    been run, so shipping it would assert unproven transfer value.
  - **A-4g (pause mechanics, recorded):** the pause is taken at a clean kernel boundary — the last
    ACCEPTED wave-2 row (`fleet_MID_W2_53_mid_gatherpoly`, commit e9da3fc). No partial table is
    retained (C_04/`_clean_interrupted` precedent). The cycle in flight at the pause
    (`fleet_LEVER_SEP_W2_53_int_sum64`, interrupted mid-measure at 171/1728 by a human-initiated
    host reboot) is reconciled through the runner's OWN pre-registered path
    (`run_fleet._reconcile_inflight`) as **CYCLE_ORPHAN, orphan_s = 1608.5 charged to the A-3d
    cap** at the last-activity lower bound. It is charged, not exempted: the pre-registered
    death-visible mechanism is used rather than the D12 environment-fault exemption, so the pause
    cannot become a cap loophole.
  - **A-4h (F1 — CF-1 quiesce-all, corrected):** the graphify post-commit rebuild is deferred
    while any campaign measure phase is live, and runs only when the runner is idle/paused. This
    OVERRULES my earlier stewardship claim that the rebuild was harmless because measurement is
    cpu3/7-isolated: cpuset isolates cores, **not DRAM bandwidth or shared LLC** (CF-4), and D5's
    root cause was precisely host load during measurement. Quiesce-all means nothing else runs.
    No measurement is retro-invalidated by this correction — it is recorded as a tightening, and
    any measurement whose quiescence is in doubt is discarded rather than defended (the standing
    rig-discipline rule from the 2026-07-24 incident).

- **A-5 (2026-07-25) — ADDENDUM: a SECONDARY regret slice on the emittable-under-default subset.
  Registered BEFORE any replay study run exists.** Human-ratified by the CLI-riders directive.
  Additive only: it introduces no new measurement, changes no algorithm, and does not touch the
  primary metric.
  - **A-5a (what is added).** Alongside the primary metric (regret over the full feasible space,
    §3.1), the study additionally reports **regret on the emittable-under-default subset**, per
    **regime × budget × algorithm**, with the same seeds, the same trajectories and the same
    tests. Definition, in the existing vocabulary: the emittable-under-default subset is
    `{c ∈ Θ : feasible(c) ∧ fast_math(c) = off}` — exactly the configs `cytune` may emit when the
    user has not passed `--allow-fast-math`, and exactly the set over which §1-v2 already defines
    `t_strict`. So `regret_emittable@B = best_found_emittable@B / t_strict − 1`, with the primary
    metric's floor convention (`best_found` floored at the reference) applied unchanged.
  - **A-5b (why — the study-vs-product semantic gap, evidenced).** The E3 live-engine audit
    (2026-07-25, verdict verbatim in `results/cli_v0/CLI_V0_REPORT.md` §4) measured that BO, run
    against the full feasible space, spent **37.0% of its paid budget on configs the product is
    forbidden to emit by default**, and in **5/5 simulated seeds returned a best-found config that
    could not be emitted**. The primary metric is the right answer to the study's question ("which
    algorithm searches the feasible space best") and the wrong answer to the product's question
    ("which algorithm should route a default-mode run"). Registering the slice now means the P3
    comparison can answer both without a second look at the data.
  - **A-5c (what does NOT change).** The primary metric, its hypothesis tests (§3.3), its effect
    sizes, the RQ-P1/RQ-P3 decision rules (§3.3/§3.4) and every budget, seed and threshold stand
    exactly as pre-registered. A-5 is **secondary and descriptive**: no primary conclusion is
    conditioned on it, and it is never substituted for the primary metric if the primary is
    unfavourable. Both are reported side by side, always.
  - **A-5d (computability — the harness records it, algorithms are untouched).** The slice is a
    post-hoc re-analysis of the SAME sealed trajectory: `replay.run_algorithm` records the set of
    configs an arm actually queried (via the already-whitelisted `SealedTable.queried_ids`) and
    computes the emittable best from the frozen table AFTER the algorithm returns. The sealed
    ask–tell interface, the §9.3 cheat-test and every algorithm's behaviour are unchanged; no arm
    is re-run and no arm can observe this metric. Because no replay study run exists yet, the
    instrumentation is in place before the first row rather than retrofitted.
  - **A-5e (scope limit).** This registers an ANALYSIS slice, not a product claim. It does not
    validate cytune's routing, does not consume the one-shot RQ-P2 evaluation (§9.2, A-4e), and
    does not license fitting anything to fleet/H/R outside the pre-registered classifier.

- **A-6 (2026-07-25) — SUPPLY-ONLY roster narrowing at the A-4 resume, on measured wave-2
  producer evidence.** Human-directed by the resume directive ("LEVER-SEP slots use the
  proven-separable cdiv-lever pool ONLY — no int_sum64/INT-flavored slots; lev_axpy-class drifters
  are evidence, not roster"). Touches **supply only**: no threshold, cell definition, tier, metric,
  cap value or cap definition changes, and A-3d's round-robin allocation is untouched.
  - **A-6a.** `REGISTRY["LEVER_SEP_W2"]` narrows from four templates to two, ordered
    `[lev_modconst, lev_csr]`. `lev_modconst` leads because it is the separable **cdivision** lever
    identified by the A-2e INT probe (candidate P3, S = 1.004) and the only template that produced
    LEVER-SEP in BOTH waves (wave-1 4/4, wave-2 1/1). `lev_csr` is retained as the strongest
    wave-1 producer (6/6); its single wave-2 accept spilled to MID, which is a miss rather than a
    drift into the neighbouring lever class.
  - **A-6b (dropped, with the evidence that dropped them).** `lev_axpy` — wave-1 4/6, wave-2
    measured **INT**. `int_sum64` — wave-1 4/4 but INT-flavoured by construction; its wave-2 slot
    drifted and was reconciled as `CYCLE_ORPHAN` at 1,608.5 s for no accept. Their wave-2 behaviour
    is **evidence for the P-2 report** (the LEVER-SEP↔INT knife-edge is real and bidirectional),
    not roster supply.
  - **A-6c (reading recorded, because the directive's phrase admits a narrower one).** "cdiv-lever
    pool" could be read as `lev_modconst` ALONE. It is read here as the proven-separable pool =
    {`lev_modconst`, `lev_csr`}, because excluding the 6/6 wave-1 producer would leave a single
    template supplying a cell that needs +2 and would make anti-clone exhaustion the binding
    constraint rather than measurement. If the human intended `lev_modconst` only, that is a
    one-line registry edit and this clause is the place it is recorded.
  - **A-6d (what this does NOT do).** It does not re-open FLAT+FM or MID rosters, does not change
    `TOPUP_MAX_SLOTS`, does not alter the D8 params-duplicate pre-guard or the anti-clone ε, and
    does not touch wave-1 evidence. Anti-clone still keys on template across waves, so wave-2 is
    checked against the ENTIRE fleet.

- **A-7 (2026-07-28) — SUPPLY-ONLY parameter extension for the holdout-H registries (FLAT+FM and
  INT). Human-ruled at the P-2 freeze boundary on a presented decision memo: "Option 1 APPROVED
  with riders; options 2 and 3 REJECTED". Full directive verbatim + evidence + the recompute
  command: `results/fleet/A7_H_SUPPLY_AMENDMENT.md`. Committed BEFORE any extended kernel was
  generated (ordering evidence in §5 of that memo).** Motivated by a MEASURED blocker, not a
  projection: H's first slot exhausted on nine consecutive `PARAMS_DUPLICATE` skips at ZERO
  measurement cost. Fresh `(template, params, feas_variant)` supply for H against the 169 keys the
  training campaign consumed was MID 14 · LEVER-SEP 13 · FLAT+FM **5** · INT **0** — the H ruling
  (≥3 per confirmatory cell, ≥15 total) was structurally unsatisfiable for INT.
  - **A-7a (scope — supply only).** Two NEW registry keys, `FLAT_FM_H` and `INT_H`, read only by
    `--stage holdout`. Wave-1 and wave-2 registries are byte-untouched: `process_slot` derives
    params as `pspace[(gi+k) % len(pspace)]`, so mutating an existing `pspace` would silently
    repoint already-frozen slot labels. Ranges are chosen by the committed producer-evidence
    analysis (`template_analysis_final.json` + the wave-2 accept ledger) FOR CELL-TARGETING ONLY.
    `FLAT_FM_H` = {`fm_sumsq`, `fm_sum`, `fm_dot`} at `dt=double` only (double → FM+ 8/9;
    float → FM+ 0/6), six new `n` each, all INTERPOLATING inside the demonstrated 4,096–1,179,648
    corridor. `INT_H` = {`int_horner32`, `int_horner64`, `int_revsum`, `int_sumsq`, `int_min32`,
    `int_max32`} ordered by measured wave-1 INT rate (3/3, 2/2, 2/2, 2/3, 2/3, 1/2), six new points
    each, degree opened for the horner pair. `int_sum64` is DROPPED (measured LEVER-SEP 4/4, INT
    0/4) on exactly the A-6b logic. The exact 102 points are tabulated in the memo §3; all were
    verified fresh against every ACCEPTED/REJECTED_CLONE ledger row — **0 collisions** — before
    this commit.
  - **A-7b (anti-sculpting guard, BINDING).** The parameter points are FIXED by this amendment
    before any generation. No iterating parameters against measured Δ/IF/greedy-gap to shape
    individual landscapes. The only filters remain the anti-clone check (vs the ENTIRE fleet AND
    every accepted H kernel — `_accepted_props` keys on template across waves and holdout) and the
    measured full-table classification. A-2i holds verbatim: membership is each kernel's OWN
    measured class, no grandfathering; H's intended-vs-measured confusion is a P-2 deliverable.
  - **A-7c (ONE-SHOT).** This is the single H supply extension. If cells remain short when the H
    cap fires, that is the final reported state — no second extension, ever.
  - **A-7d (H cap + fill priority).** The ENTIRE H campaign is capped at **86,400 s (24 h) of
    Σ(build_s + measure_s + orphan_s) over holdout ledger cycles, any status**, mirroring A-3d's
    definition and its "cap + at most one in-flight cycle" ceiling. The cap is evaluated BEFORE
    roster state so a cap-stop is never mis-recorded as roster exhaustion; the runner ledgers
    `H_CAP_STOP` and generation stops REGARDLESS of fills. Fill priority: INT ≥3 first, then
    FLAT+FM ≥3, then MID ≥3 and LEVER-SEP ≥3, then top up toward ≥15 total. H_PER_CELL = 3 and
    H_MIN_TOTAL = 15 are UNCHANGED.
  - **A-7e (provenance labels + the P4 provenance slice, PRE-REGISTERED NOW).** Every H kernel
    carries a permanent `provenance` field: **H-orig** (drawn from a pre-A-7 registry —
    `MID_W2`, `LEVER_SEP_W2`) or **H-ext** (drawn from `FLAT_FM_H` / `INT_H`). It is written to
    spec.json, the survival ledger, and `H_MANIFEST.json`. PRE-REGISTERED: **RQ-P2 acceptance
    results at P4 WILL be reported sliced by provenance** (routed-regret and acceptance on H-orig
    vs H-ext separately, never only pooled), so any routing degradation on the mildly
    out-of-distribution kernels is visible rather than averaged away. Framing, recorded in the
    manifest: the extension makes H a mild extrapolation of the training parameter distribution —
    a HARDER and more realistic generalization test, since real user kernels are OOD too.
  - **A-7f (structural-finding clause).** If INT cannot reach 3 even from the fresh extended
    points, that is reported as a STRUCTURAL FINDING — the INT-producing parameter region is
    narrow, consistent with v1's real-code evidence that strict directive×flag interactions are
    rare — accompanied by the full attempt ledger. The extension is NOT iterated (A-7c).
  - **A-7g (what does NOT change).** No class threshold, tier, metric, test, budget, seed, floor,
    study design or correctness rule. No change to anti-clone ε, A-2h knife-edge semantics, the D8
    pre-guard, or A-2i. A-1 remains SPENT. The A-2 taxonomy freeze is untouched — a supply
    amendment is not a STOP-THE-FLEET event. `FREEZE_MANIFEST.json` (129 training kernels, commit
    `0540fb2`) is NOT reopened; H seals into its own manifest and nothing in A-7 can alter a
    frozen table.
  - **A-7h (cross-listing considered and DECLINED, recorded).** Measured data offers a cheaper INT
    supply via other regimes' templates (`fm_abssum` 4/4 INT, `lev_clipmap` 4/4, `lev_sqrtmap` 3/4,
    `mid_gatherpoly_deep` 2/2, `null_inplace` 2/2), and A-3c set the cross-listing precedent with
    `int_sum64`. It is NOT taken: the ruling's scope clause authorises "new parameter points/
    ranges", and adding templates is a roster change. The 102 fresh keys make it unnecessary.
    Recorded so the option is visibly declined on scope rather than silently missed.
  - **A-7i (2026-07-28) — ALLOCATION rider: FLAT+FM is deprioritized for H's remaining budget.
    Human-ruled mid-campaign on a presented decision memo with the per-registry economics.
    ALLOCATION ONLY — no threshold, taxonomy, cell definition, metric, cap value or cap definition
    changes, and no new supply (A-7c's ONE-SHOT stands; nothing is added).** This rider is
    OUTCOME-INFORMED and says so plainly: it was decided after seeing measured per-cell costs, so
    it is recorded as an amendment rather than applied silently, and it is committed BEFORE it
    takes effect.
    - **The evidence** (H at 16.50 h of the 86,400 s cap, 5 accepts, recompute from
      `fleet_ledger.jsonl` rows with `run_kind == "holdout"`):

      | registry | accepts | clone-rejects | rate | spend | h/accept |
      |---|---|---|---|---|---|
      | `INT_H` (H-ext) | 2 | 0 | 100% | 1.59 h | **0.80** |
      | `MID_W2` (H-orig) | 1 | 0 | 100% | 1.44 h | 1.44 |
      | `LEVER_SEP_W2` (H-orig) | 1 | 2 | 33% | 2.39 h | 2.39 |
      | `FLAT_FM_H` (H-ext) | 1 | **11** | **8%** | **11.07 h** | **11.07** |

      FLAT+FM consumed **67% of the entire H budget for one accept**. All 11 clone rejects sit
      well below ε (max 0.0431; most ≈0.01–0.02) — none near the boundary.
    - **What this establishes, and it is a P-2 FINDING in its own right:** A-7 did exactly what it
      was written to do for **INT** — the structurally impossible cell became the *cheapest*
      (0 clone rejects, 0.80 h/accept). It cannot do the same for **FLAT+FM**, because FLAT+FM's
      binding constraint is the **property space, not the parameter space**. FLAT+FM landscapes are
      near-degenerate by construction (Δ_strict ≈ 1.000, IF_strict null, greedy_gap frequently 0),
      so fresh parameters yield fresh kernels that land on top of existing landscapes. This is a
      DIFFERENT exhaustion mode from INT's and is reported as such.
    - **The rule:** for H's remaining budget the walk serves `INT_H`, `MID_W2` and `LEVER_SEP_W2`
      only. `FLAT_FM_H` and `FLAT_FM_W2` are not served, including for the ≥15 total top-up. The
      FLAT+FM cell continues to be COUNTED and REPORTED at its measured value — only *serving*
      stops, never counting.
    - **Why it is defensible rather than results-shopping:** continuing to serve FLAT+FM buys no
      information. The saturation finding is already established at 11 rejects / 8%; a 12th reject
      would confirm nothing new while consuming hours that demonstrably fill cells that CAN fill.
      No kernel already measured is affected, no label moves, and the shortfall is still reported
      exactly as measured. What changes is only which cells the remaining hours are offered to.
    - **Mechanism:** `run_fleet.py --stage holdout --deprioritize FLAT_FM_H,FLAT_FM_W2`. The
      deprioritized list is written into `run_meta`, so **every subsequent H ledger row carries
      it** and the allocation regime in force is recoverable per row rather than only from the
      launch command.
    - **A-7c is untouched:** this adds no parameter points and no templates. If the human had
      instead asked for more FLAT+FM supply, that would be a second extension and A-7c forbids it.

  - **A-8 (2026-07-30) — SEQUENCING amendment: checkpoint-by-exception for the P-2 → P-5 endgame.
    Human-issued directive, recorded before it takes effect. SEQUENCING ONLY — no threshold,
    taxonomy, cell definition, metric, test, budget or seed changes.**
    - **What changes:** checkpoints P-2 / P-3 / P-4 no longer each hold a live STOP. The endgame
      runs P-2 closure → Stage-B remediation → P-3 replay → P-4 delivery → P-5 report in one pass,
      advancing on PRE-STATED TRIPWIRES instead of a live human call at each boundary. The human's
      sign-off is recorded once, on the assembled package, plus the recorded ruling that issued
      this amendment.
    - **What does NOT change, stated explicitly because a sequencing amendment is exactly where
      substance could be smuggled in:** every threshold in §2–§4 stands; the n=26 floor stands and
      is NOT waived; underpowered cells are reported with exact power at the achieved n and are
      never presented as confirmatory-passed; PREREG §4's `agreement_fail` exclusion stands;
      *correctness absolute* stands.
    - **NO new floor-filling measurement.** Filling FLAT+FM (needs +6), MID (+1) and LEVER-SEP (+6)
      at ~1–2 h/accept is not affordable in the endgame budget, and A-7's evidence is that FLAT+FM
      cannot be filled at any price. Achieved-power reporting is the pre-registered path for a
      short cell (A-3d), and it is the path taken.
    - **The tripwires that still PAUSE for the human** (everything else advances): cheat-test
      failure · any algorithm "winning" on FLAT · a stats-auditor diff ≠ 0 · a Stage-B sanitizer
      dirty cascade · Motif extractor hard-fail on >20% of kernels. Sub-floor cells do NOT pause —
      they are reported with exact power and marked *underpowered at δ=0.4*.
    - **Why it is defensible:** it changes WHEN the human looks, not WHAT is true. Every gate that
      could change a number is untouched; the tripwires are the subset of outcomes where advancing
      without a human would risk propagating a defect into the product, and they were written down
      before the runs that could trip them.
    - **It tripped on its first use, which is the evidence that it is not decorative:** the
      Stage-B sanitizer tripwire fired (D23) — see the deviations register.

  - **A-9 (2026-07-30) — the §1.4 sanitizer gate is applied RETROACTIVELY, by overlay, to configs
    the oracle passed and the sanitizer rejects. GATE APPLICATION, not a threshold change.**
    - **Why an amendment at all:** §1.4 always said an ASan/UBSan report makes a candidate
      infeasible. Nothing about the rule is new. What is new is that the rule is being applied to
      already-measured, already-frozen rows, which changes committed feasibility labels and three
      committed class labels — so it is recorded and numbered rather than done quietly.
    - **Scope, mechanically derived and reproducible:** armed `trap_wrap` kernels × the UB set
      {boundscheck=False ∧ wraparound=False} (432 of 1,728 configs) × currently-recorded-feasible.
      1,296 cells in 3 kernels. Derivation and evidence:
      `results/fleet/SANITIZER_INFEASIBLE_OVERLAY.json`.
    - **The raw is NOT edited.** `FREEZE_MANIFEST` sha256s still verify byte-for-byte; the timings
      are real and stand. Only the feasibility LABEL is corrected, on top, in a committed overlay,
      and the append-only ledger keeps its uncorrected `measured_v2` because history is evidence.
      The correction is applied at `run_fleet._cell_of`, the single point where the cell rule lives.
    - **Effect on the confirmatory counts:** INT 41→38 as-measured / 30→29 conformant;
      MID 26→29 / 24→25. No floor verdict flips — still 1 of 4 cells at or above n=26.
    - **Effect on the product, which is the point:** those 1,296 configs are now infeasible, so
      the search cannot select them and `cytune` can never emit them. Three kernels' headline 13×
      speedup was the out-of-bounds read; corrected, it is 1.32×.

  - **A-10 (2026-07-31) — SEED TRUNCATION for the P-3 study. Human-ruled on a presented decision
    memo, timeline-driven, recorded BEFORE any truncated result was read. PRECISION ONLY — no
    threshold, cell, floor, metric, test, or analysis-set change.**
    - **What changes:** the stochastic arms (RS, BO, Motif+BO) are analysed on the **20-seed
      uniform prefix** actually achieved, not the pre-registered 200. DOE is deterministic and
      unaffected.
    - **Why this is the one axis that may bend.** PREREG §3.2 makes the per-kernel summary the
      **mean regret over seeds**, and §3.3 makes the Friedman/Wilcoxon family a set of KERNELS in a
      (cell × budget) cell. **The test's n is the number of kernels; seeds never enter it.** So
      truncation cannot move a floor, cannot change a cell's membership, and cannot alter any
      pre-registered threshold. What it costs is the PRECISION of each kernel's mean: at 20 seeds
      the standard error of that mean is √(200/20) = **3.16×** the designed value.
    - **All stochastic arms are truncated to the SAME prefix**, even though RS completed all 200.
      Comparing a 200-seed RS mean against a 20-seed BO mean would give the arms unequal precision
      in a PAIRED test — the difference's variance would be dominated by whichever arm is noisier,
      which is an artifact of scheduling, not of the algorithms. Equal seeds is the only fair read.
      RS's full 200-seed rows remain committed and are reported as a precision check.
    - **Mandatory reporting:** every result carries the achieved seed count AND the mean per-kernel
      seed-mean SEM for its cell. A truncated study that does not show its own noise is a study
      that looks more precise than it is.
    - **The honest consequence:** a NON-significant result under truncation is weaker evidence of
      absence than the pre-registration intended — with 3.16× the noise, a real effect is more
      likely to be missed. Null results from this study are therefore reported as
      **UNDERPOWERED-NULL**, never as "no difference". A SIGNIFICANT result is not weakened by
      truncation: extra noise makes rejection harder, not easier, so anything that survives did so
      against a higher bar than designed.
    - **Cause, stated plainly:** wall-clock. The full 200-seed study is ~214 core-hours ≈ 27 h at
      8 threads, measured and profiled (182 RandomForest fits per trajectory). It did not fit the
      endgame budget. This is a TIMELINE-DRIVEN deviation, not a scientific one, and it is recorded
      as such in `DEVIATIONS_REGISTER.md` (DEV-12).
    - **Reversible at zero cost:** the rows are checkpointed and the study is re-shardable, so
      resuming to 200 seeds recomputes nothing. `results/study/RESUME_RUNBOOK.md`.

## §13 Pre-commit review revisions (folded from wf_14518dee-4f5, before first commit)

Resolved before commit: composite `fmffp` 3-level factor (fixes rank-deficient coding → OLS,
D-optimal designs, and 1-flip neighborhood all well-defined; §0.1/§0.3/§1.1/§8.2/§9.2); Wilcoxon
sidedness pinned (two-sided RQ-P1, one-sided RQ-P3) with the power caveat (§2/§3.3/§3.4); paired
Cliff's δ operationally defined and shared by effect-size and the Motif gate (§3.3/§3.4); BO RF
hyperparameters pinned here (§8.3); mandatory bounded pilot top-up + sensitivity re-run (§2); seed
spawn-key integer encoding + bootstrap-seed precedence (§0.4); reference-config budget accounting
uniform across arms (§3.1); incomplete-Friedman-block rule (§3.3); singular-OLS min-norm + degenerate
rules (§1.1/§8.2/§9.2); DOE explicit trajectory + ε-regularized D-criterion + ridge specifics
(§8.2); single-pass suspicious-config with rerun-fail handling (§7); RQ-P2 boundary/degenerate
branches + criterion restored to roadmap verbatim (§3.5); boundary-set is non-attrition (§2);
RQ-P3 analysis set defined (§3.4); routing tie-break (§3.3); Motif warm-start standardization +
total dedup (§8.4); de-scope cut rule + P3 estimate + forkserver lever (§10); endpoint re-measure
policy restored & pinned + carved out of §7 (§4/§7); golden band lower edge held at 50 ms (§6);
peak-RSS RUSAGE_SELF (§4); detect_leaks=1 leak audit restored (§5); auditor 20% sample seeded (§11);
generation-seed determinism (§9.1); regret_nofloor sensitivity column (§3.1); §7.4 dangling
reference corrected.
