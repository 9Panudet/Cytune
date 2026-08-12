# The defect ledger — what each one taught, and what now prevents it

*If you are taking this codebase over, this is the document to read. Every mechanism in cytune that
looks like paranoia is here, attached to the thing that made it necessary.*

Full post-mortems: `logs/defects/D<n>.md`. **The series starts at D3** — there are no D1/D2 files
on disk, and the ledger is D3–D25, twenty-three records. That gap is itself worth knowing, because
several documents in this repo's history said "D1–D12" and were wrong.

---

## The ledger

`prevented by` names the standing mechanism, or **NONE** where the fix was an instance fix.

| id | one line | found by | class | prevented by |
|---|---|---|---|---|
| **D3** | `import smac` died on a removed private sklearn symbol | environment pinning | dependency drift | pinned image + `check_python_env.sh` |
| **D4** | the rig died after the isolcpus reboot: hotplug-fragile thermal channels, governor EBUSY | a run that would not start | environment fragility | `measure_wrap.sh --verify-only`, run before every campaign |
| **D5** | floyd's "high" Δ was a CF-1 violation artifact — a build overlapping a measurement | a result that looked too good | **measurement contamination** | CF-1 phase split; **B3 measurement lock** (launch pass) |
| **D6** | the motif warm-start loop missed a seed refactor and called a stale `_propose` | a deferred gate | interface drift after a refactor | seed fixtures pinned byte-for-byte |
| **D7** | generator spec omitted `intended_class`; `finalize` crashed on fleet kernel #1 | the first real run | schema incompleteness | spec schema check |
| **D8** | the driver ignored the template's dtype; every float variant failed its call | the first float kernel | **untested variant path** | RUN-smoke on generated kernels |
| **D9** | the stencil template was out of bounds by construction | RUN-smoke upgrade | latent memory bug in test data | RUN-smoke functional calls |
| **D10** | the report counted ledger *entries*, not distinct slots — attrition inflated by relaunches | reading the report | **counting the wrong unit** | NONE (instance fix) |
| **D11** | the confirmatory FLAT family was counted as a bare class, not the FM-flagged cell | audit (F2 cell audit) | **counting the wrong unit** | cell definitions pinned in the prereg |
| **D12** | `/home` hit 100% mid-campaign; one ENOSPC-overlapped build discarded | the disk | resource exhaustion | prune policy; free-space floor in the runners |
| **D13** | the honest-flat route certified an "IMPROVEMENT" from a selection-biased probe minimum | reading a real run end to end | **composition dishonest, parts correct** | composition E2E check + **B4 path registry** |
| **D14** | "fast-math: not opted in" printed beside an emitted `-ffp-contract=fast` | reading a real run end to end | **composition dishonest, parts correct** | composition E2E check (D14 property) |
| **D15** | the emit threshold was a fixed 1.02, below the phantom-speedup floor of a min-over-B sample | `bo-math-reviewer`, finding F6 | **a threshold below the noise it filters** | margin = `max(2·CV, τ)`, every route |
| **D16** | `graphify_drain.sh` failed OPEN — "nothing owed" while a campaign was live | writing its own test | **a check that fails open** | fails closed; its own test |
| **D17** | build resume trusted the manifest alone; a pruned `_so` gave "built 17/17" then ImportError | a live run | **state trusted without verifying it** | build resume verifies artifacts exist |
| **D18** | the verify stage never built its own inputs, so a real 2× degraded to honest-flat | final transcript regeneration | **composition dishonest, parts correct** | composition E2E check (D18 property) |
| **D19** | the CF-1 busy predicate matched its own caller's command line, reporting BUSY on an idle box | pre-flight | **a predicate that matches itself** | ancestry exclusion; **B3 identifies holders by pid+starttime, never by name** |
| **D20** | a cycle killed during BUILD charged 0.0 s to a hard cap — the reconciler watched the wrong artifact | stopping a runner | **a meter that reads zero when the thing is not running** | scans build manifest + `_so` mtime; 4 tests, 2 verified RED |
| **D21** | the R transfer check compared two different metrics and manufactured a 2.41× alarm | investigating the alarm | **metric mismatch across versions** | NONE (instance fix; disproved by config-matched comparison) |
| **D22** | the report generator hardcoded a decision memo's threshold and cited it as the pre-registration | **`stats-auditor`, verdict FAIL** | **a number quoted from memory, not from the prereg** | statistics recomputed from raw by an independent auditor |
| **D23** | the §1.4 sanitizer gate **never ran**, and the oracle passed 1,296 configs that read out of bounds | a tripwire on a suspiciously large lever | **a check that never runs leaves no trace** | `run_study` REFUSES without the overlay; the gate runs on the emitted config in the product |
| **D24** | one of three demotion paths left the candidate's sanitizer verdict on a certificate emitting the reference | **the live dogfood**, under 674 green tests | **composition models fewer cases than production has** | **B4 path registry** — a REQUIRED path the sweep never reaches is now a test failure |
| **D25** | the composition-level E2E check had not run since the `_phasep` → `_vendor` rename | reading it while building B4 | **a check that never runs leaves no trace** | in `smoke.sh` step 0; `tests/test_script_imports.py` checks every script's `cytune.*` imports |

