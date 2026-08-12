# PRODUCT_ROADMAP.md — cytune (v2.0)

**A production Cython-directive × GCC-flag autotuner, grounded in a fair, fully-measured 4-algorithm
study on a controlled, beyond-dispute benchmark.** This document is the spec. **It is law.** On any
conflict with any other file (including `CLAUDE.md`), this document wins. `CLAUDE.md` tells the agent
how to work; this file tells it what is true.

Correctness is absolute and non-negotiable: **a config that fails the oracle is infeasible regardless
of its speed. The product never emits it.** Faster-but-wrong is rejected. The sale is *correct,
faster, and easier*.

---

## §0 — Goal change, standing results, hard rules

### §0.1 Recorded goal-change (supersession, not goal-post movement)
- Roadmap v1.x's paper goal (RQ1: does SMAC3-RF+EIC beat RS on the real-library corpus?) is
  **closed**. Its answer stands untouched and is never re-litigated: **the accessible real-code
  corpus is FLAT (median Δ_all 1.338 / Δ_strict 1.209 < 1.5, robust at n=7/8/9) and underpowered
  (n=9 « 12/26/103), the two real levers (boundscheck elision ~3×; −O3/native vectorization ~2.5×)
  are separable (interaction ≤ 4.6%), and BO ≤ RS is the recorded, mechanism-grounded inference.**
  Terminal record: `results/ProjectReport.md`, `results/resultNew.md`, `results/CLOSEOUT_FINAL_LOG.md`.
  The v1 roadmap's normative text remains addressable at `git show v1-final:Motif+BO-Roadmap.md`
  (annotated tag on the Phase-1 closeout commit); every "v1 §x.y" citation in this file resolves there.
- v2.0's goal is a **product**: the `cytune` CLI, plus the controlled study that decides what goes
  inside it. This supersession is a human decision, recorded here as the goal-change amendment.
  Nothing in v2.0 revises a v1 measured result.

### §0.2 New research questions (pre-registered fresh; none is v1's RQ1)
- **RQ-P1 (routing matrix):** For each MEASURED landscape class (A/B/C, §3.4) and evaluation budget
  B ∈ {8, 16, 32, 64, 128}: which of {RS, DOE, BO, Motif+BO} minimizes regret-to-true-optimum, with
  what effect size and significance?
- **RQ-P2 (router efficacy):** Does a cheap pre-registered landscape probe (§8.2) route a *new*
  kernel to the right algorithm — i.e., routed regret ≈ oracle-routed regret, and ≤ the best single
  fixed algorithm — on held-out kernels?
- **RQ-P3 (Motif value):** Does motif/graphlet-feature warm-starting (leave-one-kernel-out transfer)
  reduce BO regret at small budgets? If not, **Motif is dropped from the product** — a valid,
  desirable answer.

### §0.3 Hard rules (each one exists because its absence produced a false result somewhere in v1)
1. **Correctness absolute.** Oracle-fail ⇒ `feasible = 0` in the table; search happens in feasible
   space; the CLI never emits an infeasible config. Fast-math configs are feasibility-gated exactly
   as in v1 §3; the bit-preserving axis (Δ_strict) is always reported alongside Δ_all.
2. **Class membership is MEASURED, never asserted-by-construction.** A kernel is *designed toward*
   a class but *assigned to* a class only by measured properties of its own full table against the
   pre-registered thresholds (§3.4). Intended-vs-measured is a committed ledger.
3. **Pre-register before measure.** Thresholds, metrics, tests, budgets, seeds, the probe set, and
   the golden scale policy are committed to `/results/prereg/PREREG_PHASEP.md` **before** the first
   fleet kernel is measured. Post-hoc protocol changes are recorded deviations, never silent.
4. **Sealed-replay fairness.** Algorithms are compared **only** by offline replay against identical
   frozen tables through the sealed ask–tell interface (§5.1). No algorithm ever triggers a live
   measurement during the study.
5. **Raw before aggregate.** Every quantitative claim traces to a committed raw file + a recompute
   command + an auditor stamp. A number without a pointer does not exist (v1 §6.1, unchanged).
6. **Human checkpoints.** P-1 (pilot), P-2 (dataset freeze), P-3 (routing matrix), P-4 (release)
   are STOP-for-human gates. The agent never self-passes them.
