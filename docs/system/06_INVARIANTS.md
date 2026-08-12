# The invariants — I1, I2, I3, I4

`src/cytune/invariants.py` holds them as DATA: `(id, guarantees, callable, production site, test)`.
`test_cytune_invariants.py` walks that registry and fails if an id is duplicated, if a production
site does not exist, if a named test is missing, if an enforced invariant has no entry, or if an
entry has no enforcement (a dead letter). The registry cannot drift from the code without a test
going red.

23 invariants, four families. The families are not arbitrary — each answers a different question.

| family | question |
|---|---|
| **I1** | does the document contradict itself? |
| **I2** | did the decision follow the rules, at the moment it was made? |
| **I3** | is this run about the code as it is *now*? |
| **I4** | is the claim tied to the bytes that produced it? |

---

## I1 — coherence. Enforced in `coherence.py`, called from `cli.tune` before a byte is written.

| id | guarantees |
|---|---|
| I1.1 | the verdict, the exit code and the rendered VERDICT line all agree |
| I1.2 | the directives and flags PRINTED are those of the emitted config id |
| I1.3 | every FP-semantics field agrees with the emitted flag string |
| I1.4 | `sanitizer_gate` describes the config actually emitted, never another |
| I1.5 | a gate that did not run qualifies the summary and sets the machine-readable field |
| I1.6 | the field that licenses safety wording agrees with the gate, and only then |
| I1.7 | anything not certified as an improvement emits the user's own reference |
| I1.8 | a speedup is printed only for an improvement |
| I1.9 | the document honours its own published JSON schema |
| I1.10 | `certificate.txt` is exactly what `certificate.json` renders to |

**Why raising is right.** A self-contradicting certificate is worse than no certificate. The CLI
prints nothing and writes nothing, and says it is a cytune defect rather than a user error.

**Motivating defects:** I1.2 ← P2 (printed directives were the candidate's, not the emission's).
I1.3 ← D14 ("fast-math: not opted in" beside an emitted `-ffp-contract=fast`). I1.4 ← the cold-user
F5 finding. I1.10 replaced five substring searches with one exact statement.

## I2 — decision rules, enforced inside `certify.build_certificate` on every run

| id | guarantees |
|---|---|
| I2.1 | a candidate that does not clear the emit margin is demoted to the reference |
| I2.2 | a sanitizer-reporting candidate is refused and replaced by the reference |
| I2.3 | a rejected winner has been replaced by the reference before certification |
| I2.4 | the word "safe" is downgraded unless the gate cleared |
| I2.5 | `--apply` refuses anything that is not an improvement gated CLEAN |

These are `AssertionError`s in the builder rather than checks in the CLI, deliberately: they hold
for *any* caller that assembles a certificate, not only for `cli.tune`.

**Known asymmetry, registered as path V-10 in `paths.py`:** I2.1's guard tests the emit margin
only, while `cli.tune` demotes on margin **and** endpoint separation. A caller mirroring the CLI on
margin alone can assemble an `honest-flat` certificate with a non-reference winner — which I1.7
then refuses. Production and its source-of-truth guard disagree about what "clears" means, and that
is written down rather than smoothed over.

## I3 — freshness, enforced around the cache

| id | guarantees |
|---|---|
| I3.1 | a changed module or toolchain image invalidates cached builds **and** timings |
| I3.2 | a changed driver, workload, rig mode or oracle invalidates cached timings |
| I3.3 | discarded measurements are archived, never destroyed |
| I3.4 | `certificate.json` re-renders to `certificate.txt` byte-for-byte |

**Motivating defects:** D17 (build resume trusted the manifest alone; a pruned `_so` produced
"built 17/17" then an ImportError) and D18 (the verify stage never built its own inputs, so a real
2× degraded to honest-flat).

I3.3 matters more than it looks: an invalidation that *deletes* leaves no way to ask afterwards
what the old numbers were.

## I4 — binding. `binding.py`, called from `cli.tune` before the certificate is assembled.

This is the layer 1.0.0 was built for, and the only family that fires on things outside cytune's
control — the user's kernel, their environment, their build.

| id | guarantees |
|---|---|
| I4.1 | the emitted configuration names the artifact that was actually timed |
| I4.2 | the directives cytune varies actually change the generated code |
| I4.3 | the sanitizer verdict is about this configuration, this source tree, this build |
| I4.4 | a timing reported as decision-grade carries the rig fingerprint `measure_wrap` verified |

**I4.3 caught D-3 in production**, under 674 green tests: a demotion path left the *candidate's*
sanitizer verdict attached to a certificate emitting the *reference*, and I4.3 refused the whole
document rather than emit one about a run that did not happen. That refusal was correct, and it is
what a binding layer is for.

**I4.2 is a refusal to tune, not a refusal to certify.** If every directive combination produces
byte-identical generated C, the search cannot mean anything and the fastest build is whichever was
luckiest. cytune stops.

---

## The one that is not in the registry, and why

`Session.oracle_power()` (D26) refuses to tune when the correctness oracle cannot fail — a
multi-element golden whose every element is identical. It is a **control on an instrument**, not an
invariant about a document, so it sits with the measurement path rather than in `invariants.py`.

It is worth knowing that it existed nowhere until a first-time user hit it on their first kernel.
G1 — the guarantee the whole product rests on — had no positive control for the whole of its life.
See `logs/defects/D26.md`.
