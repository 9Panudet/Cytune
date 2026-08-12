# STATE_PHASE0 (schema: roadmap §6.4)

```
phase:           0 (Instrument Validation & Tooling) — CLOSED
subphase.step:   0.P CLOSED (E executed) — all 5 exit criteria met; I-3 human signature RECORDED; Phase 0 COMPLETE → Phase 1 open (STATE_PHASE1.md)
timestamp_utc:   2026-06-16T12:10:53Z

i3_signature_recorded (E):
  - The I-3 manual validation gate is SIGNED by the human (Panudet / operator beimfedora /
    panudetsuttiwong48@gmail.com), in-session, in their OWN WORDS typed directly in the
    conversation (NOT inferred from any file). Verbatim: "I have personally inspected the code
    in feasibility.py and test_oracle_feasibility.py. Everything is sound. I, Panudet, explicitly
    sign the I-3 manual validation gate and authorize the Phase-0 close. I acknowledge the
    corrected stats-auditor findings. Record this exact statement as my signature and proceed
    with executing E immediately." Recorded verbatim in results/preflight/I3_validation_gate_pack.md
    (signature block). NOT self-signed. Scope (§5/P3): attests to the comparator + feasibility RIG
    + calibration-kernel oracles (incl. the P1d module the human personally inspected), NOT corpus
    tolerances (Step 1.1.3).
  - GOVERNANCE NOTE: an earlier E attempt to record the closing line of
    prompts/PHASE0_CLOSE_E_ACTION_PROMPT.md ("HUMAN SIGNATURE: APPROVED...") as the signature was
    correctly BLOCKED (a file line is not a personal in-session signature); the agent stopped and
    obtained the genuine in-conversation signature above instead. No signature was ever inferred.
  - E auditor sweep on the FINAL raw (post-correction HEAD): measurement-auditor PASS
    (a9f2dd3bf1486a790), validation-auditor PASS (a6df68143afb4d7c8), stats-auditor
    PASS on RE-VERIFY (abdf868ee850767bd, stamp 6f96696315053cb7) after the 3 corrections,
    bo-math n/a, scrutinize SHIP. See audit_status.
  - E CORRECTIONS (commit 4d3a517; no gate verdict changed): the first E stats-auditor
    pass (add7d067dbc3a87e3) FAILED on 3 reported-number discrepancies, all fixed to raw:
    (1) Horner CI@30 "worst-of-12 = 0.8707% / all 12 identical" was a MISLABEL — true
    worst = seed 11 0.8778% (0.8707% = canonical seed 0xC0FFEE, 11/12 seeds); confirmed
    independently by BOTH measurement- and stats-auditor; criterion 4 evaluated on the
    true worst 0.8778% <= 1% (conservative, no seed selected); (2) §7 distinct-covered=30
    rested on an UNPINNED prose predicate → reframed to predicate-independent zero-diff
    facts (totals 37/38, column-sums 41/47, the overlap itself); (3) additive memory
    3.05 → exact 3.054 GiB. Also fixed the B-doc eff_ghz "contention proof" row (COR1).

step_0.P_finalclose:
  - A (location): single canonical roadmap at repo ROOT (git ls-files one path; no prompts/
    remnant; CLAUDE.md bare-name ref resolves to root). HEAD L482 = Horner; 2b69ab2 contains
    the PAVA->Horner edit. I-1 grounding valid.
  - B (Horner criterion 4): criterion 4 binds BOTH I-1 reference kernels; quiesce-all fixes
    memory-bound csr but NOT compute-bound Horner. Horner @4M missed (CI@30 4.005% > 1%, short-
    runtime jitter). Remedy = lengthen input n 4M->64M (PREREG_I1_horner_lengthen.md committed
    dd14054 BEFORE measuring). Pre-verify run (de19ca9): CI@30 0.964%, ratio 10.441x.
    CLOSE-OUT RE-VERIFICATION (3 human points) — re-measured via run_i1.sh (build off-core then
    measure core 3, NO concurrent compile): horner_good median 78.199ms (IN 50-500ms band), CI@30
    worst-of-12 0.8778% (seed 11; canonical-seed 0xC0FFEE 0.8707%) <= 1% MET [CORRECTED at E:
    the prior "0.8707% worst-of-12 / all 12 identical" was a mislabel — true worst is seed 11
    0.8778%, confirmed by BOTH measurement- and stats-auditor; gate unaffected, 0.8778% <= 1%],
    I-1 ratio 9.425x >= 1.5x PASS, oracle 3.109e-15 PASS, thermal throttle 0/50C.
    [Framed per COR1/COR2 below.] B.3: criterion 4 MET for BOTH kernels (csr pilot 0.315% +
    Horner worst-of-12 0.8778%, with the pre-verify 0.964% the second independent run). The re-measured raw
    supersedes the C.4-audited raw; the E close-out auditor sweep re-verifies the FINAL raw
    (1b9e6a7). 4M Horner raw superseded (history a002f38).

  closeout_corrections (honesty; no pass/fail change):
  - COR1: the re-measure is free of VARIABLE COMPILE CONTENTION by the STRUCTURAL PROTOCOL
    GUARANTEE (cores 0-1 paused during the measured window), NOT "contention-free proven by
    eff_ghz". eff_ghz flatness (0.016%) only confirms FREQUENCY was held; a DRAM-stalled core
    runs at flat frequency while stalling, so eff_ghz does NOT establish memory-stall-freeness.
    The +11% median / -10% ratio (10.441x->9.425x) = a steady additive ~8ms offset on good AND
    bad (additive offset compresses a >1 ratio toward 1 -> CONSERVATIVE for the I-1 ratio, does
    not inflate CI).
  - COR2 [further corrected at E]: the per-seed CI@30 over 12 seeds is NEAR-invariant, NOT exactly
    identical — 11 of 12 = 0.8707%, seed 11 = 0.8778% (the TRUE worst-of-12). This NEAR-invariance
    shows the n=30 discrete order-statistic effect, NOT measurement/input robustness. Criterion 4 is
    evaluated on the true worst 0.8778% <= 1% (conservative; NO seed selected to favour the gate).
    Real robustness = the TWO INDEPENDENT runs (0.964% pre-verify + 0.8778%-worst re-measure), both
    <= 1% (n=2, thin but passing). The earlier "12 identical / 0.8707% worst" wording was wrong.
  - COR3: memory keeps BOTH bounds — observed Horner-64M peak (additive 3.054 GiB) AND the
    cap-based worst-case guarantee (orchestrator + 4 GiB candidate cap + 2 GiB tmpfs = 6.05 GiB,
    the real guarantee since no candidate exceeds 4 GiB without a kill). Both < 12 GiB. Both
    retained in results/preflight/{memory_profile.json, MEMORY_PROFILE.md}.

  i3_pack_augmentation (D.2 — human withheld signature: pack showed ACCEPT + crash-DETECT but
  not REJECT-clean-but-wrong; results/preflight/I3_validation_gate_pack.md augmented):
  - SURFACED from existing tests (not new): P1a value mismatch (test_oracle_bitwise
    test_value_outcomes_delegate_to_bitwise / test_single_element_difference); P1b numeric
    outside tolerance (test_oracle_tolerance test_within_and_outside_atol / test_worst_element);
    P1c wrong/missing exception (test_cdivision_style_missing_exception_is_caught /
    test_subclass_does_not_satisfy_exception_identity); P2 negative-operand cdivision divergence
    (test_oracle_edge_suite test_negative_operand_divergence_is_caught + non-false-positive
    control). P4 §3.3 edge-case table recomputed from validation_inputs.CASES.
  - NEWLY ADDED via TDD (§6.3 red->green): P1d fast-math-on-correctness-critical -> feasible=0.
    RED = ModuleNotFoundError (test written first); GREEN = src/motifbo/oracle/feasibility.py
    oracle_feasible() (§3.5 ORACLE dimension only; full composition still 1.4.3). Test
    src/tests/test_oracle_feasibility.py (6 tests): fast-math reassociation (a+b)+c=1.0 vs
    a+(b+c)=0.0 -> bitwise mismatch -> feasible=0; manifest forbids tolerance on correctness-
    critical (non-escapable); within-tol contrast feasible=1; non-vacuity (stub fails;
    oracle_feasible(True) raises). Full suite 316 -> 322 passed.
  - P3 SCOPE clarification: §3.1 tolerance DERIVATION (max(10x cross-rep dev, floor)) does NOT
    exist in src -> it is Step 1.1.3. The I-3 signature attests to the comparator + feasibility
    RIG + calibration-kernel oracles, NOT corpus tolerances (which do not exist yet).
  - Re-presented for human in-session signature; NOT self-signed; E (close) still gated on it.
  - MEMORY PROFILE UPDATED (preflight item 2, human point 3): Horner-64M run is the new worst
    candidate, peak 1005.4 MiB (cgroup memory.peak) -> supersedes the 221.5 MiB csr build.
    Ceiling re-checked: additive 1.005 + 0.049 (orch) + 2.0 (tmpfs) = 3.054 GiB < 12 GiB PASS;
    BO-candidate hard-cap bound 6.05 GiB; Horner-64M (1.0 GiB) also fits the §3.4 4g cap.
    results/preflight/{memory_profile.json, MEMORY_PROFILE.md}.
  - C (protocol lock): quiesce-all ADOPTED (compile workers cores 0-1 quiesced during EVERY
    measured run, all units — removes the boundedness-MISCLASSIFICATION leak onto RQ1). C.2 cost:
    ZERO in Phase 0 (measurements were already serial build-then-measure); Phase-1 projection =
    per-candidate lost compile/measure overlap (~build wall-clock); default stays quiesce-all
    (correctness > throughput), reversible to memory-bound-only (protocol (i)) if §1.5 threatened
    -> re-evaluate at Step 1.2 with real per-unit build/measure times. C.3: §5.1 v1.2 APPLIED to
    the canonical root roadmap (Revision log + §5.1 L334 clause; document revision, NOT a B-12
    amendment, predates RQ1 data). C.4: measurement-auditor RE-SIGNED PASS (ab68a70ca367ad107).
  - D.1 (P0e): ACKED — location=root + Horner edit 2b69ab2 confirmed canonical (A); instrument-
    definition fix, no B-12 amendment, not D-series, scrutinize-signed, I-1 grounding valid.
    P0e CLEARED from blocking (human-acked via PHASE0_FINAL_CLOSE_ACTION_PROMPT D.1).

step_0.P_closeout:
  - G0 LAW-FORK RECONCILED (PHASE0_CLOSEOUT_ACTION_PROMPT). Diagnosis: the Horner
    §0.5.1b edit was safely committed (2b69ab2; HEAD L482 = Horner). The human had
    moved the roadmap to prompts/ INTENTIONALLY, but that prompts/ copy was a STALE
    Jun-11 PRE-Horner duplicate (PAVA at L482). My session-start restore did NOT clobber
    (the Horner edit was committed; restore recreated it at root). Human chose CANONICAL
    = ROOT. Deleted the stale untracked prompts/Motif+BO-Roadmap.md; root copy is the
    single canonical law (tracked, Horner). Zero reference edits needed (§1.4 pre-commit
    allowlist + CLAUDE.md already name root; nested prompts/ would have been hook-legal
    but root is the design home). I-1 grounding VALID (canonical law = Horner, I-1 ran
    on Horner). pava retained as §4.3 corpus-Delta finding, not the I-1 reference.
  - G1 SANITIZER INPUT-SET HOLE CLOSED (commit 80b4d56). §3.3 names Hypothesis property
    cases in the validation input set; hypothesis==6.155.2 was pinned at 0.4.2b AFTER the
    0.4.2 numpy-corpus run, so the byte-identical-toolchain carry-forward (same inputs
    only) did not cover them. Ran a fixed-seed Hypothesis corpus (derandomize, committed
    corpus_{csr,pava}.json) through the SAME known-good ASan+UBSan build + fresh-subprocess
    child: CLEAN, 0 reports / 80 cases. Non-vacuity guard test added (the first run's 11
    odd-passes ValueErrors were malformed inputs, not reports — strategy constrained to
    even passes per csr_scale.pyx L20). Full suite 316 passed. Evidence:
    results/raw/hypothesis_sanitize/. Preflight item 3 now covers the full §3.3 input set.
  - G2 DRAM-CONTENTION PROTOCOL RESOLVED (results/preflight/G2_measurement_protocol.md).
    Root cause: §5.1 L334 isolates the measurement CORE but cores 0-1 compile workers
    share the DRAM controller; csr_scale (memory-bound, ~768MB/run) contends -> I-1 IQR
    4.09% (bootstrap CI@30 1.50%) vs pilot contention-free 0.315%, frequency-invariant
    (eff_ghz spread 0.02%) = memory not compute. DECISION = protocol (i): measured runs of
    memory-bound units run with cores 0-1 quiesced (measurement core owns DRAM bandwidth;
    builds before/after, never concurrent). CRITERION-4 reconciled: MET under protocol (i)
    by the contention-free pilot (csr 0.315%, pava 0.345% CI@30); I-1 4.09% is a
    contention-present single-shot RATIO measurement (gate-robust; contention COMPRESSES
    the ratio toward 1.0 so 1.964x is a floor), not a precision characterization.
    measurement-auditor RE-SIGNED PASS under protocol (i) (replaces the 0.P PASS-with-
    concerns). Proposed §5.1 v1.2 document-revision text HELD for human ack (no unilateral
    law edit). Binds Step-1.2 drivers (memory-bound corpus units measured contention-free).

step_0.P_preflight:
  - Carried-forward catch P0a-P0e RESOLVED + recorded (results/preflight/
    PHASE0_PREFLIGHT.md, committed 04da4ff):
    P0a: Step-0.2.4 pilot ran csr_scale (119.086 ms, IQR 1.00%) + pava (73.537 ms,
      IQR 1.05%); K_final=30 + thermal 62C derived from THESE (both met <=1% CI@30:
      0.315% / 0.345%). Numeric I-1 ref swapped PAVA->Horner AFTER the pilot — stated
      plainly. csr_scale stays the raw-pointer I-1 ref AND a pilot kernel; pava stays a
      real §4.3 corpus unit. K_final basis unaffected by the swap.
    P0b: both pilot kernels IN the §4.2 50-500 ms band -> K_final=30 generalizes to the
      corpus band. Horner (5.278 ms) is sub-band but did NOT set K_final.
    P0c: Horner good IQR 13.39% @ 5.278 ms = unrepresentatively-fast artifact (not rig
      instability; Horner-bad 45.9 ms has IQR 0.11%; eff_ghz spread 0.17%). DECISION (i):
      Horner is CALIBRATION-ONLY, EXEMPT from the corpus-precision bound; the Phase-0-exit
      per-kernel-IQR-within-bound criterion is evaluated on csr_scale + pava (CI@30
      0.315% / 0.345%, within bound), NOT Horner. Exemption named + scoped, not hand-waved.
    P0d: I-1 validated the rig vs a LARGE 8.691x speedup; it did NOT validate precision in
      the 1.2-1.6x discrimination band where the corpus lives (PAVA 1.231x; §4.1c floor
      1.2x / median 1.5x). That confidence rests on the pilot variance study (CI@30
      <=0.35%) + the Phase-1 per-unit IQR re-characterization (Step 1.2). Carried forward.
    P0e: the §0.5.1b PAVA->Horner edit changed the "law" document. Correctly classed
      (instrument-definition fix; no amendment; not D-series) + scrutinize-signed, but
      self-sign on a law-level edit is the one governance gap -> BLOCKING on human ack.
  - Preflight items (§6.6): 1 digest/hash PASS (check_toolchain 21 assertions 0-diff;
    check_python_env lock-hashes + pkg-set incl hypothesis + py3.12.3 + smac/sklearn
    backend; Containerfile FROM pinned by manifest digest 023f8a75, present locally;
    local ubuntu:24.04 TAG drift to 26059926 is cosmetic — pin is by-digest). 2 memory
    PASS (results/preflight/MEMORY_PROFILE.md: worst candidate 221.5 MiB build,
    orchestrator 48.9 MiB, enforced-hard-cap additive 4+2+0.05 = 6.05 GiB < 12 GiB).
    3 sanitizer-clean PASS (validation-auditor proved carry-forward at BINARY level:
    cc1 / libasan.so / python3.12 byte-identical sha256 across the f9328a8a92f8 ->
    3bbe69a1d8f8 hypothesis re-pin; 0 reports / 75 cases). 4 raw-data presence PASS
    (stats 38/38 zero-diff). 5 scrutinize + 4 auditors: see audit_status.
  - WORKTREE FIX: Motif+BO-Roadmap.md (the "law") was DELETED in the working tree at
    session start (HEAD copy intact, §0.5.1b Horner correction present at L482). Restored
    from HEAD (git checkout). Surface to human — see blocking.

what_was_done:
  - GATE I-1 PASS (results/calibration/i1/I1_GATE.md): csr_scale (raw-pointer)
    1.964x >= 1.15x PASS; horner (numeric-loop) 8.691x >= 1.5x PASS.
  - RESOLUTION of the pava red gate = ROADMAP CORRECTION (human-directed,
    RESUME_0.5.3_ACTION_PROMPT.md): the §0.5.1b PAVA pin and the §0.3 1.5x numeric
    margin were mutually incompatible (PAVA pooling is sequential/division-bound,
    structurally out-of-class). Replaced the numeric-loop reference PAVA -> Horner
    (elementwise degree-11 polynomial, src/motifbo/refkernels/horner.pyx). This is
    a Phase-0 instrument-definition correction: does NOT consume the single
    amendment (Appendix B-12); NOT a D-series defect (those are silent code bugs);
    NOT a post-mortem (no code fix). Threshold 1.5x UNCHANGED (not lowered).
  - PRE-COMMITTED before measuring (4fbade1): results/characterization/
    I1_numeric_kernel_choice.md — a-priori expected speedup >=2x derived from the
    MECHANISM (AVX2 vectorisation + FMA + boundscheck removal; verified by objdump
    good ymm=504/vfmadd=44 vs bad 0/0), NOT from csr's number. R3 oracle-robust:
    good/bad differ by FMA rounding only (max 3.3e-15 within atol=rtol=1e-9,
    horner_oracle.json validates); no -ffast-math used.
  - R4 measured horner good/bad K_final=30 paired (a002f38), thermal clean (0
    throttle, 46C), pairing fddcb155. Measured 8.691x vs a-priori >=2x — PASS with
    large margin. scrutinize sign-off: principled (pre-committed, canonical
    compute-bound numeric loop, far above threshold = not gate-gaming).
  - R6 pava finding PRESERVED (results/characterization/pava_low_delta_finding.md):
    Delta=1.231x (directive 1.19x / gcc 1.05x), impl-invariant; pava =
    sklearn.isotonic/_isotonic.pyx is a real §4.3 corpus unit, barely clears the
    §4.1c 1.2x floor, contributes 0 to corpus-median-Delta>=1.5. RQ1-difficulty
    risk (sequential/division-bound class: _cd_fast, Bellman-Ford _shortest_path)
    to confront at Step 1.3, NOT 1.5.6 by surprise. pava raw stays committed.
  - debug-mantra (the red-gate investigation) preserved at
    logs/env/STEP_0.5.3_i1_gate_RED.log. Full suite 234 passed.
  - OBSERVATION (scrutinize nit): horner good IQR ~13% (it runs in only ~5.3ms, so
    jitter is a larger relative fraction); the §5.1 <=1% target governs K_final
    determination, not the I-1 gate (ratio >= threshold). Worst-case good 6.22ms
    still gives 7.38x >> 1.5x — verdict robust.

prior_step_0.5.2:
  - I-1 known-good vs known-bad measured at K_final=30 on PAIRED inputs, isolated
    core (roadmap §0.5.2, §5.1; PREREG_I1.md committed FIRST at 204ff84 before any
    run). Configs per prereg: good = boundscheck/wraparound/initializedcheck/
    nonecheck off, cdivision on, -O3 -march=native -ffp-contract=fast; bad = all
    checks on, cdivision off, -O1 -march=x86-64 -ffp-contract=off. Inputs = the
    frozen pilot setups (seed 20260611; csr 4M/100k/passes=24, pava 4M), imported
    from pilot_measure.SETUPS — identical to the pilot AND across configs.
  - 4 raw measurements (csr/pava × good/bad), 30 samples + 30/30 cycles each,
    written via measure_wrap on core 3. PAIRING PROVEN: csr good/bad share
    setup_sha256 32d12490, pava good/bad share 3d2b1484. Thermal CLEAN: 0 throttle
    events, max pkg 48C / core3 41C (< 62C discard threshold) — no discard.
  - NO aggregate computed (§6.1): the speedup ratio + gate decision is Step 0.5.3,
    recomputed independently by stats-auditor at preflight. Raw committed first.
  - Ultracode note: this is a serial single-core measurement (§5.1 "one benchmark
    at a time on the measurement core") — a parallel workflow would contend for
    core 3 and corrupt the timing, so it was done inline by design, not via Workflow.
  - Files: scripts/{build_i1.py, i1_measure.py, run_i1.sh}; raw under
    results/calibration/i1/raw/.

prior_step_0.5.1:
  - Reference-kernel hot-loop drivers + D2 input-scaling check (roadmap §4.4, §0.2).
    src/motifbo/timing/drivers.py: size-parameterised setups for csr_scale/pava
    consumed by the RUNTIME_NS harness (fresh subprocess, kernel-only timing,
    import/setup excluded). Declared Tier-3 bands: both O(n), [1.7, 2.3] — lower
    bound > 1.0 IS the D2 guard. TDD (tests/test_d2_scaling.py, 9): scaling_ratio/
    in_band non-vacuous (ratio 1.0 AND 4.0 rejected); every band excludes 1.0;
    generated setups build in-contract inputs at both sizes.
  - Integration D2 run on the isolated core (measure_wrap; known-good -O3
    -march=native -ffp-contract=fast): csr ratio 2.050, pava 1.998 — both IN BAND.
    Kernel fraction (§4.4 item 1) 99.99% both (overhead ~1us vs 10-32ms work);
    setup ~100ms RECORDED but EXCLUDED from the timed signal (the D2 guard).
    Result: results/calibration/d2/{REPORT.md, d2_scaling.json}.
  - Honest profiling finding: cProfile is INAPPLICABLE to these C kernels (lsprof
    records ~0 even with cython profile=True — no Python subcalls); replaced with a
    model-free overhead decomposition (kernel_fraction = 1 - overhead/work).
    Documented in STEP_0.5.1 log. Full suite 227 passed.

prior_step_0.4.3:
  - Containment wrapper src/motifbo/containment/wrapper.py (roadmap §3.4 + §3.5).
    HOST-SIDE run_contained() launches each candidate as its own podman container
    with the §3.4 limits — --network=none, --memory=4g (swap disabled), fresh 2 GB
    tmpfs /sandbox (new container per candidate => wiped automatically), wall-clock
    timeout (120 s compile / max(10x golden,5 s) run) — classifies the outcome per
    §3.5 and NEVER raises on candidate misbehaviour (harness failures surface as
    label 'harness_error'). OOM via State.OOMKilled with a SIGKILL-137 fallback.
    classify(): ok | timeout | memory_cap_kill | crash (SEGV/ABRT/BUS/FPE/ILL) |
    nonzero_exit. Carried F9 honoured: wrapper reports PROCESS labels only, asserts
    no feasibility (so leak-audit exit codes can't leak into feasibility).
  - NON-VACUITY two layers:
    (1) Pure classifier unit-tested in-container (tests/test_containment_labels.py,
        7): full crash-signal range -> crash; SIGKILL/OOM -> memory_cap_kill;
        plain nonzero NOT misread as crash; timeout dominates; §3.4 constants
        (120s, 4096MB, 2048MB) and run-timeout rule pinned.
    (2) HOST smoke (scripts/containment_smoke.py) drives REAL podman fixtures:
        clean->ok, sys.exit(3)->nonzero_exit, sleep>timeout->timeout (we kill),
        6GB alloc->memory_cap_kill (OOMKilled=true, rc137), null-deref->crash
        (rc139). All 5 caught & correctly labeled; orchestrator survived all;
        0 stray containers (rm -f cleanup). Result:
        results/containment/{REPORT.md, containment_smoke.json}.
  - Fixture honesty: the abort host-fixture was removed — in this CPython abort()
    manifests as rc139 (== SEGV, indistinguishable) and os.kill(SIGABRT) is
    deferred to rc0; the full crash-signal range is covered by the pure unit test,
    so a real SIGSEGV is the single end-to-end crash demo. Documented in the log.
  - Files: src/motifbo/containment/{__init__,wrapper}.py,
    src/tests/test_containment_labels.py, scripts/containment_smoke.py.
    Full suite 218 passed in the pinned container.

  - SUBPHASE 0.4 COMPLETE: build profiles (0.4.1) + known-good ASan/UBSan clean
    (0.4.2) + containment wrapper (0.4.3). Sanitizer & containment rig done.

carried_notes:
  - F9 (0.4.1 auditor): the FEASIBILITY COMPOSITION layer (1.4.3) must not key
    feasibility on exit code in leak-audit mode. The 0.4.3 wrapper already keeps
    this clean (labels only, no feasibility). Re-check when wiring §3.5 composition.
  - F9 (0.3.5 auditor): per-unit oracle driver (1.1.3) dispatches comparator by
    manifest output class (numerically-approximate -> compare_tolerance).
  - HYPOTHESIS: added at re-pin 0.4.2b; Hypothesis generators wired at 1.1.3/1.1.5
    (Phase-0 reference-kernel property cases still use the fixed-seed numpy corpus).

raw_result_paths:
  - /results/calibration/i1/raw/{csr_scale,pava}_{good,bad}_K30.json  (I-1 raw; 0.5.3 gate)
  - /results/prereg/PREREG_I1.md                 (committed before the run, 204ff84)
  - /results/calibration/d2/d2_scaling.json      (csr 2.050, pava 1.998; both in band)
  - /logs/env/STEP_0.5.1_d2_scaling.log
  - /results/containment/containment_smoke.json  (5 fixtures, all_pass)
  - /logs/env/STEP_0.4.3_containment.log

preregistrations: []   # none new this step

audit_status:
  # --- Phase-0-CLOSE (E) sweep on the FINAL post-correction raw (HEAD) ---
  E.validation-auditor: PASS (agent a6df68143afb4d7c8): 155/0 sanitizer-clean recomputed
                       from per-case records (numpy 75 + Hypothesis 80); toolchain binary-
                       identical re-proven from BOTH images (cc1/libasan/python3.12 sha256,
                       digests committed under results/audit/0.P-E-resign/); oracle §3.1
                       conformance 14/14 live probes; P1d non-vacuity 4 mutations; 322 passed
                       under the documented seccomp profile.
  E.measurement-auditor: PASS (agent a9f2dd3bf1486a790): criterion 4 MET both kernels on the
                       re-measured raw — csr pilot 0.315%, Horner worst-of-12 0.8778% (it
                       FLAGGED the 0.8707% mislabel, now corrected); median 78.199ms in band;
                       ratio 9.425x/1.964x; thermal 0/50C; quiesce-all §5.1 v1.2 encoding +
                       COR1 framing confirmed.
  E.stats-auditor:     RE-VERIFY PASS (agent abdf868ee850767bd, stamp 6f96696315053cb7) after
                       the 3 corrections — every in-scope statistic zero-diff vs corrected docs;
                       worst-of-12 0.8778%/canonical 0.8707% both <=1%; additive 3.054 GiB;
                       §7 totals 37/38 + column-sums 41/47 zero-diff, covered 30-31 predicate-
                       dependent confirmed. SUPERSEDES the first E pass add7d067dbc3a87e3 (FAIL
                       on the 3 now-fixed discrepancies).
  E.bo-math-reviewer:  n/a (no surrogate/acquisition code; first invocation Step 1.4.4).
  E.scrutinize:        SHIP (orchestrator outsider pass): corrections honest + re-verified;
                       5 exit criteria met; signature recorded verbatim w/ provenance + §5
                       scope (not self-signed); 4 carry-forwards complete. No blocker/major.
  # --- preflight 0.P (prior step), 100% sample, independent recompute ---
  validation-auditor:  PASS-with-concerns at 0.P (agent a58716a95f54c6d03): oracle
                       conforms to §3; I-3 suite GREEN 234 on current image 3bbe69a1d8f8;
                       feasibility labels 0-diff over 75/75; sanitizer carry-forward proven
                       (cc1/libasan/python3.12 byte-identical across re-pin). Sole concern =
                       P0e governance ack (already tracked as blocking). No blocker/major.
                       [prior: PASS 0.4.1 a7069481d0e104af6; PASS 0.3.5 ab86ba829eaae3d7e]
  measurement-auditor: FINAL RE-SIGN PASS at 0.P/C.4 (agent ab68a70ca367ad107): criterion 4
                       MET for BOTH I-1 reference kernels under the locked quiesce-all protocol
                       — csr 0.315% (pilot, contention-free) + Horner 0.964% @64M (seed-robust
                       across 10 seeds + B=200000; n NOT iterated — PREREG dd14054 pre-dates the
                       raw). Ratio 10.441x + csr 1.964x recomputed; thermal clean; §5.1 v1.2
                       quiesce-all correctly encoded (document revision, predates RQ1). No
                       blocker/major; nit: csr pilot2 raw IQR 1.0002% (criterion binds bootstrap
                       CI 0.315%, not raw IQR). Supersedes the G2 re-sign a322e455169c1efcd and
                       the 0.P PASS-with-concerns ae59f8213456d0894. [prior: 0.2.5 abee56684e72c6b14]
  stats-auditor:       PASS at 0.P (agent ac0f41068e2f04a7e): 38/38 numeric checks
                       zero-diff (I-1 ratios, pilot medians/IQR/bootstrap-CI grid, Horner
                       IQR, memory arithmetic). Its FAIL was SOLELY the §6.1 commit-ordering
                       gap (results/preflight/* uncommitted at audit time); cleared by
                       commit 04da4ff — all named files verified tracked (git ls-files).
  bo-math-reviewer:    n/a in Phase 0 (no surrogate/acquisition code exists yet) — recorded
                       n/a with justification per §6.6 item 5, not faked. First: Step 1.4.4.
  scrutinize:          DONE at 0.P (orchestrator, outsider pass over the preflight package):
                       verdict FIX-THEN-SHIP — technical preflight sound & ship-ready; the
                       only remaining "fix" is the two human gates (P0e ack + I-3 manual
                       signature) + roadmap-deletion confirmation. One MAJOR carry-forward:
                       the I-1-IQR > pilot-IQR DRAM-contention signal means the <=1% precision
                       assumption must be GENUINELY re-established at Step 1.2, not assumed.

defects: [D3, D4]

next_action: |
  PHASE 0 IS CLOSED. All 5 exit criteria met; the I-3 manual validation gate is SIGNED (E) and
  recorded (see i3_signature_recorded); the E auditor sweep is fully green on the post-correction
  FINAL raw (E.validation/E.measurement/E.stats PASS, bo-math n/a, scrutinize SHIP). Continue in
  STATE_PHASE1.md, next_action = Step 1.1.1, which carries the four close-out carry-forwards:
  (1) QUIESCE-ALL measurement protocol (C) — BINDING on ALL Step-1.2 drivers; per-unit CI@30 <=1%
  must be GENUINELY re-established there (the I-1 ratio does not stand in for per-unit precision —
  P0d); (2) PAVA-class low-Delta watch-list (PAVA, _cd_fast, Bellman-Ford _shortest_path) ->
  §1.3.3 single-amendment trigger, ASK HUMAN (Appendix B-12); (3) I-1 discrimination-band scope
  note (I-1 validated a LARGE speedup, not 1.2-1.6x band precision); (4) CF4 measurement-
  environment hygiene — identify + control the steady ~8ms (~11%) Horner run-to-run offset
  (background vs THP/page-fault) and pin a verified-quiet baseline + page policy BEFORE Step 1.2.

blocking: |
  NONE. Phase 0 is closed. All human gates resolved:
   - I-3 manual validation-gate SIGNATURE (D.2) — SIGNED in-session by the operator and recorded
     verbatim with provenance (i3_signature_recorded / I3_validation_gate_pack.md). Not self-signed.
   - P0e (D.1) — ACKED by the human via PHASE0_FINAL_CLOSE_ACTION_PROMPT (location=root + Horner
     edit 2b69ab2 canonical).
   - G2 §5.1 protocol — human DECIDED quiesce-all; §5.1 v1.2 APPLIED to the root law (C.3);
     measurement-auditor RE-SIGNED PASS (C.4, re-confirmed at E).
   - Roadmap "deletion" — was an INTENTIONAL move; reconciled to canonical = ROOT (G0/A).
```

NOTE: STATE lives under /results per roadmap §1.4.