7. **Honest negatives are valid exits** at every level: a class that fails to separate, an
   algorithm that never wins, a Motif layer that adds nothing — all are reportable products of the
   study, not failures of it.

### §0.4 Inherited findings ledger (binding context; do not re-derive, do not contradict)
- Real-code flatness/separability + the two-lever mechanism (§0.1 numbers).
- **Power table (stats-auditor zero-diff, MC N=10 000, one-sample Cliff's δ):** power ≥ 0.8 needs
  n = **12** (δ=0.6), **26** (δ=0.4), **103** (δ=0.2). This table is the normative source for all
  sample-size derivations in v2.0. Raw: `results/power/power_table*.json`.
- **Noise floor (CF-4 baseline):** within-subprocess CI@30 ≤ 1% at ~500 ms goldens (csr 0.36–0.82%,
  pava 0.996%); between-process rstd ≤ 0.26–0.39%; at ~74 ms a 3.6% slow-outlier subprocess
  population exists that vanishes at ~500 ms. This directly informs the §4.5 golden-scale tradeoff.
- **Replay/basin finding:** on 16-config grids, median near-optimum basin K/N = 0.25; RS
  evals-to-basin 1.9–8.5. (Why small grids cannot separate methods by evals — motivates full-table
  replay at real budgets.)
- **Defect series D1–D6** (D1 zero-embedding, D2 bare-import, D3 smac import, D4 rig thermal,
  D5 screen-vs-endpoint contamination, D6 in-place re-callability). D1, D2, D5, D6 were silent.
  Every v2.0 mechanism below that guards one of these cites it.
- **Protocol revisions v1.2 (quiesce-all), v1.3 (median-of-N endpoint), v1.4 (per-rep regen)** —
  all remain in force.
- **β directive policy:** in-source `# cython:`/`@cython` pins are stripped so the matrix fully
  controls Θ; the as-shipped config remains one point of Θ; a cythonize failure ⇒ feasibility-0 for
  the whole directive combo, cached once (never retried per flag).
- **v1 golden reference config:** `-O2 -march=x86-64 -ffp-contract=off`, `fast_math=off`,
  as-shipped Cython directives — remains the reference/golden build config for every kernel.

---

## §1 — Inherited, validated infrastructure (binding)

### §1.1 Timing rig (v1.4 — unchanged)
`perf_counter_ns` immediately around the kernel call only; input construction outside the timed
region; fresh subprocess; no bare imports timed, ever (D2). Per-rep input regeneration from the
committed recipe, untimed, for in-place kernels (D6). Endpoint = median over N=3 fresh
subprocesses, each with in-process K (v1.3); K_final = 30 for endpoint-tier measurements; the
frozen-reference re-measure policy (threshold_x in MAD units, capped re-rolls) applies at the
endpoint tier.

### §1.2 Carry-forward ledger (all bind Phase P)
- **CF-1 quiesce-all / phase split:** compile and measurement never overlap; during every measured
  run the compile cores are idle; the measurement core owns DRAM bandwidth. In Phase P this is
  realized as a strict per-kernel **compile-phase → measure-phase** split (§4.4).
- **CF-4 verified-quiet baseline:** `measure_wrap.sh` gates every timed run (no_turbo=1, governor
  performance, cpu3+SMT-sibling isolated, THP ∈ {madvise, never} assert — fail-loud on drift);
  frequency stability recorded. The host-prep state is asserted, never assumed.
- **CF-5 C++ sanitizer obligations:** Phase-P synthetic kernels are C-Cython by default. If any
  C++ kernel enters the fleet, the per-unit C++ sanitizer-clean + `detect_leaks=1` audit
  obligations apply unchanged (v1 mini-I-3 rig).
- **CF-2/CF-3 (v1 corpus-specific)** are retired as corpus facts but their *lessons* persist as
  §0.3-5 and §4.5.

### §1.3 Oracle (v1 §3 — unchanged mechanism)
Per-kernel `oracle.json`, frozen before any search: output classes bit-exact (int/label outputs)
and toleranced (float outputs), tolerance mechanically derived =
`max(10 × observed cross-repetition deviation under the reference config, a pre-justified domain
floor)`; exception identity by canonical type (subclass never matches); fast-math configs
feasibility-gated on the toleranced comparison and excluded from the Δ_strict axis. The oracle
check runs **inline with measurement** (§4.3) so every table row carries its feasibility bit.

### §1.4 Sanitizer policy (v1 §3.3 — unchanged)
ASan+UBSan feasibility gate with `detect_leaks=0`; verdicts memoized per safety class (6-dim key),
endpoint full-config guard wired in; the dedicated `detect_leaks=1` audit for anything with a
non-trivial allocation surface. Zero speculative suppressions.

### §1.5 Environment
Pinned Podman image **X′ (`motifbo-env:phase1`, digest `d45e33b0…`)**; all builds and runs
in-container; `-ffp-contract` always explicit; 12 GB container ceiling; TOOLCHAIN.lock /
requirements.lock unchanged. Any image change requires the v1 additive-layer + byte-identity
procedure and a recorded transition.

---

## §2 — Search space Θ (inherited verbatim)

Θ = 32 Cython-directive combinations × 54 GCC-flag combinations = **1,728 configs per kernel**.
- Cython (5 binary directives): `boundscheck`, `wraparound`, `cdivision`, `initializedcheck`,
  `nonecheck` → 2⁵ = 32.
- GCC (5 factors): `opt_level` ∈ {−O1, −O2, −O3}, `march`, `funroll`, `fast_math`,
  `ffp_contract` (conditional on `fast_math`) → 54 combinations.
- **Normative enumeration:** the exact 54-combination GCC enumeration is inherited **verbatim**
  from Roadmap v1 §2.3 and must be copied into **Appendix A** of this file at Step P0.2 from the
  in-repo v1 file — never re-derived from memory. The conditional-`ffp_contract` structure and the
  |Θ| = 1,728 invariant are unchanged.
- The reference/golden config (§0.4) is one point of Θ. β policy (§0.4) governs how in-source
  directive pins are handled.

---

## §3 — The benchmark dataset (the new core)

### §3.1 Composition and sample-size derivation
- **Dataset A (separable / flat):** target 30 kernels whose measured landscape is additive or flat.
- **Dataset B (highly interactive):** target 30 kernels with strong directive×flag interactions.
- **Dataset C (rugged / deceptive):** target 30 kernels where greedy/local search from the default
  is misled (multi-modal or deceptive feasible landscape).
- **Dataset R (real-code anchor):** the 9–10 v1 survivor kernels, extended to full 1,728 tables.
  R anchors the study to reality and is expected (not forced) to land in class A.
- **Held-out set H:** ≥ 15 additional synthetic kernels (≥ 5 per intended class) + Dataset R are
  **excluded from P3 entirely** and used only for P4 CLI acceptance (RQ-P2).
- **n = 30/class is derived, not chosen:** the §0.4 power table requires n = 26 at δ = 0.4
  (medium, the pre-registered MDE for per-class pairwise tests); 30 = 26 + attrition margin
  (kernels lost to construction failure, oracle failure, or boundary assignment). Pooled n = 90
  powers δ ≈ 0.25. This derivation is cited in PREREG_PHASEP and ends the "enough data?" debate
  by construction.

### §3.2 Kernel requirements (every kernel, no exceptions)
1. Real Cython (`.pyx`) exercising the **real mechanism of each directive** — array indexing
   (boundscheck), negative indexing (wraparound), integer division (cdivision), memoryview init
   (initializedcheck), None-typed params (nonecheck), FP loops (fast_math / vectorization /
   ffp_contract). No directive may be trivially dead across the whole fleet.
2. A §4.4-conformant driver; deterministic golden under the reference config; oracle-classifiable
   outputs (§1.3); a scale knob placing golden runtime in the **50–80 ms band** (§4.5).
3. Single-module, closure-trivial (no external cimports beyond numpy) — vendoring and the 1,728
   builds stay cheap.
4. Deterministic: fixed seed inputs via committed recipes; bit-identical across ≥ 5 fresh reps at
   the reference config (fold-membership-style gate before the kernel counts).
5. Generator-produced with a committed spec per kernel (mechanism mix, sizes, seeds) — the
   generator + spec is the reproducibility story for the dataset itself.

### §3.3 Class-targeting mechanisms (design intent — real compiler mechanisms, not contrivance)
- **A:** streaming/bounds-dominated or compute-bound-flat kernels (the mechanisms v1 measured in
  real code).
- **B:** checks-inhibit-vectorization coupling (boundscheck payoff only under −O3+march);
  cdivision × fast_math on division-heavy FP; wraparound × −O3 pointer arithmetic — documented,
  genuine interactions.
- **C:** cache-boundary + unroll/march non-monotonicity; icache-bloat traps (march+funroll hurts);
  feasibility-cliff islands (fast-math-infeasible regions shaping a deceptive feasible landscape).

### §3.4 MEASURED class assignment (the anti-"rigged-dataset" rule — normative)
Assigned from each kernel's own frozen full table, against thresholds committed in PREREG_PHASEP
**before any fleet kernel is measured** (defaults below; the pilot may recalibrate them **once**,
as a pre-registered amendment, before the fleet):
- **A:** interaction-variance fraction (saturated-ANOVA on log-runtime over the feasible table)
  **< 10%**.
- **B:** interaction fraction **≥ 25% AND Δ_all ≥ 1.5**.
- **C:** greedy-from-default (best-improvement 1-flip hill-climb on the feasible table) terminates
  **≥ 15% above the true feasible optimum**, OR the feasible landscape has **≥ 2 local optima**
  under the 1-flip neighborhood.
- Kernels matching no class (or two) → the **boundary set**: reported, excluded from per-class
  tests, usable descriptively. The **intended-vs-measured confusion table** is a committed
  deliverable (P-2).

### §3.5 Dataset artifacts
Per kernel: `spec.json` (generator inputs), source + driver + input recipe, `oracle.json`, the
full table (§4.4 schema), the class assignment record. Fleet-level: the confusion table, the
survival ledger, dataset hashes. At P-2 the dataset is **frozen** (hash-committed); P3 reads only
the frozen copy.

---

## §4 — Measurement protocol (the full-table campaign)

### §4.1 Two tiers (pre-registered)
- **Screening tier (all 1,728 configs):** 1 fresh subprocess per config; in-process K adaptive
  **5–10** with early stop at CI half-width ≤ **2%** of the median (the v1 §1.4.3 rule); report
  median + CI. This tier defines the replay landscape (§5.1).
- **Endpoint tier (decisions):** v1.3/v1.4 median-of-3-subprocess, K = 30 — for the **top decile**
  of each kernel's feasible table and for **every algorithm-selected winner** during P4
  verification. The **screen-vs-endpoint agreement** on the top decile (rank stability of the
  optimum set) is computed and reported per kernel — the standing D5 guard.

### §4.2 Multi-objective capture (free — same runs, no extra measurement)
Per config: execution time (§4.1), **peak RSS** (`getrusage` of the measurement subprocess),
**.so size** (stat after build), **compile time** (cythonize + gcc wall, logged at build). All
four land in the table; time is the primary study objective; the others are characterized and
exposed as `cytune --objective` options (§8). No multiplicity games: RQ-P1 significance testing
is on time only.

### §4.3 Correctness inline
Every screening-tier run executes the oracle comparison against the golden; the row records
`feasible ∈ {0,1}` + a failure-reason class (cythonize-fail / build-fail / sanitizer /
oracle-mismatch / crash / timeout). Cythonize-fail ⇒ feasibility-0 for the entire directive combo,
cached once (β policy). Sanitizer verdicts per §1.4 safety-class memoization.

### §4.4 Campaign mechanics
Per kernel, strictly phased (CF-1): **(1) build phase** — 32 cythonize (directive-cached) →
1,728 gcc builds, parallel on the compile cores, logging compile time + .so size;
**(2) measure phase** — all 1,728 screening runs on the isolated core under `measure_wrap`, no
compilation anywhere; **(3) endpoint phase** — top-decile re-measure. Tables are **append-only,
crash-safe, resumable** (parquet/JSONL, one row per config with a rig fingerprint + timestamps);
STATE updated per kernel; the survival ledger updated per gate.
**Table schema (minimum):** kernel_id, config_id, the 10 factor values, feasible + reason,
screen{K, median_ns, ci_halfwidth}, endpoint{medians×3, endpoint_ns} (nullable), peak_rss_kb,
so_size_b, compile_s, oracle_hash_match, rig_fingerprint, ts.

### §4.5 Golden-scale tradeoff (50–80 ms) — stated, mitigated, pre-registered
500 ms goldens (v1) are infeasible at 1,728 configs × ~100 kernels (≈ 2+ h/kernel of pure kernel
time). The 50–80 ms band keeps a kernel's screening phase ≈ 10–15 min at the cost of entering the
regime where v1 measured a ~3.6% slow-outlier subprocess population. Mitigations (binding):
(a) screening decisions tolerate 2% CI by design — class thresholds act on 10–300% effects;
(b) all *decisions* (top-decile ordering, winner verification) use the endpoint tier;
(c) a pre-registered **suspicious-config re-measure rule**: a config whose screening median is a
> 3× outlier against its 1-flip neighbors is re-run once in a fresh subprocess before the table
freezes (guards a D5-class transient without post-hoc cherry-picking);
(d) the per-kernel screen-vs-endpoint agreement stat (§4.1) is the standing check that the screen
was decision-grade.

### §4.6 Compute envelope
≈ 35–50 min/kernel (build ≈ 5–10 min parallel; screen ≈ 10–20 min; endpoint ≈ 10–15 min) ×
~120 synthetic + R-extension ⇒ **≈ 3–4 days machine time**, resumable, overnight-capable. The
replay study itself (P3) is pure computation on frozen tables — hours, zero new measurement.
Pre-registered de-scope lever if the envelope is exceeded: fleet 120 → 105 (attrition margin
first); **never** the seeds, tiers, or thresholds.

---

## §5 — Algorithms and the replay study

### §5.1 Sealed ask–tell replay interface (fairness mechanism)
`table.query(config) → (feasible, screen_median, …)` is the **only** capability an algorithm has.
Identical frozen tables, identical feasibility, identical noise realization for all four
algorithms. Regret is computed against the table's **true feasible optimum** (exhaustively known).
A conformance test proves no algorithm can access anything but `query` (positive control: a
cheating stub that peeks is caught by the harness).

### §5.2 RS — uniform without replacement over Θ per seed; determinism test (same seed ⇒ same
sequence). (v1 §1.4.1 unchanged.)

