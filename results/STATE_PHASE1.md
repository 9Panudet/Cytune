# STATE_PHASE1 (schema: roadmap §6.4)

```
CLOSEOUT_(contrib-B): TERMINAL Phase-1 decision = (B) REFRAME (human-chosen). Building the run-grounded
                 closeout (ProjectReport.md + HTML). Epistemic rule: CHARACTERIZATION measured, BO<=RS
                 INFERRED (no underpowered RQ1 run). NEXT STEP on resume = finish Phase B + C + D below.
  PHASE A (measure) — DONE + committed (7f28596, f0d1a6c, A4 note, data backbone):
    A1 crit-3 callgrind (construction-subtracted B[N]-A[0], per-object, -O3 native, threads pinned):
       8 tunable survivors (predictor/binning 100, ppoly 99.5, elkan 99.3, csr 99.1, lda 96.0=.so55+libm41,
       floyd 94.8 PASS; isotonic 85.7 BORDERLINE) + DROP spot-checks (lloyd BLAS 73.5, dbscan obj 57.9).
       MEASURED refined the triage: lda 98->96, cc/_traversal 96->44.6 (validate_graph public-API plumbing).
       Raw results/characterization/crit3/; agg crit3_aggregate.py. NOTE cc is the weakest survivor (44.6%).
    A2 9/9 endpoint Δ (uniform all-endpoint): median_all 1.338 (78%>=1.2), median_strict 1.209 (56%) ->
       FLAT both axes. high-Δ subclass = csr 3.04 + elkan 3.93 (Δ_strict). delta_aggregate_final.py.
    A3 separability factorial (2 bc x 3 opt x 2 march, endpoint, ANOVA log-runtime): csr 99.7% main/0.3%
       interaction (boundscheck SS 92.7); elkan 95.4/4.6 (bc 42.7 + opt 52.6, bc:opt 4.4). >=95% additive ->
       MEASURED separability = empirical basis for INFERRED BO<=RS. separability_decompose.py.
    A4 opt-invariance: csr (archetype G3) + elkan (L==H strict bit-identical centers_new) -> Δ_strict is
       SPEED not correctness trade. results/characterization/A4_opt_invariance.md.
    DATA BACKBONE: results/characterization/ProjectReport_data.json (build_report_data.py) — single source
       of truth for report+HTML, all from committed raw. D5 contamination post-mortem: logs/defects/D5.md.
  PHASE B (audit) — DONE (phase-b-audit workflow wf_d1131a36-849; results/characterization/PHASE_B_AUDIT.md):
       measurement-auditor PASS_WITH_NOTES (11/11 crit-3 zero-diff, 9/9 endpoint median-of-3 exact, rig
       invariants confirmed); validation-auditor PASS_WITH_NOTES (I-1=9.425x, I-3 122 tests, 4 defects, all
       zero-diff); stats-auditor Δ/separability zero-diff (inline + measurement corroborated) + power via the
       COMMITTED 1.2.4 audit (partA_worst_abs_diff=0.0 over 36 cells) — stats power re-sim stopped after 16min
       (redundant w/ 1.2.4). Two PASS_WITH_NOTES caveats: (a) uncommitted Jun-29 rig logs -> RESOLVED efc83ff;
       (b) D1 I-2 guard is a Phase-2 forward commitment (honest scope note). scrutinize (B5) DONE: fixed §8
       motifbo-CLI overclaim (components exist, CLI is Phase-5 not built) + added cc-exclusion robustness.
  PHASE C/D — DONE: results/ProjectReport.md (9 sections, MEASURED/INFERRED labeled, every number traces to
       ProjectReport_data.json + recompute + auditor) + results/ProjectReport.html (embeds backbone verbatim,
       consistency-check passes). Commits 666d138, efc83ff, + audit/scrutinize commit. STATUS: STOP FOR HUMAN
       REVIEW — closeout complete, NOT declared final until human signs off. BO<=RS labeled INFERRED (not run).
  FINAL PASS (F1-F5 + RQ1' addendum + re-audit + resultNew.md) — DONE + committed (2dc9efe..f6a6294):
    F1 canonical corpus + crit-3-line robustness: n=7(6f)/8(7f)/9(7f) all FLAT (median Δ 1.408/1.373/1.338
       <1.5) + power<0.8 at every variant, module AND fold. Fold count CORRECTED 8->7 (canonical over 9
       endpoint survivors). F2 isotonic = DOCUMENTED EXCEPTION (retained; 14.3% in-place scaffolding cancels
       in the within-driver Δ ratio) — no floating BORDERLINE. F3 complete D-series D1..D6 (SILENT=D1/D2/D5/D6,
       caught-before-ship=D3/D4). F4 elkan closure = CO-BUILT-SIBLING .so (NOT inline) verified from pxd/pyx +
       cobuild; closure-complete; attribution valid ('inline' premise corrected as a finding). F5 per-unit
       scale/t_ref column + pava sensitivity (pava->1.5 => n9 median 1.408, still FLAT).
    RQ1' OFFLINE-REPLAY (new epistemic label MEASURED-REPLAY, grid-scoped): PREREG committed 2dc9efe BEFORE any
       outcome (zero outcomes in that commit, provable order); outcome b5f3fb8. RS (uniform,no-replace,
       E=(N+1)/(K+1)+10k MC) vs res-IV 8-run DOE screen+confirm=9 evals, on the measured 16-config grids.
       Result: 1 flat certificate (floyd K=8); 8 non-flat -> RS wins 8/8, sign-test p=0.00781; pre-registered
       DOE=8 sensitivity RS 7/1 p=0.07031 (direction robust, α=.05 not). Secondary 12-config: csr+elkan DOE
       (=§5 factorial=characterize) finds optimum. Scope: measured grids ONLY, not full Θ=1728. §8 full-Θ
       BO<=RS stays INFERRED. Raw results/characterization/rq1prime/; recompute rq1prime_replay.py.
    RE-AUDIT: dedicated §6.5 subagents (stats/measurement/validation) SESSION-LIMITED (API cap, reset 9:50am)
       -> RE-RUN owed on capacity reset. In-loop INDEPENDENT reimplementation (results/audit/closeout_rq1prime/
       independent_reaudit.py, no import of project scripts) = ALL ZERO-DIFF across F1/F5/power/RQ1'/F4/F3/
       commit-order. scrutinize PASS (ship): no residual 8-folds/BORDERLINE/inline overclaim; replay
       grid-scoped; DOE=8 sensitivity confirmed pre-registered (no post-hoc tuning).
    DELIVERABLE: results/resultNew.md (complete no-omissions result report; every number MEASURED/
       MEASURED-REPLAY/INFERRED-labeled + raw+recompute+audit stamp; deviations+unilateral-choices+limitations
       + self-verify checklist).
  F6/F7 FINAL TWO-GAP CLOSE — DONE + committed (349123b..b693878):
    F6 RQ1' REFRAME (statistical-correctness): replay restated as WIDE-BASIN/TIED-QUALITY corroboration, NOT
       'RS beats DOE'. Measured: near-opt BASIN median K/N=0.25 (from raw) -> RS reaches it in ~3.4 evals
       (1.89-8.5); a >=8-eval screen on a 16-pt grid can't win by evals (grid-size+basin-width property, not
       method superiority). Endpoint QUALITY ~tied: DOE within tau 6/8 (median 1.0058, worst 10% binning
       fast-math); RS hits exact best in 16-eval budget. Sign-test relabeled evals-to-basin (RS_E<DOE-9) NOT
       quality; p=0.00781 DOE-cost-dependent (0.07031@DOE=8), grid-scoped -> DEMOTED. §5 reconciled: structure
       exists & IS findable (12-config DOE lands on csr/elkan optima) AND grids too small to separate by evals.
       Applied: ProjectReport §7+spine+§8+§9, HTML view7+KPI (11 asserts), resultNew §2+F6 fault. build_report_
       data.py adds rq1prime.basin+quality (from raw).
    F7 REAL §6.5 AUDITORS RAN TO COMPLETION (workflow wf_f7805044-f8b + measurement re-run b693878): stats
       PASS (zero-diff, framing_ok, incl. 36-cell power reseed + full replay); validation PASS_WITH_NOTES
       (zero-diff, framing_ok; F3 D-series + F4 non-inline + I-1 9.425x; notes=scope caveats I-3/D6 not
       re-executed); measurement PASS (after fixing ONE 1e-4 round-order diff in doe_quality_median_ratio
       1.0057->1.0058 via round-once; re-ran clean). independent_reaudit.py (2nd line) ALL ZERO-DIFF incl F6.
    DELIVERABLE: results/CLOSEOUT_FINAL_LOG.md (F6 before/after + median K/N + §5 reconciliation; F7 verbatim
       auditor verdicts + notes; final RQ1' table; deviations/limitations; checklist all green; plain-language
       bottom line). STATUS: STOP FOR HUMAN REVIEW — all boxes GENUINELY checked (real auditors passed
       zero-diff); NOT declared final until human signs off.

phase:           1 (Harder Corpus & RQ1 Gate)
§4.5_GATE:       ========================= RESOLVED (b) POWER-TIME FLOOR =========================
                 Classified + committed TWICE: 5bcb17e, 13dd8cb. Full quote+anchors: PREREG_RQ1_UNIT_OF_
                 ANALYSIS.md §0. Do NOT re-litigate; this is the standing classification.
                 §4.5 VERBATIM (roadmap L324-326): "Primary n = units (target ~25, floor 20). Statistical
                 power is simulated before running (Step 1.5.2): paired-Wilcoxon power at n in {20,25},
                 delta in {0.2,0.4,0.6}, variance from the Phase-0 pilot; requirement: power >= 0.8 at the
                 pre-registered MDE, ELSE EXPAND UNITS FIRST. A negative result is defined in advance (§5.3)
                 and accepted as valid data."
                 CLASSIFICATION = (b) POWER-TIME FLOOR — NOT a hard pre-run gate. Anchors: (1) §4.5's only
                 remedy "else expand units first" is gated on POWER<0.8, not on n<20; (2) §4.3 shortfall rule
                 handles "<25 admissible units" by PRE-REGISTER + power (not stop) — "<25" subsumes "<20";
                 (3) the 1.1.2<->1.5.2 loop makes "expand units" a power-triggered remedy run BEFORE the
                 experiment. Floor is ALSO met at the roadmap's own granularity (30 nominal admissible >= 20).
                 DISCHARGE: 1.2.2 driver design is CLEARED of §4.5 — NO corpus expansion now. The expansion
                 fork is DEFERRED to the 1.2.4 clustered power decision (n=module 17 AND n=fold 11; NEW-corpus
                 variance; power<0.8 @ pre-reg MDE -> STOP + add 3rd/4th codebase THEN). This pre-reg IS the
                 committed §4.3/Step-1.1.2 shortfall pre-registration. (1.2.2 also gated on the CF-4 per-unit
                 seal + the measurement-structure decision below.)
cf4_result:      CF-4 = MECHANISM-RESOLVED (NOT "green"): environment + cause resolved; per-unit worst-case
                 seal owed at 1.2.4; PAVA-CLASS (short branch-heavy) FLAGGED AT-RISK. Bind: short branch-heavy
                 units must scale TOWARD 500ms to lower CI@30, but criterion-5 CAPS at 500ms -> a unit still
                 loose at 500ms cannot scale further -> may be UNABLE to meet CI@30<=1% in-band (pava already
                 at 0.996% = zero margin @ 503ms). Carry pava-class as a NAMED measurement risk, not a passed
                 gate. Data-driven baseline — results/characterization/CF4_BASELINE.md
                 + raw results/characterization/cf4/*.json (probe scripts/corpus/cf4_probe.py, real rig,
                 :phase1 cpu3, M=12-20, 3.6GHz verified constant 160 samples / zero throttle). CAUSE of the
                 Phase-0 ~11% offset: (1) streaming kernels = non-quiesce DRAM contention (CF-1 fixes:
                 csr CI@30 2.75%->0.82%); (2) short branch-heavy (PAVA) = runtime-floor (input-scale to
                 ~500ms fixes: pava CI@30 1.67%->0.996%). THP RULED OUT (no offset at 128KB/32MB/512MB under
                 CF-1); ASLR ruled out (9.5% was a single non-reproducing outlier; setarch/personality is
                 podman-seccomp-BLOCKED, not needed). DATA-CHOSEN POLICY = CF-1 quiesce-all + per-unit
                 input-scale ~500ms (band-upper, set at 1.1.5) -> NO _child.py page pin warranted (deviation
                 from refinement #6's assumed pin; defensive prctl(PR_SET_THP_DISABLE) OFFERED, not added
                 — OPEN human decision). RESIDUAL (#10): within-proc CI@30 <=1% @~500ms (csr 0.36-0.82%,
                 pava 0.996% AT THRESHOLD/zero-margin); between-proc rstd csr<=0.26% / pava 0.39% (range
                 1.7%) -> feeds §1.3.2 Δ + §1.5 MDE. Full per-unit worst-case seal = 1.2.4 (all 30 units;
                 pava-edge => short branch-heavy units need ~480-500ms golden). measurement structure (#9):
                 CI@30=within one subprocess(30 reps); run-to-run=between fresh subprocesses.
meas_structure:  DECIDED (binds 1.2.4/§1.5.3/§1.5.4; pre-register at PREREG_RQ1 1.5.1). Outlier
                 characterized: pava @74ms = 3.6% slow-outlier pop (3/84, up to +9.14%), VANISHES @~500ms
                 (0/20, max +0.64%) — raw probe2/3/5_*pava*.json. DECISION: (1) per-unit golden ~480-500ms
                 (PRIMARY: kills outliers + CI@30<=1%); (2) K_final endpoint = MEDIAN over 3 FRESH
                 subprocesses (each in-process K_final=30) — residual insurance, ~3x K_final-remeasure
                 compute only (affordable); K_final=30 itself unchanged; (3) pre-registered re-measure
                 /discard rule (subproc-median >Xσ from triple-median -> re-measure once; X fixed in
                 PREREG_RQ1). §6.6 THP ASSERT added to scripts/measure_wrap.sh (refuse unless host THP in
                 {madvise,never}; verified pass on thp=madvise) — captures the CF-4 host invariant,
                 fail-loud on drift to 'always'; ALSO a NAMED §6.6 Phase-1 preflight item: preflight runs
                 `measure_wrap.sh --verify-only` (asserts THP) so a phase cannot close without it.
  IMPLEMENTED:   1.2.2 RIG built ONCE (TDD): src/motifbo/timing/endpoint.py — measure_endpoint() =
                 median over N=3 FRESH subprocesses (UNIFORM, all units) sitting ABOVE the validated
                 runtime_ns.measure() primitive (NOT modified; K_final=30 passed straight through, never a
                 lever). RemeasurePolicy(threshold_x, max_remeasures, min_scale_rel) — NO production
                 defaults (an unregistered threshold cannot silently act); policy=None => pure median-of-N
                 (characterization, 1.2.4; raw spread preserved). Re-measure rule uses a FROZEN reference
                 (center+MAD-with-relative-floor from the ORIGINAL N), hard-capped, raw never discarded;
                 `flagged` MONOTONIC. THREE knobs (threshold_x, max_remeasures, min_scale_rel) ALL pre-
                 registered at 1.5.1 (min_scale_rel is the n=3 degenerate-MAD floor, structurally required;
                 named so it is not introduced post-hoc). TDD: src/tests/test_endpoint.py 17 tests GREEN in
                 :phase1 (primitive regression 6 GREEN). ADVERSARIAL REVIEW (workflow wf_63867afe-0e0, 3
                 lenses: stats / p-hacking / faithfulness+vacuity) caught 1 MAJOR — re-measure recomputed
                 center+MAD on the GROWING pool, so a slow re-draw could silently absorb (un-flag) a real
                 outlier (~20% phantom endpoint shift into the paired RQ1 diff). FIXED: freeze reference to
                 original N; verified by single re-check agent (resolved, no new defect) + two regression
                 tests (test_two_slow... discriminates the bug). HONEST LIMIT (recorded): a relative rig
                 has no absolute ground truth — an ALL-N-consistently-slow config cannot be flagged here
                 (1-of-3 and 2-of-3 ARE); that residual is covered by the per-unit ~500ms golden + paired
                 diff + CF-1, NOT this layer. INPUT-MANIFEST/PAIRING is the next rig piece, built WITH the
                 per-unit drivers (real inputs) — NOT half-built now.
  IMPL (manifest): INPUT-MANIFEST/PAIRING mechanism BUILT (TDD, ahead of per-unit drivers per directive):
                 src/motifbo/timing/input_manifest.py — fingerprint_args (SHA-256 over dtype + ORIGINAL
                 shape + C-contig bytes; fail-closed TypeError on opaque types), build_manifest, verify_input
                 (VERIFY-OR-REFUSE: raises InputDriftError on recipe-hash OR content-fingerprint drift),
                 measure_paired_endpoint (verify BEFORE any subprocess spawn — structurally guaranteed). 18
                 TDD tests GREEN. Adversarial review (1 agent) caught a LATENT false-equal (0-d array / numpy
                 scalar collapsed to shape (1,) via np.ascontiguousarray -> silent pairing break) — FIXED
                 (record original obj.shape) + 2 regression tests; verify-or-refuse path confirmed sound (both
                 hashes, provably pre-spawn). PAIRING MODEL: ONE manifest-hashed input PER UNIT, regenerated
                 in each subprocess from a committed deterministic recipe, IDENTICAL across all configs /
                 methods / seeds / all 3 endpoint subprocesses (materialized bytes NOT committed — ~400MB; the
                 manifest hash is). Per-unit manifests are built at 1.1.5 with the ~480-500ms goldens.
per_unit_campaign:
  - STARTED (Step 1.2 representative-first, human-directed). SURVIVAL LEDGER created + binding:
    results/characterization/SURVIVAL_LEDGER.md — 30 units x gates G1 driver / G2 crit-3 / G3 golden /
    G4 CI / G5 bit-id / G6 C-β2 / G7 CF-5, with surviving-N rollup (the 1.2.4 viability gate reads the
    SURVIVING clustered-n, not 17/11). Corrected gate ORDER (human): crit-3 GATES golden (a golden on a
    contaminated measurement is meaningless) — G1 -> G2 crit-3 -> G3 golden -> G4 CI -> G5 bit-id -> G6/G7.
    3 ARCHETYPES first (establish pattern before 30x compute): STREAMING #1 csr_mean_variance_axis0;
    BRANCH/PAVA #6 _inplace_contiguous_isotonic_regression; WRAPPER #10 lloyd_iter_chunked_dense.
  - GOLDEN REFERENCE CONFIG — CONFIRMED (human, verified vs source): as-shipped Cython (sklearn meson set
    -X cdivision=True -X wraparound=False -X initializedcheck=False -X nonecheck=False -X boundscheck=False;
    scipy author @cython) + GCC -O2 -march=x86-64 -ffp-contract=off, fast_math=off. Justification (stronger
    than cleanest-FP): contract=off makes the golden INVARIANT across opt_level/march (contract=fast lets
    the compiler pick FMA per opt/march -> golden bits would shift); march=x86-64 = reference reduction
    order (native AVX2 reorders FP reductions -> a tolerance-bounded perturbation); consistent with the
    expert-arm fallback (FMA infeasible where bit-exact demanded, feasible-within-tolerance on approx).
  - CORRECTIONS adopted: (a) crit-3 measured at the FASTEST config -O3 -march=native (worst-case for
    kernel share — a faster kernel makes fixed wrapper overhead a larger fraction; >=90% there holds for
    all slower). (b) GOLDEN OPT-INVARIANCE CHECK: build each golden at -O2 AND -O3 (both contract=off) ->
    bit-identical; DIFFERENT -> STOP (FP-affecting flag leak). (c) 4th archetype = a C++ unit (tree or
    _dbscan_inner) so CF-5 + C++ build + wrapper get archetype-level scrutiny, not first-touch in bulk.
    (d) oracle G5: deterministic kernels have cross-rep dev ~0 -> the DOMAIN FLOOR is the binding tolerance,
    pre-justified per unit (not tuned). Gate order: G1 -> G2 crit-3 -> G3 golden+optinv -> G4 CI -> G5
    oracle -> G6 β2(scipy) -> G7 CF-5(C++). REPORT after 4 archetypes -> ARCHETYPE_CAMPAIGN_REPORT.md ->
    STOP for human replicate-or-adjust (do NOT roll into 30 builds unprompted).
  - INFRA built: scripts/corpus/build_unit.sh (parameterized build any unit x config from vendored
    closure), corpus_drivers.py (per-unit driver registry), crit3_probe.py (kernel-share profiler).
  - ARCHETYPE 1 (STREAMING csr_mean_variance_axis0): G1 driver PASS; G2 crit-3 PASS, CROSS-VALIDATED by
    TWO independent instruments @ -O3 -march=native worst-case: wall-based (cProfile python-visible) 98.6%
    AND callgrind native-symbol (Ir) 99.0% — AGREE within 0.4%. The new wall-method is VALIDATED (not an
    overcount). Decisive worst-case (LONG_fill 50M being per-call -> 78% DROP) RULED OUT by callgrind
    N=0/N=8 per-symbol equality (it is one-time scipy setup). Raw G2_csr_mean_variance_O3native.txt +
    G2_csr_crit3_xvalidation.md. perf absent (image+host, paranoid=2) -> built characterization-only
    sidecar :phase1-tools (=:phase1+valgrind, data/env/Containerfile.tools); pinned MEASUREMENT image
    untouched. Reusable method: callgrind two-run TOTAL is import-noise-dominated -> use per-SYMBOL
    determinism + N=0/N=8 equality for setup-vs-per-call.
  - ARCHETYPE 1 G3/G4/G5 — COMPLETE (real data, committed archetypes/csr_mean_variance_axis0/):
    G3 golden PASS 484.3ms (9.7M rows/97M nnz), opt-invariance -O2==-O3(march=x86-64) BIT-IDENTICAL
    (scatter-add reduction, no horizontal-sum reorder); out 8c2381eb, .so e33b6554, crit-3@golden 98.87%.
    G5 oracle PASS (5 fresh reps bit-identical -> domain floor binds). G4 criterion-5: KERNEL PASS
    (8/9 subproc ci30 0.049-0.097%, >10x under 1%) but SURFACED a between-process memory-bandwidth-
    contention finding at the ~1GB working set (thermal-ruled-out; median-of-N absorbs it). RECIPE
    REVISED: scipy.sparse.random OOMs the 12GB ceiling at 85M nnz (measured 40M->7GB) -> fast O(nnz)
    deterministic builder, timing-equivalent (RECIPE_REVISION.md). input_manifest._feed gained scipy-sparse
    handling +2 TDD (20 pass).
  - ARCHETYPES 2-4 — drivers + valid gates + 3 BLOCKERS surfaced (the campaign's purpose):
    PAVA + dbscan NOT re-callable (timed call2/call1=0.23 / 0.004) -> G3/G4 timed BLOCKED (validated
    _child builds args once; per-rep refresh = open protocol decision A, couples to crit-3 -> G2 DEFER);
    G5 determinism PASS both. dbscan G7 CF-5 PASS (ASan+UBSan clean + 0 kernel leaks, proven by no-call
    negative control = reusable CF-5 method). Lloyd bare-load BLOCKED by circular import of installed
    sklearn.cluster but FIXED by loader pre-import (verified) -> re-callable+deterministic (ratio 1.004);
    G2-G5 PEND a small _child loader change (decision C). Memory-contention = decision B.
  - REPORT WRITTEN: archetypes/ARCHETYPE_CAMPAIGN_REPORT.md. Recommendation GO-conditional on decisions
    A (in-place per-rep refresh), B (memory-contention/criterion-5 framing + rig hardening), C (wrapper
    loader pre-import). NO 30x initiated. STOPPED for human replicate-or-adjust.
  - A/B/C RESOLVED + IMPLEMENTED (human-delegated, DECISIONS_ABC.md, roadmap v1.4): A=per-rep regen for
    in-place (TDD); B=criterion-5 gates ENDPOINT precision; C=wrapper loader pre-import (lloyd drives rig).
  - ARCHETYPE RE-PROVE under v1.4 (ARCHETYPE_REPROVE_REPORT_v1.4.md): csr PASS (98.88% crit-3, golden 485.9ms
    on the corrected timing-equivalent BINOMIAL builder, opt-inv ba55942f); PAVA crit-5 PASS (endpoint 0.161%
    @485ms, CF-4 re-check verdict CF4_RECHECK.md = NOT degenerate but proxy) / crit-3 BORDERLINE 89.5%;
    dbscan DROP crit-3 (~85% memoryview ovhd); lloyd DROP crit-3 (~70% BLAS _gemm, not C1-rescuable).
    BLAS scan: _cd_fast x3 high-risk. n_module 17->15 measured (->~12-15 projected), fold ~9-11.
  - csr criterion-5 (Decision B): endpoint precision 2.4% > 1% @485ms (contention-limited) -> needs mlock.

viability_gate_1.2.4:
  - DECISION: power < 0.8 at the pre-registered MDE -> STOP -> CODEBASE-EXPANSION FORK (VIABILITY_GATE_1.2.4.md).
    Clustered paired-Wilcoxon power (scipy exact, N_SIM=10000) reaches >=0.8 ONLY at delta=0.6 AND module n>=12;
    delta<=0.4 underpowered at ALL n<=17 (delta=0.4 max 0.652@17); fold n<=11 below 0.8 even @delta=0.6 (0.781).
    ROBUST: holds at optimistic 17/11; the 2-package corpus is structurally capped <=17/11 (PREREG: >=25
    independent UNACHIEVABLE from 2 packages), crit-3 drops only worsen it. Recommend (i) add 2-3 independent
    packages (more folds) before sinking 1.3/1.4/1.5 compute. STOPPED for human (proceed-or-expand).
  - STRENGTHENED by full crit-3 triage (CRIT3_TRIAGE_FULL.md; 4 callgrind + 13 source-triaged & adversarially
    verified): surviving MODULE 9-10/17, FOLD 7-8/11 (folds linear_model, tree, manifold DROP entirely).
    SURVIVE=pure-Cython streaming/arith; DROP=BLAS(cd_fast,lloyd,bglu)+pointer-chasing(tree,tsne,mst,dijkstra)
    +memoryview(dbscan). At surviving 9-10/7-8 power<0.8 at EVERY delta (delta=0.6: module 0.73-0.75, fold
    0.56-0.63) -> expansion fork UNAMBIGUOUS across the whole MDE grid. Target ~25-28 clusters for delta=0.4
    (~2-3 more independent codebases; pandas/_libs + scikit-image, curate to pure-Cython). EXPANSION_FORK_OPTIONS.md.
    Source predictions PROJECTED pending callgrind at the expanded-corpus sweep; verdict robust (holds at 17/11 too).
  - POWER AUDITOR-VERIFIED (1e90a05): stats-auditor recomputed power_table.json INDEPENDENTLY -> ZERO-DIFF
    on all 36 cells (fork auditor-confirmed). Extended thresholds had NO committed generator + were off-by-one
    -> FIXED: extended scan now in the committed generator (power_table_extended.json, provenanced): delta=0.4
    n=26 (not 25), delta=0.2 ~102 (MC-boundary), delta=0.6 n=12. Method/delta-def: POWER_SIM_METHOD.md (one-
    sample Cliff's-delta vs 0, mu=Phi^-1((1+d)/2), scale-invariant sigma; conservative vs two-sample). raw
    results/audit/1.2.4/. EXPANSION_FORK_OPTIONS corrected 25/101->26/102.

delta_probe_1.3 (the SECOND viability axis — power necessary NOT sufficient) — 9/9 ENDPOINT-VERIFIED:
  - VERDICT: directive-tunable crit-3 SURVIVOR class is FLAT -> §1.3 FAILS on BOTH axes. Delta_all median
    1.338 (<1.5; 78% >=1.2), Delta_strict (FP=T bit-preserving = verified-correctness axis) median 1.253
    (<1.5; 56% >=1.2). ALL 9 surviving modules probed (16-config 2^4 CHK·DIV·OPT·FP); the 5 high-stakes
    units re-measured on the v1.4 median-of-3-subprocess ENDPOINT rig. PREREG_DELTA_PROBE.md (1e90a05, pre-
    data). Raw delta_probe/{<unit>.json screen, <unit>__endpoint.json endpoint}. Recompute delta_aggregate_final.py.
    Report DELTA_PROBE_REPORT.md. Drivers: corpus_drivers.py (elkan_setup/predictor_setup, pkg cobuild).
    Scripts NEW: delta_probe_pkg.py (package-import multi-module units), delta_probe_endpoint.py (bare endpoint),
    run_delta_probe_pkg.sh / run_delta_probe_endpoint.sh.
  - GAP-2 WAS DECISIVE (the human's screen-grade concern): floyd SCREEN Delta=3.188 was MEASUREMENT
    CONTAMINATION (SP*L 786/810ms ran 03:18 under duplicate-container/power-gen CF-1 violation). ENDPOINT
    floyd = 1.338/1.179 FLAT (all 16 cfg 250-336ms; mem-bandwidth-bound at N=700). This dropped the corpus
    median 1.513->1.338 — i.e. the screen showed a MARGINAL Delta_all PASS (median 1.513) that was a floyd
    artifact; the clean rig FLIPS it to robust FLAT. Every "high" unit therefore endpoint-verified; flat
    screen-only units (lda/pava/ppoly) not re-measured (contamination only inflates -> true Δ <= screen).
  - 9/9 best-available Delta_all/Delta_strict (5/9 endpoint, 4/9 screen): elkan 3.929/3.929 (endpoint 500k;
    vectorization REPRODUCES SPLT209->SPHT83=2.5x; screen was 4.298), csr 3.183/3.040 (endpoint; boundscheck,
    checks-off 197 vs -O1-on 626; SPLT-ep
    626~=screen625 so NOT contaminated), _binning 1.696/1.253 (endpoint; Delta_all is FAST-MATH INSTABILITY
    best+worst both FP=A; strict flat), _predictor 1.408/1.381 (endpoint; OPT-only, boundscheck ~1.03x),
    floyd 1.338/1.179 (endpoint), lda 1.311/1.192, cc 1.299/1.299 (clean screen), PAVA 1.154/1.134,
    ppoly 1.109/1.084. CORPUS IS BIMODAL: 2/9 genuine high-Δ (csr boundscheck, elkan vectorization) + 7/9 flat;
    median is the 5th-of-9 in the flat cluster -> robust to the rank-8/9 outliers.
  - MECHANISM (CORRECTED from the 5/9-screen report): TWO real levers, neither universal — (1) boundscheck
    elision (csr 3.2x, index-streaming), (2) -O3/-march=native AUTO-VECTORIZATION (elkan 2.5x, dense FP
    distance loop). Both already in Θ. The prior "GCC flags ~1.0-1.14x, boundscheck lone lever" claim is
    FALSIFIED: GCC opt/march DO move dense vectorizable kernels a lot. Flat majority (transcendental/sequential/
    bisect/pointer-BFS/tree-DFS/mem-bound) has neither lever -> ~1.1-1.4x. §1.3.3 amendment (extended -f flags)
    ADVISE AGAINST: only >=3x levers are boundscheck (Cython directive, in Θ) + -O3/march (in Θ); -f flags <=1.4x.
  - DEEPER RQ1 CONCERN (compounds toward B, independent of flatness): even the 2 high-Δ units are LOW-DIM/
    SEPARABLE (csr=single boundscheck binary cliff; elkan=2-3 near-additive discrete knobs) -> RS≈BO there too.
    Both regimes RQ1-unfavorable: flat 7/9 null-from-absence, high 2/9 null-from-separability.
  - STOPPED for human A/B/C: (A) PROCEED FORECLOSED (median<1.5 both axes, production rig). (B) REFRAME to
    contribution-(B) [LEAN] §0.4/§1.5.6b — stronger than bare negative (mechanism explains BO<=RS). (C)
    DIFFERENT-CLASS available but cautioned (high-Δ subclass EXISTS but is low-dim/separable -> still
    RS-favorable); guardrail = PRE-REGISTER candidate criterion + cheap Δ-probe BEFORE vendoring. NOT
    self-decided. MDE options for pre-reg if expanding: delta=0.4->~26 vs delta=0.6->~12.

protocol_revisions:
  - v1.3 (2026-06-25, Step 1.2.2) MEASUREMENT-PROTOCOL REVISION — median-over-N=3-subprocesses endpoint.
    Recorded VISIBLY (not absorbed silently) the way v1.2 quiesce-all was: roadmap Revision log
    (Motif+BO-Roadmap.md line 6, v1.3 entry) + inline §5.1 tag (line 336) + evidence doc
    results/characterization/CF4_BASELINE.md (v1.3 banner). CLASSIFICATION = DOCUMENT REVISION: does NOT
    consume the §1.3.3/B-12 single amendment; PREDATES any RQ1/endpoint data (none exists yet). Motivation:
    the CF-4 between-process outlier (pava +9.14% @74ms -> 0% @500ms). Structure: N=3 fresh subprocesses +
    per-(unit,config) median + fail-closed re-measure rule vs a FROZEN original-N reference (3 knobs
    threshold_x/max_remeasures/min_scale_rel pre-registered at PREREG_RQ1 1.5.1). K_final=30 PRESERVED
    (per-subprocess rep count, never a lever). Binds 1.2.4 / §1.5.3 / §1.5.4 uniformly. Impl
    src/motifbo/timing/endpoint.py (TDD 17 green; adversarial review caught+fixed a growing-pool MAD-mask
    bug, frozen-ref fix). Honest limit kept: all-3-consistently-slow not flaggable by this layer.
  - REPORTING LEVELS (auditor clarity — do NOT conflate; stated in CF4_BASELINE "REPORTING LEVELS"):
    WITHIN-subprocess (K_final=30) -> median + IQR + MAD; the Step-1.2.4 CI@30<=1% gate (CF-3) is
    evaluated HERE (single-subprocess precision; pava-class AT-RISK seal at this level).
    BETWEEN-subprocess (N=3) -> the median is the robustness-layer ENDPOINT (the value entering the paired
    RQ1 diff §1.5.3/§1.5.4); its rstd is characterized SEPARATELY and is NOT the CI@30 gate. endpoint.py
    returns both (subproc_medians_ns for the spread, endpoint_ns for the comparison); stats-auditor
    recomputes each at its own level.

subphase.step:   1.2.2 (DRIVER STRUCTURE — rig built; see IMPLEMENTED above) — the median-of-3 +
                 re-measure endpoint rig is TDD-green + adversarially reviewed (MAJOR found+fixed). NEXT =
                 per-unit drivers (~480-500ms goldens, seed-generated/manifest-hashed/committed/paired
                 inputs) -> 1.1.4 D1 smoke -> 1.1.5 golden+SHA-256 (manifold >=5-rep bit-identity gate) ->
                 oracle.json tolerance freeze (pre-registered floors) -> 1.2.1 >=90% kernel share (crit-3
                 drop gate) -> 1.2.4 CI@30<=1% per-unit worst-case (CF-3; pava-class AT-RISK) -> C-β2
                 faithfulness -> CF-5 (tree/_dbscan_inner ASan+UBSan+leak) -> VIABILITY GATE (clustered
                 power preview re-gridded to REAL n in {11,17}, NEW-corpus between-cluster variance, pre-reg
                 MDE; power<0.8 -> STOP + codebase-expansion fork BEFORE 1.3). [Prior 1.2.0 record retained:]
                 RQ1 unit-of-analysis + curated set RATIFIED (human); §4.5 floor-20 classified (b)
                 POWER-TIME FLOOR -> PROCEED to 1.2. Entering the CF-4 measurement-hygiene gate.
                 RATIFIED (locked): cluster PRIMARY=module n=17 / SENSITIVITY=fold n=11 / function×seed=§5.2
                 secondary; robust <=> 3x §5.3 @ module AND direction @ fold; n=19 (tree 3 .pyx) REJECTED
                 (one .so, coupled import cascade -> 1 feasibility unit); median-to-module aggregation;
                 fold-direction-agreement as n=11 rule; curated 30-unit set (tree=2; KEEP bellman_ford;
                 sparse-kmeans/group_sparse TRIM stays). §4.5 FLOOR CLASSIFICATION (b), recorded
                 results/prereg/PREREG_RQ1_UNIT_OF_ANALYSIS.md §0 (gating resolution): no run/no-run count
                 gate in §4.5; only remedy "expand units" is power-gated (§4.5/§1.5.2 "else expand units...
                 before running"); §4.3/1.1.2 shortfall = pre-register reduced n + power, NOT stop; floor MET
                 at nominal granularity (30>=20). Adaptations pre-registered: power sim at clustered n
                 (17/11), NEW-corpus variance (1.2.4) not Phase-0 pilot, gate moved earlier to 1.2.4.
                 Expansion fork DEFERRED to the 1.2.4 power decision (power<0.8 @ MDE -> STOP + add 3rd/4th
                 codebase). This pre-reg IS the committed shortfall pre-registration.
                 ---- prior boundary (1.2.0-PREP, retained for trace) ----
                 (A) RQ1 UNIT-OF-ANALYSIS pre-reg (results/prereg/PREREG_RQ1_UNIT_OF_ANALYSIS.md, PROPOSED):
                 a §5.1/§5.2 OPERATIONALIZATION of the analysis "unit" (NOT B-12 — touches no pinned constant;
                 seeds>=20, K_final=30, B unchanged). The matrix cythonizes per MODULE -> function-units in a
                 module share IDENTICAL feasibility + correlated timing -> n=43-44 is n-INFLATED ->
                 anti-conservative Wilcoxon -> falsely-significant RQ1. RATIFIED CLUSTER: PRIMARY = MODULE
                 (n=17, feasibility-independence); SENSITIVITY = FOLD (n=11, LOMO §5.4); function×seed (43-44)
                 = the §5.2-named labeled secondary only. RQ1 robust <=> all 3 §5.3 criteria hold at MODULE
                 AND direction preserved at FOLD. Aggregation frozen (per-fn paired diff -> median to module
                 -> Wilcoxon/Cliff/BCa @ n=17 -> median to fold @ n=11). HONEST LIMIT: §4.1b ">=25 units" is a
                 COMPOSITION req (nominal, MET); >=25 INDEPENDENT units is UNACHIEVABLE from 2 packages -> n=17/11
                 are BELOW §4.5 floor-20 -> this IS the §1.1.2 shortfall condition at inference granularity,
                 pre-registered not papered over. VIABILITY GATE: clustered power preview at 1.2.4 (n=fold AND
                 n=module, NEW-corpus variance, pre-registered MDE); power<0.8 -> STOP + surface fork (add
                 independent codebases OR accept+prereg underpowered) BEFORE 1.3/1.4/1.5.
                 (B) CURATED UNIT SET (results/characterization/CURATED_UNIT_SET.md, PROPOSED): source-grounded
                 fan-out (workflow wf_1107d32d-c3a, 11 reader-agents) -> curated by INDEPENDENT INFORMATION to
                 30 NOMINAL units / 17 modules / 11 folds (from 43-44; ~30% drive-compute cut, no independent
                 signal lost; all 17 modules + 11 folds keep >=1 rep). Trims = layout/dtype variants (csc, sparse
                 k-means, binned-predictor, group_sparse, evaluate_nd) + reduction-subsets. TREE honestly = 2
                 (build-via-fit + ccp_pruning_path); split/criterion/partitioner are cdef INTERNALS reachable
                 only via fit() -> NOT independent §4.4 units. Overrides flagged: KEPT bellman_ford (CF-2
                 Δ-watch + distinct relaxation pattern). _map_num_col_to_bins does NOT exist (removed).
                 (C) CORRECTIONS LOGGED (not acted on prematurely): (i) import-confirmed != fully-admissible —
                 the 11 folds still owe criterion-3 (>=90% share, 1.2.1), criterion-5 (50-500ms, 1.1.5), Δ (1.3);
                 (ii) MANIFOLD determinism: "twice" is insufficient — re-confirm bit-identity across >=5 reps ON
                 THE ACTUAL 1.1.5 GOLDEN INPUT (binding 1.1.5 obligation; deferred — golden not built yet);
                 (iii) ORACLE.JSON: NOT authored with provisional floors; floors pre-registered BEFORE any
                 config-pass observed; freeze is mechanical derive_tolerance(max(10x measured dev, justified
                 floor)) at 1.2/1.1.5.
timestamp_utc:   2026-06-23T00:00:00Z

phase0_closed:
  - Phase 0 is COMPLETE (see results/STATE_PHASE0.md, closed 2026-06-16). Exit criteria all met:
    I-1 PASS with margins (csr_scale raw-pointer 1.964x >= 1.15x; Horner numeric-loop 9.425x >=
    1.5x); I-3 oracle suite GREEN (322 passed) + the I-3 MANUAL VALIDATION GATE SIGNED in-session
    and recorded (results/preflight/I3_validation_gate_pack.md); ASan/UBSan clean on known-good
    over the FULL §3.3 input set (155 cases, 0 reports = 75 numpy + 80 G1 Hypothesis); pilot
    report committed with K_final=30 + thermal-discard 62C; preflight 100%.
  - E auditor sweep on the FINAL post-correction raw: E.validation PASS (a6df68143afb4d7c8),
    E.measurement PASS (a9f2dd3bf1486a790), E.stats RE-VERIFY PASS (abdf868ee850767bd,
    stamp 6f96696315053cb7), bo-math n/a, scrutinize SHIP. The E stats sweep caught + corrected
    3 reported-number discrepancies (Horner worst-of-12 0.8778% not 0.8707%; §7 predicate-
    independent reframe; additive memory 3.054 GiB) — no gate verdict changed.

carry_forwards (BINDING on Phase 1 — from the Phase-0 close-out, PHASE0_CLOSE_E_ACTION_PROMPT):
  - CF-1 QUIESCE-ALL measurement protocol (§5.1 v1.2): compile workers on cores 0-1 are quiesced
    during EVERY measured run, all units. BINDING on ALL Step-1.2 drivers. Per-unit bootstrap
    CI@30 <= 1% must be GENUINELY RE-ESTABLISHED at Step 1.2 — the I-1 ratio does NOT stand in
    for per-unit precision (P0d). Default stays quiesce-all (correctness > throughput); reversible
    to memory-bound-only (G2 protocol (i)) only if §1.5 throughput is threatened — re-evaluate at
    Step 1.2 with real per-unit build/measure times. The C.2 cost projection = per-candidate lost
    compile/measure overlap.
  - CF-2 PAVA-class low-Delta WATCH-LIST: sequential / division-bound units (PAVA =
    sklearn.isotonic _isotonic.pyx Delta~1.231x; _cd_fast; Bellman-Ford _shortest_path) are
    expected DOWNWARD pressure on corpus-median Delta. §4.1c admission = median Delta >= 1.5 AND
    >= 70% units >= 1.2. If these pull the median under 1.5, that is the §1.3.3 SINGLE-AMENDMENT
    trigger (Appendix B-12, still UNSPENT) -> ASK THE HUMAN before spending it. Confront at Step
    1.3, not by surprise at 1.5.6.
  - CF-3 I-1 DISCRIMINATION-BAND scope note: I-1 validated the rig against a LARGE speedup
    (8.691x/9.425x), NOT precision in the 1.2-1.6x band where the corpus lives. Band precision is
    ESTABLISHED at Step 1.2 (per-unit IQR/CI re-characterization), NOT assumed from the I-1 ratio.
  - CF-4 measurement-environment HYGIENE: a steady ~8ms (~11% of the Horner median) run-to-run
    offset appeared between two clean Horner runs; eff_ghz flat (frequency ruled out), thermal
    clean (throttle ruled out), source UNIDENTIFIED — background process OR transparent-huge-page/
    page-fault variance on the 512MB streaming alloc (4KB pages -> TLB thrash vs THP). Did NOT
    block Phase 0 (cancels in paired RQ1 comparisons, conservative for ratios) but a measurement
    floor drifting 11% run-to-run is an RQ1 liability. BEFORE Step 1.2 corpus measurements:
    (1) determine the cause (compare an explicit hugepage/pre-fault policy; check an idle-baseline
    run with no candidate for residual load); (2) bring the measurement core to a VERIFIED-QUIET
    baseline + pin the page policy; (3) document the residual offset + its bound.

phase1_standing_constraints (roadmap §5.3 / §6.1 / Appendix B-12):
  - RQ1 is the hard gate (§5.3): Phases 2-5 stay dead until it passes. Phase-1 EXIT does NOT mean
    "BO beats RS" — it means the RQ1 decision is recorded HONESTLY per §5.3 with auditor-verified
    zero-diff stats and preflight 100%. An RQ1-NEGATIVE result, with the Step-1.5.6 decision tree
    triggered correctly, IS a valid and complete Phase-1 exit.
  - NEVER tune, re-run, p-hack, select seeds, or reframe criteria to force a positive. Seeds >= 20
    and K_final = 30 are NEVER levers. Pre-registered reduction levers if the envelope is exceeded:
    B = 40, unit count — only those.
  - The SINGLE pre-registered amendment (Appendix B-12) is UNSPENT project-wide. Exactly one exists
    (Step 1.3.3 / 1.5.6). Spending it is recorded in STATE and gated on ASK-HUMAN.
  - Empirical honesty: raw -> /results committed BEFORE any aggregate; stats recomputed only by
    stats-auditor from raw; pre-register (/results/prereg/PREREG_*.md) committed before any
    comparison; a number without a raw-file pointer does not exist.
  - Ask the human before: spending the single amendment; any deviation from a pinned constant;
    anything requiring host root (turbo/governor); any roadmap-interpretation ambiguity.

step_1.1.1_scouting (pre-vendor evidence; CHECKPOINT 1 approved):
  - VERSION SKEW found + surfaced to human: the container's pinned/installed stack is
    scikit-learn 1.8.0 / scipy 1.17.1 (requirements.lock; what SMAC's RF backend uses), NOT the
    human-approved CORPUS pins 1.5.2 / 1.13.1. DECISION (human approved 1.5.2/1.13.1 + "continue"):
    vendor the corpus at 1.5.2/1.13.1 as INDEPENDENT external source compiled standalone in-
    container; the harness's own 1.8.0/1.17.1 is a DOCUMENTED skew. Corpus units build self-
    contained against numpy 2.4.6 + Cython 3.2.5 + gcc-13; golden from the unit's own reference-
    config build, NOT the installed package. (Build-compat of OLD source vs NEW numpy/Cython is the
    open risk → the build-isolatability proof below is the arbiter.)
  - SDISTS fetched + sha256-VERIFIED against PyPI-declared digest (THIS IS THE UPSTREAM PIN; sdist
    == release tag):
      scikit_learn-1.5.2.tar.gz  sha256 b4237ed7b3fdd0a4882792e68ef2545d5baa50aca3bb45aa7df468138ad8f94d
      scipy-1.13.1.tar.gz        sha256 095a87a0312b08dfd6a6155cbbd310a8c51800fc931b8c0b84003014b874ed3c
  - INVENTORY at 1.5.2/1.13.1 (criterion 1 non-templated):
    * scipy 1.13.1 FULLY INTACT — all 6 target .pyx present incl optimize/_bglu_dense.pyx (verified
      to EXIST per human directive — NO preemptive swap; optimize/_group_columns.pyx also present
      as a backup unit). csgraph _shortest_path/_traversal/_min_spanning_tree.pyx, interpolate
      _ppoly.pyx all present.
    * sklearn neighbors EXCLUDED at BOTH versions — _ball_tree.pyx.tp / _kd_tree.pyx.tp /
      _binary_tree.pxi.tp are Tempita at 1.5.2 AND 1.8.0. The neighbors fold is OUT regardless of
      version (not a recoverable-by-pin loss).
    * sklearn PAVA present at TOP-LEVEL sklearn/_isotonic.pyx (NOT isotonic/_isotonic — first path
      check was wrong; corrected). utils/sparsefuncs_fast.pyx, linear_model/_cd_fast.pyx,
      manifold/_barnes_hut_tsne.pyx, tree/_tree+_splitter+_criterion.pyx,
      cluster/_k_means_lloyd+_k_means_elkan+_dbscan_inner+_hierarchical_fast.pyx,
      ensemble/_hist_gradient_boosting/_binning+_predictor.pyx all present (non-templated).
  - FOLD COUNT now EXACTLY 10 (neighbors lost): sklearn {utils, isotonic(_isotonic top-level),
    tree, cluster, linear_model, manifold, ensemble._hist_gb} = 7 + scipy {csgraph, optimize,
    interpolate} = 3. Meets §4.1b >=10 with ZERO MARGIN — any further fold loss breaks the gate.
    ACTION at 1.1.2: scout a non-Tempita 11th-fold candidate for safety margin.
  - UNIT CEILING ~21 realistic at 1.5.2/1.13.1 (neighbors gone). Reaching the >=25 floor requires
    aggressive WITHIN-codebase expansion (utils/_cd_fast/csgraph/_ppoly multi-function units). The
    §1.1.2 SHORTFALL RULE (pre-register reduced n + power consequence -> 1.5.2 power sim) is a LIVE
    possibility, not remote. Do NOT pad with inadmissible units (human directive). [Earlier
    "comfortable >=25" claim was WRONG — own maxes sum to ~21.]
  - CONSTRAINTS now binding on all corpus build/measure (human directives, this step):
    OMP_NUM_THREADS=1 at build AND run (kill non-deterministic parallel float-reduction order);
    bias input scale toward ~500ms band-upper (dilute the unresolved CF-4 ~8ms offset: 16% on 50ms
    vs ~1.6% on 500ms — makes CF-3 <=1% CI@30 reachable; watch 12GB ceiling); prove per-unit
    isolated compilability IMMEDIATELY after vendoring (cimport-coupled _tree/_splitter/_criterion,
    _k_means_* are the real criterion-3 risk, not Tempita).
  - sdists DOWNLOADED + listed at host /tmp/dl/*.tar.gz (scratch, re-fetchable by sha256 above);
    NOT yet extracted/vendored into /data/corpus — vendoring + manifests + checklists is the next
    committed action. (These STATE edits are themselves uncommitted, pending the next git commit.)

step_1.1.1_build_isolatability (criterion-3 proof, in-container; human directive):
  - BUILD MECHANISM PROVEN end-to-end (low-coupling case): sklearn 1.5.2 utils/sparsefuncs_fast.pyx
    cythonize (Cython 3.2.5) -> gcc-13 -O3 -march=native -ffp-contract=fast -fopenmp -> .so ->
    STANDALONE import OK under OMP_NUM_THREADS=1. 1.5.2 source builds CLEAN against the container's
    NEWER numpy 2.4.6 / Cython 3.2.5 — NO source patch needed. The version-compat risk (old source
    vs new numpy/Cython) is RESOLVED for this case. Probe harness: scripts/corpus/build_probe.sh.
  - sparsefuncs_fast exports 7 hot-loop fns (csr/csc_mean_variance_axis0, incr_mean_variance_axis0,
    inplace_csr_row_normalize_l1/l2, csr_row_norms, assign_rows_csr) -> SEVERAL candidate UNITS from
    ONE file (eases the tight ~21-unit count).
  - COMPILE succeeds in isolation for 5/6 probed: sparsefuncs_fast, _isotonic (PAVA), _cd_fast,
    _k_means_lloyd (OpenMP prange), scipy csgraph/_shortest_path. The __check_build / scipy.__config__
    ImportErrors are STANDALONE-IMPORT-HARNESS artifacts (the fresh .so does an init-time absolute
    `import sklearn`/`scipy` that trips the package "are-you-built" guard) — the .so compiled fine.
  - _tree.pyx FAILS C-mode cythonize because it is a C++ unit (libcpp.vector/algorithm + cdef extern
    "<algorithm>") -> needs cython --cplus + g++ + -std=c++14. FIXABLE (build as C++), not a defect.
    Also has runtime `from scipy.sparse import issparse,csr_matrix` + cnp (numpy C-API) + sibling
    ._utils cimport. Tree-fold survival is GATE-RELEVANT (folds at exactly 10) -> must confirm a tree
    unit (_tree/_splitter/_criterion) builds as C++ before counting the fold.
  - CLOSURE PATTERN for coupled units (the real 1.1.1/1.2.2 work): per unit resolve (a) C vs C++
    mode; (b) sibling Cython modules with runtime .so that must ALSO be built (_cd_fast needs
    utils/_cython_blas + _random; _tree needs ._utils); (c) runtime Python imports needing a minimal
    importable package context (sklearn/__init__ stubbed past __check_build; sklearn/exceptions.py
    for ConvergenceWarning; scipy for _tree). PLAN: vendor a minimal-but-real package subtree per
    fold (submodule + utils closure + stubbed __check_build), build unit + sibling closure from
    1.5.2/1.13.1 source, then standalone-import. NOT mixing 1.5.2 .so into the installed 1.8.0 tree
    (ABI/version skew on shared .pxd like _cython_blas).

step_1.1.1_CPP_TOOLCHAIN_BLOCKER (HOLDING for human decision):
  - ENV BLOCKER: the pinned image has NO C++ compiler — cc1plus missing, libstdc++ headers MISSING,
    no g++/c++ binary (image was built for C Cython; Phase 0 kernels were C). => every C++ Cython
    unit is UNBUILDABLE in the current pinned container.
  - C-vs-C++ map of §4.3 candidates (grep: language=c++ / from libcpp / cdef extern from "<):
      C++ (BLOCKED): sklearn tree/_tree + _splitter + _criterion (WHOLE tree fold),
                     cluster/_dbscan_inner, cluster/_hierarchical_fast.
      C   (buildable): utils/sparsefuncs_fast, _isotonic(PAVA), linear_model/_cd_fast,
                     cluster/_k_means_lloyd, cluster/_k_means_elkan, manifold/_barnes_hut_tsne,
                     ensemble/_binning, ensemble/_predictor, scipy csgraph/_shortest_path +
                     _traversal + _min_spanning_tree, optimize/_bglu_dense + _group_columns,
                     interpolate/_ppoly.
  - CONSEQUENCE (gate-relevant): tree fold LOST (all C++) -> folds 10 -> 9 < §4.1b's >=10 = HARD
    violation. cluster fold SURVIVES (lloyd+elkan are C). C-buildable unit ceiling ~23 across 9 folds.
  - DECISION REQUIRED (human — deviation-from-pinned-image AND gate-relevant; NOT self-decided):
      (A) Add g++ + libstdc++-dev (matching gcc-13) to the image -> re-pin digest + TOOLCHAIN.lock +
          re-verify the Phase-0 C-toolchain byte-identical invariance (cc1/gcc/libasan unchanged) so
          Phase-0 reproducibility is undisturbed -> recovers tree + dbscan + hierarchical, >=10 folds
          with margin. RECOMMENDED (the §4.3 inventory explicitly lists C++ units; a C-only corpus
          would systematically bias against tree-based + hierarchical algorithm families AND breaks
          the >=10-fold gate).
      (B) Stay C-only: drop all C++ units (tree fold + dbscan + hierarchical), recover a 10th
          (+ 11th-margin) fold from a NEW C-Cython codebase (standard curation expansion, NOT the
          B-12 amendment; the substitute fold must pass all 5 §4.2 criteria). Avoids any image change
          but loses the tree algorithm family + weakens §4.3 representativeness.
  - RESOLVED — human chose OPTION A (add C++ toolchain) with 5 binding conditions. Progress:
    * COND 1 DONE — Containerfile: appended ADDITIVE C++ layer (g++-13 + libstdc++-13-dev,
      =13.3.0-6ubuntu2~24.04.1, gcc-13-matched, appended LAST so C layers stay cache-identical).
      Rebuilt: X(:phase0)=3bbe69a1 -> X'(:phase1)=d45e33b0. apt "0 upgraded, 0 to remove, 3 newly
      installed". Re-pinned TOOLCHAIN.lock (image_tag->:phase1, [apt-pinned-cpp], image_id_1.1.1);
      transition recorded data/env/IMAGE_TRANSITION.md + logs/env/STEP_1.1.1_cpp_toolchain.log.
      NO RQ1/endpoint data predates X'. :phase0 (X) retained for Phase-0 repro.
    * COND 2 DONE — PROVEN byte-identical C binaries X vs X' (zero diff): cc1 5d167913, gcc-13
      1b998261, libasan.so.8.0.0 8d5845bd, python3.12 e1efa562 (match prior validation-auditor
      digests). cc1plus NEW (840b332f). check_toolchain.sh PASS 24 assertions zero-diff vs X'.
      Purpose confirmed: tree/_criterion now builds as C++ (was blocked in X).
    * COND 4 DONE — per-unit build sweep in X' (scripts/corpus/build_probe.sh): ALL 14 C-classified
      units BUILD-OK in isolation (sparsefuncs_fast, _isotonic, _cd_fast, _k_means_lloyd/_elkan,
      _barnes_hut_tsne, _binning, _predictor; scipy _shortest_path/_traversal/_min_spanning_tree,
      _bglu_dense, _group_columns, _ppoly). No n=1 generalization. C++ units 3/5 BUILD-OK (_criterion,
      _tree, _dbscan_inner); _splitter + _hierarchical_fast cythonize-FAIL (folds survive via
      siblings). The __check_build/scipy.__config__ ImportErrors are import-harness artifacts (compile
      OK). _bglu_dense.pyx EXISTS -> NO swap (human directive verified).
    * COND 5 DONE — full fold ledger: results/characterization/CORPUS_FOLD_LEDGER.md. 10 folds IN
      (manifold CONTINGENT on t-SNE determinism), 1 OUT (neighbors = Tempita .pyx.tp both versions).
      Zero margin -> recover an 11th fold at 1.1.2 (candidate sklearn.decomposition/_online_lda_fast,
      ordinary curation deviation NOT B-12). Unit ceiling: 17 .pyx BUILD-OK -> >=25 via within-
      codebase function-granularity expansion; §1.1.2 shortfall rule live if <25.
    * COND 3 IN PROGRESS (CRITICAL PATH — without the 3 C++ units folds=9<10) — mini-I-3 C++ extension.
      EVIDENCE GATHERED (logs/env/STEP_1.1.1_cpp_sanitizer.log; probe scripts/corpus/sanitizer/):
      - FOUND: a C++ throw aborts ASan under the Phase-0 runtime env ("CHECK real___cxa_throw != 0")
        — ASan-as-LD_PRELOAD into non-instrumented python can't bind __cxa_throw at init. SPECIFIC to
        C++ EXCEPTION UNWINDING (alloc path use_vector was fine).
      - FIX (runtime-env, NOT a suppression line): LD_PRELOAD libasan.so:libstdc++.so.6 -> operational
        run (detect_leaks=0) exit=0 CLEAN; leak-audit shows ONLY CPython teardown leaks (769B, already
        covered) — NO libstdc++ leak for the tested archetype.
      - ORACLE §3.1 C++ exception-identity CONFIRMED (deterministic Cython except+ map): std::out_of_range
        ->IndexError, std::length_error->RuntimeError, std::invalid_argument->ValueError. Oracle compares
        the TRANSLATED Python type -> works UNCHANGED on C++ units.
      HONEST NOTE: contra the anticipated mechanism, no new suppression-file LINES were needed; the
      enablement is a build-profile (g++-13 --cplus + same flags) + runtime-env (libstdc++ preload)
      change. Per-unit libstdc++ leak suppressions added later ONLY if a specific unit surfaces one.
      RIG AUDIT DONE (non-vacuous; human conditions 2+3; scripts/corpus/sanitizer/cpp_rig_probe.pyx
      + rig_audit.sh; logs/env/STEP_1.1.1_cpp_sanitizer.log [D]): (a) clean STL exit=0 no FP; (b)
      exception map confirmed; (c) NON-VACUITY — rig CATCHES heap-OOB (ASan), iterator-invalidation
      UAF (ASan), vptr/RTTI (UBSan); (d) LEAK POLICY resolved: detect_leaks=1 + lsan_cpython.supp ->
      clean unit 0 leaks, stl_leak() DETECTED. Production: feasibility gate keeps detect_leaks=0
      (Phase-0 invariant); a DEDICATED C++ leak-audit pass uses detect_leaks=1 + suppressions so STL
      leaks are actively caught (not only via §3.4 memory-cap kill).
      (i) DONE — src/motifbo/build/profiles.py: sanitizer_argv/performance_argv gained language="c"/"c++"
      (g++-13 + -std=c++14); sanitizer_runtime_env gained libstdcpp= (preload). TDD GREEN:
      test_build_profiles.py 20 passed (incl REAL C++ clean build + STL heap-OOB catch via profiles.py).
      (ii) DONE — test_oracle_cpp_exceptions.py 4 passed (real C++ unit -> translated exception -> oracle
      identity match / wrong-exception caught / subclass!=identity). POLICY DONE — SANITIZER_POLICY.md
      C++ section. (iv) DONE — validation-auditor PASS (agent ad6e5a529d3e834e2, stamp 873e9ddb3bf835fe):
      independently re-authored a throwing C++ unit to reproduce the __cxa_throw abort-without-preload /
      clean-with-preload; verified each non-vacuity catch is a genuine specific report (UBSan vptr, ASan
      freed-by/allocated-by); confirmed oracle test kills any isinstance-stub; lsan_cpython.supp unchanged
      (no speculative suppressions). Evidence results/audit/1.1.1-cond3/.
      (v) SIGNED — human (Panudet) signed the mini-I-3 C++ rig gate in-session, verbatim, scoped to the
      RIG (recorded results/preflight/MINI_I3_CPP_gate_pack.md; not self-signed). ALL 5 OPTION-A
      CONDITIONS DONE. C++ rig validated -> the building C++ units (tree _criterion/_tree, cluster
      _dbscan_inner) count at the RIG level; folds back to 10. (iii) per-unit C++ sanitizer-clean
      remains a CONTINUING obligation at 1.2/preflight (signer acknowledged). NEXT: CHECKPOINT-1
      fold-honesty (10-on-the-nose, manifold contingent) + vendoring into /data/corpus.
    Canonical Phase-1 image is now :phase1 (X'). All Phase-1 corpus build/run uses it.

step_1.1.1_vendoring (MECHANISM established on sparsefuncs_fast — human-ordered step 1):
  - LAYOUT (per-unit template): /data/corpus/<codebase>/<unit>/ holds closure/ (vendored cimport
    closure preserving the upstream package path so relative cimports resolve) + MANIFEST.md +
    CHECKLIST_4.2.md + build_from_closure.sh. sparsefuncs_fast is the reference exemplar.
  - sdists RE-FETCHED + sha256-VERIFIED vs the pins (prior /tmp/dl was transient, re-fetchable):
    scikit_learn-1.5.2 b4237ed7…  / scipy-1.13.1 095a87a0…  (both MATCH).
  - sparsefuncs_fast CLOSURE = 2 source files (sparsefuncs_fast.pyx + _typedefs.pxd) + 2 empty
    pkg-marker __init__.py stubs. _typedefs.pxd is PURE compile-time typedefs (no cimport/include/
    numpy-header, NO runtime .so to co-build) → genuinely low-coupling. Vendored-file sha256s MATCH
    the verified sdist (provenance proven).
  - VENDORED-CLOSURE BUILD-CONFIRM (the REAL §4.2-3 isolatability gate; stricter than build_probe.sh):
    compiles from the VENDORED CLOSURE ALONE in X′ — not the sdist root, not installed sklearn.
    POSITIVE: cythonize→gcc-13 -O3 -march=native -ffp-contract=fast -fopenmp→.so 790064 B→import OK
    (7 public callables). NEGATIVE CONTROL (non-vacuity): hide vendored _typedefs.pxd → cythonize
    FAILS → proves the build uses the vendored closure, not installed sklearn. EXIT=0.
    Raw: logs/corpus/STEP_1.1.1_vendor_sparsefuncs_fast_build.log.
  - HONESTY (human asked): the earlier "14 build-OK" was SDIST-ROOT-based (build_probe.sh does
    `cd /dl/<sdist>; cython -I .` → cimports resolve against ALL siblings in the full sdist tree),
    NOT vendored-closure-based and NOT installed-package-based. The vendored-closure build is the
    real isolatability gate and is now established + non-vacuous (negative control).
  - §4.2: 4/5 criteria PASS; criterion 5 (golden 50–500 ms) is PENDING-1.1.5 (measured under the
    timing rig with a raw pointer — no runtime number claimed at vendoring time). Provisionally
    admissible; sealed at 1.1.5. MANIFEST.md + CHECKLIST_4.2.md committed.

step_1.1.1_margin (human-ordered step 2 — secure ≥10 confident, aim 11):
  - 11th FOLD SECURED: sklearn.decomposition/_online_lda_fast (NEW fold, ordinary §4.2 curation, NOT
    B-12). Vendored-closure build PASS (281080 B) + DETERMINISM SMOKE PASS (mean_change +
    _dirichlet_expectation_2d bit-identical on repeat; no RNG, no prange — serial kernel) + negative
    control. MANIFEST + CHECKLIST committed. Same clean low-coupling profile as sparsefuncs_fast
    (only ..utils._typedefs). Raw: logs/corpus/STEP_1.1.1_vendor_online_lda_fast_build.log.
  - manifold/_barnes_hut_tsne DETERMINISM APPROACH established (for 1.1.3): drive gradient() at kernel
    level with a FIXED input embedding + FIXED val_P + a _QuadTree built from the fixed embedding,
    OMP_NUM_THREADS=1 (kills prange reduction non-determinism). t-SNE's randomness is the embedding
    INIT (random) — sidestepped by init='pca' OR by direct kernel driving with a fixed embedding.
    BUT manifold BUILD is blocked (see below) -> determinism PROOF deferred to 1.1.3 behind the build.
  - *** "BLOCKER" RESOLVED AT DIAGNOSIS — build-config, NOT a version break (debug-mantra) *** :
    - ROOT CAUSE: build-replication gap. I cythonized with the bare `cython -3` CLI and never passed
      sklearn's build-level directives. sklearn 1.5.2 (meson) builds with `-X cdivision=True` (+ wraparound/
      initializedcheck/nonecheck=False, boundscheck conditional) at the BUILD level (sklearn/meson.build:
      184-185; _build_utils/__init__.py:72-78), NOT in-source. Under default cdivision=False, `/` on C ints
      is Python true-division -> double -> "Invalid index type 'double'" (_splitter:580/659/1367; and the
      _utils `_realloc_test` `<size_t>(-1)/2` fused-method failure). NOT a Cython-3.2.5 defect.
    - PROVEN (logs/corpus/STEP_1.1.1_cdivision_rootcause_import_confirm.log): under faithful directives,
      _splitter + _utils CYTHONIZE-OK; the full tree cluster (_utils,_criterion,_splitter,_tree) + manifold
      chain (_quad_tree,_barnes_hut_tsne) BUILD and standalone-IMPORT-OK (with minimal pkg context:
      sklearn/utils/__init__ providing check_random_state, per _random.pyx:14). Version-break hypothesis
      FALSIFIED. _hierarchical_fast is SEPARATE (cimports Tempita metrics/_dist_metrics) — cluster survives
      via C _k_means; non-gate-critical.
    - RESOLUTION = branch (i): build-config + minimal pkg context. NO `/`->`//` patch (it would be WRONG:
      cdivision=False is genuinely INFEASIBLE for tree kernels; patching corrupts the §3.5 feasibility
      landscape), NO Cython downgrade, NO sklearn re-pin, NO fold drop. Tree fold + manifold RECOVERED at
      import level. Manifold remains contingent ONLY on the 1.1.3 t-SNE determinism proof.
    - DOC rewritten: results/characterization/CYTHON_3.2.5_COMPAT_BLOCKER.md ("resolved: build-config").
  - *** §2 Θ-DIRECTIVE POLICY — AWAITING HUMAN RATIFICATION (binds ALL units) *** :
    - The 5 Θ Cython directives (§2.3: boundscheck/wraparound/initializedcheck/nonecheck/cdivision; 2^5=32 ×
      54 GCC = |Θ|=1728/unit) interact with in-source directives. M1 (logs/corpus/
      STEP_1.1.1_theta_directive_scan.log): sklearn 13 units = ZERO in-source pins (matrix fully controls Θ);
      scipy 6/6 = function-level @cython decorators (_ppoly/_bglu_dense pin boundscheck+wraparound+cdivision;
      _min_spanning_tree/_group_columns pin boundscheck+wraparound; _shortest_path/_traversal pin boundscheck)
      -> those Θ dims go SILENTLY INERT (file/fn directive overrides -X) -> effective combos collapse 2^k
      (M2: _ppoly/_bglu_dense 4-of-32 = 8x dup; MST/_group_columns 4x; _shortest_path 2x).
    - DECISION (§2.3 Θ-operationalisation; HUMAN-RATIFIED; NOT B-12, NOT D-series): α HONOR in-source (non-
      uniform per-unit Θ, no source change, effective-directive cache key) vs β STRIP scipy decorators
      (uniform |Θ|=1728, documented directive-only source mod, author config still a Θ point). Lean β —
      results/characterization/THETA_DIRECTIVE_POLICY.md. NO policy applied until ratified.
  - BUILD-CONFIRM REDEFINED (§4, binds going forward): a unit counts only if it standalone-IMPORTS from its
    vendored closure (full cimport + runtime-import cascade) in X' — NOT merely cythonize+compile. The
    already-confirmed units (sparsefuncs_fast, _online_lda_fast) WERE import-confirmed; the 9 unblocked folds
    need import-level re-confirmation in the fan-out.

