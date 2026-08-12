# cytune, in three pages

*The document to read first. Everything else in `docs/system/` is detail hanging off this one.*

---

## What it is

**cytune takes a Cython kernel and tells you which compiler settings make it fastest — and refuses
to tell you anything it cannot stand behind.**

You give it two files: your `.pyx` module, and a `driver.py` that says how to build inputs, how to
call it, and how to compare two results. It compiles your kernel about 35 different ways, times
them on a quiesced CPU core, checks that each one still produces your answer, and hands back a
**certificate**: a document naming one configuration, what it measured, and everything it did not
prove.

```
cytune init kernel.pyx                        # writes a driver.py you can run
cytune doctor                                 # is this machine ready?
cytune tune kernel.pyx --driver driver.py     # the answer
```

Three exit codes are all answers, not failures: `0` a faster config was found, `2` nothing is
reliably faster than what you have, `3` something faster existed and could not be safely claimed.
Only `1` means it could not finish.

**The search space** is 1,728 configurations: six Cython directives (`boundscheck`, `wraparound`,
`cdivision`, `initializedcheck`, `nonecheck`) crossed with GCC's `-O1/-O2/-O3`, `-march`,
`-funroll-loops`, and a three-level floating-point axis. By default only **576** of those may be
emitted, because the two settings that change floating-point results are opt-in.

---

## The six stages

`cli.py::tune()` runs them in order. Each is a separate container invocation, which is how the
compile/measure split is enforced structurally rather than by convention.

| # | stage | what happens | where |
|---|---|---|---|
| 1 | **ingest** | copy the module and driver into a workspace, hash them, invalidate any stale cache | `session.py::Session.vendor` |
| 2 | **probe** | build and measure a fixed 17-configuration D-optimal design; establish the golden output and the oracle | `probe.py`, `session.py::golden` |
| 3 | **route** | decide from the probe whether the landscape is worth searching, and with what budget | `routing.py::route` |
| 4 | **tune** | a second screening design, then an adaptive walk down the predicted-best ranking | `plan.py::screen_plan`, `walk_plan` |
| 5 | **verify** | re-measure the winner and the reference at a heavier tier (K=30, median-of-3); run the sanitizer on the config actually being emitted | `session.py::endpoint`, `sanitize_gate.py` |
| 6 | **certify** | assemble the document, check it against itself, bind it to the artifacts, write it | `certify.py`, `coherence.py`, `binding.py` |

Detail: [`02_PIPELINE.md`](02_PIPELINE.md).

---

## The four guarantees

Stated as what cytune *refuses to do*, because that is what they are.

**G1 — it never recommends a configuration that changes your output.**
Every measured configuration is re-run against a golden output produced by your own `canon`
function. A configuration that fails is *infeasible* regardless of how fast it was. The check runs
twice: once at the screening tier, once again at the endpoint tier, because a screen pass is not a
licence (`plan.py::confirm_winner`).

**G2 — it never recommends a configuration that reads memory it does not own.**
Before emitting anything, cytune rebuilds that exact configuration under AddressSanitizer and
UBSan and runs your driver against it. A report means the configuration is refused. **A gate that
did not run is never recorded as a pass** — it is recorded as not-run, and the certificate's safety
wording is downgraded accordingly.

**G3 — it says "no improvement" instead of inventing one.**
Three separate mechanisms produce that answer: a routing rule that declines to search a flat
landscape, a guard against reporting the minimum of a noisy sample as a finding, and an emit margin
of `max(2 × measured CV, 2%)` below which no gain is claimed at all.

**G4 — every claim is bound to the bytes that produced it.**
The certificate records the sha256 of the emitted `.so`, and it must equal the sha256 of the `.so`
that was timed and the one that was gated. If they differ, cytune writes nothing at all. This layer
caught a real defect in production during the launch pass.

Detail: [`05_CORRECTNESS.md`](05_CORRECTNESS.md), [`06_INVARIANTS.md`](06_INVARIANTS.md).
The guarantees as published: `docs/GUARANTEES.md`.

---

## Where the numbers come from

This is the part that distinguishes cytune from a tuner that simply asserts it works.

