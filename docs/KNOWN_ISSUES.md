# Known issues

Two lists: what is still open, and what was fixed in the productisation pass with the test that
proves each. Nothing is deleted from the record.

Finding IDs are from
[`../results/usertest/USER_TEST_REPORT.md`](../results/usertest/USER_TEST_REPORT.md); the fixes and
their evidence are in
[`../results/usertest/PRODUCTIZATION_REPORT.md`](../results/usertest/PRODUCTIZATION_REPORT.md).

---

## Open

### The environments this release was actually run in

Stated because "supported" and "exercised" are different words and this page is where the difference
belongs. Everything in the left column was run; everything in the right column was not, and no claim
anywhere in this repository may exceed it.

| | exercised | not run |
|---|---|---|
| **host Python** | **CPython 3.9.25, 3.10.20, 3.11.15, 3.12.13, 3.13.15, 3.14.7** — the shipped suite on each, **786 passed / 19 skipped / 0 failed, identical on all six** | anything below 3.9; PyPy or any non-CPython |
| **container runtime** | rootless podman | **podman as root**; docker; any other OCI runtime |
| **hardware** | one Intel i3-10100F, x86-64 Linux | everything else — see **N3**, this is the big one |
| **disk** | normal operation | **disk exhaustion mid-run** (see K-21) |
| **filesystem** | ext4, unicode and spaces in paths | network filesystems, case-insensitive filesystems |

The Python row was measured, not assumed: `pyproject.toml` claimed `requires-python = ">=3.9"` while
every run in the launch pass used 3.14.5, so five of the six supported versions had never executed a
line of this code. Running them found **D33** — see below.
Raw: [`../evidence/python_matrix.json`](../evidence/python_matrix.json), with the six full pytest
logs and the script (`scripts/release/pymatrix.sh`) on the `dev` branch.

**K-20 — podman as root is untested, and `rootless is fine` was the wrong way round.** Every
measurement in this repository was made with rootless podman. Running the pinned image as root is
not known to break anything and is not known to work; in particular the measurement lock's path
(`/var/lock/cytune/` falling back to `/tmp/`) and the workspace's ownership after a root container
writes into it have not been exercised. *Why not fixed:* it is a real test matrix cell, not a code
change, and running it properly means a second machine rather than a `sudo` on this one.

**K-21 — disk exhaustion mid-run is untested.** A tuning run writes builds, artifacts, a golden and
a growing `table.jsonl`. What happens when the filesystem fills between the build phase and the
measure phase has never been observed. The failure is expected to be loud (an `OSError` from a
write), and "expected to be" is the whole reason this entry exists. *Why not fixed:* simulating it
faithfully needs a size-capped filesystem, which is a rig change.

**D33 — a test that read the host instead of the code, found by running the Python matrix.**
`test_failure_path_sanitizer_check_passes_when_the_image_is_present` stubbed `doctor._run` but not
`sanitize_gate.is_pinned_image()`, which shells out to podman on its own. It therefore passed on the
development machine because the pinned image happens to be there, and **failed on every machine
without it** — which is every machine a new contributor starts from, and all six interpreters in the
matrix. Fixed: both dependencies are stubbed, and the H6 branch it was shadowing (an image that
exists but is not the pinned one) now has a test of its own.

### Limitations that will not be "fixed" — they are the honest shape of the product

**The routing policy is an engineering default, not a validated router.** Measured, not
speculative: RQ-P2 found routing does not beat always-DOE on held-out kernels. cytune ships one
algorithm and says so in one sentence everywhere. `../results/PHASEP_REPORT.md` §5.

**Three of four kernel categories are underpowered** (achieved power 0.708 / 0.776 / 0.708 against
a 0.80 target) and the study ran 20 of a planned 200 repetitions. Non-significant study findings
are underpowered nulls, not "no difference".

**Single hardware.** One i3-10100F, one pinned image. Nothing transfers. `-march=native` can be
emitted; cytune warns, and `--portable-flags` gives a fleet-safe alternative.

**The statistical auditor's independent recompute has never run** against the corrected data — it
was killed twice by service limits. Every number is traceable to raw measurements, but not
independently recomputed.

### Real, open, and not yet worth the fix

**K1 — the FP-work heuristic can under-warn.** The `FLOATING-POINT SEMANTICS` block is suppressed
when the oracle's output class is integral *and* no `float`/`double`/`complex` token appears in the
module source. A kernel that computes in double and returns an int reads as "no FP work". *Why not
fixed:* the honest alternatives are parsing Cython's AST or always warning; the first is a large
dependency for a warning, the second is what F21 was about. The heuristic is biased toward
over-warning, is labelled as a heuristic in the certificate, and only ever affects a **warning** —
never what is emitted.