what_was_done:
  - "1.1.1 vendoring MECHANISM established on sklearn.utils/sparsefuncs_fast: vendored cimport
     closure → /data/corpus + MANIFEST + §4.2 checklist + build_from_closure.sh; vendored-closure
     build-confirm PASS in X′ with a non-vacuous negative control. Raw:
     logs/corpus/STEP_1.1.1_vendor_sparsefuncs_fast_build.log."
  - "1.1.1 margin: 11th fold decomposition/_online_lda_fast vendored + build-confirmed + determinism
     smoke PASS (logs/corpus/STEP_1.1.1_vendor_online_lda_fast_build.log)."
  - "1.1.1 margin/diagnose: the apparent 'Cython-3.2.5 blocker' was MISDIAGNOSED. debug-mantra root cause =
     build-replication gap (omitted sklearn's build-level -X cdivision=True). Under faithful directives the
     tree fold + manifold build AND standalone-IMPORT in X' (logs/corpus/
     STEP_1.1.1_cdivision_rootcause_import_confirm.log). NO version break / patch / downgrade / fold drop.
     Tree + manifold RECOVERED. Blocker doc rewritten 'resolved: build-config'."
  - "1.1.1 diagnose: exposed a §2.3 Θ-directive operationalisation decision (M1: sklearn clean, scipy 6/6
     pin boundscheck/wraparound/cdivision at function level -> matrix-inert dims). AWAITING HUMAN RATIFICATION
     of policy α (honor) vs β (strip) — results/characterization/THETA_DIRECTIVE_POLICY.md."
  - "1.1.1 fan-out (Workflow wf_fa221f3b-bf4 + inline): vendored + IMPORT-confirmed the remaining folds into
     /data/corpus under reference directives. Workflow did 7 sklearn units (isotonic, _cd_fast,
     _k_means_lloyd/elkan, _dbscan_inner, _binning, _predictor); 6 scipy subagents hit a session/quota cap
     (NOT technical) -> completed inline (csgraph _shortest_path/_traversal dotted-import; optimize
     _bglu_dense/_group_columns + interpolate _ppoly by-file w/ image cython_blas/lapack). Tree fold (3 units,
     shared cluster) + manifold materialized inline. ALL import_ok independently re-verified by re-running
     each build_from_closure.sh (IMPORT-OK + non-vacuous negative control). Per-unit MANIFEST + §4.2 CHECKLIST
     committed. Raw: logs/corpus/STEP_1.1.1_vendor_*_build.log. §4.1b >=10 MET (10 folds; 11 w/ manifold)."

