# PHASE P — FINAL REPORT

**All three research questions are answered. Every answer is negative for the product** — though
RQ-P3's is negative only after its pre-registered gate fired *positive* and the probe showed why
that reading does not carry (§4).

Date: 2026-07-31. Hardware: i3-10100F, 16 GB, GPU unused; all builds and runs inside the pinned
image `motifbo-env:phase1` (d45e33b0…).

Every number has a raw pointer and a recompute command. Where a number changed during this phase,
both values are given.

**Not sign-off-ready, for one specific reason:** the stats-auditor's independent zero-diff
recompute has never run (§8). Everything else is closed.

---

## 0. The short version

A 149-kernel × 1,728-config benchmark was built and measured (225.95 h of rig time). Two defects
found during the close changed results: a decision memo was being cited as the pre-registration
(0-of-3 confirmatory floors, not the claimed 2-of-3), and the roadmap's **ASan/UBSan feasibility
gate was never invoked at all** — the campaign ran on the oracle alone, which let 1,296 configs
that read out of bounds be recorded as feasible and gave three kernels a 13× "speedup" that was
really 1.32×. The same missing gate was then found in the shipping product and installed there.

Then the study ran and answered its questions:

- **RQ-P1 — which algorithm wins?** DOE, a deterministic D-optimal screen. **BO loses to it in 18
  of 20 cells and is worse than random search on flat landscapes.** The expensive Bayesian arm does
  not earn its cost.
- **RQ-P3 — does Motif transfer help?** Three separate statements, and collapsing them would
  misreport the result: **the pre-registered gate fired POSITIVE** (p = 3.5e-17, δ = 0.77); **the
  sibling probe then showed the effect is a corpus artifact** — Motif's warm-start sources are 9.7×
  enriched for siblings of the target's own template; **so the product answer is no**, reinforced
  by the fact that the corpus it needs does not exist where the product runs.
- **RQ-P2 — does routing beat one fixed algorithm?** **No, at any budget.** On held-out kernels the
  router equals always-DOE at four budgets and is *worse* at the fifth.

The product ships what survived: never emit a wrong config, never emit one that reads out of
bounds, and say "no improvement" rather than invent one.

---

## 1. What was measured

| set | kernels | role |
|---|---|---|
| Training | 129 | synthetic, generator v2, anti-clone separated |
| Holdout H | 11 | sealed for acceptance; never in the study set |
| Dataset R | 9 | real code — the v1 survivors, at Phase-P scale |
| **Total** | **149** | each with a full 1,728-config table |

**Rig time: 225.95 h true / 157.91 h accepted-cycle**, both independently verified. The larger is
the honest envelope; quoting 157.91 h alone understates the cost by 30%.

**Rig integrity:** one single fingerprint across all 82,944 sampled rows; zero throttle events
campaign-wide across 791 thermal samples.

---

## 2. The confirmatory floors — 1 of 4

Evaluated on the **§4-conformant n** (PREREG §4 excludes `agreement_fail` kernels from per-class
inference, unconditionally; DEV-1b adds the endpoint-voided kernels).

| cell | n as-measured | excluded | **n conformant** | exact power @δ=0.4 | vs floor 26 |
|---|---|---|---|---|---|
| FLAT+FM | 20 | 0 | **20** | 0.708 | BELOW by 6 |
| MID | 29 | 5 | **24** | 0.776 | BELOW by 2 |
| LEVER-SEP | 26 | 6 | **20** | 0.708 | BELOW by 6 |
| INT | 38 | 9 | **29** | 0.853 | **OK** |

Power is exact at the achieved n from the committed generator, never interpolated
(`results/fleet/exact_power.json`).

**Why these as-measured counts differ from the pre-close P-2 draft:** D23's three corrected
reduction kernels moved **INT → MID**, because their Δ_all fell from 13.1 / 13.0 / 13.9 to
**1.32**, which lands inside MID's [1.10, 1.5) band rather than INT's Δ ≥ 1.5. That is the whole
of the shift — INT 41 → 38, MID 26 → 29.

**The FEAS contrast is powered.** Inference set: the 129 training kernels minus the 20 excluded
by §4/DEV-1b = **109**, split **FEAS+ 51 / FEAS− 58**. FEAS+ is the arm whose kernels have a
substantial infeasible region — `4·n_infeasible ≥ n_total`, i.e. ≥25% of configs infeasible,
compared in integer arithmetic per A-2h/E4. The quoted **0.974 / 0.986** are the exact power of the
same paired one-sided Wilcoxon model at those two arm sizes (n = 51 and n = 58 respectively), at
δ = 0.4 — the pooled contrast's n is the arm size, not a per-cell count.

