# ACTION PLAN PROMPT — Phase 0 close-out (law-fork reconcile + 2 technical holes + 3 human gates)

> Paste into Claude Code CLI. Phase 0 is held at 0.P. Do NOT close Phase 0 or green any exit
> criterion until G0–G2 are resolved and the three human gates are answered.
> Roadmap is law; `CLAUDE.md` is how-to. On conflict, roadmap wins.

---

## CONTEXT — what changed since your last turn

The human moved `Motif+BO-Roadmap.md` from the project root into `prompts/` **intentionally**
(answer to your "deletion intentional?" question = *intentional, reconcile it*). Your
session-start `git checkout HEAD -- <root path>` restore therefore did **not** recover an
accidental deletion — it may have **forked the law document**: the human's working copy at line
482 reads *"(b) numeric-loop path — PAVA-style loop"*, while you believe §0.5.1b was corrected to
**Horner**. Those cannot both be the single source of truth. Resolve this before anything else —
it determines whether I-1 is even validly passed (I-1 ran against Horner; if the canonical law
still names PAVA, the 0.5.3 resolution is ungrounded).

---

## G0 — Reconcile the law fork (BLOCKING; do first)

- [ ] **G0.1 Diagnose the git state. Report verbatim:**
      ```
      git status
      git log --oneline -8 -- 'Motif+BO-Roadmap.md'
      git log -p -S 'Horner' -- '*.md'      # was the Horner edit ever committed, and where?
      git show HEAD:'Motif+BO-Roadmap.md' 2>/dev/null | sed -n '482p'   # HEAD/root copy
      [ -f prompts/Motif+BO-Roadmap.md ] && sed -n '482p' prompts/Motif+BO-Roadmap.md
      sed -n '482p' Motif+BO-Roadmap.md 2>/dev/null                     # current root working copy
      ```
      State plainly: does any commit contain the Horner edit? Which physical copies exist
      (root, prompts/), and what does line 482 say in each? Was your restore a clobber of an
      uncommitted Horner edit?
- [ ] **G0.2 Decide the canonical location WITH the human — do not pick silently.** The human
      moved it to `prompts/`. Confirm the intended home (`prompts/` or root). Check the
      §1.4/0.1.4 pre-commit hook: if it rejects loose root files, the roadmap + `CLAUDE.md` must
      be on its allow-list at whichever location is chosen; if the hook would flag the root
      roadmap, `prompts/` is the consistent home. **Exactly one copy survives; delete the other**
      (`git rm` the loser, `git mv` if relocating).
- [ ] **G0.3 Fix all references to the canonical path.** `CLAUDE.md` hardcodes the roadmap by
      bare name in the header, "Session start", "Hard gates", and the "Where to look" table;
      update them to the chosen path. Confirm your own session-start file-discovery reads the
      canonical copy, not a stale duplicate.
- [ ] **G0.4 Verify / restore the §0.5.1b content in the canonical copy.** Line 482 (Step 0.5.1
      row, numeric-loop reference) must read the intended reference. If G0.1 shows the Horner
      edit was lost in the move/restore, **re-apply it to the single canonical copy** — it is the
      already-scoped instrument-definition correction (PAVA → elementwise degree-11 Horner numeric
      reference), logged in the header Revision log as a pre-/intra-Phase-0 **document revision**
      that does **not** consume the Appendix B-12 experiment amendment and is **not** a D-series
      defect. Keep the original PAVA row's intent recorded as the §4.3 corpus-unit Δ finding, not
      as the I-1 reference.
- [ ] **G0.5 Re-confirm I-1 grounding.** After reconciliation, the I-1 numeric reference (Horner)
      must match what §0.5.1 of the single canonical roadmap says. If the canonical law still says
      PAVA and the human does not re-approve Horner at G-P0e below, **I-1 is not validly passed →
      reopen Subphase 0.5**. Record the outcome in STATE; this is the precondition for the P0e ack.

---

## G1 — Sanitizer carry-forward completeness (the `hypothesis` hole)

Your item-3 carry-forward proved cc1 / libasan.so / python3.12 are byte-identical sha256 across
the `hypothesis` re-pin. That proves the **toolchain** is unchanged — it does **not** prove the
**input set** is unchanged. §3.3 makes Hypothesis property-based cases part of the validation
input set.

- [ ] **G1.1 Establish the fact:** was `hypothesis` installed **and were its property-based cases
      part of the 0.4.2 clean run (the 75 cases)?** Show evidence (the 0.4.2 manifest / case list).
- [ ] **G1.2 Branch:**
      - If `hypothesis` was already present and its cases were in the 75 → the carry-forward is
        complete; record that with the evidence pointer. Done.
      - If `hypothesis` is **newly pinned** (its property cases were NOT in the 75) → the
        byte-identity argument covers re-running the *same* inputs only. Run **one** ASan + UBSan
        pass over the now-available Hypothesis property corpus (fixed seed per unit, committed,
        §3.3) on the known-good build; **require zero reports.** Only then is preflight item 3
        green and the I-3 manual gate signable. Commit the log under `/results/raw/` (gate evidence).

---

