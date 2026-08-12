# ACTION PLAN PROMPT — Phase 0 FINAL CLOSE (Horner precision + protocol lock + human gates → Phase 1)

> Paste into Claude Code CLI. Phase 0 is held at 0.P. G0/G1 resolved; G2 resolved on the csr side.
> Human decisions now fixed: **canonical roadmap location = repo root**; **G2 protocol = quiesce-all
> (see C)**. One open technical item (Horner precision, B) and two human gates remain.
> Roadmap is law; `CLAUDE.md` is how-to. On conflict, roadmap wins. Do not close Phase 0 until E.

---

## A — Finalize G0 (location decided = root)

- [ ] **A.1** Confirm exactly **one** canonical roadmap at repo root. Delete any `prompts/` remnant
      if present. Verify: `git ls-files '*oadmap*'` returns a single path at root, and
      `find . -iname '*roadmap*.md'` shows one file. Confirm `CLAUDE.md`'s references resolve to
      the root copy (no stale `prompts/` paths).
- [ ] **A.2** Re-verify the canonical content: `git show HEAD:Motif+BO-Roadmap.md | sed -n '482p'`
      must print the **Horner** numeric-reference row, and `git show 2b69ab2 -- Motif+BO-Roadmap.md`
      must contain the PAVA→Horner edit. Record both in STATE. This is the precondition for P0e (D.1).

---

## B — Horner precision (criterion 4, BOTH pilot kernels) — REQUIRED before the §5.1 lock

Exit criterion 4 ("per-kernel IQR within the pilot-set bound", §5.1) binds **both** Step-0.5 pilot
kernels — csr **and** Horner. The G2 work resolved csr only. Protocol (i)/quiesce is memory-bound;
it **cannot** fix Horner, which is compute-bound — its variance is short-runtime timer/scheduling
jitter at ~5.3 ms, not DRAM contention.

- [ ] **B.1** State Horner's **contention-free pilot CI@30** (median CI half-width) explicitly from
      `/results/pilot/`. Last turn you reported Horner-good **single-shot IQR ~13%** at ~5.3 ms —
      show the **pilot K_final median-CI statistic**, not the single-shot IQR. These are different
      numbers; do not substitute one for the other.
- [ ] **B.2 Branch:**
      - **CI@30 ≤ bound (≤ 1%)** → criterion 4 met for Horner; record with the raw pointer (the 13%
        single-shot was an unrepresentative single observation, not the median CI). No remedy needed.
      - **CI@30 > bound** → apply a **Horner-specific** remedy (quiesce does nothing here):
        **preferred — lengthen the Horner reference input** so one measured run is long enough to
        average out per-iteration jitter (double win: keeps K_final = 30 uniform per §5.1, and moves
        the reference into the 50–500 ms corpus band instead of an unrepresentative 5.3 ms). After
        lengthening, **re-confirm the I-1 ratio (≥ 1.5×) and the oracle pass at the new input scale**,
        then re-measure CI@30. (Alternative — a Horner-only higher K — is acceptable since Horner is a
        calibration reference, not an RQ1 endpoint, but it breaks K uniformity; prefer lengthening.)
- [ ] **B.3** Re-confirm criterion 4 for **both** pilot kernels with raw pointers: csr under the C
      protocol, Horner under B.2. Only then is exit criterion 4 actually met. Do not let "csr fixed"
      stand in for "criterion 4 met".

---

## C — Lock the measurement protocol (decision fixed: quiesce-all)

- [ ] **C.1 Adopt quiesce-all:** compile workers on cores 0–1 are **quiesced during every measured
      run**, for **all** units — not only memory-bound ones — so the measurement core owns DRAM
      bandwidth on each measured run. Rationale (human decision): eliminates the
      memory-boundedness-**classification** failure mode entirely — a unit misclassified as
      compute-bound would otherwise leak DRAM contention into RQ1 endpoints. Correctness over throughput.
