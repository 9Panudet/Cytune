# CLOSEOUT_FINAL_LOG.md — action + result log for the human's decision (F6 reframe + F7 real auditors)

The detailed record of the final two-gap close. Companion artifacts: `results/ProjectReport.md` (narrative),
`results/ProjectReport.html` (visual, consistency-asserted), `results/resultNew.md` (full result report),
`results/characterization/ProjectReport_data.json` (single source of truth, built from committed raw).

---

## 1. F6 — RQ1′ replay reframe (statistical-correctness fix)

**The misframe (before).** The replay's numbers recompute exactly, but the *framing* — "RS wins 8/8 non-flat,
RS is hard to beat" — read as an **"RS beats DOE" horse-race**. That is (a) attackable by a reviewer and (b)
apparently in tension with §5 (separability ⇒ a structured screen is the domain-appropriate tuner).

**The corrected statement (after).** The measured content is that **the near-optimum basin on the 16-config
grids is wide**, so on grids this small *no* search method can win by evaluations, and endpoint **quality is
~tied**. This is the §4 flatness / §5 separability finding expressed as a search trajectory — a **corroboration
of the easy landscape**, not an "RS beats DOE/BO" result.

**Median K/N (from committed raw, `delta_probe/*__endpoint.json`, N=16 per grid):**

| unit | near-opt K | basin K/N | RS E[evals] to basin | DOE endpoint quality (pred/t_best) |
|---|---|---|---|---|
| _k_means_elkan | 1 | 0.06 | 8.50 | 1.036 (3.6% off — K=1 single-config basin) |
| sparsefuncs_fast (csr) | 4 | 0.25 | 3.40 | 1.010 (within τ) |
| _binning | 1 | 0.06 | 8.50 | 1.100 (10% off — fast-math-instability config) |
| _predictor | 4 | 0.25 | 3.40 | 1.013 (within τ) |
| _shortest_path (floyd) | 8 | 0.50 | 1.89 | 1.007 *(flat certificate)* |
| _online_lda_fast | 1 | 0.06 | 8.50 | 1.000 (exact best) |
| _traversal (cc) | 4 | 0.25 | 3.40 | 1.001 (within τ) |
| _isotonic (PAVA) | 5 | 0.31 | 2.83 | 1.000 (exact best) |
| _ppoly | 2 | 0.12 | 5.67 | 1.000 (exact best) |

**Overall:** median K = **4**, **median K/N = 0.25**; RS evals-to-basin median **3.4** (range 1.89–8.5). A
balanced main-effect screen needs **≥ 8 evals** to estimate 4 factors on a 16-point grid, so RS's short hitting
time is below any structured screen's fixed cost **as a matter of grid size + basin width, not method quality.**
Endpoint quality: DOE lands within τ on **6/8** non-flat units (median 1.006); worst is binning at 10% (the
fast-math-instability config); RS reaches the exact best within its 16-eval budget. Recompute:
`python3 scripts/corpus/build_report_data.py` (block `rq1prime.basin` / `rq1prime.quality`); auditor-verified (§2).

**The sign-test, correctly labeled + demoted.** "RS expected evals-to-basin < DOE's fixed 9 on all 8 non-flat
units, p = 0.00781" measures **evals-to-basin, NOT solution quality**. It is DOE-cost-dependent (**p = 0.07031**
at the pre-registered DOE=8 sensitivity) and grid-scoped. It is **not** the headline; the wide-basin /
tied-quality mechanism is.

**§5 reconciliation (explicit).** §5 shows the landscape is separable, so a structured screen
(`characterize` / DOE) is the domain-appropriate tuner — and the 12-config strict factorials **confirm
structure is findable: the additive DOE screen lands on the csr and elkan optima** (csr→`BCF_-O3_G`,
elkan→`BCF_-O3_N`). Both hold together: **structure exists and is findable, AND the 16-config grids are too
small / basins too wide for evals-to-optimum to separate a structured screen from RS.** Not a contradiction —
a grid-size statement.

**Where applied:** `ProjectReport.md` §7 (rewritten) + epistemic spine + §8 point 2 + §9 point 3;
`ProjectReport.html` view 7 + KPI (11 consistency asserts; embedded == committed JSON); `resultNew.md` §2 +
the F6 fault entry.

---

## 2. F7 — dedicated §6.5 auditor subagent verdicts (the gate)

_Run read-only against the committed F1–F6 raw via the `rq1prime-final-audit` workflow (run `wf_f7805044-f8b`,
3 agents, 0 errors) + a focused measurement re-run (commit `b693878`). Each auditor recomputed independently
with its own scripts (no import of the project code) in the pinned container; required diff exactly zero._

**ALL THREE PASS at zero-diff, framing_ok=true.**

