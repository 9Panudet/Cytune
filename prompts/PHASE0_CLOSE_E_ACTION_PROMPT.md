# ACTION PLAN PROMPT — Phase 0 close-out (E): corrections + hygiene carry-forward → open Phase 1

> Paste into Claude Code CLI. The three verification points are resolved; criterion 4 is met for
> both kernels (two independent runs ≤ 1%). Before E, record two honesty corrections and one new
> Phase-1 carry-forward; then execute E **only on the human's in-session I-3 signature**.
> Roadmap is law; `CLAUDE.md` is how-to. On conflict, roadmap wins.

---

## PRE-CLOSE — record corrections in STATE (do now, before E)

These do not change any pass/fail verdict; they correct overclaimed *interpretations* so STATE
reflects what the evidence actually supports.

- [ ] **COR1 — Reframe the contention-freeness claim.** The re-measure was free of **variable
      compile contention** because the protocol pauses cores 0–1 during the measured window — that
      **structural guarantee** is the basis, not `eff_ghz`. `eff_ghz` flatness confirms the
      **frequency** was held; it does **not** establish memory-stall-freeness (a core stalled on
      DRAM runs at flat frequency while stalling). The admitted facts — median 70.2→78.2 ms
      (+11%) and ratio 10.441×→9.425× (−10%) — are consistent with a **steady additive ~8 ms
      background offset** on both good and bad (an additive offset compresses a >1 ratio toward 1),
      which is **conservative for the I-1 ratio and does not inflate the CI**. Record the claim as
      *"free of variable compile contention (by protocol) + a steady background offset"*, not
      *"contention-free, proven by eff_ghz."*
- [ ] **COR2 — Qualify the seed-robustness result.** The 12 identical CI@30 values demonstrate
      **bootstrap-RNG invariance** (the n=30 order-statistic effect you correctly identified) — they
      do **not** demonstrate measurement/input robustness. The actual robustness evidence is the
      **two independent measurement runs** (0.964% pre-verify, 0.8707% re-measure), both ≤ 1%
      (n=2, thin but passing). Record that as the basis; stop presenting bootstrap-seed invariance
      as worst-case robustness.
- [ ] **COR3 — Keep both memory bounds.** State **both** the observed Horner-64M peak (additive
      3.05 GiB) **and** the cap-based worst-case guarantee (orchestrator + 4 GiB candidate cap +
      2 GiB tmpfs = 6.05 GiB). The cap-based figure is the real guarantee (no candidate exceeds
      4 GiB without a kill); both < 12 GiB. Do not drop it.

---

## NEW PHASE-1 CARRY-FORWARD — measurement-environment hygiene (CF4)

- [ ] **CF4** — A steady ~8 ms (~11% of the Horner median) run-to-run offset appeared between two
      "clean" runs; `eff_ghz` was flat (frequency ruled out) and thermal was clean (throttle ruled
      out), so the source is **unidentified**. The agent attributed it to "background load" **without
      ruling out transparent-huge-page / page-fault variance** on the 512 MB streaming allocation
      (4 KB pages → TLB thrashing vs THP → none; a known large-streaming-kernel effect). This does
      **not** block Phase 0 (it cancels in within-unit paired RQ1 comparisons and is conservative
      for ratios). **Before Step 1.2 corpus measurements:**
      1. Determine the actual cause — background process **or** THP/page-fault variance (run with
         an explicit hugepage / pre-fault policy and compare; check an idle-baseline run with no
         candidate for residual load).
      2. Bring the measurement core to a **verified-quiet baseline** and pin the page policy.
      3. Document the residual offset and its bound.
      Rationale: RQ1's whole thesis is per-unit runtime differences; a measurement floor that drifts
      11% run-to-run is a liability even when it cancels in pairs.

---

## E — Phase 0 close (execute ONLY on the human's in-session I-3 signature)

- [ ] **Gate on the signature.** The human reviews `results/preflight/I3_validation_gate_pack.md`
      (a sample `oracle.json` per §3.1 class; feasibility labels vs their §3.5 backing; the 155-case
      full-§3.3 sanitizer-clean; non-vacuous negatives) and signs in-session. **Do not self-sign;
      do not proceed to E without the signature.**
- [ ] **On signature — re-run preflight (§6.6) at 100% and sweep auditors on the FINAL raw
      (1b9e6a7)**, which supersedes the raw the measurement-auditor saw at C.4:
      - `measurement-auditor` re-confirms criterion 4 on the re-measured raw (csr 0.315% pilot +
        Horner 0.8707% worst-seed) **under the COR1 framing** (variable-compile-contention-free by
        protocol + steady offset) — clean PASS.
      - `validation-auditor` re-confirms the 155-case sanitizer-clean incl. the G1 Hypothesis 0/80.
      - `stats-auditor` re-confirms zero-diff on every reported number from raw.
      - `bo-math-reviewer` **n/a** (no surrogate code) with written justification.
      - fresh `scrutinize` on the close-out.
- [ ] **Record the human signature in STATE.** Clear `blocking`. **Close `STATE_PHASE0.md`.**
- [ ] **Open `STATE_PHASE1.md`** (§6.4 schema), `next_action = Step 1.1.1`, with **four**
      carry-forwards in the first entry:
      1. **quiesce-all measurement protocol** — binding on all Step-1.2 drivers;
      2. **PAVA-class low-Δ watch-list** (PAVA, `_cd_fast`, Bellman–Ford) → §1.3.3 single-amendment
         trigger (**ask-human**, Appendix B-12);
      3. **I-1 discrimination-band scope note** — I-1 validated a *large* speedup, not 1.2–1.6× band
         precision; precision is established at Step 1.2, not assumed from the I-1 ratio;
      4. **CF4 measurement-environment hygiene** — identify + control the ~8 ms offset (background
         vs THP/page-fault) and pin a verified-quiet baseline before Step 1.2.

---

## HANDOFF — Phase 1 per `PHASE1_ACTION_PROMPT.md` §1.1 → §1.P

Proceed unchanged, with these bindings:
1. **Step 1.2** — every driver runs under the **quiesce-all** protocol **and** on a **verified-quiet
   measurement baseline** (CF4 resolved: offset source identified, page policy pinned); per-unit
   CI@30 ≤ 1% is genuinely re-established there (the I-1 ratio does not stand in for per-unit
   precision).
2. **Step 1.3** — PAVA-class sequential/division-bound units are expected downward pressure on
   corpus-median Δ (§4.1c: median ≥ 1.5, ≥ 70% units ≥ 1.2). If they pull the median under 1.5,
   that is the §1.3.3 single-amendment trigger — **ask the human before spending it**.

---

Record COR1–COR3 and CF4 now. Then await the human's I-3 signature before executing E.

**HUMAN SIGNATURE: APPROVED. Proceed with E immediately.**
