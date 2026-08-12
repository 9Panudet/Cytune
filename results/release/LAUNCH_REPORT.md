# LAUNCH_REPORT — cytune, the measurement pass before a public launch

**Status: LAUNCHED (v1.1.0, pushed and tagged by human authorization).
Closeout complete 2026-08-13 — see §6b. Prepared as v1.1.1; not pushed, not tagged.**

Released as **v1.1.0**, not v1.0.0: `v1.0.0` is already published against `0310bed`, and this
release **refuses runs that one certified** — a degenerate correctness oracle (D26) and a
calibration miss beyond the rig's resolution (D30). It is not the same product that tag names, so
the tag was not moved.

Governing pre-registration: `results/prereg/PREREG_LAUNCH.md`, committed (by sha256 pin) before any
replicate of the repeated campaign existed. Nothing here changes a study number, a frozen table, or
an audit verdict.

---

## 0. The one-paragraph version

The flagship accuracy number rested on **one live run**, and a rule that judged engine changes at
**1.0 percentage point per anchor**. Five repeated runs per arm now show the instrument's own
run-to-run spread is **6.711 pp** — the rule was **6.7× tighter than the thing it measured**. Under
the re-derived bound, `--probe-as-screen` passes every live rule handsomely: median regret
1.409 % → 0.802 %, worst anchor 9.791 % → 2.664 %, same cost, and *more* stable. It is still **not**
shipping as the default, because the new fleet-wide gate — the one built this pass — finds nine
kernels it regresses past 5 pp, one by 28 pp, **none of which is a live anchor**. That is the second
independent demonstration this pass that nine anchors are validation and not coverage.

---

## 1. A1 — the repeated dogfood

90 live runs: 9 anchors × 5 replicates × 2 arms, arms interleaved by replicate, fresh workspace
every run, rig re-verified before every replicate. 6.79 h of measurement. All 90 exited 0; all 10
rig verifications passed; all 90 workspaces pruned after their evidence was verified intact.

Raw: `results/release/dogfood_repeat/` (`CAMPAIGN.json`, `MANIFEST.jsonl`, `RIG_VERIFY.jsonl`,
`SCORED.json`, `REPEAT_REPORT.json`).
Recompute: `.venv/bin/python scripts/release/analyse_repeat.py`.
Commit under test: `5ebd592`, source tree sha256 `2de40eaf…` — identical across all 90 runs (L4).

### 1.1 Arm D — the shipped default

| anchor | median | min | max | **spread** | configs | distinct configs emitted |
|---|---:|---:|---:|---:|---:|---:|
| csr | 0.000 % | 0.000 % | 0.000 % | 0.000 pp | 33 | 1 |
| pava | 1.409 % | 1.409 % | 1.719 % | 0.310 pp | 33 | 2 |
| lda | 0.945 % | 0.945 % | 0.945 % | 0.000 pp | 33 | 1 |
| binning | 1.850 % | 1.850 % | 1.850 % | 0.000 pp | 49 | 1 |
| ppoly | 0.802 % | 0.777 % | 0.802 % | 0.024 pp | 33 | 2 |
| floyd | 5.404 % | 5.404 % | 5.404 % | 0.000 pp | 33 | 1 |
| cc | 0.793 % | 0.793 % | 0.793 % | 0.000 pp | 33 | 1 |
| **elkan** | 5.412 % | 5.412 % | 9.791 % | **4.379 pp** | 33 | 2 |
| **predictor** | 5.097 % | 1.500 % | 8.211 % | **6.711 pp** | 33 | **3** |

**Fleet headline, quoted as a range from here on:**
median-of-medians **1.409 %, range [1.409 %, 1.719 %]**;
worst anchor per replicate **range [5.412 %, 9.791 %]**;
**313 configurations measured**, identical in every replicate.

### 1.2 The shape of the noise, which matters more than the range

Five of nine anchors emitted the **same configuration in all five runs** — zero spread. The
dispersion is not a smear; it is concentrated in two anchors that flip between 2 and 3 distinct
configurations. Regret is discrete: it changes if and only if the search emits a different config.

