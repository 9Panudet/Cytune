# PREREG_DOE_V2 — pre-registration for the DOE-engine v2 evaluation

**Status: COMMITTED BEFORE ANY VARIANT RESULT WAS READ.**
Written after Stage 0's defect determination (which is descriptive, uses no search and produces no
regret number) and before any variant existed in code. Changes to this document are numbered,
human-approved amendments, never silent — the same rule PREREG_PHASEP §12 operates under.

Governing documents that still bind and are not amended here: `PRODUCT_ROADMAP.md` (law),
`PREREG_PHASEP.md`, `docs/GUARANTEES.md`. Nothing in this exercise may change a study number, a
frozen table, or an audit verdict.

---

## §0. What is being decided

Whether cytune's shipped search engine should change. The default answer is **no**: the current
engine ships unless a variant clears §5's ship rule on **held-out real code**. "Nothing beat V0" is
a valid, publishable outcome and the exercise is designed to be able to return it.

---

## §1. The Stage-0 finding this evaluation is built on top of

Established before pre-registration, from structure and from the frozen tables:

1. The frozen designs (`_vendor/data/doe_designs_theta.json`) are D-optimal over
   **1,728 candidates with 13 parameters**.
2. A default (FP-strict) run may only **emit 576** of those, and only **11** parameters are
   non-constant over that set. `+contract` → 1,152/12. `--portable-flags` → 288/10.
3. Consequently the screen tier spends, under the default policy:
   `doe_7` **6 of 7** points (86 %), `doe_15` **11 of 15** (73 %), `doe_24` **16 of 24** (67 %)
   on configurations the run cannot emit.
4. `docs/CONTRIBUTING.md` line 101 states the rule this breaks: *"Spend budget only on configs this
   run could actually emit. Measuring a config the policy forbids burns measurement to produce a
   number the certificate must then refuse to act on."* `plan.walk_plan` obeys it; `plan.screen_plan`
   does not. **The rule is enforced in one of the two places the product spends budget.**
5. `plan.py`'s docstring defends the un-emittable rows as "what makes the fast-math signal
   reportable at all". **Measured, that defence does not apply to the tune design:**
   `worker.cmd_features` computes the features and the fast-math signal from
   `probe.probe_config_ids()` only. The tune design's fast-math rows reach no reported signal.
6. The remaining defence is additivity — that effects measured under fast-math transfer to strict
   FP. Measured on all 149 exhaustive tables (`results/doe_v2/stage0_additivity_probe.json`):
   median shared-effect bias 3.3 %, worst 35.7 % (`march=native` on INT), 30 % on FLAT+FM
   (`opt_level=-O3`). The selection consequence is a **coin flip, not information**: 51 kernels
   hurt, 44 helped, 54 unchanged; worst hurt +15.9 %, worst help −12.4 %.

**VERDICT: DEFECT**, on the budget rule (item 4), independently of the additivity result.

## §2. Variants

`V0` is the shipped engine, called through the product's own functions
(`probe.features`, `routing.route`, `plan.screen_plan/walk_plan/select_winner/confirm_winner`).
Variants override exactly one seam each and inherit the rest.

| id | name | what changes |
|---|---|---|
| **V0** | baseline | nothing. The shipped engine. |
| **V1** | policy-matched design | frozen D-optimal designs rebuilt **per emission policy**, each over its own candidate set with its own parameter count. Stage 0.2's fix. |
| **V2** | probe-augmented | V1 + the 17 probe rows enter the design criterion; the tune design is a Fedorov D-optimal **augmentation** conditioned on them. |
| **V3** | Bayesian-D | V2 + criterion `det(X'X + K)`, `K` = diagonal prior precision from the measured between-kernel variance of each factor's effect **on the training fleet only**, committed as data with the script that produced it. |
| **V4** | ordinal coding | V2 + orthogonal-polynomial (linear + quadratic) contrasts for `opt_level` and `funroll` instead of drop-first dummies. Same parameter count. |
| **V5** | low-budget axis pinning | V2 + at `B ≤ 16`, factors the fleet prior says are near-dead are pinned to their safe level **unless the probe shows signal on that axis**. |
| **V6** | sequential augmentation | V2 + the fixed escalation replaced by budget-aware D-optimal augmentation for interaction terms live in the current fit. Only bites at `B ≥ 32`. |
| **V7** | artifact-equivalence candidates | V2 + the design is built over equivalence classes of artifact hash, one representative per class. |