raw_result_paths:
  - logs/corpus/STEP_1.1.1_vendor_sparsefuncs_fast_build.log     # vendored-closure build-confirm (X′)
  - logs/corpus/STEP_1.1.1_vendor_online_lda_fast_build.log      # 11th fold build + determinism smoke
  - logs/corpus/STEP_1.1.1_vendor_barnes_hut_tsne_build.log      # manifold deep-build probe (blocked)
  - logs/corpus/STEP_1.1.1_cython325_compat_blocker.log          # SUPERSEDED version-break analysis (breadcrumb)
  - logs/corpus/STEP_1.1.1_cdivision_rootcause_import_confirm.log # ROOT CAUSE + tree/manifold build+IMPORT-OK
  - logs/corpus/STEP_1.1.1_theta_directive_scan.log              # M1 in-source directive scan (§2 policy)

preregistrations: []   # none yet this phase (PREREG_RQ1 due at Step 1.5.1; PREREG for any 1.3 amendment)

audit_status:
  # Phase-1 auditor passes are recorded at their mandated steps (§6.5): measurement-auditor at
  # 1.2.4 (20% driver sample) + 1.5.5; bo-math-reviewer at 1.4.4; stats-auditor at 1.5.5 + every
  # preflight; validation-auditor at every preflight + on any I-3 anomaly. None due yet at 1.1.1.
  carried_from_phase0_close: E sweep fully green (validation a6df68143afb4d7c8, measurement
                             a9f2dd3bf1486a790, stats abdf868ee850767bd, bo-math n/a, scrutinize SHIP).

