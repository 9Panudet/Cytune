# The pipeline, stage by stage

`cli.py::tune()` runs six stages in order. Each timed stage is a separate container invocation —
that is how the compile/measure split (CF-1) is enforced structurally rather than by convention.

Before stage 1, two things happen that are easy to miss:

* **C2 preflight** — `doctor.blocking_preflight()` runs doctor's own BLOCKING checks (podman,
  pinned image, sanitizer gate, python). A failure prints doctor's own fix line and returns exit 1
  *before any directory is created*.
* **B3 lock** — `lock.MeasurementLock` takes a machine-wide lock for the whole run. A second run
  refuses (or queues with `--wait`). Taken after rig-mode resolution so the refusal can name it,
  before `Session(...)` so a refusal leaves no workspace behind.

---

## `[1/6] ingest` — `session.py::Session.vendor`

Copies the module tree and driver into `<workspace>/_kernels/<name>/`, hashes them, and records
what it found. Two things happen here that change later stages:

* **scoped directives.** If your source pins `boundscheck` with a decorator or a `with` block,
  Cython honours that over the `-X` flags, so the emitted header will not reach those functions.
  Detected here and listed on the certificate rather than silently producing a smaller effect.
* **cache invalidation** — `invalidate_stale_builds`. If the module, the driver, or the toolchain
  changed, cached builds and measurements are discarded. D17: build resume once trusted
  `build_manifest.jsonl` alone, and a pruned `_so` produced "built 17/17" then an ImportError.

## `[2/6] probe` — `probe.py`, `session.py::build/golden/measure`

Builds and measures a fixed **17-configuration** design (16 D-optimal points plus the reference,
`_vendor/data/doe_designs_theta.json`, pre-registered).

`Session.golden()` is the first timed phase. Inside it, `_vendor/campaign.py::calibrate` scales the
driver's knob so the reference lands near `--target-ms` (65 ms default), then `golden_and_oracle`
captures the golden output and runs 5 determinism repetitions. Everything downstream compares
against that golden.

`probe.features()` derives the landscape summary the router reads: `delta_probe` (the spread across
the probe), `if_probe` (an interaction fraction), and the feasible fraction.

**I4.2** fires here: if every directive combination produces byte-identical generated C, the search
cannot mean anything, and cytune refuses rather than reporting whichever build was luckiest.

## `[3/6] route` — `routing.py::route`

| rule | condition | result |
|---|---|---|
| **R0** | the reference is infeasible, or fewer than 4 probe rows are feasible | ABORT, exit 1 |
| **R1** | `delta_probe <= 1.10` | **honest-flat**: skip tuning entirely |
| **R2** | degenerate landscape | DOE @ 16 |
| **R3** | interaction present | DOE @ 32 |
| **R4/R5** | otherwise | DOE @ 16 |

Plus `+8` when the feasible fraction is below 0.75, because a landscape that keeps rejecting
configurations needs more of them. Routed budgets are therefore 16, 24, 32 or 40.

**Routing is installed as a negative result.** The study found that per-cell engine switching adds
nothing on held-out kernels; cytune routes to DOE unconditionally. The rules that survived — R0 and
R1 — are the two that earned it.

## `[4/6] tune` — `plan.py::screen_plan`, `plan.py::walk_plan`

**Screen.** A second D-optimal design, capped at `min(24, budget - 1)`. The `- 1` reserves budget
for the walk; capping at `budget` instead was **defect D-2**, which starved the walk for every
budget in [17, 24] and cost median regret 3.95% vs 1.46%, worst 516% vs 46%, on 58 of 149 kernels —
while reaching **0 of the 9 real-code anchors**.

**Walk.** `walk_plan` fits main effects on what the screen returned (`_vendor/algorithms.py::_fit`,
ridge) and takes the predicted-best unqueried configurations. The walk visits **only configurations
this run could emit** — measuring a policy-forbidden config burns budget to produce a number the
certificate must then refuse to act on. `screen_plan` does not obey that rule, which is the known,
deliberately-unfixed defect **D-1**; see `04_SEARCH.md`.

## `[5/6] verify` — `session.py::endpoint`, `plan.py::confirm_winner`, `sanitize_gate.py`

The winner and the reference are re-measured at the **endpoint tier**: K=30, median-of-3, inputs
regenerated per repetition.

Then, in this order — and the order is the design:

1. **`confirm_winner`** — the endpoint re-checks the oracle. A screen pass is not a licence.
2. **the sanitizer gate on the search's best candidate** — gated *before* the emit decision,
   deliberately, because the gate is a bug finder and not only an emission filter. Gating only the
   eventual emission once let a real out-of-bounds read go unreported because the offending config
   was dropped for being slow.
3. **C1 wall-clock corroboration** — `certify.corroborate_ratio`. Does the parent process's wall
   clock account for the claimed gain? If not, the claim is withheld.
4. **the emit margin** — `certify.assess`. `max(2 × combined endpoint CV, 2%)`, plus a rank-based
   separation guard.
5. **the gate on whatever is actually being emitted** — usually the reference, after a demotion.

Each of 1–4 can demote the candidate to the reference. Those demotion paths, and the disposition of
the sanitizer verdict on each, are enumerated in `src/cytune/paths.py`; **D-3 was a demotion that
forgot to invalidate the candidate's gate verdict**, and the certificate would have described a run
that did not happen.

## `[6/6] certify` — `certify.py`, `coherence.py`, `binding.py`

`build_certificate` assembles the document. Then, before a single byte is printed or written:

* **I1 coherence** (`coherence.assert_certificate_coherent`) — the document must not contradict
  itself. Raising is deliberate: there is nothing to salvage in a certificate that disagrees with
  itself.
* **I1.10** — `certificate.txt` must be exactly what `certificate.json` renders to.
* **I4 binding** (`binding.assert_emission_bound`, `assert_gate_bound`, `assert_rig_bound`) — the
  emitted config id, the gated config id, and the timed artifact must all be the same thing.

If any of these fails, **nothing is written**. Then the human answer (`certify.next_step`) is
printed above the rendered certificate, and `--explain` and `--apply` run if asked.

---

## What can fail, and what happens

| failure | result |
|---|---|
| bad arguments / not-ready machine | exit 1, nothing created |
| ingest cannot read the module or driver | exit 1 |
| not one configuration compiles | `BuildFailure`, exit 1 |
| total directive degeneracy | I4.2, exit 1 |
| routing rule R0 | ABORT, exit 1 |
| nothing feasible, or everything policy-excluded | `no-safe-improvement`, exit 3, no config emitted |
| the winner fails at the endpoint | reference emitted, exit 3 |
| the sanitizer reports on the candidate | reference emitted, exit 3, with a memory-safety finding |
| C1 cannot account for the gain | reference emitted, exit 3, no speedup claimed |
| the margin is not cleared | reference emitted, `honest-flat`, exit 2 |
| the **emitted** config reports | exit 3, verdict forcibly overwritten, `--apply` refuses |
| the gate could not run | verdict unchanged, safety wording downgraded, `--apply` refuses |
| a binding or coherence violation | exit 1, nothing written |