This is why `PREREG_LAUNCH.md` §1 required the emitted-config multiset to be reported alongside the
range. "0–6.7 pp over three configs" and "0–6.7 pp over twenty" would print the same range and
describe different instruments.

### 1.3 Arm P — `--probe-as-screen`

median-of-medians **0.802 %, range [0.663 %, 0.957 %]**; worst anchor per replicate
**range [2.111 %, 2.664 %]**; **313 configurations** — the same cost.

Its per-anchor spreads are also smaller: elkan and ppoly and pava go to zero spread; the worst
spread in arm P is 0.884 pp against arm D's 6.711 pp.

---

## 2. A2 — the re-derived ship bound

By the formula fixed in `PREREG_LAUNCH.md` §3.1 before the data existed, computed on arm D only:

```
per-anchor spread s[a]:  median 0.000 pp,  worst S = 6.711 pp
fleet-median spread      S_fleet = 0.310 pp

B_anchor = max(S, 1.0 pp)      = 6.711 pp      (LOOSENED)
B_fleet  = max(S_fleet, 0.0)   = 0.310 pp      (new)
```

**The old bound was 6.7× tighter than the instrument.** A variant's fate under a 1.0 pp per-anchor
rule was decided by which configuration the search happened to land on, not by the variant.

The correction could only loosen — that direction was fixed in advance precisely so that a change
made after seeing results could not be mistaken for moving the goalposts.

### 2.1 What it changes about the six rejected DOE-v2 variants — **nothing**

| what | evidence it was judged on | re-judged? |
|---|---|---|
| V1–V6, SPLIT15, SPLIT24 (worst anchor +3.11 pp to +5.02 pp) | **offline** replay on the frozen R tables — deterministic | **No.** §3.2: offline comparisons keep their own exact arithmetic |
| the live SPLIT0 / `--probe-as-screen` confirmation, which failed §5.1c on `ppoly` at **+1.37 pp** | **live**, one run per anchor | **Yes.** 1.37 pp is far inside B_anchor = 6.711 pp. **That failure is withdrawn** |

So the DOE-v2 headline stands: **the six Tier-1 variants are still rejected**, on deterministic
offline evidence that the bound correction does not touch. What is withdrawn is the *live*
rejection of probe-as-screen — and it is replaced below by a better-founded one.

One honest consequence must be stated in both directions. An offline difference smaller than
**S = 6.711 pp** is a true difference in expectation that **a user cannot observe in one run**. That
applies to V1–V6's +3.11 pp regressions *and* to their median improvements. Determinism of the
simulator does not confer resolution on the prediction it makes about a live machine.

---

## 3. A3 — the `--probe-as-screen` decision

### 3.1 Live rules: PASS, decisively

| anchor | D median | P median | Δ |
|---|---:|---:|---:|
| csr | 0.000 % | 0.000 % | +0.000 pp |
| pava | 1.409 % | 1.246 % | −0.163 pp |
| lda | 0.945 % | 0.607 % | −0.337 pp |
| binning | 1.850 % | 2.175 % | **+0.325 pp** |
| ppoly | 0.802 % | 0.802 % | +0.000 pp |
| floyd | 5.404 % | 1.324 % | −4.081 pp |
| cc | 0.793 % | 0.793 % | +0.000 pp |
| elkan | 5.412 % | 0.320 % | −5.092 pp |
| predictor | 5.097 % | 1.522 % | −3.575 pp |

Fleet median of per-anchor medians **1.409 % → 0.802 % (−0.607 pp)**. Cost **313 → 313**.
Rule 4.1 PASS (the one regression, +0.325 pp, is inside B_anchor = 6.711 pp), 4.2 PASS.

### 3.2 Offline, all 149 frozen kernels × 9 budgets: it wins on the median almost everywhere

Median `regret_emittable`, all 149: routed 1.246 % → 0.167 %; B=8 1.576 % → 0.503 %;
B=16 1.811 % → 0.289 %; B=24 1.084 % → 0.075 %. Holdout-H median improves at 6 of 9 budgets.
Raw: `results/release/dogfood_repeat/A3_OFFLINE.txt`.
Recompute: `.venv/bin/python scripts/release/a3_offline.py`.

