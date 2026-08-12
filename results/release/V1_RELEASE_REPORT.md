# cytune 1.0.0 — release report

**STOP. This is for the human. The release is not tagged.**

What this pass did: made the product ship standalone, institutionalised the one defect class this
project kept rediscovering, turned the biggest stated limitation into a capability, froze the public
API, and then tried to break the result — first against ground truth, then with three adversaries.

Everything below is measured. Where something was not measured, it says so.

---

## 1. Architecture — before and after

### The dependency rule (A2)

`src/cytune/**` may not import study, replay or benchmark code. Before this pass it did the
opposite: `_phasep.py` inserted `scripts/phasep` onto `sys.path`, and the package imported `theta`,
`campaign`, `classify`, `algorithms` and `sanitizer_spot_audit` from the study tree. `rig.py`
mounted `scripts/` **and** `results/` into every measurement container.

| | before | after |
|---|---|---|
| study modules imported by the package | 5 | **0** |
| container mounts | 4 (`/probe`, `/src`, `/results`, `/work`) | **2** (package read-only, workspace) |
| dependency violations | — | **0** |
| does it run with no `scripts/` and no `results/`? | no | **yes, proven by execution** |

The load-bearing test is not an assertion. `test_the_package_imports_with_no_study_tree_on_sys_path`
launches a subprocess whose `sys.path` cannot reach the study tree and imports every product module.
A static scan can be defeated by a lazy import or a `sys.path` insert; an execution cannot.

`test_cytune_architecture.py` — 69 tests: static import scan (including imports inside function
bodies), string-literal path scan, the execution proof, the two mount checks, and the reachability
walk. Positive controls included: a planted `import replay` must be caught, a dead module must come
out unreachable, and the walk must follow `plan.py`'s function-local `import algorithms`.

### Leanness (A3), measured

|  | files | LOC |
|---|---:|---:|
| **before** — in-package product | 15 | 3,298 |
| **before** — borrowed from `scripts/` at runtime* | 11 | 1,914 |
| **before** — effective total | 26 | 5,212 |
| **after** — own product modules | 19 | 4,949 |
| **after** — vendored + pinned | 11 | 1,295 |
| **after** — product total, all in-package | 30 | **6,244** |
| tests | 8 → 16 | 1,760 → **3,708** |

\* imported at runtime from `scripts/phasep`, invisible in the package's own LOC count, and
unavailable to anyone who installed only the package.

**The honest reading: the product did not get smaller.** It grew by ~1,000 lines of new capability
(`audit`, `coherence`, `invariants`, `schema`) and absorbed 1,295 lines it was already using but not
counting. What changed is that its real size is now visible and every line of it is reachable from a
CLI entry point — enforced by `test_every_product_module_is_reachable_from_an_entry_point`, which
found `examples/` shipped but undocumented and 619 lines of study-only code that was **not** vendored
because nothing reaches it.

The vendored files are trimmed to what the product actually calls (`campaign.py` 356 → 210 lines,
`algorithms.py` 137 → 55) and pinned two ways: whole-file sha256 for the seven copied verbatim,
per-function source-text comparison for the three trimmed. Drift in either direction fails
`test_cytune_vendor.py`, and `test_the_drift_check_is_not_vacuously_skipping` fails if the study
tree is present but nothing got compared.

### One test moved out of the package, and it was silently vacuous

`test_cytune_plan.py` verifies that cytune's DOE reproduces `algorithms.doe`'s trajectory exactly.
It imports study code, so it moved to `tests/`. Moving it exposed a real problem: `cytune/_vendor/`
ships a file called `algorithms.py` and puts itself at `sys.path[0]`, so a plain `import algorithms`
in that directory resolves to **cytune's own copy** — the test would have asserted that cytune
agrees with cytune, and passed forever while the two drifted arbitrarily far apart.

The study modules are now loaded by file path under distinct names, and
`test_the_study_modules_are_not_the_vendored_ones` asserts they really came from `scripts/phasep`.

---

## 2. The invariant registry

`cytune/invariants.py`. Every entry: a stable id, the function that enforces it, where it runs in
production, and the test that makes it fire. `test_cytune_invariants.py` fails if an entry's test
does not exist, if `coherence.py` raises an id with no entry, or if an entry is registered but never
raised.

| id | guarantees | enforced in | test that fires it |
|---|---|---|---|
| `I1.1` | verdict, exit code and rendered VERDICT line agree | cli.tune, before writing | `test_verdict_and_exit_code_must_agree` |
| `I1.2` | the directives and flags PRINTED are those of the emitted config id (**P2**) | cli.tune, before writing | `test_p2_emit_block_must_match_the_emitted_config` |
| `I1.3` | FP fields agree with the emitted flag string, incl. fast-math implying contraction (**R2**), neither exceeding policy (G4) | via coherence | `test_r2_fp_fields_must_agree_with_the_emitted_flag_string` |
| `I1.4` | `sanitizer_gate` describes the config actually emitted (**F5**) | cli.tune, before writing | `test_f5_the_gate_must_describe_the_emitted_config` |
| `I1.5` | a not-run gate qualifies the summary and sets the machine-readable flag (**P4**) | cli.tune, before writing | `test_p4_a_not_run_gate_must_qualify_the_verdict_line` |
| `I1.6` | no wording asserts safety unless the gate came back CLEAN (**P1**) | via coherence | `test_p1_safety_wording_cannot_survive_a_reporting_gate` |
| `I1.7` | anything not an improvement emits the user's own reference | cli.tune, before writing | `test_a_non_improvement_must_emit_the_reference` |
| `I1.8` | a speedup prints only for an improvement; an improvement never has a reporting gate (G2) | cli.tune, before writing | `test_an_improvement_verdict_cannot_have_a_reporting_gate` |
| `I1.9` | the document honours its own published JSON schema | via coherence | `test_i1_9_a_certificate_violating_its_own_schema_is_refused` |
| `I2.1` | a non-clearing candidate is demoted before certification, or the build refuses (**P2 at its source**) | certify.build_certificate | `test_b2_a_non_clearing_winner_is_refused_at_its_source` |
| `I2.2` | a reporting candidate is refused and replaced before certification (G2) | certify.build_certificate | `test_a_reporting_candidate_cannot_be_certified_without_a_rejection` |
| `I2.3` | a rejected winner has been replaced by the reference | certify.build_certificate | `test_a_rejected_winner_must_be_replaced_before_certification` |
| `I2.4` | "safe" is downgraded unless the gate cleared | certify.build_certificate | `test_b2_the_invariant_holds_over_every_generated_run_outcome` |
| `I2.5` | `--apply` refuses anything not an improvement gated CLEAN | apply.check_applicable | `test_apply_refuses_when_the_gate_did_not_run` |
| `I3.1` | a changed module or image invalidates builds AND their timings | cli.tune, before first build | `test_a_changed_module_discards_builds_and_measurements` |
| `I3.2` | a changed driver, workload, rig mode or oracle invalidates timings (**R4**) | cli.tune, after golden | `test_a_changed_rig_mode_discards_measurements_but_keeps_builds` |
| `I3.3` | discarded measurements are archived, never destroyed | cli.tune, on invalidation | `test_discarded_measurements_are_archived_not_destroyed` |
| `I3.4` | `certificate.json` re-renders to `certificate.txt` byte-for-byte | cli.tune, step 6 | `test_b4_a_certificate_rerenders_byte_for_byte_from_its_json` |

### What the coherence work found

Writing the invariant found **three live defects**, two of them by the property sweep rather than by
inspection:

1. **`build_certificate` would still assemble a P2-shaped certificate.** The CLI demotes a
   non-clearing winner before certifying (that was P2's fix), but nothing enforced it. The B2 sweep
   over (gate state × policy × winner × speed) hit the state directly: `EMIT: the reference
   configuration (unchanged)` above config 1506's directives. Now raises at its source (I2.1).
2. **The EMIT line and three summaries asserted "the best safe choice" under a gate that had not
   run.** The same document withdrew the claim two paragraphs later. Found by I1.6's sweep; the
   wording is now downgraded in one place (I2.4) rather than at six sites.
3. **A reporting non-reference config could reach the certificate** without a recorded rejection,
   where the EMIT-NOTHING block would call it "what you already have" — true only of the reference.
   Now refused (I2.2).

A fourth was a defect in the invariant itself: the safety-wording check matched the substring
`certified safe` inside the sentence **"it is NOT certified safe"** — flagging the line written to
prevent the very defect it was flagging. The check now judges each occurrence against a negation
window.

### Cache-key completeness (B3)

The key covered calibration only. Everything else that can change what a measurement *means* was
missing — most seriously the module source itself: **editing your kernel and re-running reused the
previous kernel's `.so` and its timings**, because `campaign.build_all` resumes on "a config with a
manifest row is done".

Two keys now, because the artifacts have different dependencies. Builds depend on the module source
and the toolchain image; timings additionally on the driver, the calibrated workload, `--target-ms`,
the rig mode and the oracle. Ten fields, each with a test that moves it, and
`test_the_key_covers_every_field_the_module_declares` fails if a field is added without one.

Policy flags are **deliberately excluded**, with the reason recorded at the definition site: they
change what is *selected*, not what a measurement *yields*, and invalidating on them would discard
valid timings to assert a dependency that does not exist.

**Verified live.** A kernel was tuned, edited to do 3× the work, and re-run into the same workspace:

```
cache invalidated because the module source changed — discarding 33 cached build(s)
and 33 measurement row(s)
(everything is recompiled from the module as it is now)
```

Run 1 emitted config 588 at 4.395×; run 2 emitted config **804** at 3.694×. Different code,
different answer. Identical results would have meant stale reuse.

---

## 3. `cytune audit` — K6 from limitation to capability

`tune` gates two configurations out of 1,728: the search's best candidate and the config it emits.
That is enough to guarantee it never *emits* something unsafe (G2), and not enough to reliably
*find* a latent bug — measured at **3 of 5** runs on the same out-of-bounds fixture, because the DOE
walk's winner varied.

`audit` removes the search from the loop: no tuning, no timing, no rig requirement. It gates a
pre-registered set of eight configurations and reports, per directive, whether disabling it is safe
for this kernel.

### Detection rate

| | detection | determinism |
|---|---|---|
| `cytune tune` | **3 of 5** | verdict varied between runs (`no-safe-improvement` ×3, `honest-flat` ×2) |
| `cytune audit` | **6 of 6** | byte-identical verdict structure across all six runs (one sha256) |

Five runs on the pre-final code plus one re-verification on the released build after the renderer
changed (U1/T8). All six produce the identical verdict structure `ab518413336a4c83`.
Archived: `results/release/audit_runs/` — six workspaces, six logs, `EXITS.txt`.

### The design decision that made it work

The obvious risk set — the reference plus each directive flipped singly — **would have missed D23**,
the defect the feature exists to catch. Live output from the fixture:

```
[CLEAN   ] boundscheck_off  (config 1152)
[RAISED  ] wraparound_off   (config 720)
[REPORTED] boundscheck_and_wraparound_off  (config 1584)
            >>> AddressSanitizer, SUMMARY: AddressSanitizer, buffer-overflow
```

With `boundscheck=False` but `wraparound=True`, `a[-1]` is rewritten to `a[n-1]` — in bounds, legal,
clean. With `wraparound=False` but `boundscheck=True`, Cython raises before the read happens. Only
the **pair** reads before the buffer. `test_the_risk_set_contains_the_d23_pair` pins it.

Running it also improved the report: `RUN_FAIL_NO_TOKEN` was being displayed as "NOT RUN", which
hid the most useful thing the audit had learned — that with `boundscheck` on, Cython *caught* the
bad index. It is now a distinct `RAISED` outcome that counts as evidence the directive is unsafe to
disable, while genuinely-unchecked rows still never read as safety.

---

## 4. Ground-truth dogfood — nine real library modules

Nobody had ever checked cytune's answer against a known optimum. The data existed: the nine
Dataset-R anchors are modules from scipy and scikit-learn whose full 1,728-configuration tables were
measured exhaustively by the Phase-P study.

**This required a product change to be possible at all.** All nine are multi-file closures — real
library code `cimport`s its siblings — and cytune's ingest accepted only a lone `.pyx`. So the
product could not be pointed at the very code the study measured. That is a finding the dogfood
produced before it produced a single number.

### Method

Regret is computed **entirely inside the frozen table**, at one measurement tier:

```
regret = table_time(cytune's emitted config) / table_time(best allowed config) − 1
```

"Allowed" means feasible in the frozen table **and** permitted by cytune's default FP-strict policy
— comparing against an optimum cytune was forbidden from choosing would measure the policy, not the
search. cytune re-calibrated each anchor to its own 65 ms target, so its absolute times are not
comparable with the study's; a ratio taken inside the frozen table is.

### Results

| anchor | verdict | emitted | rank | **regret** | headroom available | headroom captured | configs | wall |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `csr` (sparsefuncs_fast) | improvement | 1392 | **1** | **+0.00%** | +98.76% | +98.76% | 33 | 11m35s |
| `pava` (_isotonic) | improvement | 1383 | 12 | +1.41% | +9.85% | +8.32% | 33 | 4m31s |
| `lda` (_online_lda_fast) | improvement | 1392 | 5 | +0.94% | +9.36% | +8.33% | 33 | 3m59s |
| `binning` (_binning) | improvement | 198 | 11 | +1.85% | +5.71% | +3.79% | 49 | 6m33s |
| `ppoly` (_ppoly) | improvement | 1392 | 27 | +0.80% | +6.65% | +5.80% | 33 | 5m30s |
| `floyd` (_shortest_path) | improvement | 786 | 79 | +5.40% | +39.99% | +32.81% | 33 | 5m07s |
| `cc` (_traversal) | improvement | 1371 | 25 | +0.79% | +22.12% | +21.16% | 33 | 6m53s |
| `elkan` (_k_means_elkan) | improvement | 1389 | 28 | **+5.41%** | +62.58% | +54.23% | 33 | 16m48s |
| `predictor` (_predictor) | improvement | 1398 | 5 | +5.10% | +38.51% | +31.79% | 33 | 7m15s |

**n=9 · median regret +1.41% · worst +5.41% · every emitted config sanitizer-CLEAN · 33–49 of 1,728
configurations measured (~2%).**

Raw: `results/release/dogfood/REGRET.json`, nine certificates under
`results/release/dogfood/runs/`, method in `scripts/release/analyse_dogfood.py`.

### Caveats, stated rather than buried

- **The regret figures are over-estimates.** The denominator is a screen-tier sample minimum over
  ~1,150 configurations and is therefore biased low. The direction of the bias understates cytune;
  it is reported this way because that is the conservative direction, not because it flatters.
- **Nine kernels from two libraries is not a general claim.** These anchors were selected by the
  study as real-code anchors; they are not a random sample of Cython code.
- **Three of them (`pava`, `binning`, `ppoly`) the study classed FLAT.** cytune returned
  `improvement` on all three, with captured gains of 3.8–8.3%. That is not a contradiction: the
  study's FLAT boundary is Δ<1.10 and these sit at it (two carry the `delta_strict~1.10` boundary
  flag in their own class records). But it is worth stating that on the kernels closest to the flat
  boundary, cytune is claiming small gains, and small gains are where a tuner is most likely to be
  wrong.
