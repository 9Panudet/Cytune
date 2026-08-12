# cytune v0 — INTERIM routing policy (FROZEN before first use)

**Status:** INTERIM heuristic — pending the P3 study. **Authority:** PREREG §12 A-4e.
**Frozen:** 2026-07-25, before any `cytune` run against any module.
**Every cytune output carries the label `routing: INTERIM heuristic — pending P3 study`.**

---

## 0. What this document is, and what it is NOT

This is a **fixed, written-down-in-advance** mapping from probe features to a tuning engine and
budget. It exists because v0 has to route *something*, and the thing that is supposed to do the
routing does not exist yet.

It is **NOT** the §9.2 probe→class classifier. That classifier must be fit on **fleet tables only**,
committed with a SHA-256 hash before P4 begins, and evaluated for RQ-P2 **exactly once** against
that hash. A-4d forbids the CLI from touching fleet/H/R at all, so v0 cannot fit or use it.

The governance consequence, stated explicitly because it is the point that could quietly go wrong:
**using this interim policy does NOT consume the one-shot RQ-P2 evaluation.** v0's routing decisions
are not evidence for RQ-P2 and are not a "first look" at the routing question. When the real
classifier is fit and hashed, RQ-P2 is still unspent.

This policy is derived ONLY from (a) standing v1 findings and (b) pilot development data (demoted to
development status by A-2b). It is **never** tuned against fleet, H, or R — not now, not later. If it
turns out to route badly, that is reported as a v0 limitation, not fixed by looking at study data.

## 1. Inputs — the probe features

The probe measures the pre-registered 16-point D-optimal main-effects design (`probe_16` in
`results/prereg/doe_designs_theta.json`) plus the reference config.

**§9.2 features (verbatim, unmodified):**

| Feature | Definition |
|---|---|
| `delta_probe` | max/min over **feasible** probe medians |
| `if_probe` | 1 − R² of the §0.1 main-effects fit on the probe's feasible rows |
| `feas_frac` | feasible probe rows / probe rows attempted |

**Degenerate-probe rule (§9.2, applied verbatim):** if feasible probe rows ≤ (model rank after
dropping constant columns) + 2, then `if_probe = NA`. NA is its own feature value, never imputed.

**v0-interim derived signals** — these are NOT §9.2 features and are labelled as such wherever they
appear. They exist because v0 must decide about fast-math, which §9.2's three features cannot express:

| Signal | Definition |
|---|---|
| `delta_probe_strict` | max/min over feasible probe medians restricted to `fmffp[0] == "off"` |
| `fm_signal` | (best strict median) / (best all median); > 1 means fast-math looks faster |
| `feas_signal` | `feas_frac < 0.75` — a materially infeasible region was hit during the probe |

## 2. The routing table (fixed; read top-to-bottom, first match wins)

| # | Condition | Route | Budget (extra measured configs) |
|---|---|---|---|
| R0 | reference config infeasible, or < 4 feasible probe rows | **ABORT — cannot certify** | 0 |
| R1 | `delta_probe` ≤ 1.10 | **HONEST-FLAT EXIT** | 0 |
| R2 | `if_probe` is NA | **DOE**, conservative | 16 |
| R3 | `delta_probe` ≥ 1.5 and `if_probe` ≥ 0.25 | **INTERACTION** → BO if gated in, else DOE | 32 |
| R4 | `delta_probe` ≥ 1.5 and `if_probe` < 0.25 | **DOE** (separable lever) | 16 |
| R5 | otherwise (1.10 < `delta_probe` < 1.5) | **DOE**, modest | 16 |

**Feasibility modifier (applies to any route that tunes):** if `feas_signal` is true, the budget is
raised by 8 and the certificate reports the infeasible fraction prominently. It never changes which
engine runs, and it never relaxes the correctness rule.

**Fast-math modifier:** `fm_signal` is *reported* always and *acted on* never unless the user passed
`--allow-fast-math`. See §4.

## 3. Why each threshold — and how much to trust it

Every number here is inherited, not invented for v0. That is deliberate: an invented threshold would
be an unregistered scientific choice.

- **1.10 (R1)** is A-1b's IF-evaluation floor: 5× the measured ~2% noise floor of this rig. Below it,
  a "speedup" is noise/noise. Using it as the honest-flat cutoff means v0 declines to tune exactly
  where the study says the signal is indistinguishable from noise. **This is the most important row
  in the table** — v1's standing finding is that real code is usually flat, so R1 is expected to be
  the common outcome, and being right here matters more than being clever anywhere else.