FLAT+FM **cannot** be filled at any price — its binding constraint is the property space, not the
parameter space (11 clone rejects, 8% acceptance, 67% of the H budget for one accept).

---

## 3. RQ-P1 — which algorithm wins

Per (cell × budget), 20 families, Friedman + Holm-corrected pairwise Wilcoxon on conformant sets.
**Median regret, product-runnable arms:**

| cell \ arm | RS | DOE | BO | best |
|---|---|---|---|---|
| FLAT+FM @8 | 1.446 | **0.863** | 1.704 | DOE |
| MID @8 | 0.151 | **0.071** | 0.123 | DOE |
| LEVER-SEP @8 | 0.276 | **0.039** | 0.201 | DOE |
| INT @8 | 0.359 | **0.017** | 0.026 | DOE |

**DOE is the best product-runnable arm in 18 of 20 cells.** Effect sizes at B=8 (paired Cliff's δ,
Holm-corrected):

| comparison | MID | LEVER-SEP | INT | FLAT+FM |
|---|---|---|---|---|
| DOE vs RS | δ 0.833, p 3.9e-05 | 0.600, p 6.7e-04 | 0.862, p 9.8e-05 | 0.200, p 0.012 |
| DOE vs BO | δ 0.667, p 5.6e-03 | 0.500, p 9.7e-03 | 0.034, p 0.33 (ns) | 0.400, p 9.7e-03 |

**BO is worse than random search on flat landscapes** (FLAT+FM @8: RS 1.446 vs BO 1.704; δ = 0.800
for RS over BO, p = 5.3e-05). It spends its budget modelling noise. This is the clearest negative
in the study: a Bayesian surrogate over 1,728 configs, at the budgets a user would actually accept,
is beaten by a fixed D-optimal design that needs no model at all.

---

## 4. RQ-P3 — Motif transfer, and why a passed gate did not ship

Motif+BO won 13 of 20 cells and **passes PREREG §3.4 outright**: Holm p = 3.46e-17 at both
B ∈ {8,16}, paired Cliff's δ = 0.772, against a gate of p < 0.05 and δ ≥ 0.2.

**It is not installed.** A favourable surprise is an alarm here, so it was probed before being
believed:

> Motif's warm-start sources are **9.7× enriched** for kernels of the target's own generated
> template — 3.74 of 8 selected sources share it, against a 0.39 random-pick baseline on the same
> corpus. 19 of 129 kernels draw **all 8** from their own template.

Two independent reasons, either sufficient:

1. **Structural.** Motif+BO warm-starts from a corpus of previously-tuned sibling kernels under
   leave-one-kernel-out. `cytune tune mykernel.pyx` has no corpus. The setting that produced the
   win does not exist where the product runs.
2. **Construct validity.** The advantage is substantially warm-starting from a near-copy of the
   target's own landscape — an artifact of a synthetic corpus with ~4 kernels per template.
   Dataset R's nine real anchors have no siblings at all.

Recorded as a deviation (DEV-13), because the pre-registration committed to a decision rule and the
rule fired. **Passing a gate is not sufficient for shipping when the gate's setting cannot be
reproduced where the product runs.** Raw: `results/study/MOTIF_SIBLING_PROBE.json`.

---

## 5. RQ-P2 — does routing beat one fixed algorithm? No.

18 held-out kernels (11 H + 7 R; `ppoly`/`floyd` excluded per DEV-3), replay mode:

| B | routed | best-fixed (DOE) | oracle-routed | routing wins? |
|---|---|---|---|---|
| 8 | 0.14632 | 0.14632 | 0.07240 | no (tie) |
| 16 | 0.17410 | **0.13544** | 0.09064 | **no — routing is worse** |
| 32 | 0.04464 | 0.04464 | 0.03227 | no (tie) |
| 64 | 0.00852 | 0.00852 | 0.00537 | no (tie) |
| 128 | 0.00200 | 0.00200 | 0.00095 | no (tie) |

The matrix installs DOE in 18 of 20 cells, so "routing" is nearly "always DOE" by construction —
and the two cells where it differs (FLAT+FM|16 → RS, INT|16 → BO) are exactly where it loses.

**The oracle gap is the honest headroom:** 0.074 at B=8 down to 0.001 at B=128. That is what a
genuinely predictive router would capture and this one does not.