- **`csr`'s +98.76% headroom is the study's number, not a claim about sklearn.** It is what the
  frozen table says about this kernel at this scale under this driver.

---

## 5. The public API, frozen

| | |
|---|---|
| `cytune-certificate/1.0` | `tune --json`, `certificate.json` |
| `cytune-dry-run/1.0` | `tune --dry-run --json` |
| `cytune-audit/1.0` | `audit --json`, `audit.json` |
| `cytune-doctor/1.0` | `doctor --json` |

Machine-readable specs in `src/cytune/schema.py`, human-readable promise in
`docs/COMPATIBILITY.md`. The validator is hand-written and dependency-free — the host side declares
`dependencies = []`, and that property is worth more than the convenience of `jsonschema`.

**The schema is checked against real output, not fixtures.** `I1.9` validates every certificate
against its own published contract before it is written, so emitter and schema cannot drift; and
`test_every_archived_certificate_from_a_released_build_validates` validates all nine dogfood
certificates. Archived documents from *pre-release* builds are partitioned out and counted rather
than silently skipped.

Exit codes: `0` improvement · `1` error · `2` honest-flat · `3` no-safe-improvement. A usage error
returns `1`, tested against the real parser so it cannot collide with honest-flat (P3). `audit`
shares the scheme (`0` clean, `3` defects found, `1` could not complete).