Combinations beyond the stated inheritance chain must be registered as their own named variant
before being run.

**The probe is FIXED at `probe_16` + reference in every Tier-1 variant.** It is the router's input
and `routing.py`'s thresholds are pre-registered against it; changing it would make this a test of
the router, not the engine. It is also where the fast-math signal comes from, so keeping it fixed
preserves that reporting unchanged (§1 item 5).

## §3. Metrics

**PRIMARY — `regret_emittable`** = `emitted_ns / min(median_ns over feasible AND policy-allowed) − 1`.
The denominator is the best answer the run could possibly have given under its own emission policy;
it is the only target a ship rule can act on. Mirrors PREREG_PHASEP §12 A-5a's emittable slice.

**SECONDARY, always reported alongside — `regret_all`**, same numerator, denominator over all
feasible configs including fast-math. Reported for the same reason Δ_strict always accompanies
Δ_all: the reader gets both, and the one the product can act on is named as such.

**CO-PRIMARY — `configs_measured`** = distinct non-reference configs queried. The reference is
observation 0 and free (PREREG_PHASEP §3.1). *Note the live CLI counts it, so live figures are
exactly 1 higher; C6 checks that offset is constant.*

Descriptive: `n_probe / n_screen / n_walk`, `n_paid_emittable`, route taken, emitted config id.

## §4. Design of the evaluation

**Replay.** Sealed ask-tell against the frozen `results/fleet` tables, freeze-hash verified against
`FREEZE_MANIFEST_V2.json` and with the §1.4 sanitizer overlay applied, in that order. An engine
that reaches the table other than through `query()` fails control C3.

**Split**, from the manifest `role` field written at the P-2 freeze:

| role | n | status |
|---|---|---|
| `training` | 129 | **development data — already seen.** Variants are tuned here. |
| `holdout-H` | 11 | confirmatory, synthetic |
| `R-anchor` | 9 | confirmatory, **real code — what the product runs on** |

**H and R are reported separately and are never pooled.** The class distributions differ (INT: 41
synthetic vs 0 of 9 real), so a pooled number would be dominated by the synthetic majority.

**Budgets.** Primary: the **routed** budget — what production actually spends. Secondary sweep at
forced `B ∈ {8, 16, 24, 32, 40}`, the range the router and `--preset` can produce.

**Seeds.** The product engine is **deterministic** given a table: the probe is fixed, the designs
are frozen data, and the ranking walk is a deterministic sort. One replay per (variant, kernel,
budget) is therefore exact, not a sample, and 200 seeds would be 200 identical rows. Any variant
introducing randomness must instead commit its design as frozen data built by a seeded script, so
the shipped engine stays deterministic. Pairing is by kernel.

**Statistics.** Paired **Wilcoxon signed-rank** over kernels, variant vs V0, with **Cliff's delta**
as the effect size, **Holm-corrected** across variants within each (role × budget) family. On R
(n=9) a Wilcoxon has almost no power; the ship rule below therefore does not depend on one.

**Auditor.** `stats-auditor` recomputes the winning variant's reported numbers from raw by an
independent script. Required diff exactly zero.

## §5. The ship rule — fixed now, applied without renegotiation

A variant ships **only if all of the following hold**:

1. **R-anchors, regret:** median `regret_emittable` does **not increase**, max does **not
   increase**, and **no individual anchor worsens by more than 1.0 percentage point**.
2. **R-anchors, cost:** `configs_measured` does **not increase on any anchor**.
3. **holdout-H:** median `regret_emittable` does not increase. (H is confirmatory but synthetic;
   it can veto, it cannot by itself justify.)
4. **No guarantee weakens.** G1 oracle, G2 sanitizer, G3 honest-flat, and every I1/I2/I3/I4
   invariant behave identically. The emitted config is always inside the effective policy.
