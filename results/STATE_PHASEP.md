# STATE_PHASEP.md — cytune / Phase P (product pivot)

Schema: v1 §6.4. Updated at every step boundary; cold-start resumable. Spec: `PRODUCT_ROADMAP.md`
(v2.0, law). Register: `results/prereg/PREREG_PHASEP.md`.

---

## Current

```
phase / subphase.step / timestamp_utc : P2->P3 / **STAGE A CLOSED, STAGE B TRIPWIRE FIRED AND REMEDIATED, STAGE C COMPUTE RUNNING** / 2026-07-30

ENDGAME under amendment A-8 (checkpoint-by-exception; sequencing only, no threshold moved).

== STAGE A — P-2 HONEST CLOSURE: DONE ==
  - PREREG §4 applied everywhere. The ">10% / B_02" rule was a DECISION MEMO string, not the
    prereg (D22, found by the stats-auditor). DELETED from report_p2.py; governs nothing.
  - **1 of 4 confirmatory cells meets the n=26 floor.** Exact power at the CONFORMANT n, from the
    committed generator (N_SIM=60,000, SEED_EXT=20260628, delta=0.4):
        FLAT+FM   n=20  power 0.708   BELOW by 6
        MID       n=24  power 0.776   BELOW by 2
        LEVER-SEP n=20  power 0.708   BELOW by 6
        INT       n=29  power 0.853   OK
  - **A2 VERIFIED — the FEAS contrast, the product's key question, IS POWERED:** FEAS+ 62->51
    (0.974), FEAS- 67->58 (0.986). Both arms clear 26 on the conformant set.
  - FREEZE_MANIFEST_V2: 149 kernels, v1 sha256 set verified byte-for-byte (0 drift), plus
    conformance flags (conformant 123 / descriptive-only 24 / sanitizer-corrected 3 /
    directive-partial 2 / scale-band-deviation 1).
  - DEVIATIONS_REGISTER.md: 11 numbered deviations, consequences at full strength.
  - PREREG A-8 (sequencing) + A-9 (retroactive §1.4 gate) recorded BEFORE taking effect.

== STAGE B — SANITIZER REMEDIATION: TRIPWIRE FIRED (D23). REMEDIATED. AWAITING HUMAN. ==
  - **The roadmap §1.4 sanitizer gate was NEVER invoked by the Phase-P fleet harness.** ~149
    kernels x 1,728 configs were gated on the ORACLE ALONE.
  - Instrument controls PASSED FIRST, 6/6: a planted 16-element overflow is detected at both
    checks-off corners; a known-good kernel reads clean.
  - 195 units audited (65 groups x 3 risk corners), 151 clean, 44 sanitizer reports, 0 unaudited.
    All 9 Dataset-R anchors CLEAN — real code has no UB at the corners.
  - **1,296 (kernel,config) cells were recorded FEASIBLE while executing an out-of-bounds read.**
    All in 3 min/max-reduction kernels, 432/432 each; the other 76 armed trap kernels were caught
    by the oracle at 432/432. A reduction absorbs one garbage element without changing its output,
    so the oracle passed them. ASan reports heap-buffer-overflow on all three.
        fleet_INT_14_int_min32      INT -> MID   d_all 13.14 -> 1.32
        fleet_INT_16_int_max32      INT -> MID   d_all 13.01 -> 1.32
        fleet_INT_20_int_sum64_r3   INT -> MID   d_all 13.92 -> 1.32
    The 13x lever WAS the out-of-bounds read.
  - Remediated by OVERLAY: raw byte-identical, FREEZE_MANIFEST sha256s still verify, only the
    feasibility LABEL corrected on top. run_study REFUSES to run without it (SANITIZER GUARD).
  - **DEV-1b (measurement-auditor F2, verified independently):** the endpoint tier of those three
    is 100% inside the overlay — 0 of 130 configs survive, both argmins are UB. Their
    agreement bit is NOT EVALUABLE. Conservative ruling applied (excluded); MID n=24. Reading it
    as PASS would give MID=27 and 2 of 4 — a defect improving our own result. HUMAN RULING OPEN.
  - **TRIPWIRE STATUS: the directive says PAUSE for the human before P-3 results are read.**
    Compute proceeds; no P-3 conclusion is recorded until the human rules.

== STAGE C — P-3 REPLAY: **COMPLETE under amendment A-10 (20-seed truncation)** ==
  - RS + DOE at the FULL pre-registered spec. BO + Motif at the 20-seed uniform prefix (contiguous
    0..19, all 129 kernels, both arms). All stochastic arms truncated to the SAME prefix.
  - SEM inflation 3.162x. MEASURED cost via RS (which has both a 20- and 200-seed mean):
    21.6% mean relative shift, max 290%, over 645 kernel-budget pairs.
  - FLAT no-winner TRIPWIRE: PASSES (spread <= 0.0046 vs a 0.01 bar).
  - **RQ-P1: DOE wins.** Best product-runnable arm in 18 of 20 cells. BO loses to DOE in 18 of 20
    and is WORSE THAN RANDOM SEARCH on flat landscapes. The Bayesian arm does not earn its cost.
  - **RQ-P3: Motif passes its gate (p=3.46e-17, delta=0.772) and is NOT SHIPPED.** Its warm-start
    sources are 9.7x enriched for siblings of the target's own template (3.74/8 vs 0.39 baseline),
    and the corpus it needs does not exist at the point of use. DEV-13.
  - **RQ-P2: ROUTING ADDS NOTHING.** On 18 held-out kernels the router equals always-DOE at
    B in {8,32,64,128} and is WORSE at B=16 (0.174 vs 0.135). Per-cell engine switching not shipped.
  - Provenance slice behaves as A-7e predicted: real code easiest (0.035 @B8), H-ext hardest (0.308).

== STAGE D — P-4: routing installed as a NEGATIVE; product hardening done ==
  - cytune routes to DOE unconditionally — the study changed the STATUS of that choice, not the
    choice. The router's surviving rules (R0 abort, R1 honest-flat) are the ones that earned it.
  - §1.4 sanitizer gate in the product on the ACTUAL emitted config; not-run is never a pass.
  - cytune doctor, README quickstart, v1.0.0-rc0+research-preview labeling.
  - Routing label pins BOTH halves: "P3-VALIDATED ... NOT validated on real code". 2 tests.
  - NOT DONE: live end-to-end runs.

== STAGE E — P-5: DELIVERED ==
  - PHASEP_REPORT.md — all three RQs ANSWERED, all three negative; routing matrix with powered vs
    underpowered cells marked; full D-series; 13 deviations; limitations.
  - DEFENSE_SUMMARY.md — one page, four buckets, product guarantees and non-guarantees.

== THE ONE OPEN BLOCKER ==
  - stats-auditor dispatched TWICE, died TWICE (monthly spend limit, then session limit). The
    independent zero-diff recompute has NEVER RUN against the corrected artifacts. Every number is
    self-computed and raw-pointered but not independently verified. NOT SIGN-OFF-READY for this
    reason and this reason only.

== AUDITORS ==
  - stats-auditor: FAIL (D22) -> fixed; RE-RUN dispatched against the corrected artifacts.
  - measurement-auditor: **PASS_WITH_NOTES**. Rig clean: 48 kernels (32.2%), ZERO issues, one rig
    fingerprint across 82,944 rows, agreement bits ZERO diff on all 149, both rig-time figures
    (157.91 h / 225.95 h) verified. Findings -> DEV-1b, DEV-9, DEV-10, DEV-11.
  - validation-auditor: dispatched (R oracle 100% + adversarial review of MY D23 remediation).
  - scrutinize: pending, runs last.
```

---
# STATE_PHASEP.md — cytune / Phase P (product pivot)

Schema: v1 §6.4. Updated at every step boundary; cold-start resumable. Spec: `PRODUCT_ROADMAP.md`
(v2.0, law). Register: `results/prereg/PREREG_PHASEP.md`.

---

## Current

