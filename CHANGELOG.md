# Changelog

All notable changes to cytune. The compatibility promise is in
[docs/COMPATIBILITY.md](docs/COMPATIBILITY.md).

---

## 1.0.0 — API freeze, and artifact binding

The first release with a frozen public interface. Two structural changes: the product now ships
standalone, and **every claim it makes is tied to the bytes that produced it**.

### The finding this release is built on

The adversarial campaign that gated `1.0.0-rc1` produced three false certificates. Its own summary
named the cause better than any of the individual fixes did:

> Every check verifies the DOCUMENT against the config_id, and nothing verifies the config_id
> against the ARTIFACT actually built, gated and timed.

H12 (a `# cython:` header overriding the `-X` flags), H6 (a stub image printing `clean: true`) and
H1 (the driver owning the clock) were three instances of that one gap, and the coherence gate passed
all three because all three produced internally perfect documents. Patching instances of a named
class and shipping is how this project has paid for the same defect four times (D22 → P2 → R2 → H\*).
So the class is closed instead: `binding.py` adds four invariants whose ground truth is a **hash of
a file** rather than a function of the configuration id. See [GUARANTEES.md](docs/GUARANTEES.md) G8.

### Behavioural changes a user must know about

These change what cytune does, not just what it says.

- **A certificate is refused unless the emitted configuration's `.so` is the one that was timed** —
  on both sides of the ratio, since a forged reference manufactures a speedup as well as a forged
  winner. (I4.1)
- **A run is refused if every directive combination produces identical generated C.** cytune cannot
  tell whether something is overriding the directives or your kernel has no code they affect, and
  it will not guess. Partial collapse is *reported*, by name, in the certificate: "`initializedcheck`
  never changed the generated C for this kernel". (I4.2)
- **A `# cython:` header is now refused anywhere in the module tree**, not only in the `.pyx` you
  named. A header in a cimported `.pxd` defeats the search for every file that includes it.
- **`@cython.boundscheck(False)` and `with cython.cdivision(True):` are detected and REPORTED** —
  the certificate names the file, the line and the directive, because the emitted header does not
  reach the code they cover. Deliberately **not** a refusal: a header neutralises a directive for
  the whole module, a decorator for one function, and refusing on decorators would have blocked
  three of the nine real scipy/scikit-learn anchors this product is validated against — all three
  of which are non-degenerate. See K15.
- **A speedup the parent process's wall clock cannot account for is withheld**, and the verdict
  becomes `no-safe-improvement`. This closes the *under*-claim half of H1 — the half a speedup is
  manufactured from. (C1)
- **The pinned toolchain is identified by DIGEST, not by tag.** The previous fix compared image
  names, which `podman tag stub localhost/motifbo-env:phase1` defeats in one command.
- **`--objective size|compile` is gone.** It was a flag whose only behaviour was to refuse. Both
  metrics are still recorded per configuration in `build_manifest.jsonl`; the user guide says how to
  rank on them. **A `.cytune.toml` containing `objective = ...` is now an unknown-key error.**
- **Re-runs actually resume.** Ingest re-copies your driver, which resets the calibration knob, so
  calibration re-derived the workload from one measurement every run — and timing noise moved the
  answer by a fraction of a percent (33831, then 33699, for an untouched kernel). The calibrated
  workload is in the measurement cache key, so **every re-run discarded the entire table**. Builds
  resumed; measurements never had, despite the documentation saying otherwise. Found by the new live
  smoke gate, not by 602 unit tests.

- **FMA contraction is opt-in.** `-ffp-contract=fast` used to be emitted by **default** while
  `-ffast-math` required a flag — two floating-point-semantics changes under two different consent
  models. Both are opt-in now: `--allow-fast-math`, `--allow-fp-contract`. The default is FP-strict
  and every certificate says so. **If you relied on the old default your emitted flags will
  change.** (F19)
