# PREREG_I1 — gate I-1 known-good vs known-bad (Steps 0.5.2 measure / 0.5.3 gate)

Committed BEFORE any I-1 measurement run (§6.1 pre-register-before-comparing). The gate
criteria are roadmap-fixed (§0.3); this file freezes the exact configs, inputs, and
decision procedure so nothing can be adjusted post-hoc.

## Configurations (§0.5.2) — built per kernel, paired inputs

- **known-good** (aggressive, safe-by-oracle): cython `boundscheck=False,
  wraparound=False, initializedcheck=False, nonecheck=False, cdivision=True`; gcc
  `-O3 -march=native -ffp-contract=fast -g0 -pipe -shared -fPIC`.
- **known-bad** (all safety checks on, low opt): cython `boundscheck=True,
  wraparound=True, initializedcheck=True, nonecheck=True, cdivision=False`; gcc
  `-O1 -march=x86-64 -ffp-contract=off -g0 -pipe -shared -fPIC`.

`-ffp-contract` is explicit in both (§3.2 item 3). Both produce valid output on these
inputs (I-1 is a TIMING gate; the kernels divide only by doubles, so cdivision does not
change their results — correctness is not at issue here).

## Inputs — paired, frozen, reused from the pilot (§5.1 pairing)

The committed pilot setups (`scripts/pilot_measure.py` SETUPS, seed 20260611):
- csr_scale: nnz=4,000,000, nrows=100,000, passes=24.
- pava: n=4,000,000.
Identical inputs across both configs (same setup_sha256 recorded in every raw record =
pairing proof) and identical to the pilot (so the I-1 numbers are comparable to the
0.2.4 variance study).

## Measurement protocol (§5.1)

- Isolated measurement core 3 via `scripts/measure_wrap.sh` (refuses unless no_turbo=1
  + performance governor + idle/isolated sibling verified). 1 s thermal watch.
- K_final = 30 measured reps + 5 warmup (warmup never reported). Fresh subprocess per
  measurement (§3.2(2)). perf cycles on the 10% subsample as a cross-check.
- Discard rule (logged, never silent): any rep window with throttle_delta > 0, or
  package/core temp above the pilot threshold (`MEASUREMENT_CONSTANTS.json`
  thermal_discard_mC), is discarded and re-run.
- Raw per (kernel, config) -> `/results/calibration/i1/raw/<kernel>_<config>_K30.json`,
  committed BEFORE any ratio is computed (§6.1). No aggregation in 0.5.2.

## Gate I-1 (§0.3) — applied in Step 0.5.3, recomputed by stats-auditor at preflight

For each kernel: **speedup = median(known-bad samples_ns) / median(known-good samples_ns)**
(median over the 30 reps; median-of-medians degenerates to the single-instance median
here). Pass criteria:
- **csr_scale (raw-pointer path): speedup ≥ 1.15×.**
- **pava (numeric-loop path): speedup ≥ 1.50×.**

## Decision (frozen)

- **PASS** (both thresholds met): gate I-1 satisfied; recorded in STATE (0.5.3); the
  Phase-0 "I-1 pass with stated margins" exit criterion is met.
- **FAIL** (either threshold missed): RED GATE. Per §0.5.3 the instrument is **presumed
  wrong until proven otherwise** -> `debug-mantra` before any change. No tuning,
  seed-selection, config-fiddling, or re-run to force a pass. The raw stays committed as
  the honest negative.

Single-amendment rule untouched (this is an instrument gate, not a corpus/space change).