### 3.3 And the fleet gate fails it — on the tail, on kernels no anchor contains

**B1 verdict: FAIL.** 1 × F2 (worst-case) and 17 × F3 (per-cell), over **9 distinct kernels**:

| budget | kernel | D | P | Δ |
|---|---|---:|---:|---:|
| 8 | fleet_INT_20_int_sum64_r3 | 2.957 % | 31.621 % | **+28.664 pp** |
| 8 | fleet_INT_16_int_max32 | 3.345 % | 31.768 % | +28.423 pp |
| 8 | fleet_INT_14_int_min32 | 3.455 % | 31.820 % | +28.365 pp |
| routed/8/16/17/24 | fleet_INT_15_int_sumsq | 1.13–3.39 % | 27.633 % | +24.2 to +26.5 pp |
| 32/40/64 | fleet_MID_24_mid_gatherpoly_r2 | 4.244 % | 17.2–17.9 % | +13.0 to +13.6 pp |
| routed/24 | fleet_MID_30_mid_gatherpoly_r2 | 1.656 % | 9.976 % | +8.320 pp |
| 16 | fleet_MID_14_mid_branchy | 0.000 % | 7.114 % | +7.114 pp |
| 32/40 | fleet_MID_W2_202_mid_gatherpoly_r2 | 0.358 % | 5.633 % | +5.275 pp |
| 8 | fleet_MID_W2_52_mid_hist_r3 | 0.000 % | 5.164 % | +5.164 pp |
| **64** | *worst case over the fleet* | 5.913 % | **17.230 %** | +11.317 pp (F2) |

**Roles of the 9 harmed kernels: 8 training, 1 holdout-H, and 0 R-anchors.**

**Mechanism.** Without the second screen, the walk's main-effect fit is seeded by the 17-point
probe alone. On interaction-heavy `INT` landscapes and some `MID` gather kernels the probe alone
ranks the space wrongly, and the walk then follows that ranking to the bottom. The second screen's
extra design points are what rescue exactly those kernels — it is insurance against a tail, paid
for out of the median.

### 3.4 Decision

**`--probe-as-screen` stays OFF by default.** Rule §4.4 (no tail regression on the fleet) fails.
It remains implemented, tested, documented, and available as an opt-in flag.

The stated reason in `docs/USER_GUIDE.md` §13.7 and in `--help` has been **replaced**. It used to
say "measured better nearly everywhere, inside run-to-run noise". That is now known to be wrong on
both halves: the improvement is *larger* than run-to-run noise, and the reason to decline it is a
tail regression, not noise. The documentation says so in those terms.

---

## 4. The standing gates, and the defect class each closes

| gate | closes | proven non-vacuous by |
|---|---|---|
| **B1** fleet replay, 149 tables × 9 budgets, 9 s | "nine anchors are validation, not coverage" | D-2 reintroduced ⇒ **106 findings**, and **0 on an R anchor** |
| **B2** vendor manifest, 23 pins as data | "a check that never runs leaves no trace" — 12 of 14 items skipped forever on a product-only branch | on a product-only tree: **2 passing → 18 passing** |
| **B3** machine measurement lock | wrong numbers with no warning from concurrent runs (626 rows discarded, 2026-07-24) | two **real** concurrent `cytune tune` runs; the second refused (smoke step 5b) |
| **B4** path registry, 24 paths, 12 REQUIRED | "the unit is tested, the composition models fewer cases than production has" — D13, D14, D18, D-3 | mutation test: deleting any single mark is reported **by name** |

B1's positive control is the real D-2 defect rather than a planted one, so it also proves the gate
would have caught the defect the nine anchors missed. B4's construction forced the composition
sweep to grow fixtures for six paths it had never reached, including V-4-N — the branch shape that
let D-3 hide.

All four run in `scripts/release/smoke.sh` **step 0**, ahead of the live steps. On a branch without
the frozen tables B1 prints **NOT RUN** in yellow and says a gate that cannot run here has not
passed here.

### 4.1 D25, found during this pass

`scripts/cytune_e2e_composition_check.py` has been dead since the `_phasep` → `_vendor` rename: it
raised `ModuleNotFoundError` on import and had not run once. It is the host-side check for
D13/D14/D18 — the same class B4 defends — so **the instrument built to watch that class was itself
missing from every gate that claimed to include it.**

