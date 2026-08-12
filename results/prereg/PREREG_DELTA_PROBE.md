# PREREG — Step 1.3.1 fixed 16-config Δ-probe (landscape non-flatness screen)

**Status: PRE-REGISTERED. Committed BEFORE any Δ timing is observed** (empirical-honesty rule:
pre-register before any comparison runs). This file pins the EXACT 16-config factorial, the
build-flag mapping, the timing protocol, and the §1.3.2 admission arithmetic. Nothing here is
tunable after a number is seen.

## Purpose & scope
Roadmap §1.3.1/§1.3.2/§4.1c: characterize landscape **non-flatness** via a fixed 16-config probe;
`Δ(unit) = t_worst / t_best`; **admission: corpus median Δ ≥ 1.5 AND ≥ 70% of units with Δ ≥ 1.2**
(Tier-3 thresholds; §4.1c basis: prior rebuild measured directive deltas 1.5×–14.7× across 7 modules).

This run is the **GATING characterization for the codebase-expansion decision** (per the active goal):
the 1.2.4 viability gate found the surviving crit-3 class underpowered → expansion is the power remedy,
BUT power is necessary-not-sufficient. If the surviving directive-tunable class is **flat** (Δ < 1.5),
adding more of the same class yields a well-powered NULL from flatness, not from BO≤RS — so expansion
would be unjustified and the honest terminus is the contribution-(B) reframe (§0.4 / §1.5.6b). The Δ-probe
on the EXISTING crit-3 survivors answers "is expansion worthwhile?" before any new package is vendored.

The §1.3 admission SEAL is later re-run on the full combined corpus (§1.3.4); this is the survivor-class
screen on the already-vendored units.

## The 16 configurations (2⁴ factorial over four binary axes)
Four axes, each at two poles, crossed fully ⇒ 16. The axes are the highest-leverage knobs of the §2.3
search space Θ; the probe BRACKETS t_worst (all-conservative) and t_best (all-aggressive).

| axis | pole 0 | pole 1 |
|---|---|---|
| **CHK** (Cython memory-safety checks) | `S` = boundscheck,wraparound,initializedcheck,nonecheck = **True** | `U` = all four **False** |
| **DIV** (Cython cdivision) | `P` = cdivision=**False** (Python `//`/`%`, ZeroDivisionError) | `C` = cdivision=**True** (C truncation) |
| **OPT** (GCC opt/march/unroll bundle) | `L` = `-O1 -march=x86-64` | `H` = `-O3 -march=native -funroll-loops` |
| **FP** (GCC floating-point aggression) | `T` = strict: `-ffp-contract=off`, no fast-math | `A` = aggressive: `-ffast-math` (implies `-ffp-contract=fast`) |

**Named-pole coverage (§1.3.1 text):** *all-safe-on* = `SPLT` (slow pole); *all-checks-off+O3+native* =
`UCHT`/`UCHA` (fast pole); *fast-math poles* = the FP axis (T vs A); *contract poles* = `-ffp-contract=off`
(in T) vs `-ffp-contract=fast` (carried by A). The screen does NOT independently isolate
`contract=fast`-without-fast-math (that point lives in the full §2.3 Θ the RQ1 search explores); for a
t_worst/t_best SPREAD screen the FP poles bracket the contraction effect. Justified deviation, recorded.

**Enumerated 16 (label = CHK·DIV·OPT·FP):**
`SPLT SPLA SPHT SPHA SCLT SCLA SCHT SCHA UPLT UPLA UPHT UPHA UCLT UCLA UCHT UCHA`

### build_unit.sh argument mapping (exact, reproducible)
For each config the probe calls `build_unit.sh <pyx> <mod> <out> "<OPT_FLAGS>" <FFP> <lang> "<CYDIRS>"`:
- **CYDIRS** = checks + cdivision:
  - CHK=S → `-X boundscheck=True -X wraparound=True -X initializedcheck=True -X nonecheck=True`
  - CHK=U → `-X boundscheck=False -X wraparound=False -X initializedcheck=False -X nonecheck=False`
  - DIV=P → `-X cdivision=False` ; DIV=C → `-X cdivision=True`
