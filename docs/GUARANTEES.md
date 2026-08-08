# What cytune guarantees — and what it does not

Every guarantee names the evidence that its **failure path** was exercised, or says plainly that it
wasn't. A guarantee whose failure path has never fired is a claim, not a guarantee — that is the
lesson of this project's Phase P, and it is applied here to its own product.

Two kinds of evidence appear below:

- **live** — a real end-to-end run, archived under [`../results/usertest/`](../results/usertest/).
- **test** — an automated test that drives the failure state, in `src/cytune/`. Run them with
  `pip install -e ".[test]" && pytest -q src/cytune`.

---

## Guarantees

### G1 — It will not recommend a configuration that produces wrong output

Every candidate the search selects is re-measured at the endpoint tier and re-checked against a
golden output captured from your reference build. A config that passes the fast screen and fails
here is never emitted. Comparison is bit-exact (sha256 of the canonical array) for `OUTPUT_CLASS`
of `int`/`bool`, tolerance-based for `float`. A determinism gate runs the reference 5 times and
checks bit-identity first — if your kernel is not deterministic, cytune refuses rather than
guessing a tolerance.

**Exercised.** *live:* on `t3_oob`, 12 of 41 measured configs were rejected as incorrect and none
reached the output (`runs/t3_oob/certificate.json` → `correctness.configs_rejected_infeasible`).
*test:* `test_cytune_plan.py` drives `confirm_winner` on an endpoint failure and asserts the
fallback; `test_cytune_product_fixes.py::test_f4_endpoint_rejection_is_also_not_flat_...` asserts
the verdict that results.

### G2 — It will not recommend a configuration the sanitizer reported on

Before certification, the config cytune is about to emit is rebuilt under AddressSanitizer +
UndefinedBehaviorSanitizer inside the pinned image and run. If either reports, the recommendation
is **withdrawn** and cytune falls back to the reference — **and then gates the reference too.**

**G2 now holds with no asterisk.** Three properties, each tested:

| property | evidence |
|---|---|
| a reporting candidate is refused and the reason recorded | *live:* `t3_oob` — `WINNER REJECTED by the sanitizer: config 1326 — AddressSanitizer, SUMMARY: buffer-overflow`, `the oracle passed it; ASan did not` |
| the `sanitizer_gate` field describes the config **actually emitted**, never the rejected one | *test:* `test_f5_sanitizer_gate_field_always_describes_the_emitted_config` |
| a config the gate reported on is never called safe — even the reference | *test:* `test_g2_a_reporting_emitted_config_is_never_called_safe`; asserts `EMIT: NOTHING` and that the words "best safe choice" cannot appear |
| a clean config still passes normally | *live:* `t2_lever` emitted `boundscheck=False, wraparound=False` — the same corner that was illegal in `t3_oob` — and the gate returned `CLEAN` |

**This was a real defect, found by a live run of the fix itself.** With the gate extended to the
fallback, a fixture whose *reference* reported (an unrelated int64 overflow UBSan caught) made
cytune emit a reporting config under the words "the best safe choice". That path now produces
`EMIT: NOTHING` and a `NO SAFE RECOMMENDATION` verdict. Recorded in
[`../results/usertest/PRODUCTIZATION_REPORT.md`](../results/usertest/PRODUCTIZATION_REPORT.md).

This guarantee exists because the study found **1,296 configurations that read out of bounds while
passing an output check** — the oracle was weakest exactly where the computation was most forgiving.
See `../logs/defects/D23.md`.

**Two scope limits, stated rather than buried.**

*Without the pinned image the gate cannot run at all* — see N1.

*And `tune`'s G2 is a NON-EMISSION guarantee, not a detection guarantee.* `cytune tune` gates the
search's best candidate and the config it emits — two configs out of 1,728. If the search's best
candidate happens not to be one of the unsafe ones, the latent bug is never exercised and never
reported. Measured directly: five runs of the same out-of-bounds fixture found it in three, because
the DOE walk's winner varied between runs (`prod_runs/t3_clean`, `prod_runs/retest_fixes` — verdict
`no-safe-improvement` in three, `honest-flat` in two, with the emitted reference gated CLEAN each
time). **A clean `tune` run is not evidence your kernel is safe.** What is guaranteed is the
converse: if the gate reports, that config is not emitted.

