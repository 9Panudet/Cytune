# PREREG — RQ1 unit-of-analysis (clustered n) — §5.1/§5.2 operationalization

**Status:** PROPOSED — pending human ratification at the RATIFY-RQ1 checkpoint (this session).
Once ratified in-session (recorded verbatim in STATE), this is SEALED and is referenced by
`PREREG_RQ1` (Step 1.5.1) and the §1.5.2 power simulation. **Committed before any RQ1 comparison runs**
(the comparison is Step 1.5; this pre-registration long precedes it).

**Classification:** a §5.1/§5.2 **operationalization** of the analysis "unit" (which the roadmap leaves to
§0.5: *"Primary unit: the hot loop / function"*; §5.2: *"n = units"*). It pins the analysis ROW at the
feasibility-independence level. It is **NOT** the single Appendix-B-12 amendment (UNSPENT) and **NOT** a
D-series change: it touches **no pinned constant** — seeds ≥ 20, K_final = 30, and budget B (proposals)
are all unchanged and remain non-levers.

---

## 0. §4.5 floor-20 classification (gating resolution) — POWER-TIME FLOOR (b)

**Question:** is §4.5's "floor 20" a HARD PRE-RUN GATE (the corpus must contain ≥ 20 *independent* units
before the experiment may run — which a 2-package corpus can never satisfy → expand codebases now) or a
POWER-TIME FLOOR (n feeds the power computation; adequacy is decided by the power sim)?

**§4.5 verbatim:** *"Primary n = units (target ~25, floor 20). Statistical power is **simulated before
running** (Step 1.5.2): paired-Wilcoxon power at n ∈ {20, 25}, δ ∈ {0.2, 0.4, 0.6}, variance from the
Phase-0 pilot; requirement: power ≥ 0.8 at the pre-registered MDE, **else expand units first**. A negative
result is defined in advance (§5.3) and accepted as valid data."*

**Classification: (b) POWER-TIME FLOOR.** Three independent roadmap-verbatim anchors:

1. §4.5 states **no run/no-run count gate**. Its only remedy clause — *"else expand units first"* — is
   conditioned on **power < 0.8**, not on n < 20. Floor-20 is the lower anchor of the simulated grid
   n ∈ {20,25}; the binding adequacy criterion is the power threshold.
2. §4.3 **shortfall rule** verbatim: *"if curation yields **< 25** admissible units, the reduced n and its
   power consequence are **pre-registered** (links Step 1.5.2) — the small-n limitation is owned explicitly,
   not papered over."* The roadmap's explicit mechanism for sub-target n (< 25 subsumes < 20) is
   **pre-register + power**, not a stop. A hard gate would make this rule incoherent.
3. The **1.1.2 ↔ 1.5.2 loop**: Step 1.1.2 *"on shortfall: pre-register reduced n + power consequence
   (→ 1.5.2)"*; Step 1.5.2 *"power ≥ 0.8 … **else expand units (→ 1.1.2) before running**."* "Expand units"
   is a **conditional remedy gated on the power result**, executed before the 1.5.3 run — not a pre-1.2 gate.

**The floor is also MET at the granularity §4.5 counts.** §4.5's "n = units" is the nominal admissible-unit
count (§0.5: primary unit = function; §5.2: n = units). The curated corpus has **30 nominal admissible
units ≥ 20 floor (≥ 25 target)** → satisfied as the roadmap counts. The clustered independent-n (module=17,
fold=11) is a STRICTER inference choice ratified in §2 of this pre-reg to defeat pseudo-replication; §4.5
does not gate on it — its adequacy is governed by the power sim at the actual clustered n.

**Three faithful adaptations (pre-registered):**
- (i) the power sim runs at the **actual clustered n (module=17, fold=11)**, extending §4.5/§1.5.2's nominal
  {20,25} grid — module/fold is the ratified inference unit. Strictly more conservative.
- (ii) **variance from the NEW corpus** (measured at 1.2.4), **not the Phase-0 pilot** — CF-3 established the
  Phase-0 ratio does not characterize the corpus's 1.2–1.6× band, so pilot variance would be unrepresentative.
