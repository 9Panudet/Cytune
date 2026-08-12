# PREREG_LAUNCH — pre-registration for the launch measurement protocol

**Status: COMMITTED BEFORE ANY REPEATED-DOGFOOD REPLICATE EXISTS.**
No replicate of the k≥5 campaign has been run, staged, or read at the time this document is
committed. The bound derived in §3 is defined here as a *formula over data that does not yet
exist*; its numeric value is filled in by `scripts/release/analyse_repeat.py` and by nothing else.

Governing documents that still bind and are not amended here: `PRODUCT_ROADMAP.md` (law),
`PREREG_PHASEP.md`, `PREREG_DOE_V2.md`, `docs/GUARANTEES.md`. **Nothing in this exercise may change
a study number, a frozen table, or an audit verdict.** Phase-1 is closed and is not re-litigated.

Amendments to this document are numbered and human-approved, never silent.

---

## §0. Why this document exists

`PREREG_DOE_V2.md` §5.1 fixed a per-anchor ship bound of **1.0 percentage point**: no individual
Dataset-R anchor may worsen by more than 1.0 pp. That rule decided the fate of six engine variants
and of `--probe-as-screen`.

It is not a rule the instrument can support. Two live runs of the **same unchanged 1.0.0 engine**,
`results/release/dogfood/` and `results/release/dogfood2/`, disagree on one anchor by **3.597 pp**:

| anchor | `dogfood` regret | `dogfood2` regret | Δ |
|---|---|---|---|
| fleet_R_09_predictor | 5.097 % | 1.500 % | **+3.597 pp** |
| the other eight | — | — | **0.000 pp (bit-identical)** |

Recompute:
`.venv/bin/python -c "import json,statistics as st; [print(d, [round(x['regret']*100,3) for x in json.load(open(f'results/release/{d}/REGRET.json'))]) for d in ('dogfood','dogfood2')]"`

A decision rule finer than the instrument's own reproducibility is not conservative, it is
arbitrary: which side of it a variant lands on is decided by run-to-run variation rather than by
the variant. This document replaces that rule with one derived from measurement.

**The correction can only loosen the bound, never tighten it.** A protocol change that made it
easier to reject variants would be indistinguishable from moving the goalposts after seeing the
results, so the direction is fixed here in advance.

---

## §1. What is being measured, and the shape of the noise

Regret is computed by looking the **emitted config id** up in that anchor's frozen 1,728-config
table. It is therefore **not a continuous noisy quantity**. Between two runs, regret changes *if and
only if* the search emits a different config. The observed 8-identical / 1-moved-3.6-pp pattern is
exactly this signature: the engine is trajectory-deterministic given its measurements, and
occasionally a measurement ordering flips one selection.

Two consequences bind the protocol:

1. **Dispersion must be reported as a discrete distribution, not only as a range.** For each anchor
   the campaign reports the *multiset of emitted config ids* over the K replicates and their
   frequencies, alongside the regret statistics. A range of "0.0–3.6 pp" over two configs and a
   range of "0.0–3.6 pp" over seven configs describe different instruments.
2. **A bound must be at least as large as the largest single-flip gap the instrument produces.**
   Anything smaller is decided by which config the search happened to land on.

---

## §2. A1 — the repeated dogfood campaign

### §2.1 Design

| | |
|---|---|
| units | the nine Dataset-R anchors, in fixed order (R_01…R_09) |
| arms | **D** = shipped default (second screen on) · **P** = `--probe-as-screen` |
| replicates | **K = 5 per arm**, 10 passes, 90 runs total |
| ordering | **arms interleaved by replicate**: D₁ P₁ D₂ P₂ D₃ P₃ D₄ P₄ D₅ P₅ |
| workspace | **fresh per (arm, replicate, anchor)** — never resumed, never reused |
| commit | one commit for all 90 runs; its sha is recorded in the campaign manifest at launch |
| rig | `scripts/measure_wrap.sh --verify-only` must exit 0 **before each replicate**; recorded |