**K2 — `.cytune.toml` on Python < 3.11 without `tomli`** falls back to a minimal parser that
handles only `[section]` and `key = value` with string/number/bool values. It refuses anything else
rather than guessing. *Why not fixed:* the alternative is a hard runtime dependency on a host that
currently needs none. `pip install tomli` for full TOML.

**K3 — `--target-ms 0` (calibration disabled) is untested.** The code path exists and is
documented; no run has exercised it.

**K10 — your driver owns the clock, and cytune certifies what it reports.** `measure_child` loads
your driver into the very process that times it. A driver that replaces `time.perf_counter_ns`
produced a certified `5.0000x` on a kernel where nothing is faster than anything else. *Why not
fixed:* the driver IS the thing being timed; moving the clock out of its process means a different
measurement architecture, not a patch.

*Narrowed in 1.0.0, and by exactly how much.* Over-claims were already flagged. Under-claims — the
direction a speedup is actually manufactured from — are now attacked too: the winner and the
reference share driver, `K`, inputs and image, so their non-timed remainders (`wall − K × median`,
measured by the PARENT) must differ by exactly `warmup × (t_win − t_ref)`. When the residual exceeds
its budget the speedup is **withheld** and the verdict becomes `no-safe-improvement`.

The power is not "catches lying drivers"; it is a curve, and the curve is pinned by test rather than
described. A claimed `r_claim` is caught whenever the TRUE speedup is below `1.24x` (for a 1.5x
claim) rising to `2.30x` (for a 100x claim) — so any claim at all about a kernel that is really flat
is caught, which is the demonstrated H1 attack, while **a genuine 2.5x reported as 5x is not**. See
GUARANTEES N8 for the table and `test_cytune_binding.py` for the pins.

*What is left, and it is not closable by timing.* A driver can see which module it was handed, so
one that does genuinely **more work** for the reference burns real wall clock — every relation above
holds and the certificate is a true statement about a rigged comparison. For the real use case, you
tuning your own code, this is self-deception rather than an attack. **Do not treat a certificate as
attesting a speedup to someone who does not trust the driver** — since 1.0.0 the certificate says
this itself, in its `attestation` block. Full statement in [`../SECURITY.md`](../SECURITY.md) and
GUARANTEES N8.

**K11 — CLOSED in 1.0.0.** It read: *"nothing verifies the config id against the artifact that was
actually built"*, and concluded *"there is no general fix"*. That conclusion was wrong. The fix is
not to hash the `.so` against the directives it should have been built with — the toolchain does not
expose that — but to stop reasoning from the id at all: hash the artifact at build, hash it again at
the moment it is timed, and refuse to emit unless they are the same file, on both sides of the
ratio. That is I4.1, and I4.2/I4.3/I4.4 do the same for the generated code, the gate and the rig.
See [GUARANTEES.md](GUARANTEES.md) G8 and `src/cytune/binding.py`.

**K12 — `# pragma GCC optimize` / `#pragma GCC target` inside the module are not inspected.** The
certificate's flag string is ground truth for what cytune **passed** to the compiler, and invariant
I1.3 checks that rigorously. It is not ground truth for what gcc **applied**: a module can steer the
compiler from inside via `cdef extern from *` blocks. *Partially covered since 1.0.0:* if such a
pragma neutralises a GCC factor, the artifacts stop differing and `binding.degeneracy` counts fewer
distinct binaries than configurations, which appears in the certificate's PROVENANCE line. That is a
signal, not a refusal — the degeneracy refusal covers the five *directive* factors, not the four GCC
ones.

**K15 — a decorator or `with` block that pins a tuned directive is REPORTED, not refused.**
`@cython.boundscheck(False)` and `with cython.cdivision(True):` override the `-X` flags for the code
they cover, exactly as a file header does for a module. cytune names the file, the line and the
directive on the certificate and tunes the rest of the module normally. *Why not refused:* a header
neutralises a directive for the WHOLE module — every combination compiles identically and nothing
the certificate says about directives is true — while a decorator covers one function and the rest
still varies. Refusing on decorators would have blocked **three of the nine** real
scipy/scikit-learn anchors this product was validated against (`_ppoly`, `_shortest_path`,
`_traversal`), all three of which still produce 21 distinct generated sources from 21 directive
combinations. *What is still true:* for the functions those decorators cover, the emitted header —
including the reference's "Cython's safe defaults" — does not apply. Found by the focused
adversarial re-run.

