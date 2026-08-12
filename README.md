# cytune — the research branch

This branch carries **the study**: the pre-registrations, the reports, the manifests, and the
negative results. It is here so that a claim made on `main` can be checked by someone who did not
make it.

The other two branches:

| branch | what is on it |
|---|---|
| **`main`** | the product, its user docs, and a self-contained `evidence/` |
| **`dev`** | everything on main plus the development harnesses, the study-equivalence tests, release tooling, and `docs/system/` |
| **`research`** | you are here |

---

## What the research programme was

**Question.** Given a Cython kernel, which of 1,728 (directive × compiler-flag) configurations is
fastest — and can a search find it cheaply enough to be worth running?

**Method.** A controlled benchmark of 149 kernels: 129 synthetic training kernels, 11 held out, and
**9 taken from real library code**. Every kernel was measured **exhaustively** — all 1,728
configurations — so the true optimum is known and a search's *regret* can be computed exactly rather
than estimated.

Four algorithms — random search, D-optimal design, Bayesian optimisation, and a motif-transfer
method — were then compared by **offline replay against those frozen tables**, through a sealed
ask–tell interface with a cheat-test proving no algorithm could see more than its budget. Everything
was pre-registered before results were read.

## What it found, including the parts nobody wanted

**DOE wins; Bayesian optimisation does not earn its cost.** The Bayesian arm loses to D-optimal
design in 18 of 20 cells and is **worse than random search on flat landscapes**.

**Motif+BO passed its statistical gate and was not shipped.** p = 3.46e-17, Cliff's δ = 0.772 — and
its warm-start sources were **9.7× enriched for siblings of the target's own template**, while the
corpus it needs does not exist at the point of use. A win produced by leakage is not a win. This is
the single most consequential negative result here, because it is the one where the statistics said
ship.

**Routing adds nothing.** On held-out kernels a per-cell router equals always-DOE at
B ∈ {8, 32, 64, 128} and is *worse* at B=16. cytune therefore routes to DOE unconditionally, and
every certificate it emits says so.

**The most interesting class does not occur in real code.** The synthetic generator produced 42
kernels in the INT class (genuine directive × flag interaction). The nine real-code anchors produced
**zero** — and those nine were already filtered as the most promising non-flat units available. Any
algorithm whose advantage concentrates in INT may have an advantage unreachable on real user code.

**1,296 cells were recorded correct while reading out of bounds.** The §1.4 sanitizer gate had never
been invoked across ~149 kernels × 1,728 configurations. Three min/max-reduction kernels passed the
output oracle at 432/432 each while executing a heap buffer overflow — a reduction absorbs one
garbage element without changing its result. Their 13× "lever" *was* the out-of-bounds read.
Remediated by overlay; the raw data is byte-identical and only the feasibility label is corrected on
top. `logs/defects/D23.md`.

**All six DOE-v2 engine variants failed on real code**, and the exercise was designed to be able to
return that. `results/release/DOE_V2_REPORT.md`.

**The ship bound was 6.7× tighter than the instrument.** Five repeated runs per arm measured the
engine's own run-to-run spread at 6.711 pp, against a rule that judged engine changes at 1.0 pp.
`results/release/LAUNCH_REPORT.md`.

## Where things are

| | |
|---|---|
| `results/prereg/` | every pre-registration, each committed before the results it governs |
| `results/PHASEP_REPORT.md` | the study report — all three research questions answered, all three negative |
| `results/DEFENSE_SUMMARY.md` | one page: four buckets, guarantees and non-guarantees |
| `results/release/DOE_V2_REPORT.md` | the engine re-evaluation, and why nothing shipped |
| `results/release/LAUNCH_REPORT.md` | the repeated-measurement pass and the re-derived bound |
| `results/fleet/FREEZE_MANIFEST_V2.json` | the 149 kernels, their sha256s, and their measured classes |
| `PRODUCT_ROADMAP.md` | the spec the study was executed against |
| `logs/defects/` | D3–D26, every post-mortem |
| `scripts/phasep/` | the study harness |

## The frozen tables are not committed here

The 149 `table.jsonl` files — 1,728 measured rows each, **215 MB** — are **not** in this branch.
`FREEZE_MANIFEST_V2.json` pins every one of them by sha256, so a copy can be verified byte-for-byte
against what the study used.

Committing 215 MB into a repository whose `.git` is 3 MB is a publishing decision with a real and
hard-to-reverse cost, and it belongs to a human rather than to the process that generated the data.
The manifests, the reports and the code that produced them are all here; the bulk data is one
decision away.

## How to read a negative result

Every headline finding on this branch is something that did not work. That was the expected outcome
and it was pre-registered as an acceptable one: *honest negatives — a class that will not populate,
an algorithm that never wins, Motif adding nothing — are valid, reportable outcomes.*

The shipped product is the residue: the one algorithm that won, with the routing installed as a
negative, and a certificate that states what it does not prove.