- [ ] **C.2 Report the cost:** measure wall-clock for quiesce-all vs the memory-bound-only variant
      (the lost compile/measure overlap). If the delta materially threatens the §1.5 compute envelope,
      surface it explicitly — the decision is reversible to memory-bound-only (protocol (i)), itself a
      documented revision; **default stays quiesce-all** unless the human revisits after seeing the cost.
- [ ] **C.3 Apply §5.1 v1.2** to the canonical root roadmap: the quiesce-all measured-run protocol.
      Log in the header Revision log as a **mid-Phase-0 DOCUMENT REVISION** — explicitly **not** an
      Appendix B-12 experiment amendment (no corpus/search-space change), and explicitly noting it
      **predates any RQ1/endpoint data**.
- [ ] **C.4 measurement-auditor RE-SIGNS** under the final protocol, with criterion 4 met for both
      kernels (B.3) — a clean **PASS**, not PASS-with-concerns. A "with-concerns" verdict on the exact
      criterion the auditor covers is not acceptable at exit.

---

## D — Human gates

- [ ] **D.1 P0e (ack) — clearable now.** Location decided = root (human, A); Horner edit 2b69ab2
      confirmed canonical (A.2); instrument-definition fix, no B-12 amendment consumed, not D-series,
      scrutinize-signed, I-1 grounding valid. **Record P0e acked in STATE** and clear that part of
      `blocking`.
- [ ] **D.2 I-3 (manual validation gate) — PRESENT for human review; do NOT self-sign.** Assemble a
      reviewable evidence pack and surface it:
      - a sample `oracle.json` from each class — one **bit-exact** unit and one **tolerance** unit
        (show the tolerance-setting per §3.1);
      - a sample of **feasibility labels** with their backing raw (compile log, sanitizer log,
        oracle diff, timing vector per §3.5);
      - the 316-test summary;
      - the full-§3.3-input sanitizer-clean logs, including the G1 Hypothesis corpus (0/80).
      The manual gate **is** the human's own validation — wait for the human's signature in-session;
      record it only once given. Do not record a signature on the human's behalf.

---

## E — Phase 0 close (only after D.2 is signed)

- [ ] Re-run preflight (§6.6); confirm **all five** exit criteria: I-1 pass with margins;
      I-3 reliable (suite green + **human signature** recorded, D.2); ASan/UBSan clean on the full
      §3.3 input set (G1); timing variance — criterion 4 met for **both** kernels (B.3) under the
      locked protocol (C). Item 100% or the phase does not advance.
- [ ] All four auditors clean: measurement re-signed (C.4); validation and stats clean; bo-math
      **n/a** with written justification (no surrogate code yet). `scrutinize` re-run on the close-out.
- [ ] `blocking` cleared (P0e acked, I-3 signed). **Close `STATE_PHASE0.md`.** Open
      `STATE_PHASE1.md` (§6.4 schema), `next_action = Step 1.1.1`, carrying forward in its first entry:
      1. **quiesce-all measurement protocol** (C) — binding on all Step-1.2 drivers;
      2. **PAVA-class low-Δ watch-list** (PAVA, `_cd_fast`, Bellman–Ford) → §1.3.3 single-amendment
         trigger (**ask-human**, Appendix B-12);
      3. **I-1 discrimination-band scope note** — I-1 validated a *large* speedup, not 1.2–1.6× band
         precision; that precision is established at Step 1.2, not assumed from I-1's ratio.

---

## F — Handoff: Phase 1 per `PHASE1_ACTION_PROMPT.md` §1.1 → §1.P

Proceed unchanged, with these bindings from this close-out:
1. **Step 1.2** — every driver runs under the **quiesce-all** protocol; per-unit CI@30 ≤ 1% is
   **genuinely re-established there** (the I-1 ratio does not stand in for per-unit precision).
2. **Step 1.3** — PAVA-class sequential/division-bound units are expected downward pressure on
   corpus-median Δ (§4.1c: median ≥ 1.5, ≥ 70% units ≥ 1.2). If they pull the median under 1.5, that
   is the §1.3.3 single-amendment trigger — **ask the human before spending it**.

---

Begin at **A.1**. Resolve B (Horner CI@30) and report the number before applying the §5.1 v1.2 lock.
