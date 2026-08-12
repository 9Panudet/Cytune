# Measurement — the rig, the tiers, and what makes a number decision-grade

## Two rig modes, and the difference is not cosmetic

`rig.probe_rig()` shells out to `scripts/measure_wrap.sh --verify-only`. Exit 0 → **quiesced**;
anything else → **portable**, with the refusal text carried through to the certificate.

`measure_wrap.sh` refuses (exit 78) unless **all** of:

| assert | why |
|---|---|
| `no_turbo == 1` | turbo makes clock rate a function of thermal history, not of the code |
| `governor(cpu3) == performance` | otherwise frequency tracks load, and load is what you are measuring |
| cpu7 offline, **or** isolcpus covers 3 and 7 | cpu7 is cpu3's SMT sibling; a busy sibling halves your core |
| `thp` is `madvise` or `never` | `always` breaks CF-4 page-backing determinism |

It records `RIG_FINGERPRINT` — the whole state string — into the container environment, and **I4.4**
refuses to call a timing decision-grade unless the certificate carries the fingerprint that
`measure_wrap` actually verified.

`--rig quiesced` makes the absence of a verified rig a hard failure. `--rig portable` accepts
indicative numbers knowingly. `auto` (the default) uses whichever is available and says which.

## CF-1: compile and measure never overlap

Within one process this is structural: one container invocation per phase (`worker.py`), and builds
pinned off the isolated cores by `rig._build_cpus()` — *"CF-1 separates the phases in TIME while
this separates them in SPACE"*.

**Across processes it was nothing at all** until the launch pass. `cli.tune` alternates build and
measure four times, so a second `cytune tune` in another terminal drops its parallel build into
your timed phase. The failure mode is not a crash: it is a contended machine measuring slower, and
because config id order correlates with the `-O1`/`-O3` factor, **a time-correlated slowdown can
alias onto a factor**. 626 measured rows were discarded to exactly that on 2026-07-24.

`lock.py` now takes a machine-wide `flock` for the whole run. Details in `00_SUMMARY.md`; the two
design points worth repeating here are that the holder is identified by `pid` + `/proc` start time
(never by matching a command line — that is D19), and that `Session._run` asserts the lock is held
before `golden`, `measure` or `endpoint`, so no future code path can time outside its scope.

## Calibration

`_vendor/campaign.py::calibrate` rewrites your driver's `REPS` (or `SCALE`) knob so the reference
lands near `--target-ms`, default 65 ms. It extrapolates **linearly from one measurement**, so a
kernel whose cost is not linear in the knob — or a machine that was busy for that one measurement —
lands somewhere else. cytune **reports** the achieved value rather than iterating: re-calibrating in
a loop would spend measurement budget on the calibration instead of the search, and a 30 ms target
that produced a 49 ms reference is information the user needs, not a number to quietly fix.

## Two tiers

| tier | used for | shape |
|---|---|---|
| **screen** | every configuration during search | cheap; the search's ranking signal |
| **endpoint** | the winner and the reference only | K=30, median-of-3, inputs regenerated per repetition |

The tiers are never mixed in a ratio. Anything the certificate claims comes from the endpoint tier;
the screen tier ranks, it does not certify.

## The emit margin, and why it is not a constant

`margin = max(2 × combined endpoint CV, τ)` with `τ = 0.02`.

It used to be a flat 1.02. **D15**: taking the minimum over B noisy configurations produces a
phantom speedup floor of about 1.064× at B=32 with s=0.03 — *above* the threshold meant to filter
it. A fixed threshold below the noise it is filtering does not filter anything. The margin is now
computed from the run's own measured spread, and the certificate shows the arithmetic.

A rank-based separation guard runs alongside it as a second, cheap check. It is reported as a
diagnostic and is **not** an independent verdict driver — in practice it keys off the same spread,
and saying otherwise would overstate what two guards give you.

## C1 — wall-clock corroboration

`certify.corroborate_ratio` asks whether the parent process's wall clock can account for the claimed
gain. `overhead := wall − K × median`; the two configurations share spawn, imports, K and inputs and
differ only in warmup, so `predicted = warmup × (t_win − t_ref)`. The budget is
`max(0.5 × claimed_gain, 3σ)`.

Three outcomes, and the third is the one that matters:

* `True` — accounted for.
* `False` — **the claim is withheld** and the reference is emitted.
* `None` — **no power to decide** (no wall clock recorded, no medians, or the residual budget
  exceeds what the test could ever detect: `budget >= (1 + warmup/K) × claimed_gain`). `None` is a
  pass-through, not a pass, and it is registered as its own path (V-4-N) precisely because a test
  suite can "cover C1" while only ever reaching one of its three shapes. That is how D-3 hid.

## The cache key

A run is reused only if every input to it is unchanged. I3.1 keys on the module and the toolchain
image; I3.2 adds the driver, the workload, the rig mode and the oracle. Discarded measurements are
**archived, not deleted** (I3.3) — an invalidation that destroys leaves no way to ask afterwards
what the old numbers said.
