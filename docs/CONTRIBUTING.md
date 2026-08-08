# Contributing to cytune

For someone who is going to extend this. Read `ARCHITECTURE.md` first for the module map and the
dependency rule.

The house style is one sentence long: **a guarantee whose failure path has never fired is a claim,
not a guarantee.** Everything below is that rule applied to a specific situation.

---

## Running the tests

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
pytest -q                       # both suites
pytest -q src/cytune            # the product; must pass with NO scripts/ and NO results/
pytest -q tests                 # study-equivalence; needs the full checkout, skips cleanly without
```

The split is load-bearing. `src/cytune` is what ships and must be self-contained;
`tests/` holds the checks that are *allowed* to import the study's code, and there is exactly one
of those (the DOE trajectory equivalence).

Two suites you should run deliberately when you touch the relevant thing:

| you changed | run |
|---|---|
| anything in `_vendor/` | `pytest -q src/cytune/test_cytune_vendor.py` — byte/function pins against the study source |
| the module layout | `pytest -q src/cytune/test_cytune_architecture.py` — import graph, mounts, reachability |
| the certificate | `pytest -q src/cytune/test_cytune_coherence.py src/cytune/test_cytune_api.py` |

---

## Adding a flag — and the G5 obligation

**G5: no flag may loosen G1 (oracle), G2 (sanitizer) or G3 (honest-flat).** A new flag is not done
when it works. It is done when you have shown it cannot weaken a guarantee.

1. Add it to `config.FIELDS` if it should also be settable in `.cytune.toml`. Unknown keys there
   are an error, not a warning — a typo'd `allow_fastmath = true` that was silently ignored would
   leave a user believing they had opted in.
2. Add it to `dest_by_flag` in `cli.main`, so `config.resolve` can tell a typed flag from an
   argparse default. Otherwise a value left at its default out-ranks the `.cytune.toml` the user
   wrote on purpose.
3. **Write the G5 test.** It has to be structural, not an example. The pattern is
   `test_policy_flags_only_ever_narrow_the_candidate_set`, which checks over the whole 1,728-config
   space that the strict default's allowed set is a subset of every looser policy's. For
   `--preset` the equivalent is `test_no_preset_can_touch_a_guarantee`, which asserts over the
   preset *table* that no preset sets a guarantee-bearing field — so adding a bad preset fails
   immediately rather than when someone happens to use it.
4. **Write the failure-path test.** Not "the flag works" — "the thing the flag is supposed to
   prevent is actually prevented". `test_f19_fp_contract_is_excluded_from_emission_by_default`
   drives a config that is *5× faster* and must still not be chosen. A test where the forbidden
   option was unattractive anyway proves nothing.
5. Document it in `USER_GUIDE.md`. **If you cannot justify the flag in one sentence there, it does
   not ship** — that is the leanness rule, and it is why `--resume` does not exist (see below).

---

## Adding an oracle class

The oracle lives container-side, in `_vendor/campaign.golden_and_oracle` (determinism gate, golden
capture, tolerance derivation) and `_vendor/measure_child._feasible` (the per-config check). Both
are **byte-pinned to the study source** — see `test_cytune_vendor.py`. You cannot just edit them.

To add a class, either:

- get the change into `scripts/phasep/` first and re-vendor, so the study and the product stay the
  same code; or
- if it is genuinely product-only, move that function out of the pinned set and into a product
  module, and say so in `_vendor/__init__.py`'s docstring.

Whichever you choose, the class needs: a determinism story (what does "the same answer" mean?), a
tolerance story (bit-exact, or a floor, or derived — and derived from what?), and a test that a
*wrong* answer in that class is actually rejected. `OUTPUT_CLASS` is validated at ingest, so add it
to the driver-contract check too.

---

## Adding a search engine

There is a seam and you should use it. `plan.py` exposes three functions the CLI drives:

```
screen_plan(budget)                     -> {"ids": [...], "design_key": ...}
walk_plan(medians, queried, remaining)  -> {"ids": [...], "fit": {...}}
select_winner(feasible_medians, policy) -> (config_id, detail)
```

An engine is those three. `routing.py` decides whether yours is ever chosen — and note what the
study found before you assume it will be: **DOE beat BO in 18 of 20 cells, BO was worse than random
search on flat landscapes, and per-kernel routing did not beat always-DOE on held-out kernels.** A
new engine needs to beat that, measured, not argued.

Two hard requirements:

- **`select_winner` must respect the `EmissionPolicy`.** It is a pure filter; the emitted config is
  always inside the effective policy, and `test_b2_the_emitted_config_is_always_inside_the_effective_policy`
  checks it over the outcome space.
- **Spend budget only on configs this run could actually emit.** Measuring a config the policy
  forbids burns measurement to produce a number the certificate must then refuse to act on.

---

## Adding an invariant

Runtime invariants live in `invariants.py`, and the registry is checked by
`test_cytune_invariants.py`. To add one:

1. Give it a stable id in the existing tiers — `I1.*` certificate coherence, `I2.*` emission,
   `I3.*` artifacts.
2. Make it a function, and **call it in production**. An invariant that only runs in tests is a
   test.
3. Write the test that makes it FIRE. Then write the control asserting an honest input passes —
   without that, a function that raised unconditionally would pass every violation test you wrote.
4. Add the registry entry. `test_every_coherence_invariant_in_the_code_has_a_registry_entry` fails
   if you skip this, and `test_no_registry_entry_is_a_dead_letter` fails if you register something
   the code never raises.

---

## Adding a guarantee

**A new guarantee may not be written into `GUARANTEES.md` until its failure path has fired in a
test.** This is the rule the whole document is organised around: every entry names the evidence
that the thing it promises was actually exercised, and says plainly when it wasn't.

So the order is: implement it → write the test that drives the failure → run it and watch it fail
→ make it pass → *then* write the guarantee, citing the test by name. Not the other way round.

If the failure path can only be exercised live, say so and archive the run under `results/`. "live"
and "test" are both acceptable evidence; "obviously true" is not.

---

## Changing the public API

Read `COMPATIBILITY.md`. Within 1.x you may **add** fields; you may not remove or re-type them, and
you may not repurpose a flag name or change what an exit code means. `schema.py` is the machine-
readable contract and `test_cytune_api.py` validates real output against it — including every
archived certificate from a released build.

If you must break something, it waits for 2.0 and gets a deprecation warning for one minor release
first.

---

## Things that were deliberately NOT built

Recorded so they are not re-proposed as oversights.

- **`--resume`.** cytune already resumes: `table.jsonl`, `build_manifest.jsonl` and
  `artifacts.jsonl` persist and are validated against a complete cache key on every run, so an
  interrupted run continues by simply being run again. A flag would have been a second name for
  the default behaviour. What was added instead is *visibility* — the run says which cached work
  it reused and which it discarded, and why.

  This claim was **false for measurements until 1.0.0**, and it is worth saying how. Ingest
  re-copies the user's driver, which resets the calibration knob; calibration then re-derived the
  workload from one measurement of the reference, and timing noise moved the answer by a fraction
  of a percent on every run (33831, then 33699, for an untouched kernel). The calibrated workload
  is in the measurement cache key — correctly — so every re-run discarded the whole table. Builds
  resumed; measurements never had. The calibration is now reused when nothing it depends on has
  changed (`Session.reusable_knob`), and `scripts/release/smoke.sh` step 5 is what caught it.
- **A `--no-sanitizer` escape hatch.** It would be a flag whose only function is to weaken G2.
- **`--objective size` / `--objective compile`.** These existed as a flag that only ever refused,
  which is a paragraph of the user guide wearing a flag costume: a line in `--help`, a field in
  `.cytune.toml`, an entry in the exit-code table and a section of TROUBLESHOOTING, for behaviour
  that was "print an error". Removed in 1.0.0. Both metrics are still recorded per config in
  `build_manifest.jsonl` and the user guide says how to rank on them.
- **A router that picks between algorithms.** The study measured that this does not beat
  always-DOE. Shipping one anyway would be the overclaim this project exists to refuse.
