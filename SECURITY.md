# Threat model

Written before the adversarial campaign, not after it, so the campaign tests a stated position
rather than rationalising whatever it found.

---

## What cytune is, in security terms

**cytune executes your module and your driver. It is not a sandbox for untrusted code.**

To tune a kernel, cytune must compile it and run it. Both happen inside the pinned container image,
which is a real boundary and a useful one — but the container exists to make *measurement*
reproducible, not to contain hostile code. It runs `--network=none`, mounts the package read-only,
and mounts your workspace read-write. That is it.

If you point cytune at a `.pyx` and a `driver.py` you did not write and do not trust, you have
executed them. The same is true of `python setup.py build_ext`, `pytest`, and every build system in
this ecosystem. cytune does not change that and does not claim to.

**Not a threat we defend against:** a malicious kernel or driver damaging the machine cytune runs
on, exfiltrating data the container can reach, or consuming resources.

---

## The property that must hold under attack

**CERTIFICATE INTEGRITY.**

> cytune must never issue a certificate whose claims are false.

Everything else is negotiable; this is not. The product's entire value is that its refusals mean
something. A tool that can be made to say "verified 3.2× speedup, sanitizer CLEAN" about a
configuration that is neither is worse than no tool, because it launders a false claim through a
document designed to look careful.

Concretely, a certificate must never claim:

| claim | when it would be false |
|---|---|
| `verdict: improvement` | the configuration was not measured to be faster, or did not clear the margin |
| `sanitizer_gate.clean: true` | the ASan+UBSan gate did not actually run and pass on the emitted config |
| `correctness.*` | the emitted config did not pass the oracle at the endpoint tier |
| the emitted flags | they are not the flags of `emitted_config.config_id` |
| `fp_semantics.*` | it disagrees with the emitted flag string |
| `emission_policy` | a config outside it was emitted |

The runtime enforcement is in two layers, and the second one exists because of what the first could
not see.

**I1 — coherence.** Runs on every real run and refuses to emit a document that contradicts itself.
Its ground truth is `theta.config_of(emitted_config.config_id)`.

**I4 — binding.** Also runs on every real run. Its ground truth is a **hash of a file**.

The distinction is the whole finding of the adversarial campaign, in the hacker's own words: *every
check verifies the DOCUMENT against the config_id, and nothing verifies the config_id against the
ARTIFACT actually built, gated and timed.* A ground truth recomputed from an id can only ever
confirm the id. H12 (a header overriding the `-X` flags), H6 (a stub image printing `clean: true`)
and H1 (a driver owning the clock) are three instances of that one gap, and I1 passed all three
because all three produced internally perfect documents.

| bound | by | against |
|---|---|---|
| the emitted config's `.so` == the one timed at the endpoint tier, on both sides of the ratio | I4.1 | a stale or swapped artifact |
| the directives cytune varies change the generated code | I4.2 | a factor neutralised by any mechanism |
| the gate's config, source tree and image **digest** | I4.3 | a re-tagged or substituted image |
| the rig fingerprint behind a decision-grade timing | I4.4 | a measurement taken outside `measure_wrap` |

---

## The classes cytune cannot defend against, stated plainly

### 1. Your driver is inside the trust boundary — it owns the clock

**This section is a correction.** An earlier version of this document said, of a driver that
monkeypatches cytune internals: *"the driver runs in the container, in a fresh subprocess per
measurement; the certificate is built host-side from JSON parsed out of that subprocess's stdout.
There is no shared interpreter to patch."*

**That was false, and the adversarial campaign demonstrated it.** `_vendor/measure_child.py` loads
your driver with `importlib` `exec_module` into the very process that calls `perf_counter_ns()`
around `driver.call(...)`, computes the median, decides the oracle bit, and prints the JSON the host
parses. The host/container split is real; it is simply on the wrong side of the number. A twelve-line
driver that replaces `time.perf_counter_ns` at import produced a certified
`VERDICT: IMPROVEMENT, MEASURED SPEEDUP: 5.0000x`, separation confirmed, sanitizer CLEAN, exit 0 —
on a kernel where no configuration is faster than any other.