5. **Live confirmation:** the nine-anchor ground-truth dogfood re-run live, and the live smoke gate
   green.

**A variant that wins on H and not on R does not ship.**

**Tie-break: prefer the simpler engine.** Equal regret and equal cost ⇒ V0 stays. A variant must be
strictly better on at least one primary metric while not violating any of 1–5.

## §6. Tier 2 — the gate it must pass before it is even built

Tier 2 (a static-feature model predicting a prior over the 11-coefficient effect vector) is built
**only if** Stage 3 shows headroom the Tier-1 winner leaves on the table — defined here as: the
best Tier-1 variant's median `regret_emittable` on R remains **above 1.0 %** *and* an oracle
variant that is given the true effect vector achieves materially less. Otherwise Tier 2 is not
built and the report says the ceiling was already reached.

If built, these bind:

- The model is fit on the **training fleet only**, leave-one-kernel-out.
- It **never transfers configs** — only a prior over the effect vector. Transferring configs is
  Motif+BO's failure mode: it won by warm-starting from siblings 9.7× enriched for the target's own
  template, and Dataset R has no siblings at all.
- The prior feeds **exactly two places**: `K` in V3's criterion, and the ridge prior of the fit.
- **HARD INVARIANT.** The model may only decide *where measurements are spent*, never what is
  emitted. `test_an_adversarial_prior_cannot_change_what_is_emitted` feeds a deliberately inverted
  / garbage prior and asserts (a) the emitted config is still inside the effective policy, (b) the
  oracle, sanitizer and emit-margin decisions are byte-identical to the no-prior run **given the
  same measurements**, (c) no certificate field changes except the design provenance.
- Unavailable or failing model ⇒ fall back to V3's fleet prior, then to classical D. The
  certificate records which prior was used.

## §7. Instrument controls — passed before any reading counts

`scripts/doe_v2/controls.py` (C1–C5) and `scripts/doe_v2/control_dogfood.py` (C6).

| id | kind | what it refuses to let pass |
|---|---|---|
| C1 | negative | a synthetic flat table must route honest-flat and spend only the probe |
| C2 | positive | a planted 2× lever on an emittable axis must be found, regret ≈ 0 |
| C2b | negative-of-the-positive | a 1.0× "lever" must **not** be claimed |
| C3 | cheat | the table must be unreachable through the sealed object |
| C4 | accounting | reference free, repeats free, paid count exact |
| C5 | real | on a real frozen table the emitted config is emittable and the denominator reachable |
| C6 | **cross-instrument** | the harness reproduces the **live** nine-anchor dogfood |

C6 status at commit time: **PASS** — 7/9 emitted configs identical, worst-case regret identical
(5.41 %), `configs_measured` offset a constant 1 (the free reference), and both differing anchors
are near-ties at +0.161 % and +0.024 %, inside the ~2 % rig noise floor.

## §8. What offline replay cannot answer, stated as a limit

The frozen tables record a screen-tier median per config and no endpoint-tier median. The endpoint
re-check (`plan.confirm_winner`) is therefore modelled as "feasible in the table confirms". A
variant that changed how often the endpoint tier *rejects* a winner could not be evaluated here.
None of V1–V7 touches that path. Stage 5's live dogfood is what closes this gap, and no variant
ships on offline evidence alone.

---

## §9. Amendments

### A-1 — the fit population is a separate seam from the design population (registered before Stage 2 ran)

**Why.** §2 as committed says only that the design changes. But the fast-math rows reach the engine
through **two** doors, and V1–V7 as written closes only one:

1. **the design** — which configs get measured. V1 closes this.
2. **the fit** — which measured rows inform the ranking walk. `worker.cmd_walk` fits on *every*
   feasible row in the table, so the probe's 10 non-strict rows keep entering the fit even after
   the design is policy-matched, carrying exactly the additivity assumption §1 item 6 measured to
   be a coin flip.

Leaving that implicit would let a V1-vs-V0 result be read as "the design fix worked" when half the
mechanism was untouched. It is registered rather than silently chosen, because which door matters
is precisely what is being measured.