### §5.3 DOE — pre-registered fractional-factorial screen (16–32 runs; resolution-IV or D-optimal
over the 10 factors with `opt_level` 3-level), additive main-effect fit → predicted-best →
confirmation eval → **fold-over escalation on ambiguity** (aliased or near-tie effects). All design
choices fixed in PREREG_PHASEP; the fold-over rule is part of the protocol, not a post-hoc patch.

### §5.4 BO — SMAC3-RF + EIC exactly per v1 §2.1–2.2 (finally built): log-runtime target; σ-floor
10⁻³ log-units; feasibility weighting α = EI·P̂(feasible) with add-one Laplace smoothing; μ/σ from
feasible observations only; infeasible runtimes never imputed (information flows only through P̂);
1-in-4 random interleave; the 8-config initial design; conditional-`ffp_contract` native in the RF.
**TDD against hand-computed fixtures (red→green) + a `bo-math-reviewer` pass are gates** before BO
enters the study.

### §5.5 Motif+BO — §5.4 warm-started across kernels via motif/graphlet features of the kernel
source. The in-repo `motifbo-graph` extractor is built under the v1 §0.6 **hard-fail contract**:
extraction failure excludes the kernel from the Motif arm with a recorded reason — never a zero
vector (D1). Transfer protocol = **leave-one-kernel-out**: the target kernel's own table is never
in its prior; held-out kernels (H, R) are never in any prior. If RQ-P3 shows no value, Motif is
dropped from the product; the finding ships.