**What this means in practice.** cytune measures *your kernel, called by your driver*. If the driver
misreports, cytune faithfully certifies the misreport. For the actual use case — you tuning your own
code — this is self-deception, not an attack, and it is the same boundary as "cytune executes your
module and your driver". It matters because a certificate is a document people forward, and it did
not say the driver was inside the boundary. Now it does.

**Mitigation, in two halves.** The parent brackets the whole child with a clock the child cannot
reach.

*Over-claims* — a child reporting `K × median` greater than the wall time that elapsed is reporting
time that did not happen. `worker.implausible_timings` flags it, with no false positives.

*Under-claims* — reporting **less** time than elapsed, which is how a speedup is actually
manufactured. The earlier version of this document called this indistinguishable from spawn
overhead. That was too pessimistic. The winner and the reference run the same driver, the same `K`
and the same inputs, so their non-timed remainders (`wall − K × median`) must differ by exactly
`warmup × (t_win − t_ref)`. `certify.corroborate_ratio` withholds the speedup and refuses the
improvement verdict when the residual exceeds a budget derived from the run's own measured
process-noise spread.

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

**What remains, and it cannot be closed by timing.** A driver can see which module it was handed.
One that does genuinely *more work* for the reference burns real wall clock, so every relation
above still holds and the certificate is a true statement about a rigged comparison. That is the
residue, and it is what the trust boundary means.

Do not treat a cytune certificate as attesting a speedup to a third party who does not trust the
driver. **Since 1.0.0 the certificate says this itself**, in an `attestation` block, because a
certificate is forwarded and this file is not.

### 2. A kernel that behaves differently under the sanitizer build

**It can evade the gate by construction.**

The §1.4 gate rebuilds your configuration with `-fsanitize=address,undefined` and runs it. A kernel
that detects that build — through `__SANITIZE_ADDRESS__`, a timing difference, the presence of the
ASan runtime, an environment variable, or anything else — and takes a different path under it will
be gated on code that is not the code you ship.

This is not a bug to be fixed. It is what dynamic analysis is: ASan observes the execution it is
given. Detecting adversarial divergence between two builds of the same source is not a problem
cytune can solve, and a product that implied otherwise would be making exactly the kind of
unearned claim this project exists to refuse.

**The distinction that matters:** this is an *adversarial* limit, not a *buggy-code* limit. Ordinary
latent defects — the out-of-bounds read inside a reduction that D23 is about — do not detect their
instrumentation, and the gate finds them. A kernel deliberately written to behave differently under
ASan is outside the model.

`cytune audit` widens the search to a pre-registered risk set and makes detection deterministic, but
it uses the same gate and inherits the same limit.

---

## What is defended, and how

