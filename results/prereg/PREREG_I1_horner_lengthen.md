# PREREG — Horner I-1 reference input lengthening (Step 0.P close-out B.2)

**Committed BEFORE re-measuring.** Pre-commitment separates a principled instrument refinement
from tuning-to-a-threshold. Measure ONCE; report whatever results; do NOT iterate n to hit ≤1%.

## Trigger (raw pointer)
Horner numeric-loop reference fails exit-criterion-4: bootstrap **CI@30 half-width = 4.005% > 1%**
(median 5.278 ms; B=10000, seed 12648430). Raw: `results/calibration/i1/raw/horner_good_K30.json`.
Root cause (B.2): compute-bound kernel at an unrepresentatively short ~5.3 ms — per-run
timer/scheduling jitter (absolute, frequency-invariant per measurement-auditor) is a large
*relative* fraction. Quiesce-all (G2/C) is memory-bound and **cannot** help here.

## Decision — lengthen the reference INPUT (input-only; kernel/build/oracle UNCHANGED)
`HORNER_SETUP` in `scripts/i1_measure.py`: **n: 4_000_000 → 64_000_000** (×16). Degree (12 coeffs),
seed (20260611), kernel (`horner.pyx`), and both good/bad build configs are UNCHANGED. Both
configs continue to share one `HORNER_SETUP` string ⇒ pairing (setup_sha256) preserved.

## A-priori predictions (committed before the run)
1. **Runtime:** good ≈ 5.278 ms × 16 ≈ **84 ms** → lands inside the §4.2 corpus band (50–500 ms).
   The "double win": longer run averages jitter AND moves the reference into the operating band.
2. **CI@30:** jitter is absolute (timer/scheduler; eff_ghz-stable), so relative CI ∝ 1/runtime ⇒
   predicted **CI@30 ≈ 4.005% × (5.278/84) ≈ 0.25% ≤ 1%** (≈4× margin).
3. **I-1 ratio:** **PRESERVED ≈ 8.69× ≥ 1.5×.** Horner is compute-bound (11 FMA : 2 array
   accesses, `I1_numeric_kernel_choice.md`); good/bad both scale ~linearly with n, so the ratio
   median(bad)/median(good) is invariant under proportional n.
4. **Oracle:** **PASS.** good/bad differ by FMA rounding only (~3.3e-15 per element,
   `horner_oracle.json` atol=rtol=1e-9); the difference is per-element and **scale-invariant**.

## Decision rule (pre-committed)
Criterion-4 for Horner is MET iff, at n=64M: **CI@30 ≤ 1% AND I-1 ratio ≥ 1.5× AND oracle PASS.**
If any fails, that is a recorded FINDING — escalate (debug-mantra / human); do **NOT** iterate n
or K to force the threshold (forbidden tuning, §6.1). K_final = 30 stays uniform (§5.1).

## Classification
Phase-0 **instrument-definition refinement** (reference input scale). NOT an Appendix B-12
experiment amendment (no corpus/search-space change). NOT a D-series defect. Predates any
RQ1/endpoint data. The prior 5.3 ms Horner raw remains in history (commit a002f38).
