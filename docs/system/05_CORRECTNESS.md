# Correctness — the oracle, the sanitizer gate, and exactly what each proves

Two independent checks, answering different questions. Neither subsumes the other, and the project's
largest defect (D23) is precisely a case where one passed and the other would have failed.

## The oracle — "does it still compute what you wrote?"

Built once, in the golden stage. Its parts:

**Output class** — `float`, `int` or `bool`, declared by your driver. `int` and `bool` buy a
bit-exact comparison; `float` gets a tolerance.

**Tolerance** — derived, not asserted, from the output class and the observed spread.

**Determinism gate** — the reference is run 5 times and must produce the same canonical output. A
kernel that is not deterministic under its own driver cannot be tuned, because "different" would be
indistinguishable from "wrong".

**Golden** — the canonical output of the reference, hashed into the certificate
(`oracle.golden_sha256`). Every build's output is compared against it.

**Correctness is absolute.** A configuration whose output does not match is *infeasible* regardless
of speed. The check runs twice — the screen tier during search, and `plan.confirm_winner` again at
the endpoint tier, because a screen pass is not a licence.

### What the oracle does NOT prove

It proves that on **the inputs your driver generated**, the canonical outputs matched. It says
nothing about other inputs, and nothing at all if `canon()` throws away the distinction you care
about. **Your driver is inside the trust boundary** — the certificate says so in those words, and
adds that it is evidence to whoever controls the driver and *not* evidence to a third party.

### Oracle power (D26) — the control the oracle did not have

If the golden is a multi-element array whose every element is identical, the comparison **cannot
fail**. Every build matches. The certificate then prints `rejected as incorrect: 0 (0.0%)`, which is
arithmetic wearing the clothes of evidence.

A first-time user reached this on their first kernel: `clip(x, lo, hi)` with `cytune init`'s
invented `lo = hi = 1.0`. The run certified `IMPROVEMENT 1.0790x` on a kernel that is flat, and
`--apply` wrote a `boundscheck=False` header into their source.

`Session.oracle_power()` now refuses. A single-valued output (a reduction) is **not** degenerate; an
unreadable golden is reported as not-checked and never as fine. See `logs/defects/D26.md`.

## The sanitizer gate — "does it read memory it does not own?"

`sanitize_gate.py` rebuilds the configuration **actually being emitted** with ASan + UBSan and runs
your driver against it. `SAN_TOKENS` (pinned by the vendor manifest since the launch pass) decides
what counts as a report.

Verdicts: `CLEAN`, `SANITIZER_REPORT`, `RUN_FAIL_NO_TOKEN`, `BUILD_FAIL`, `IMAGE_UNAVAILABLE`,
`TIMEOUT`, `HARNESS_ERROR`, and `NOT_RUN`. **Only `SANITIZER_REPORT` demotes.** Everything else that
is not `CLEAN` is a *qualifier*: the verdict is untouched, `sanitizer_gate_ran` goes false, and the
summary's safety wording is downgraded (I1.5, I1.6, I2.4).

**Not-run is never a pass.** This is the single most important sentence in the file, and it is there
because of D23.

Two ordering decisions, both deliberate:

* The gate runs on the search's **best candidate** *before* the emit decision, because the gate is
  a bug finder and not only an emission filter. Gating only the eventual emission once let a real
  out-of-bounds read go unreported because the offending configuration was dropped for being slow.
* It then runs on **whatever is actually emitted** — including the reference. If your own baseline
  reads out of bounds, that is a defect in your code and you should hear it from the tool that just
  rebuilt it under ASan.

### What a CLEAN gate does NOT prove

That nothing was detected, on your driver's inputs, for that configuration. Different inputs reach
different code. `docs/GUARANTEES.md` N1 states this and does not soften it.

## `cytune audit` — determinism instead of luck

`audit.py` runs a **pre-registered risk set** of directive corners under the sanitizer. No search,
no timing, no rig required: the same kernel gives the same verdict every run. This is the answer to
"the tuner happened not to try the configuration that would have found my bug".

Verdicts `CLEAN` / `DEFECTS_FOUND` / `INCOMPLETE`. `INCOMPLETE` exists because a risk-set entry that
could not be gated must not be silently counted as clean — the smoke gate asserts `n_not_run == 0`.

## D23 — why both checks exist

The Phase-P fleet gated ~149 kernels × 1,728 configurations on **the oracle alone**. The sanitizer
gate was never invoked.

**1,296 (kernel, configuration) cells were recorded FEASIBLE while executing an out-of-bounds
read.** All in three min/max-reduction kernels, 432/432 each. A reduction absorbs one garbage
element without changing its output, so the oracle passed them — correctly, by its own definition.
ASan reports `heap-buffer-overflow` on all three.

The three kernels had been classified INT with a 13× lever. **The 13× lever *was* the out-of-bounds
read.** After remediation they reclassify as MID with Δ 1.32.

An output check and a memory check are not two ways of asking the same question.