Fixed; it now runs in the pre-tag gate and its three red controls all fire. The general defence was
built rather than deferred: `tests/test_script_imports.py` statically checks every committed
script's `cytune.*` imports, 122 checks, with the real defect as its positive control. Running it
immediately found a bug in my own check (three scripts import a re-exported *function*, not a
module) — fixed before the file claimed to work. Post-mortem: `logs/defects/D25.md`.

---

## 5. The CLI

`tune` now runs doctor's own BLOCKING checks (`doctor.blocking_preflight`) before creating
anything, and fails with doctor's own fix line rather than a container spawn error three stages
later. A plain-language "WHAT TO DO" sentence (`certify.next_step`) prints above the certificate;
it is a pure function of the document, is not part of the rendered certificate, and is pinned by 11
tests — including that a memory-safety finding outranks a good speed result and suppresses the
number.

**Leanness, counted:** 4 commands · 27 flags · 10 config keys · 3 verdicts (+2 non-verdict exit
codes) · 23 invariants · 24 registered paths. **Nothing was cut** — every flag earned a sentence in
`USER_GUIDE.md` §13, and `test_every_flag_and_config_key_is_documented_here` fails if one does not.

---

## 5b. The tester campaign — five defects, four of them wrong-number class

Three of four agents reported (the fourth died on a session limit). **Five defects, four of which
produce a confident wrong answer rather than an error** — the directive's own definition of a launch
blocker. All five fixed; six further findings documented.

### D26 — the correctness oracle could not fail (beginner agent, 14 minutes)

`clip(double[::1] x, double lo, double hi)`, the first kernel the tester wrote. `cytune init`
scaffolds `1.0` for every float-ish scalar, so `lo == hi`, so the output is constant.

| driver | verdict | exit |
|---|---|---|
| exactly as `cytune init` wrote it | **IMPROVEMENT, 1.0790x** | 0 |
| one line fixed (`lo=-2.0, hi=2.0`) | HONEST-FLAT, 1.0000x | 2 |

`init` said `DRIVER CONTRACT: passes`; `doctor` said READY; the certificate said `rejected as
incorrect: 0 (0.0%)`; the gate was CLEAN; **`--apply` accepted it** and wrote a `boundscheck=False`
header into the user's source.

The proximate cause is one line of `init.py`. The real cause: **G1 had no positive control.** A
constant golden makes the comparison unfalsifiable, and `rejected as incorrect: 0 (0.0%)` is then
arithmetic printed where evidence goes. Fixed at both depths; validated live both ways.

### D27 — the gate's checks and its licence keyed on different fields (adversarial agent)

Every *check* on the sanitizer gate was conditioned on `gate["ran"]`; every *licence* on
`gate["clean"]`. A gate carrying `ran=False, clean=True` was checked by nothing and licensed by
everything. The adversary rendered `CLEAN — config 7 … ran with no report` on a certificate emitting
config 0, and then **reproduced D-3 exactly** — the reference emitted carrying the demoted
candidate's verdict, under the words "best safe choice".

Same family: `gate["authoritative"]` was written in three places and read in **none**, so the
warning `binding.py` embeds in the certificate — *"the 'safe' wording is withheld and --apply
refuses"* — was false in the same document that carried it. The test that appeared to cover it
asserted the flag was set and stopped.

Fixed by one predicate, `certify.gate_is_trustworthy`, used by all three consumers. 14 tests.

### D28, D29, D30 — the systematic breaker

Ten stability-matrix cells; two wrong numbers and one wrong verdict.

**D28** — after you edit your kernel and re-run into the same workspace, cytune reused the
*previous* kernel's calibration. `invalidate_stale_builds` writes the new module hash, and
`reusable_knob` runs afterwards and compares against the record that line just overwrote, so it
always matched. The narration contradicted itself eight lines apart: *"cache invalidated because the
module source changed"*, then *"reusing the calibrated REPS … module … unchanged"*. A user who asked
for 5 ms got 23.3 ms with `target_ms: 5.0` on the certificate. **This is the normal edit-then-retune
loop**, and the reference is the denominator of every speedup in the document.