**K16 — wall-clock corroboration reports NOT CHECKED when the claim is small relative to process
noise.** The largest discrepancy any misreport of a gain `g` can produce is `(1 + warmup/K) × g`. On
a kernel with a large fixed per-process cost and a small claimed gain, the measured noise floor
exceeds that, so nothing could fail the check and passing it would mean only "the arithmetic was
performed". It reports unavailable instead, on the same rule as a sanitizer gate that could not run.
The emit margin and the separation test still gate small gains. Found by the focused adversarial
re-run, which observed that C1 had no lower cutoff.

**K14 — the driver still shares the process with the measurement, and that is the root of two
separate findings.** K10 is the timing half. The focused adversarial re-run found the artifact half:
`measure_child` loads the driver *before* the `.so`, so a driver's import-time code ran between
I4.1's hash and the binary being loaded. Both are instances of one fact — the driver is inside the
trust boundary — and each needed its own fix, because binding the artifact does not bind the clock
and corroborating the clock does not bind the artifact. The artifact half is now closed structurally
(`_so/` is mounted read-only during measure phases; nothing in a measure phase writes there) — but
only against a FILE SWAP. The adversary's own follow-up names the escape it did not demonstrate: the
driver is loaded first, so it can hijack its own interpreter's module loader — monkeypatching
`importlib.util.spec_from_file_location`, or setting `KERNEL_MODULE`/`PKG_MODULE` — and have the
child import a different binary while the honest `.so` on disk is never touched. I4.1 would match
and C1 would corroborate. No hash can reach that; it is the same trust boundary as the clock, and
the certificate's provenance note now says "the FILE the endpoint tier was pointed at" rather than
"the binary that ran". The timing half cannot be closed either. *What this means:* expect further
instances of this shape rather than treating any of these fixes as having closed "the driver
problem".

**K13 — the generic degeneracy check refuses only TOTAL collapse, and that is weaker than it
sounds.** `binding.degeneracy` hashes the generated C per directive combination; I4.2 refuses when
every combination produces identical C. Measured against the actual H12 header
(`# cython: boundscheck=False, wraparound=False`) on a real kernel, **it does not fire** — the other
three directives still change the C, so the partition has several classes. What it does do is report
`boundscheck` and `wraparound` as *inert*, by name, without knowing the mechanism. The refusal for
that case comes from `check_pinned_directives_tree`, which is exact but is a blacklist of one
mechanism (a `# cython:` header, now searched across the whole module tree rather than only the
named file). *Why not fixed:* refusing on any single inert directive would refuse every kernel that
simply does no division or has no `None`-able arguments, which is most of them. Verified end to end
in `test_cytune_binding.py`.

