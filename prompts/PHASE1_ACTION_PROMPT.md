# MISSION

Build the Motif+BO autotuner **from an empty repository** through the full completion of
**Phase 0 (Instrument Validation & Tooling)** and **Phase 1 (Harder Corpus & RQ1 Gate)**, ending
with Phase 1 exit criteria satisfied per the roadmap.

`Motif+BO-Roadmap.md` is the spec and it is law. `CLAUDE.md` tells you how to work. On any
conflict between this prompt and the roadmap, **the roadmap wins**. Read the roadmap sections
on demand per the table in `CLAUDE.md` — do not paraphrase from memory; quote section numbers.

**Critical framing — read twice:** Phase 1 exit does NOT mean "BO beats RS." Phase 1 exit means
**the RQ1 decision is recorded honestly per §5.3 with auditor-verified zero-diff statistics,
and preflight is 100%.** An RQ1-negative result, recorded with the pre-registered decision tree
of Step 1.5.6 triggered correctly, is a **valid and complete Phase 1 exit** (roadmap: "this *is*
a valid exit"). You must never tune, re-run, p-hack, select seeds, or reframe criteria to force
a positive. §6.1 empirical-honesty mechanisms are binding at every step.

---

## HOST CONTEXT (Fedora Workstation 44 — adjust accordingly)

The host OS is **Fedora Workstation 44**, not Ubuntu. The *container* stays
`ubuntu:24.04@sha256:<digest>` per roadmap §1.3 — only host-side mechanics change:

- [ ] **Podman is native on Fedora.** Use rootless podman. Fedora uses cgroups v2 by default;
      verify rootless memory limits work: `podman run --rm --memory=512m ubuntu:24.04 cat /sys/fs/cgroup/memory.max`
      must show the limit. If delegation is missing, document the fix (systemd user delegation)
      in `/data/env/HOST_NOTES.md`.
- [ ] **SELinux is enforcing.** Every bind mount gets a `:Z` label (private) — e.g.
      `-v ./data:/data:Z`. Never disable SELinux; record labels used in `/data/env/HOST_NOTES.md`.
- [ ] **Turbo/governor control requires host root** (Step 0.2.1):
      - Disable turbo: `echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo`
      - Performance governor: `sudo cpupower frequency-set -g performance` (package: `kernel-tools`)
      - These do not survive reboot — the wrapper script must **verify state at every invocation**
        and refuse to run if `no_turbo != 1` (roadmap Step 0.2.1 check). Provide a
        `scripts/host_prep.sh` the human runs with sudo; the orchestrator itself never assumes it ran.
- [ ] **CPU pinning:** pass `--cpuset-cpus` to podman for the measurement container
      (core 3 isolated; SMT sibling of core 3 idle — on i3-10100F with 4C/8T, identify the sibling
      via `/sys/devices/system/cpu/cpu3/topology/thread_siblings_list` and exclude it from all
      other cpusets). Record the mapping in `/logs/governor/CPU_MAP.md`.
- [ ] **Thermal monitoring:** read `/sys/class/thermal/` or `coretemp` hwmon from the host side
      (package: `lm_sensors`); log to `/logs/governor/thermal/`.
- [ ] **tmpfs `/sandbox` (2 GB):** mount inside the container (`--tmpfs /sandbox:size=2g`);
      it counts against the 12 GB ceiling (§3.4).
- [ ] **ASan + CPython** inside the container: candidate runs need
      `LD_PRELOAD=$(gcc -print-file-name=libasan.so)` and `ASAN_OPTIONS=detect_leaks=0` (CPython
      leaks by design); every suppression line gets a written justification (Step 0.4.1).

---

## OPERATING RULES (non-negotiable, from CLAUDE.md + roadmap §6)

1. **Session start:** read `STATE_<PHASE>.md`; do exactly the named next Step, nothing else.
   Update STATE (schema §6.4) at every Step boundary. If STATE does not exist yet, the next
   Step is 0.1.1.
2. **Red gate ⇒ `debug-mantra` first** (reproduce → trace the fail path → falsify the hypothesis
   → cross-reference every breadcrumb) — in order, before any fix. After a validated fix:
   `post-mortem` → `/logs/defects/D<n>.md` before the Step closes.
3. **Raw before aggregate:** every measurement → `/results/**`, committed, before any number is
   quoted anywhere. Statistics recomputed only by `stats-auditor` from raw files. A number
   without a raw-file pointer does not exist.
4. **Pre-register before comparing:** `/results/prereg/PREREG_*.md` committed before any
   comparison run.
5. **Scoped TDD (§6.3):** red–green–refactor for the oracle (§3), timing-region placement
   (0.2.2), BO/acquisition math (§2.2), RS sampler, statistics code. Infrastructure gets
   smoke/golden tests. No vacuous tests.
6. **Minimum code per Step.** Unclear ⇒ stop and ask the human; never pick an interpretation
   silently. State assumptions before implementing.
7. **All builds and candidate runs happen inside the pinned container.** Never on the Fedora host.
8. **`-ffp-contract` is always passed explicitly** on every build (GCC default is `fast`, §0.7-1).
9. **Single-amendment rule (Appendix B-12):** exactly one pre-registered corpus/space amendment
   exists for the whole project (Step 1.3.3 / 1.5.6). Spending it is recorded in STATE.
10. **Tooling map (§6.7):** `graphify query` for codebase questions (not grep);
    `scrutinize` at every preflight; auditor subagents read-only on `/src`.

---

## PHASE 0 CHECKLIST — Instrument Validation & Tooling

Goal: pinned, isolated, sanitizer-backed instrument passing **I-1**, a reliable **I-3** oracle,
characterized timing variance. No corpus search in Phase 0.

### 0.1 Container & toolchain pinning
- [ ] **0.1.1** `Containerfile` from `ubuntu:24.04`; pull once, record the **digest**; rebuild
      bit-identically from digest. Artifacts: `Containerfile`, `/data/env/IMAGE_DIGEST`.
- [ ] **0.1.2** Pin GCC 13.x via apt version pin inside the image → `TOOLCHAIN.lock` +
      committed `gcc -v` output; CI asserts version match.
- [ ] **0.1.3** Pin Python 3.12.x, Cython 3.x, SMAC3 2.x **including which RF backend is active
      (pyrfr vs sklearn — record it explicitly)**, all deps → hash-pinned `requirements.lock`;
      preflight asserts lockfile hash.
- [ ] **0.1.4** Scaffold `/data /src /sandbox /logs /results`; `git init`; pre-commit hook
      rejecting loose root files; test the hook with a deliberate violation.
- [ ] **0.1.5** Inside the pinned container, verify against the pinned GCC's own manual +
      `gcc -Q --help=optimizers`: `-ffast-math` sub-flag composition, `__FAST_MATH__`,
      `-Ofast` composition **and its deprecation status (this resolves §0.7 item 9 — record the
      finding)**, `-ffp-contract` default → `/data/env/GCC_SEMANTICS.md`.
      **Empirical MXCSR probe:** compile a fast-math `.so`, read the MXCSR control word before/
      after `dlopen` in a probe process, commit the evidence (grounds §3.2(2) FTZ/DAZ rule).
- [ ] **0.1.6** Initialize `STATE_PHASE0.md` (§6.4 schema). Commit the four auditor-subagent
      definitions (`validation-auditor`, `bo-math-reviewer`, `stats-auditor`,
      `measurement-auditor`; mandates per §6.5, `/src` read-only to them). One `scrutinize`
      review of the definitions.
- [ ] **0.1.7** Install agent tooling, pinned in `TOOLCHAIN.lock`:
      `uv tool install graphifyy==<ver>`; `graphify install`; `/graphify .` (commit
      `graphify-out/`); `graphify hook install`; `npx skills add thananon/9arm-skills`
      (pin commit hash). Check: `graphify query` answers a smoke question; hook regenerates
      the graph on a test commit.

### 0.2 Measurement rig
- [ ] **0.2.1** Governor/turbo control + logging (`/logs/governor/`); taskset/cpuset wrapper for
      core 3; thermal monitor. **Wrapper refuses to run if `no_turbo != 1`.** (Fedora host notes
      above apply.)
- [ ] **0.2.2** RUNTIME_NS harness — `time.perf_counter_ns` immediately around the kernel call
      only; candidate module loaded in a **fresh subprocess** (§3.2(2)). **TDD:** sleep-kernel
      fixture, measured ≈ slept ± tolerance; a deliberately mis-placed timing region must fail.
- [ ] **0.2.3** perf cycle-count cross-check path (10% subsample); divergence-report format defined.
- [ ] **0.2.4** **Pilot variance study** on the two 0.5 reference kernels, K_pilot = 30 →
      `/results/pilot/` (median, IQR, MAD). Set **K_final** so bootstrap 95% CI half-width of
      the median ≤ 1% of median; set the thermal-discard threshold. Commit both as constants.
- [ ] **0.2.5** `measurement-auditor` review of all rig evidence → pass recorded in STATE.

### 0.3 Tiered oracle (TDD throughout)
- [ ] **0.3.1** `oracle.json` schema: output classes (correctness-critical / numerically-
      approximate), tolerances (atol/rtol | ULP), expected exception types → schema + validator.
- [ ] **0.3.2** Bitwise comparator (bytes + dtype + shape + **exception identity**) — red-green-refactor.
- [ ] **0.3.3** Tolerance comparator (atol/rtol and ULP modes) — red-green-refactor incl.
      NaN/Inf policy tests.
- [ ] **0.3.4** cdivision edge-suite generator (negative operands, zero divisors) — tests assert
      the Python-vs-C semantic divergence is **caught** by the oracle (a missed divergence is a
      failing test).
- [ ] **0.3.5** `validation-auditor` review → pass recorded.

### 0.4 Sanitizer & containment rig
- [ ] **0.4.1** Build profiles: performance = `-g0 -pipe` + explicit `-ffp-contract`; ASan+UBSan
      profile keeps `-g`. CPython suppression file committed with **line-by-line justification**;
      reviewed by `validation-auditor`.
- [ ] **0.4.2** Known-good build runs the full validation input set **clean** (zero reports) →
      log committed (Phase 0 exit evidence).
- [ ] **0.4.3** Containment wrapper: run timeout = max(10× golden median, 5 s); compile timeout
      120 s; 4 GB cgroup cap; `--network=none`; tmpfs (2 GB) `/sandbox` wiped per candidate.
      Smoke fixtures (deliberate OOM / timeout / segfault) are caught and labeled per §3.5 —
      the orchestrator never crashes.

### 0.5 I-1 calibration (real workloads only — guards D2)
- [ ] **0.5.1** Two reference kernels with real hot-loop drivers per §4.4 + the input-scaling D2
      check: (a) raw-pointer path — CSR scaling loop; (b) numeric-loop path — PAVA-style loop.
- [ ] **0.5.2** Known-good (`boundscheck=False, wraparound=False, cdivision=True, -O3,
      march=native, contract=fast`) vs known-bad (all checks on, `-O1`, baseline march) at
      **K_final**, paired inputs.
- [ ] **0.5.3** **Gate I-1:** raw-pointer ≥ 1.15×, numeric-loop ≥ 1.5×. Fail ⇒ `debug-mantra`;
      presume the instrument wrong until proven otherwise.

### 0.P Preflight (§6.6) — all five items at 100% + `scrutinize`
- [ ] Digest/hash validation (image digest, `TOOLCHAIN.lock`, `requirements.lock`, golden hashes,
      input manifests).
- [ ] Memory profiling: peak RSS (orchestrator + worst candidate + tmpfs) < 12 GB ceiling.
- [ ] Sanitizer-clean confirmation on the known-good build.
- [ ] Raw-data presence: every claimed result resolves to a committed raw file.
- [ ] `scrutinize` completed; all four auditors pass (or n/a with written justification).

**Phase 0 exit (all required):** I-1 pass with stated margins · I-3 oracle suite green + manual
validation gate signed in STATE · ASan/UBSan clean on known-good · pilot report committed with
K_final + thermal threshold set · preflight 100%.

---

## PHASE 1 CHECKLIST — Harder Corpus & RQ1 Gate

### 1.1 Corpus curation (§4)
- [ ] **1.1.1** Apply the five §4.2 admissibility criteria to the §4.3 inventory (sklearn/scipy
      `.pyx` units). Pin upstream commits; vendor sources → `/data/corpus/<codebase>/<unit>/`
      + manifest. Per-unit criteria checklist committed. Exclusions enforced: Tempita `.pyx.tp`,
      `scipy.special`, golden runtime outside 50–500 ms.
- [ ] **1.1.2** Reach **≥ 25 units across ≥ 10 codebases** by adding admissible kernels within
      the listed codebases. On shortfall: pre-register reduced n + its power consequence
      (feeds 1.5.2). Do not pad with inadmissible units.
- [ ] **1.1.3** Per-unit `oracle.json` incl. the tolerance-setting procedure of §3.1
      (tolerance = max(10× observed cross-repetition deviation under reference config,
      domain-justified floor)) — **frozen and committed before any search**.
- [ ] **1.1.4** Early D1 smoke per unit: the reference build's Cython translation must succeed;
      any front-end failure flags the unit immediately. Commit one
      `graphify export callflow-html` at Phase-1 preflight (documentation role only).
- [ ] **1.1.5** Golden outputs + SHA-256 hashes under the reference config; input manifests
      hashed and committed.

### 1.2 Hot-loop drivers (guards D2)
- [ ] **1.2.1** Profile every unit (cProfile + perf): **≥ 90% of driver wall time inside the
      target kernel**; evidence committed per unit.
- [ ] **1.2.2** RUNTIME_NS driver per unit (§4.4): timing immediately around the kernel call;
      input construction outside the timed region; fresh subprocess; **no bare imports timed, ever**.
- [ ] **1.2.3** Input-scaling D2 regression test in CI for **every** driver: declared complexity
      band per unit (e.g. O(n log n) at n→2n ⇒ ratio ∈ [1.8, 2.6]); violation = red gate ⇒
      `debug-mantra`.
- [ ] **1.2.4** `measurement-auditor` pass on a 20% random driver sample.

### 1.3 Landscape characterization (non-flatness, §4.1c)
- [ ] **1.3.1** Fixed 16-config probe set, **pre-registered** (factorial screen: all-safe-on /
      all-checks-off+O3+native / fast-math poles / contract poles).
- [ ] **1.3.2** Δ(unit) = t_worst/t_best per unit. **Admission: corpus median Δ ≥ 1.5 AND
      ≥ 70% of units with Δ ≥ 1.2.**
- [ ] **1.3.3** On fail only: the **single permitted pre-registered amendment** — extended flag
      space (§2.3 escalation, curated by the `gcc -Q --help=optimizers -O2` vs `-O3` diff
      procedure) **or** corpus revision; re-run 1.3 **once**. No second amendment exists.
- [ ] **1.3.4** Characterization report (per-unit Δ, oracle-class mix, probe timings) →
      `/results/characterization/`.

### 1.4 Optimizer implementations (TDD on the math)
- [ ] **1.4.1** RS baseline: uniform **without replacement** per seed over Θ including the
      `ffp_contract` conditional (active only when `fast_math=off`; |Θ| = 1,728). Determinism
      test: same seed ⇒ same sequence.
- [ ] **1.4.2** SMAC3-RF + EIC per §2.1–2.2, unit-tested against **hand-computed fixtures**
      (red-green) for each of: EI algebra, log-transform of runtimes, **σ-floor 10⁻³ log-units**,
      feasibility weighting with **add-one Laplace smoothing**, conditional-parameter handling,
      μ/σ from feasible observations only, infeasible runtimes never imputed into the regressor,
      1-in-4 random interleave, the 8-config initial design (all-defaults / expert / known-bad /
      5 seeded uniform).
- [ ] **1.4.3** Memoized evaluation table + replay layer (§1.5 item 2): each unique (unit, config)
      evaluated once (compile → I-3 → adaptive K_search ∈ [5,10] with early stop at CI half-width
      ≤ 2% of median); deterministic replay across seeds/methods. Cython-translation cache keyed
      by (source-hash, directive set, Cython version) — 32 combos/unit. Sanitizer verdicts
      memoized per **safety class** (6-dim key, §3.3) with the endpoint full-config guard wired
      in. Trajectory determinism test required.
- [ ] **1.4.4** `bo-math-reviewer` pass.

### 1.5 RQ1 experiment
- [ ] **1.5.1** `PREREG_RQ1.md` committed **before the run**: endpoint per §5.3; B = 60 proposals
      (both methods, infeasible evaluations charged to both); seeds ≥ 20; tests + α = 0.05;
      memoized-table/replay design incl. the K_search/K_final two-tier rule; fairness rule.
- [ ] **1.5.2** Power simulation (n ∈ {20, 25}, δ ∈ {0.2, 0.4, 0.6}, pilot variance):
      requirement power ≥ 0.8 at the pre-registered MDE — else expand units (back to 1.1.2)
      **before** running.
- [ ] **1.5.3** Run both methods; raw per-evaluation records → `/results/rq1/raw/`, committed
      continuously (compile log, sanitizer log, oracle diff, timing vector per §3.5).
- [ ] **1.5.4** Fresh **K_final = 30** re-measurement of every per-(unit, method) winner on
      paired inputs → endpoint statistics per §5.3. Headline numbers never rest on cached
      search-phase timings.
- [ ] **1.5.5** `stats-auditor` + `measurement-auditor` independent recomputation from raw —
      **required diff: exactly zero.**
- [ ] **1.5.6** **Decision per the pre-registered tree — record it verbatim in STATE:**
      - PASS (all three: one-sided paired Wilcoxon p < 0.05 BO-better AND Cliff's δ > 0 AND
        BCa 95% CI of median paired difference excludes zero) → Phase 2 unlocked.
      - FAIL → record the negative as valid data; Motif layer stays disabled; then
        (a) if 1.3 evidence indicates flatness as cause AND the single amendment is unspent →
        exercise it and re-run Phase 1 **once**; otherwise (b) terminate search phases —
        Phase 4 reporting-only mode + Phase 5 ships `motifbo validate`/`characterize`.
        **No silent second attempts.**

### 1.P Preflight (§6.6, all five items) + `scrutinize`.

**PHASE 1 EXIT — definition of done (all required):**
- [ ] RQ1 decision recorded per §5.3 with **auditor-verified, zero-diff statistics**
      (Wilcoxon + Cliff's δ + BCa CI, ≥ 20 seeds, paired, fresh K_final endpoints).
- [ ] If RQ1-negative: the negative result + the triggered 1.5.6 branch are committed —
      **this is a valid exit, treat it as success of the process.**
- [ ] Every reported number carries a raw-file pointer + exact recomputation command.
- [ ] Preflight 100%; `scrutinize` complete; STATE_PHASE1.md closed with `next_action` set
      (Phase 2 if positive; Step-1.5.6 branch otherwise).

---

## EXECUTION DISCIPLINE

- Work strictly in Step order; one Step per unit of work; STATE updated at every boundary.
  This is a multi-session project — assume any session may be your last and leave STATE
  good enough for a cold-start successor.
- Estimated compute (roadmap §1.5, rebased): ≈ 3–4 days wall-clock pipelined for the RQ1 run
  (2 compile workers on cores 0–1 + isolated measurement core 3). Long runs must be resumable:
  the memoized table and continuous raw commits are the checkpoint mechanism.
- Pre-registered reduction levers if the envelope is exceeded: B = 40 (≈ −35%), unit count.
  **Seeds ≥ 20 and K_final = 30 are never levers.**
- Ask the human before: spending the single amendment; any deviation from a pinned constant;
  anything requiring host root (turbo/governor); any interpretation ambiguity in the roadmap.

Begin now at **Step 0.1.1**. State your assumptions for 0.1.1 first, then implement.