- **OPT_FLAGS**: OPT=L → `-O1 -march=x86-64` ; OPT=H → `-O3 -march=native -funroll-loops`;
  FP=A additionally appends `-ffast-math`.
- **FFP**: FP=T → `off` ; FP=A → `fast`.
- `-ffp-contract` is ALWAYS explicit (§3.2 item 3); no `-std`-dependence.

## Δ definition & two reported spreads
- **Δ_all = t_worst / t_best over all 16 timings** — the literal §1.3.2 metric (landscape spread).
- **Δ_feasible = t_worst / t_best over the 8 FP=`T` (strict, bit-preserving) configs** — the RQ1-honest
  spread for bit-exact units (fast-math FP=`A` is INFEASIBLE on any correctness-critical/bit-exact output,
  §3.2(1); it cannot be an RQ1 winner there). Both are reported per unit; the §1.3 gate is evaluated on
  **Δ_all** (spec-literal) with **Δ_feasible** reported alongside as the decision-relevant lower view.
  (For units whose output is declared numerically-approximate within tolerance, FP=`A` may be feasible;
  feasibility is per-unit per the oracle and is NOT decided here — this is a timing screen.)

## Timing protocol (screen-grade, CF-1)
- All builds + timings run **inside the pinned `:phase1` container, ONE container at a time** (CF-1
  quiesce-all). cpuset = the isolated measurement core; OMP_NUM_THREADS=1.
- Per (unit,config): `gate_runner.py scale-probe <unit> <so> <scale> <NREPS>` → in-process median_ns
  over NREPS timed reps (3 warmup), v1.4 per-rep regen for in-place kernels. **NREPS = 25.**
- Per-unit **probe scale** chosen so t_best ≳ 100 ms (kernel dominates wrapper overhead + dilutes the
  CF-4 residual; crit-3 ≥ 90% regime). Scale is recorded per unit; identical scale across all 16 configs
  of a unit (the ratio is within-unit, same input, same core, same container session).
- This is a SCREEN (in-process median, not the median-of-3-subprocess endpoint rig). It is adequate
  because Δ is a within-unit RATIO at 1.2–1.5 resolution and the measured endpoint precision (≤2.4%) is
  far finer than the decision band. Any unit landing **borderline (1.4 ≤ Δ_all < 1.6 or near the 1.2
  per-unit line)** is re-measured with the full endpoint rig before it seals §1.3.

## Units in scope (the crit-3 SURVIVORS — `SURVIVAL_LEDGER.md`, `CRIT3_TRIAGE_FULL.md`)
9 surviving modules: sparsefuncs_fast (csr_mean_variance_axis0), _online_lda_fast, _isotonic (PAVA),
_k_means_elkan, _binning, _predictor, _shortest_path (floyd_warshall / bellman_ford), _traversal,
_ppoly (evaluate). Currently DRIVEN: csr, PAVA. The other 7 get drivers authored here (same
`corpus_drivers.py` discipline: deterministic (scale,seed) recipe, kernel called as close to the loop as
possible). DROPPED units (cd_fast, lloyd, dbscan, tree, tsne, MST, bglu) are OUT of scope — not
directive-tunable, so their Δ is irrelevant to RQ1.

## Decision rule (frozen)
Compute per-unit Δ_all over the survivors → corpus **median Δ** and **fraction with Δ ≥ 1.2**.
- **median Δ ≥ 1.5 AND ≥ 70% units Δ ≥ 1.2** → directive-tunable class is **NON-FLAT** → expansion (for
  power) is worthwhile → proceed to the expansion decision (MDE pre-registration + curate for both axes).
- **median Δ < 1.5** (or < 70% ≥ 1.2) → class is **FLAT** → more streaming kernels won't help → STOP and
  present to the human: different kernel class OR the contribution-(B) reframe. (The §1.3.3 single
  amendment — extended flag space — is the in-band escalation if Δ is BORDERLINE; spending it is a human
  decision, ASK first.)

Report the full per-unit Δ distribution, worst-case, and raw `/results/characterization/delta_probe/*`
pointers. Never force a number; import-confirmed ≠ admissible; worst-case + raw pointers.