- **stats-auditor — PASS (zero-diff, no notes).** Reproduced from raw with two independent scripts (no project
  code): F1 variants n=7/8/9 exact, F5 pava 1.408, the **primary power table with worst |diff| 0.000000 over
  all 36 cells** (replicating the pre-registered PCG64 seeds) + n80 12/26/103, the full RQ1′ replay (τ=0.02,
  K=1/4/1/4/8/1/4/5/2, RS_E, MC bit-exact, DOE res-IV predicted-best labels + main effects, DOE mis-predicts
  only elkan+binning, floyd sole flat certificate, sign-test 8/0 p=0.00781 + DOE=8 7/1 p=0.07031, Wilcoxon
  W+=0/W−=36), and F6 median K/N=0.25. Commit order provable (2dc9efe ancestor of b5f3fb8). **Framing check
  PASSES:** wide-basin/tied-quality corroboration, sign-test labeled evals-to-basin not quality, p demoted,
  "NOT an RS beats DOE/BO result."
- **validation-auditor — PASS_WITH_NOTES (zero-diff).** F3 D-series complete (logs/defects = {D3,D4,D5}, none
  omitted; D1/D2 roadmap §0.2 SILENT; D3/D4 caught-before-ship; D5/D6 SILENT; four-silent set matches). F4
  co-built-sibling .so + closure-complete confirmed; **no inline overclaim survives**. I-1 = **9.425×** exact
  (bad 737064276 / good 78199098 ns). F6 framing honest, grid-scoped, never RS-beats-DOE. *Notes (scope
  caveats, not diffs):* I-3 = 100 test functions by static count, not re-executed this pass (unchanged-from-
  prior); `test_per_rep_regen.py` non-vacuous by static inspection, not executed in-container this pass; this
  pass covered F3/F4/I-1/I-3/F6 only.
- **measurement-auditor — PASS (zero-diff after the round-once fix).** Every timing number exact — incl. the
  elkan construction-subtraction (`cgB[2]−cgA[0]` = unit_so_ir **758,813,497** exact; the 622M-Ir
  `_euclidean_dense_dense` attributed to `_k_means_common.so` → F4 co-built-sibling confirmed), crit-3 shares,
  all 9 t_best, DOE quality spot-ratios + worst 1.0999 + within-τ 6. Initial pass found **one** diff — a
  derived-summary round-order artifact (`doe_quality_median_ratio` 1.0057 stored vs 1.0058 full-precision). It
  was **fixed** (round once over full-precision ratios, commit `b693878`) and the **measurement-auditor re-ran
  to a clean PASS:** *"the sole prior diff is RESOLVED … recompute … yields 1.0058, exactly equal to the
  committed value (zero diff); the old double-rounding path reproduces the prior 1.0057, confirming the root
  cause … VERDICT: PASS."*

**Second line (belt-and-suspenders):** `results/audit/closeout_rq1prime/independent_reaudit.py` (an
independent reimplementation — own parser, own res-IV enumeration, own sign test; no import of the project
scripts) recomputes every headline statistic incl. the F6 basin/quality numbers → **ALL ZERO-DIFF** (median
K/N=0.25, DOE within-τ 6/8, worst 1.0999). The dedicated §6.5 auditors above are the **gate**; this is the
corroborating second line.

---

## 3. Final RQ1′ table (numbers unchanged; interpretation column corrected)

| unit | K | basin K/N | RS E[evals] | DOE quality | correct interpretation (per unit) |
|---|---|---|---|---|---|
| _k_means_elkan | 1 | 0.06 | 8.50 | 1.036 | single-config basin; DOE lands 3.6% off (near-tie); RS finds exact best in ≤16 |
| sparsefuncs_fast | 4 | 0.25 | 3.40 | 1.010 | wide basin; both reach near-opt; evals can't separate |
| _binning | 1 | 0.06 | 8.50 | 1.100 | single-config basin at a fast-math outlier; DOE 10% off; strict-axis flat |
| _predictor | 4 | 0.25 | 3.40 | 1.013 | wide basin; quality tied |
| _shortest_path | 8 | 0.50 | 1.89 | 1.007 | flatness certificate (half the grid near-opt); no method needed |
| _online_lda_fast | 1 | 0.06 | 8.50 | 1.000 | single-config basin; DOE hits exact best |
| _traversal | 4 | 0.25 | 3.40 | 1.001 | wide basin; quality tied |
| _isotonic | 5 | 0.31 | 2.83 | 1.000 | wide basin; DOE hits exact best |
| _ppoly | 2 | 0.12 | 5.67 | 1.000 | small basin but DOE hits exact best; grid too small to separate |

