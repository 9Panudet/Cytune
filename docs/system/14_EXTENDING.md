# Extending cytune — the seams, and the bar

Contributor process: `docs/CONTRIBUTING.md`, in particular *"The bar: how an engine change is
evidenced"*. This file names the seams and the traps.

## The seams

| you want to… | change | and you must also |
|---|---|---|
| add a search strategy | `plan.screen_plan` / `plan.walk_plan` | pass the B1 fleet gate against the committed baseline; `tests/test_study_equivalence.py` must still hold |
| add a routing rule | `routing.py` | the certificate's routing label must stay honest about what is validated |
| add a verdict or demotion path | `cli.tune` | **add it to `paths.py` and to the composition mirror in the same commit** |
| add an invariant | `binding.py` / `coherence.py` | add it to `invariants.REGISTRY` with a real production site and a named test, or the registry walker fails |
| add a flag | `cli.py` + `config.FIELDS` | one sentence in `USER_GUIDE.md` §13, or `test_every_flag_and_config_key_is_documented_here` fails |
| re-sync a vendored file | `_vendor/` | regenerate `VENDOR_MANIFEST.json` **in the same commit** |
| add a script | `scripts/` | its `cytune.*` imports are checked by `tests/test_script_imports.py` |

## The traps, each paid for once already

**Do not add a demotion path without the mirror.** D-3 was the fourth defect of the shape "the unit
is tested, the composition models fewer cases than production has". `paths.py` turns the *second*
half of that into a test failure; the first half — noticing that you added a path — is still yours.

**Do not add a test you cannot describe a mutation for.** Four of eight gated properties in the BO
review were vacuous: four mutations left all twelve tests green.

**Do not build fixtures that cannot reach the branch you are testing.** D-3's sweep carried no
`wall_ns`, so the branch it existed to cover was unreachable in principle.

**Do not let a check skip silently.** If it cannot run here, say so loudly. The fleet gate prints
`NOT RUN` in yellow on a branch without the frozen tables, because a gate that cannot run here has
not passed here.

**Do not refresh a baseline to make a gate pass.** `fleet_gate.py --record` refuses without
`--i-am-establishing-a-new-baseline` and a `--reason`, and that is not a formality.

**Do not weaken a guarantee through a preset or a flag.** G5. Presets may move `budget_scale` and
`target_ms` and nothing else, enforced by `config.PRESET_SETTABLE`.

**Do not edit `_vendor/` in place.** It is hash-pinned to the study source in both directions.
Re-copy the correct side and regenerate the manifest.

## Before you tag

```bash
.venv/bin/python -m pytest src/cytune tests -q          # 922 tests
.venv/bin/python scripts/release/fleet_gate.py          # B1, 9 s
.venv/bin/python scripts/release/fleet_gate_controls.py # L6/L7 — the gate must be able to fail
bash scripts/release/smoke.sh                           # the live ritual, ~6 min
```

A green suite says the code is self-consistent. The smoke gate says the product works on this
machine. During the 1.0.0 architecture pass, 526 tests were green while `measure_wrap.sh` returned
rc=127 mid-run.