- **Verdicts split.** A run where a faster configuration was found and **refused** used to report
  `HONEST-FLAT` — telling you your kernel had no headroom when the truth was that all of its
  headroom was unsafe. That is now `NO-SAFE-IMPROVEMENT`. (F4)
- **Exit codes.** `0` improvement, `2` honest-flat, `3` no-safe-improvement, `1` error. Usage errors
  return `1`, not argparse's `2`, which used to collide with honest-flat. A dry run has its own
  code and no verdict. (P3, R3)
- **The sanitizer gate runs on the emitted configuration**, including when that is your own
  reference. A gate that could not run is recorded as `NOT RUN`, which is not a pass. (F5)
- **Editing your kernel now invalidates the cache.** It previously did not: a re-run reused the
  previous kernel's `.so` and its timings.

### Added

- **`cytune init <module.pyx>`** — writes a `driver.py` from your kernel's signature, a starter
  `.cytune.toml`, and then runs the same contract check `tune` uses so you see it pass. Typed
  arguments (`double[::1]`, `long[:, ::1]`, `Py_ssize_t`) are filled in; anything untyped or
  `object` gets a loud `TODO`. It does not guess — an invented input becomes the workload your
  oracle is derived from. Writing the driver by hand was the largest remaining onboarding cost.
- **`cytune doctor --build-image`** — builds the pinned toolchain and **verifies the resulting
  digest**. A build that succeeds and produces a different image is reported as a failure, because
  that is an unpinned toolchain rather than a green checkmark.
- **A PROVENANCE block on every certificate** — emitted artifact hash, the artifact actually timed,
  toolchain image digest, rig fingerprint, and how many distinct binaries were built from how many
  distinct generated sources. Every line is a hash of a file this run produced.
- **An ATTESTATION block on every certificate** — what the document does and does not attest, and
  that it is not evidence to a third party who does not trust the driver. It lives in the
  certificate because certificates get forwarded and `SECURITY.md` does not travel with them.
- **`measurement.timing_corroboration`** — the parent process's own check on the reported ratio.
- **A live end-to-end smoke gate** (`scripts/release/smoke.sh`), wired into CONTRIBUTING as the
  pre-tag ritual. 526 tests were green while the rig returned rc=127; a suite that cannot catch
  that is not a release gate by itself. It found the resume defect above on its first full pass.
- **`cytune audit <module.pyx> --driver d.py`** — a deterministic memory-safety audit. It does not
  tune and does not time anything; it builds a pre-registered risk set under ASan+UBSan and reports
  which directives are safe to disable *for your kernel*. Measured 6/6 detection on the
  out-of-bounds fixture, against `tune`'s 3/5, because `tune` gates only the configuration it is
  about to recommend. See K6.
- **Multi-file module trees.** `cytune tune <dir>` accepts a directory holding `kernel_meta.json`
  and `closure/`. Real library code `cimport`s siblings; ingest previously accepted only a lone
  `.pyx`, which meant the product could not be pointed at the code the study measured. Found by
  running the ground-truth dogfood.
- **Certificate coherence gate (I1).** Runs on every real run, before anything is printed or
  written, and refuses to emit a certificate that contradicts itself. See
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#invariants).
- **`cytune-audit/1.0`** and a `schema` field on `cytune doctor --json`, completing the four public
  artifacts.
- **JSON Schemas** for all four, with a dependency-free validator and a test that validates every
  archived certificate.
- **The invariant registry** (`cytune/invariants.py`): every runtime invariant has a stable id, a
  function, a production call site, and a test that makes it fire.
- `docs/ARCHITECTURE.md`, `docs/CONTRIBUTING.md`, `docs/COMPATIBILITY.md`, `SECURITY.md`.

### Changed

- **Builds are ~3× faster, and the certificate is what makes that checkable.** The study's
  `campaign.build_all` cythonizes one representative per directive combination *serially*. Inside
  the study that is free — 32 serial calls out of 1,728 builds. In the product the ratio is
  inverted: a tuning run measures ~33 configurations spanning ~22 combinations, so the serial phase
  was two thirds of the work, and the build phase was **71 % of total wall clock** (csr: 496 s of
  695 s). `worker._build_all` parallelises it. Rescheduling a build is safe only if the bytes are
  identical, so that is a test rather than an argument:
  `test_cytune_binding.py::test_the_parallel_scheduler_produces_byte_identical_artifacts` builds a
  real kernel both ways inside the pinned image and compares every artifact hash.