defects: [D3, D4]   # carried; no new defects at Phase-1 open

next_action: |
  IMMEDIATE (1.1.1 build-isolatability proof — human directive, the criterion-3 gate): from the
  pinned sdists, prove each candidate unit compiles in TRUE isolation in-container against
  numpy 2.4.6 + Cython 3.2.5 + gcc-13 with OMP_NUM_THREADS=1 + explicit -ffp-contract. START with
  sparsefuncs_fast (low-coupling; the Phase-0 csr origin), then the cimport-coupled units
  (_tree/_splitter/_criterion, _k_means_*). Procedure: extract the unit .pyx + walk its cimport/
  include closure (.pxd/.pxi), vendor the minimal closure, cythonize → cc → import-smoke. A unit
  that will not isolate-compile FAILS criterion 3 and is dropped (record it). KEY OPEN RISK:
  1.5.2/1.13.1 source vs the container's newer numpy 2.4.6 / Cython 3.2.5 — if a unit needs source
  patches to build, that patch is a documented vendoring fix (NOT the B-12 amendment) and must be
  recorded in the unit manifest.
  THEN: vendor the proven-admissible units → /data/corpus/<codebase>/<unit>/ + per-unit manifest
  (sdist sha256 pin + closure file list + the 5 §4.2 calls + chosen input scale targeting ~500ms)
  + committed §4.2 checklist. ENFORCE exclusions (Tempita .pyx.tp [neighbors OUT], scipy.special,
  golden outside 50-500ms). Then 1.1.2 (>=25 units across >=10 codebases — currently 10 folds /
  ~21-unit ceiling, so scout an 11th fold + within-codebase expansion; on shortfall pre-register
  reduced n + power consequence -> 1.5.2) -> 1.1.3 (per-unit oracle.json incl. the §3.1 tolerance-
  derivation, frozen+committed BEFORE any search — the gate the I-3 signature did NOT cover) ->
  1.1.4 (D1 smoke) -> 1.1.5 (golden + SHA-256). Build/run only inside the pinned container.

blocking: |
  NONE. §4.1b ≥10 gate MET at import level (10 folds, 11 w/ manifold). Open follow-ups (NOT blocking, next
  steps): (a) scipy csgraph _min_spanning_tree unit fix (import 'minimum_spanning_tree' not exported — csgraph
  fold already confirmed via _shortest_path+_traversal, so this is a unit-count item, manifest pending);
  (b) 1.1.2 reach >=25 units (function-granularity expansion within codebases; current ~17-18; shortfall rule
  if <25); (c) 1.1.3 oracle.json freeze + §3.1 tolerance-derivation TDD + manifold(t-SNE)/decomposition(LDA)
  determinism proofs (manifold fold membership hinges on it). Forward-binding: FR-1/FR-2 (1.4.x), FR-3/C-β2
  (1.2). CF-5 binds the C++ units (tree _tree/_criterion/_splitter, cluster _dbscan_inner) at 1.2/preflight.
```

NOTE: STATE lives under /results per roadmap §1.4.