```
phase / subphase.step / timestamp_utc : P2 / **DATASET R COMPLETE** (9/9 anchors, full 1728 tables); next: audit battery (#63, incl. the undischarged #65 trigger) → P2_REPORT → STOP for the human's freeze sign-off / 2026-07-30

R_COMPLETE (2026-07-30 — all 9 v1 survivors to full 1728 tables, 29.62 h, zero BUILD/MEASURE failures):
  - **MEASURED CLASSES:** MID **4** (lda, floyd, cc, predictor) · FLAT **3** (pava, binning, ppoly)
    · LEVER-SEP **2** (csr, elkan) · **INT 0**.
  - **THE HEADLINE FINDING — INT DOES NOT OCCUR IN REAL CODE (0/9).** The synthetic generator
    produced **42** measured-INT kernels; the real-code anchors produced **none**. This is not a
    small-sample accident of arbitrary kernels: the 9 are the **v1 SURVIVORS**, already filtered as
    the most promising non-flat units in the corpus, so a zero here is the strongest form the
    result could take. INT is defined as Δ_strict ≥ 1.5 ∧ IF_strict ≥ 0.25 — a genuine
    directive×flag *interaction*. **Construct-validity consequence for P3/P4, to be stated
    prominently and never buried:** if an algorithm's advantage concentrates in INT, that advantage
    may not be reachable on real user code. This bears directly on the routing matrix (P-3) and on
    the RQ-P2 acceptance argument (P-4).
  - **v1 → v2 TRANSFER: CLEAN ON ALL NINE**, span-vs-span, ratios **0.78–1.01**, none near the
    ≥2× investigate bar. P's span is consistently ≥ v1's because P sweeps 1728 configs against
    v1's 16 and therefore finds wider extremes — the expected direction, and a mild positive
    control on the comparison itself. Real code reproduces its v1 character under an INDEPENDENT
    taxonomy: csr and elkan → LEVER-SEP (the two real levers), pava → FLAT.
  - **AGREEMENT WATCH: 9/9 PASS.** Real code sits entirely outside the synthetic generator, so
    this is independent evidence bearing on the still-undischarged #65 trigger — consistent with
    the ruggedness hypothesis, and NOT a discharge. The auditor's three questions stand verbatim.
  - **D21 (found here, fixed, post-mortem written).** `elkan` tripped the ≥2× bar at 2.41× — and
    it was a metric mismatch, not a measurement problem. v1's `delta_all` is `t_worst/t_best`
    (span); Phase P's committed `delta_all` is `t_ref/t_star` (`classify.py:75`, speedup over the
    DEFAULT). Their ratio is `t_worst/t_ref` and carries no cross-version information. Disproved by
    matching all 16 v1 configs individually into Θ: P is uniformly 1.32–1.43× faster on **every**
    config (constant offset from the calibrated scale, which cancels in a ratio), and elkan
    transfers at **1.009×** — the closest of all nine. Two of my own hypotheses died with it,
    including a WRONG claim I had already committed (that `-fopenmp` is never applied; `build.py:119`
    does apply it). Two of my own runs had to be RETRACTED from the ledger — they reported
    "NO MATCH ×16" because my extractor read a top-level `median_ns` that lives under
    `row["screen"]`, so the lookup was empty by construction. `logs/defects/D21.md`.

H_SEALED (2026-07-29 — H_CAP_STOP; the A-7/A-7i step closes here):
  - **FINAL CELLS:** INT **3/3 MET** · MID **4/3 MET** · LEVER-SEP **3/3 MET** ·
    FLAT+FM **1/3 SHORT by 2** · TOTAL **11/15 SHORT by 4**. Provenance **H-ext 4 / H-orig 7**.
  - **CAP:** `H_CAP_STOP` at **86,540.5 s / 86,400 s = 100.16%**; overshoot 140.5 s, inside the
    pre-recorded "cap + at most one in-flight cycle" ceiling. Ledger: ACCEPTED 11 ·
    REJECTED_CLONE 15 · PARAMS_DUPLICATE 26 · SLOT_EXHAUSTED 2 · CYCLE_ORPHAN 3.
  - **A-7 DID ITS JOB.** INT went from **0 fresh candidates** — the blocker that forced the
    amendment — to **3/3 MET, all H-ext, with ZERO clone rejections**. The cheapest cell in the
    campaign was the one that had been structurally impossible.
  - **FLAT+FM IS SHORT BY RULING, NOT BY SUPPLY**, and the write-once seal says so in those words
    (`cause: "DEPRIORITIZED (A-7i human allocation ruling) — NOT short by supply"`). Three
    shortfall causes exist — deprioritized / supply-exhausted / cap-stopped — and conflating them
    would attribute a human decision to the data. The seal also pins the deprioritized list, the
    H_CAP_STOP record, per-cell met/not-met, and h_spend_s.
  - **MEASURED DRIFTER for the confusion table:** `fleet_LEVER_SEP_W2_202_lev_modconst_r3` was
    intended LEVER-SEP and measured **MID** (A-2i, no grandfathering) — which is why MID is 4.
  - **MY PROJECTION MISSED, pessimistically this time.** I predicted ~2.3 further accepts, 2 cells
    MET, and warned MID might SLOT_EXHAUST; actual was 6 accepts, 3 cells MET, MID 4. The pooled
    rate I extrapolated from was dominated by the FLAT+FM sink that A-7i removed. Recorded because
    I have now missed these estimates in BOTH directions; treat my cycle-rate projections as
    weak priors, not planning numbers.
  - **Write-once guard verified POSITIVELY:** a second `--make-h-manifest` refuses with "H is
    sealed". H_MANIFEST is separate from FREEZE_MANIFEST by necessity (the freeze predates H) and
    by design (the P3 firewall needs the training and acceptance sets distinguishable at load).

A7_H_SUPPLY (2026-07-28 — the CURRENT step; supersedes the H line in FREEZE_EXECUTED below):
  - **THE BLOCKER, MEASURED.** H's first slot exhausted on nine consecutive `PARAMS_DUPLICATE`
    skips at **zero** measurement cost. The D8 pre-guard keys on (template, params, feas_variant)
    fleet-wide and the training campaign had consumed **169** such keys; `H_START_INDEX` renumbers
    slots but does not refill the pool. Fresh supply for H: MID **14** · LEVER-SEP **13** ·
    FLAT+FM **5** · INT **0**. The ≥3-per-confirmatory-cell ruling was structurally unsatisfiable
    for INT. The original non-W2 registries did not rescue it (FLAT_FM 0, INT 0).
  - **DECISION MEMO → HUMAN RULING.** Presented as a decision-type block. Ruling: **Option 1
    APPROVED with riders**; options 2 (relax the per-cell rule) and 3 (accept H short) REJECTED —
    "2 = 3 in amendment clothing", and an empty INT cell removes a quarter of RQ-P2's validation
    in precisely the class where BO is most likely to win.
  - **AMENDMENT A-7** (`29daa03`, committed BEFORE any extended kernel existed; PREREG §12 +
    `results/fleet/A7_H_SUPPLY_AMENDMENT.md`). Supply-only: two NEW registry keys `FLAT_FM_H` /
    `INT_H`, read only by `--stage holdout`. Wave-1/wave-2 registries byte-untouched, because
    `process_slot` derives params as `pspace[(gi+k) % len(pspace)]` — appending to an existing
    pspace would silently repoint already-FROZEN slot labels. **102 candidate keys, 0 collisions**
    against the survival ledger. `int_sum64` dropped (measured LEVER-SEP 4/4, INT 0/4). Riders:
    A-7b anti-sculpting (points fixed pre-generation), A-7c ONE-SHOT, A-7d cap, A-7e provenance +
    the pre-registered P4 provenance slice, A-7f structural-finding clause, A-7h cross-listing
    declined on scope with the evidence recorded.
  - **CODE** (`502457d`): `H_CAP_S = 86,400 s` over Σ(build_s+measure_s+orphan_s) across ALL
    holdout rows any status, evaluated BEFORE roster state, `H_CAP_STOP`/`H_CAP_DEFERRED` distinct
    from the wave-2 statuses. `H_ORDER = (INT_H, FLAT_FM_H, MID_W2, LEVER_SEP_W2)`. Permanent
    `provenance` H-orig/H-ext on spec.json, every holdout ledger row, holdout_summary and
    H_MANIFEST; H is wave-EXEMPT (`wave: null`) per A-3b. `run_study.make_h_manifest` seals H
    write-once, separate from FREEZE_MANIFEST.json. **18 new A-7 tests; suite 123 passed.**
  - **READING RECORDED (in code, A-6c style).** A-7d's "INT ≥3 first, then …" is implemented as
    SERVICE ORDER inside round-robin-over-under-floor-cells, NOT strict pre-emption. Strict
    pre-emption would let a structurally unfillable cell — exactly A-7f's anticipated INT case —
    consume all 86,400 s and leave MID and LEVER-SEP at zero, strictly worse than the pre-A-7
    state. This is A-3d's own allocation rule and its worst-case-balance rationale.
  - **D20, found during this transition and fixed here.** A cycle killed during the BUILD phase
    charged **0.0 s** to the hard cap: `_run` flushes its header then hands the fd to a
    block-buffered child, so the run log's mtime never advances during a build and `table.jsonl`
    does not exist yet (CF-1) — the reconciler's `max()` collapsed to `t_start`. Its docstring
    claimed "both phases write CONTINUOUSLY"; true of measure, false of build, and only measure had
    a test. Fixed by scanning `build_manifest.jsonl` + the `_so` dir mtime (4 tests, 2 verified RED
    pre-fix). **It had already happened 3×** — wave-2 rows 2095/2099/2103 carry `orphan_s == 0.0`.
    Exact undercharge NOT recoverable (those dirs were later resumed to completion, overwriting the
    bounding mtimes); recoverable UPPER bound from run_id windows **≤ 7,266 s (2.02 h)**. So A-3's
    recorded 175,406.8 s is a LOWER bound and the true overrun past the cap lies in
    **[0.72 h, 2.72 h]** — carried into P2_REPORT envelope-actuals as an interval, never a point.
    An undercharge stops the runner LATE, never early, so no kernel was denied a cycle, and no
    measured data is affected (`orphan_s` feeds the cap gate and nothing else). `logs/defects/D20.md`.
  - **LIVE VALIDATION:** the killed H build was reconciled by the fixed path and charged
    **1,660.7 s**, where the pre-fix reconciler would have charged 0.0.
  - **RUNNING:** `run_fleet.py --stage holdout --controls-dir controls_a4`, launched after a
    `measure_wrap --verify-only` PASS on an idle box (`campaign_busy.sh` rc=1). Firewall armed;
    graphify deferred; measurement-only box.
  - **LAUNCH DISCIPLINE (learned the expensive way — use `setsid`).** A plain
    `nohup … &` runner has now been killed TWICE by session/agent teardown, mid-build both times,
    costing 1,660.7 s + 421.0 s = **2,081.7 s** of redone compile work charged to the caps. `nohup`
    only ignores SIGHUP; it does not detach the process from the session, so a teardown that kills
    the process *group* takes the runner with it. Every campaign relaunch from here uses
    `setsid nohup … < /dev/null & disown`, which puts the runner in its own session and group.
    Both deaths were charged correctly ONLY because of the D20 fix — each kernel dir held `_so`
    but no `build_manifest.jsonl`, so the `_so`-mtime backstop was the sole signal; the pre-fix
    reconciler would have charged 0.0 s twice and the cap would have silently over-run.
  - **A-7i ALLOCATION RIDER (2026-07-28, human-ruled mid-campaign on presented economics;
    `1b51ecf`).** At 16.50 h of the 86,400 s cap with 5 accepts, per-registry cost was:
    `INT_H` 2 acc / 0 clone-rej / **0.80 h per accept** · `MID_W2` 1/0 / 1.44 h ·
    `LEVER_SEP_W2` 1/2 / 2.39 h · `FLAT_FM_H` 1 acc / **11 clone-rej** / **11.07 h per accept**.
    FLAT+FM had consumed **67% of the whole H budget for one accept**, with all 11 rejects well
    below ε (max 0.0431). RULING: serve `INT_H`/`MID_W2`/`LEVER_SEP_W2` only for the remainder;
    FLAT+FM is still COUNTED and REPORTED, only serving stops. Recorded as a numbered amendment
    (PREREG §12 A-7i) precisely BECAUSE it is outcome-informed, and committed before taking effect.
  - **THE FINDING BEHIND IT (a P-2 result, not logistics).** A-7 did what it was written to do for
    **INT** — the structurally impossible cell became the CHEAPEST (0 clone rejects). It cannot do
    the same for **FLAT+FM**, whose binding constraint is the **property space, not the parameter
    space**: those landscapes are near-degenerate by construction (Δ_strict ≈ 1.000, IF_strict
    null, greedy_gap often 0), so fresh parameters yield fresh kernels landing on top of existing
    landscapes. Two DIFFERENT exhaustion modes, reported separately. This is also why A-7c's
    one-shot rule is right here: a second extension could not fix FLAT+FM either.
  - **CUTOVER COST 3.2 s.** The in-flight `mid_hist_r1` cycle (1,728 screen rows written, in its
    endpoint phase, ~62 min sunk) was NOT killed; a watcher waited for its terminal ledger row and
    then stopped the runner by explicit PID. The watcher's first version used `pkill -f`, which
    would have matched the watcher's OWN command line — D19's failure mode in a new costume,
    caught before it fired. Ledger rows now carry `deprioritized`, so the allocation regime in
    force is recoverable per row rather than only from shell history.
  - **REVISED OUTLOOK, honestly.** MID is NOT the cheap cell the single-accept figure suggested:
    `mid_hist_r1` came back REJECTED_CLONE at ~1.05 h and mid_hist's remaining parameter points
    now dup-skip, so MID may reach SLOT_EXHAUSTED rather than 3/3. Remaining budget **6.44 h**.
    Expect INT 3/3; MID and LEVER-SEP uncertain; FLAT+FM final at 1/3 by ruling, not by supply.
  - **RESUME VERIFIED:** after the second death the relaunch printed
    `[skip accepted] fleet_INT_H_200_int_horner32` — the accepted kernel was not re-measured, so
    resumability holds across the extended registries. H at that point: INT 1/3, total 1/15,
    spend 1.35 h / 24 h.

A3_WAVE2_COMPLETE (2026-07-28 — TOPUP_CAP_STOP; SUPERSEDES A4_RESUMED below):
  - **FINAL CONFIRMATORY CELLS:** FLAT+FM **20/26 SHORT by 6** · MID **26/26 MET** ·
    LEVER-SEP **26/26 MET**. Descriptive: bare FLAT 16, INT 41. **2 of 3 floors met.**
  - **CAP:** final spend **175,406.8 s = 101.51%** of the 172,800 s cap. NOT a breach — A-3d checks
    the cap BEFORE starting a cycle, so the last cycle begins under and finishes over; the ceiling
    "cap + at most one in-flight cycle" was recorded in advance and the overshoot is 2,606.8 s =
    exactly one cycle. Stop recorded as `TOPUP_CAP_STOP`, not "rosters exhausted" (A-3d evaluates
    cap before roster state precisely to keep those distinguishable).
  - **WAVE-2 LEDGER (91 rows):** ACCEPTED 25 (19 on-target) · REJECTED_CLONE 24 · PARAMS_DUPLICATE
    31 (free) · CYCLE_ORPHAN 7 · MEASURE_FAIL 1 · SLOT_EXHAUSTED 2 · TOPUP_CAP_STOP 1.
    Cell contributions: FLAT+FM 9, MID 8, INT 4, LEVER-SEP 3, bare FLAT 1.
  - **THE FLAT+FM SHORTFALL HAS TWO DISTINCT CAUSES; ONLY ONE IS THE CLOCK.** (1) DIVERSITY CEILING
    — the A-2d property vector is effectively 2-D for this cell (`IF_strict` identically 0 across
    all accepted members, `lnΔ_strict` range 0.09, `infeas_frac` binary), so diversity rests on
    `lnΔ_all` + `greedy_gap` and each accept removes an ε-ball from a plane. Slot 56 showed the cost:
    10 attempts / 3 templates / 8 parameterisations / 6.01 h / 0 accepts, none clearing max|Δ| ≥
    0.05. (2) THE CAP bound first, but lifting it would not have reached 26 at the observed
    per-on-target cost (~1.9 h). Report BOTH, with the ceiling as the deeper one.
  - **FOUR FINDINGS FOR P-2 §2** (all survived adversarial re-checking): mid_gatherpoly **degree**
    controls the cell (deg=2 → MID 8/8; deg≥3 scatters INT) — A-3c framed it as a cache-tier
    corridor, but degree is the generation-time lever; **fm_dot × trap_wrap → bare FLAT 0/7** across
    both waves and 4 orders of magnitude in n (trap makes fast-math oracle-infeasible → fm_ratio
    ~1.1 → FM flag lost), while fm_dot without trap is 4/4; **greedy_gap is the separating
    coordinate** for FLAT+FM — small n leaves it non-zero, large n zeroes it, so populate this cell
    with SMALL n rather than sweeping n up; **two SLOT_EXHAUSTED modes** — clone-driven (slot 56,
    6.01 h) vs supply-driven (slot 60, 0.00 h, all free dup-skips); only the first costs budget.
  - **METHOD NOTE, recorded against myself:** my point projections for the final FLAT+FM n
    oscillated (26 → 23 → 21 → 18 → 16-17; actual 20) because I repeatedly extrapolated from the
    last 3-5 cycles. What held throughout was the per-on-target COST and the dimensionality
    mechanism. The P-2 report should carry those, not any projection. I also twice quoted a
    non-decision statistic (min clone distance instead of max|Δ|, which is what
    `anti_clone_check` tests) and once mis-attributed a template from the kernel_id instead of
    `spec.json`; all corrected in-commit, ledger never wrong.
  - **NEXT — STAGE 3, in order:** freeze (E4 integer alignment + exhaustive zero-label-change proof
    + FREEZE_MANIFEST.json) → holdout H (≥15, ≥3/confirmatory class) → all 9 R-anchor full tables →
    audit battery (stats-auditor, measurement-auditor ≥20% incl. the period slice, scrutinize) →
    P2_REPORT.md → **STOP for the human's freeze sign-off + P3 go. NEVER self-pass P-2.**
  - **WATCH AT H:** the holdout needs ≥3 per confirmatory class INCLUDING FLAT+FM — the cell whose
    property space is demonstrably tight. H draws fresh post-A-3 kernels so wave-2's consumed
    parameters do not block it, but the same 2-D vector applies. If H cannot reach 3 there, that is
    a SECOND honest negative to report, not something to engineer around.

A4_RESUMED (2026-07-25 — superseded by A3_WAVE2_COMPLETE above; kept for the resume record):
  - **STAGE 0 CLI RIDERS CLOSED** (detail in the block below + `results/cli_v0/CLI_V0_REPORT.md`
    §5a). D-numbers are **D13–D19**, not D9–D12 (taken). SEVEN records, not four — the rider work
    surfaced D17 (stale build manifest → raw ImportError), D18 (verify stage never built its own
    inputs; a real 2× degraded to honest-flat) and D19 (CF-1 busy predicate matched its own
    caller). **For the P-2 report: there are no D1/D2 files on disk — the series is D3–D19 (17
    records).**
  - **STAGE 1 PRE-FLIGHT — BOTH PASSED.** `measure_wrap --verify-only` PASS (run, not assumed).
    **CONTROLS_A4 RE-GATE PASS** into a FRESH dir (`results/fleet/controls_a4/`) so controls_a3's
    evidence is preserved: planted Δ_all=**10.9090**, opt_level top, −O3 faster → ok; flat
    Δ_all=**1.0165** ≤1.10, class A, IF-gated → ok; bcprobe bc_effect=0.1171 (characterization,
    NOT gated). **RIG STABILITY ACROSS THREE GATES** — wave-1 10.6747/1.0391/0.1205 · a3
    10.9216/1.0160/0.1181 · a4 10.9090/1.0165/0.1171. a3→a4 spans the whole cytune build, four
    container-heavy smoke campaigns and a host reboot: planted moved 0.12%, flat 0.05%. That is a
    measurement-validity datum for P-2 §4, not merely a green light.
  - **STAGE 2 RUNNING**: `run_fleet.py --stage topup --controls-dir controls_a4`, log
    `logs/governor/topup_a4.log`. Roster + forecast committed BEFORE the first kernel:
    `results/fleet/A4_RESUME_ROSTER.md` (PREREG §12 **A-6**, supply-only). LEVER_SEP_W2 narrowed to
    `[lev_modconst, lev_csr]` (lev_axpy → INT, int_sum64 drifted+orphaned: both are EVIDENCE, not
    supply); MID_W2 REORDERED so mid_gatherpoly (4/4 accepts, 0 clones) leads mid_hist (6 clones),
    mid_hist kept for parameter supply; FLAT+FM unchanged.
  - **FORECAST ON RECORD (judge it afterwards):** ~68 ks of the 101,873 s remaining (~9 h
    headroom) — FLAT+FM +11 ≈44.3 ks, MID +4 ≈17.2 ks, LEVER-SEP +2 ≈6.5 ks, from per-cell measured
    rates rather than a blended average. **Falsifiers named in advance:** clone rate rising as
    FLAT+FM fills 15→26 (its 4/4 diagonal rests on FIVE cycles); off-target accepts; one fat-tail
    kernel (~5 ordinary cycles). If any bind, the cap stops the run REGARDLESS of floors and the
    shortfall is reported with exact power at achieved n (A-3g) — pre-registered, a valid result.
  - **BOX IS MEASUREMENT-ONLY** for the whole resumed campaign: no dev work, no test suites,
    graphify deferred until the runner is down. Verified working in production — a commit during
    the run printed `DEFERRED — campaign runner (run_fleet.py) is alive`.

A4_PAUSE (superseded by A4_RESUMED above; kept for the pause-point record):
  - **AMENDMENT A-4 (2026-07-25, human-directed): SCOPE-ORDER ONLY, no science changed.** Full text:
    `results/prereg/PREREG_PHASEP.md` §12 A-4a–h. A P4-alpha `cytune` CLI is built and smoked BEFORE
    P-2 completion; the standing P-2 plan (freeze → H → R → audits → P2_REPORT → STOP) then resumes
    UNCHANGED. No threshold, cap, tier, metric, test, budget, seed, or study-design change. A-1
    (spent), A-2 (taxonomy freeze) and A-3 remain in force verbatim. CHECKPOINT P-2 is neither moved
    nor weakened and is NEVER self-passed.
  - **PAUSE POINT (exact):** last ACCEPTED wave-2 row = `fleet_MID_W2_53_mid_gatherpoly` (MID, commit
    e9da3fc). No partial table retained anywhere. Runner is DOWN (deliberate host reboot for a
    human-initiated OS switch — NOT a fault, NOT a D5/D12-class incident; no investigation owed).
  - **CAP AT PAUSE — THE PAUSE CONSUMES NONE (A-4c):** wave-2 spend **70,927.4 s / 172,800 s
    (41.0%)**, remaining **101,872.6 s ≈ 28.3 h**. Recompute: `run_fleet._topup_spend(
    'results/fleet/fleet_ledger.jsonl')`. The cap is defined over WAVE-2 LEDGER CYCLES; no wave-2
    cycle runs during the pause, and cytune's development measurements are not wave-2 rows — so the
    pause charges zero BY THE CAP'S EXISTING DEFINITION, not by an exemption invented for it.
  - **CELLS AT PAUSE** (recomputed, `run_fleet._cell_counts`): FLAT+FM **15** · MID **22** ·
    LEVER-SEP **24** · INT 39 · FLAT 15 (bare FLAT + INT are descriptive/oversaturated, not floors).
    Remaining to the n≥26 floor: **FLAT+FM +11 · MID +4 · LEVER-SEP +2.**
  - **IN-FLIGHT CYCLE, CHARGED NOT EXEMPTED:** `fleet_LEVER_SEP_W2_53_int_sum64` was interrupted
    mid-measure at 171/1728. Reconciled through the runner's OWN pre-registered path
    (`run_fleet._reconcile_inflight`) → **CYCLE_ORPHAN orphan_s = 1608.5 s charged to the A-3d cap**
    at the last-activity lower bound. Deliberately used the death-visible mechanism rather than the
    D12 environment-fault exemption, so a pause can never become a cap loophole.
  - **DISK ACTIONS TAKEN AT THE BOUNDARY** (~0.8 GB reclaimed; /home 52%, 20 G free):
    discarded `fleet_LEVER_SEP_W2_53_int_sum64/` (orphan-charged, zero git-tracked files, slot is
    being re-rostered away) and `fleet_FLAT_FM_W2_52_fm_sumsq_r1/` (abandoned partial build, NO
    ledger row, no measurement ever existed); D12-pruned `_so`/`_ccache` of the completed+tracked
    `fleet_MID_W2_53_mid_gatherpoly` (its 8 measurement artifacts verified intact). The 6
    `controls/` + `controls_a3/` build caches were KEPT ON PURPOSE — A-4 item 9 re-runs the controls
    gate before resume, and the B_05/C_04 precedent allows reusing a build cache for a re-measure.
  - **RESUME INSTRUCTIONS (do these IN ORDER when the human says resume; A-4 items 9–11):**
    1. `bash scripts/measure_wrap.sh --verify-only` → must exit 0.
       **CORRECTION (2026-07-25): my earlier claim here — "the reboot reset sysfs, so this WILL fail
       until host_prep re-runs" — was FALSE and is withdrawn.** I asserted it from the general rule
       that a reboot clears sysfs instead of checking. Verify-only was then run and **PASSED**
       (no_turbo=1, gov_cpu3=performance, cpu7_online=1, isolated=3,7, freq 3600000, thp=madvise),
       and all four cytune quiesced smoke runs measured on that verified rig. isolcpus comes from
       the kernel cmdline and survives a reboot. So: RUN the verify, do not assume its outcome; only
       run `sudo bash scripts/host_prep.sh` if it actually refuses. Box is back on
       `graphical.target` with Xorg up (headless did not persist across the OS-switch reboot).
    2. Re-run the controls gate into a FRESH dir (planted detected ∧ flat reads flat) — the host did
       CLI dev work in between; RE-VERIFY, never assume. HARD STOP on fail.
    3. RE-ROSTER by producer evidence (F2) BEFORE relaunching: LEVER-SEP (+2) draws the
       proven-separable cdiv-lever pool, **NOT `int_sum64`/INT-flavored drifters** (it drifted to INT
       and cost 1608.5 s for nothing); MID (+4) continues its working producer; FLAT+FM (+11) gets
       volume priority (~68% diagonal ⇒ ~16 generations). State roster + expected accepts against the
       28.3 h remainder BEFORE relaunch. Hard-stop at cap REGARDLESS of floors (honest final-n +
       exact power per A-3g — the pre-registered honest negative, never tuned away).
    4. Graphify hook stays deferred during measure phases (A-4h / F1).
  - **CYTUNE v0 DELIVERED (2026-07-25) — `results/cli_v0/CLI_V0_REPORT.md`; STOP for the human's
    resume call.** Runnable end to end (ingest→probe→route→tune→verify→certify). 4 live smoke runs,
    all reported: toy_running_max **1.9621x** (R4/DOE, quiesced) · pilot_C_01 **HONEST-FLAT**
    (R1, emitted the reference) · pilot_ctrl_planted **9.5859x** (R3, 49 of 1728 configs measured;
    the committed full table's delta_all is 10.185, approximately comparable only) ·
    toy portable 1.9646x. Raw: `results/cli_v0/`. Tests 72 passed / 1 skipped in-container.
  - **E3 GATE FOR THE CLI: bo-math-reviewer returned FAIL** — BO does NOT ship in v0; DOE-only
    (A-4f). NOT a finding that BO's math is wrong (EI re-derived, 0 ULP match); it is unfitness for
    live use: no emittability concept (chases fast-math configs the product may not emit; 37% of
    budget on ineligible candidates), returns a runtime not a config_id so the never-emit guarantee
    has nothing to attach to, no failure tolerance, and 4 of 8 gated properties are vacuous (4
    mutations leave all 12 test_bo.py tests green). Verdict verbatim in the report §4; evidence at
    `results/audit/P4alpha/e3_cli_gate/`. **This does NOT disturb the prior study-arm verdict**
    (PASS_WITH_NOTES, 2026-07-24) — different question, different setting. N1/N2 unchanged: N1 is a
    P-2 ratification debt; N2 blocks the first BO STUDY row and needs FREEZE_MANIFEST.
  - **4 DEFECTS FOUND AND FIXED** (detail in report §5). Two were found only by reading a real run
    end to end, and share a shape worth remembering: **each component was individually correct and
    the COMPOSITION was dishonest** — (D1) the honest-flat route emitted an "IMPROVEMENT 1.031x"
    verdict from a selection-biased probe minimum, contradicting its own routing text in the same
    document; (D2) the certificate said "fast-math: not opted in" while emitting
    `-ffp-contract=fast`, which is a different axis but still changes FP results. (D3) the
    honest-flat threshold (1.02) sat BELOW the phantom-speedup floor from taking a min over B noisy
    configs (1.064x at B=32, s=0.03) — reviewer finding F6, fixed with an endpoint-separation
    requirement, recorded as a v0 PRODUCT rule not a pre-registered threshold. (D4) graphify_drain
    failed OPEN when it could not resolve its repo root; now fails closed.
  - **CLI RIDERS CLOSED (2026-07-25, box idle — dev work done HERE, not during the campaign):**
    1. **D-SERIES: the four CLI defects are D13-D17, NOT D9-D12.** The directive said D9-D12; those
       are TAKEN (D9 stencil OOB, D10 SLOT_EXHAUSTED miscount, D11 FLAT-vs-FLAT+FM cell, D12 disk).
       Verified against `logs/defects/` before numbering, as instructed. Next free was D13.
       Five records, not four — the rider work itself surfaced D17. Full post-mortems:
       D13 (flat route certified an IMPROVEMENT from a selection-biased probe minimum),
       D14 (undisclosed `-ffp-contract=fast` beside "fast-math: not opted in"),
       D15 (fixed 1.02 emit floor below the phantom-speedup floor — reviewer F6),
       D16 (graphify_drain failed OPEN), D17 (stale build manifest -> raw ImportError).
       **NOTE for the P-2 report: there are no D1/D2 files** — the series on disk starts at D3.
       Report the D-series as D3-D17 (15 records), not "D1-D12".
    2. **COMPOSITION-LEVEL E2E CHECKS** (`scripts/cytune_e2e_composition_check.py`): D13 and D14
       are properties of the WHOLE pipeline output and were invisible to unit tests of the parts.
       Runs BOTH directions — green on current code, **RED on reconstructed pre-fix behaviour**
       ("flat route produced verdict=improvement", "undisclosed FP flag is CAUGHT"). Host-side
       (spawns podman); transcript `results/cli_v0/transcripts/composition_checks.txt`.
    3. **EMIT THRESHOLD GENERALIZED to every route**: `margin = max(2 x combined endpoint CV, tau)`,
       tau=0.02 inherited (PREREG §1.1). Replaces the fixed 1.02. Stated in every certificate WITH
       the caveat "v0 product rule, not a pre-registered study threshold". Honest note recorded in
       code and tests: the margin **subsumes** the earlier separation rule in practice (both key off
       the same spread; no fixture isolating separation is constructible for n>=3), so separation is
       kept as a cheap rank-based second guard and reported diagnostic, NOT as an independent
       verdict driver.
    4. **PREREG A-5 ADDENDUM COMMITTED BEFORE ANY REPLAY RUN EXISTS** — secondary regret slice on
       the emittable-under-default subset (feasible AND fast_math=off, i.e. exactly §1-v2's
       t_strict set), per regime x budget x algorithm. Additive: primary metric, tests, seeds and
       decision rules untouched; never substituted for the primary. Harness support landed too
       (`replay.run_algorithm` records it post-hoc from the already-whitelisted `queried_ids`) so
       the registration is real rather than a promise — algorithms, the sealed interface and the
       §9.3 cheat-test are all unchanged (15 replay tests still green, cheat-test included).
       Writing its tests caught a definitional error in my own metric before first use:
       `queried_ids` is seeded with the free reference while `budget_used` excludes it, so the
       budget fraction exceeded 1.0; the numerator now counts PAID queries only, commensurable with
       the E3 "37.0% of paid budget" figure it generalises.
  - **FIREWALL IS PERMANENT (rider 4):** the AST fleet/H/R-access scan
    (`src/cytune/test_cytune_firewall.py`) stays ARMED for ALL future CLI work until P4 acceptance
    is EXPLICITLY sanctioned by the human. It carries a positive control (a planted violation must
    be caught, else the scanner is vacuous) and a negative control (prose about the firewall must
    not trip it). No CLI change ships without it green. Removing or weakening it is a human
    decision, never a maintenance one.
  - **DATA FIREWALL, BINDING WHILE PAUSED (A-4d):** cytune touches DEVELOPMENT DATA ONLY — demoted
    pilot kernels (A-2b) + fresh toy modules authored outside every dataset. `results/fleet/**`, the
    holdout **H**, and the 9 **R** anchors are NOT read to tune it, NOT measured by it, NOT written
    by it. This is what keeps §3.5 (RQ-P2 evaluated at P4 on H+R only) evaluable at all.
A3_execution:
  - HUMAN RULED (P-2 COMPLETION directive, 2026-07-24): A-3 top-up approved with caps; E4 =
    align code at freeze + ratify erratum; H = ≥15 fresh post-A-3 synthetic (≥3/class incl.
    LEVER-SEP) + all 9 R-anchors; then audit battery → P2_REPORT.md → STOP for freeze sign-off.
    Full sequence + binding: results/fleet/A3_TOPUP_AMENDMENT.md §6.
  - **F2 CELL AUDIT — CORRECTION TO THE SYNTH-COMPLETE ENTRY BELOW:** the confirmatory families
    are CELLS (A-2c verbatim): FLAT+FM means measured FLAT ∧ FM+ (FLAT∧FM− descriptive-only).
    Measured wave-1 cell n: **FLAT+FM 11 · MID 18 · LEVER-SEP 23 · INT 37 · FEAS+ 50.** The
    "FLAT 26 ✓" line below silently substituted the bare class for the flagged cell ⇒ wave-1
    honest negative is **1 of 4 cells cleared (INT), not 2 of 4**; FLAT+FM (+15) is the largest
    shortfall, not LEVER-SEP. No label/table/measurement affected — derived count only. Raw:
    results/fleet/template_analysis_final.json; recompute scripts/phasep/template_analysis.py.
  - A-3 COMMITTED (PREREG §12 A-3a–g + memo + basis artifact) BEFORE any wave-2 kernel:
    scope +15/+8/+3 to the three sub-26 cells; producers-only templates (FM dtype finding:
    double→FM+ 8/9, float→0/6; MID corridor L2-tier 6/6; lev_csr/modconst/axpy/int_sum64 for
    LEVER-SEP); hard cap 172,800 s Σ(build+measure) over wave-2 cycles, TOPUP_CAP_STOP
    regardless of floors; allocation FLAT_FM→MID→LEVER_SEP round-robin skipping filled cells;
    wave labels everywhere + P3 with/without-wave-2 robustness slice PRE-REGISTERED; controls
    re-gate into results/fleet/controls_a3/ (HARD STOP; wave-1 gate dir preserved); no wave-2
    nulls (drift stands; FLAT-negative-control P3 check pre-registered); exact power at
    achieved n from committed power(n, δ=0.4, SEED_EXT stream, N_SIM 60000) in-container.
  - H-sourcing conflict check (ruling requirement): ruling ≈ option (a) in substance; one
    difference surfaced in memo §5 — A-3 regenerates NOTHING (wave-1 stands; wave-2 adds).
  - **RIG-DISCIPLINE INCIDENT (self-inflicted, 2026-07-24 — measurement DISCARDED, not trusted):**
    the first controls_a3 gate attempt was contaminated. Build ran 07:14–07:45:53 (untimed, fine);
    the timed measure phase began 07:45:53 while (a) a 22-agent adversarial review workflow I had
    launched was still running to ~07:53 and (b) an auditor subagent's abandoned container
    (`e3_checks3.py`, sys.settrace coverage) burned ~97% of a core 07:35–07:52:58. All 626 rows
    measured to that point overlapped host contention. Because config_id order correlates with the
    -O1/-O3 factor, a time-correlated slowdown can ALIAS ONTO A FACTOR — precisely the confound
    that would corrupt the planted control's Δ and its opt-dominance criterion. Response: killed
    the run + orphaned measure chain, verified rig quiesced (verify-only PASS), DELETED the
    contaminated measure products (table/oracle/golden; build cache of 1728 .so kept — B_05/C_04
    precedent), and re-ran the gate on a quiet box. NO contaminated number was read, reported, or
    used as a gate verdict. STANDING RULE for the rest of P-2: no multi-agent workflows and no
    sustained CPU during any timed phase; code/tests are batched BEFORE a measurement launch.
    Goes in the P-2 report §4 as a self-reported measurement-validity event.
  - **E3 RE-ACK COMPLETE — bo-math-reviewer: PASS_WITH_NOTES** (2026-07-24, read-only; raw +
    independent scripts `results/audit/P3.3/e3_reack/`). Verified: mod-2^32 applied at the CONSUMER
    only (`bo.py:108`, sole occurrence in scripts/phasep); `seeds.py` + `seed_fixtures.json`
    BYTE-IDENTICAL to their P1.0 commit (blob hashes compared); 15/15 committed fixtures reproduced
    from an INDEPENDENT pure-Python reimplementation of FNV-1a + numpy SeedSequence mixing
    (cross-validated on 200 keys); E3's premise confirmed live (sklearn rejects the uint64,
    accepts the reduction); no other seed consumer altered; determinism holds across 3 processes;
    alg_id still discriminates BO(3) vs Motif+BO(4) after reduction. COLLISION SWEEP (computed,
    not asserted): 0 collisions over the 104 accepted kernels × 2 algs × 200 seeds = 41,600 keys;
    within-(kernel,alg) replicate collisions 0/1,406 groups. Prior note (b) CLOSED — motif §8.4
    <8-warm-config fill proven non-vacuous by MUTATION (deleting the fill kills
    `test_motif_84.py`'s EXPERT assertion 40/40 seeds). Container: test_bo 11, test_motif_84 4,
    test_motif 6, test_run_study 7 — all pass. **P3.3 BO study entry UNBLOCKED**, conditional on
    two report deliverables below.
    - **N1 (GOVERNANCE — for the human at P-2, NOT self-applied):** PREREG §8.3 still pins the
      UNREDUCED derivation, and E3 CANNOT be filed under the existing "Errata" heading, which is
      scoped verbatim to "post-commit prose corrections with ZERO semantic effect". E1/E2 qualify;
      E3 does NOT — the value the model consumes changes (5959135207994664877 → 420194221). Zero
      effect on any committed artifact and zero study data affected (no BO row exists), but the
      ratification text must (i) amend §8.3's random_state line to include the `% 2**32` and
      (ii) state that scope honestly instead of inheriting the "zero semantic effect" boilerplate.
    - **N2 (blocking the first BO row):** re-run the collision sweep against the FROZEN study set
      once FREEZE_MANIFEST exists and record the count. Computed forward estimate at the final
      size: P(≥1 cross-kernel collision) ≈ 10.7–27%. Impact if one occurs is bounded — colliding
      runs are on DIFFERENT kernels with DIFFERENT bo-init streams, so trajectories are not
      duplicated and the 200-seed replicate class is provably collision-free — but it must be
      counted and disclosed, not assumed away.
    - N3 CLOSED by me: named regression test added (`test_bo.py::test_e3_rf_random_state_reduced_
      at_the_consumer`) — the pinned branch was previously exercised by NO test in test_bo.py.
    - N4 (pre-existing, awareness only): the `bo-init` key omits alg_id BY THE §8.3 PIN, so BO and
      Motif+BO share the init/interleave stream for the same (kernel, seed) — deliberate paired
      randomness, not an E3 side-effect. The RF stream does carry alg_id.
  - **A-3 PREFLIGHT REVIEW (adversarial, before any wave-2 measurement): 17 raw findings → 12
    CONFIRMED / 5 refuted.** Fixed before launch, each with a named test whose revert fails it:
    (1) BLOCKER — the A-3d cap leaked: BUILD_FAIL/MEASURE_FAIL rows carried no timings, so failed
    cycles charged ZERO against a HARD human-approved cap (wave-1 evidence: all 3 MEASURE_FAIL
    rows lack timings, two datable at ~1 h each). (2) MAJOR — a cycle killed mid-phase was
    invisible to the cap and accumulated unboundedly across relaunches; now reconciled as
    CYCLE_ORPHAN at a last-activity lower bound. (3) MINOR — TOPUP_CAP_STOP could be skipped
    entirely (recorded as "rosters exhausted") or duplicated on relaunch; cap is now evaluated
    before roster state and recorded once. (4) MINOR — topup_summary.json was truncated on
    relaunch; now rebuilt from the append-only ledger. (5) MINOR — A-3b's wave label reached
    neither FREEZE_MANIFEST (write-once! would have been unfixable) nor any wave-1 spec.json;
    manifest now carries `wave`, `study_set(waves=...)` implements the robustness slice, and 122
    specs were backfilled. (6) MINOR — memo/code drift on the fm_sumsq n-set (the E4 defect class)
    corrected. Cap ceiling stated honestly: cap + at most one in-flight cycle ≈ 2.19 days.
  - **CONTROLS_A3 RE-GATE PASS (A-3e, 2026-07-24; clean-box re-run after the discarded contaminated
    attempt).** Raw: results/fleet/controls_a3/controls_gate.json + per-control class_record/endpoint.
    planted Δ_all=10.9216, opt_level DOMINANT (0.862, top main effect), -O3 faster → ok:true
    (criterion Δ≥1.6 ∧ opt largest ∧ -O3 faster; priors 10.19/10.675 — in family, ~7% spread, no
    drift). flat Δ_all=1.0160 ≤1.10 → ok:true (priors 1.045/1.0391; IF=0.939 correctly A-1b-GATED
    to class A — Δ<1.10 ⇒ IF is noise/noise; validated a 3rd time; endpoint agreement_binary_ok
    True, τ_b=−0.16 = the correct flatness signature, no rank signal to correlate — NOT a defect).
    bcprobe (A-1c characterization, NOT gated): bc_effect=0.118, matches pilot 0.118 / wave-1 0.120
    — bc ceiling stable on this rig. GATE PASS ⇒ wave-2 measurement is unblocked (run_fleet
    structurally refuses without this file). For P-2 §5: the gate itself carried the fat tail —
    flat is a pointer-chase (same latency-bound class as null_chase, 256min measure in wave-1), so
    its endpoint CV gate ran long; gate cost is a real envelope line item, not overhead.
  - EARLY E4 VERIFICATION (over wave-1's 122 kernels; authoritative run repeats at freeze under the
    aligned code): ZERO label changes. Layer 1 exhaustive 1,495,584 (n,k) pairs n≤1728, 0
    disagreements; knife-edge 432/1728 exactly representable, both predicates fire → MID+FEAS.
    Layer 2: 3 kernels sit EXACTLY on 0.25 (int_min32, int_max32, int_sum64_r3) — the knife-edge is
    populated by real measured kernels, so E4 ratification is concretely evidenced. Raw:
    results/fleet/E4_ALIGNMENT_EVIDENCE.json.
  - **D12 — /home hit 100% mid wave-2 (unpruned _so caches); recovered, 0 data lost** (2026-07-24;
    logs/defects/D12.md). results/fleet grew to 52G (≈355MB/kernel of gitignored _so+_ccache ×130
    kernels) on a 43G disk. FIX: pruned _so/_ccache of 262 COMPLETED kernels (reproducible from
    committed pyx; tables committed; freeze/study/auditors read table.jsonl not _so) → freed 23G
    (100%→45%). The in-flight FLAT_FM_W2_52 fm_sumsq was in its BUILD phase when the disk filled —
    ENOSPC can be miscached as feasibility-0 (correctness risk), so it was DISCARDED and rebuilt
    fresh (no measurement existed). Rig re-verified PASS; runner resumed at fm_sumsq; 6 prior
    wave-2 acceptances intact. The ~25min discarded build is operational cost (env fault), NOT
    charged to the A-3d cap (mirrors runner-death idle). STEWARD RULE going forward: prune
    completed-kernel _so/_ccache each tick to keep /home bounded through wave-2 + H + R.
  - WAVE-2 PROGRESS (at the D12 recovery point): 6 ACCEPTED — FLAT+FM 13 (fm_sum, fm_dot n=1.2M),
    MID 20 (mid_gatherpoly deg2; +lev_csr nnz8 spill), LEVER-SEP 24 (lev_modconst), INT 38
    (mid_gatherpoly deg3 overshoot, already-full cell) — + 3 REJECTED_CLONE (mid_hist ×3). Cap
    ~33568s/172800 (~19%). Targets remaining: FLAT+FM +13, MID +6, LEVER-SEP +2.
  - **DEFINITIVE CELL RULE (from CODE _cell_counts run_fleet.py:158-159; supersedes my earlier
    taxonomy notes in 3d99923 AND 374c83b, both of which I got wrong — 2026-07-25)**:
    `cls=measured_v2; cell = "FLAT+FM" if (cls=="FLAT" and flag_FM) else cls`. So the confirmatory
    CELL is: FLAT+FM = measured_v2==FLAT ∧ flag_FM=True; bare FLAT = FLAT ∧ ¬flag_FM (docstring L148:
    "descriptive-only, NOT counted toward any floor"); MID/INT/LEVER-SEP = measured_v2 directly.
    **flag_FEAS is NOT part of cell assignment** — it is an orthogonal feasibility property (redefined
    at the E4 step 4·n_inf≥n_total, reported alongside Δ_strict), NOT a FLAT/FLAT+FM discriminator.
    MY TWO PRIOR ERRORS, corrected: (a) 3d99923 said fm_sum flag_FM=False → FALSE, it is True;
    (b) 374c83b said flag_FEAS gates FLAT-vs-FLAT+FM and the kernel is "bare FLAT" → FALSE, the cell
    is FLAT+FM because flag_FM=True. Committed DATA (ledger/class_v2) was always correct; only my prose
    erred. fm_sum_r1 (measured_v2=FLAT, flag_FM=True, flag_FEAS=False) → FLAT+FM cell = correct.
  - FEASIBILITY-GATE OBSERVATION (still valid, but it's a REPORTED property, not a cell rule):
    fm_sum's FM win (fm_ratio 3.987, delta_all 3.987) is strict-INFEASIBLE (flag_FEAS=False, breaks
    oracle on 576/1728, delta_strict=1.0). Such kernels STILL populate FLAT+FM (cells don't gate on
    feasibility) but their infeasibility is recorded in the intended-vs-measured + Δ_strict ledger —
    auditors/P2_REPORT must note the FLAT+FM cell includes flag_FEAS=False members. Good gate
    illustration for the report; does NOT reduce the FLAT+FM count.
  - PROJECTION REVISED UPWARD: because FLAT+FM = FLAT ∧ flag_FM (feasibility-independent), the FM
    producers (fm_sum/fm_dot/fm_sumsq) yield FLAT+FM whenever flag_FM=True (common) — so FLAT+FM +12
    is MORE reachable than the earlier pessimistic honest-negative lean; the binding constraint is
    anti-clone property-diversity across the 3 FM templates, not feasibility. Watch clone-rejection
    rate as FLAT+FM climbs.
  - NEXT (bound order): (1) generate_v2 W2 registries + run_fleet --stage topup + TDD, commit;
    (2) controls_a3 re-gate (HARD STOP on fail); (3) topup launch + stewardship to floors/cap;
    (4) freeze boundary: E4 align (4·n_inf ≥ n_total) + exhaustive zero-label-change evidence +
    FREEZE_MANIFEST (waves+hashes); (5) holdout H + anchors R; (6) auditors + E3 re-ack +
    scrutinize → P2_REPORT.md → STOP P-2 (never self-passed).
phase / subphase.step / timestamp_utc : P2 / SYNTH RUNNING (30/130) — supply-cap + A-2h prose-vs-code errata, two human decisions flagged / 2026-07-20
P2_confusion_watch:
  - SECOND INDEPENDENT n-EROSION MECHANISM (partial, 32/130 — surfaced early, NOT acted on): under
    rider R3 the confirmatory families populate by MEASURED class, but the fleet allocates slots by
    INTENDED regime. The two do not agree well. Measured confusion so far:
    FLAT+FM intended n=25 (block FINAL, exhausted) → 17 FLAT / 3 MID / 0 LEVER-SEP / 5 INT = **68%
    diagonal**; MID intended n=7 (of 30) → 1 FLAT / 2 MID / 2 LEVER-SEP / 2 INT = **28.6% diagonal**,
    scattered across ALL four classes.
  - MEASURED-CLASS POPULATION vs the n=26 floor (what R3 makes binding): FLAT 18 · MID 5 ·
    LEVER-SEP 2 · INT 7 (total 32). Recompute: tally `measured_v2` over ACCEPTED non-holdout
    non-R rows of results/fleet/fleet_ledger.jsonl.
  - REFINEMENT (36/130, supersedes the "scattered" framing above — the off-diagonal is STRUCTURED,
    not noise): grouping by template shows most of the confusion is TEMPLATE-CONSISTENT, i.e. specific
    templates systematically produce a class other than the one they were designed for.
    CONSISTENT-and-WRONG: `fm_abssum` 4/4 → INT (intended FLAT+FM) · `mid_convert` 2/2 → LEVER-SEP
    (intended MID) · `mid_gatherpoly_deep` 1/1 → INT (n=1, weak). CONSISTENT-and-CORRECT: `fm_sum`
    6/6 · `fm_dot` 5/5 · `fm_sumsq` 4/4 · `mid_gatherpoly` 2/2. PARAMETERIZATION-DEPENDENT (MIXED):
    `fm_altsum`, `fm_runmean`, `mid_branchy`, `mid_hist`, `mid_stencil`. Recompute: group ACCEPTED
    rows by (intended_regime, template) and tally measured_v2. Per-template n is 1–6, so the MIXED
    calls and any n≤2 CONSISTENT call are weak; `fm_abssum`(4) `fm_sum`(6) `fm_dot`(5) are the solid
    ones. INTERPRETATION: this is a GENERATOR-CHARACTERIZATION finding (design-time landscape
    prediction was wrong for named templates), not measurement noise — it belongs in P-2 §2 as such.
    Still NO action: R3 assigns measured class; retuning templates remains a scope change.
  - INTERACTION WITH THE SUPPLY-CAP: these are DISTINCT mechanisms and they compound — the supply-cap
    erodes how many SLOTS a regime can fill; the confusion erodes how many filled slots LAND in the
    intended class. A regime can hit its 30-slot target and still leave its measured class short of 26.
  - UNCERTAINTY STATED: only 2 of 5 blocks are touched. FLAT+FM is final (25, exhausted); MID is 7/30;
    LEVER_SEP, INT and NULL blocks are entirely unrun, so 3 of 4 measured classes cannot yet be
    projected. MID is currently the class most at risk. No claim beyond the 32 measured rows.
  - NO ACTION TAKEN, BY DESIGN: raising the diagonal = retuning generator templates = a SCOPE change
    (STOP-THE-FLEET-class). PREREG §2 / A-2b already govern the outcome: sub-26 measured classes are
    presented at P-2 with the power consequence stated, not tuned away. The directive's own words:
    "an off-diagonal pattern is a finding to report, not tune away." Feeds CHECKPOINT P-2 §2 verbatim.
SYNTH_STAGE_COMPLETE (2026-07-24 — runner exited cleanly, 104 accepted; AT THE P-2 BOUNDARY):
  - FINAL measured-class population vs the n=26 δ=0.4 floor:
      INT 37 ✓ · FLAT 26 ✓ · LEVER-SEP 23 (MISS by 3) · MID 18 (MISS by 8).
    ⇒ **2 of 4 confirmatory classes clear the floor; 2 miss** — MID clearly, LEVER-SEP a NEAR-miss.
    Pre-registered honest negative (PREREG §2 / A-2b); reported with power consequence, not tuned.
  - FINAL confusion (intended→measured, diag): FLAT+FM 68% (17/3/0/5) · MID 41% (5/12/3/9) ·
    LEVER-SEP 54% (2/1/14/9) · INT 63% (0/1/6/12) · NULL-as-FLAT off-design (2/1/0/2 → half the
    5 accepted nulls carry a real landscape). Recompute: report_p2.build_report or the group-by in
    the synth-complete tick. Directional drift confirmed end-to-end: FLAT/MID never reach LEVER-SEP
    (0 in 54); the lever-heavy classes (LEVER-SEP↔INT) swap across the IF_strict 0.25 knife-edge.
  - **KEY POSITIVE — RIDER R1 IS POWERED:** FEAS+ measured = **50 ≥ 26** floor. The product's core
    RQ-P1 (feasibility-weighted EIC, BO<RS) has its confirmatory n even though the landscape-class
    floors were missed — FEAS is the orthogonal flag, a different axis. Realized 50 vs the 60
    designed (15/15×4); still powered at δ=0.4.
  - LEDGER (whole synth campaign): ACCEPTED 104 · REJECTED_CLONE 18 (each with 5 distances) ·
    SLOT_EXHAUSTED 115 entries / ~21 distinct slots · MEASURE_FAIL 3 (D7/D8/D9, all fixed) ·
    dup-skips 1834 (D8 pre-guard ≈ 1680 h of measurement avoided).
  - NEXT IS HUMAN-GATED (autonomous stewardship ends here): holdout + freeze + P-2 report + auditors
    are the CHECKPOINT, all STOP-for-human. Two decisions block them: (1) H-SOURCING (options a-d,
    commit 8478d5c) — now sharpened by the LEVER-SEP 3-kernel near-miss; (2) ERRATUM E4 (float-vs-int
    FEAS compare, proven zero-impact — ratify as doc erratum or align code at freeze). NO freeze
    manifest created, NO study run, NO report self-passed.
P2_all_confirmatory_blocks_FINAL (at 99/130 — only NULL remains; endgame projection):
  - INT block FINAL: **19 accepted of 30 slots** (11 lost: rejections #12-16 + slots 25/26/28-35
    SLOT_EXHAUSTED entirely via free dup-skips), diagonal **12/19 = 63%**, classes 12 INT / 6
    LEVER-SEP / 1 MID. The original supply-cap finding predicted INT worst at ~24 distinct — realized
    19 accepted + ~5 measured rejections ≈ 24. **The pre-campaign supply prediction was near-exact.**
  - ALL FOUR CONFIRMATORY BLOCKS NOW CLOSED (final diagonals): FLAT+FM 68% (25 acc, 5 exh) · MID 41%
    (29 acc, 1 exh) · LEVER-SEP 54% (26 acc, 4 exh) · INT 63% (19 acc, 11 exh).
  - ENDGAME (10 NULL slots left; honest-nulls are designed FLAT): FLAT 24+2 → CLEARS · INT 35 →
    CLEARED · **LEVER-SEP 23 needs 3 but NULL will not supply lever landscapes → likely finishes
    23-24, JUST SHORT of 26** · MID 17 → SHORT. Expected misses back to **2 of 4 (MID clearly,
    LEVER-SEP by a hair)** — the INT block's early exhaustion closed LEVER-SEP's spill source ~3
    kernels too soon. Honest negative per PREREG §2/A-2b; the near-miss margin (2-3 kernels) is
    itself decision-relevant context for the human's H-sourcing call at P-2.
P2_int_block_reverses_lever_sep_starvation (at 86/130 — REVISES the floor projection AGAIN, with data):
  - LEVER_SEP block FINAL: 26 accepted (4 SLOT_EXHAUSTED), diagonal 14/26 (54%). Final template
    split: lev_csr 6/6 · lev_modconst 4/4 · lev_axpy 4/6 (producers, 14/16 combined) vs
    lev_clipmap 0/4 · lev_sqrtmap 0/4 · lev_strided 0/2 (non-producers, 0/10).
  - THE SURPRISE (investigated, mechanistically coherent): INT block first 6 = [LEVER-SEP,
    LEVER-SEP, MID, LEVER-SEP, INT, INT] — **half land LEVER-SEP**, the class nothing else spilled
    into. REFINES the directional-drift claim: FLAT/MID-designed kernels never drift to LEVER-SEP
    (0 in 54), but INT-designed kernels are LEVER-SEP's NEIGHBORS — both need Δ_strict≥1.5 and only
    the IF_strict 0.25 knife-edge separates them, so drift between the two lever-heavy classes flows
    BOTH ways. The earlier "LEVER-SEP can only be populated deliberately" stands for FLAT/MID
    sources; the INT block is a legitimate second supply.
  - FLOOR PROJECTION REVISED (44 kernels remain: INT 24, NULL 10; supersedes "2 of 4 miss"):
      FLAT      24 (needs 2) → NULL block supplies; CLEARS.
      INT       25 (needs 1) → next INT-measuring kernel clears it; CLEARS imminently.
      LEVER-SEP 20 (needs 6) → 24 INT slots spilling LEVER-SEP at ~50% so far ⇒ **plausibly CLEARS**.
      MID       17 (needs 9) → thin spill only ⇒ still the likely honest-negative MISS.
    ⇒ Expected misses now 1 of 4 (MID), down from 2 of 4. Confusion table (P-2 §2) captures all of it.
P2_lever_sep_block_measured (at 64/130 — UPDATES the projection below with data):
  - LEVER_SEP block 10/30, diagonal **5/10 = 50%** (vs MID 41.4%, FLAT+FM 68.0%). NOTE the field
    value is `intended_regime == 'LEVER-SEP'` (HYPHEN); an underscore filter silently returns 0.
  - THE SPLIT IS CLEAN AND TEMPLATE-DETERMINED — half the LEVER_SEP-designed templates work, half
    never do: PRODUCES LEVER-SEP 5/5 → `lev_csr` 2/2 · `lev_modconst` 2/2 · `lev_axpy` 1/1.
    NEVER PRODUCES IT 0/5 → `lev_clipmap` 2/2→INT · `lev_sqrtmap` →INT,FLAT · `lev_strided` →FLAT.
  - THIS CORRECTS the "LEVER-SEP may be unhittable / needs ~76% diagonal" framing above: LEVER-SEP
    IS reliably hittable *deliberately* (5/5 on the three good templates). The real defect is
    narrower and nameable — **three of the six LEVER_SEP templates were mis-designed** and yield
    interaction-dominated or flat landscapes instead. That is a concrete generator finding for a
    post-P-2 amendment, NOT actionable now (retuning templates mid-fleet = scope change).
  - FLOOR OUTCOME (projection at measured rates; 66 kernels remain — LEVER_SEP 20, INT 30, NULL 10):
      FLAT      24 (needs 2)  → CLEARS.
      INT       17 (needs 9)  → own 30-slot block plus continuing INT-ward drift → CLEARS.
      MID       15 (needs 11) → block CLOSED at 41.4%, spill only → lands ~18-22, **MISSES 26**.
      LEVER-SEP  8 (needs 18) → 8 + 20×0.50 → ~18, **MISSES 26**.
    ⇒ EXPECT 2 of 4 confirmatory classes below the δ=0.4 power floor. Pre-registered honest negative
    (PREREG §2 / A-2b): reported with the power consequence, never tuned away.
P2_confusion_is_directional (FINAL for 2 of 5 blocks, at 55/130 — for CHECKPOINT P-2 §2):
  - Both completed blocks (intended → measured; FLAT+FM n=25 with 5 SLOT_EXHAUSTED, MID n=29 with 1):
      FLAT+FM : 17 FLAT · 3 MID · **0 LEVER-SEP** · 5 INT  → 68.0% diagonal
      MID     :  5 FLAT · 12 MID · 3 LEVER-SEP · **9 INT** → 41.4% diagonal
    Recompute: group ACCEPTED non-holdout non-R rows by (intended_regime, measured_v2).
  - THE FINDING — the off-diagonal has a DIRECTION, it is not symmetric scatter: across 54 kernels
    from two blocks, **14 landed INT unintentionally vs only 3 LEVER-SEP**, and the FLAT+FM block
    produced ZERO LEVER-SEP in 25 attempts. Mechanistic reading (hypothesis, testable when the
    LEVER_SEP block lands): LEVER-SEP requires a CLEAN dominant lever with IF_strict<0.25 — a special
    low-interaction structure rarely hit by accident — whereas interaction-dominated landscapes are
    the generic outcome, so accidental drift lands in INT. Consequence: INT self-populates from
    everyone else's misses; LEVER-SEP can only be populated deliberately, by its own block.
  - FLOOR PROJECTION (69 kernels remain: LEVER_SEP 29, INT 30, NULL 10):
      FLAT 22 (needs 4)  → clears on spill alone. LIKELY OK.
      INT  14 (needs 12) → own 30-slot block PLUS the directional spill above. LIKELY OK.
      MID  15 (needs 11) → only spill left (block closed at 41.4%); lands ~22-25. BORDERLINE SHORT.
      LEVER-SEP 4 (needs 22) → needs ~76% diagonal from its own 29 slots; no block has beaten 68%.
        MOST AT RISK. First data point is favourable (LEVER_SEP_06_lev_csr measured LEVER-SEP,
        on-diagonal) but n=1 — explicitly NOT projectable yet.
  - SUPERSEDES my earlier "MID is the class most at risk" framing: with the MID block closed and the
    INT-ward drift quantified, **LEVER-SEP is the acute risk and INT is the surprise beneficiary.**
  - NO ACTION (unchanged): R3 assigns measured class; retuning templates to chase the diagonal is a
    scope change. PREREG §2/A-2b govern — sub-26 classes are reported with the power consequence.
P2_envelope_actuals (for CHECKPOINT P-2 §5; measured, n=60 cycles at 53/130):
  - MUST SEGREGATE WARM FROM COLD: 5 cycles have build_s≈0 (cache hit after a runner relaunch) and
    median 27.8 min — these are RELAUNCH ARTIFACTS, not measurement, and pooling them deflates the
    envelope. They correspond 1:1 with the 5 runner deaths. Report COLD only.
  - COLD-build actual (n=55): total median **57.3 min/kernel** (build med 25.0 + measure med 32.1),
    max 75.2, min well under. vs PREREG D3 band **55–105 min/kernel**: 32/55 (58%) within band,
    **42% BELOW 55**, **0% above 105**. Recompute: group ledger ACCEPTED+REJECTED_CLONE rows by
    build_s>60, take (build_s+measure_s)/60.
  - HONEST READING (favorable surprise, investigated not celebrated): the band is violated only on
    its LOWER edge — the campaign is CHEAPER than budgeted, never more expensive. The D3 band is
    mis-centred, not the rig mis-measuring. No de-scope needed; the fleet-size lever is untouched.
  - SLOW-SIDE EXCEEDANCE (update at 103/130): the `null_chase` pointer-chase kernels are the
    exception on the HIGH edge. NULL_10_r1 (measured FLAT, REJECTED_CLONE) recorded build 1466s +
    measure **15340s = 256 min** ⇒ ~280 min total, ~2.7× the 105-min band ceiling. Cause is
    structural: memory-latency-bound so REPS-per-target is tiny AND high-variance, so the endpoint
    CV>0.05 gate takes the max 5 sub-measures/config over 173 top-decile configs. Bounded, correct,
    but it means the envelope has a fat high tail on latency-bound templates — P-2 §5 must report the
    band as [~21 (warm-relaunch) … ~280 (null_chase)] with the median, not a symmetric band.
    SECOND-ORDER: paying ~4.7 h to then anti-clone-REJECT is the slow-kernel analogue of the
    anti-clone-vs-scarce-class tension; the D8 pre-guard only catches EXACT param dups for free, so
    property-space near-clones on slow kernels are expensive by design. Not actionable (designed
    behavior); flagged as a real cost characteristic.
  - OPERATIONAL COST NOT IN THE ENVELOPE: 8 runner deaths so far, all environment-driven (session/
    host restarts), none from fleet code. Each costs idle machine time bounded by the heartbeat
    interval; the worst (death #5) went undetected ~2 h. The resumable design lost ZERO measurements
    across all eight. If idle time becomes material, an auto-restart supervisor is the obvious lever —
    NOT built, since adding supervision to a live measurement campaign is a human decision.
  - **ROOT CAUSE OF THE FREEZE CLUSTER = nouveau GPU driver crash (deaths #6/#7/#8; HUMAN ACTION
    NEEDED)**. Three hard freezes in ~1h43m (Jul24 23:12 / 23:52 / Jul25 00:55). `journalctl -b -N -k`
    shows the SAME signature ~1 min before EACH reboot: `nouveau 0000:01:00.0: gsp: mmu fault queued`
    → `gsp: rc engn:1 chid:4 ... fault_type:2` → `fifo:[Xorg]: channel 4 killed` (boot -3 also logged
    `error fencing pushbuf: -19`). GPU = NVIDIA GTX 1650 SUPER (TU116/Turing, GSP-firmware) on the
    open-source **nouveau** driver; i3-10100**F** has NO iGPU so this card is the ONLY display adapter
    and must drive Xorg. Thermal RULED OUT (pkg ≤55°C, cool). The measurement stack is innocent:
    headless `--network=none` container on isolated cpu3, GPU never used — the crash is in the desktop
    display path (Xorg-on-nouveau), independent of the campaign. RECOMMENDATION TO HUMAN (cheapest
    first): (1) run the box HEADLESS during campaigns (`sudo systemctl isolate multi-user.target`, or
    set default target to multi-user) — no Xorg → no GPU channel → removes the reproduced fault path,
    zero install, manage via SSH/console; (2) or replace nouveau with the proprietary NVIDIA driver
    (Fedora RPM Fusion `akmod-nvidia`) for a stable desktop. Until fixed, expect a freeze roughly every
    ~40–60 min (≈ one cold cycle), so wall-clock progress is throttled though data is never lost.
  - **HEADLESS TRANSITION IN PROGRESS (human chose option 1, 2026-07-25)**: human runs
    `sudo systemctl isolate multi-user.target` (+ optional `set-default multi-user.target`) from a
    TTY/SSH to stop Xorg and remove the nouveau fault path. This is NOT a reboot → the sysfs rig
    state PERSISTS (measure_wrap --verify-only should still pass; NO host_prep needed). The GUI
    Claude Code session may die with Xorg; a cold-start session resumes from here. POST-HEADLESS
    CHECKLIST: (1) `bash scripts/measure_wrap.sh --verify-only` → expect exit 0 (rig persisted);
    (2) `pgrep -af 'run_fleet.py --stage topup'` → if the isolate killed the nohup'd runner (pid
    3724), relaunch `nohup python3 scripts/phasep/run_fleet.py --stage topup --target-ms 65 >>
    logs/governor/topup_steward.log 2>&1 &` (resumable — reconciles CYCLE_ORPHAN, discards any
    power-cut partial); (3) resume normal stewarding. SUCCESS SIGNAL: no more reboots in `last -x`
    → nouveau fix confirmed. Inflight at transition: mid_hist_r3 (building fresh).
  - DEATHS #6/#7 DIAGNOSED = HOST FREEZES (2026-07-24, corrects e5e71bc which logged #6 as an
    undiagnosable "routine runner death"): `uptime`/`last -x reboot` show two hard reboots at 23:12
    and 23:52 local — the box FROZE twice and the human hard-restarted + fixed it. Evidence unified
    everything: silent deaths with NO Python traceback (external SIGKILL, not an exception), and the
    scratchpad topup.log vanishing is just tmpfs /tmp cleared on reboot (→ durable log now at
    logs/governor/topup_steward.log). Debug-mantra chain: repro (2 deaths) → fail-path (durable log
    ends at rig-verify OK, no trace) → hypotheses [OOM / reaper / reboot] → the human's report + uptime
    disproved OOM/reaper and confirmed reboot. RECOVERY: rig RE-VERIFIED clean post-reboot (sysfs
    restored by the human's fix; isolcpus persists via cmdline) — measure_wrap --verify-only exit 0,
    full checklist green. mid_hist_r2 was mid-BUILD at the 23:52 freeze (only _so/_ccache, no
    build_manifest) → partial build DISCARDED for a fresh rebuild (D12 power-cut-corruption rule:
    never reuse a build that overlapped a host fault); CYCLE_ORPHAN charged 0.0s (build barely
    started). mid_hist_r1 had already re-measured clean post-#6 (table config_id 0..N monotonic, 0
    dups) → REJECTED_CLONE, so ZERO data lost. 5 SIGABRT python cores at 23:31 are freeze-collateral
    (host destabilizing pre-23:52), no data impact (the completed r1 measure has a clean table).
    STANCE: these are HOST hardware/stability events for the human, NOT pipeline defects; if freezes
    recur the human owns the box-stability fix. The pipeline's job — resume clean, lose nothing,
    re-verify the rig before measuring, discard fault-overlapped builds — held on both.
P2_kernel_id_is_not_template (CORRECTION — read before using the ledger):
  - TRAP, and three of my own tick reports fell into it: `kernel_id` is the SLOT label carrying the
    ORIGINALLY-ROSTERED template name; `template` is the ACTUALLY-EMITTED template. They diverge
    whenever a slot exhausts its ≤3 re-parameterizations and SWAPS template (run_fleet.py:45
    MAX_ATTEMPTS, :183 "emit under the slot's kid but the template may have swapped — spec records
    it"). 381 of 519 ledger rows have kernel_id-derived name ≠ template. **`template` (and
    `_kernels/<kid>/spec.json`) is authoritative; kernel_id is NOT.**
  - VERIFIED BY ARTIFACT, not inference: `fleet_MID_22_mid_convert_r2` and `fleet_MID_19_mid_hist_r2`
    both have spec.json template=mid_gatherpoly, params {deg:3,n:4096}, and a kernel.pyx signature
    `run(double[::1] a, long[::1] idx, ...)` — an index-array GATHER signature, not a convert/hist one.
  - ANTI-CLONE INTEGRITY INTACT (the reason this mattered): `_accepted_props` (:115-121) and
    `_params_duplicate` (:101-109) both key on `e["template"]`, the authoritative field — so every
    distinctness check compared against the correct template's accepted set. No corruption; NO defect;
    no fix made and none needed.
  - CORRECTIONS to earlier tick reports + commit messages 39/41/42 (they inferred template from
    kernel_id and are WRONG): `mid_hist` is NOT 3-sample {INT,MID,FLAT} — it is n=2 {INT,MID} ·
    `mid_stencil` is NOT 3-sample — it is n=2 {LEVER-SEP,INT} · `mid_convert` did NOT go MIXED — it
    remains n=2 CONSISTENT {LEVER-SEP}. The three kernels behind those claims were all swapped-in
    `mid_gatherpoly`. The STATE groupings themselves were always computed from the `template` field
    and were never wrong; only the prose narration was.
  - TRUE template picture at 42/130 (recompute: group ACCEPTED by (intended_regime, template)):
    FLAT+FM — fm_sum 6 CONSISTENT FLAT · fm_dot 5 CONSISTENT FLAT · fm_sumsq 4 CONSISTENT FLAT ·
    fm_abssum 4 CONSISTENT INT · fm_altsum 3 MIXED · fm_runmean 3 MIXED.
    MID — mid_gatherpoly 6 MIXED · mid_branchy 3 MIXED · mid_hist 2 MIXED · mid_stencil 2 MIXED ·
    mid_convert 2 CONSISTENT LEVER-SEP · mid_gatherpoly_deep 2 CONSISTENT INT.
  - SWAP-DRIVEN SKEW (new, for P-2 §3 diversity evidence): swaps concentrate a block on whichever
    templates still have unused parameter room — mid_gatherpoly is now 6 of 17 MID acceptances (35%).
    The ≥6-distinct-templates-per-regime mandate is still MET (6/6 in MID), but the DISTRIBUTION is
    skewed and the P-2 diversity section should report the per-template histogram, not just the count.
P2_fidelity_audit:
  - A-2 FIDELITY AUDIT (read-only, adversarial, 2026-07-20): verified every clause of the signed A-2
    directive against committed artifacts + the live fleet. 6 lenses (R1 / R2 / R3 / freeze-integrity /
    live-fleet-discipline / absolute-guard+controls). Raw: workflow journal
    `.claude/projects/**/subagents/workflows/wf_9308d7f8-ffc/journal.jsonl`.
  - PARTIAL — STATED AS PARTIAL: 8 of 12 agents completed. The 4 adversarial refuters for R1, R2,
    FREEZE and LIVE-FLEET **died on a session limit** and did NOT run. Only R3 and ABSOLUTE-GUARD
    carry adversarial confirmation (both `survived=true`). The other four verdicts are SINGLE-VOTE,
    unrefuted. 3 agents ran while the safety classifier was unavailable ⇒ their key claim was
    re-verified by hand (below).
  - VERDICTS: R1 PASS (n=60≥26, δ=0.4, one-sided paired Wilcoxon, 15/15 enforced in roster() + TDD) ·
    R3 PASS+survived (measured_v2 from own table; 28 off-diagonal cases prove measured-not-intended) ·
    FREEZE PASS (PREREG A-2a..A-2i committed 3bbaae7; FREEZE_MANIFEST correctly absent) ·
    LIVE-FLEET PASS (N1 rig fingerprint on every sampled row under key `rig`; CF-1 split clean;
    anti-clone distances logged; ledger append-only) · ABSOLUTE-GUARD PASS+survived (no study artifact
    repo-wide; `regret.jsonl`/`motif_exclusions.jsonl` never produced; controls gate ok:true, planted
    Δ_all=10.67≥1.6, flat 1.0391≤1.10) · **R2 CONCERNS — one real gap (below)**.
  - ERRATUM E4 (prose-vs-code, MEASURED IMPACT ZERO — human decision, NOT silently fixed): frozen
    amendment A-2h promises flag fractions "compared in INTEGER arithmetic (FEAS+ ⇔ 4·n_infeasible ≥
    n_total)". The operative fleet classifier `a2_reclassify.py:140` (reached live via
    run_fleet→a2.reclassify) instead uses the FLOAT compare `(n_inf/len(rows)) >= 0.25`.
    EQUIVALENCE PROVEN by exhaustive recompute over EVERY table size n≤1728 and every k:
    **0 disagreements** between `k/n >= 0.25` and `4k >= n`; the A-family knife-edge 432/1728 is
    exactly representable (2⁻²) and both paths fire ⇒ MID+FEAS as the amendment requires. Recompute:
    `python3 -c "print([(n,k) for n in range(1,1729) for k in range(n+1) if (k/n>=0.25)!=(4*k>=n)])"`.
    ⇒ NO kernel is misclassified; NO re-measurement implied; the amendment's INTENT (no float-equality
    fuzz at the knife-edge) is satisfied in effect but not in letter.
    OPTIONS FOR THE HUMAN: (a) ratify as a documentation erratum at P-2 (E3 precedent) — code
    untouched, zero risk to the 30 already-classified kernels [RECOMMENDED]; (b) align the code to
    `4*n_inf >= len(rows)` at the freeze boundary, where all kernels are re-classified anyway, and
    demonstrate zero-diff. Editing the operative classifier MID-fleet is a STOP-THE-FLEET-class act
    and was NOT performed.
P2_supply_cap_finding:
  - DECISION-GRADE P-2 FINDING (measured, honest-negative; surfaced mid-synth ~29/130): generator v2's
    distinct-landscape SUPPLY < signed counts in 4 of 5 regimes. Combinatorial combos per regime
    (template×params×trap) vs demand (30 fleet + 5 holdout = 35): FLAT_FM 28 nominal / **25 MEASURED
    distinct-beyond-ε** (5 slots SLOT_EXHAUSTED — the binding cap); INT **24** (worst); LEVER_SEP 32;
    NULL **7** (of 10 fleet, no H); MID 40 (OK). Recompute: `python3 -c` over generate_v2.REGISTRY +
    fleet_ledger ACCEPTED distinct combos. Raw: results/fleet/fleet_ledger.jsonl.
  - CONSEQUENCE 1 (fleet under-fill = PRE-REGISTERED honest negative, no action): FLAT_FM lands 25<26
    δ=0.4 power floor; INT/NULL will land low too. PREREG §2 / A-2b already govern this: "sub-26
    regimes presented at P-2 with the power consequence." Synth stage CORRECTLY records exhaustions
    and CONTINUES — the data is valid; the smaller-n is reported, not tuned.
  - CONSEQUENCE 2 (HOLDOUT BLOCKER — needs human decision BEFORE the holdout stage runs, days away):
    the pool is exhausted, so H (5 distinct/regime) cannot be generated distinct-from-fleet; also
    run_fleet.process_slot anti-clone (_accepted_props / _params_duplicate) is scoped by TEMPLATE only,
    not run_kind, so H would anti-clone vs the FLEET and exhaust to an empty set. Raising supply =
    widening generator param ranges = a SCOPE change (STOP-THE-FLEET-class, human-only). NOT silently
    fixed. Options for the human: (a) widen generator param ranges for the shortfall regimes
    (pre-registered generator amendment; regenerate affected regimes) · (b) accept smaller/absent H
    with the RQ-P2 power consequence stated · (c) source H from the v1/real anchors only · (d) shrink H.
  - NO code/generator/threshold change made mid-fleet. Synth continues to completion; the holdout +
    freeze stages WAIT on the human's H-sourcing decision. This is a P-2 checkpoint input, surfaced
    early so it is decided before it blocks.
A2_ratification:
  - HUMAN SIGNED A-2 (directive 2026-07-16): Option A; INT fielded; conditional on riders R1-R3.
    Riders FOLDED into memo + PREREG diff BEFORE the freeze commit (conflict check: none; two
    tightenings recorded as deltas — FEAS overlay ≥10 → exact 15/15; FEAS+ in FM+ regimes must use
    directive-crash not fm-cliff, target infeas_frac ≥0.30).
  - R1: FEAS = balanced flag 15/15 per confirmatory regime; confirmatory one-sided paired Wilcoxon
    BO<RS pooled over 60 FEAS+ kernels at B∈{16,32} Holm-2; n=60≥26 ⇒ δ=0.4 powered. FEAS− delta
    descriptive.
  - R2: ALL thresholds closed-lower-bound (≥); integer arithmetic for flag fractions; A-family
    (432/1728=0.25 exactly) = MID+FEAS; anti-clone strict <0.05; ±0.01-of-boundary kernels
    ledger-flagged; templates target away from boundaries (FEAS ≥0.30, FM ≥2.0 by design).
  - R3: INT membership = each fleet kernel's OWN full-table v2 class; NO grandfathering; P-2
    scrutinizes screen-vs-table inflation ≥2× (D5 lesson) before freeze.
  - PREREG §12 A-2 (a-i) APPENDED = TAXONOMY FREEZE. Mid-fleet threshold change = STOP-THE-FLEET.
  - BO-MATH-REVIEWER GATE: **PASS_WITH_NOTES** (2026-07-16, read-only, artifacts
    results/audit/P3.3/hand_checks.py + hand_checks_output.txt, 25/25 auditor checks ALL-OK).
    bo.py math PASS (EI hand-recompute 1.0833154706; floor-before-z; Laplace 1/102..101/102;
    feasible-only spy-verified; exhaustive α; RF pins verbatim). Fixtures PASS — runtime-falsified
    (floor→RED, interleave-delete→RED, positive exclusion). Seeds PASS (independent FNV-1a
    recompute == committed fixtures; two streams independent; alg_id=4 stream distinct). motif
    D6 wiring PASS. Container: 25 passed (11+6+8; the '30' in tasking was a mis-count).
    P3.3 BO study entry UNBLOCKED. Non-blocking notes recorded; ACTIONABLE for the P3 driver:
    (b) the study driver MUST complete motif's warm-start fill to 8 configs (motif_warmstart
    §8.4 fill covers only ref/expert/known-bad; <8-warm-config path untested).
  - GENERATOR v2 BUILT+COMMITTED (b167caf): 6 templates/confirmatory regime + 4 NULL, measured
    provenance per template; FEAS variants (trap_wrap ~0.5, fm_cliff ~0.333, never fm_cliff on FM+
    templates, int_revsum never trapped); roster 15/15 FEAS balance; anti_clone strict <0.05
    (pilot A-clones correctly rejected in TDD); boundary_flags ±0.01; spread_report. TDD 8/8 +
    compile smoke PASS (every template × variant × {cfg288, cfg1506}).
  - FLEET RUNNER run_fleet.py WRITTEN (uncommitted — container py_compile+helper-TDD pending, the
    tool-safety classifier is transiently down): stages controls/synth/holdout/anchors; refuses
    without verify-only PASS; synth refuses without a PASSED fresh controls re-gate in
    results/fleet/controls; acceptance loop (emit→build→measure→classify_v2→anti-clone, ≤3
    re-parameterizations then template swap, SLOT_EXHAUSTED = honest P-2 finding); resume via
    ACCEPTED ledger entries; interrupted-measure delete+redo (B_05/C_04 precedent); kernel dirs
    under the rw /work mount (calibrate rewrites REPS — an :ro kernels mount was caught and fixed
    in self-review). anchors stage stubbed pending task #43 (7 remaining v1 survivor adapters).
  - FLEET RUNNER COMMITTED (58c86fe) + R-ANCHORS COMPLETE 9/9 (0c94f8e stage A, 58d9126 stage B):
    all 9 v1 survivors adapt — 7 single-module (REPS/SCALE knob discipline: linear-in-knob for
    calibrate; PREIMPORT for floyd/cc) + elkan/predictor via the cobuild package-import path
    (v1 delta_probe_pkg recipe: per-combo cythonize cache, gcc -fopenmp into per-config closure
    trees, PKG_MODULE import; OMP_NUM_THREADS=1 in every child). Smoke 9/9 deterministic across
    fresh children. run_fleet --stage anchors implemented (R stays in H; no anti-clone — that is
    a generator discipline). 16 harness tests green in X'.
  - REMAINING CODE (task #44, during compute): P3 replay-runner scale-out (200 seeds × 5 budgets ×
    4 algs × fleet, checkpointed) + Motif extractor completion + the bo-math note (b) obligation
    (study driver completes motif warm-start fill to 8). ABSOLUTE GUARD: no algorithm touches any
    measured table before the P-2 freeze.
  - P3 STUDY MACHINERY COMPLETE (task #44, code-only, 36 tests green in X'):
    (i) motif.py §8.4 conformance fixes — z-score now FIT ON S ONLY (was: sources+target stacked,
    a real spec bug); init dedup includes the REFERENCE; similarity ties by generation index;
    motifbo completes a <8 warm start through the §8.3 default order incl. seed-randoms (closes
    bo-math note (b)). Discriminating TDD: test_motif_84.py.
    (ii) run_study.py — sealed replay study runner with the STRUCTURAL freeze guard: refuses
    without results/fleet/FREEZE_MANIFEST.json and sha256-verifies every table AT LOAD (§11);
    make_freeze_manifest is the immutable P-2 freeze act. Arms RS/DOE/BO/Motif+BO (§3.3 order),
    §3.2 seeds, DOE single-trajectory, LOKO sources exclude target (H/R never in the study set),
    motif hard-fail exclusions ledgered + RQ-P3 20% evaluability computed, checkpointed
    append-only regret.jsonl with (kernel,alg,budget,seed) resume. TDD: test_run_study.py (7).
  - PENDING ERRATUM E3 (present at P-2 for ratification; found pre-study by the FIRST caller of
    the pinned seed path — exactly the bo-math reviewer's declared coverage hole): sklearn
    random_state requires [0,2^32-1]; the §8.3/E2 pin derives a full uint64. Fix at the
    bo._streams boundary: derivation unchanged (seed_fixtures.json stands), RF consumes the value
    mod 2^32. Deterministic; ZERO study data affected (BO has never run in-study). bo-math
    re-ack folds into the P-2 preflight audit.
  - ORCA graphlet extractor (P3.2-full, per its own pre-registered schedule): the structural-count
    baseline is the working §2.4 feature set under the hard-fail contract; the ORCA ≤5-node census
    wiring lands before the study runs (post-freeze), gated by its own TDD.
  - CONTROLS RE-GATE PASS on the prepped rig (2b2b21d, 2026-07-17): planted Δ=10.675 opt-dominant
    -O3-faster ✓ · flat Δ=1.0391→A ✓ · bcprobe bc=0.120 recorded — consistent with the pilot gate
    (10.19/1.045/0.118), no drift. Task #42 gate half complete.
  - SYNTH STAGE LAUNCHED (bg b98lcfra4): 130 kernels (30×4 regimes 15/15 FEAS-balanced + 10
    honest-null), anti-clone live, N1 fingerprints on every row, resumable. ~5.5 days. Heartbeat:
    verify alive, commit completed kernels continuously, watch REJECTED_CLONE/SLOT_EXHAUSTED and
    agreement bits. Then --stage holdout (20) → --stage anchors (9) → make_freeze_manifest →
    report_p2 → auditors → STOP P-2.
  - CAMPAIGN LAUNCHED 2026-07-16 ~12:10Z: human confirmed host prep ("I ran host prep — GO" via
    the launch decision prompt; task #40 closed). verify-only PASS re-confirmed post-prep.
    CONTROLS RE-GATE RUNNING (run_fleet --stage controls, bg blhqgq443, ~3-4h, HARD STOP on fail)
    into results/fleet/controls/. On PASS → --stage synth (130, anti-clone live) → --stage holdout
    (20) → --stage anchors (9) → make_freeze_manifest → report_p2 → auditors → STOP P-2.
    Heartbeat cadence: verify process alive, commit newly-completed kernel artifacts continuously
    (large binaries gitignored), record per-kernel v2 class + boundary flags + agreement bits.
  - (superseded) CAMPAIGN LAUNCH BLOCKED AT THE HUMAN CHECKPOINT (recorded 2026-07-16): the goal hook demands
    the P-2 campaign run; verify-only PASSES (rig quiesced all boot); but the signed directive
    makes host prep a HUMAN step, and the permission layer denied both the agent-side sudo
    (correctly) and the controls-stage launch pending human confirmation. Everything is staged;
    the launch command on confirmation is:
      python3 scripts/phasep/run_fleet.py --stage controls   (HARD STOP if gate fails)
      python3 scripts/phasep/run_fleet.py --stage synth      (130 kernels, after gate PASS)
      python3 scripts/phasep/run_fleet.py --stage holdout && --stage anchors
  - NEXT (bound order): (1) HUMAN HOST PREP — awaiting human: `sudo bash scripts/host_prep.sh` then
    `bash scripts/measure_wrap.sh --verify-only` must PASS (~6.4-7.1 day machine commitment,
    resumable); (2) controls re-verify on prepped rig (HARD STOP if fail); (3) generator v2
    build+TDD (anti-clone live) — CAN PROCEED NOW (code, no measurement); (4) fleet 130 synth
    (30×4 regimes 15/15 FEAS-balanced + 10 honest-null) + 9 R-anchors full tables + H ≥15 post-
    freeze; (5) P3 code + bo-math gate during compute (NO replay on measured tables pre-freeze);
    (6) P2_REPORT.md + auditors → STOP P-2.
phase / subphase.step / timestamp_utc : P1 / A-2 amendment package — protocol committed, probe running / 2026-07-16
A2_execution:
  - P-1 ACCEPTED by human (ruling recorded in A2_DECISION_MEMO.md header). Pilot data DEMOTED to
    taxonomy-development; confirmatory = fleet only. A-1 spent, untouched; §1.6 precedence option
    superseded by structural A-2.
  - TAXONOMY v2 recompute (a2_reclassify.py, container, committed json): families UNIFORM under v2 —
    A→MID×5 (Δs≈1.21, IFs≈0.48) · B→FLAT+FM×5 (fm_ratio≈3.95) · C→FLAT+FEAS×5 (fm-cliff 0.333) ·
    csr→LEVER-SEP (2.016/0.092) · pava→FLAT · planted→INT (Δs=10.18, IFs=0.41 — strict map-
    vectorization; favorable surprise INVESTIGATED: corroborated by A-1 targeted probe + bc=0.343).
    FEAS mechanisms exact+learnable: C=fm-on 576/576 oracle_mismatch; A=wrap∧cdiv 432/432 crash.
  - S-statistic instrument controls (committed data only): positive B01 1.651 ✓, positive planted
    2.796 ✓ (initial mislabel as negative corrected pre-protocol-commit, recorded), negative csr
    0.903 ✓.
  - CLOSURES IMPLEMENTED: N1 per-row rig fingerprint (measure_wrap -e RIG_FINGERPRINT + campaign
    _rig() stamps rows/endpoint/remeasure; UNGATED marker); ledger run_id+run_kind; config_set
    "ids:"; 19 tests green in-container (test_a2_harness + theta + classify).
  - INT PROBE protocol committed (run_probe_int.py + memo Part 3): 4 integer AND-gate candidates
    (P1 sum64 bc×opt, P2 min32 bc×opt, P3 mod64 cdiv×opt, P4 rev64 wrap×opt), 16-config strict
    2^4 + ref, bars Δ16≥1.3 ∧ S≥1.15, kill = 0 pass ⇒ NOT-EXHIBITED-among-probed; fielding
    recommendation ≥2 pass. Budget ≤1 day (expect ~30 min). Probe = the ONLY new measurement.
  - PROBE COMPLETE (run_id 20260715T190058Z, ~5 min wall, all 16/16 feasible, bit-exact oracle):
    P1 sum64 bc×opt Δ16=5.29 S=2.35 PASS · P2 min32 bc×opt Δ16=11.40 S=5.17 PASS · P3 mod64
    cdiv×opt Δ16=1.67 S=1.004 no (cdivision = clean separable ~1.56× main effect → LEVER-SEP
    template, honest INT-negative) · P4 rev64 wrap×opt Δ16=5.22 S=1.80 PASS. Kill criterion NOT
    fired; ≥2 rule satisfied → INT RECOMMENDED as fleet regime (4 mechanism families incl. planted
    map). N1 end-to-end positive control PASS (probe rows+endpoint carry the measure_wrap
    fingerprint; ledger run_kind=probe-int). raw: results/probes/int/probe_verdict.json.
  - A-2 PACKAGE COMPLETE: A2_DECISION_MEMO.md final (probe results folded; fleet plan resolves to
    Option A with INT = 130 synthetic + 9 R ≈ 6.4-7.1 d, inside PREREG §10's 5-9.5 d band).
    STOPPED for A-2 sign-off. NO fleet kernel is generated or measured before the human signs;
    on approval: append Part-6 diff to PREREG §12 → generator v2 (TDD + §9.1 re-gate under v2
    targets) → regenerate H post-freeze → fleet.
  - bo-math-reviewer gate: still PENDING, blocking before P3.3 (post-freeze) — unchanged by A-2.
P1_checkpoint:
  - PILOT COMPLETE 17/17 under measure_wrap (5A+5B+5C+2R, full 1728 tables, both tiers). Committed
    54475fb (14/17) + 5ac6624 (17/17). Report: results/pilot/P1_REPORT.md (report_p1.py, host-run).
  - CONFUSION TABLE is largely OFF-DIAGONAL (the pilot's primary verdict; HONEST NEGATIVE, NOT tuned):
    A-family(intended A)→C×1/boundary×4 (Δ≈1.21, IF≈0.48, greedy_gap straddles the 0.15 C-edge);
    B-family(intended B)→boundary×5 [B∧C] (Δ_all≈3.97 but Δ_strict≈1.006 — interactivity is a
    feasibility-gated FAST-MATH artifact; huge greedy_gap also fires C); C-family(intended C)→A×5
    (Δ≈1.03 flat feasible landscape; the "cliff" is pure feasibility, nfeas=1152); R-anchors(A)→A×2
    (the ONLY on-diagonal cells). Mechanism: synthetic generator does NOT populate classes B/C by
    MEASURED properties; only A populates, only real-code anchors match intent. Bears on the P-2
    fleet-go decision (generator redesign vs re-scope thresholds vs real-code-anchored dataset) — the
    HUMAN decides. A-1 recalibration is SPENT; do NOT kernel-tune.
  - A-1b footprint: moved exactly 6 kernels (C_01-05 + R_02_pava, all Δ<1.10) from ungated boundary→A.
  - CONTROLS GATE PASS (A-1): planted Δ=10.19 opt-dominant -O3-faster; flat Δ=1.045 class A (IF gated);
    bcprobe bc-effect 0.118 (opt-dominated, records bc ceiling). raw: results/pilot/controls_gate.json.
  - ENVELOPE: median 61 min/kernel, ≈5.5-day fleet (~129) — WITHIN PREREG §10 D3 band (55-105 min,
    5-9.5 days); over only the superseded roadmap §4.6 3-4 day figure. No de-scope forced; human decides.
  - AUDITORS BOTH PASS (independent zero-diff recompute, pinned container, src untouched):
    stats-auditor PASS — Δ_all/Δ_strict/IF/greedy_gap all 0.0e0 diff over 17 kernels, 17/17 class labels
    agree, confusion counts + 6-kernel A-1b footprint reproduced (results/audit/P1/recompute_p1.py).
    measurement-auditor PASS_WITH_NOTES — max abs diff 0 (medians/feasibility/endpoint τ_b/top_decile);
    rig+thermal PASS; 35% sampled (results/audit/p1_measurement/recompute.py).
  - N1 PRE-P-2 ACTION ITEM (measurement-auditor): table.jsonl rows carry NO per-row rig_fingerprint
    (only in logs/governor/invocations.log at per-container granularity). CF-1's single gated container
    per measure-phase attests every row so pilot measurements STAND; but §4.4 implies per-row. Add a
    per-row rig fingerprint to the table schema BEFORE the P-2 freeze so the frozen dataset is
    self-describing. Not a defect (nothing to fix in the pilot data); a schema hardening for the fleet.
  - STOP AT P-1: present to human. NO P-2 fleet launch, NO generator change, NO threshold change without
    human approval. bo-math fixtures/seed re-run in-container still PENDING before P3.3 (post-freeze).
phase / subphase.step / timestamp_utc : P1 / P1.2 controls-gate A-1 re-run / 2026-07-09
A1_execution:
  - First controls gate (1728, measure_wrap) FAILED = correct HARD STOP. debug-mantra: PIPELINE
    SOUND (measured real levers), CONTROL SPEC over-pinned bc@2× vs hardware. 4-design ledger
    (results/pilot/CONTROLS_DEBUG.md). Human approved Amendment A-1 (5b0e14a, spec BEFORE re-run):
    A-1a planted→vectorization lever, A-1b IF Δ-floor 1.10, A-1c bcprobe characterization.
  - A-1 code (28bf796): planted = 12-term Horner poly; targeted opt×march probe (isolating -O3 that
    every stride subset had missed) measured -O1/x86-64=68.6ms vs -O3/native=16.9ms = 4.06× with
    opt_level dominant. classify IF_FLOOR=1.10 (14 tests). config_set 'factorial' guarantees -O3.
  - A-1 controls gate re-run LAUNCHED (all 1728, measure_wrap, PID 17004, watcher biomnuvx9): planted
    Δ≥1.6 AND opt largest AND -O3 faster; flat Δ≤1.10 (IF-gated); bcprobe recorded. ~2.5-3h.
  - A-1 is THE single pre-registered P-1 recalibration — now SPENT.
  - A-1 gate re-run result: planted PASSED (Δ=10.19, opt-dominant, -O3 faster); bcprobe recorded bc
    ceiling (bc 0.118, opt dominant, Δ=1.41). flat FAILED Δ=2.96 — debug-mantra: the bandwidth SUM's
    float reduction is vectorized 3× by -O3×native×fast_math (a 3-way interaction; every main-effect
    median ~1.0×). Instrument fix (1110b94, NOT a criterion/threshold change — ≤1.10 unchanged): flat
    → pointer chase j=nxt[j] (latency-bound, no FP, no vectorizable compute). Re-measuring ONLY flat
    (PID 6463, watcher b2r04vi1p); planted/bcprobe cached. On PASS → launch 17-kernel pilot.
  - CONTROLS GATE PASSED (A-1 + flat pointer-chase): planted Δ=10.19 opt-dominant -O3-faster ✓;
    flat Δ=1.045 class A (IF=0.966 correctly GATED OUT by A-1b Δ-floor — A-1b validated) ✓; bcprobe
    bc-ceiling recorded (bc 0.118, opt top, Δ=1.41). raw: results/pilot/controls_gate.json.
    flat wall-clock build=27min measure=56min (~83min/kernel — feeds P-1 envelope).
  - 17-KERNEL PILOT LAUNCHED (5A+5B+5C+2R, measure_wrap, resumable). P3 code built during compute.
    STOP at P-1 with report_p1.py output + auditors.
  - bo-math-reviewer (ffdbc10): BO production math PASS; 3 vacuous fixtures + §8.3 two-stream seed
    FIXED (must-re-run-green in-container before P3.3; deferred for CF-1 during pilot).
  - REBOOT RESUME (user restarted machine): quiesce SURVIVED (measure_wrap PASS). Pilot resumed
    (PID 8614, watcher b7aku0oa1) — 9/17 committed (A_01-05, B_01-04); B_05 was interrupted
    mid-endpoint so DELETED+redone (calibrate-knob consistency); then C_01-05 + R_01_csr/R_02_pava.
  - EARLY PILOT FINDING (honest negative, for P-1 confusion table): B_02/B_03/B_04 measured class
    = **boundary**, NOT B — the B-family (bc×opt vectorization-inhibition) is not cleanly landing in
    class B (B needs IF≥0.25 AND Δ_all≥1.5). Report at P-1; do NOT kernel-tune (A-1 recalibration spent).
  - RESUME #2 (user restarted machine a SECOND time): quiesce RE-VERIFIED PASS (measure_wrap
    --verify-only exit0: no_turbo=1, gov_cpu3=perf, cpu7 online-but-isolcpus=3,7, thp=madvise,
    freq 3.6GHz; isolcpus/nohz baked in GRUB cmdline). 13/17 committed (5A+5B+3C). C_04 was
    interrupted early-in-screen (108/1728 rows, no endpoint/class_record) → DELETED measure products
    (table/oracle/golden), KEPT cached build (_so/_ccache/build_manifest, REPS-independent), driver
    reset to REPS=120 baseline. Pilot relaunched (PID 6389, bg bzkwbu1c6) — C_04 re-measuring FRESH
    (single calibrate knob, table.jsonl regrowing from 0). Then C_05 + R_01_csr/R_02_pava. STOP at P-1.
  - NEXT on pilot completion: commit remaining tables → run_pilot report_p1.py → measurement-auditor
    (≥20% tables zero-diff) + stats-auditor (confusion + A-1b IF-gating recompute) → P1_REPORT.md → STOP P-1.
phase / subphase.step / timestamp_utc : P1 / P1.0→P1.1 (P0 CLOSED) / 2026-07-08
what_was_done:
  - P0 COMPLETE. P0.1/P0.2 (7604942): goal-change amendment; RQ1 negative stands (tag v1-final);
    Appendix A verbatim; |Θ|=1728 + canonical config_id. P0.3 (c7377e9): PREREG_PHASEP.md, pre-commit
    4-lens reviewed (wf_14518dee-4f5), all BLOCKER/MAJOR folded — keystone composite fmffp factor
    (full-rank 13-param; repairs OLS + D-optimal designs + 1-flip neighborhood). P0-EXIT: the 3 §6.5
    auditors ACKNOWLEDGED the register (wf_ec722d7d-1b0) — all ACK_WITH_NOTES, sha256 match, ZERO
    blocking. Two prose errata folded (E1 fnv1a64 digits, E2 BO random_state uint64 pin) + generate.py
    mechanism-coverage docstring corrected (fleet-level, not per-kernel).
  - P1.0 built+tested in X': theta.py (13 tests: config_id==Appendix-A, rank 13, |N|=12), seeds.py
    +fixtures, build_doe_designs.py + doe_designs_theta.json (ranks 7/13/13/13), classify.py (A/B/C/
    boundary, 7 fixtures incl. cliff-island singular-OK). Campaign harness: build.py (cythonize-cache
    + gcc), measure_child.py (adaptive-K 2%-CI, RUSAGE_SELF, per-rep regen), oracle.py (bit-exact/
    toleranced), campaign.py (screen + suspicious §7 + endpoint §4 + classify, resumable JSONL).
  - P1.1 generator: 3 real-mechanism families (A separable / B bc×opt vectorization / C fast-math
    cliff) + 2 controls. Pipeline smoke 5/5 (generate→cythonize→gcc→run, deterministic hashes).
    C-family feasibility-cliff was too weak at rtol=1e-9 (Kahan-vs-naive ~1e-13) → REDESIGNED with
    dynamic-range data (±1e16 spike); dry-run re-validating the cliff fires.
raw_result_paths:
  - results/prereg/PREREG_PHASEP.md  (sha256 291024bf41e29ceda1e026a41a3db2bcdf6c547d8083fd049f5bc0bb1da286a8 after E1/E2 errata)
  - results/prereg/{seed_fixtures.json, doe_designs_theta.json}
  - scripts/phasep/*.py  (theta, seeds, classify, build, measure_child, oracle, generate, campaign, tests)
preregistrations:
  - results/prereg/PREREG_PHASEP.md  (the Phase-P register)
audit_status:
  {validation-auditor: ACK_WITH_NOTES (P0 register), bo-math-reviewer: n/a (BO not built until P3.2),
   stats-auditor: ACK_WITH_NOTES (P0 register), measurement-auditor: ACK_WITH_NOTES (P0 register)}
  # All 3 verdicts: sha256-verified, 0 blocking, notes folded (E1/E2 + generate docstring).
  # bo-math-reviewer gates BO entry at P3.2. Auditors re-run for zero-diff at P-2/P-3.
defects: []
next_action:
  - CONTROLS GATE RUNNING (all 1728, measure_wrap, launched PID 21617, watcher b0y0tk3uj). On PASS →
    launch the 17-kernel pilot (run_pilot --classes A:5 B:5 C:5 --anchors 2 --rig measure_wrap). On
    FAIL → HARD STOP + debug-mantra (strengthen the control instrument, pre-pilot). Then: bo-math-reviewer
    on bo.py; run report_p1.py; measurement+stats auditors on pilot tables; present P-1, STOP.
progress_2026-07-08 (P1.2/P1.3 execution + pipelined P3):
  - Host quiesce CONFIRMED: measure_wrap --verify-only PASS (no_turbo=1, gov perf, cpu3+7 isolated,
    THP madvise). config_id bijection re-confirmed EXHAUSTIVE over all 1728 (both directions).
  - R-anchor adapter (r_anchor.py) VALIDATED E2E in X': csr (closure build, SCALE calib, det golden,
    400-elem child-side tolerance) + pava (IN-PLACE, per-rep regen D6, SCALE calib, 3.9M-elem golden).
    Goldens+tolerances RE-DERIVED at pilot scale (never v1 500ms). Determinism gate = bit-identical 5 reps.
  - Two-phase container split (CF-1/§4.4): build_phase.py (plain, parallel gcc) + measure_phase.py
    (measure_wrap, isolated core, no compile). Oracle moved INTO the child (arbitrary-size float arrays,
    §5 tolerance not bit-hash). build_all PARALLELIZED (32-combo cache-warm + thread-pool gcc).
  - P3 code (NO study pre-freeze): replay.py sealed harness + cheat-test; algorithms.py RS+DOE;
    bo.py SMAC-RF+EIC (TDD 11/11, EI hand-fixture 1.0833154); motif.py extractor skeleton (hard-fail
    contract) + LOKO warm-start. 25 P3 tests green. bo-math-reviewer gate PENDING.
  - report_p1.py: decision-grade P-1 report generator (confusion / agreement-distribution / envelope-
    with-phase-breakdown / ledger / controls / amendment / auditors).
audit_status_P3:
  {bo-math-reviewer: PENDING (gate before BO enters the P3 study, not before code+TDD)}
blocking:
  - Controls gate must PASS before the 17-kernel pilot launches (HARD STOP if fail). Pilot ≈20-30h
    (parallel build ≈20min + measure ≈50min per kernel × 17) → multi-session, resumable, committed live.
```