### G2b — `cytune audit` makes detection deterministic

That limit is why `audit` exists. It does not tune and does not time anything; it builds a
**pre-registered risk set** under ASan+UBSan and reports which directives are safe to disable for
your kernel. Same kernel, same set, same verdict, every run.

**Exercised.** *live:* six consecutive runs of the same out-of-bounds fixture, **6/6 detected**,
producing a byte-identical verdict structure (one sha256 across all six, the last on the released
build) — against `tune`'s measured 3/5. Archived in [`../results/release/audit_runs/`](../results/release/audit_runs/).

The risk set is: the reference, each of the four risky directives flipped singly, **the
boundscheck+wraparound pair**, and the two all-checks-off corners the Phase-P study audits.

> **The pair is the reason this works, and it is not derivable from the singles.** With
> `boundscheck=False` but `wraparound=True`, `a[-1]` is rewritten to `a[n-1]` — in bounds, legal,
> CLEAN. With `wraparound=False` but `boundscheck=True`, the index raises before it can read. Only
> both-off reads before the buffer. A per-directive risk set would have missed D23, the exact defect
> the feature exists to catch. `test_the_risk_set_contains_the_d23_pair` pins it.

**Scope, in the report itself:** `audit` checks the configurations in that set, on the inputs your
driver generates. A clean audit is evidence, not proof — **N1 still applies**. What a *report*
means is definite: that configuration commits a memory-safety error and cytune will never emit it.

### G3 — It will say "no improvement found" rather than invent one

On a flat landscape cytune skips the tuning budget entirely and emits your reference configuration.
The fastest config it happened to see is reported as an **observation, explicitly not a
recommendation**: the minimum of a small sample is biased low when nothing really differs.

**Exercised.** *live:* on `t1_flat` (a DRAM-latency-bound pointer chase) the probe's fastest config
measured **1.0029× faster at the endpoint tier** and cytune declined to recommend it. *test:*
`test_f4_a_genuinely_flat_run_is_still_honest_flat` pins that adding the NO-SAFE-IMPROVEMENT
verdict did not weaken this — a run with nothing refused is still honest-flat, on both flat routes.

**And it no longer over-applies.** `HONEST-FLAT` used to also cover "a faster config was found and
refused", which told a user their kernel had no headroom when the truth was that all of its
headroom was unsafe. Those are now different verdicts (F4).

### G4 — Every floating-point-semantics change is opt-in

Two axes, two flags, both off by default: `--allow-fast-math` (`-ffast-math`) and
`--allow-fp-contract` (`-ffp-contract=fast`). Neither changes what is **accepted** — an opted-in
config is still emitted only if it passes the same oracle. `-ffp-contract` is always explicit in
the emitted flags because GCC's default is `fast`.

**Exercised.** *test:* `test_f19_fp_contract_is_excluded_from_emission_by_default` drives the
failure path — a contraction config that is **5× faster** and must still not be chosen — and
`test_f19_fast_math_optin_does_not_silently_grant_contraction` pins that one opt-in does not smuggle
in the other. *test:* `test_strict_default_admits_no_fp_semantics_change_at_all` checks all 1,728
configs. *live:* see the T4 proof runs in the productisation report for the `--allow-fast-math`
opt-in path and the `OUTPUT_CLASS="float"` tolerance oracle.

**This changed in this pass.** Contraction used to be emitted by **default** while `-ffast-math`
required a flag (finding F19).

### G5 — No flag can loosen G1, G2 or G3

Every flag added for configurability narrows the candidate set or changes what is *reported*;
none reaches the gates. The emission policy is a pure filter, and
`test_policy_flags_only_ever_narrow_the_candidate_set` checks over the **whole 1,728-config space**
that the strict default's allowed set is a subset of every looser policy's, and that
`--portable-flags` only ever removes. `--apply` refuses on anything that did not pass the gate
cleanly (`test_apply_refuses_when_the_gate_did_not_run`).