| attack | defence |
|---|---|
| a driver that monkeypatches cytune internals or the certificate builder | **PARTIAL — see limit 1 above.** The driver cannot reach the host: the certificate is built host-side, and cytune never imports the driver there (`_driver_contract_gaps` parses it as text). It DOES share the interpreter that times it. Over-claims are flagged (`implausible_timings`) and under-claims are now caught by parent-side ratio corroboration (`certify.corroborate_ratio`); a driver that does genuinely different work per configuration is not detectable and is stated as the residue |
| a `# cython:` header that pins a directive cytune varies | **REFUSED at ingest, across the whole module tree.** Cython's file header overrides the `-X` flags the builder uses. Checked in every `.pyx`/`.pxd`/`.pxi` of the tree, not only the file you named, because a header in a cimported `.pxd` defeats the search for everything that includes it (`session.check_pinned_directives_tree`) |
| a directive pinned by `@cython.boundscheck(False)` or `with cython.cdivision(True):` | **REPORTED, not refused, and the proportionality is measured.** These override -X for the code they cover, but only for that code — the rest of the module still varies. Refusing would have blocked three of the nine real scipy/scikit-learn anchors, all of which are non-degenerate. The certificate names the file, the line and the directive. Found by the focused adversarial re-run |
| a factor neutralised by some OTHER mechanism | **DETECTED generically.** `binding.degeneracy` hashes the generated C per directive combination and names the directives that never changed it, without knowing why. Total collapse is refused (I4.2). Measured caveat: a header pinning only *some* directives does not produce total collapse, so the refusal there comes from the tree-wide header check and this reports the neutralised names |
| an artifact swapped between the build phase and the measurement | **REFUSED.** Every `.so` is hashed at build and re-hashed at the moment it is timed; I4.1 refuses to emit unless they match, on both sides of the ratio. The measure phase re-verifies every artifact on entry and exit |
| a driver that hijacks its own module loader instead of the file | **NOT DEFENDED — stated.** The driver is loaded before the `.so`, so it can monkeypatch `importlib.util.spec_from_file_location` or set `KERNEL_MODULE`/`PKG_MODULE` and have the child import a different binary while the honest `.so` on disk is never touched: I4.1 matches and C1 corroborates. Named by the adversary as the undemonstrated escape from the fix below. No hash reaches it — it is the same boundary as the clock (limit 1), and the certificate's provenance note now says "the FILE the endpoint tier was pointed at" rather than "the binary that ran" |
| an artifact swapped by the DRIVER, between the hash and the load | **FIXED in 1.0.0, and the hole was in I4.1 itself.** `measure_child` loads the driver *before* the `.so`, so a driver could overwrite the winner's binary with a faster one producing identical output — and all three checks agreed: I4.1 (both hashes taken of the honest file), C1 (the fast binary really did take that long) and the oracle (identical output). A fully bound, fully corroborated forged speedup. Nothing in a measure phase writes to `_so/`, so it is now mounted **read-only** and the swap fails at the filesystem; the endpoint tier also re-hashes afterwards. Found by the focused adversarial re-run (Attack B), reproduced against the fix as `OSError: [Errno 30] Read-only file system`. `test_cytune_binding.py::test_attack_b_*` |
| a driver with side effects or global state between reps | one fresh subprocess per configuration, per-rep input regeneration, and a determinism gate that runs the reference five times and requires bit-identical output before any tolerance is derived |
| a kernel that is nondeterministic | the determinism gate refuses rather than guessing a tolerance |
| an oracle-canon that hides a wrong answer | `canon()` is the user's own; a driver that canonicalises everything to a constant is lying to itself. cytune's guarantee is *against the oracle you supplied*, and the certificate states the oracle class, the tolerance and the golden hash so the claim's scope is visible |
| `CYTUNE_SANITIZER_IMAGE` pointed at a stub | **FIXED.** The gate parses whatever JSON the image prints, so a stub *did* turn a reporting kernel into `clean: true`. A clean result from an unpinned image is not a pass: the "safe" wording is withheld, `--apply` refuses, and I1.6 enforces it. `test_cytune_h6.py` |
| the same stub, re-tagged with the pinned NAME | **FIXED in 1.0.0.** The first fix compared the image name, which `podman tag stub localhost/motifbo-env:phase1` defeats in one command. The comparison is now against the pinned **digest**, and the gate additionally attests the source tree it built (I4.3) |
| a re-tag placed BETWEEN the digest check and the container launch | **FIXED in 1.0.0, and it was self-inflicted.** The digest lookup memoises per image name and was first populated at stage `[1/6]`; the gate compared that cached value minutes later while `podman run <name>` resolved the tag live, so one `podman tag` in between made the pin answer *pinned* while a stub executed — H6 rebuilt on top of its own fix, by a cache added for speed. cytune now resolves the image **once and then runs that ID**, so the image whose digest was compared is by construction the image that ran. Found by the focused adversarial re-run (Attack A); `test_cytune_binding.py::test_attack_a_a_retag_after_resolution_cannot_redirect_the_run` |
| forcing an `improvement` verdict below the margin | the margin is computed from this run's own endpoint spread; invariant I2.1 refuses to build a certificate for a non-clearing candidate |
| smuggling an FP-semantics change past the strict default | the emitted flag string is ground truth and invariant I1.3 cross-checks every FP field against it; I2 refuses a config outside the effective policy |
| path traversal or symlinks via `--workspace` / `--apply` | `--apply` refuses on anything not gated CLEAN and writes a sibling copy unless `--in-place` is passed explicitly |

None of these defences is asserted here without a test; the mapping from claim to test is in
`docs/GUARANTEES.md` and `docs/KNOWN_ISSUES.md`.

---

## Reporting

A way to make cytune emit a false certificate is the highest-severity issue this project has, and
it is a release blocker. Report it with the module, the driver and the exact command; the
certificate alone is not enough, because the interesting part is what the inputs made it do.