**D30** — on a kernel whose single call is ~16 ns: `calibrated REPS: 1 → 1431 (reference ~5.0 ms)`
printed, and the same document measured the reference at **0.023 ms**, under `IMPROVEMENT 1.1709x`.
Now refuses below 1 ms and warns beyond 3×. Live: the breaker's kernel exits 1 with *"calibration
missed by 125x"* where it used to certify 1.17×.

**D29** — `doctor` returned `[ok]` for any image that exists, appending a digest mismatch to the
*label*. The `[ok]/[warn]` column is what a user scans, and the row that owns the pinning claim gave
the wrong answer on exactly the condition that makes results incomparable.

### D31, D32 — the senior power-user gate (D2)

Verdict: **adopt-with-caveats**. It read **zero lines of source** — docs, `--help` and `--json` were
sufficient — and scripted a working CI wrapper first try. Two defects, both fixed.

**D31 — the certificate said a flag the user typed was not typed.** With a `.cytune.toml` present
and `--allow-fp-contract` on the command line, the rendered consent block printed *"that opt-in did
NOT come from the command line you typed"* while the same document's JSON recorded
`allow_fp_contract: "command line"`. The guard tested the provenance of **both** FP flags, so a
config file merely *mentioning* `allow_fast_math` fired the note against a flag just typed.

That is a **G7 violation on the consent block** — the guarantee that a self-contradicting
certificate is never emitted, of exactly the precedent class G7 names (R2). It also cries wolf on
the one warning a reviewer is meant to trust.

**D32 — the documented directory-mode invocation crashed.** `cytune tune .` from inside a closure
module, with the default `.cytune` workspace, copytree'd the module directory into a workspace
inside itself: ~150 levels of `.cytune/_kernels/…` and `[Errno 36] File name too long`.
`USER_GUIDE` §2.1's own default was a trap.

**And `cytune init` was scaffolding the K-15 collision** into every new project — both `target_ms`
and `preset`, so editing one line to `preset = "quick"` silently discards the `target_ms` the user
wrote. It now writes one of them.

Two further findings are recorded as **K-18** (no `--min-speedup` / `--fail-on-thin`: a run can be
certified `IMPROVEMENT` at 1.0259× over a 1.0236× bar with 0.0107 % separation, and `thin` is in the
JSON but there is no flag) and **K-19** (the improvement path reports a *count* of policy-excluded
candidates without the best excluded ratio — which on the agent's kernel concealed a measured
**2.0036×** behind "7 excluded by policy"). K-19 is the D26/D28/D30 shape once more: the tool had
the number and did not report it.

### What held

Six attempts on the artifact binding layer, all blocked by named invariants. Concurrency (the second
run refused, naming the holder; eight subsequent runs serialised). Interruption at build and at
measure, then resume — both inside the clean band. Unicode and spaces throughout. Hostile
`.cytune.toml`, all rejected before the lock. A constant `canon()` refused (D26's fix, confirmed
independently). A non-deterministic `canon()` refused. And a planted monotonic time-drift lever
**defeated by per-sub-measure process isolation** — a real negative control passing.

### Documented rather than fixed

`docs/KNOWN_ISSUES.md` K-12 … K-17. The important one is **K-12**: C1's noise floor is a MAD
estimate over n=3 wall clocks **the driver's own process reported**, with no minimum-sample guard,
so a noisy driver inflates the budget, trips the no-power cutoff, and gets its claim certified with
`NOT CHECKED` beside it. Demonstrated: `IMPROVEMENT 2.000x` on a kernel whose true speedup was
1.000×.

**Not fixed because changing the C1 budget changes verdicts, and every number in this report was
measured with the current formula.** `docs/CONTRIBUTING.md` sets the bar for an engine change —
pre-registration, offline evaluation, the fleet gate — and this has not had it. What *was* fixed is
the false sentence: the attestation claimed C1 "catches ANY claimed speedup on a kernel that is
really flat", which the demonstration falsifies.

### What the campaign says about the 900-test suite

