# Phase P — one-page defense summary

Plain language. Every claim sits in exactly one of four buckets, and the boundaries between them
are the point of the page.

---

## What is PROVEN — measured, with enough data to support the conclusion

**The benchmark is measured and rig-verified.** 149 kernels, each timed at all 1,728
compiler/directive combinations — 226 hours of machine time on a quiesced rig. An independent
auditor re-derived the timing discipline on a third of them and found **zero discrepancies**; all
82,944 checked rows carry the same rig fingerprint; nothing thermally throttled, ever.

**A simple method beats the sophisticated one.** A fixed statistical design (DOE) — no model, no
learning — beat Bayesian optimization in **18 of 20** test cells. On flat landscapes BO was worse
than *random search*: it spends its budget modelling noise. This is the study's clearest result and
it is negative for the expensive approach.

**Routing between algorithms does not help.** Tested on 18 kernels held out from everything: at
four of five budgets, picking an algorithm per kernel-type performed *identically* to just always
using DOE; at the fifth it performed **worse**. The product therefore ships one algorithm, not a
router.

---

## What is MEASURED BUT UNDERPOWERED — real numbers, not enough of them

Three of four kernel categories fell short of the pre-registered sample size:

| category | needed | got | chance of detecting a real effect |
|---|---|---|---|
| flat-but-fast-math-sensitive | 26 | 20 | 71% |
| mid-range | 26 | 24 | 78% |
| separable-lever | 26 | 20 | 71% |

The target was 80%. They are reported short, with exact numbers, and never called passed. One
cannot be filled at any cost: its kernels are near-identical by nature, so making more produces
duplicates rather than data.

**The study also ran on 20 of a planned 200 repetitions**, because the full run needs 27 hours of
compute and the deadline did not allow it. That does not change any sample size — repetitions
sharpen each kernel's average, they are not extra data points. The cost was measured directly
rather than assumed: averages move about **22%** on average at 20 repetitions versus 200.
Consequence, stated precisely: **findings that came out significant are not weakened** — extra
noise makes it *harder* to find an effect, so anything that survived cleared a higher bar. Findings
that came out *non*-significant are weaker than planned and are labelled "underpowered null," not
"no difference."

---

## What is INFERRED — reasoned from evidence, not directly demonstrated

**A method passed its test and we still did not ship it.** The transfer-learning approach
(Motif+BO) beat the alternatives decisively and met every pre-registered criterion — the planned
test came out *positive*, and that is stated first because burying it would misreport what
happened. Investigating *why* it won showed it was mostly reusing answers from near-copies of the
same kernel: its
reference examples were **10× more likely** than chance to be siblings of the target — the same
generated template with different numbers. Real code has no such siblings, and the method needs a
library of previously-tuned relatives that a user tuning one file does not have. So it was
recorded as a measured win that does not license a product claim.

**The categories the benchmark is built around may not exist in real code.** The one category with
adequate data ("interacting levers") appeared in **0 of 9** real-world kernels, against 41
synthetic ones. Those 9 were already pre-filtered as the most promising real code available. If a
method's advantage lives in that category, it may be unreachable in practice.

**Two defects found during the close changed the results.** A threshold from an internal memo was
being applied while cited as the formal plan; correcting it turned "2 of 3 categories passed" into
"0 of 3." And a required memory-safety check had **never been switched on** for the entire
campaign — which let 1,296 configurations that read past the end of an array be recorded as
working, because the answer they produced happened to be right. Three kernels' "13× faster" was
really 1.32×; the rest was the cost of the safety check they had removed.

Both share one cause worth stating alone: **a check that never runs leaves no trace.** The records
said "this passed" without recording *which* checks produced that verdict.

---

## What is explicitly NOT CLAIMED

- **No speedup is promised.** On most real code the honest answer is that there isn't one.
- **The code is not certified memory-safe.** The remediation checked 3 configurations per kernel out
  of 1,728, at the settings where problems are most likely. It found real problems. It cannot prove
  their absence.
- **Nothing transfers to other hardware.** One machine, one configuration.
- **This is not independently signed off.** Three of four audits completed; the statistical
  auditor's re-check was killed twice by service limits and has never run against the corrected
  data. Every number is traceable to raw measurements, but not independently recomputed.

---

## What the product guarantees — and what it does not

**Guarantees:**

- **It will not recommend a configuration that produces wrong output.** Every candidate is
  re-measured and re-checked against a known-correct result before it can be suggested.
- **It will not recommend a configuration that reads memory it doesn't own** — *demonstrated
  end-to-end.* New here because the audit found the product had the *same* blind spot the study
  did. The detection machinery is separately control-verified (a planted out-of-bounds read is
  caught 9/9), and the full path was then exercised on a live run: an out-of-bounds read was
  planted in a user kernel inside a max reduction that absorbs the garbage element, **the output
  oracle passed it, the sanitizer gate refused it, and the tool fell back to the safe reference** —
  `results/usertest/runs/t3_oob/` (certificate `sanitizer_gate.verdict = "SANITIZER_REPORT"`,
  `winner_rejection.action = "fell back to the reference config"`); the clean direction is
  confirmed on the same day by `runs/t2_lever/` (`"CLEAN"`). Two gaps remain, and they are the
  reason this bullet is not stated more broadly: on the fallback path the certificate reports the
  *rejected* config's sanitizer status and never asserts one for the config actually emitted, and
  the **image-absent `not-run` path has still never been run end-to-end** — which is the same
  never-exercised-gate shape this phase is a record of.
- **It will say "no improvement found" rather than invent one.** On a flat landscape it declines to
  tune, instead of reporting the best of a small sample as a win.
- **Risky floating-point optimizations are off unless you ask**, and are then held to the same
  correctness check as everything else.

**Does not guarantee:**

- **A clean memory check is not proof of safety** — it means no error was detected on the inputs
  tested.
- **The recommendation is not optimal** — it is the best found within the budget.
- **Without the sandbox image the memory check cannot run.** The certificate then records it as
  **not run**, which is not the same as *passed*. That distinction is the main lesson of this phase.
