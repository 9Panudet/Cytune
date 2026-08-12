# PREREG_PILOT2 — diagnostic re-pilot after the 0.2.4 red gate (committed BEFORE the run)

## Trigger (raw: commit ee008e8, results/pilot/raw/*.json; report: results/pilot/PILOT_REPORT.md)
Pilot 1 missed the §5.1 calibration target (bootstrap 95% CI half-width of median
<= 1% of median at K_final=30): csr_scale 2.753%, pava 1.667%.

## Diagnosis (cycles cross-check discriminates the mechanisms; debug-mantra applied)
- pava: slow reps show eff_ghz DIPS (3.465 vs 3.534 fast-rep) -> fewer user-cycles
  per wall-second -> PREEMPTION on the soft-isolated core 3.
- csr_scale: outliers to +37.9% with eff_ghz STABLE (3.471-3.506) -> on-CPU with
  proportionally more stall cycles -> DRAM-bandwidth contention (~768 MB streamed
  per run; desktop shares the memory controller).

## Intervention (pre-registered at 0.2.1 in logs/governor/CPU_MAP.md, trigger now fired)
Kernel boot args isolcpus=3,7 nohz_full=3 rcu_nocbs=3 (scripts/host_isolcpus_prep.sh,
human + sudo + reboot), then host_prep.sh re-applied. Removes scheduler preemption on
core 3. NOT expected to remove DRAM contention (different mechanism).

## Procedure
ONE re-pilot (pilot2): identical protocol, inputs, seeds, K_pilot=30, warmup=5,
cycles on; raw -> results/pilot/raw2/, committed REGARDLESS of outcome.

## Decision tree (verbatim; recorded in STATE on resolution)
1. Both kernels CI@30 <= 1%  ->  K_final=30 VALIDATED; thermal threshold from the
   pilot2 window; MEASUREMENT_CONSTANTS.json finalized; 0.2.4 closes.
2. pava passes AND csr fails WITH the stable-eff (bandwidth) signature  ->  one
   pre-stated instrument-design change: resize calibration kernels to L3-resident
   working sets (<= 4 MB), passes adjusted to keep 50-500 ms golden runtime; ONE
   final re-pilot (pilot3). Rationale: the calibration target measures INSTRUMENT
   precision; DRAM-contention sensitivity is a workload-class property (handled
   in-protocol by medians/discard rules for corpus kernels), not rig imprecision.
   The kernels' I-1 contrast role (bounds-check/wraparound sensitivity) is
   unaffected by sizing.
3. Any other outcome (pava still failing; csr failing with a preemption signature;
   new signature)  ->  STOP. Escalate to the human with full data: deeper isolation
   work or target reassessment is a roadmap-level decision.

No re-runs beyond pilot3 under any branch. K_final=30 and the 1% target are NOT
adjustable here (§5.1/§1.5: K_final is never a lever).