Version single-sourced from `cytune.__version__`, asserted identical across the banner, `--version`,
`doctor` and every artifact. **`pyproject.toml` was found carrying a second version** (`1.0.0rc1`
against the package's `1.0.0`) — F7 reappearing at the packaging layer — and now derives it.

"research preview" **stays**. The version freezes the interface; it does not claim the underpowered
study became complete.

---

## 6. What was deliberately not built

- **`--resume`.** cytune already resumes: the table and manifest persist and are validated against a
  complete cache key, so an interrupted run continues by being run again. A flag would have been a
  second name for the default. What was added instead is *visibility* — the run says which cached
  work it reused and which it discarded, and why.
- **`measure_wrap.sh` as package data.** Tried, and it broke the quiesced rig: the script resolves a
  sibling `scripts/thermal_log.sh` through `REPO_ROOT="$(dirname $0)/.."`, so the package copy died
  with rc=127 mid-run instead of degrading. **Caught by a live run, not by a test** — reverted, and
  the reason is recorded at the definition site. This was scope creep on my part; A2 never asked for
  it.
- A `--no-sanitizer` escape hatch, certified `--objective size/compile`, and a router that picks
  between algorithms. Reasons in `docs/CONTRIBUTING.md`.

---

## 7. Test suite

| | before this pass | after |
|---|---:|---:|
| tests | 180 | **447** |
| test LOC | 1,760 | 3,708 |
| test modules | 8 | 16 |

`446 passed, 1 skipped` (the skip is a pilot-table fast-math case with nothing to exclude).

New suites: `test_cytune_architecture.py` (69), `test_cytune_coherence.py` (26),
`test_cytune_audit.py` (21), `test_cytune_api.py` (23), `test_cytune_cache.py` (21),
`test_cytune_invariants.py` (57), `test_cytune_vendor.py` (16), `test_cytune_ux.py` (14).

---

## 8. Self-review before the campaign

`scrutinize` was run against this pass's own work, per the project's rule that it precedes any
report leaving the repo. It found three things by tracing claims rather than trusting them.

**S1 (fixed) — I1.3 did not check `--portable-flags`.** The invariant's registry entry says
"neither exceeds the policy", but the implementation re-derived only the two floating-point axes.
Demonstrated directly: a certificate emitting `-march=native` under
`EmissionPolicy(portable_flags=True)` was **accepted**. The check now asks the `EmissionPolicy`
object itself, so every axis is covered — including any added later, without anyone remembering to
extend the function. `test_i1_3_catches_a_config_outside_portable_flags`, plus a control asserting
`-march=native` is still fine when portability was not requested.

**S2 (fixed) — only one of the four public artifacts was validated at runtime.** `I1.9` guarded
`certificate.json`; the dry-run and audit documents are equally part of the compatibility promise
and were checked only by hand-written fixtures, so their emitters could drift from the schema
freely. Both now validate before emitting, and
`test_the_cli_actually_calls_the_dry_run_validator` guards the wiring rather than just the
function — a validator nobody calls is decoration.

**S3 (documented, not fixed) — the safety-wording check uses a 40-character negation window.**
`_affirms` decides whether text *asserts* "best safe choice" or denies it, by looking back 40
characters for a negation. This is a heuristic over prose. Measured: `"It is NOT certified safe"`
is correctly read as a denial, and `"This is not a recommendation. The reference is the best safe
choice."` is correctly read as an affirmation (the negation falls outside the window) — but that
outcome depends on distance, and a sentence could be constructed that evades it. It is a
belt-and-braces check over wording, backed by the structural checks I1.7/I1.8/I2.4 which do not
depend on prose at all. Recorded here rather than hardened, because the honest fix is to keep
safety claims out of generated prose, which I2.4 now does at the source.

---

## 9. Adversarial campaign

**One methodological caveat, stated first.** The three agents ran concurrently, and this host's
measurement rig isolates a single core. Up to five `cytune` processes were timing on it at once,
so any agent finding about *timing* — a verdict flipping between runs, a margin that seemed wide —
is confounded by contention and should not be read as a property of cytune. Findings about
behaviour, messages, exit codes, refusals and documentation are unaffected.

Three fresh agents, no memory of this work, run in parallel. Full reports in
[`agents/`](agents/).

| agent | scope | verdict |
|---|---|---|
| **USER** (novice, docs + `--help` only) | install, tune two of its own kernels, preset, `--apply`, read a certificate | **QUALIFIED** — time-to-first-result **1.7 min, 0 guesses**; 18 findings, no blockers |
| **TESTER** (systematic, docs + CLI) | ~60 cases: 24 error paths, 9 config, 9 driver-contract, cache, repeatability, 5 full tunes | **"Refusal machinery is strong; input validation at the edges is not."** 2 BLOCKERs, 6 major |
| **HACKER** (white-box, objective: force a false certificate) | 14 attacks | **FALSE CERTIFICATE PRODUCED: YES — 3 of them.** Release blocker |

### The three false certificates

**H12 — an ordinary `# cython:` header silently defeated the whole directive search. No adversary
required.** In Cython the file header overrides `-X`, and `-X` is how the builder applies every
configuration in Θ. **I reproduced this independently before accepting it**: with a header naming
`boundscheck`, `cython -X boundscheck=True` and `-X boundscheck=False` produce **byte-identical C**.
So all 32 directive combinations compile the same, the search times 33 configurations that cannot
differ, and the certificate describes directives that were never applied — including calling config
288 "Cython's safe defaults" when it was built with the checks off. The coherence gate could not see
it: I1 verifies the document against the config id, and the config id was never what got built.

The README had warned against this for two releases. **A warning did not stop it.**

*Fixed:* refused at ingest, naming the offending line (`session.check_pinned_directives`, 16 tests).
Headers naming directives cytune does not vary (`language_level`, `cpow`) are left alone — verified
in the pinned image that they do not disable `-X`. **The dogfood was re-checked against this: eight
of nine anchors carry no header, `ppoly` carries `# cython: cpow=True`, and none is affected. §4
stands.**

**H1 — the driver owns the clock.** `_vendor/measure_child.py` `exec_module`s the driver into the
very process that calls `perf_counter_ns()` around it, computes the median, and prints the JSON the
host parses. A twelve-line driver replaced the clock and cytune certified `IMPROVEMENT`,
`5.0000x`, separation confirmed, sanitizer CLEAN, exit 0 — on a kernel where no configuration is
faster than any other.

**My SECURITY.md said the opposite**: *"There is no shared interpreter to patch."* That was false.

*Fixed as far as it can be:* the claim is corrected and the limit is now stated in SECURITY.md and
GUARANTEES N8. Partial mitigation added — the parent times the whole child, so `K × median`
exceeding the elapsed wall is time that did not happen and is flagged, with no false positives. The
**under**-claim direction is indistinguishable from spawn overhead and is **not** detected. Users are
told not to treat a certificate as attesting a speedup to a third party who does not trust the
driver.

**H6 — `CYTUNE_SANITIZER_IMAGE` manufactured `clean: true`.** A stub image whose `python3` echoes
one JSON line turned a kernel whose real gate returns `SANITIZER_REPORT` into a clean pass under the
words "the best safe choice". **GUARANTEES claimed this was impossible, citing a test that asserted
on hand-written dictionaries and never pointed the override at an image.**

*Fixed:* a clean result from an unpinned image is no longer treated as a pass — the certificate
records the image, the "safe" wording is withheld, `--apply` refuses, and invariant I1.6 enforces it.
The override still exercises the not-run path and still cannot suppress a report.

### The two TESTER blockers

**T1 — a build failure shipped no compiler diagnostic.** Two documents promise "the compiler's own
words"; the tool printed `cythonize_fail (cached)` and a 79-byte "full build log" containing that
same string. Root cause: `_cythonize_synth` *does* save the compiler output to `<c_path>.FAIL`, but
returns only the reason on a cached failure and nothing read the file back. **The named proof test
stubbed the build result, so it never saw a real cythonize failure.** *Fixed and verified live* — the
error now arrives with the caret and the line number.

**T2 — the driver contract could be satisfied by a comment.** `if "OUTPUT_CLASS" not in src` is a
substring search, so `# TODO: set OUTPUT_CLASS` passed. The run then proceeded with no output class
and the oracle fell back to `float` — the **tolerance** mode — silently costing an integer kernel the
bit-exact sha256 oracle G1 promises it. `def make_inputs` in a comment *was* rejected, so one
contract was held to two standards. *Fixed:* the driver is parsed, not scanned; the value is
validated too (T3: `OUTPUT_CLASS = "banana"` used to reach the certificate).

### Everything else fixed in response

| id | finding | fix |
|---|---|---|
| U1 (MAJOR) | every CLEAN audit row was also stamped `NOT CHECKED (CLEAN). Not-run is not a pass.` — the feature that sells determinism contradicted itself eight times per report | the `else` branch caught `OK`; now outcome-specific, with a test that asserts the report does not contradict itself |
| U2 (MAJOR) | two docs stated the emit margin as `0.0200` "on a quiesced rig" — a user measured **0.2196** | corrected: the margin is computed from the noise *this run* measured, never a property of the rig mode |
| U3 (MAJOR) | separation reported as a bare yes; a 74 µs gap (0.2%, a tenth of tau) read like a 40% one | the magnitude is reported, and a gap below tau is labelled **THIN** |
| U4 (MAJOR) | escalation ran to the 5-sub-measure cap and ended at CV 0.1097 — twice its target — silently | `escalation` block; the certificate says the target was not met and what that means |
| U5 (MAJOR) | `--target-ms 30` produced a 49 ms reference, unflagged | calibration is a one-point linear extrapolation and now says so when it lands far off |
| U14 | the audit's directive table omitted `nonecheck` with no explanation | stated: already off at the reference, so there is no "disable" direction to audit |
| T4 (MAJOR) | `--target-ms -5` accepted; certificate signed for a `REPS=1` workload | rejected, with sub-millisecond targets too |
| T5 (MAJOR) | malformed/unreadable `.cytune.toml` printed raw tracebacks | every failure becomes a `ConfigError` |
| T7 (MAJOR) | unknown config KEYS were errors but invalid enum VALUES were silently ignored | rejected — the same defect the key check exists to prevent |
| T8 (MAJOR) | RAISED rows were all annotated "with boundscheck ON…", including checks-off corners | the explanation now matches the row |
| U8, U9, U16, U17, U18 | no `.pyx` example in the docs; the driver-contract error pointed at a page with no template; `docs/README.md` listed 5 of 8 documents; an image-ID mismatch had no stated consequence; the test command missed `tests/` | all corrected |

**U6/U7 (`--preset`, `--explain`, `audit` missing from USER_GUIDE) were closed mid-run** by an edit
made while the agents were working. That is documented drift, not a fix earned by the report: the
TESTER snapshotted the docs and flagged it, and it is recorded here rather than quietly counted.

### What held, named by the code that held it

The HACKER could not desynchronise the document from the config id (**I1.2**), could not get an FP
change past the strict default (**I1.3**), could not get a sub-margin candidate or a reporting gate
into an EMIT block (**I1.7/I1.8** plus the demote-then-gate ordering), could not inject JSON, could
not confuse `config.load`'s whitelist, and never saw a traceback. The host's refusal to import user
code is why H1 had to attack the number rather than the process.

Its own summary is the fairest statement of where the product stands:

> The architecture isn't the problem. Every check verifies the *document* against the *config id*;
> nothing verifies the *config id* against the artifact actually built and timed. H1 corrupts the
> timing, H12 the build, H6 the gate — and I1 certifies all three as perfectly coherent.

That is now the product's stated shape: I1 guarantees the document is honest about the run;
`check_pinned_directives` and the image-provenance rule close two of the three ways the run itself
could be a lie; the third (the driver's clock) is documented as inside the trust boundary.

### Caveats on the campaign

- **Concurrency.** Up to five `cytune` processes timed simultaneously on a rig that isolates one
  core. The USER's U2/U3/U4 numbers are confounded by that — but each also exposed a real reporting
  gap that exists regardless, which is why all four were fixed rather than dismissed.
- **The TESTER did not reach** `audit --json`, exit 3 from `tune`, `--in-place` backup verification,
  or the `--apply` refusal paths. It says so; they remain untested by an independent party.
- **The H6 fix is verified by test, not by a live stub run.** The HACKER's stub run is the "before";
  the eight tests in `test_cytune_h6.py` are the "after".

---

## 9. Release gate

| gate | status |
|---|---|
| A2 dependency test green; A3 leanness reported; ARCHITECTURE + CONTRIBUTING written | **GREEN** |
| B1 coherence in production and firing in tests; B3 cache-key; B4 round-trip | **GREEN** — B4 verified on 9 real archived artifacts, byte-identical |
| `cytune audit` detects the OOB fixture 5/5 | **GREEN** — 6/6, byte-identical verdicts, including one run on the released build |
| Schema 1.0 + compatibility promise + CHANGELOG + single-sourced 1.0.0 | **GREEN** |
| F1 ground-truth dogfood on all 9 anchors with real regret numbers | **GREEN** — median +1.41%, worst +5.41% |
| USER verdict "a stranger succeeds" | **QUALIFIED** — 1.7 min, 0 guesses, no blockers |
| TESTER's untested-path list empty or deferred with reasons | **PARTIAL** — K3 closed; 4 paths explicitly deferred and named above |
| **HACKER produced NO false certificate** | **WAS RED — 3 produced.** Two fixed at the source (H12, H6); one (H1) cannot be fixed and is now a stated limit with partial detection |
| Full suite green; docs synced | **GREEN** — 526 passed, 1 skipped |

**The release gate as written is not met.** It required the HACKER to produce no false certificate,
and it produced three. Two of the three are closed; the third is a property of running the user's own
driver in the process that times it, and the honest response was to document it rather than claim
otherwise.

**This is a decision for the human, and it is the one thing in this report that is not mine to
make.** My recommendation: 1.0.0 is tag-able on the strength of H12 and H6 being fixed and H1 being
correctly scoped — but only if the H1 limit is acceptable as *stated*, because it will not be
engineered away without moving the timing out of the driver's process.

---

## 10. Remaining limitations, verbatim

These are unchanged by this pass and are stated in `docs/GUARANTEES.md` with their evidence:

- A clean sanitizer run is **not** proof of memory safety. `audit` checks eight configurations of
  1,728, on the inputs your driver generates; `tune` checks two. N1/K4.
- The recommendation is **best-in-budget, not optimal** — now quantified at median +1.41% regret on
  nine real modules, but quantified is not the same as bounded.
- **Nothing transfers to other hardware.** One i3-10100F, one pinned image, one toolchain.
- **Routing is DOE-unconditional.** The study measured that per-kernel routing does not beat
  always-DOE on held-out kernels.
- **The study is underpowered** (achieved power 0.708/0.776/0.708 against a 0.80 target; 20 of a
  planned 200 repetitions) and **the statistical auditor's independent recompute has never run**
  against the corrected data.
- The FP-work heuristic can under-warn (K1); `.cytune.toml` on Python <3.11 without `tomli` uses a
  minimal parser (K2); `--target-ms 0` remains untested (K3); the vendored rig cannot be edited
  in place (K7); nothing enforces the `-march=native` portability warning (K8).

---
---

# Part II — 1.0.0 final: artifact binding

Part I ended with the gate red and one sentence explaining why. This part is what closing it took.

## 11. The ruling, recorded

The adversarial campaign in §9 produced three false certificates. Its own summary named the cause
better than any of the three fixes did:

> Every check verifies the DOCUMENT against the config_id, and nothing verifies the config_id
> against the ARTIFACT actually built, gated and timed.

H12, H6 and H1 are three instances. Two were patched at their instance and the class was left open.
This project has paid for instance-patching a named class four times — D22 → P2 → R2 → H\* — so the
class is what this pass closes. **H1 itself is accepted as an architecture-level limit inside the
stated trust boundary. It is not what held the gate. The missing binding layer was.**

## 12. I4 — the binding layer, and what each invariant refuses

`src/cytune/binding.py`. The distinction that matters: I1's ground truth is
`theta.config_of(emitted_config.config_id)` — a pure function of the id, so **I1 can prove a
document is internally consistent and can never prove it is about the run that happened.** I4's
ground truth is a hash of a file.

| id | what it binds | what it refuses |
|---|---|---|
| **I4.1** | the emitted `.so` is the one the endpoint tier timed, on **both** sides of the ratio | a stale, swapped or unrecorded artifact — a forged reference manufactures a speedup as well as a forged winner |
| **I4.2** | the varied directives change the generated code | every combination producing identical C, naming the collapsed factors |
| **I4.3** | the gate's config id, source tree and image **digest** | a verdict about another source, or from an image that is not the pinned toolchain |
| **I4.4** | a decision-grade timing carries its verified rig fingerprint | `quiesced` asserted over a row stamped `UNGATED` |

A `PROVENANCE` block goes on every certificate: emitted artifact hash, the artifact actually timed,
toolchain image digest, rig fingerprint, and how many distinct binaries came from how many distinct
generated sources. Every line is a hash of something on disk.

Also added: **I1.10**, which replaced five substring searches of the rendered certificate with one
exact statement — the text is re-rendered from the document's own JSON round-trip and must be
byte-identical. Strictly stronger than the phrase checks (every byte instead of six sentences), and
it catches what none of them could: `certificate.txt` describing a different run from
`certificate.json` beside it.

### What the degeneracy check actually does, measured against the defect it generalises

The brief's rule was *"all 32 combinations collapsing to ONE class ⇒ refuse"*. Run against the real
H12 header on a real kernel, **that rule does not fire.**
`# cython: boundscheck=False, wraparound=False` neutralises two directives; the other three still
change the generated C, so the partition has several classes and `total_collapse` is `False`. The
rule as stated would have missed the exact defect it was written to generalise.

What works is per-directive: flipping `boundscheck` changes nothing and flipping `cdivision` does,
and that is observable without knowing why. So the detector **names the neutralised directives**,
total collapse remains the refusal condition, and the exact refusal for a partial pin comes from
`check_pinned_directives`, now widened to scan the **whole module tree** — a header in a cimported
`.pxd` defeats the search for every file that includes it. Verified end to end against real Cython
in `test_cytune_binding.py::test_the_degeneracy_check_names_the_directives_a_header_neutralised`.

### The degeneracy result on all nine anchors — a real finding about real library code

Recomputed from the frozen dogfood artifacts through the shipped `binding.degeneracy`:

| anchor | configs | directive combos | distinct generated C | inert |
|---|---|---|---|---|
| csr | 33 | 22 | **15** | `initializedcheck` |
| pava | 33 | 21 | **14** | `initializedcheck` |
| lda | 33 | 21 | **14** | `initializedcheck` |
| binning | 49 | 26 | **15** | `initializedcheck` |
| ppoly | 33 | 21 | 21 | — |
| floyd | 33 | 22 | 22 | — |
| cc | 33 | 21 | 21 | — |
| elkan | 33 | 21 | 21 | — |
| predictor | 33 | 21 | 21 | — |

**`initializedcheck` does nothing to four of the nine anchors.** Turning it off cannot make those
kernels faster, and cytune now says so on the certificate instead of quietly tuning a factor with no
effect. Total collapse: 0 of 9 — no anchor would be refused.

**This number was wrong the first time, and the way it was caught is the point.** The shipped path
initially reported *no* inert directive on any anchor, because `_source_digest` mixed the filename
into the hash and cythonize writes `<module>_<combo>.c` — so every combination got a distinct source
digest **by construction** and I4.2 could never fire in production. The end-to-end test against real
Cython passed the whole time, because it hashed the `.c` files itself instead of calling the
function under test. A named test asserting the wrong thing: R2 and T1 again. It was caught only by
comparing the shipped code's answer against a measurement taken before the code existed, and they
disagreed. `test_the_source_digest_is_equal_for_combinations_that_generated_identical_c` now drives
the production function.

## 13. The speed dividend — measured, and mostly not where the brief expected

Before writing anything, the build manifests and tables of the nine anchors were measured:

| lever | measured reality | shipped? |
|---|---|---|
| **B1** identical-artifact reuse | **distinct `.so` == config count on every anchor** (33/33, 49/49). Two configs differ in at least one GCC factor, and gcc produces different bytes | yes — 20 lines, fires 0 times here |
| **B2** one container per phase | podman spawn measured at **0.20–0.30 s**; a run makes **12** container launches. 5 of them are measure phases that would have to bypass `measure_wrap`'s per-invocation host verification. Ceiling on the 7 safe ones: **~1.75 s of a 411 s run — 0.4 %** | **no** |
| **B3** parallel builds | **build was 71 % of wall clock** (csr: 496 s of 695 s) and `campaign.build_all`'s cythonize phase is **serial** | **yes — this is the dividend** |
| **B4** racing early-abort | the fixed per-config cost (spawn, imports, warmup, per-rep input regeneration) is **80 %** of the measure phase; racing every config to K=1 saves at most **16 % of the measure phase**, which is a minority of wall clock once the build is parallel | **no** |

**B1** is kept although it never fires, because when it does fire, re-measuring is not merely
wasted — a "speedup" between two byte-identical binaries is noise being certified as a gain.

**B3** is the whole win. The study's scheduler serialises one cythonize per distinct directive
combination, which is free in a fleet run (32 serial calls out of 1,728 builds) and crippling in a
tuning run (~22 serial calls out of ~33). `worker._build_all` parallelises it.

Rescheduling a build is safe only if the bytes are identical, which is a test rather than an
argument: `test_the_parallel_scheduler_produces_byte_identical_artifacts` builds a real kernel with
both schedulers inside the pinned image and compares every artifact hash. **This is the second thing
binding buys** — it makes a performance change checkable instead of plausible.

**B2 and B4 were built as measurements and not as features.** Neither could be justified in one
sentence in the user guide against its measured ceiling, and B2's measure half would have required
weakening the one thing that verifies the host is quiesced.

## 14. C — H1 to the edge of what the architecture allows

`certify.corroborate_ratio`. The parent brackets every sub-measure with a clock the child cannot
reach. What makes it usable is what cancels: the winner and the reference run the same driver, the
same `K`, the same inputs, in the same image, so their non-timed remainders
(`wall − K × median`) must differ by **exactly** `warmup × (t_win − t_ref)`.

**Its power is a curve, and the curve is pinned by test rather than described.** For a true speedup
`r_true` reported as `r_claim`, the unexplained fraction of the claimed gain is
`(1 + warmup/K) × (1/r_true − 1/r_claim) / (1 − 1/r_claim)`:

| a driver claiming | is caught whenever the true speedup is below |
|---|---|
| 1.5× | 1.24× |
| 2× | 1.40× |
| 5× | 1.84× |
| 10× | 2.06× |
| 100× | 2.30× |

That fraction is `1 + warmup/K` whenever there is **no real speedup at all**, whatever is claimed —
so the entire "this kernel is flat and the driver says otherwise" class, which is the demonstrated
H1 attack, is caught with more than a factor of two to spare.

**The blind spot, stated because it is real:** inflating an already-large real gain is not caught. A
genuine 2.5× can be reported as 5×, or a genuine 3× as 100×.
`test_c1_the_blind_spot_is_real_and_is_not_hidden` pins it.

**The threshold cannot simply be tightened.** The fresh novice user's *honest* 9.85× run left 38 %
of its claimed gain unexplained — 53 ms of residual against that run's own 10.2 ms process-noise
sigma — so a stricter budget would withhold real speedups, and withholding honest results is the
failure direction this product cannot take. That run also showed the budget's floor was an arbitrary
constant (5 % of the overhead) when the run had already sampled the right quantity 25 times; it is
now 3σ of the per-process overhead spread measured over the run's own screened configurations.

**C2:** every certificate now carries an `ATTESTATION` block saying what it does and does not
attest, and that it is not evidence to a third party who does not trust the driver. It is in the
certificate because certificates get forwarded and `SECURITY.md` does not travel with them.

**C3:** GUARANTEES N8, KNOWN_ISSUES K10 and SECURITY.md state the limit with the table above rather
than the word "catches".

## 15. D — the cuts, with counts

| | before | after |
|---|---|---|
| product modules | 18 | 20 |
| product LOC | 5,378 | 7,022 |
| vendored rig LOC | 1,295 | 1,295 |
| test LOC | 4,488 | 5,455 |
| `tune` flags | 18 | **17** |
| runtime invariants | 18 | 23 |
| tests | 527 | 651 |

The product grew 1,644 lines: `binding.py`, `init.py`, the parallel scheduler, ratio corroboration.
Each is justifiable in one sentence in the user guide, which was the rule. Removed:

- **`--objective size|compile`** — a flag whose only behaviour was to refuse, costing a line in
  `--help`, a field in `.cytune.toml`, a row in the exit-code table and a section of
  TROUBLESHOOTING. §6 of the guide now shows how to rank on `compile_s`/`so_size_b` directly.
- **The prose-scanning half of the coherence gate** — `SAFETY_WORDING`, `_affirms`, the negation
  window and five substring searches. Replaced by one field, one exact invariant (I1.10) and a
  renderer test file. Removing it exposed a live defect: the no-feasible-config path returned with
  no `exit_code` and an un-downgraded "remains the best safe choice", i.e. it asserted safety for a
  configuration nothing had gated. The field made the branch that never set it visible.
- **Nothing else.** `examples/` was checked for reachability and stays (`README.md` points at it;
  a test fails if no document mentions it). `measure_wrap.sh` is confirmed **not** vendored.

## 16. E — the last two setup frictions

`cytune init <module.pyx>` reads the kernel's first public signature and writes a driver: typed
memoryviews and scalars are filled in, anything untyped or `object` gets a loud `TODO`, and
`SCALE` starts smaller as dimensionality rises so a 2-D kernel does not open with a 134 MB array. It
then runs the same contract check `tune` uses. It deliberately does not guess — an invented input
becomes the workload the oracle is derived from.

`cytune doctor --build-image` builds the pinned toolchain and **verifies the resulting digest**. A
build that succeeds and produces a different image is a failure, not a checkmark: that is an
unpinned toolchain, and a clean sanitizer verdict from one is not treated as a pass.

Both were tried by a fresh novice user; §19 has the result.

## 17. F1 — the live smoke gate, and what it found on its first pass

`scripts/release/smoke.sh` runs `doctor → init → tune → audit → resume → the container-backed
binding tests` against real containers, and is now the pre-tag ritual in CONTRIBUTING. It exists
because 526 tests were green while the rig returned rc=127.

**It found a defect on its first complete pass, and the defect was two years of documentation being
wrong.** Ingest re-copies the user's driver, which resets the calibration knob; calibration then
re-derived the workload from a single measurement of the reference, and timing noise moved the
answer by a fraction of a percent every run — **33831, then 33699, for an untouched kernel.** The
calibrated workload is in the measurement cache key, correctly, so **every re-run discarded the
entire table and re-measured from nothing.** Builds resumed; measurements never had, while
CONTRIBUTING asserted "cytune already resumes". Fixed by reusing the calibration when nothing it
depends on has changed; the probe stage of a repeat run went from 12 s to 1 s, and `delta_probe`
became reproducible between runs.

No unit test could have caught it: every one of them either mocks the rig or exercises the cache key
in isolation. That is the argument for the gate.

## 18. G1 — the focused adversarial re-run

A fresh hacker with no memory of this project was aimed at the binding layer and told only that
certificate integrity was the property. Objectives in priority order: bind-break, degeneracy
evasion, gate-source forgery, ratio forgery. Its work is under `results/release/agents/hacker2/`.

**It produced two bind-breaks. Both were introduced by this release's own fixes.** That is the
result worth stating plainly: aiming an adversary at a *defence* rather than at the defect the
defence replaced is what found them, and neither would have been found by re-running the previous
campaign.

### Attack A — a re-tag between the digest check and the container launch

The fix for H6 replaced a name comparison with a digest comparison. The digest lookup memoises per
image name and was first populated at stage `[1/6]`; the sanitizer gate compared that cached value
minutes later while `podman run <name>` resolved the tag **live**. One command —
`podman tag stub localhost/motifbo-env:phase1` — placed between those two moments made
`is_pinned_image()` answer *pinned* from a stale, honest digest while a stub actually executed.

Demonstrated with a stub image whose `python3` is a three-line script printing
`{"clean": true, ...}`. False fields: `sanitizer_gate.clean=true`,
`sanitizer_gate.image_digest=<pinned>`, `image_overridden=false`, and the `safety_wording_earned`
licence that follows from them. **H6 rebuilt on top of its own fix, by a cache added for speed.**

**Fixed** by resolving the image once and passing the resolved **ID** to `podman run` everywhere
(`rig.image_ref`), so the image whose digest was compared is by construction the image that ran; a
tag moved afterwards points somewhere cytune is no longer looking. The adversary re-tested it and
reports the compare-value and the run-reference are now the same value, with no asymmetry left.

**Its secondary defect, also fixed:** `assert_gate_bound` only compared source trees when the gate
*volunteered* one. The stub simply omitted `source_tree_sha256` and I4.3 passed with it `None`.
Silence is not agreement — a CLEAN verdict that does not say what it was about now clears
`authoritative`.

### Attack B — the driver swapping the artifact between the hash and the load

**This one was inside I4.1.** `cmd_endpoint` hashed the `.so` in the parent before spawning the
child; `_vendor/measure_child.py` loads the **driver first** and the `.so` afterwards. The driver's
import-time code therefore runs between the hash and the load, in a container where the whole
workspace was mounted read-write. A driver that overwrote the winner's binary with a faster one
producing identical output satisfied every check at once:

- **I4.1** — both hashes were taken of the honest file, so they matched;
- **C1** — the fast binary really did take that long, so the wall clock corroborated;
- **the oracle** — identical output, so feasibility held.

A forged speedup, fully bound and fully corroborated. Not the H1 clock residue: the clock was
honest and a real faster binary really ran — it just was not the one certified.

**Fixed** by removing the capability rather than detecting the act. Nothing in a measure phase
writes to `_so/` — the build phase is a separate container, which is what CF-1 is for — so it is
mounted **read-only**, and the endpoint tier re-hashes after the loop as well. Reproduced against
the fix on the adversary's own fixture:

```
OSError: [Errno 30] Read-only file system: '/work/atkb/_so/kernel_564.so'
  -> winner rejected at endpoint, fell back to the reference, VERDICT: NO-SAFE-IMPROVEMENT
```

### What held — the failed attempts

Reported by the adversary, and this section is the evidence that the layer was tested rather than
merely built:

| attempt | why it failed |
|---|---|
| Attack A with the re-tag placed **before** stage 1 | the cache fills with the stub's id, the digest mismatches, `--apply` refuses, and the measure phases run the stub and fail loudly |
| `CYTUNE_SANITIZER_IMAGE=<stub>` with no re-tag | resolves the stub's real id; digest mismatch ⇒ not authoritative |
| `# cython:` header in the named `.pyx`, and in a sibling `.pxd`/`.pxi`/`.py` | refused at ingest by the tree-wide scan |
| total degeneracy | refused at stage `[1/6]`, before any budget is spent |
| screen-phase swap with an `atexit` restore | the restore segfaults at teardown ⇒ every config `crash` ⇒ R0 abort; independently blocked by the read-only mount |
| forging the digest itself | `{{.Id}}` is content-addressed; no image can be built to a chosen id |

Its own method note is worth recording: *"I found the real defences by running the worker and
hitting EROFS, not by trusting the read."* Its first reads were a stale snapshot.

### What it could not demonstrate, and what that is worth

- **The loader-hijack variant of Attack B.** The read-only mount and the re-hash both key on the
  file on disk. They do not stop the driver — loaded first — from monkeypatching
  `importlib.util.spec_from_file_location` or setting `KERNEL_MODULE`/`PKG_MODULE` so the child
  imports a different binary while the honest `.so` is never touched. I4.1 would match and C1 would
  corroborate. **Believed exploitable, not demonstrated.** No hash reaches it: it is the same trust
  boundary as the clock. The certificate's provenance note now says "the FILE the endpoint tier was
  pointed at" rather than "the binary that ran", and SECURITY.md lists it.
- **`@cython.boundscheck(False)` as degeneracy evasion.** Correct and previously untested: a
  decorator overrides `-X` and is not a header, so the header scan missed it entirely. Now detected
  — and **reported rather than refused**, because refusing would have blocked three of the nine real
  anchors (`_ppoly`, `_shortest_path`, `_traversal`), all of which are non-degenerate. K15.
- **C1 had no lower cutoff.** Correct. With a large fixed per-process cost and a small claimed gain,
  the noise floor exceeds the largest discrepancy any lie could produce, so `corroborated: true`
  would have meant only "the arithmetic was performed". It now reports NOT CHECKED — not-run is not
  a pass, one level up. K16.

### The adversary's own assessment

> The binding layer, as fixed, closes the concrete class it names — every certificate hash is now
> tied to the bytes actually built, gated (by resolved image Id) and timed (from a read-only
> artifact tree) — with the one honest, pre-declared residue that a hostile in-process driver can
> still make cytune time or load a binary other than the one it hashed, which is the trust boundary
> the document states rather than a hole it hides.

## 19. G2 — the fresh novice user

A working developer who had never seen cytune, docs only, no source. **Time from writing a `.pyx`
to a verdict: ~2 minutes of tool time**, of which 90 seconds was the tuning run itself. It never
opened the user guide — the README quickstart plus `--help` was enough.

`cytune init` inferred every shape, dtype and parameter of `run(double[::1] x, double lam, int
reps)` correctly and the driver **ran unedited**. Its verdict on the feature: *"earned its place —
the value wasn't the boilerplate, it was that it introspected my function signature."*

Three findings, all fixed:

1. **The corroboration line was the one gate in the certificate that required arithmetic.** It
   printed `38.2% of the gain unexplained, budget 50%` and never said that meant PASS. Every other
   gate states its own criterion inline. Now it says PASS and both quantities, and has a glossary
   entry.
2. That same run exposed something the user could not see: **an honest 9.85× passed with only 24 %
   headroom**, because the budget's floor was an arbitrary "5 % of the overhead" constant when the
   run had already sampled the right quantity 25 times. The floor is now 3σ of the per-process
   overhead spread the run itself measured.
3. `[2/6] probe — pre-registered 16-config screen` reported `feasible 17/17` on the next line; and
   `doctor --build-image --help` said what it did but not when to reach for it.

## 20. B5 — the nine anchors, re-run on the released build

Same nine Dataset-R modules, same frozen 1,728-config tables, same analyser
(`scripts/release/analyse_dogfood.py`, now taking the directory as an argument so one definition of
regret covers both runs). Raw: `results/release/dogfood2/`.

| anchor | wall before | wall after | faster | regret before | regret after | configs | binaries | sources |
|---|---|---|---|---|---|---|---|---|
| csr | 695 s | **440 s** | 36.7 % | +0.00 % | +0.00 % | 33 | 33 | 15 |
| pava | 271 s | **183 s** | 32.5 % | +1.41 % | +1.41 % | 33 | 33 | 14 |
| lda | 239 s | **165 s** | 31.0 % | +0.94 % | +0.94 % | 33 | 33 | 14 |
| binning | 393 s | **299 s** | 23.9 % | +1.85 % | +1.85 % | 49 | 49 | 15 |
| ppoly | 330 s | **210 s** | 36.4 % | +0.80 % | +0.80 % | 33 | 33 | 22 |
| floyd | 307 s | **185 s** | 39.7 % | +5.40 % | +5.40 % | 33 | 33 | 22 |
| cc | 413 s | **265 s** | 35.8 % | +0.79 % | +0.79 % | 33 | 33 | 21 |
| elkan | 1008 s | **758 s** | 24.8 % | +5.41 % | +5.41 % | 33 | 33 | 21 |
| predictor | 435 s | **297 s** | 31.7 % | +5.10 % | **+1.50 %** | 33 | 33 | 21 |
| **total / median** | **4091 s** | **2802 s** | **31.5 %** | **+1.41 %** | **+1.41 %** | 313 | | |

**Regret did not get worse: median +1.41 %, worst +5.41 %, both identical to the baseline.** Eight
of the nine emitted the *same configuration* as before; `predictor` happened to land better. That
is the result the re-run was for — the build was rescheduled and the measurement path was left
alone, so the answers should not move, and they did not.

**The honest headline, with every term measured:**

> On nine real scipy and scikit-learn modules, cytune's recommendation was **within 1.41 % of the
> exhaustively-known optimum** (worst case 5.41 %), measured on **2.0 % of the search space**
> (313 of 15,552 configurations), in a **median of 4.4 minutes per module**.

Every one of the nine was also, on the released build:

- **artifact-bound** — the emitted `.so` is the one the endpoint tier timed (9/9);
- **wall-clock corroborated** — the parent's clock agrees with the reported ratio (9/9);
- **sanitizer CLEAN** on the emitted configuration (9/9).

And `initializedcheck` was measured **inert on four of the nine** — flipping it never changed the
generated C. That is a fact about scipy and scikit-learn that no previous version of this tool could
have told anyone, and it is on those four certificates.

## 21. The release gate

| requirement | status |
|---|---|
| I4 invariants fire in tests and run in production | **met** — I4.1–I4.4, each with a failure-path test; all four run on every real `tune`, and all four fired against real attacks during this pass |
| the generic degeneracy check stands with the blacklist off | **met, with a correction.** It stands, and it is *weaker than the brief assumed*: run against the real H12 header it does not reach total collapse and does not refuse. It names the neutralised directives; the refusal for a partial pin comes from the tree-wide header check. Stated, not smoothed over |
| B5 dogfood shows regret not worse with materially less work | **met** — 31.5 % less wall clock, regret bit-identical on 8 of 9 and better on the 9th |
| C1 / C2 shipped | **met** — with the power curve tabulated and the blind spot pinned by test |
| D cuts done with counts reported | **met** — §15 |
| F1 live smoke gate green | **met** — and it found the resume defect on its first complete pass |
| G1 produced no bind-break | **NOT met as stated. It produced two.** Both were introduced by this release's own fixes, both are closed at the source, and the adversary re-tested both against the fixes and could not get past them |

### On the last row, which is the one that matters

The gate asked for an adversarial pass that produces no bind-break. It produced two — and that is a
better outcome than the same gate passing would have been, because both were **created by the fixes
in this very release**: a digest cache added for speed re-opened H6, and the artifact hash added to
close the class was itself taken at a moment the driver could act between. Neither existed before
this pass, and neither would have been found by re-running the previous campaign against the
previous defects.

The honest reading is not "the gate failed" and not "the gate passed after fixes". It is: **aiming a
fresh adversary at a defence, rather than at the defect the defence replaced, is what this project
should have been doing all along.** Two of the four remaining items it raised were also real and are
fixed; a third (the decorator vector) is fixed proportionately, and the fourth (loader hijack) is
inside the stated trust boundary and is now written down.

**What has not changed:** a hostile driver shares the process that measures it. It can misreport the
clock beyond the corroboration curve, and it can hijack its own module loader. Those are the trust
boundary, they are in `SECURITY.md`, GUARANTEES N8, K10 and K14, and — new in this release — in the
`attestation` block of every certificate, because certificates get forwarded and `SECURITY.md` does
not.

**This is a recommendation to tag, not a decision.** Everything the gate asked for is met except a
requirement whose failure produced the two best findings of the pass, both of which are fixed and
re-tested. The one thing that remains a human judgement is the same one as last time, one notch
narrower: **the driver is inside the trust boundary, and no amount of hashing changes that.** The
tag is the human's.

## 22. The two tag conditions, resolved against the committed build

The gate's checklist (§21) is about the *pass*. The tag condition is a different, narrower
statement, and it is worth resolving on its own terms because the two are easy to conflate:

> Tag only when **no agent can produce a certificate whose claims are not bound to the artifacts
> that produced them**, and **every remaining limit is stated in the certificate, not only in
> SECURITY.md**.

### Clause 1 — can an agent still produce an unbound certificate?

Both bind-breaks were re-run against the committed tree, from the adversary's own fixtures:

| attack | result on the committed build |
|---|---|
| **A** — re-tag between the digest check and the container launch | the gate returned `source_tree_sha256` and `sanitizer_artifact_sha256`, **fields the stub's canned JSON cannot produce**, so the real pinned image ran while the tag pointed at the stub. `is_authoritative: true` is correct rather than forged |
| **B** — driver swaps the `.so` between the hash and the load | `measure_failed` at the endpoint tier, winner rejected, fell back to the reference, `VERDICT: NO-SAFE-IMPROVEMENT`, `speedup: 1.0`, emitted artifact still bound |

The adversary's own conclusion, after re-testing: A is *"fully closed"* — the compare-value and the
run-reference are the same value by construction — and B's file-swap route is closed by two
independent defences.

**Note on how this clause should be read.** Taken as "an agent produced one at any point during
testing", it is unsatisfiable by construction: any adversarial pass that finds anything would bar
the release permanently, and the incentive would be to run a weaker adversary. Read as it is
written — present tense, about what an agent *can* do — it is a statement about the code that
exists now, and that is the reading under which fix-then-re-test is the point of running an
adversary at all. Under that reading, clause 1 holds: **no attack in this campaign reaches an
unbound certificate against the committed build.**

What remains is the loader-hijack route the adversary named and did not demonstrate. It is inside
the declared trust boundary, no hash reaches it, and it is why clause 2 matters.

### Clause 2 — is every remaining limit in the certificate?

**It was not, and checking this clause is what found the gap.** The artifact-binding limit had been
written into `provenance.note` in `certificate.json` and was never rendered, so a reader of
`certificate.txt` — the copy that gets forwarded, which is the entire reason the attestation block
exists — saw the clock limit and not the loader one. A limit that lives only in a field a human does
not read is stated in exactly the sense the pre-1.0 documentation was.

Every certificate now renders both halves of the boundary:

```
WHAT THIS CERTIFICATE ATTESTS
  IT ATTESTS that cytune built, oracle-checked, sanitizer-gated and timed the configuration
  named above, in the pinned toolchain, and that every claim here is bound to the hashes in
  PROVENANCE.

  IT DOES NOT ATTEST that the timings are what the kernel really takes. ...the reported medians
  are as trustworthy as that driver.

  IT DOES NOT ATTEST that the binary the measurement imported is the one hashed above. The
  hashes bind the FILE cytune built and pointed the endpoint tier at... They do not bind against
  a driver that hijacks its own interpreter's module loader.

  this is evidence to whoever controls the driver. It is NOT evidence to a third party who does
  not trust that driver.
```

`test_cytune_render.py::test_every_stated_limit_reaches_the_RENDERED_certificate` fails if any
attestation field stops being printed.

**Both tag conditions now hold against the committed build.** 653 tests, live smoke gate green.

### The tag itself

Not created, and deliberately. §H of the directive that commissioned this work reads: *"Then update
the release report and STOP for the human to tag — the human tags, not you."* The work is committed
on `release/1.0.0` so that the act is one command:

```bash
git checkout main && git merge --ff-only release/1.0.0
git tag -a v1.0.0 -m "cytune 1.0.0 — artifact binding"
```
