# Repo map — every directory and top-level file, and which branch it lives on

Branch column: **M** main (product) · **D** dev (development) · **R** research (the study).
`dev` is a superset of `main`; `research` carries the study material.

## Top level

| path | branch | what it is |
|---|---|---|
| `src/cytune/` | M D R | the product package. Nothing here imports anything outside it |
| `src/motifbo/` | R | the study's own package (build profiles, algorithms). `test_cytune_architecture.py` lists it as STUDY_ONLY |
| `pyproject.toml` | M D R | package metadata, the `cytune` console script, pytest config |
| `Containerfile` | M D R | the pinned toolchain image `motifbo-env:phase1` (digest `d45e33b0…`) |
| `README.md` | M D R | different on each branch, deliberately: main's is the customer-facing page |
| `CHANGELOG.md` | M D R | |
| `SECURITY.md` | M D R | |
| `CLAUDE.md` | D R | how to work in this repo |
| `PRODUCT_ROADMAP.md` | R | the spec. Law for the study |
| `docs/` | M D R | see below |
| `tests/` | D R | study-equivalence and cross-tree tests (the package's own tests live beside it) |
| `scripts/` | D R | everything that is not the product: harnesses, the study, release tooling |
| `results/` | R | every raw measurement, every report, every pre-registration. **Gitignored in its entirety** — see the note below |
| `logs/defects/` | D R | the D3–D25 post-mortems |
| `data/` | D R | toolchain and requirement lock files |
| `sandbox/`, `prompts/`, `graphify-out/` | D R | scratch, prompt archive, the code knowledge graph |

**`results/` is not tracked by git.** `.gitignore:43` is a bare `results/`, so `git ls-files
results/` returns nothing. Every pre-registration and report in this project is pinned by sha256 in
a commit message rather than by being committed. This is why `main` gets a **tracked** `evidence/`
directory instead of pointing at `results/` — a sales page whose evidence is in an untracked
directory on another branch is a claim with a broken pointer.

## `src/cytune/` — the product

| file | what it does |
|---|---|
| `cli.py` | the six-stage orchestration, argument parsing, every user-facing line |
| `session.py` | the workspace: vendoring, cache invalidation, and the single `_run` that spawns every container |
| `worker.py` | runs *inside* the container; dispatches `build \| golden \| measure \| endpoint \| features \| screen \| walk` |
| `rig.py` | container command construction, rig-mode detection, image digest pinning |
| `lock.py` | the machine-level measurement lock (B3) |
| `probe.py` | the 17-config probe design and the features derived from it |
| `routing.py` | rules R0–R5: whether to search, and with what budget |
| `plan.py` | the emission policy, the screening design, the adaptive walk, winner selection and endpoint confirmation |
| `certify.py` | assembles, renders and explains the certificate; `corroborate_ratio`, `assess`, `next_step` |
| `coherence.py` | I1 — the certificate must not contradict itself |
| `binding.py` | I4 — the claim must be tied to the artifact that produced it |
| `invariants.py` | the I1–I4 registry as data, walked by tests |
| `paths.py` | the verify/emit path registry as data (B4), walked by tests |
| `sanitize_gate.py` | the ASan+UBSan gate on the config being emitted |
| `audit.py` | `cytune audit` — the pre-registered memory-safety risk set |
| `doctor.py` | environment checks, their fix lines, and `blocking_preflight()` which `tune` runs itself |
| `init.py` | scaffolds `driver.py` and `.cytune.toml` from the function signature |
| `apply.py` | writes the emitted header into the source, and refuses when it must not |
| `config.py` | `.cytune.toml`, presets, and flag precedence |
| `schema.py` | the four document schemas |
| `examples/` | the shipped quickstart kernel and driver (data, pinned by a test) |
| `_vendor/` | the study's measurement machinery, copied and hash-pinned. See `08_CONTAINER.md` |
| `test_cytune_*.py` | the product test suite — shipped inside the package, because it is part of what the product asserts about itself |

## `scripts/`

| path | what it is |
|---|---|
| `release/` | `smoke.sh` (the pre-tag ritual), `fleet_gate.py` + controls (B1), `build_vendor_manifest.py` (B2), `run_repeat.py` + `analyse_repeat.py` (the repeated dogfood), `run_dogfood*.sh`, `analyse_dogfood.py`, `stage_dogfood.py` |
| `doe_v2/` | the offline replay harness: the sealed ask–tell interface, the fleet loader, the engine variants, the controls |
| `phasep/` | the study: `theta.py`, `campaign.py`, `run_fleet.py`, `classify.py`, and the sources the vendored copies are pinned against |
| `corpus/` | the real-code drivers behind the nine Dataset-R anchors |
| `hooks/` | git hooks, the graphify gate, `campaign_busy.sh` |
| `measure_wrap.sh` | the host-side rig gate. Refuses to measure unless turbo is off, the governor is `performance`, the SMT sibling is idle or isolated, and THP is not `always` |
| `host_prep.sh`, `thermal_log.sh`, … | host setup and instrumentation |

## `docs/`

| file | audience | on |
|---|---|---|
| `USER_GUIDE.md` | user | M D R |
| `GUARANTEES.md` | user | M D R |
| `TROUBLESHOOTING.md` | user | M D R |
| `KNOWN_ISSUES.md` | user | M D R |
| `COMPATIBILITY.md` | user | M D R |
| `ARCHITECTURE.md` | contributor | D R (referenced from main) |
| `CONTRIBUTING.md` | contributor | D R (referenced from main) |
| `system/` | contributor | D R — this set |

## `results/` (research branch)

| path | what it is |
|---|---|
| `fleet/` | the 149 frozen kernels: `table.jsonl` (1,728 rows each), `FREEZE_MANIFEST_V2.json`, the sanitizer overlay |
| `prereg/` | `PREREG_PHASEP.md`, `PREREG_DOE_V2.md`, `PREREG_LAUNCH.md`, and the frozen designs |
| `release/` | `V1_RELEASE_REPORT.md`, `DOE_V2_REPORT.md`, `LAUNCH_REPORT.md`, and every dogfood campaign |
| `doe_v2/` | the offline replay raw output and the measured fleet prior |
| `audit/`, `power/`, `calibration/`, `pilot/`, `probes/` | the study's supporting evidence |
| `PHASEP_REPORT.md`, `DEFENSE_SUMMARY.md`, `STATE_PHASEP.md` | the study's own reports and its resumable state |
