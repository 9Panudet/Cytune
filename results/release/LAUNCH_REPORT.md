# LAUNCH_REPORT — cytune, the measurement pass before a public launch

**Status: STOP FOR THE HUMAN.** Nothing is pushed. Nothing is tagged.

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

## 6. What is NOT done, stated plainly

This report covers sections A, B, C and part of H of the launch directive. The following are
**incomplete**, and the launch gate is therefore **not met**:

| item | status |
|---|---|
| **D1–D4** the tester campaign (beginner, senior power user, systematic breaker, hacker regression) | **NOT RUN.** The agent budget for this session was exhausted (weekly limit) partway through the first scouting fan-out. Three of eight scouts died and were replaced by direct inspection |
| **D3 stability matrix** — concurrency, interruption/resume, disk full, read-only workspace, unicode paths, Python 3.9–3.14, rootless vs root podman, image absent/mismatched, clock changes | **NOT RUN**, except *concurrency*, which is now covered live by smoke step 5b |
| **E** the three-branch split | **NOT DONE** |
| **F** the system documentation set | **PARTIAL** — `00_SUMMARY`, `01_REPO_MAP`, `02_PIPELINE`, `12_HISTORY` written; 11 documents outstanding |
| **G** the sales README on main | **NOT WRITTEN** |

No claim in this report depends on any of them. They are the remaining work, not caveats on what is
above.

---

## 7. Recommendation

**Do not launch yet.** The measurement work is done and it changed two things that matter: the
flagship number now has a measured range, and the rule used to judge engine changes was wrong by a
factor of 6.7 and is now derived from the instrument. The four standing gates are in and each is
demonstrably able to fail.

But the directive's launch gate requires the tester campaign to leave nothing unfixed-and-
undocumented, and the tester campaign has not run. Section 6 is the honest list.

**What is ready to be relied on now:**

- the flagship number, as a range: **median regret 1.409 % (range 1.409–1.719 %), worst anchor
  5.412 % (range 5.412–9.791 %), 313 configurations measured**, on nine real-code kernels against
  exhaustively-known optima, one machine, five repetitions per arm;
- `B_anchor = 6.711 pp` as the per-anchor live bound, and `B_fleet = 0.310 pp`;
- `--probe-as-screen` settled: **off by default**, for a documented, measured tail reason.

**The single most important thing this pass produced** is not a number. It is that the same claim —
*nine live anchors are validation, not coverage* — was demonstrated twice from opposite directions:
once by reintroducing D-2 and watching 106 findings appear with none on an anchor, and once by a
change that every live anchor endorsed and the fleet refused.