### §5.6 Study design (RQ-P1, RQ-P3 — normative)
- **Primary metric:** regret@B = best-found-feasible-time(B) / true-feasible-optimum-time − 1, at
  B ∈ {8, 16, 32, 64, 128}; secondary: evals-to-within-τ-of-optimum, τ = 2%.
- **Seeds ≥ 200** per (algorithm × kernel) — free under replay.
- **Tests (per class × budget):** Friedman across the 4 algorithms on per-kernel mean regret →
  Holm-corrected pairwise Wilcoxon; α = 0.05; effect sizes (Cliff's δ) reported alongside p.
  n = 30/class powers pairwise δ = 0.4 (§3.1).
- **RQ-P3 endpoint:** paired Motif+BO vs BO regret at B ∈ {8, 16} (where priors matter), across
  the fleet minus holdouts, LOKO.
- **stats-auditor** independently recomputes the full result matrix from the frozen tables —
  required diff exactly zero — before P-3 is presented.

---

## §6 — Governance (unchanged machinery, new objects)

- **STATE_PHASEP.md** per v1 §6.4 schema; updated at every step boundary; cold-start resumable.
- **Prereg register:** PREREG_PHASEP.md (thresholds, tiers, metrics, tests, budgets, seeds,
  golden-scale policy, suspicious-config rule, DOE design, BO fixtures list, probe set) — committed
  before the fleet; any later change is a numbered, human-approved amendment.
- **Survival ledger:** per-kernel per-gate pass/drop with reasons (construction, determinism,
  oracle, class assignment, table completeness).
- **Auditors (§6.5 unchanged):** validation / bo-math / stats / measurement subagents, read-only,
  independent recompute, zero-diff required at each checkpoint; `scrutinize` before any report
  leaves the repo; `debug-mantra` on any red gate; `post-mortem` after any validated fix.
- **Evidence rules** (v1 discipline + the hard-task tripwires): worst-case reporting, never
  proxy-as-proof, count-before-"all", positive/negative controls on every new instrument (the
  generator, the replay harness, the probe), favorable surprises treated as alarms.

---

## §7 — Phase plan (P0–P5) with exit criteria

### P0 — Governance + specs (no construction before this is committed)
- P0.1 This file + new CLAUDE.md committed; goal-change recorded in STATE.
- P0.2 Appendix A populated verbatim from v1 §2.3 (Θ enumeration).
- P0.3 PREREG_PHASEP.md committed (everything in §6's prereg list).
- **Exit:** prereg hash in STATE; auditors acknowledge the register.

### P1 — Generator + pilot (representative-first) → **CHECKPOINT P-1**
- P1.1 Kernel generator + spec format; **instrument controls:** a planted-effect kernel (known 2×
  lever) detected by the pipeline, and a known-flat kernel reading flat (positive/negative control
  for the whole measurement chain).
- P1.2 Pilot fleet: 5 kernels/intended-class + 2 Dataset-R anchors through the **full** pipeline
  (1,728 table + oracle + both tiers + class assignment).
- P1.3 Pilot report: intended-vs-measured separation, timing precision at 50–80 ms
  (screen-vs-endpoint agreement), per-kernel wall-clock vs the §4.6 estimate, any threshold/scale
  recalibration (as the single pre-registered amendment).
- **Exit / STOP:** human approves thresholds + scale + fleet go.

### P2 — Fleet campaign + freeze → **CHECKPOINT P-2**
- P2.1 Generate + measure ~120 synthetic kernels; extend Dataset R to full tables.
- P2.2 Measured class assignment; confusion table; boundary set; survival ledger.
- P2.3 Hold out H (≥15 synthetic) + R from P3; freeze the dataset (hashes committed).
- P2.4 measurement-auditor samples ≥ 20% of tables (re-derive from raw); zero-diff.
- **Exit / STOP:** human approves the frozen dataset + class counts (attrition vs n=26 floor
  checked per class; if a class lands < 26, present the §3.1 power consequence before P3).

### P3 — Algorithms + replay study → **CHECKPOINT P-3**
- P3.1 Sealed replay harness + conformance/cheat test.
- P3.2 RS, DOE, BO (TDD + bo-math-reviewer gate), Motif+BO (extractor hard-fail contract) built.
- P3.3 The full replay: ≥200 seeds × 5 budgets × 4 algorithms × fleet; regret curves;
  per-class tests per §5.6; RQ-P3 LOKO analysis.
- P3.4 stats-auditor zero-diff on the full matrix.
- **Exit / STOP:** human receives the **routing matrix** + the Motif verdict and decides the
  product routing.

### P4 — The product: `cytune` → **CHECKPOINT P-4**
- P4.1 Build §8 pipeline; unit tests on every component.
- P4.2 **Acceptance:** end-to-end on H + R (never seen in P3): probe → route → tune → verify →
  certify; the CLI's measured speedups + certificates are themselves raw-committed. RQ-P2 verdict:
  routed regret vs oracle-routing vs best-fixed-algorithm.
- P4.3 Regression suite in CI; docs + quickstart.
- **Exit / STOP:** human release decision on the acceptance evidence.

### P5 — Final report
- PHASEP_REPORT.md + HTML (from committed JSON only, consistency-asserted): dataset construction +
  confusion table, routing matrix with regret curves, Motif verdict, CLI acceptance, every number
  MEASURED with raw + recompute + auditor stamp; detailed per-phase action+result logs in
  `results/` for the human's records.

---

## §8 — Product spec: `cytune`

### §8.1 Pipeline
`cytune tune <module.pyx> --driver <driver.py> [--objective time|memory|size|compile]`
1. **Ingest:** vendor the module; build the reference config; capture the golden; derive the §1.3
   oracle automatically (tolerance derivation + floors; bit-exact where outputs are integral).
2. **Probe:** the pre-registered ~16-config screen → interaction/Δ estimate → class guess.
3. **Route:** per the P3 routing matrix (expected: A/flat → DOE path, ~12–20 builds; B → BO;
   C → BO with restarts; Motif warm-start iff RQ-P3 proved value). Budget defaults per class from
   the matrix; user-overridable.
4. **Verify:** endpoint-tier re-measure of the winner (median-of-3, K=30) + oracle + sanitizer
   (opt-in full).
5. **Certify + emit:** directive header + GCC flags + measured speedup vs baseline + a
   **correctness certificate** (oracle class, tolerance, configs rejected as infeasible).
   Fast-math is opt-in only and always accompanied by the tolerance report.

### §8.2 Hard guarantees
- Never emits a config that failed the oracle — under any flag, any objective, any budget.
- Reports honestly when the landscape is flat: "no worthwhile speedup found (Δ < x%); best safe
  config = reference" is a first-class, tested output — the v1 finding says it will be the common
  case on real code, and the product's honesty there **is** the differentiator.
- Every claim in `cytune`'s output is reproducible from its own emitted artifacts.

---

## §9 — Risks (named now, owned by a phase)
1. **Class construction fails to separate** (B kernels measure separable) → caught at P-1 by the
   confusion table; the single pre-registered threshold/mechanism amendment is the remedy; if B
   remains unpopulatable, that is a *finding* about the domain (interactions are rare even when
   sought) and the study proceeds with the classes that exist.
2. **50–80 ms noise** → §4.5 mitigations; P-1 measures the screen-vs-endpoint agreement before the
   fleet spends anything.
3. **BO implementation error** → §5.4 TDD fixtures + bo-math-reviewer are hard gates; the sealed
   harness cheat-test guards the comparison itself.
4. **Motif extractor fragility** → hard-fail contract (D1); droppable by RQ-P3 without harming the
   product.
5. **Envelope overrun** → §4.6 pre-registered de-scope lever (fleet size only).

---

## Appendix A — Θ enumeration (populated at P0.2, verbatim from Roadmap v1 §2.3)

> Provenance: copied verbatim (2026-07-08) from `git show v1-final:Motif+BO-Roadmap.md`,
> section 2.3 (the v1 root file is removed from the tree by the §0.1 goal change; the tag
> `v1-final` = Phase-1 closeout commit `7121727` keeps the normative v1 text addressable).
> v2.0 annotations appear only in blockquotes like this one; everything else is the v1 text.

### 2.3 Search space Θ (exact enumeration and dimensionality)

Structural template: OpenTuner's GCC autotuner — choose among `-O0..-O3`, then per `-f` flag decide on/off/omit, plus bounded `--param`s; OpenTuner reports speedups up to 2.8× across 7 projects / 16 benchmarks (Ansel et al. 2014) [V]. We instantiate a bounded, conditional version:

**Per-unit Cython directives (pinned Cython 3.x semantics; defaults and risk wording verified against current docs [V]):**

| Directive | Default | Search values | Verified risk note |
|---|---|---|---|
| `boundscheck` | True | {True, False} | False: out-of-range indexing "may instead cause segfaults or data corruption" (Cython docs) [V] |
| `wraparound` | True | {True, False} | False: negative indices neither checked nor handled — possible segfaults/corruption (docs, paraphrased) [V] |
| `cdivision` | False | {True, False} | False = Python `//`/`%` semantics + ZeroDivisionError, at a penalty of up to ~35% per the docs [V]; True = C truncated semantics, **no zero-divisor check** — semantics change on negative operands and zero divisors is probed by the oracle edge-suite (§3.1) |
| `initializedcheck` | True | {True, False} | False: uninitialized-memoryview access unchecked [V] |
| `nonecheck` | False | {True, False} | default already False; included to span the safe direction too [V] |

⇒ 2⁵ = **32 directive combinations** per unit. (`cpow` is pinned to the Cython-3 default `False` and excluded from Θ — it changes result *typing*, which is an oracle-definition hazard rather than a performance knob. Trade-off: forgoes a minor optimization axis for a stable oracle.)

**Per-unit C flags (GCC 13.x pinned):**

| Flag dimension | Values | Notes |
|---|---|---|
| `opt_level` | {-O1, -O2, -O3} | -O0 excluded: never competitive, wastes budget. **-Ofast excluded as a dimension** — it is exactly -O3 + `-ffast-math` (+ newer extras), i.e. redundant under this factorization; this also makes the unresolved -Ofast-deprecation question (§0.7 item 9) operationally moot. Composition verified against the pinned manual at Step 0.1.5. |
| `march` | {x86-64 (baseline), native} | `native` on Comet Lake enables AVX2/FMA. IEEE-preserving in itself, but FMA availability interacts with contraction — controlled below. |
| `funroll_loops` | {omit, on (-funroll-loops), off (-fno-unroll-loops)} | OpenTuner's on/off/omit pattern [V]; IEEE-preserving. |
| `fast_math` | {off, on (-ffast-math)} | Unsafe by design; gated by §3.2, never banned a priori. |
| `ffp_contract` | {off, fast} — **conditional: active only when `fast_math=off`** | Always passed explicitly (§0.7 correction: GCC's default is `fast`; we never rely on `-std`). When `fast_math=on`, contraction is already permitted via the fast-math pipeline, so the dimension collapses. The conditional is handled natively by the RF surrogate (§2.1). |

C-flag count: `fast_math=off`: 3·2·3·2 = 36; `fast_math=on`: 3·2·3 = 18 ⇒ **54**.

**Base per-unit space: |Θ| = 32 × 54 = 1,728.**

> **v2.0 note:** v1's *extended space* (escalation to ≈ 1.13 × 10⁷ via 8 curated `-f` flags) was a
> Phase-1 contingency and is **retired** in v2.0: |Θ| = 1,728 is fixed for the whole Phase-P study
> (dataset, replay, product). The v1 "joint corpus space" note also carries over: per-kernel tuning
> is independent; there is no Cartesian joint space.
>
> **Canonical config_id order (normative for every table, design, and tie-break):** config_id =
> 0-based index of the tuple in the lexicographic product of the dimensions **in the exact order
> listed above** (boundscheck, wraparound, cdivision, initializedcheck, nonecheck, opt_level, march,
> funroll_loops, fast_math, ffp_contract), each dimension's values in the exact order listed above
> (booleans: True before False), with the conditional collapse: when `fast_math=on`, `ffp_contract`
> takes the single value `NA`. The enumeration script and its |Θ|=1,728 self-check are committed at
> P1.0 and are the sole source of config_ids.

## Appendix B — Class thresholds (normative copy of §3.4; versioned with any P-1 amendment)

Version 1 (P0, 2026-07-08 — the pre-registered defaults; the pilot may recalibrate **once**, as a
numbered pre-registered amendment, before the fleet):

- **A (separable/flat):** **Δ_all < 1.10 (flat-by-Δ; Amendment A-1b) OR** interaction-variance
  fraction **IF < 10%**, where IF = 1 − R² of the main-effects-only OLS fit on log(screen median)
  over the kernel's feasible table rows. [**Version 2, Amendment A-1b (2026-07-09):** IF is evaluated
  only when Δ_all ≥ 1.10 = 5× the 2% noise floor; below it IF = noise/noise is meaningless, so a
  sub-1.10-Δ kernel is class A directly. Correctness fix to the estimator. See PREREG §12 A-1.]
- **B (highly interactive):** **IF ≥ 25% AND Δ_all ≥ 1.5**.
- **C (rugged/deceptive):** greedy best-improvement 1-flip hill-climb from the reference config on
  the feasible table terminates **≥ 15% above the true feasible optimum**, OR the feasible landscape
  has **≥ 2 τ-prominent local optima** (τ = 2%) of which at least one lies ≥ 15% above the true
  feasible optimum.
- Kernels matching no class (or two) → the **boundary set**: reported, excluded from per-class
  tests, usable descriptively.

Exact operational definitions (estimators, neighborhoods, edge cases, tie-breaks) are normatively
fixed in `results/prereg/PREREG_PHASEP.md` §1 — committed before any fleet kernel is measured.

## Appendix B — Class thresholds (normative copies of §3.4, versioned with any P-1 amendment)

## Appendix C — Standing citation discipline
The v1 verified-citation corrections (§0.7 of v1) remain binding wherever cited; any new external
claim in Phase-P reports goes through the same verify-before-cite pass.