**What is registered.** The fit population becomes an explicit suffix, applied to any variant:

| suffix | fit population | assumption |
|---|---|---|
| *(none)* | every feasible measured row, drop-constant columns (**what V0 does today**) | additivity across `fmffp` |
| **`+s`** | feasible measured rows the **policy allows**, 11-parameter strict model | none |

So `V1` and `V1+s` are both registered, and likewise for V2–V7. The ship rule in §5 is unchanged
and applies to whichever performs best.

**Prediction, recorded before the run** (so it can be wrong in public): `+s` helps most on
**FLAT+FM** and **INT**, where §1 item 6 measured the largest shared-effect bias (30 % and 35.7 %),
and is close to neutral on FLAT and LEVER-SEP.

### A-2 — a SECOND defect, found during Stage 2: the adaptive walk is starved at budgets 17–24

**The defect.** `plan._design` computes the design size as `N_d = min(24, B−1)`. The `B−1` is there
to reserve at least one point for the adaptive walk. When that size is not one of the three frozen
designs it falls back to `doe_24` — a **24-point** design — and `plan.screen_plan` then truncates
to `budget`, not to `N_d`. So for **every budget in [17, 24]** the screen consumes the entire
budget and **the walk gets nothing**. The reserve the formula exists to create is silently spent.

**Reachability.** `budget = 24` is `BUDGET_DOE (16) + BUDGET_FEAS_BONUS (8)` — any DOE-routed module
whose probe feasibility is under 75 %. Measured on the frozen fleet: **58 of 149 kernels** (53
training, 5 holdout-H, **0 of 9 R-anchors**).

**Why the live dogfood could not have caught it.** All nine real anchors route to budget 16 or 32,
neither of which is in the affected range. The defect is real and reachable, and the evidence that
it costs *real* users anything is currently zero. Both halves are reported.

**Controlled measurement** (same 136 tuned kernels, forced budgets, so the harder-kernel confound
that makes the routed comparison useless is removed):

| B | design | screen | walk | median regret | mean | worst |
|---:|---|---:|---:|---:|---:|---:|
| 23 | doe_24 | 23 | 0 | 3.95 % | 25.58 % | 516.53 % |
| 24 | doe_24 | 24 | 0 | 3.95 % | 25.58 % | 516.53 % |
| **25** | doe_24 | 24 | **1** | **1.46 %** | **3.29 %** | **46.31 %** |
| 26 | doe_24 | 24 | 2 | 1.06 % | 3.07 % | 46.31 % |

One additional measured configuration — the first walk point — moves median regret 3.95 % → 1.46 %
and worst-case 516 % → 46 %. Paired: **75 kernels worse at B=24, 0 better, 61 unchanged.**

**Registered fixes**, evaluated under §3–§5 exactly as the other variants, first in isolation on
V0 and then composed with the winner:

| id | fix |
|---|---|
| **W1** | cap the screen at `min(budget, N_d)` — smallest diff; drops one point by config_id order, which is arbitrary |
| **W2** | use the largest *available* frozen design of size ≤ `N_d` (B=24 → `doe_15`, screen 15, walk 9) — needs no new design |
| **W3** | build the missing size exactly (`doe_23`), so `N_d` is always available — most principled, one extra design per policy |

This is a defect, so *some* fix ships regardless of whether any Tier-1 variant does; the ship rule
in §5 selects among W1/W2/W3, and "V0 stays" means "V0 plus the chosen W".

### A-3 — W4 "probe-as-screen": POST-HOC, therefore EXPLORATORY. Recorded as such.

**Provenance, stated first because it determines the evidential status.** W4 was not designed. It
appeared as a **bug in W2**: `walk_reserve_screen` chose "the largest available design of size
≤ N_d", and the shipped design dict contains `probe_16` alongside the `doe_*` entries. At N_d=23 it
selected `probe_16` — a design already fully measured by the probe before the tune stage — so the
screen cost nothing and the whole tune budget fell through to the adaptive walk. The bug was found
by tracing an unexplained drop in `configs_measured`, not by the result looking good.