**K7 — the vendored rig is pinned to the study source, so it cannot be edited in place.** Product
fixes to `_vendor/campaign.py`, `_vendor/build.py`, `theta`, `seeds`, `measure_child`, `san_child`
or `profiles` fail `test_cytune_vendor.py` until the same change lands in `scripts/phasep/`. *Why
this is the design, not a defect:* the alternative is a fork that drifts silently from the code
every number in `results/` was measured on, which would also invalidate the ground-truth dogfood.
The procedure is in [CONTRIBUTING.md](CONTRIBUTING.md#adding-an-oracle-class).

**K8 — the emitted `march` is not checked against the machine that will run the binary.** cytune
warns when it emits `-march=native` and offers `--portable-flags`, but it cannot know where your
artifact will run. Nothing enforces the warning.

**K9 — `cytune audit` costs one container build+run per risk-set entry** (8 entries, ~4 minutes
total on the acceptance fixtures). It is not free and is not run as part of `tune`; `tune` points
at it when a run ends `no-safe-improvement`.

**K4 — the sanitizer gate checks one config out of 1,728, on the inputs your driver generates.**
A clean gate is evidence, not proof. This is a property of sanitizers, not a bug, but it is the
single most over-readable line in the certificate, so it is repeated here.

**K5 — no repeatability guarantee is claimed.** One fixture was run twice and the verdict was
stable (proof 22), which is one observation, not a distribution.

**K6 — `tune`'s sanitizer gate is a non-emission guarantee, not a detection guarantee. NOW
ADDRESSED, and the limitation restated precisely.** `cytune tune` gates two configs out of 1,728:
the search's best candidate and the config it emits. Whether a latent memory bug is *found*
therefore depends on where the DOE walk lands, which varies between runs — measured at **3 of 5**
on the same out-of-bounds fixture, with the emitted reference gated CLEAN every time, so nothing
unsafe was ever emitted.

*What changed in 1.0.0:* `cytune audit` turns detection into a deterministic capability. It gates a
pre-registered risk set — including the boundscheck+wraparound **pair**, which is the only
combination that exposes D23 and is not derivable from the per-directive singles — and measured
**6 of 6** on the same fixture, with a byte-identical verdict structure across all six runs.

*What remains true:* `tune` still gates two configs, and `audit` still checks eight of 1,728 on the
inputs your driver generates. Neither is a proof of memory safety (K4). The honest statement is now
split across [GUARANTEES.md](GUARANTEES.md) G2 (non-emission) and G2b (deterministic detection over
a stated risk set).

---

## Fixed in this pass

Every fix ships with a test that drives its **failure** path. Run them with
`pip install -e ".[test]" && pytest -q src/cytune`.

### Entry (T1)

| # | was | now | proof |
|---|---|---|---|
| **F1** | `cytune doctor` — the README's first command — did not exist. No packaging, no `PYTHONPATH` note. Four guesses to start the CLI. | `pyproject.toml` with a `cytune` console script; `pip install -e .` then `cytune doctor`. `python3 -m cytune` still works. `doctor` has an **entry point** check that names the fix. | live install + `test_doctor_json_is_machine_readable` |
| **F2** | `docs/` did not exist. | Five documents, written from what a cold tester actually needed. | this directory |
| **F3** | The pinned image is BLOCKING and nothing said how to get it. | `doctor` prints `podman build -f Containerfile -t localhost/motifbo-env:phase1 .` and the expected image ID, and flags a mismatch. The README carries the same command. | `test_doctor_names_the_image_build_command` |

### Truth (T2)

| # | was | now | proof |
|---|---|---|---|
| **F4** | A kernel whose entire 1.74× headroom was refused as unsafe was reported `HONEST-FLAT` — "your kernel has no headroom" when the truth was "all of it is unsafe". | Distinct `NO-SAFE-IMPROVEMENT` verdict (exit 3) and a `!!!` **MEMORY-SAFETY DEFECT** block above the recommendation, with the config id, how much faster it looked, the ASan summary, and the path to the full report. | `test_f4_rejected_winner_is_never_reported_as_honest_flat`, `..._memory_safety_finding_is_loud_...`, and `test_f4_a_genuinely_flat_run_is_still_honest_flat` (G3 not weakened) |
| **F5** | After a fallback, `sanitizer_gate` described the **rejected** config; the emitted config's own status was never stated. G2 held with an asterisk. | The gate runs on whatever is emitted, **including the reference fallback**. A skipped gate says `emitted config not gated: <reason>`. | `test_f5_sanitizer_gate_field_always_describes_the_emitted_config`, `test_f5_missing_gate_is_recorded_as_not_run_and_never_as_a_pass` |
| **F6** | A `.pyx` that failed to compile produced `built 0/17` and `cythonize_fail` — no compiler diagnostic, no log path, and the run continued to the next stage. | Aborts immediately with the compiler's own words and the path to the full build log. A *partial* failure still continues. | `test_f6_total_build_failure_aborts_with_the_compilers_own_words` |
| **F7** | Three version strings: `1.0.0-rc0+research-preview`, `cytune v0`, `cytune-certificate/v0`. | One, from `cytune.__version__`, used by the banner, `doctor`, and the certificate schema. | `test_f7_one_version_string_everywhere` |
| **F8** | `delta_probe = 2.65` and `MEASURED SPEEDUP: 1.27x` with nothing connecting them. | A `WHY THE PROBE NUMBER AND THE SPEEDUP DIFFER` section, plus a one-line caveat at probe time. | `test_f8_certificate_reconciles_delta_probe_with_the_measured_speedup` |
| **F9** | `not found: <path>` for either argument — a user who mistyped one of two could not tell which. | Both paths validated up front; each problem names its argument; swapped arguments are diagnosed. | `test_f9_path_errors_name_which_argument_was_wrong`, `..._both_bad_paths_...`, `..._swapped_arguments_...` |
| **F10** | `doctor` spliced raw multi-line subprocess stderr into a formatted field. | Flattened and truncated. | `test_doctor_flattens_multiline_subprocess_output` |
| **F11** | Failed runs left `.cytune/<name>/` behind; a bad `--driver` had already vendored `kernel.pyx`. | The workspace is created only when there is something to put in it, and the driver contract is checked before anything is copied. | `test_f11_a_failed_run_leaves_no_workspace_behind`, `..._a_bad_driver_does_not_leave_a_vendored_kernel` |
| **F12** | An unrecognised `tune` flag printed the **top-level** usage, so `--allow-fast-math` was not visible. | `tune`'s own usage, plus a pointer to `cytune tune --help`. | `test_f12_unknown_tune_flag_shows_the_tune_usage_not_the_top_level_one` |
| **F13** | `--rig quiesced` was invalid; the quiesced value was spelled `auto`. | `quiesced` is a real choice and **requires** the quiesced rig, refusing rather than silently degrading. | `test_f13_rig_quiesced_is_a_valid_choice` |
| **F14** | README said the routing policy was "interim"; every certificate said "P3-VALIDATED". | One sentence, in `routing.LABEL`, used verbatim everywhere. | `test_every_route_carries_the_provenance_label_including_its_limit` — asserts the overclaiming wording **cannot come back** |
| **F15** | The label claimed "RQ-P2 acceptance has not run" after `RQP2_ACCEPTANCE.json` existed. | Gone with F14; the same test asserts the stale clause cannot return. | as F14 |
| **F16** | Certificates used `rule R2`, `PREREG §9.2`, `IF_probe`, `tau`, `§301` with no glossary. | A `GLOSSARY` section inside the certificate defining every term it uses. | `test_f16_certificate_defines_its_own_insider_terms` |
| **F17** | On a fallback, `endpoint_separation` compared the reference against **itself** and reported "the sub-measures OVERLAP". | Reported as `not_applicable` with the reason, and still computed for real comparisons. | `test_f17_no_vacuous_separation_claim_when_the_winner_is_the_reference`, `..._is_still_computed_...` |
| **F18** | `n_candidates: 17, n_excluded_fast_math: 12` — no denominator, no sum. | `emittable candidates : 10 of 29 feasible (19 excluded by policy: fast_math=12, fp_contract=7)`, with the denominator stated in the JSON. | `test_f18_selection_counts_name_their_denominator_and_sum` |
| **F19** | FMA contraction was emitted **by default** while `-ffast-math` needed a flag. Two FP-semantics changes, two consent models. | Both opt-in: `--allow-fast-math`, `--allow-fp-contract`. Default is FP-strict and the certificate says so. | `test_f19_fp_contract_is_excluded_from_emission_by_default` (a 5×-faster forbidden config), `..._fast_math_optin_does_not_silently_grant_contraction`, `test_strict_default_admits_no_fp_semantics_change_at_all` |
| **F20** | `-march=native` emitted with no portability warning. | A `PORTABILITY WARNING` block, and `--portable-flags` to restrict *selection* to `-march=x86-64`. | `test_f20_march_native_carries_a_portability_warning`, `test_f20_portable_flags_excludes_native_from_selection` |
| **F21** | The FP-semantics block fired on a pure-integer kernel. | Fires only when the emitted config changes FP semantics **and** the kernel plausibly has FP work; otherwise a one-line qualifier. See **K1** for the heuristic's limit. | `test_f21_fp_block_is_muted_when_the_kernel_has_no_floating_point_work`, `..._still_fires_when_there_is_fp_work` |

### Found during this pass, by running the fixes

| # | what | proof |
|---|---|---|
| **P1** | With the gate extended to the fallback (F5), a kernel whose **reference** reported made cytune emit a reporting config under the words "the best safe choice". Now: `EMIT: NOTHING` and a `NO SAFE RECOMMENDATION` verdict. | `test_g2_a_reporting_emitted_config_is_never_called_safe`, `test_g2_both_a_rejected_candidate_and_a_dirty_baseline_are_reported` |
| **P2** | On a run where the search's winner did not clear the emit margin, the certificate said `EMIT: the reference configuration (unchanged)` and printed `boundscheck=False, wraparound=False`. **The words and the directives disagreed.** The emit decision is now settled *before* gating, and an invariant refuses to build a certificate that emits a rejected winner. | `test_a_non_improvement_certificate_always_emits_the_reference_itself`, `test_certificate_refuses_to_be_built_with_a_rejected_winner_still_emitted`, `test_assess_*` |
| **P3** | Argparse's usage errors exited **2**, colliding with the documented `2 = HONEST-FLAT`. | `test_usage_errors_do_not_collide_with_the_honest_flat_exit_code` |
| **P4** | A `NOT RUN` gate left the verdict line unqualified, so a reader (or a script) stopping at the summary saw a plain "improvement" for a recommendation nobody memory-checked. | `test_a_not_run_gate_degrades_the_verdict_line_itself` |

### Found by the FRESH-TESTER re-test — a second cold reader, docs-only

A new tester with no memory of the work, allowed only `README.md`, `docs/` and the CLI, ran the
whole acceptance again and returned **"a stranger would succeed"** — plus 13 more findings. All 13
are fixed; four of them were honesty defects.

| # | was | now | proof |
|---|---|---|---|
| **R1** | the "full sanitizer report" the certificate points at was the shadow-byte legend, cut off mid-token: no `ERROR:` line, no faulting address, no stack trace, no source location. The tool told you your kernel had a memory bug and then handed you nothing to act on. | The excerpt anchors on the first `ERROR:`/`runtime error:` marker and takes forward; the report file carries the full output. It now opens with `ERROR: AddressSanitizer: heap-buffer-overflow`, `READ of size 8 at 0x…`, and the stack frame in your kernel. | `test_r1_sanitizer_excerpt_keeps_the_actionable_head_not_the_shadow_map`, `test_r1_report_file_carries_the_full_output`; live at `prod_runs/retest_fixes/sanitizer_report_1392.log` |
| **R2** | `--allow-fast-math` alone emitted `-ffp-contract=fast` while both the certificate and `fp_semantics.fma_contraction_permitted` said contraction was **not** permitted. A user scripting on that field would compile with contraction. | The emitted flag string is the ground truth: `fma_contraction_permitted` is true whenever the flags permit it, with `fma_contraction_implied_by_fast_math` distinguishing how, and the certificate explains the subsumption. | `test_r2_fast_math_certificate_does_not_deny_the_contraction_it_emits` |
| **R3** | `--dry-run` borrowed verdict exit codes (0 for a flat kernel, 2 for a tunable one — so the documented `case $?` recipe took the "verified speedup, safe to use" branch on a memory-unsafe kernel), and `--dry-run --json` printed nothing at all. | A dry run has no verdict, so it has its own code (`EXIT_DRY_RUN`) and emits a `cytune-dry-run/1.0` JSON object. | `test_r3_dry_run_has_its_own_exit_code_and_never_borrows_a_verdicts`; live in `prod_runs/retest_fixes/verify_console.log` |
| **R4** | cached probe rows were reused across a changed `--target-ms`, so a 40 ms run reported a **byte-identical** `delta_probe` to the 65 ms run that actually measured it. A screening number attributed to a workload it was never measured on. | The calibration is part of the cache key; stale rows are archived, counted and announced, and the probe re-measures. Builds are still reused, so a repeat run stays fast. | `test_r4_a_changed_calibration_discards_stale_measurements`, `test_r4_builds_survive_a_calibration_change`; live: `calibration CHANGED … discarding 17 cached measurement rows` |
| **R5** | the "ready-to-paste `setup.py` fragment" had no newline after its banner comment, so the first import was swallowed and the snippet raised `NameError`. | Fixed; the test `compile()`s the snippet. | `test_r5_build_snippet_is_syntactically_valid_python`, `..._with_the_march_native_warning` |
| **R6** | the live narration called the candidate "the EMITTED config" *before* it was rejected. | It is "the search's best candidate" until it survives the gate. | live: `§1.4 sanitizer gate on the search's best candidate (config 1392, ASan+UBSan)` |
| **R7** | `--rig portable` on an already-quiesced host printed "The host was not quiesced" — a false statement of fact about the user's machine. | "Measurement was forced to portable by `--rig portable`, so the host's quiesced state (whatever it is) was not used or verified." | `test_r7_forced_portable_does_not_claim_the_host_was_unquiesced` |
| **R8** | `12 crash`, with no diagnostic, on the run where the diagnosis mattered most — those 12 were exactly the configs where Cython caught the same off-by-one the memory block was about. | The certificate reports the factor levels every rejected config shares: `all 12 share: boundscheck=True, wraparound=False`, with a line telling you to look at your indexing. | `test_r8_rejections_report_the_factor_levels_they_all_share`, `..._no_pattern_claimed_when_there_is_none`, `..._reaches_the_rendered_certificate` |
| **R9** | the exit-code table still documented argparse's `2` for usage errors and told scripters to disambiguate a collision that had already been fixed. | Corrected to `1`, with the dry-run row added. | `docs/USER_GUIDE.md` §8 |
| **R10** | the `0.0808` portable emit margin read as a property of the *flag*; forcing portable on a quiesced host gives `0.0200`. | Labelled as a property of an unquiesced **host**, with the distinction spelled out. | `docs/USER_GUIDE.md` §5 |
| **R11** | `PYTHONPATH=src` is relative and resolves only from the repo root — which is the one directory the user's kernel is not in. The one guess the fresh tester had to make. | The absolute form is shown in both the README and TROUBLESHOOTING. | `README.md`, `docs/TROUBLESHOOTING.md` |
| **R12** | `doctor` leaked `[Errno 2] No such file or directory: 'bash'` into a user-facing field — the same class as F10, on a path F10 did not cover. | "bash was not found on PATH". | `test_r12_rig_reports_a_missing_bash_in_english` |
| **R13** | ~60 s of total silence at `[1/6]`, the first thing a new user sees, while TROUBLESHOOTING claimed every stage prints elapsed time. | The stage says what it is doing and why it is the slow one. | `cli.py` ingest line |

### Newly proven paths (T4)

Previously untested, now exercised end-to-end — evidence in the productisation report:

- the sanitizer **NOT-RUN** path (`"ran": false, "clean": null`), the largest open gap and the same
  class as D23;
- `--allow-fast-math` opt-in;
- `OUTPUT_CLASS = "float"` and the tolerance oracle;
- verdict repeatability across two runs of the same fixture.

---

## K-12 — C1's noise floor is estimated from the driver's own wall clocks (adversarial finding)

**Status: known, documented, not fixed. Reported by an adversarial pass, 2026-08-12.**

`certify.corroborate_ratio` checks a claimed speedup against the parent process's wall clock. Its
budget is `max(0.5 × claimed_gain, 3σ)`, and when that budget exceeds what the test could ever
detect it returns `corroborated: None` — "no power to decide" — which is a pass-through, not a pass.

**The weakness.** The per-configuration `σ` is a MAD estimate over **n = 3** overhead values, all
derived from wall clocks that **the driver's own process reported**. A driver whose reported wall
clocks are noisy enough inflates σ, which inflates the budget, which trips the no-power cutoff — and
the claimed speedup is then certified with `wall-clock corroboration: NOT CHECKED` beside it. An
adversary demonstrated a certified `IMPROVEMENT 2.000x` on a kernel whose true speedup was 1.000×.

Note the screen-overhead term of the same formula *does* require n ≥ 4 (`_robust_sigma`); the
per-configuration term has no minimum-sample guard.

**Why it is not fixed here.** Adding a minimum-n guard changes the C1 budget, which changes
verdicts, which would invalidate every measured number in `results/release/LAUNCH_REPORT.md` — those
were measured with the current formula. `docs/CONTRIBUTING.md` sets the bar for an engine change:
pre-registration, offline evaluation against the frozen tables, and the fleet gate. This one has not
had it, and shipping it on an adversary's say-so would be exactly the shortcut this project refuses.

**What changed instead.** The certificate's own attestation used to say C1 "catches ANY claimed
speedup on a kernel that is really flat". That sentence was false, and it was false *in the document
the claim appears in*. It now states the limit, including that a noisy driver can disarm the check
and that `NOT CHECKED` means the speedup is uncorroborated.

**What protects you meanwhile.** This requires a driver that misreports. Your driver is already
inside the trust boundary — `docs/GUARANTEES.md` N8 says so, and the certificate says it is evidence
to whoever controls the driver and *not* evidence to a third party. C1 is a defence against an
honest driver on a busy machine, not against a hostile one.

## K-13 — a directive is only checked for inertness when a single-bit-flip pair was built

**Status: known, documented, not fixed. Same adversarial pass.**

`binding.degeneracy` classifies a directive as live or inert by comparing two builds that differ in
exactly that one directive. If the measured set contains no such pair — which a Hamming-distance-≥2
screening design produces *by construction* — every directive comes back `undetermined`, and I4.2's
`total_collapse` check does not fire because the sources genuinely differ.

`directives_undetermined` is computed and then dropped: it is not in `binding.provenance`, not in
`render_provenance`, and not in the schema. So a reader sees an empty inert list and no signal that
the question was unanswerable.

The probe design cytune actually ships does contain flip pairs, so this is latent rather than live
today. It is recorded because "the check is only performed when a particular pair happens to have
been built" is exactly the shape of finding this project has learned to write down.

## K-14 — the PROVENANCE block is as true as its caller

**Status: known, documented, not fixed. Same adversarial pass.**

`assert_emission_bound` returns the artifact hash it bound; `cli.py` discards the return value and
the `provenance` dict is assembled separately. So I4.1 binds the **decision** and nothing binds the
**document** — a one-line drift in which config id is passed to `binding.provenance` would produce
a certificate whose PROVENANCE names an artifact that was never built, under that block's own line
"every hash here is of a file this run produced", with every invariant green.

This needs a defect in `cli.py` rather than hostile input. It is the class `src/cytune/paths.py`
exists for, and it is listed here because no invariant currently compares the rendered block against
the artifacts it names.

## K-15 — a `preset` in `.cytune.toml` overrides that same file's `target_ms`, and the certificate blames a flag

**Status: known, documented, not fixed. Breaker agent, 2026-08-12.**

`config.resolve` applies preset values ahead of file values whenever the preset is not `standard` —
including when the preset itself came from the file. So a `.cytune.toml` saying
`preset = "quick"` **and** `target_ms = 100.0` produces `target_ms = 30.0`, with one file value
losing to another file value.

Worse, the provenance string is hardcoded to `f"--preset {preset_name}"` regardless of where the
preset came from, so the certificate's answer to "where did this setting come from" names a command
line flag that was never typed. A reader auditing a certificate cannot distinguish "someone typed
`--preset quick`" from "a checked-in config file did it".

The documented precedence (`docs/USER_GUIDE.md` §13.4) is *flag > preset > file > default*, and
this is the case where "preset" and "file" are the same file.

## K-16 — two identical runs can emit different directive headers, and a near-tie is not disclosed

**Status: known, documented, not fixed. Breaker agent, 2026-08-12.**

Three clean runs of one kernel, identical flags, fresh workspace each, emitted config **786** twice
and config **210** once. The winner endpoint times were within **0.13 %**, so the choice is
noise-determined — and the two headers differ in `-O` level, `wraparound` and `nonecheck`, which
that run's own `factor_degeneracy` listed as **live** directives.

The speedup claim is honest in both cases. What is missing is disclosure: the certificate has no
runner-up field and no tie margin, so a user who re-runs to confirm gets a different header with no
indication that the two were within noise of each other.

This is the discrete-regret property described in `results/release/LAUNCH_REPORT.md` §1.2 seen from
the user's side rather than the fleet's. A tie-margin field on the certificate is the obvious fix and
is not built.

## K-17 — a read-only workspace raises an unhandled `PermissionError`

**Status: known, documented, not fixed. Breaker agent, 2026-08-12.**

`chmod 500` on the workspace produces a bare traceback from `session.py::_ensure` rather than a
cytune-level message. Honest — nothing is silently wrong — but it is the one environment failure
`doctor`'s workspace row promises to pre-check, and it does not.

## K-18 — no way to demand more than the emit margin (`--min-speedup` / `--fail-on-thin`)

**Status: known, documented, not fixed. Senior power-user agent, 2026-08-12.**

The emit margin is `max(2 × combined endpoint CV, 2 %)`, computed from the run's own noise. It is a
floor, not a policy: a run can be certified `IMPROVEMENT` at 1.0259× having cleared a 1.0236× bar
with an endpoint separation of 0.0107 %, and the certificate labels that separation `THIN`.

`thin` **is** in the JSON (`measurement.endpoint_separation.thin`), so CI can act on it — the agent
did, in four lines of bash. What is missing is a flag: no `--min-speedup`, no `--fail-on-thin`, and
no way to make a thin result exit 3 instead of 0.

Not added here because it is a new decision rule about what cytune certifies, and this project puts
those through pre-registration rather than through a good suggestion. The workaround is one `jq`
expression and it is documented in the agent's evaluation.

## K-19 — the improvement path does not report what the emission policy cost

**Status: known, documented, not fixed. Senior power-user agent, 2026-08-12.**

On the improvement path the certificate reports a *count* of policy-excluded candidates
(`emittable candidates: 9 of 25 feasible (16 excluded by policy: fast_math=9, fp_contract=7)`) but
never the **ratio of the best excluded config**.

On the agent's kernel that concealed a 2×: the strict run certified 1.0259×, and the same kernel
with `--allow-fp-contract` measured **2.0036×**. cytune had measured those configurations and had
the numbers in hand; the strict certificate said only that seven were excluded.

`OBSERVED BUT NOT RECOMMENDED` exists for exactly this kind of disclosure but is scoped to the flat
route. Extending it to the improvement path is the obvious fix and is not built.

This is the same shape as D26/D28/D30 — **the tool had the number and did not report it** — which is
why it is written down rather than left as a nice-to-have.
