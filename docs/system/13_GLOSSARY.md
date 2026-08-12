# Glossary

**anchor / Dataset-R anchor** — one of the nine kernels taken from real library code for which all
1,728 configurations were measured exhaustively. Used as ground truth. *Nine anchors are
validation, not coverage* — see `11_EVIDENCE.md`.

**artifact** — the compiled `.so` for one configuration. Identified by sha256; I4 binds the
certificate to it.

**canon()** — your driver's function turning a result into a comparable numpy array. It defines
what "the same answer" means, and it is inside the trust boundary.

**cell** — a measured class of kernel landscape: FLAT, FLAT+FM, INT, LEVER-SEP, MID. Assigned by
measurement, never by construction.

**CF-1** — the rule that compile and measure phases never overlap. Enforced structurally within one
process and, since the launch pass, across processes by the measurement lock.

**config_id** — an integer in [0, 1728) identifying one point of Θ. `theta.py` is its sole source.

**corroboration (C1)** — a cross-check that the parent process's wall clock can account for the
claimed speedup. Returns `True`, `False`, or `None` (no power to decide). `None` is not a pass.

**degeneracy** — when the directives cytune varies do not change the generated C. Total degeneracy
is a refusal (I4.2); partial degeneracy is reported ("initializedcheck did not change the generated
C for this kernel").

**delta_probe / Δ** — the spread across the probe design, the router's main input.

**emit margin** — `max(2 × combined endpoint CV, 2%)`. Below it, no gain is claimed at all.

**emission policy** — which configurations this run may emit. Default is FP-strict: 576 of 1,728.
`--allow-fp-contract` → 1,152; `--allow-fast-math` → 1,728; `--portable-flags` → 288.

**endpoint tier** — the heavy re-measurement of the winner and the reference: K=30, median-of-3,
inputs regenerated per repetition.

**feasible** — a configuration whose output matched the golden. Correctness is absolute: an
infeasible configuration is never emitted regardless of speed.

**golden** — the reference output captured once, from your driver, that every build is compared
against. If it is constant, the oracle cannot fail — see `oracle power`.

**honest-flat** — the verdict meaning "nothing is reliably faster than what you have". Exit 2. An
answer, not a failure.

**oracle** — the correctness check: output class, tolerance, determinism gate, and the golden.

**oracle power** — whether the oracle *can* fail on this workload. A multi-element golden with one
distinct value has none, and cytune refuses (D26).

**probe** — the fixed 17-configuration design measured before any routing decision.

**quiesced / portable** — the two rig modes. `quiesced` means `measure_wrap.sh` verified the host
(turbo off, performance governor, isolated core, THP not `always`); `portable` means it did not,
and every number is labelled indicative.

**reference** — config 288: Cython's safe defaults with `-O2 -march=x86-64`. What a user has before
cytune runs, and what is emitted whenever cytune declines to recommend anything else.

**regret** — `t(emitted) / t(best allowed) - 1`. How much slower cytune's pick is than the best pick
it was allowed to make. Only computable where the true optimum is known.

**screen tier** — the cheap measurement tier used during search.

**sealed replay** — offline evaluation where an algorithm may only see the frozen tables through an
ask–tell interface. Makes algorithm comparison fair and reproducible.

**Θ (theta)** — the 1,728-configuration search space: 5 Cython directives × `-O1/-O2/-O3` × `march`
× `funroll` × a 3-level floating-point axis.