## Phase map (roadmap §7) — checkpoints are STOP-for-human

- **P0** governance + specs — IN PROGRESS (P0.1/P0.2 done; P0.3 authored; P0-exit auditor ack pending).
- **P1** generator + pilot → **CHECKPOINT P-1** (pilot report + any single pre-registered
  threshold/scale amendment; human approves fleet go).
- **P2** fleet campaign + freeze → **CHECKPOINT P-2** (frozen dataset + class counts + confusion
  table; measurement-auditor ≥20% zero-diff).
- **P3** algorithms + sealed replay study → **CHECKPOINT P-3** (routing matrix + Motif verdict;
  stats-auditor zero-diff on the full matrix).
- **P4** `cytune` CLI → **CHECKPOINT P-4** (acceptance on H+R; RQ-P2 verdict; release decision).
- **P5** final report (PHASEP_REPORT.md + HTML from committed JSON only).

## Ledgers

- **Survival ledger** (per-kernel per-gate) — created at P1.1 (`results/dataset/survival_ledger.jsonl`).
- **Intended-vs-measured class ledger** — created at P2.2 (`results/dataset/class_ledger.jsonl`).
- **Deviations from roadmap** (pre-registered, PREREG §12): D1 golden band upper→100 ms; D2 DOE
  N_d=min(24,B−1) < 16 at B∈{8,16}; D3 envelope ≈55–105 min/kernel, ≈5–9.5 days fleet.

## Inherited (do not re-derive; roadmap §0.4)

Real-code flatness/separability + two-lever mechanism (RQ1 negative, tag v1-final); power table
(n=12/26/103 at δ=0.6/0.4/0.2); noise floor (CI@30 ≤1% at ~500 ms; ~3.6% slow-outlier at ~74 ms);
D1–D6 (D1/D2/D5/D6 were silent); v1.2/v1.3/v1.4 protocol revisions in force; β directive policy;
v1 golden reference config.