- (iii) the gate is brought **earlier — to 1.2.4** (before 1.3/1.4/1.5), so driver/optimizer/search compute
  is not sunk into an underpowered design. Still satisfies §4.5 "simulated before running."

**The expansion fork is NOT dismissed — it is DEFERRED** to the power decision (§4.5's exact remedy "expand
units first"), executed at the 1.2.4 viability gate (§5). If the new-corpus variance yields power < 0.8 at
the MDE for n=17/11, we **STOP and fork to add a 3rd/4th codebase THEN** — we do not pre-emptively expand
before measuring the variance the decision depends on.

**Consequence: PROCEED to 1.2 (CF-4 gate first).** This pre-registration constitutes the committed §4.3 /
Step-1.1.2 shortfall pre-registration (reduced clustered n + power consequence → 1.5.2), recorded before any
1.2 driver work.

---

## 1. The problem this pre-registration fixes

The directive matrix applies the 5 Θ Cython directives **per `.pyx` module** — one `cythonize` per module
per directive combo (§1.5 split-pipeline). Therefore every drivable **function-unit inside one module
shares an IDENTICAL feasibility label** (same compile/sanitizer/oracle outcome for a given directive set)
and a **correlated timing response** (same source, same codegen, same memory system; functions differ in
which directives bite, so timing-correlation is looser than feasibility but still module-coupled).

Consequence: the **43–44 function-units are NOT 43–44 independent samples.** A paired Wilcoxon run over
n = 43–44 correlated rows is **n-inflated → anti-conservative → a falsely-significant RQ1.** The effective
independent-n is the **cluster count**, not the function count.

- **Feasibility-independence clusters by MODULE** (separate cythonize): **n = 17.**
- **LOMO / maintenance-independence clusters by FOLD = codebase** (§0.5 grouping factor; §5.4): **n = 11.**

A nominal n of 25–44 does **not** by itself buy statistical validity; the clustered effective-n is the
real adequacy gate.

## 2. Ratified operationalization (human-ratified at this checkpoint)

| Role | Granularity | n | Independence basis |
|---|---|---|---|
| **PRIMARY endpoint** | **MODULE** (`.pyx` cythonize-unit) | **17** | feasibility-independence — one cythonize per module |
| **SENSITIVITY / robustness** | **FOLD** (codebase / subpackage) | **11** | LOMO / maintenance-independence (§0.5, §5.4) |
| Tertiary (the §5.2-named secondary) | function-unit × seed | 43–44 | reported as a LABELED sensitivity only — **never** the primary test |

**RQ1 is declared ROBUST iff all three §5.3 criteria hold at the PRIMARY (module) level AND the directional
result is preserved at the FOLD (sensitivity) level.** The module level is the gate; the fold level guards
against a result driven by within-fold module correlation. The function×seed level is descriptive only.

This **harmonizes** §5.1/§5.2 (*"n = units"*) with §5.4 (*folds = the LOMO independence unit*): the
function-level "unit" of §0.5/§5.2 is retained as the *measurement* granularity but **aggregated to the
independence unit for inference**, exactly as §5.2's anti-pseudo-replication clause already does for seeds
(*"the (unit × seed)-level analysis is reported as a labeled secondary sensitivity analysis"*) — extended
one level up because the module, not the function, is the feasibility-independence unit.

## 3. Aggregation procedure (frozen here; executed at §5.3)

Per §5.3, winning per-(unit, method) configurations are **re-measured fresh at K_final = 30 on paired
inputs** before any of this aggregation — headline numbers never rest on cached search-phase timings.

1. Per (function-unit *u*, method *m* ∈ {BO, RS}, seed *s* ≥ 20): best-found **feasible** log-runtime at
   budget B.
2. Per (function-unit *u*, method *m*): **median over seeds** → x[u, m]. *(= §5.2 seed aggregation.)*
3. Per function-unit: paired difference **d[u] = x[u, BO] − x[u, RS]** (log-runtime; negative ⇒ BO faster).
4. **PRIMARY (module):** D_mod[k] = **median over the function-units in module k** of d[u]. **n = 17.**
   Paired one-sided Wilcoxon signed-rank (α = 0.05, BO better) + Cliff's δ + BCa 95% CI (10,000 resamples)
   on {D_mod[k]}.
5. **SENSITIVITY (fold):** D_fold[j] = **median over the modules in fold j** of D_mod[k]. **n = 11.** Same
   three statistics on {D_fold[j]}.

**RQ1 PASS** ⇔ at the PRIMARY (module) level: (1) Wilcoxon significant at α = 0.05 one-sided, (2) Cliff's
δ > 0, (3) BCa 95% CI of the median paired difference excludes 0 — **and** the FOLD-level direction agrees
(criteria 1–3 reported, direction must not reverse). All statistics are recomputed from raw `/results`
files by `stats-auditor` (zero-diff), never hand-entered.

## 4. Honest small-n limitation (binding — recorded, not papered over)

- §4.1b *"≥ 25 hot-loop units across ≥ 10 codebases"* is a **corpus-COMPOSITION** requirement (corpus
  manifest; nominal drivable kernels). The curated set holds **≥ 25 NOMINAL units** → §4.1b MET.
- The **INDEPENDENT n is capped by the corpus structure**: **2 packages → 11 folds → 17 modules.**
  **≥ 25 INDEPENDENT units is UNACHIEVABLE** from 2 packages (sklearn, scipy). At the independence level,
  **n = 17 (module) / 11 (fold) are BELOW the §4.5 floor of 20.**
- Therefore the earlier "≥ 25 met, no shortfall" (Step 1.1.2 ledger) is **true only NOMINALLY**. At the
  inference granularity this **IS** the §4.3 / §1.1.2 shortfall condition: nominal ≥ 25 met, but the
  independent n is short → the reduced (independent) n and its power consequence are **pre-registered here**
  and confronted at the viability gate (§5), per the shortfall rule ("the small-n limitation is owned
  explicitly, not papered over").

## 5. VIABILITY GATE (binding, early — before sinking 1.3/1.4/1.5 compute)

As soon as **Step 1.2.4** yields the **new-corpus per-unit variance** (NOT the Phase-0 pilot variance), run
a **CLUSTERED power preview** (the §1.5.2 simulation, brought forward as a go/no-go):

- paired-Wilcoxon power at **n = fold (11) AND n = module (17)**, using the **measured new-corpus variance**
  and the **pre-registered MDE** (§4.5: effect on log-runtime / Cliff's δ; the MDE itself is fixed at
  PREREG_RQ1 / §1.5.1 — not chosen here, to avoid post-hoc selection).
- **If n ≈ 11–17 cannot clear power ≥ 0.8 at the MDE → STOP and surface the fork to the human BEFORE
  1.3/1.4/1.5.** Options: **(i)** add genuinely-independent codebases (more folds) to raise the cluster
  count, or **(ii)** accept + pre-register an underpowered test (with both a positive and a negative read
  interpreted under the explicit power caveat).
- **Do not discover this after the 3–4 day search run.** Both the §1.5.2 power simulation and the §5.3 test
  use this clustered n.

## 6. What is NOT changed

Seeds ≥ 20 (fixed, not a lever); K_final = 30 (fixed, never adaptive); budget B in proposals (fixed);
the §5.3 three-criteria gate; RS-without-replacement baseline; the §5.2 log-runtime metric; nested LOMO
selection (§5.4). The single B-12 amendment remains **UNSPENT**. The pre-registered reduction levers (B = 40,
unit count) are untouched here.

---

*Raw-data dependency:* the n = 17 module count and n = 11 fold count are fixed by the corpus structure
(see `results/characterization/CORPUS_UNIT_LEDGER.md` and the curated set
`results/characterization/CURATED_UNIT_SET.md`). The variance and the power preview are produced at Step
1.2.4 and committed to `/results` before any power number is quoted.