**Why interleaved.** A thermal or background-load trend across a 7-hour campaign would alias onto
the arm factor if all D replicates ran before all P replicates. This is the same confound recorded
against this project on 2026-07-24, when a time-correlated slowdown could have aliased onto the
`-O1`/`-O3` factor because config id order correlates with it. Interleaving makes replicate index
the block and arm the within-block factor.

**Why anchor order is fixed rather than randomised.** Anchors are analysed per-anchor, never
pooled; a fixed order keeps replicates directly comparable and makes a monotone drift *visible* as
a trend across replicate index rather than dispersed into the anchor factor. Both arms see the same
order, so any order effect is common to both and cancels in the paired arm comparison.

**Why fresh workspaces.** A reused workspace resumes: the engine sees prior measurements and takes
a different, cheaper trajectory. One such run was discarded during DOE-v2 for exactly this reason
(49 configs vs 33). A replicate must be an independent run of the tool as a user would experience
it on a clean machine.

### §2.2 Disk discipline

A full pass costs ≈ 665 MB, of which ≈ 71 MB per anchor is `_so` + `_ccache` and ≈ 120 KB is
evidence. Free space at launch is ≈ 8 GB. After each anchor completes, and **only** after its
`certificate.json`, `certificate.txt`, `table.jsonl`, `artifacts.jsonl`, `build_manifest.jsonl`,
`cache_key.json` and `oracle.json` are verified present and non-empty, the runner prunes `_so/` and
`_ccache/` for that anchor. This is the D12 precedent (prune build caches of a completed run whose
measurement artifacts are verified intact), applied per anchor rather than per campaign.

A pruned workspace is recorded as pruned in the manifest. **No run is ever pruned mid-flight, and a
pruning failure aborts the campaign rather than continuing silently.**

### §2.3 What is reported

Per anchor, per arm:

- `regret` for each replicate; **median, min, max, spread = max − min** (percentage points)
- the multiset of emitted `config_id`s and their counts; `n_distinct_configs`
- `configs_measured` for each replicate; median and range
- the verdict for each replicate, and whether it was ever anything but the modal verdict
- wall seconds per replicate

Fleet headline, per arm:

- `M_k` = median over the nine anchors of replicate k's regret
- **median-of-medians** `median_k M_k`, with **range** `[min_k M_k, max_k M_k]`
- worst-anchor regret per replicate, with its range
- total `configs_measured` per replicate, with its range

**Every downstream document quotes the range. The single-run figure is never quoted alone.**

---

## §3. A2 — the re-derived ship bound

Defined now, computed by formula from A1's default arm (**D**) only. The P arm is a candidate under
test and cannot contribute to the bound that judges it.

Let `r[a,k]` be anchor *a*'s regret in replicate *k* of arm D, *a* = 1..9, *k* = 1..K.

```
s[a]      = max_k r[a,k] − min_k r[a,k]                      per-anchor spread, pp
S         = max_a s[a]                                       instrument reproducibility, pp
S_median  = median_a s[a]                                    reported alongside, never used as the bound
M[k]      = median_a r[a,k]                                  replicate k's fleet median
S_fleet   = max_k M[k] − min_k M[k]                          fleet-median reproducibility, pp
```

### §3.1 The bounds

| bound | value | replaces |
|---|---|---|
| **B_anchor** | `max(S, 1.0 pp)` | PREREG_DOE_V2 §5.1's flat 1.0 pp |
| **B_fleet** | `max(S_fleet, 0.0 pp)` | (new; §5.1 had no explicit fleet-median bound) |

`max(S, 1.0)` is written this way so the bound can only move outward. If the campaign were to
return a spread *below* 1.0 pp — i.e. if the instrument turned out to be tighter than the rule that
was already in force — the existing 1.0 pp bound stands unchanged and this exercise reports that
the original rule was defensible after all. That is a possible and reportable outcome.

### §3.2 What the bound applies to