**Five defects in a few hours, by three agents with no stake in the answer, on a codebase that had
just passed 900 tests and gained four standing gates.** None was reachable by reading the code with
the intention of confirming it works.

Two are not even adversarial. D26 is what you reach by **using the tool normally on a kernel with
two bounds**. D28 is what you reach by **editing your kernel and running again**.

Three — D26, D28, D30 — share one shape, and it is the shape to watch for next: **the tool had both
numbers and never compared them.** The golden was in hand and nothing asked whether it could
discriminate. The module hash had just changed and nothing asked whether the calibration survived
it. The requested and achieved workloads were in the same document and nothing subtracted them.

## 5c. E — the branch split, prepared and verified

| branch | tracked files | suite, from a **fresh clone** | carries |
|---|---:|---|---|
| **main** | 109 | **753 passed, 16 skipped** | `src/cytune`, its test suite, six user docs, `evidence/` |
| **dev** | 695 | **907 passed, 31 skipped** | everything on main + `scripts/`, `tests/`, `logs/defects/`, `docs/system/` |
| **research** | 727 | **908 passed, 30 skipped** | everything on dev + 32 study documents |

`main`'s suite passing from a clone with no `scripts/`, no `tests/` and no `results/` is the first
**real** test of the one-way dependency rule; every previous check of it was simulated.

**Nothing is pushed.** The 149 frozen tables (215 MB) are deliberately **not** committed:
`FREEZE_MANIFEST_V2.json` pins every one by sha256, and committing 215 MB into a 3 MB `.git` is a
publishing decision that belongs to a human.

### Three defects in the split itself, found by verifying it

1. **Force-adding gitignored documents on `research` means switching back to `main` deletes them
   from the working tree.** `LAUNCH_REPORT.md` vanished mid-edit three times, including while this
   section was being written. `docs/system/15_BRANCH_HAZARD.md` documents it with the recovery
   command.
2. **Merging `main` into `dev` carried `main`'s reduction with it** — 590 files deleted from `dev`
   by a commit whose entire purpose was to remove them from `main`. The same hazard in a different
   costume, walked into within an hour of writing it down. Restored; the workflow rule is now
   explicit: **`main` is derived from `dev` by removal and must never be merged back.**
3. **Tests that pass on the full tree and fail from a clean clone** — the shipped example was
   documented only in `main`'s README; the vendor vacuity guard lumped the study *code* tree with
   the study *data* tree, failing on `dev` and, for the mirror reason, on `research`. All fixed.
   None was visible from a working tree that has everything, which is exactly why E5 asks for the
   clean-clone check.

## 6. What is NOT done, stated plainly

> **Three layers, labelled by time.** This section was written while D2, E, F and G were still
> outstanding; the table was then updated in place as each landed, and the prose above it was not.
> That left a paragraph saying the gate was **not met** directly above a table in which every row
> read DONE — **the P2/R2 defect class in a document**: two components each correct, disagreeing,
> with nothing whose job it was to notice. The layers are kept, because when a thing was true is
> part of the record. The prose is corrected.

**Layer 1 — written 2026-08-12, before D2 ran, kept verbatim:**

> This report covers sections A, B, C and part of H of the launch directive. The following are
> **incomplete**, and the launch gate is therefore **not met**.

**Layer 2 — 2026-08-12, at the launch.** Every section of the directive is DONE. **One cell inside
D3 was not run**, and it is in the table as NOT RUN rather than omitted; the gate was met with that
cell stated rather than closed.

**Layer 3 — 2026-08-13, the closeout.** That cell has now been half closed and half converted into
a written limitation. Nothing else in this table changed.

| item | status |
|---|---|
| **D1** beginner agent | **DONE.** Succeeded unaided, 3 min 35 s to first result. Found D26 |
| **D3** systematic breaker | **DONE.** 10 cells. Found D28, D29, D30 |
| **D4** hacker regression | **DONE.** 3 blockers claimed, 2 verified and fixed (D27), 3 documented |
| **D2** senior power user | **DONE.** Verdict adopt-with-caveats, zero source reads. Found D31, D32 |
| **D3 stability matrix**, Python 3.9–3.14 | **RUN 2026-08-13.** All six interpreters, 786 passed / 19 skipped / 0 failed, identical. Found **D33** |
| **D3 stability matrix**, rootless vs root podman | **NOT RUN, and now written down as such** — rootless is the only mode ever exercised. `KNOWN_ISSUES` **K-20** |
| **D3 stability matrix**, disk full | **NOT RUN, and now written down as such** — `KNOWN_ISSUES` **K-21** |
| **E** the three-branch split | **DONE** — see §5c |
| **F** the system documentation set | **DONE** — 16 documents |
| **G** the sales README on main | **DONE**, with a tracked `evidence/` beside it |

