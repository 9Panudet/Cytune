# What happened when four people tried to break it

The README claims cytune refuses to recommend things it cannot stand behind. This is what happened
when that claim was tested by agents with no stake in the answer: a first-time user, an adversary
attacking the trust layer, a QA engineer working a stability matrix, and a senior engineer
evaluating it for CI.

**Five defects were found in a few hours, on a codebase with 900+ tests and four standing gates.
Four of the five produced a confident wrong answer rather than an error.** All five are fixed. The
findings that were not fixed are listed at the end, with the reason.

This page is here because a tool that says "we test it thoroughly" and a tool that publishes what
the testing found are making different claims.

---

## The five

| id | what | found by | how long |
|---|---|---|---|
| **D26** | the correctness oracle could not fail | a first-time user | on the first kernel they wrote |
| **D27** | the sanitizer gate's checks and its licence keyed on different fields | an adversary | ~30 min |
| **D28** | an edited kernel silently reused the previous kernel's calibration | a QA breaker | stability cell 2c |
| **D29** | `doctor` said `[ok]` on a toolchain digest mismatch | a QA breaker | stability cell 9 |
| **D30** | a 215× calibration miss reported as success | a QA breaker | stability cell 7a |

### D26 — the one that matters most

A first-time user wrote `clip(x, lo, hi)`. `cytune init` invented `1.0` for both bounds, so
`lo == hi`, so every output element was identical. The correctness check compares each build against
a golden — and a constant golden **cannot fail**. Every build matched.

cytune reported `IMPROVEMENT 1.0790x` on a kernel that is flat, printed `rejected as incorrect: 0
(0.0% of measured)` as though that were evidence, and `--apply` wrote a `boundscheck=False` header
into the user's source. Fixing one line of the driver turned the same run into `HONEST-FLAT`.

**Why it is here rather than quietly patched:** the guarantee cytune is built on had no positive
control. Every other instrument in this project is required to have one — a planted lever must be
detected, a known-flat kernel must read flat — and the oracle had none for its entire life. It now
refuses to tune when the correctness check cannot fail.

### D28 and D30 — the calibration pair

D28: after you edit your kernel and re-run into the same workspace, cytune used to reuse the
*previous* kernel's calibrated workload. It printed *"cache invalidated because the module source
changed"* and then, eight lines later, *"reusing the calibrated REPS … module … unchanged"*. A user
who asked for a 5 ms reference got 23.3 ms with `target_ms: 5.0` on the certificate.

D30: on a kernel whose single call is ~16 ns, cytune printed `calibrated REPS: 1 → 1431 (reference
~5.0 ms)` and the same document then measured the reference at **0.023 ms**, under a confident
`IMPROVEMENT 1.1709x`.

Both are now caught. The shared lesson, which is the useful part: **the tool had both numbers and
never compared them.**

### D27 — the adversarial one

Every *check* on the memory-safety gate was conditioned on "did it run"; every *licence* granted by
it on "was it clean". A gate claiming both `ran=False` and `clean=True` was checked by nothing and
licensed by everything. The adversary used it to render `CLEAN — config 7 … ran with no report` on a
certificate emitting config 0.

One predicate now answers the question, and every consumer calls it.

---

## What held

Not everything broke, and the list matters as much as the failures:

* **the artifact binding layer** — six separate attempts to make the certificate claim one
  configuration while a different one was built, timed or gated. All six blocked, each by a named
  invariant.
* **concurrency** — a second run refused while the first held the machine, naming the holder; eight
  subsequent runs serialised correctly.
* **interruption and resume** — killed mid-build and mid-measure, then re-run; both landed inside
  the clean-run band.
* **a lying driver** — a `canon()` returning a constant was refused (that is D26's fix, confirmed
  independently); a non-deterministic `canon()` was refused with `determinism_gate_FAIL`.
* **a planted time-drift lever** — defeated by per-measurement process isolation. A real negative
  control passing.
* **unicode and spaces** in module paths, workspace paths and session names.
* **hostile config files** — garbage TOML, unknown keys, wrong types, absurd values: all rejected
  with named errors before any measurement began.

---

## What is known and not fixed

Published rather than omitted. Full text in [`../docs/KNOWN_ISSUES.md`](../docs/KNOWN_ISSUES.md).

| id | what |
|---|---|
| K-12 | C1's timing cross-check estimates its noise floor from the driver's own reported clocks, so a sufficiently noisy driver can disarm it. The certificate's attestation used to claim C1 catches *any* fabricated speedup; that sentence was false and has been corrected |
| K-13 | a directive is only checked for inertness when two builds differing in exactly that directive were made |
| K-14 | the provenance block is assembled separately from the check that binds the decision |
| K-15 | a `preset` in `.cytune.toml` overrides that same file's `target_ms`, and the provenance names a flag that was never typed |
| K-16 | two identical runs can emit different directive headers when the winner is a near-tie, and the tie is not disclosed |
| K-17 | a read-only workspace raises an unhandled `PermissionError` |

K-12 is the one to read if you are deciding whether to trust a speedup claim. Its short form: **your
driver is inside the trust boundary**, and the certificate says so itself — it is evidence to
whoever controls the driver, and not evidence to a third party.

---

## The honest conclusion

The four standing gates in this release were each built to catch a class of defect this project had
already suffered. They work — each has a control proving it can fail — and in this campaign they
caught **nothing new**.

The testers caught five things in an afternoon, and two of them were reached by using the tool
normally rather than attacking it.