**B_anchor and B_fleet govern LIVE comparisons only.** They are statements about what a single live
run of cytune can resolve.

Offline replay against the frozen tables is **deterministic**: the same engine on the same table
emits the same config every time, so an offline difference is exact and carries no run-to-run
error. Offline comparisons are therefore **not** re-judged against B_anchor. They keep their own
exact arithmetic.

But the two must be read together, and the report states this explicitly:

> An offline difference smaller than **S** is a true difference in expectation that a user cannot
> observe in one run. It may justify a change; it may never be advertised as something a user will
> see.

Determinism of the simulator does not confer resolution on the prediction it makes about a live
machine.

### §3.3 Comparisons are made between medians

Every live comparison under this protocol compares **per-anchor medians over K replicates**, never
single runs. The bound `B_anchor` is derived from single-run spread and applied to a
difference-of-medians, which is deliberately conservative: the median of five is a tighter
statistic than one run, so a difference that clears a single-run bound is comfortably real.

Secondary, reported but not decisive: a paired Wilcoxon signed-rank test across the nine anchors on
per-anchor medians, with Cliff's delta, exactly as `scripts/doe_v2/analyse.py` already computes.
Nine pairs cannot carry a decision; it is reported so the reader can see the direction and its
weakness rather than have it hidden.

---

## §4. A3 — the `--probe-as-screen` decision rule

`--probe-as-screen` is currently **implemented, tested, and off by default**. It becomes the
default **only if all of the following hold**. Any single failure leaves it opt-in.

1. **R live, regret:** no anchor's median regret (over K replicates) worsens by more than
   **B_anchor**, *and* the median-of-medians does not worsen by more than **B_fleet**.
2. **R live, cost:** median `configs_measured` does not increase on any anchor.
3. **H offline, regret:** on the 11 holdout-H kernels, replayed against the frozen tables at every
   budget, median `regret_emittable` does not increase. H is confirmatory and synthetic: **it can
   veto, it cannot by itself justify.**
4. **Fleet offline, no tail regression:** across all 149 frozen tables × all budgets, no budget's
   worst-case `regret_emittable` worsens beyond the B1 gate bound (§5). This is the check that
   would have caught D-2, which reached 58/149 kernels and 0/9 anchors.
5. **No guarantee weakens.** G1 oracle, G2 sanitizer, G3 honest-flat and every I1–I4 invariant
   behave identically; the emitted config is always inside the effective policy; the live smoke
   gate is green.
6. **Strictly better on at least one primary metric** (median regret on R, worst-case regret on R,
   or `configs_measured`), while violating none of 1–5.

**Tie-break: the incumbent stays.** If the evidence cannot separate the arms, the shipped default
does not change. Recorded honestly and against interest: on a pure count-of-moving-parts metric
`--probe-as-screen` is the *simpler* engine — it removes the second design lookup, the design cap,
and the walk-reserve arithmetic. That fact is reported but does not override rule 6, because
"simpler" was invoked in PREREG_DOE_V2 §5 as a tie-break *toward the incumbent*, and reversing its
direction after seeing which way it points would be exactly the renegotiation this project forbids.

**If it does not become the default, `docs/USER_GUIDE.md` states why in these terms:** measured
better nearly everywhere, by an amount smaller than one live run can resolve.

---

## §5. B1 — the fleet-wide offline replay gate

A standing pre-tag gate, not a one-off. Zero live measurement.

| | |
|---|---|
| population | all 149 frozen kernel tables (129 training + 11 holdout-H + 9 R) |
| budgets | every budget the product can route to: **16, 24, 32, 40**, plus **8, 64, 128** as the DOE-v2 registered grid |
| metrics | `regret_emittable` (primary), `regret_all`, `configs_measured`, `n_paid_emittable` |
| baseline | a committed JSON of per-(kernel, budget) results for the current engine |
| verdict | **FAIL** on any of the conditions below |

**Fail conditions, fixed now:**

- **F1** any budget's **median** `regret_emittable` over the 149 kernels worsens by more than
  **0.10 pp** versus the baseline;