**The `CYTUNE_SANITIZER_IMAGE` claim was FALSE and the behaviour was changed to make it true.** This
page previously said the override "can only make the guarantee weaker and say so — never turn a
report into a pass", citing a test that asserted on hand-written dictionaries and never pointed the
override at an image. The adversarial campaign pointed it at a stub whose `python3` echoes one JSON
line and turned a kernel whose real §1.4 gate returns `SANITIZER_REPORT` into `clean: true`, under
the words "the best safe choice".

A clean result from an unpinned image is now **not treated as a pass**: the certificate records
which image gated it, the "safe" wording is withheld, `--apply` refuses, and invariant I1.6 enforces
it. The override still does its job — exercising the NOT-RUN path — and still cannot suppress a
report. `test_cytune_h6.py`, eight tests, each driving the failure.

**`--preset` was the first new flag added since G5 was written down**, and it is checked the same
way: `test_no_preset_can_touch_a_guarantee` asserts over the preset *table* that no preset sets a
guarantee-bearing field, so a bad preset fails when it is defined rather than when someone happens
to use it. A preset scales the routed search budget and the workload size; it cannot reach the
oracle, the gate, the emission policy or the emit margin.

### G7 — A certificate that contradicts itself is never emitted

Before anything is printed or written, the assembled certificate and its rendered text are checked
against each other and against the emitted config id. On violation cytune **raises and emits
nothing** — there is nothing to salvage in a document that disagrees with itself.

