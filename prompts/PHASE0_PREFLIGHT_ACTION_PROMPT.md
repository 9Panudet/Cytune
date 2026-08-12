# ACTION PLAN PROMPT — Step 0.P (Phase 0 preflight + exit) → open Phase 1

> Paste into Claude Code CLI. Resuming at Step 0.P. I-1 is cleared
> (csr_scale 1.964× raw-pointer + horner 8.691× numeric, threshold 1.5× unchanged).
> Roadmap is law; `CLAUDE.md` is how-to. On conflict, roadmap wins.

---

## CARRIED-FORWARD CATCH — resolve P0 BEFORE declaring any preflight item green

The 0.5.3 resolution closed the I-1 *gate* but left a **timing-variance thread open**, and the
Phase-0 *exit* criterion explicitly requires *"per-kernel IQR within the pilot-set bound"* — not
just gate robustness. Do not let it pass silently.

- [ ] **P0a — Pin down what the pilot (Step 0.2.4) actually ran on.** State, from committed
      artifacts: which two kernels the pilot used, their median runtimes, and whether K_final +
      the thermal threshold were derived from those. If the numeric reference was swapped
      PAVA→Horner *after* the pilot, then K_final was set on variance from a kernel that is no
      longer the I-1 numeric reference — say so plainly.
- [ ] **P0b — Check K_final validity against the corpus runtime band.** §4.2 admits corpus units
      at golden runtime **50–500 ms**; Horner runs at ~5.3 ms and csr at its own scale. Confirm
      the pilot kernels sit in (or are conservative for) the 50–500 ms band, so the K_final that
      achieves ≤ 1 % CI half-width on them generalizes to the corpus. If the pilot kernels are
      sub-band (atypically fast), K_final may be set on an unrepresentative basis — flag it as a
      Phase-1 risk and decide whether a corpus-representative pilot kernel is needed before 1.5.
- [ ] **P0c — Classify Horner's ~13 % IQR honestly.** Horner-good's IQR (~13 % at 5.3 ms ⇒
      bootstrap median CI half-width ≈ 3 %, above the ≤ 1 % target) is an artifact of the kernel
      being unrepresentatively fast, not rig instability. Decide and record one of:
      (i) Horner is a **calibration-only kernel, exempt** from the corpus-precision bound (it is
      not a corpus unit, its only job was the I-1 ratio, which is robust at 8.69× ≫ 1.5×) — the
      per-kernel-IQR-within-bound exit criterion is evaluated on the **corpus-representative pilot
      kernels**, not Horner; **or**
      (ii) if the exit criterion is read to bind Horner, raise its K until CI half-width ≤ 1 %.
      Prefer (i) with explicit written justification in STATE; do not hand-wave it as "governs
      K_final not the gate" — name the exemption and its scope.
- [ ] **P0d — Record the I-1 scope limitation (one line, STATE + Phase 0 report).** I-1 validated
      the rig against a *large* known speedup (8.69×); it did **not** validate rig precision in
      the **1.2–1.6× discrimination band** where the corpus actually lives (PAVA 1.23×, §4.1c
      floor 1.2× / median 1.5×). That confidence comes from the pilot variance characterization
      and the per-unit IQR re-characterization in Phase 1 — not from I-1. State this so Step 1.3
      / 1.5 inherit it as a known scope, not a gap discovered late.
- [ ] **P0e — Roadmap-edit ack.** The §0.5.1b PAVA→Horner edit changed the document declared as
      "law." It is correctly classed (instrument-definition fix; no amendment consumed; not
      D-series) and `scrutinize`-signed, but surface it to the human for an explicit ack before
      Phase 0 closes — self-sign on a law-level edit is the one governance gap. List it under
      `blocking` in STATE until acked.

---

## STEP 0.P — Preflight (§6.6) — advance only at 100 %

- [ ] **1. Digest / hash validation:** container image digest matches `/data/env/IMAGE_DIGEST`;
      `TOOLCHAIN.lock`, `requirements.lock`, golden-data hashes, input manifests all verify.
      CI asserts. (Fedora: confirm rootless podman reproduces the digest; SELinux `:Z` mounts
      intact.)
- [ ] **2. Memory profiling vs 16 GB:** peak RSS (orchestrator + worst candidate) **+ the 2 GB
      tmpfs `/sandbox`** < the 12 GB container ceiling. Commit the profile.
- [ ] **3. Sanitizer-clean confirmation** on the known-good build (zero ASan/UBSan reports;
      CPython suppressions justified line-by-line, `validation-auditor`-reviewed).
- [ ] **4. Raw-data presence:** every claimed number (I-1 ratios, pilot stats, oracle results)
      resolves to a committed raw file with an exact recomputation command.
- [ ] **5. `scrutinize` complete** + all four auditors:
      - `validation-auditor` → oracle + sanitizer rig; recomputes feasibility labels from raw.
      - `measurement-auditor` → governor/turbo logs, taskset/cpuset masks, thermal logs, warmup
        discipline, pairing hashes, the P0a–P0c timing-variance resolution.
      - `stats-auditor` → recompute I-1 ratios + pilot stats from raw; **zero-diff required.**
      - `bo-math-reviewer` → **n/a in Phase 0** (no surrogate/acquisition code exists yet);
        record `n/a` with that written justification per §6.6 item 5. Do not fake a pass.

Any failed item ⇒ phase does not advance; `debug-mantra` applies.

---

## PHASE 0 EXIT — verify all, then hand off

- [ ] I-1 pass with stated margins (recorded).
- [ ] I-3 reliable: oracle test suite green **and the manual validation gate signed in STATE**
      (§ Phase-0 exit). Confirm the signature exists — it is a named exit artifact, not implied
      by green tests.
- [ ] ASan/UBSan clean on the known-good build.
- [ ] Timing variance characterized: pilot report committed; K_final + thermal threshold set;
      per-kernel IQR within the pilot-set bound **(per the P0c scoping)**.
- [ ] Preflight 100 %; P0e roadmap-edit ack received (clears `blocking`).
- [ ] Close `STATE_PHASE0.md`. Open `STATE_PHASE1.md` (§6.4 schema) with
      `next_action = Step 1.1.1`, and carry forward in its first entry: the PAVA-class low-Δ
      watch-list (PAVA, `_cd_fast`, Bellman–Ford) and the I-1 discrimination-band scope note
      (P0d).

---

## HANDOFF — Phase 1 per `PHASE1_ACTION_PROMPT.md` §1.1 → §1.P

Proceed with the existing Phase 1 checklist unchanged. Two carry-forwards bind into it:

1. **Step 1.2 driver IQR:** corpus units run 50–500 ms; re-characterize per-unit IQR there —
   this is where rig precision in the operating band is actually established (the I-1 8.69×
   number does not stand in for it, per P0d).
2. **Step 1.3 characterization:** PAVA-class sequential/division-bound units are an *expected*
   downward pressure on corpus-median Δ (§4.1c: median ≥ 1.5, ≥ 70 % units ≥ 1.2). If they pull
   the median under 1.5, that is the §1.3.3 single-amendment trigger — **ask the human before
   spending it** (Appendix B-12).

---

Begin at **P0a**. Report the pilot kernels + their runtimes first; do not green any preflight
item until P0a–P0e are resolved and recorded.