The bug is fixed (W2 now considers `doe_*` only). The behaviour it accidentally produced is kept
as its own variant because the question it asks is real: **the probe is a 17-point D-optimal design
that has already been paid for — is buying a second screen worth anything at all?**

**Evidential status.** W4 was written and run in the same step, after §2's variants were fixed.
It therefore has **no pre-registration** and its frozen-table results are **EXPLORATORY, not
confirmatory** — on training, on holdout-H and on R alike, because all three were read after the
variant existed. Nothing about the numbers below is invalidated by that; what is invalidated is any
claim that they are a confirmatory test.

**What would make it confirmatory.** Stage 5's live nine-anchor dogfood is a fresh measurement
against a real compiler and a real timer, not a replay of tables already in hand. That is the
confirmatory test for W4, and §5.5 already requires it. **W4 may not ship on offline evidence.**

**Mechanism, checked rather than inferred from the win.** W4 measures the SAME number of
configurations as V0 on all 149 kernels (difference exactly 0 everywhere), but spends a median of
**22** of them inside the emittable set against V0's **11**. The probe already estimates the main
effects; the second screen re-estimates them, and D-1 means 67–86 % of that re-estimation lands
outside the space the run may emit. Removing it is D-1's fix arriving through a different door.

**Known failure mode, not designed away.** W4 has no exploration at the tune stage — all of it is
in the fixed 17-point probe. Where the probe's fit is badly wrong the greedy walk chases a wrong
ranking: one training kernel (`fleet_INT_15_int_sumsq`, INT) regresses **+26.3 %**. Every other
regression across all 149 kernels is ≤ +2.6 %, and on R the two regressions are +0.26 % and
+0.02 %.

### A-4 — the SPLIT family: screen size as a parameter, not a constant. REGISTERED BEFORE RUNNING.

**Why.** V0 and W4 are the two endpoints of one axis — how much of the tune budget buys a fixed
screen design and how much buys the predicted-best walk. V0 spends 15 of 16 on the screen; W4
spends 0. Comparing only the endpoints answers "which extreme", not "what is the right split",
and the second question is the one an engine has to answer.

**The mechanism each endpoint is trading.** W4's single large failure is diagnostic:
`fleet_INT_15_int_sumsq` regresses +26.3 %, and on that kernel the probe reports `IF_probe = 0.034`
— separable — while the full-table classifier says **INT**, interaction-dominated. The probe
misreads the landscape, the greedy walk trusts an additive fit that is the wrong model, and it
chases a wrong ranking. V0 survives that kernel only because its fixed screen happens to contain a
good configuration the greedy walk never visits. **The fixed design is insurance against a probe
that misreads the landscape.** The question is what that insurance should cost.

**Registered variants.** `SPLIT(n)` uses the **V2 policy-matched, probe-augmented** design of size
`n` as the screen and spends the remaining budget on the walk:

| variant | screen | walk at B=16 | note |
|---|---:|---:|---|
| `SPLIT(0)` | none | 16 | W4, but with the D-1 fix applied to the walk's candidate set |
| `SPLIT(7)` | 7 | 9 | minimum insurance |
| `SPLIT(15)` | 15 | 1 | V0's split, with a policy-matched design |
| `SPLIT(24)` | 24 | 0 at B=24 | V0's split at the higher budgets |

Evaluated under §3–§5 unchanged. `configs_measured` is identical across the family by construction,
so this axis cannot buy regret with budget.

**Pre-registered prediction, recorded so it can be wrong in public:** the minimum of median regret
sits at a **small but non-zero** screen (`SPLIT(7)`), because W4's win is large and its failure mode
is real but rare; and the INT cell is where a non-zero screen earns its cost.

**Status: written before `SPLIT` existed in code and before any SPLIT result was read.**

---

*§0–§8 committed at Stage 1; no variant existed in code (commit `acea795`, which carries the
document's sha256). A-1 registered before Stage 2 ran. A-2 registers a defect found during Stage 2
together with its candidate fixes, before any of those fixes was evaluated. A-3 registers a variant
found POST-HOC and marks its offline results exploratory — the amendment is written after those
results were read, and says so rather than pretending otherwise. A-4 is registered before the
variants it names exist.*