No claim in this report depends on the two remaining cells. They are stated limitations, not
caveats on anything above.

---

## 6b. The closeout — four named items, 2026-08-13

Released as **v1.1.1**. The four items were: mark 1.0.0 as known-defective (it is public and its
certificates can be wrong), make this report agree with itself, turn the tester pass into a standing
gate and sweep every guarantee for a positive control, and reconcile the untested matrix cells.

### 6b.1 The 1.0.0 advisory

1.0.0 is published and cannot be unpublished. **Six defects found after it shipped were already in
it, and four make it give a confident wrong answer rather than an error** — D26 (an oracle no build
could fail, ending in `--apply` writing `boundscheck=False` into user source), D28, D30, D29, plus
D27 and D31. `CHANGELOG.md` opens with the advisory and its 1.0.0 entry is marked in place and
otherwise left unedited. `certify.version_advisory` is the runtime half: a run that meets a ≤ 1.0.0
certificate in the workspace it is about to overwrite names the defects and tells the user to check
their source for a `# cython:` header they did not write.

### 6b.2 The G1–G7 control sweep — four missing controls, three on the oldest guarantees

The question, asked of each guarantee in turn: *does a deliberately wrong input make it fire?*

| | what was missing |
|---|---|
| **G1** | **not one test in the repository called `_vendor/measure_child._feasible`.** The correctness oracle had never been handed a wrong answer. Its evidence line named tests of the orchestration *around* it. That is exactly what D26 cost |
| **G2** | every sanitizer-gate test fed a hand-built verdict dict, so all of them would pass if `SAN_TOKENS` matched nothing a real sanitizer prints |
| **G5** | the whole-space subset sweep proved today's flags narrow; nothing proved the comparison would notice one that widened |
| **G6** | *"every number recomputes"* was enforced by **nothing**. The headline speedup was never checked against the endpoint medians four keys away in the same document. Now **invariant I1.11**. The `RAW:` line was also naming `table.jsonl` as the source of numbers that are not in it |

The sweep's table is now part of `docs/GUARANTEES.md`, and re-running it is a release step in
`docs/CONTRIBUTING.md` alongside the fresh-agent tester pass — whose justification is this pass's
own ratio: **four new standing gates found 0, 900 tests found 0, three strangers found 5 in an
afternoon**, two of them by using the tool normally.

### 6b.3 Two more defects, both found by running something on a branch it had not been run on

**D33** — `requires-python = ">=3.9"` covered six interpreters and one had ever executed this code.
Running the other five found a test that stubbed one of the *two* things it depended on and had
therefore been reading the developer's own image store for its entire life. `pytest -q src/cytune`
did not pass on a machine that had not built the toolchain — which is every machine a contributor
starts from.

**D34** — one root cause, found twice in an hour, in opposite directions. A checkout deletes the
tracked files a branch does not carry and **leaves the directory** when anything untracked is inside
it. Two gates asked "is the tree here?" by asking "does the directory exist?":

- **B1, the fleet gate, had not been running on `dev`** — both freeze artifacts were force-added on
  `research` only, so a checkout removed them and `smoke.sh` printed `NOT RUN`, on the branch its
  own message recommended, for the gate that exists because *nine anchors are validation and not
  coverage*. **Failed open.** Fixed; B1 then ran on `dev`: 149 kernels × 9 budgets, every cell
  byte-identical to baseline.
- **the vendor drift guard failed shut on `main`**, demanding ten study files that are not supposed
  to be on that branch, because `scripts/phasep/` survives as a shell holding a `__pycache__`.

