# cytune architecture

One page. For someone who is about to change this code.

The shape of the program is: **the host orchestrates, the container measures, and nothing is
claimed that was not measured.** Every module below exists to keep one of those three true.

---

## The pipeline

```
   cytune tune  ──►  ingest ──► probe ──► route ──► search ──► measure ──► verify ──► certify
                       │          │         │         │          │           │          │
                    session    probe     routing     plan      worker      plan      certify
                       │          │                             │        sanitize      │
                       │          │                             │        _gate         │
                       └──────────┴─────── all container-side ──┘                   apply
                                                                                       │
   cytune audit ──►  ingest ──► sanitizer-gate a fixed risk set ──► report          coherence
                       │                    │                          │           (refuses to
                    session            sanitize_gate               audit           emit a lying
                                                                                   certificate)
   cytune doctor ─►  check the environment, name what to fix              doctor
```

`tune` answers *"is there a faster configuration I can safely recommend?"*.
`audit` answers *"which directives is it safe to disable for this kernel?"* — deterministically,
with no search and no timing.

---

## Module map

Each module has one job. "May import" is enforced by
`test_cytune_architecture.py::test_no_product_module_imports_study_code` and by the reachability
walk in the same file.

| module | its one job | in | out | may import |
|---|---|---|---|---|
| `cli.py` | argument parsing, stage narration, and the ORDER the stages run in | `argv` | exit code | everything below |
| `config.py` | `.cytune.toml` + flag precedence, recording where each value came from | file + `argv` | effective settings + provenance | stdlib |
| `session.py` | the workspace: vendor the user's files, run each container phase, own the cache | paths | JSON payloads per phase | `rig` |
| `rig.py` | quiesced vs portable, and the container command lines | — | `argv` lists | stdlib |
| `probe.py` | the pre-registered 17-config screen → landscape features | table rows | `delta_probe`, `IF_probe` | `_vendor` |
| `routing.py` | which rule fires, which engine, what budget — and the honest label | features | route dict | stdlib |
| `plan.py` | the DOE search: screen design, main-effects fit, predicted-best walk, winner selection, emit margin | measured medians | config ids, winner | `_vendor` |
| `worker.py` | **container-side** entry point: build (scheduling + artifact hashing), calibrate, golden+oracle, measure, endpoint | subcommand + ids | one JSON line | `_vendor`, `binding`, `plan`, `probe` |
| `sanitize_gate.py` | rebuild one config under ASan+UBSan and run it; three-valued result | kernel dir, config id | gate dict | `_vendor` (in-container) |
| `audit.py` | the pre-registered risk set and its report | gate function | audit report | `_vendor` |
| `certify.py` | assemble the certificate, decide the verdict, render it | everything measured | certificate + exit code | `_vendor`, `plan`, `routing` |
| `coherence.py` | refuse to emit a certificate that contradicts ITSELF (I1) | certificate | raises or returns | `_vendor`, `plan`, `certify` |
| `binding.py` | refuse to emit a certificate that is not about the ARTIFACTS THIS RUN PRODUCED (I4) | build records, endpoint records, gate | raises or returns | `_vendor` |
| `init.py` | scaffold a driver from the kernel's signature; refuse to guess what it cannot read | `.pyx` | `driver.py`, `.cytune.toml` | `config`, `session` |
| `apply.py` | write the directive header into the user's source, or refuse | certificate | file writes | stdlib |
| `doctor.py` | check the environment, name what to fix and whether it blocks | — | check rows | `rig`, `sanitize_gate` |
| `_vendor/` | the study's audited measurement rig, copied and pinned | — | — | itself only |

### Where the oracle lives

There is no `oracle.py`. The oracle is derived and enforced inside the container, in
`_vendor/campaign.golden_and_oracle` (determinism gate, golden capture, tolerance floor) and
`_vendor/measure_child._feasible` (the per-config check). That is deliberate: the oracle must run
in the same process that ran the kernel, on the same array, before anything is serialised. A
host-side oracle module would be a second place for the rule to live, and D11/D22 were both caused
by a rule living in two places.

---

## Dependency rule

**One way, and it points out of the study.**

```
    scripts/phasep  ──X──►  src/cytune          FORBIDDEN
    src/cytune      ──X──►  scripts/phasep      FORBIDDEN
    src/cytune/_vendor  ◄── (a pinned copy of the parts the product needs)
```

`src/cytune/**` may not import `replay`, `run_study`, `run_fleet`, `generate*`, `analyze_study`,
`report_p*`, `san_overlay`, `sanitizer_spot_audit`, or `motifbo`. It may not name a study path
(`scripts/phasep`, `/probe`, `/results/prereg`, `results/fleet`) in a string literal either.

The product must work with **no `scripts/` and no `results/` directory on the machine**. That is
tested by execution, not assertion:
`test_the_package_imports_with_no_study_tree_on_sys_path` imports every module in a subprocess
whose `sys.path` cannot reach the study tree.

A measurement container gets exactly two mounts — the package read-only, and the user's workspace.
It cannot see the study tree at all.

### Tests that are allowed to break the rule

`tests/` at the repo root. cytune's DOE planner claims to reproduce `algorithms.doe`'s trajectory
exactly; the only way to test that claim is to import both. So that test lives outside the package,
where importing study code is legitimate, and `tests/conftest.py` says so.

Everything under `src/cytune/` must pass with the study tree absent.

---

## `_vendor/`: why a copy, and what stops it rotting