- **F2** any budget's **worst-case** `regret_emittable` worsens by more than **1.0 pp**, or by more
  than **10 %** relative, whichever is larger;
- **F3** any **individual kernel × budget** cell worsens by more than **5.0 pp**;
- **F4** total `configs_measured` over the population increases at any budget;
- **F5** the fraction of paid measurements spent on **emittable** configs
  (`n_paid_emittable / configs_measured`) **decreases** at any budget;
- **F6** the freeze-hash guard or the sanitizer overlay fails to apply.

F3 is the D-2 detector: D-2 moved 58 kernels, worst case 516 % → 46 %, and 0 of 9 anchors. A
per-cell bound catches a defect confined to a budget band that the median and the anchors both miss.

**Baseline provenance.** The baseline is regenerated only by an explicit, recorded act (a numbered
amendment here, or a release), never as a side effect of a failing gate. A gate whose baseline can
be refreshed to make it pass is not a gate.

---

## §6. Instrument controls — passed before any reading counts

Inherited and re-run, per `PRODUCT_ROADMAP.md` §6 ("new instruments get positive AND negative
controls before their readings count"):

| id | control | passes when |
|---|---|---|
| **L1** | rig verify before every replicate | `measure_wrap.sh --verify-only` exit 0, recorded per replicate |
| **L2** | fresh-workspace check | each run's workspace did not exist before the run; asserted, not assumed |
| **L3** | prune-safety | evidence files present and non-empty before any prune; a prune failure aborts |
| **L4** | commit pin | every one of the 90 runs reports the same `cytune` version and source-tree sha |
| **L5** | replay-vs-live agreement | for each anchor, the offline replay of arm D at the routed budget emits a config whose table time is within the same table; disagreement is reported, not silently reconciled |
| **L6** | B1 positive control | a deliberately regressed engine (the pre-D-2-fix `screen_plan` cap) must FAIL the B1 gate; if it passes, the gate is vacuous |
| **L7** | B1 negative control | the unmodified engine must PASS against its own baseline with zero diff |

L6 and L7 are the planted-lever / known-flat pair this project requires of every new instrument.

---

## §7. What would make this exercise report "nothing changes"

Stated in advance so that the outcome is not read as failure:

- If **S ≤ 1.0 pp**, the existing bound was already defensible; it stands, and the report says the
  3.597 pp `predictor` disagreement was the extreme of a distribution the rule could tolerate.
- If `--probe-as-screen` fails any of §4.1–4.6, it stays opt-in and the guide records why.
- If the B1 gate finds no regression, it ships as a standing gate with an empty finding list — a
  gate's value is that it *can* fail, not that it *did*.
- If the repeated campaign shows the fleet headline is stable to within a few tenths of a point,
  the flagship number gets a narrow range and the launch claim is *stronger*, not weaker.

**"The instrument is better than we feared and nothing changes" is a valid, publishable outcome of
this exercise.** So is its opposite.

---

## §8. Amendments

**A-1 (before first use, before any gate result existed) — F5 restated as a ratchet.**
F5 was first drafted as *"any kernel × budget cell measures a config the effective policy could not
emit"*. That is a condition **the shipped engine fails by construction**: Stage 0 of DOE-v2
established that under the FP-strict default the screen design spends 86 % / 73 % / 67 % of
`doe_7` / `doe_15` / `doe_24` on un-emittable configs (D-1), and the report deliberately did *not*
fix it because every policy-matched variant made real-code regret worse. A gate that red-lights on
day one is not a gate; it is a permanently-suppressed alarm.

F5 now reads: the **fraction** of paid measurements spent on emittable configs may not decrease.
That is the same defect measured as a ratchet — D-1 cannot get worse, and any future fix shows up
as the gate improving rather than as the gate finally going green.

Recorded rather than silently edited, and recorded with the direction of the change: this amendment
makes the gate **easier to pass** for the current engine, which is exactly the kind of change that
must never be invisible.