- **The build container is pinned to the non-isolated cores**, so a parallel build cannot touch the
  measurement core. CF-1 separated the phases in time; this separates them in space.
- **The coherence gate no longer reads the rendered certificate.** It searched the text for phrases
  — and its negation heuristic once fired on "it is NOT certified safe", the sentence written to
  prevent the defect it was flagging. Runtime checks are now on structured fields, one new invariant
  (I1.10) re-renders the document from its own JSON and requires byte identity, and "may these words
  appear when this field has that value?" moved to `test_cytune_render.py`, where a negation is a
  test case instead of a lookbehind window. Five substring searches covering six sentences became
  one exact check covering every byte — which also catches `certificate.txt` on disk describing a
  different run from `certificate.json` beside it.
- **The package ships standalone.** `src/cytune` no longer imports anything from `scripts/phasep`.
  The measurement rig it needs is vendored into `cytune/_vendor/`, pinned to the study originals by
  sha256 (whole-file) or by function source text (for the three files trimmed to what the product
  reaches). A measurement container now gets exactly two mounts — the package read-only and your
  workspace — where it previously also saw the study's `scripts/` and `results/`.
- **The cache key covers every input that can change a measurement**: module source, toolchain
  image, driver, calibrated workload, `--target-ms`, rig mode, and the oracle. Invalidation says
  which one changed. Policy flags are deliberately excluded, with the reason recorded at the
  definition site — they change what is *selected*, not what a measurement *yields*.
- **"Safe" is earned by a CLEAN gate.** Summaries and the EMIT line no longer call a configuration
  "the best safe choice" when the gate did not run; they say it was not memory-checked.
- The version is single-sourced. `pyproject.toml` derives it from `cytune.__version__` instead of
  repeating it — the literal had already drifted (`1.0.0rc1` against `1.0.0`).

### Removed

Leanness is measured, not asserted. Counts for this pass:

| | before | after |
|---|---|---|
| product modules | 18 | 20 (`binding.py`, `init.py`) |
| product LOC | 5,378 | 7,022 |
| vendored rig LOC | 1,295 | 1,295 (unchanged) |
| test LOC | 4,488 | 5,455 |
| `tune` flags | 18 | **17** |
| runtime invariants | 18 | 23 |
| tests | 527 | 651 |

The product grew by 1,644 lines. Every one of them is `binding.py` (the four I4 invariants),
`init.py` (the scaffold), the parallel build scheduler, and ratio corroboration — each justifiable
in one sentence in the user guide, which was the rule. What came out:

- **`--objective size|compile`** — a flag whose only behaviour was to refuse. It cost a line in
  `--help`, a field in `.cytune.toml`, a row in the exit-code table and a section of
  TROUBLESHOOTING, for the behaviour "print an error". §6 of the user guide now shows how to rank on
  `compile_s`/`so_size_b` directly.
- **The prose-scanning half of the coherence gate** — `SAFETY_WORDING`, `_affirms`, the negation
  window, and five substring searches of the rendered certificate. Replaced by one field
  (`safety_wording_earned`), one exact invariant (I1.10), and a renderer test file.
- **Nothing else.** `examples/` was checked for reachability and stays: `README.md` points at it as
  the zero-file quickstart, and `test_cytune_architecture.py` fails if no document mentions it.
  `measure_wrap.sh` is confirmed **not** vendored — vendoring it is what broke the rig with rc=127
  during the previous pass, and `scripts/release/smoke.sh` is now the thing that would catch a
  repeat.

### Fixed

Every finding below ships with a test that drives its failure path. Full detail, with the test
names, in [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md).