**Aggregate:** median K/N 0.25; RS evals-to-basin 1.89–8.5; DOE within-τ 6/8; sign-test on evals-to-basin
p=0.00781 (DOE=9) / 0.07031 (DOE=8). **Interpretation:** wide-basin / tied-quality corroboration of the
flat/separable landscape; grid-scoped MEASURED-REPLAY; **not** "RS beats DOE/BO".

---

## 4. Deviations + limitations carried forward (explicit, not buried)

- **MEASURED-REPLAY is grid-scoped** (16/12 configs), NOT full Θ = 1728. The full-Θ BO ≤ RS remains **INFERRED**;
  no BO surrogate was built or run (n underpowered ⇒ an uninterpretable null).
- **DOE ≠ BO.** DOE is a deterministic proxy for structure-exploitation; the ≤4.6% measured interaction
  variance (§5) is the INFERRED bridge from "evals can't separate here" to "BO wouldn't help either."
- **Small paired n.** 8 non-flat modules (fewer independent folds). The p-values are module-level and
  DOE-cost-dependent; the robust claim is the wide-basin/tied-quality *mechanism*, not a significant test.
- **Single-machine measurement** (i3-10100F, pinned image); cross-hardware generality is not measured.
- **cc kept in the canonical Δ set despite crit-3 DROP** (44.6%) as the boundary case; the n=7/8 variants show
  the FLAT verdict holds without it.
- **F4 premise corrected by verification:** the "cimported-INLINE" premise was factually wrong; reported as a
  finding (co-built sibling .so, closure-complete). No re-measurement needed (attribution already correct).
- **Fold count corrected 8 → 7** (canonical over the 9 endpoint survivors).

---

## 5. Self-verification checklist (every box; item 2 real-auditor-backed on F7 completion)

| # | item | status | evidence |
|---|---|---|---|
| 1 | F6 reframe applied everywhere; no "RS wins" takeaway; §5 reconciled; median-K/N from raw | ✅ | ProjectReport §7/spine/§8/§9, HTML view7/KPI, resultNew §2/F6; K/N 0.25 recompute |
| 2 | F7 real §6.5 auditors ran to completion, zero-diff, verbatim verdicts recorded; resultNew item 6 ✅ | ✅ | §2 above: stats PASS · validation PASS_WITH_NOTES · measurement PASS (re-run `b693878`); all zero-diff, framing_ok=true |
| 3 | Every number traces to committed raw + recompute; every claim labeled MEASURED/MEASURED-REPLAY/INFERRED | ✅ | ProjectReport §10 appendix; independent_reaudit.py ALL ZERO-DIFF |
| 4 | Replay framed as corroboration of flat/separable, grid-scoped, quality-tied — never RS>DOE/BO | ✅ | §1 above; framing_ok checks in F7 auditors |
| 5 | No forced/softened result; no underpowered BO-vs-RS run | ✅ | replay = computation on existing tables; DOE=8 sensitivity reported |
| 6 | HTML consistency assert passes; embedded == committed JSON | ✅ | 11 asserts; verified True |

---

## 6. Plain-language bottom line (for the decision)

**What is PROVEN (MEASURED):** On the accessible pure-Cython numeric corpus, the directive×flag landscape is
**flat** — median speedup ratio Δ ≈ 1.34 (< the 1.5 admission line) — and the corpus is **statistically
underpowered** (n = 9 modules / 7 folds vs the 12/26/103 needed), and this holds at **every** reasonable
cut of the corpus (n = 7/8/9). Only two kernels have a real speedup (csr 3.0×, elkan 3.9×) and both are
**separable** (≥95% additive main effects). The measurement instrument is validated (I-1 = 9.4×, tiered
oracle, four documented silent defects).

**What is CORROBORATED (MEASURED-REPLAY, grid-scoped):** On the measured 16-config grids the near-optimum
**basin is wide** (median K/N = 0.25), so Random Search reaches a near-optimal config in ~3 evaluations and a
structured screen (which costs ≥8 on a 16-point grid) cannot beat it by evaluations — while endpoint quality
is **tied** (both reach near-optimal). This is the flat/separable landscape seen as a search trajectory. It
holds **only on these small grids**, not on the full 1728-config space.

**What is INFERRED (not measured):** Over the full space, **BO ≤ RS** — a landscape-grounded expectation from
the measured flatness + separability + the grid-scoped replay + BO theory. A full-Θ BO-vs-RS experiment was
**deliberately not run** because n is underpowered (its null would be uninterpretable).

**What is explicitly NOT claimed:** This is **not** "RS beats DOE or BO." It is **not** a full-Θ result. No BO
was built or run. The structured screen (`characterize`) **does** find the optimum where structure exists
(§5) — the replay only shows the grids are too small for evaluations to separate the methods.

**Status: STOP for human review — not declared final until you sign off.**
