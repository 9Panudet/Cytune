# ACTION PLAN PROMPT — Augment the I-3 evidence pack before signature (D.2)

> Paste into Claude Code CLI. The human reviewed `results/preflight/I3_validation_gate_pack.md`
> strictly and is **withholding signature**: the pack demonstrates that the rig *accepts* good
> configs and *detects process crashes*, but never demonstrates that it *rejects configs that run
> cleanly yet produce wrong/out-of-tolerance output* — the discriminating behavior the I-3 gate
> exists to validate. Augment the pack, then re-present. Do NOT self-sign.
> Roadmap is law; `CLAUDE.md` is how-to. On conflict, roadmap wins.

These are **evidence-completeness** additions. The underlying tests likely already exist (316 tests,
oracle subset 108) — surface and document them. If any genuinely does not exist, add it via TDD
(§6.3, red→green) and say so explicitly; a vacuous or after-the-fact test is not acceptable.

---

## P1 — Exhibit worked `feasible=0` for every NON-process-crash §3.5 cause (the core gap)

Every feasibility example in the current pack is `feasible=1`; the process-smoke fixtures show
*detection* but not the composed `feasible=0`, and they are crashes, not correctness failures.
Add a worked, raw-backed `feasible=0` case for each of the following §3.5 causes — show the config,
the backing artifact (oracle diff / sanitizer / exception), and the resulting `feasible=0`:

- [ ] **P1a — correctness-critical value mismatch → 0**: a config that compiles and runs `rc=0`
      but produces a wrong bit-exact value; show the bitwise comparator catching it and the label = 0.
- [ ] **P1b — numeric outside declared tolerance → 0**: a config whose numerically-approximate
      output exceeds `atol+rtol·|g|`; show `max|diff| > tolerance` and label = 0. (Contrast with the
      existing Horner PASS case 3.109e-15 ≤ 3.663e-9.)
- [ ] **P1c — wrong / missing exception → 0**: the cdivision zero-divisor case where the candidate
      fails to raise (or raises the wrong type); show exception-identity mismatch → label = 0.
- [ ] **P1d — fast-math on a bit-exact output → infeasible (§3.2(1)) — REQUIRED.** This is the
      central empirical-exclusion mechanism the whole approach rests on ("preserve the optimization
      ceiling at zero correctness cost"). Exhibit it concretely: a configuration with `fast_math=on`
      on an output declared **correctness-critical** yields `feasible=0` (via correctness-critical
      mismatch). A feasibility-function unit test (`feasible(fast_math=True, class=bit-exact) == 0`)
      is sufficient and needs no kernel; if a kernel-level demonstration exists, show that too.
      Without this, the project's core safety claim is unvalidated at the gate.

---

## P2 — Exhibit the negative-operand cdivision probe (§3.2(4))

- [ ] §3.2(4) requires **negative-operand AND zero-divisor** probes for every dividing kernel; the
      pack shows only `int_zero_divisor`. For the dividing reference kernel (pava), exhibit the
      **negative-operand** probe — the C truncate-toward-zero vs Python floor divergence
      (e.g. `-7 / 2`: C `-3` vs Python `-4`) — and show the **bit-exact comparator catching the
      value divergence** under `cdivision=True` (a missed divergence must be a failing test, per
      Step 0.3.4). This is a value mismatch, not an exception.

---

## P3 — Clarify the signature's scope (§3.1 tolerance derivation)

- [ ] The current tolerance exemplar shows the manifest value (`atol=rtol=1e-9`), the degenerate
      (zero) rejection, and `tolerance.py` **scaling** (`rtol·|golden|`) — i.e. the comparator
      machinery. It does **not** show the §3.1 **derivation** procedure
      (`tolerance = max(10 × observed cross-repetition deviation, domain-justified floor)`), which
      is applied to corpus `oracle.json` at **Step 1.1.3 (Phase 1)**. State this in the pack
      explicitly: **the I-3 signature attests to the comparator + feasibility RIG and the
      calibration-kernel oracles — NOT to corpus tolerances, which do not exist yet.** If a
      derivation unit test already exists (e.g. fed a synthetic cross-rep series, it returns
      `max(10×dev, floor)`), exhibit it; otherwise note it as Step-1.1.3 scope.

---

## P4 — Enumerate the §3.3 edge cases actually present

- [ ] The 75-case numpy set is asserted "golden+edge+property". §3.3 names the required edge cases:
      empty arrays, single-element, max-stride / **negative-stride** views, NaN/Inf (where the domain
      admits), zero divisors, boundary indices. Itemize which of these are present in the csr (37) and
      pava (38) sets — a small table mapping each §3.3-named edge case to its case count — so the
      "edge" claim is verifiable rather than asserted.

---

## P5 — Re-present; do NOT self-sign

- [ ] Recommit the augmented `I3_validation_gate_pack.md` (raw/test pointers for every new exhibit).
- [ ] Note in STATE which exhibits were **surfaced from existing tests** vs **newly added via TDD**
      (with the red→green evidence for any new one).
- [ ] Re-present the pack for the human's in-session signature. The gate stays open; do not self-sign;
      do not proceed to E (close) until the human signs the augmented pack.

---

## Scope guard

This augments the **I-3 evidence pack only**. It does **not** reopen A (roadmap), B (Horner
criterion 4), C (quiesce-all protocol), or the COR1–COR3 / CF4 items — those stand. Phase 0 remains
correctly gated on the I-3 signature; this makes that signature honest.

Begin at P1a. Prefer surfacing existing tests; add via TDD only where genuinely missing, and label which is which.