**Cold-user acceptance test — 21 findings.** F1 no packaging or `cytune` entry point · F2 no
`docs/` · F3 nothing said how to get the pinned image · F4 refused speedup reported as honest-flat ·
F5 the gate described the rejected config · F6 build failure with no compiler output · F7 three
different version strings · F8 probe number and speedup unreconciled · F9 path errors did not name
the argument · F10 raw subprocess stderr in a formatted field · F11 failed runs left a workspace
behind · F12 unknown flag showed the wrong usage · F13 `--rig quiesced` was not a valid choice ·
F14 README and certificate contradicted each other on routing · F15 a stale "acceptance has not
run" claim · F16 insider terms with no glossary · F17 vacuous separation claim on a fallback ·
F18 selection counts with no denominator · F19 contraction emitted by default · F20 `-march=native`
with no portability warning · F21 FP block fired on an integer kernel.

**Found by running those fixes — 4 defects.** P1 a reporting config emitted as "the best safe
choice" · P2 the EMIT block claimed the reference above a non-reference header · P3 usage errors
collided with the honest-flat exit code · P4 a not-run gate left the verdict unqualified.

**Fresh-tester re-test — 13 findings.** R1 the "full sanitizer report" was the shadow-byte legend ·
R2 `--allow-fast-math` denied the contraction it emitted · R3 `--dry-run` borrowed verdict exit
codes · R4 cached rows survived a `--target-ms` change · R5 the build snippet did not compile ·
R6 narration called a candidate "emitted" before it survived · R7 forced-portable claimed the host
was unquiesced · R8 `12 crash` with no diagnosis · R9 the exit-code table documented a fixed
collision · R10 the portable margin read as a property of the flag · R11 `PYTHONPATH=src` is
relative · R12 a raw `Errno 2` in a user-facing field · R13 sixty seconds of silence at `[1/6]`.

**Found during the 1.0.0 pass itself.** The B2 property sweep found that `build_certificate` would
still assemble a P2-shaped certificate if any caller forgot to demote a non-clearing winner — that
now raises at its source. The I1.6 sweep found the EMIT line and three summaries asserting "best
safe choice" under a gate that had not run. The reachability check found `examples/` shipped but
undocumented. Vendoring `measure_wrap.sh` into the package broke it (it resolves a sibling script
through `$(dirname $0)/..`) and was reverted — caught by a live run, not by a test.

### Fixed — found by the three-agent adversarial campaign

The campaign is recorded in [`results/release/V1_RELEASE_REPORT.md`](results/release/V1_RELEASE_REPORT.md)
§9, with each agent's full report under `results/release/agents/`.

**Two false certificates, closed at their source.**

- **A `# cython:` file header pinning a tuned directive is now REFUSED at ingest.** Cython's header
  overrides the `-X` flags cytune builds with, so such a module compiled identically for all 32
  directive combinations and every certificate describing them was false — including calling the
  reference "Cython's safe defaults" when it had been built with the checks off. **This fires on
  ordinary code**; headers like it are standard in scipy and scikit-learn. The README had warned
  against it for two releases, which did not stop it.
- **A clean sanitizer gate from an unpinned image is no longer a pass.** `CYTUNE_SANITIZER_IMAGE`
  pointed at a stub turned a reporting kernel into `clean: true`. The certificate now records which
  image gated it, the "safe" wording is withheld, and `--apply` refuses.

**One that cannot be closed, now stated instead of denied.** Your driver is loaded into the process
that times it, so it can control the numbers cytune certifies. `SECURITY.md` previously claimed
otherwise; it no longer does. Over-claims are flagged, under-claims are not, and the limit is
GUARANTEES N8 / K10.

**Two blockers from the systematic tester**, both cases where a named proof test was vacuous:

- **A build failure now ships the compiler's actual words.** It printed `cythonize_fail (cached)`
  and a 79-byte "full build log" containing that same string — the diagnostic was on disk the whole
  time and nothing read it back. The proof test stubbed the build result.