**Provenance slice (A-7e), behaving as pre-registered:**

| slice | n | regret @8 |
|---|---|---|
| real code (R) | 7 | **0.0349** — real code is easiest to tune well |
| H-orig | 7 | 0.1653 |
| H-ext | 4 | **0.3081** — the extrapolated kernels are hardest, as A-7e predicted |

**Product consequence:** per-cell engine switching is not shipped. cytune routes to DOE
unconditionally. What the study changed is the *status* of that choice — a conservative default is
now an evidence-backed one. The router's surviving rules are the ones that earned their place:
abort when there is no feasible reference, and honest-flat, which declines to tune a flat landscape
rather than reporting the minimum of a small sample as a win.

---

## 6. The two defects that changed results

**D22 — a decision memo cited as the pre-registration.** `report_p2.py` applied a ">10% agreement
failures" rule attributed to "B_02"; `grep -c "B_02" PREREG_PHASEP.md` returns 0. The real §4 rule
is unconditional. The report said 2 of 3 floors MET; under the pre-registered rule it was 0 of 3.
Found by the stats-auditor.

**D23 — the §1.4 sanitizer gate was never invoked.** All ~149 kernels × 1,728 configs were gated on
the oracle alone. Of 34,128 cells executing a planted out-of-bounds read, **1,296 were recorded
FEASIBLE** — all in three min/max reductions, at 432/432 each, because a reduction absorbs one
garbage element without changing its output. Δ_all 13.1/13.0/13.9 → **1.32** in all three.

*Why it survived a whole campaign:* no artifact records **which gates** produced a verdict, so
"oracle only" and "oracle + sanitizer" are indistinguishable after the fact. A missing check leaves
no trace unless something counts the checks.

*Product half, found by the validation-auditor:* the same gate was missing from `cytune`, which
measures live and gated on the oracle alone. On a user's kernel with a latent out-of-bounds read
inside a reduction it would have reproduced D23 exactly. Fixed —
`src/cytune/sanitize_gate.py` gates the actual emitted config (PREREG §301).

**VERIFICATION STATUS of that gate, stated because D23 is precisely the defect of a gate nobody
demonstrated.** Three levels, and only the first two are done:

| level | status |
|---|---|
| decision logic — which verdicts forbid an emit, and that a gate which *could not run* is neither a pass nor a rejection | **unit-tested**, `src/cytune/test_cytune_sanitize_gate.py` (4 tests) |
| detection machinery — does ASan actually catch a planted out-of-bounds read | **control-verified 9/9**, `sanitizer_spot_audit.py --controls` (`ctrl_oob` over-read, `ctrl_oob_under` under-read, `ctrl_clean`); the product gate calls the same `_sanitizer_build` + `san_child.py` |
| **product end-to-end — plant an OOB in a user kernel, run `cytune tune`, confirm the recommendation is withdrawn** | **NOT DONE this phase** |

So the gate's *components* are demonstrated and its *wiring* is not. No live end-to-end run was
performed (§10), which is the same gap. This is recorded rather than smoothed over: a gate whose
failure path has never been exercised end-to-end is the exact shape of D23, and repeating that
pattern in the product while claiming it fixed would be worse than the original lapse.

---

## 7. The complete D-series