- **1.5 (R3/R4)** is the A-2a boundary between MID and the lever-bearing classes (LEVER-SEP/INT).
- **0.25 (R3/R4)** is the A-2a `IF_strict` boundary separating LEVER-SEP from INT.
- **0.75 (feasibility modifier)** is the complement of A-2a's `FEAS` flag threshold
  (`infeas_frac ≥ 0.25`).

**Trust level: LOW, and knowingly so.** These thresholds were pre-registered for classifying a
kernel from its **full 1,728-config table**. Here they are applied to a **16-point probe estimate**
of the same quantities. §9.2 itself says the probe is "a **coarse** router input, validated
empirically by RQ-P2, not a precise estimator" — and RQ-P2 has not been run. So the thresholds are
principled but their *transfer to probe scale is unvalidated*. Concretely: `delta_probe` is a
max/min over 16 points and is a **downward-biased** estimator of the full-table Δ, so R1 will
sometimes call a mildly tunable kernel flat. v0 prefers that direction — a missed speedup is a
disappointment, a false speedup claim is a lie.

## 4. Fast-math is opt-in, always

Fast-math (`fmffp = ("on", "NA")`) changes floating-point semantics and is **feasibility-gated**:
in this study it routinely produces the fastest configs *while failing the oracle* (a measured
example: `fm_sum`, `fm_ratio` 3.987, oracle-failing on 576/1728 configs, Δ_strict = 1.0).

v0 rules, in force regardless of routing:
1. Fast-math configs are **excluded from winner selection and from the adaptive predicted-best
   walk** unless `--allow-fast-math` is passed.
   *(Precision added 2026-07-25, before the first cytune run of any kind — the original wording
   "excluded from the candidate set" was ambiguous about fixed designs. It is resolved in the
   stricter-reading direction for what may be EMITTED, and the resolution is: **fixed
   pre-registered designs — the 16-point probe and the DOE screen — are measured exactly as
   specified**, because measuring is not emitting, dropping points would break the designs'
   D-optimality, and it is precisely those measurements that make `fm_signal` reportable at all.
   Nothing about which configs may be emitted changes.)*
2. Even with `--allow-fast-math`, a fast-math config is emitted **only if it passes the same oracle**
   as everything else. Opt-in changes what is *tried*, never what is *accepted*.
3. Whenever the emitted config uses fast-math, the certificate carries the tolerance report: oracle
   class, rtol/atol, and how the tolerance was derived.
4. `fm_signal` is reported even without the flag, phrased as an *unclaimed* observation — e.g.
   "fast-math configs appeared ~2.1× faster in the probe but were not evaluated for correctness;
   re-run with --allow-fast-math to have them oracle-checked." v0 never reports an unverified
   speedup as an available one.

## 5. Engine selection

- **DOE** (PREREG §8.2) is the default and the only engine guaranteed present.
  **Known v0 gap, stated up front:** the committed `algorithms.doe` implements screen → fit →
  predicted-best ranking walk. The §8.2 **fold-over escalation** (interaction-augmented D-optimal
  design on the top-3 |effect| factors) is *not implemented* — it is a P3.3 refinement carrying its
  own TDD, scheduled after the P-2 freeze. v0 ships the baseline and says so. Implementing it now
  would mean editing a sealed-study algorithm arm mid-campaign, which is a worse risk than shipping
  a documented gap.
- **BO** (PREREG §8.3) ships **only** if a `bo-math-reviewer` pass for this use returns PASS. If it
  does not, R3 falls back to DOE at the same budget and the certificate says so. No silent fallback.
- **Motif+BO** (PREREG §8.4) is **excluded from v0**. RQ-P3 has not been run, so shipping it would
  assert a transfer benefit that no evidence supports.

## 6. What the router may never do

1. Never emit a config that failed the oracle — no budget, flag, or route can reach that state.
2. Never read fleet/H/R data, at routing time or any other time.
3. Never present the interim routing as validated, or its class guess as a measured class. The probe
   yields a *guess*; the study's classes are measured from full tables. Outputs say "probe suggests",
   never "this kernel is".
4. Never silently change route mid-run. The route is decided once from the probe and recorded in the
   certificate; if a fallback fires (e.g. BO absent), that is printed and certified, not hidden.