- **The driver contract is parsed, not substring-searched.** `# TODO: set OUTPUT_CLASS` satisfied it,
  after which the oracle fell back to the tolerance-based `float` mode and an integer kernel
  silently lost its bit-exact check. `OUTPUT_CLASS = "banana"` also reached the certificate.

**And eleven smaller ones**, including: every CLEAN row of a `cytune audit` report was also stamped
"NOT CHECKED"; two documents stated the emit margin as a property of the rig mode when it is
computed from measured noise; separation was reported without its magnitude, so a 0.2% gap read like
a 40% one; the endpoint tier could end above its CV target silently; `--target-ms -5` was accepted;
malformed `.cytune.toml` files printed raw tracebacks; and invalid config *values* were ignored
while invalid *keys* were errors.

### Fixed — found by the focused adversarial re-run

A fresh hacker was aimed at the new binding layer and told only that certificate integrity was the
property. It produced **two bind-breaks, both introduced by this release's own fixes**, which is the
argument for re-running an adversary against a defence rather than against the defect it replaced.

- **Attack A — a re-tag between the digest check and the container launch.** The fix for H6 compared
  the pinned image by digest instead of by name. The digest lookup memoises per name and was first
  populated at stage `[1/6]`; the sanitizer gate compared that cached value minutes later while
  `podman run <name>` resolved the tag live. One `podman tag stub localhost/motifbo-env:phase1` in
  between made the pin answer *pinned* while a stub executed — H6 rebuilt on top of its own fix, by
  a cache added for speed. cytune now resolves the image **once and runs that ID**, so the image
  whose digest was compared is by construction the image that ran.
- **Attack B — the driver swapping the artifact between the hash and the load.** This one was inside
  I4.1. `cmd_endpoint` hashed the `.so` in the parent before spawning the child, and
  `measure_child` loads the *driver* first and the `.so` afterwards. A driver that overwrote the
  winner's binary with a faster one producing identical output satisfied every check at once: I4.1
  (both hashes taken of the honest file), C1 (the fast binary really did take that long) and the
  oracle (identical output). Nothing in a measure phase writes to `_so/`, so it is now mounted
  **read-only** and the swap fails at the filesystem; the endpoint tier re-hashes afterwards as
  well. Reproduced against the fix: `OSError: [Errno 30] Read-only file system`.

### Fixed — found by the fresh novice user

- The wall-clock corroboration line printed a percentage and a budget and left the reader to compare
  them — the one gate in an otherwise self-explaining certificate that required arithmetic. It now
  states PASS and both quantities, and has a glossary entry.
- Its noise floor was a flat "5 % of the overhead" constant, under which an honest 9.85× run passed
  with only 24 % headroom. It is now 3σ of the per-process overhead spread **the run itself
  measured** over its screened configurations — an estimator that was already in the workspace and
  unused.
- `[2/6] probe — pre-registered 16-config screen` reported `feasible 17/17` on the next line. Two
  adjacent lines, two denominators, no explanation.
- `doctor --build-image --help` said what it did but not when to reach for it.

### Known limitations

Unchanged and still true: a clean sanitizer run is not proof of memory safety; the recommendation
is best-in-budget, not optimal; nothing transfers to other hardware; routing is DOE-unconditional;
the study behind it is underpowered and has never been re-audited against the corrected data.
`GUARANTEES.md` states each with its evidence, and the "research preview" label stays for exactly
that reason.

---

## 1.0.0-rc1 — productisation

Packaging and the `cytune` console script, the truth pass over all 21 acceptance findings,
`.cytune.toml`, `--dry-run`, `--json`, `--apply`, progress and ETA, and the T4 proof runs
(sanitizer NOT-RUN path, `--allow-fast-math`, the float-tolerance oracle, repeatability).
Recorded in `results/usertest/PRODUCTIZATION_REPORT.md`.

## 1.0.0-rc0 — first cold-user acceptance test

The state a stranger met. Verdict: *"NO — not at the first step."* Recorded in
`results/usertest/USER_TEST_REPORT.md`.