There is a frozen benchmark of **149 Cython kernels** — 129 synthetic training kernels, 11
held-out, and **9 taken from real library code** (sparse matrix-vector multiply, isotonic
regression, LDA, Floyd-Warshall, k-means with the Elkan bound, and others). For every one of them,
**all 1,728 configurations were exhaustively measured**. So for those kernels the true optimum is
not estimated — it is known.

That makes a question answerable that normally is not: *when cytune measures ~35 configurations out
of 1,728 and picks one, how much slower is its pick than the best one it could have picked?* The
answer is its **regret**, and it can be computed exactly.

Two things follow, and both matter:

1. **The accuracy claim is measured, not argued.** Against exhaustively-known optima on real
   library code.
2. **The claim carries a range, not a point.** Two runs of the *same unchanged engine* were found
   to disagree by 3.597 percentage points on one anchor. A single-run figure is not a property of
   the tool; it is one draw. Every published number therefore comes from a repeated campaign and is
   quoted with its spread.

The engine itself is not a guess either. Four search algorithms — random search, D-optimal design,
Bayesian optimisation, and a motif-transfer method — were compared under one pre-registered
protocol on frozen tables. **Bayesian optimisation lost.** The motif method won by 9.7× enrichment
for siblings of its own target and was **not shipped** for that reason. What ships is the design
method that won, and the study's negative results stand on the record.

Detail: [`11_EVIDENCE.md`](11_EVIDENCE.md), [`04_SEARCH.md`](04_SEARCH.md).

---

## What the branches hold

| branch | what is on it | who it is for |
|---|---|---|
| **main** | the product: `src/cytune`, its test suite, user docs, and a self-contained `evidence/` carrying exactly what the README's claims rest on | a user, and anyone checking a claim |
| **dev** | everything on main, plus `scripts/`, the study-equivalence tests, release tooling, and this `docs/system/` set | a contributor |
| **research** | the study: `results/`, the pre-registrations, the roadmap, the frozen tables, the thesis material | a reviewer or a researcher |

The split is **by content, not by rewriting**: nothing is deleted from history.

The rule that makes it work is one-way: **the product depends on nothing in the study tree.** The
measurement machinery the study used is vendored into `src/cytune/_vendor/` and pinned by hash, so
a user's install measures the same way every published number was measured, without needing the
study. `test_cytune_vendor.py` enforces the pin from committed data, on every branch.

Detail: [`01_REPO_MAP.md`](01_REPO_MAP.md).

---

## What to look at when something breaks

| symptom | look here first |
|---|---|
| `cytune: this machine is not ready to tune` | `cytune doctor` — it prints the fix line for each blocking check |
| `REFUSING TO CERTIFY — a claim could not be tied to the artifact behind it` | an I4 binding violation. The run is real, the document would have been about a different one. `06_INVARIANTS.md` |
| `INTERNAL — refusing to emit a certificate that contradicts itself` | an I1 coherence violation. This is a cytune defect; the report is wanted |
| `REFUSING TO MEASURE — another cytune measurement holds this machine` | working as designed. `--wait` to queue. `03_MEASUREMENT.md` |
| a verdict you doubt | `--explain`, then `certificate.json`, then `table.jsonl` — every measured row is there |
| numbers that look wrong | was the rig quiesced? `certificate.json → measurement.rig_mode`. A `portable` run is explicitly labelled indicative |
| a test failed and you cannot see why | `10_TESTING.md` names every suite and which gate it belongs to |

---

## The one habit this codebase runs on

**A number without a raw pointer and a recompute command does not exist.**

Every figure in every document here names the file it came from and the command that regenerates
it. Statistics are recomputed from raw by an independent auditor, never transcribed. Worst cases
are reported, not representative ones. Partial results are stated as partial.

And favourable surprises are treated as alarms. The two largest findings in this project's history
— that 1,296 configurations had been recorded as correct while reading out of bounds (D23), and
that the composition-level regression check had not run since a rename (D25) — were both found by
someone asking why something looked better than it should.

The defect ledger, and what each defect taught, is [`12_HISTORY.md`](12_HISTORY.md). If you are
taking this codebase over, read that one next.