The product needs the study's config space (`theta`), builder (`build`), timing child
(`measure_child`), phase library (`campaign`), seeds, the main-effects fit (`algorithms`), the
landscape classifier (`classify`), the sanitizer build and its child, and the compiler-flag profiles.
Before v1.0.0 these were imported from `scripts/phasep` through a `sys.path` bridge.

They are copied, not rewritten, because CLAUDE.md's inherited machinery binds: the v1.4 timing rig,
the CF-1 phase split, the CF-4 asserts. A reimplementation could weaken a hard gate silently, and it
would break the one comparison that makes the product's accuracy checkable — the ground-truth
dogfood, which measures cytune's answer against frozen tables produced by exactly this code.

Drift is caught two ways, in `test_cytune_vendor.py`:

- **whole-file** — sha256 identical to the study original (`theta`, `build`, `seeds`,
  `measure_child`, `san_child`, `classify`, `profiles`, plus the frozen DOE design JSON,
  `measure_wrap.sh` and the `Containerfile`).
- **per-function** — for the three files trimmed to what the product reaches (`campaign`,
  `algorithms`, `sanitizer_build`), each kept function's source text must equal the study's.

If the study tree is absent the checks skip and say so. `test_the_drift_check_is_not_vacuously_
skipping` fails if the tree IS present but nothing got compared.

---

## Invariants

`invariants.py` is the registry: every runtime invariant has a stable id, is a function, is called
in production, and has a test that makes it fire. See `docs/CONTRIBUTING.md` for the obligation
that comes with adding one.

The load-bearing one is **I1, certificate coherence**. It exists because of a defect class this
project kept rediscovering: every component correct, the composition lying.

- **P2** — the certificate said `EMIT: the reference configuration (unchanged)` and printed
  `boundscheck=False, wraparound=False` underneath it.
- **R2** — `--allow-fast-math` emitted `-ffp-contract=fast` while the certificate field said
  contraction was not permitted.
- **R3** — `--dry-run` borrowed a verdict's exit code, sending the documented `case $?` recipe down
  the "safe to use" branch on a memory-unsafe kernel.
- **R4** — cached probe rows survived a `--target-ms` change, so a 38% smaller workload produced a
  byte-identical `delta_probe`.

None of these was a broken function. Each was two correct components disagreeing, with nothing
whose job was to notice. `coherence.assert_certificate_coherent` is that job. It runs on every real
run, before anything is printed or written, and raises rather than emit.

### I4, artifact binding — and the limit of I1 that made it necessary

I1's ground truth is `theta.config_of(emitted_config.config_id)`. That is a pure function of the
id, so **I1 can prove a document is internally consistent and can never prove it is about the run
that happened.** The adversarial campaign found three certificates that were false and internally
perfect:

- **H12** — a `# cython:` header overrode the `-X` flags, so every directive combination compiled
  identically and the document described directives that were never applied.
- **H6** — a stub image printed `clean: true`, and the document reported a gate that never ran the
  rig.
- **H1** — the driver owns the clock, and the document reported times the artifact never took.

I1 passed all three. `binding.py` is the layer whose ground truth is a **hash of a file**:

| id | what it binds | how it fails |
|---|---|---|
| **I4.1** | the emitted `.so` is the one the endpoint tier timed, on both sides of the ratio | a stale, swapped or unrecorded artifact ⇒ refuse |
| **I4.2** | the varied directives change the generated code | every combination producing identical C ⇒ refuse, naming the collapsed factors |
| **I4.3** | the gate's config, source tree and image **digest** | a different tree or an unpinned digest ⇒ not authoritative |
| **I4.4** | a decision-grade timing carries its verified rig fingerprint | `quiesced` over an `UNGATED` row ⇒ refuse |

**I1.10** was added in the same pass and replaced five substring searches of the rendered
certificate: the text is re-rendered from the document's own JSON round-trip and must be
byte-identical. That is strictly stronger than the phrase checks it replaced — it covers every byte
instead of six sentences — and it catches the case none of them could, `certificate.txt` on disk
describing a different run from `certificate.json` beside it. Questions of the form "may these words
appear when this field has that value?" moved to `test_cytune_render.py`, where a negation is a test
case rather than a regex with a lookbehind window.

### The build scheduler, and why rescheduling a build is allowed at all

`worker._build_all` parallelises the cythonize phase that the study's `campaign.build_all` runs
serially. Inside the study that serialisation is free — a fleet run builds 1,728 configs, so 32
serial cythonize calls are noise. In the product the ratio is inverted: a tuning run measures ~33
configs spanning ~22 distinct directive combinations, so the serial phase *was* two thirds of the
work. Measured on the dogfood anchors, the build phase was **71 % of total wall clock**.

Rescheduling a build is safe only if the bytes are identical, and that is a test rather than an
argument: `test_cytune_binding.py::test_the_parallel_scheduler_produces_byte_identical_artifacts`
builds a real kernel both ways inside the pinned image and compares every artifact hash. This is
the second thing artifact binding buys — it makes a performance change checkable instead of
plausible.

---

## Adding to this

Read `docs/CONTRIBUTING.md`. The short version:

- a new **flag** carries a G5 obligation — prove it cannot loosen G1/G2/G3;
- a new **guarantee** may not be written into `GUARANTEES.md` until its failure path has fired in a
  test;
- a new **search engine** goes behind `plan.py`'s existing seam (`screen_plan` / `walk_plan` /
  `select_winner`), and `routing.py` decides whether it is ever chosen;
- anything unreachable from an entry point gets deleted, and the reachability test will tell you.