The false failure was investigated in seconds. The false pass had been a yellow line in a wall of
green. That asymmetry is the finding.

### 6b.4 Gates re-run for the closeout

| | |
|---|---|
| live smoke gate | **PASSED**, with B1 green inside it for the first time on `dev` |
| B1 fleet replay | **PASS** — 149 × 9, every cell identical to the committed baseline |
| suites | `dev`/`research` **972 passed, 2 skipped**; `main` **792 passed, 13 skipped** |
| interpreter matrix | **786 passed, 19 skipped, 0 failed** on each of CPython 3.9.25 → 3.14.7 |

No study number, frozen table or audit verdict changed. The engine did not change — the fleet gate's
zero movement in every one of 9 × 149 cells is the evidence for that, not an assertion.

---

## 7. Recommendation

**Launched, with the caveats below stated rather than resolved.**

The gate condition — *the tester campaign leaves nothing unfixed-and-undocumented, and no claim on
main exceeds what main can prove* — is met: all four agents ran, and every finding is either fixed
with a failure-path test (D25–D32) or documented with its reason (K-12 … K-19). **What is
documented is not thereby harmless**, and K-12 in particular is a real hole shipped knowingly:
a driver whose reported wall clocks are noisy enough disarms C1's cross-check, demonstrated as a
certified `2.000x` on a kernel whose true speedup was 1.000×. It is not fixed because changing the
C1 budget changes verdicts and would invalidate every measured number in this report; the fix
belongs in a pre-registered engine change, not in a release scramble.

**Updated 2026-08-13, after the closeout (§6b).** The gate condition still holds, and two things
about it are now stronger than they were: the tester pass is a *standing* gate rather than a thing
that happened once, and every guarantee has been asked whether a wrong input makes it fire — four
answers were no, and those four controls now exist. K-12 is unchanged and still shipped knowingly.

*Everything below this line was written on 2026-08-12, before the decision to launch and before the
closeout. It is kept unedited. Where it names remaining work, that work has since been done — the
senior power-user agent ran (§5b, D31/D32) and the smoke gate was re-run twice — and the sentence is
left standing rather than quietly updated, because when a thing was true is part of the record.*

The original recommendation, kept because it was written before the decision and should not be
retrofitted:

The measurement work is done and it changed two things that matter: the flagship number now has a
measured range, and the rule used to judge engine changes was wrong by a factor of 6.7 and is now
derived from the instrument. The four standing gates are in, each with a control proving it can
fail.

Then the tester campaign found **five defects in a few hours**, four of which produce a confident
wrong answer, on a codebase that had just passed 900 tests and four new gates. Two of them are
reached by using the tool normally, not by attacking it.

That is not an argument against launching; it is an argument that **the tester campaign was the
missing gate**, and it has now run three quarters of the way. The remaining work is small and named:
run the senior power-user agent, and re-run the live smoke gate against the five fixes.

### What is ready to be relied on now

- the flagship number, as a range: **median regret 1.409 % (1.409–1.719 %), worst anchor 5.412 %
  (5.412–9.791 %), 313 configurations measured** — nine real-code kernels against exhaustively-known
  optima, one machine, five repetitions per arm;
- **`B_anchor` = 6.711 pp** as the per-anchor live bound, `B_fleet` = 0.310 pp;
- `--probe-as-screen` settled: **off by default**, for a measured tail reason;
- three branches cut and verified from a fresh clone, nothing pushed.

### The three things worth remembering from this pass

**Nine live anchors are validation, not coverage.** Demonstrated twice from opposite directions:
reintroducing D-2 produced 106 fleet findings with **none on an anchor**, and a change every live
anchor endorsed was refused by the fleet for regressions on kernels no anchor contains.

**A rule finer than the instrument is not conservative, it is arbitrary.** The 1.0 pp bound decided
the fate of six engine variants and was 6.7× tighter than the run-to-run spread it was judging them
against.

**The gates caught nothing new; the testers caught five things in an afternoon.** Every mechanism in
§4 was built to catch a class this project had already suffered, and each does. Every defect in §5b
was found by someone using or attacking the tool from outside. Both are worth having, and the ratio
is worth remembering when deciding where the next hour goes.
