# ACTION PLAN PROMPT — Resolve I-1 numeric gate (Step 0.5.3) → Phase 0 exit → Phase 1

> Paste into Claude Code CLI. Resuming mid-Phase-0; `STATE_PHASE0.md` is blocked at Step 0.5.3.
> Roadmap is law; `CLAUDE.md` is how-to. On conflict, roadmap wins.

---

## DECISION ALREADY MADE — DO NOT RE-LITIGATE

The I-1 numeric-loop gate fired red: `csr_scale` (raw-pointer) **PASSES 1.964×** (≥ 1.15×);
`pava` (numeric-loop) **FAILS 1.231×** (< 1.5×). `debug-mantra` has already established the
mechanism: PAVA pooling is inherently **sequential + division-bound** (decomposition: directive
removal 1.19×, gcc opt 1.05×; neither path reaches 1.5×). **The instrument is correct.**

**Root-cause classification — this is a *roadmap defect*, not an instrument failure and not a
code defect.** Step 0.5.1 pinned PAVA as the numeric-loop reference *and* §0.3 pinned the
numeric-loop margin at 1.5×; those two pins are mutually incompatible because PAVA is
structurally out-of-class for a 1.5× margin. I-1's stated purpose (§0.3) is to prove the rig can
**detect a known large speedup** — so the reference kernel must be one with *provable large
headroom*, not one sitting near the detectability floor. Calibrate the scale with a known weight,
not with something that might or might not weigh enough.

**Resolution = Option 1 (swap the numeric-loop reference), with the corrected justification
below.**
- NOT Option 2: do **not** lower the 1.5× threshold. It permanently dulls the gate's
  discriminating power for every future numeric kernel to accommodate one atypical one.
- NOT Option 3: the mechanism is **impl-invariant** (sequential dependency + division latency
  do not change with a different faithful PAVA). Re-probing is redundant — `debug-mantra`
  already produced the decomposition.

**Change classification (binding):** this is a **Phase-0 instrument-definition correction**,
analogous to the v1.1 document revisions — it does **NOT** consume the single experiment
amendment (Appendix B-12 / Steps 1.3.3 / 1.5.6). It is also **not** a D-series empirical defect
(D1/D2 are *silent code* defects); record it as a documented roadmap correction + STATE
rationale + `scrutinize` sign-off. Do **not** manufacture a D-series `post-mortem` for a spec
mis-pin.

---

## STEP 0.5.3-R — Resolve & re-validate (in order)

- [ ] **R1 — Pick ONE replacement numeric-loop reference a priori, before any measurement.**
      Required class: a **vectorizable FP reduction with genuine FMA + reassociation headroom** —
      e.g. a squared-Euclidean-distance / dot-product accumulation (Lloyd/k-means inner-loop
      archetype) or a Horner-polynomial-over-array accumulation. The justification **must** be:
      *"this kernel's ≥ 1.5× headroom is derivable from the optimization mechanism (AVX2
      vectorization + FMA + `-ffast-math` reassociation) — exactly the class the numeric-loop
      gate exists to detect."*
      **Do NOT justify the swap with csr's 1.96×** — csr is the raw-pointer path and says nothing
      about numeric-path detectability. The two paths have different thresholds for a reason.
- [ ] **R2 — Record the expected speedup + mechanism derivation BEFORE measuring** →
      `/results/characterization/I1_numeric_kernel_choice.md`, committed. This pre-commitment is
      what separates a principled swap from kernel-shopping.
- [ ] **R3 — Feasibility check against I-3.** If `-ffast-math` reassociation pushes the reduction
      outside its declared tolerance, fast-math is infeasible for it → headroom must then come
      from vectorization + FMA alone; verify *that* path still derives ≥ 1.5× a priori, else pick
      a different in-class kernel. Choose the kernel whose headroom is robust to the oracle.
- [ ] **R4 — Re-run Steps 0.5.2 / 0.5.3** with the new numeric kernel at K_final, paired inputs.
      **ONE run.**
- [ ] **R5 — Branch:**
      - PASS ≥ 1.5× → I-1 satisfied (csr 1.96× raw-pointer + new kernel ≥ 1.5× numeric); record.
      - FAIL → this is now a **genuine instrument problem** (a known-headroom kernel the rig
        cannot resolve). STOP, invoke `debug-mantra`, escalate to the human. **Do NOT swap to a
        third kernel** — swapping until one passes is gate-gaming and is forbidden (§6.1).
- [ ] **R6 — Preserve the PAVA finding (mandatory, not a footnote).** Record pava's full-config
      Δ = 1.231× with the 1.19× / 1.05× decomposition under `/results/characterization/` as a
      known **low-Δ kernel**. This is RQ1-relevant signal: PAVA = `sklearn.isotonic/_isotonic.pyx`
      is a **real corpus unit** (§4.3); its 1.23× barely clears the §4.1c per-unit **1.2× floor**
      and contributes **nothing** toward the corpus-median-Δ-≥-1.5 admission. Flag explicitly in
      STATE that sequential / division-bound units (PAVA-class; watch `_cd_fast` coordinate
      descent, Bellman–Ford in `_shortest_path`) are an early **downward pressure on corpus-median
      Δ** and therefore an **RQ1-difficulty risk** to confront at Step 1.3 — not at 1.5.6 by surprise.
- [ ] **R7 — Update `STATE_PHASE0.md`:** decision + rationale (verbatim), raw paths, the roadmap
      correction note, `scrutinize` sign-off. `next_action = Step 0.P`.

---

## STEP 0.P — Phase 0 preflight (§6.6) — advance only at 100%

- [ ] Digest/hash validation (image digest, `TOOLCHAIN.lock`, `requirements.lock`, golden hashes,
      input manifests).
- [ ] Memory profiling: peak RSS (orchestrator + worst candidate + 2 GB tmpfs) < 12 GB ceiling.
- [ ] Sanitizer-clean confirmation on the known-good build.
- [ ] Raw-data presence: every claimed number resolves to a committed raw file.
- [ ] `scrutinize` complete; all four auditors pass (or n/a with written justification).

**Phase 0 exit (all required):** I-1 pass with stated margins (csr 1.96× + new numeric ≥ 1.5×) ·
I-3 oracle suite green + manual validation gate signed in STATE · ASan/UBSan clean on known-good ·
pilot report committed with K_final + thermal threshold set · preflight 100%. Close
`STATE_PHASE0.md`; open `STATE_PHASE1.md` with `next_action = Step 1.1.1`.

---

## PHASE 1 — proceed per `PHASE1_ACTION_PROMPT.md` §1.1 → §1.P

Execute the existing Phase 1 checklist unchanged, with **one carry-forward** baked in from R6:

- At **Step 1.3** (landscape characterization), the PAVA-class low-Δ finding is a **prior
  expectation, not a surprise**. When you compute corpus-median Δ and the ≥ 70%-of-units-≥-1.2
  admission (§4.1c): if sequential / division-bound units drag the median below 1.5, that is
  precisely the **§1.3.3 trigger**, and the single permitted amendment (extended flag space
  **or** corpus revision) is the only lever. **Ask the human before spending it** (Appendix B-12).
- Do not let the kernel swap erase the lesson: a measurable slice of the corpus may be
  near-flat, which is the central thing standing between you and an RQ1-positive. Surface it
  early in the characterization report, not late in 1.5.6.

---

Begin at **R1**. State the chosen kernel + its mechanism-derived expected speedup **before**
running anything.
