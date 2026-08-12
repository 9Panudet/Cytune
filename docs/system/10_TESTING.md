# Testing — every suite, what it proves, and which gate it belongs to

## The suites

Run everything: `.venv/bin/python -m pytest src/cytune tests -q` (~70 s, 922 tests).
Run one: `.venv/bin/python -m pytest src/cytune/test_cytune_binding.py -q`.

| suite | proves | gate |
|---|---|---|
| `test_cytune_api.py` | the public surface, verdict↔exit mapping | suite |
| `test_cytune_architecture.py` | the dependency rule; **no unreachable module** | suite |
| `test_cytune_audit.py` | the risk set and its verdicts | suite |
| `test_cytune_binding.py` | I4.1–I4.4 against **real Cython and real gcc** | smoke step 6 |
| `test_cytune_cache.py` | I3.1–I3.4 invalidation and archiving | suite |
| `test_cytune_certify.py` | document assembly, I2.1–I2.3 | suite |
| `test_cytune_coherence.py` | I1.1–I1.10 + the **composition sweep** | suite |
| `test_cytune_contract.py` | the driver contract | suite |
| `test_cytune_doctor.py` | every check and its fix line | suite |
| `test_cytune_firewall.py` | no product module reads study data; **no user-facing string cites a path the reader lacks** | suite |
| `test_cytune_h12.py`, `test_cytune_h6.py` | the H-series product fixes | suite |
| `test_cytune_init.py` | scaffolding from a signature | suite |
| `test_cytune_invariants.py` | the invariant registry is complete and has no dead letters | suite |
| `test_cytune_lock.py` | **B3** — two real processes contend for the machine lock | smoke step 0 + 5b |
| `test_cytune_next_step.py` | the human answer is total over the verdict space | suite |
| `test_cytune_oracle_power.py` | **D26** — the oracle can fail | suite |
| `test_cytune_paths.py` | **B4** — the sweep covers every REQUIRED production path | smoke step 0 |
| `test_cytune_product_fixes.py` | the D-series product fixes | suite |
| `test_cytune_render.py` | I1.10 round-trip | suite |
| `test_cytune_routing.py` | R0–R5 | suite |
| `test_cytune_sanitize_gate.py` | verdicts, and not-run ≠ pass | suite |
| `test_cytune_ux.py` | argument validation; **every flag and key is documented** | suite |
| `test_cytune_vendor.py` | **B2** — tier 1 everywhere, tier 2 where the study is | smoke step 0 |
| `test_cytune_worker.py` | the in-container dispatch | suite |
| `tests/test_study_equivalence.py` | the product's search reproduces the study's engine | dev only |
| `tests/test_script_imports.py` | every script's `cytune.*` imports resolve (**D25**) | dev only |

## The gates above the suite

| gate | what it is |
|---|---|
| `scripts/release/smoke.sh` | the pre-tag ritual. Step 0 the offline gates, then doctor → init → tune → audit → resume → the live lock test → the container-backed binding tests |
| `scripts/release/fleet_gate.py` | **B1** — 149 frozen tables × 9 budgets vs a committed baseline, 9 s |
| `scripts/release/fleet_gate_controls.py` | L6/L7 — the gate must fail on reintroduced D-2 and pass on itself |
| `scripts/cytune_e2e_composition_check.py` | D13/D14/D18 as whole-pipeline properties, each with a **red control** |

## THE STANDING WARNING: vacuous tests

Three defects in this project's history were tests that could not fail. Read this section before
adding a test.

**R2 — a gated property that no mutation breaks.** During the BO review, 4 of 8 gated properties
turned out to be vacuous: four separate mutations left all 12 tests in `test_bo.py` green. If you
cannot describe the mutation your test catches, you have not written a test.

**D-3 — a branch that could not execute.** The composition sweep's docstring said its purpose was
"reproduce the CLI's decision order". It modelled two of three demotion paths, and its endpoint
fixtures carried **no `wall_ns`**, so `corroborate_ratio` returned `None` for every row and the
third branch was unreachable **in principle**. Adding a branch to a mirror proves nothing if the
fixtures cannot enter it. This is why `test_the_c1_branch_of_the_composition_actually_executes`
asserts the sweep reaches both `True` and `False`.

**D25 — a check that never ran at all.** `cytune_e2e_composition_check.py` died on import for an
entire release. A skipped test prints `s`; a script nobody invokes prints nothing.

The countermeasures now standing: `paths.py` + `test_cytune_paths.py` (a REQUIRED path the sweep
never reaches is a failure, mutation-checked), the vendor manifest (tier 1 cannot skip),
`tests/test_script_imports.py`, and the rule that every new instrument gets a **positive and a
negative control** before its readings count.

That last rule is not decoration. The oracle — the instrument the entire correctness guarantee is
made of — had no positive control until a first-time user found the gap (D26).

## Conventions

* Test names are sentences: `test_a_timing_refusal_emits_the_reference_gated_as_the_reference`.
* Every defect fix carries a test whose **revert fails it**, and post-mortems record which.
* Anti-vacuity tests are named as such and are not optional.
* Exemptions (the reachability walk's `TEST_SUPPORT`, `EXAMPLE_DATA`) each carry their own test
  proving the exempted thing is actually used.