---

## The classes, counted

Twenty-three defects, six recurring shapes. The counts are what justify the mechanisms.

### 1. "Each part is correct and the composition is dishonest" — **4** (D13, D14, D18, D24)

The most expensive class in this project's history, and the most persistent. Every time, the units
had tests; every time, the thing that made the output wrong was how the units were *combined*.

D24 is the instructive one. `corroborate_ratio` had four unit tests including a power-curve sweep.
There *was* a composition sweep, and its docstring stated its purpose as "reproduce the CLI's
decision order". It modelled two of three demotion paths — and its fixtures carried no `wall_ns`,
so the third was unreachable **in principle**, not merely unwritten. A branch that cannot execute
is not coverage. A live run found it.

**Defence:** `src/cytune/paths.py` enumerates production's 24 verify/emit paths as data. The
composition mirror records which it reaches, and `test_the_composition_sweep_covers_every_required_
path` fails when a REQUIRED path was never exercised. Mutation-checked: deleting any single mark is
reported by name.

**What it does not cover, stated plainly:** nothing notices a path added to `cli.py` and not added
to the registry. That is still a human duty. The defence closes the second half of the failure.

### 2. "A check that never runs leaves no trace" — **3** (D16, D23, D25)

A failing check shouts. A check that fails *open* whispers. A check that never executes at all is
indistinguishable from a check that passed.

D23 is the largest single finding in the project: 149 kernels × 1,728 configs were gated on the
oracle alone, and 1,296 (kernel, config) cells were recorded FEASIBLE while executing an
out-of-bounds read. A reduction absorbs one garbage element without changing its output, so the
oracle passed them. The 13× lever that made three kernels interesting **was** the out-of-bounds
read.

D25 is the same shape at small scale and is worth more than its size: the instrument built to
defend class 1 had itself been silently absent since a rename.

**Defence:** the sanitizer gate runs on the config actually being emitted and *not-run is never a
pass*; the vendor manifest cannot skip; the composition check is inside the pre-tag gate; and every
committed script's `cytune.*` imports are checked statically.

### 3. "Counting the wrong unit" — **2** (D10, D11)

Both produced wrong headline statistics from correct raw data. Neither had a class defence beyond
pinning definitions in the pre-registration, which is the right defence: the unit is a *decision*,
so it belongs in the document that fixes decisions in advance.

### 4. "Measurement contamination" — **2** (D5, and the 2026-07-24 event that discarded 626 rows)

D5 was a build overlapping a measurement inside one campaign. The 2026-07-24 event was a 22-agent
workflow and an abandoned auditor container burning a core during a timed phase — and it is the
sharper lesson, because config id order correlates with the `-O1`/`-O3` factor, so a
time-correlated slowdown **can alias onto a factor** and look like a result.

**Defence:** CF-1 splits the phases; `measure_wrap.sh` refuses to measure on an unverified host;
and since the launch pass, `cytune/lock.py` takes a machine-wide lock for the whole of a run, so
two ordinary `cytune tune` invocations cannot interleave.

### 5. "A number quoted from memory rather than recomputed" — **1** (D22)

Found by an auditor, not by the author. That is the point of having one. The standing rule —
*statistics are recomputed from raw by `stats-auditor`, never hand-entered* — exists because of
this one defect.

### 6. Environment, resources, and interface drift — the remainder

D3, D4, D6, D7, D8, D9, D12, D17, D20, D21. Ordinary engineering defects, each with an ordinary
fix. They are in the ledger because the ledger is not a highlight reel.

---

## Four things the ledger says about this project that a reader should not have to infer

**Live runs find what test suites do not.** D24 was found by a live dogfood under 674 green tests.
D13, D14, D17 and D18 were all found by reading a real run end to end. This is why
`scripts/release/smoke.sh` exists and why it is not a pytest.

**The most valuable finding came from suspicion of a good result.** D23 started as a tripwire on a
lever that was larger than it should have been. The standing rule — *favourable surprises are
alarms; investigate before celebrating* — is not a slogan, it is what produced the largest
correction in the record.

**Auditors find things the author cannot.** D22 was found by `stats-auditor` after the author had
read the same report repeatedly. During the launch pass an independent audit corrected **three**
numbers in the DOE-v2 report, and all three made the conclusion weaker.

**Instance fixes are marked as instance fixes.** D10 and D21 carry **NONE** in the prevented-by
column. That is deliberate. A ledger that claimed a class defence for every entry would be a
worse document, and the honest gaps are where the next defect will come from.