D1–D19 predate this close (D1/D2 are Phase-1's zero-embedding and bare-import defects); the
series has no gaps. This phase's own:

- **D20** — build-phase deaths charged 0.0 s to a hard cap; wave-2 rig time is an interval
  [175,406.8 , 182,672.8] s, never a point.
- **D21** — the R transfer check compared two metrics sharing a name, manufacturing a 2.41× flag on
  `elkan`; it actually transfers at 1.009×, the closest of all nine.
- **D22** — proxy-as-prereg (above).
- **D23** — the sanitizer gate that never ran (above).

---

## 8. Auditors

| auditor | verdict |
|---|---|
| measurement-auditor | **PASS_WITH_NOTES** — rig clean; 48 kernels (32.2%), zero issues; agreement bits zero-diff on all 149; both rig-time figures verified |
| validation-auditor | **FAIL** on evidence integrity → both findings closed. All 15,552 R labels zero-diff; the D23 derivation confirmed empirically and could not be broken |
| scrutinize | **FIX-THEN-SHIP** → both findings fixed |
| **stats-auditor** | **FAIL** (D22) → fixed. **The re-run has NEVER COMPLETED — killed twice by API limits (monthly, then session).** |

**This is the one open blocker.** No independent zero-diff recompute exists against the
D23/DEV-1b/A-10-corrected artifacts. Every number in this report is self-computed and
raw-pointered, but not independently verified.

---

## 9. Deviations — 13, in `results/fleet/DEVIATIONS_REGISTER.md`

The ones that bear on interpretation: **DEV-1/1b** (sanitizer lapse; endpoint-voided ruling),
**DEV-3** (`ppoly`/`floyd` inert axes, excluded from directive inference), **DEV-4** (`binning`
188.67 ms, outside the binding [50,100] ms band), **DEV-9** (measurement-core temperature never
recorded; throttle-discard rule unwired — benign only because counters never moved),
**DEV-11** (one run_id with p=0.012 agreement excess, *unexplained-but-benign, not discharged*),
**DEV-12** (seed truncation), **DEV-13** (Motif's passed-but-unshipped gate).

---

## 10. Limitations

- **Seed truncation (A-10).** 20 of 200 seeds; SE inflation 3.16×, and the *measured* cost is a
  21.6% mean relative shift in RS's per-kernel means (max 290%, n=645 pairs). **Significant results
  are not weakened** — noise raises the bar. **Null results are UNDERPOWERED-NULL**, never "no
  difference".
- **Three of four cells are underpowered** at δ=0.4 (0.708 / 0.776 / 0.708) and are marked so
  everywhere.
- **Synthetic scope.** 129 of 149 kernels are generator output, and the corpus's ~4-kernels-per-
  template structure is what invalidated Motif's win. **INT does not occur in real code: 0 of 9**,
  against 41 synthetic — so an advantage concentrated in INT may not be reachable on real code.
- **The sanitizer evidence is a spot audit, not the gate** — 3 configs per kernel out of 1,728.
- **117 of 206 kernel directories have a 1-element output oracle**, the maximally-absorbing shape
  that hid D23. The 206 is *not* the frozen 149: it is every directory under `results/fleet/`
  carrying a committed `oracle.json`, i.e. the 149 accepted kernels plus clone-rejected and
  exhausted candidates that got as far as golden capture. **Of those 117, for 57** the kernel is
  unarmed *and* its oracle rejected none of its 1,728 configs — so for those 57 there is no
  in-situ demonstration that the oracle can fail at all. Expected for unarmed kernels, but it is
  the residual risk D23's own lesson names, and the spot audit cannot close it.
- **The oracle verdict is not re-derivable from committed raw** — no per-config `output_sha256`.
- **Live end-to-end product runs: 4**, in a cold-user acceptance test at the close of the phase —
  `t1_flat` (flat pointer-chase, quiesced, 17 configs measured), `t2_lever` (bounds-check lever,
  **portable**, 33 configs), `t3_oob` (a planted D23-shaped out-of-bounds read inside a max
  reduction, quiesced, 41 configs) and a quickstart verification (quiesced, 33 configs), plus
  2 `doctor` invocations (one on a deliberately broken environment) and 8 misuse invocations. All four emitted a certificate; **the §1.4 sanitizer
  gate rejected the winner on `t3_oob` — a config the output oracle had passed — and fell back to
  the reference.** These are product evidence on newly written fixtures, not study measurements:
  no study number, statistic or audit verdict is affected. Report, verbatim transcripts, raw
  tables and 21 numbered findings (none CRITICAL): `results/usertest/USER_TEST_REPORT.md`.
- **Single machine, single rig fingerprint.**

---

## 11. Recompute

```
python3 scripts/phasep/report_p2.py                     # P-2 report
podman run … python3 scripts/phasep/exact_power.py      # exact power at achieved n
podman run … python3 scripts/phasep/analyze_study.py    # RQ-P1 / RQ-P3
podman run … python3 scripts/phasep/rqp2_acceptance.py  # RQ-P2
podman run … python3 scripts/phasep/motif_sibling_probe.py
podman run … python3 scripts/phasep/san_overlay.py      # the §1.4 overlay
podman run … python3 scripts/phasep/freeze_manifest_v2.py
```

Raw: `results/fleet/<kernel>/{table.jsonl,class_v2.json,endpoint.json,oracle.json}`,
`results/study/{regret*.jsonl,P3_ANALYSIS.json,ROUTING_MATRIX.json,RQP2_ACCEPTANCE.json}`,
`results/sanitize/phasep_spot_audit/`, ledger `results/fleet/fleet_ledger.jsonl`.