## G2 — DRAM-bandwidth contention / pilot optimism (measurement isolation, NOT a mere carry-forward)

measurement-auditor found single-shot IQR **4.09%** with a **DRAM-bandwidth-contention signature**
on the memory-bound reference kernel, exceeding the pilot's 1.00%. Root cause: §5.1 isolates the
measurement **core** (core 3 + idle SMT sibling) but **not the memory channel** — DRAM bandwidth
is shared, and compile workers on cores 0–1 contend with a memory-bound measurement on core 3.
This is a protocol gap, and corpus units `sparsefuncs_fast`, `_shortest_path`, `_dbscan_inner`,
`_traversal` are memory-bound — deferring without a fix moves the contamination onto RQ1 endpoints.

- [ ] **G2.1 Resolve the PASS-with-concerns / exit-criterion-4 contradiction.** Exit criterion 4
      requires *"per-kernel IQR within the pilot-set bound."* If 4.09% single-shot (⇒ median CI
      half-width ≈ 1.1% at K_final = 30) is outside the pilot's ≤ 1% bound, then criterion 4 is
      **not met** and a measurement-auditor "PASS-with-concerns" is not acceptable on it. Force a
      decision; do not straddle.
- [ ] **G2.2 Pick and record a protocol (one of):**
      - (i) **Quiesce compile workers during measured runs of memory-bound units** — serialize
        measure-vs-compile so the measurement core owns DRAM bandwidth during a measured run.
        Preferred; it fixes the root cause for both the calibration kernel and the corpus.
      - (ii) Raise **K_final** until the median CI half-width ≤ 1% under worst-case contention
        (more expensive; does not remove the contention, only averages over it).
      - (iii) Classify the calibration kernels as exempt and defer to Step 1.2 — **only** if you
        first commit that the memory-bound corpus units will be measured under a contention-free
        protocol (i.e. you have effectively chosen (i) for the corpus). Bare deferral is not allowed.
- [ ] **G2.3 Reconcile criterion 4 under the chosen protocol.** Either bring per-kernel IQR within
      the pilot-set bound, or formally re-set the pilot bound / K_final / protocol as a **document
      revision** (header Revision log; not an experiment amendment) with the new numbers and
      rationale. **measurement-auditor RE-SIGNS** under the final protocol (not PASS-with-concerns).
- [ ] **G2.4** Keep the "≤ 1% genuinely re-established at Step 1.2" note in STATE — but as a
      *consequence* of the chosen protocol binding into Step 1.2, not a substitute for resolving
      it now.

---

## HUMAN GATES — answer only after their dependencies clear

- [ ] **G-P0e (law-edit ack)** — depends on **G0**. After the fork is reconciled to one canonical
      copy and line 482 is confirmed, present the committed diff (the PAVA → Horner numeric-
      reference change, and nothing else) for the human's explicit ack. Do not treat the edit as
      acked until the human says so; keep `blocking` set until then.
- [ ] **G-I3 (I-3 manual validation gate)** — depends on **G1**. The validation-auditor PASS is
      the automated proxy only; Phase-0 exit requires the human's signature on the I-3 manual gate
      in STATE. Present it for signature only after G1 confirms the sanitizer-clean result covers
      the full §3.3 input set (incl. Hypothesis cases).
- [ ] **G-move (roadmap relocation)** — handled inside G0 (intentional move → single canonical
      copy + reference fixes). No separate action.

---

## PHASE 0 CLOSE — re-verify, then hand off

- [ ] Re-run preflight (§6.6) and re-confirm **all five** exit criteria, with criterion 4 now
      reconciled under the G2 protocol and item 3 complete per G1.
- [ ] All four auditors at a clean verdict (measurement-auditor re-signed; bo-math n/a justified).
      `scrutinize` re-run on the close-out.
- [ ] G-P0e acked and G-I3 signed; `blocking` cleared.
- [ ] Close `STATE_PHASE0.md`. Open `STATE_PHASE1.md` (§6.4 schema), `next_action = Step 1.1.1`,
      carrying forward in its first entry: (a) the PAVA-class low-Δ watch-list → §1.3.3
      single-amendment trigger (ask-human, Appendix B-12); (b) **the chosen memory-bound
      measurement protocol from G2** (binding on Step 1.2 drivers); (c) the I-1 discrimination-band
      scope note (I-1 validated a large speedup, not 1.2–1.6× band precision — that is
      established at Step 1.2).

---

## HANDOFF — Phase 1 per `PHASE1_ACTION_PROMPT.md` §1.1 → §1.P

Proceed unchanged, with these bindings from this close-out:
1. **Step 1.2** drivers for memory-bound units run under the G2 contention-free protocol; per-unit
   IQR is genuinely re-established to ≤ 1% there — the I-1 8.69× number does not stand in for it.
2. **Step 1.3** treats PAVA-class sequential/division-bound units as expected downward pressure on
   corpus-median Δ (§4.1c: median ≥ 1.5, ≥ 70% units ≥ 1.2); if they pull the median under 1.5,
   that is the §1.3.3 single-amendment trigger — **ask the human before spending it**.

---

Begin at **G0.1**. Report the git diagnosis verbatim before touching any file.