This exists because of a defect class this project kept rediscovering one instance at a time: P2
(the EMIT block claimed the reference above a non-reference header), R2 (`--allow-fast-math`
emitted `-ffp-contract=fast` while the JSON field denied it), P1 (a reporting config emitted as "the
best safe choice"), P4 (a not-run gate left the verdict unqualified). None was a broken function;
each was two correct components disagreeing, with nothing whose job was to notice.

**Exercised.** *test:* `test_cytune_coherence.py` drives a violation of each of the nine checks and
asserts the refusal, plus controls asserting an honest certificate passes. The invariants are
registered with stable ids in `cytune/invariants.py`, and `test_cytune_invariants.py` fails if an
invariant is enforced without an entry, or registered without being raised.

**It found two live holes when it was written.** The property sweep over the outcome space showed
`build_certificate` would still assemble a P2-shaped document if any caller forgot to demote a
non-clearing winner, and that the EMIT line plus three summaries asserted "best safe choice" under a
gate that had not run. Both are fixed at their source.

### G6 — Every number recomputes

Every certificate carries a `RAW:` pointer to the `table.jsonl` it was computed from, plus a
machine-readable `certificate.json`. Sanitizer reports are written out in full next to it.

---

## Not guaranteed

### N1 — A clean sanitizer run is not proof of memory safety

`sanitizer_gate.clean == true` means **no error was detected on the inputs your driver generated,
for the one configuration cytune emitted.** ASan does not see errors on code paths your inputs
never take, and it checks one config out of 1,728.

`clean` is three-valued: `true`, `false`, or **`null`**. `null` means the gate could not run — most
often because the pinned image is absent — and the certificate records it as **NOT RUN**, in those
words, with the D23 explanation. *Not-run is not a pass.* If you take one thing from this page,
take that.

**This path is now demonstrated end-to-end** (T4.19): a full `tune` run with the gate pointed at a
non-existent image, showing `"ran": false, "clean": null` in the certificate and the loud NOT-RUN
block. Evidence in the productisation report. It was the largest open gap after the first
acceptance test, and it was the same class as D23 — a gate whose failure path had never fired.

### N2 — The recommendation is not optimal, and here is what that costs

It is the best configuration **found within the budget** — 17 probe configs plus a 15–24 config
search, out of 1,728. No run searches exhaustively.

**Measured, on real library code.** The nine Dataset-R anchors are modules from scipy and
scikit-learn whose full 1,728-config tables were measured exhaustively by the Phase-P study. cytune
was run end-to-end on all nine and its answer compared against the frozen tables:

| | |
|---|---|
| configs measured | 33–49 of 1,728 (~2%) |
| **median regret** | **+1.41%** |
| **worst regret** | **+5.41%** (`elkan`) |
| best case | `csr` — found the exact optimum, rank 1 of 1,152 allowed configs |
| verdicts | 9 of 9 `improvement`, every emitted config sanitizer-CLEAN |
| wall clock | 4–17 min per anchor |

Regret is `time(emitted) / time(best allowed) − 1`, with both times taken from the **same frozen
table at the same measurement tier**, over the configs cytune was permitted to emit under the
default FP-strict policy. Full table and method:
[`../results/release/V1_RELEASE_REPORT.md`](../results/release/V1_RELEASE_REPORT.md).

Two honest caveats. The denominator is a screen-tier sample minimum over ~1,150 configs and is
therefore biased *low*, which makes these regret figures **over**-estimates — the direction that
understates cytune. And nine kernels from two libraries is not a general claim about all Cython
code.

### N8 — Your driver is inside the trust boundary; it owns the clock

**Found by the adversarial campaign, and this page previously implied the opposite.**

`_vendor/measure_child.py` loads your driver with `exec_module` into the very process that calls
`perf_counter_ns()` around it, computes the median, decides the oracle bit, and prints the JSON the
host parses. A twelve-line driver that replaces `time.perf_counter_ns` at import produced a
certified `IMPROVEMENT`, `MEASURED SPEEDUP: 5.0000x`, separation confirmed, sanitizer CLEAN, exit 0
— on a kernel where no configuration is faster than any other.

cytune measures *your kernel, called by your driver*. If the driver misreports, cytune faithfully
certifies the misreport. For the real use case — you tuning your own code — that is self-deception
rather than an attack, and it is the same boundary as "cytune executes your module and your
driver". It is stated here because a certificate is a document people forward, and it did not say
the driver was inside the boundary.

**Mitigation, and exactly what it does and does not catch.** The parent process brackets the whole
child with its own clock, which the child cannot reach. Two checks use it:

- `worker.implausible_timings` flags a child reporting `K × median` **greater** than the wall time
  that elapsed. That is the over-claim half, and it has no false positives.
- `certify.corroborate_ratio` (**new in 1.0.0**) attacks the under-claim half, which is the half a
  speedup is manufactured from. The winner and the reference run the same driver, the same `K`, the
  same inputs, in the same image, so their *non-timed remainders* (`wall − K × median`) must differ
  by exactly `warmup × (t_win − t_ref)` and by nothing else. When the residual exceeds a budget
  derived from the run's own measured process-noise spread, the speedup is **withheld**, the verdict
  becomes `no-safe-improvement`, and the certificate says why.

**Its power, measured rather than asserted.** For a true speedup `r_true` reported as `r_claim`,
the unexplained fraction of the claimed gain is
`(1 + warmup/K) x (1/r_true - 1/r_claim) / (1 - 1/r_claim)`, because the untimed warmup calls pay
the real cost too and a driver cannot separate them from the timed region. So:

| a driver claiming | is caught whenever the true speedup is below |
|---|---|
| 1.5x | 1.24x |
| 2x | 1.40x |
| 5x | 1.84x |
| 10x | 2.06x |
| 100x | 2.30x |

The entire **"this kernel is flat and the driver says otherwise"** class — which is the demonstrated
H1 attack — is caught with more than a factor of two to spare, at every claim size. **Inflating an
already-large real gain is not caught:** a genuine 2.5x can be reported as 5x, or a genuine 3x as
100x. That is a real blind spot and it is pinned by
`test_cytune_binding.py::test_c1_the_blind_spot_is_real_and_is_not_hidden` rather than left to be
discovered.

The threshold cannot simply be tightened. An honest 9.85x run left 38 % of its claimed gain
unexplained — 53 ms of residual against the run's own 10.2 ms process-noise sigma — so a stricter
budget would withhold real speedups, and withholding honest results is the failure direction this
product cannot take.

**And one thing no timing check can catch.** A driver can see which module it was handed. One that
does *genuinely more work* for the reference burns real wall clock, so every relation above holds
and the certificate is a true statement about a rigged comparison.

**Do not treat a cytune certificate as attesting a speedup to a third party who does not trust the
driver.** Since 1.0.0 the certificate itself says so, in its `attestation` block, because
certificates get forwarded and `SECURITY.md` does not travel with them.

### N9 — A `# cython:` header that pins a tuned directive is REFUSED, not tuned

Cython's file header overrides the `-X` flags the builder uses. On a module carrying
`# cython: boundscheck=False`, all 32 directive combinations compile to byte-identical C — measured
in the pinned image — so the search runs, times 33 configurations, picks a winner and certifies
directives that were never applied, including calling config 288 "Cython's safe defaults" when it
was built with the checks off.

The coherence gate cannot see this: I1 verifies the document against the config id, and the config
id was never what got built. So it is caught at **ingest** and the run is refused, naming the file
and the line. Headers that pin directives cytune does not vary (`language_level`, `cpow`, …) are
left alone.

**Widened in 1.0.0, in two directions.**

1. The check now scans the **whole module tree**, not only the `.pyx` you named. Real modules
   `cimport` siblings, and a header in a `.pxd` defeats the search for every file that includes it.
2. A generic detector backs it up. `binding.degeneracy` hashes the generated C per directive
   combination and reports which directives never changed it — by name, without knowing the
   mechanism, so a `compiler_directives=` block or an included `.pxi` is covered by the same
   observation. Total collapse (every combination producing identical C) is **refused** as I4.2.

   **A measured caveat, because it changes what the generic check is worth.** The original H12
   header pins two of the five directives, and the other three still change the generated C — so
   the partition does *not* collapse to one class and the total-collapse rule does **not** fire on
   it. It reports `boundscheck` and `wraparound` as inert, which is real information, but the
   refusal comes from the tree-wide header check. Verified end to end against real Cython in
   `test_cytune_binding.py::test_the_degeneracy_check_names_the_directives_a_header_neutralised`.

The README had warned against this for two releases. A warning did not stop it — which is precisely
the difference between a claim and a guarantee. `test_cytune_h12.py`, `test_cytune_binding.py`.

### G8 — Every claim is bound to the artifact that produced it

**New in 1.0.0, and the reason this release exists.** Every check before it — the whole I1 family —
recomputes its ground truth from `emitted_config.config_id`, so it can prove the document is
internally consistent and can never prove the document is about the run that happened. H12, H6 and
H1 were three instances of that one gap.

Four invariants close it, and their ground truth is a hash of a file rather than a function of an
id:

| id | what it binds |
|---|---|
| **I4.1** | the emitted configuration's `.so` is byte-identical to the one the endpoint tier timed — on **both** sides of the ratio, since a forged reference manufactures a speedup as well as a forged winner |
| **I4.2** | the directives cytune varies actually change the generated code |
| **I4.3** | the sanitizer verdict is about this configuration, this source tree, and the pinned toolchain **by digest** — `podman tag` cannot buy a pass |
| **I4.4** | a timing reported as decision-grade carries the rig fingerprint `measure_wrap` verified for it |

The certificate carries a `PROVENANCE` block with the emitted artifact hash, the image digest, the
rig fingerprint, and how many distinct binaries were built from how many generated sources. Every
one of those is a hash of something on disk. `binding.py`, `test_cytune_binding.py`.

### N3 — Nothing transfers to other hardware

Every measurement, and every number in `../results/`, comes from one machine: an Intel i3-10100F
with one pinned toolchain image. The emit margin was calibrated against *this* rig's noise.

`-march` is in the search space, so `-march=native` can be emitted. cytune now warns when it does,
and `--portable-flags` restricts selection to `-march=x86-64` so you can get a fleet-safe answer
that was actually measured under baseline flags (F20).

### N4 — Routing is DOE-unconditional, and here is why

cytune ships **one search algorithm**, not a router. Every routing rule resolves to DOE or to "skip
tuning".

That is a result, not an oversight. The study tested routing on 18 kernels held out from
everything: at four of five budgets, picking an algorithm per kernel type performed *identically*
to always using DOE; at the fifth it performed **worse**. Bayesian optimisation lost to a fixed
statistical design in 18 of 20 cells, and on flat landscapes it was worse than random search — it
spends its budget modelling noise. `../results/PHASEP_REPORT.md` §5,
`../results/study/RQP2_ACCEPTANCE.json`.

So "routing" chooses a **budget** and decides whether to search at all. There is now **one
sentence** describing this, in `cytune/routing.py::LABEL`, used verbatim by the CLI banner and
every certificate — the README and the certificate used to contradict each other (F14), and the
label also claimed "RQ-P2 acceptance has not run" after it had (F15). Both are pinned by
`test_every_route_carries_the_provenance_label_including_its_limit`, which asserts the old
overclaiming wording **cannot come back**.

### N5 — The study behind this is incomplete

Three of four kernel categories fell short of their pre-registered sample size (achieved power
0.708 / 0.776 / 0.708 against a 0.80 target), and the study ran 20 of a planned 200 repetitions.
Non-significant findings there are **underpowered nulls**, not "no difference". The statistical
auditor's independent re-check was killed twice by service limits and has never run against the
corrected data. Full accounting: `../results/DEFENSE_SUMMARY.md`.

### N6 — Timing claims are rig-dependent

In `portable` mode the certificate says `INDICATIVE, not decision-grade` and the bar a speedup must
clear rises with the measured noise (0.0200 → 0.0808 on the acceptance runs). G1–G5 are unaffected
by rig mode; only the timing claim degrades.

### N7 — The FP-work heuristic can be wrong in one direction

The `FLOATING-POINT SEMANTICS` block is suppressed when the oracle's output class is integral *and*
no `float`/`double`/`complex` token appears in the module source. A kernel that computes in double
and returns an int would read as "no FP work". The heuristic is deliberately biased toward
over-warning, is labelled as a heuristic in the certificate, and only ever affects a *warning* —
never what is emitted.

---

## Summary

| | claim | status |
|---|---|---|
| G1 | never emits an oracle-failing config | **exercised** — live + test |
| G2 | never emits a sanitizer-reporting config, **including the fallback** | **exercised both directions, live + test**; the no-asterisk case was a real defect found by a live run and fixed. **Non-emission, not detection** — see the scope limit under G2 |
| G2b | `cytune audit` detects deterministically over a pre-registered risk set | **exercised** — live 5/5 on the OOB fixture, byte-identical verdicts, against `tune`'s 3/5 |
| G3 | says "no improvement" rather than inventing one; and no longer says it when something was refused | **exercised** — live + test |
| G4 | both FP-semantics axes are opt-in | **exercised** — test drives a 5×-faster forbidden config; live opt-in run archived |
| G5 | no flag can loosen G1/G2/G3 | **exercised** — whole-space subset test, the preset-table test, + `--apply` refusal tests |
| G6 | every number recomputes from raw | **exercised** |
| G7 | a self-contradicting certificate is never emitted | **exercised** — nine invariants, each with a firing test; found two live holes when written |
| N1 | clean ≠ safe; **not-run ≠ pass** | **the not-run path is now demonstrated end-to-end** |
| N2 | best-in-budget, not optimal | by construction |
| N3 | single hardware; `-march=native` warns | by construction + test |
| N4 | routing is effectively DOE-unconditional | measured; one wording, pinned by test |
| N5 | the study is underpowered and un-re-audited | measured |
| N6 | portable timing is indicative only | **exercised** — live |
| N7 | the FP-work heuristic can under-warn | stated, warning-only |
| N8 | **your driver owns the clock** — cytune certifies what the driver reports | **demonstrated by the adversarial campaign**; over-claims flagged, under-claims not detected |
| N9 | a `# cython:` header pinning a tuned directive is refused at ingest | **exercised** — measured in the pinned image + 16 tests |
