# cytune — v1.0.0-rc0, **research preview**

Tunes Cython directives and GCC flags for one module, measures the result on a controlled rig, and
emits a certificate saying exactly what it did and what it refused to do.

**Read this before using it.** The label "research preview" is load-bearing, not modesty:

- **The algorithm study did not complete.** The routing policy shipped here is the **interim** one,
  not a measured routing matrix. See `results/PHASEP_REPORT.md` §5–§6.
- **On most real code the honest answer is "no improvement."** The tool is built to say that rather
  than manufacture a win, and on the nine real-code anchors in our benchmark that is usually what
  it says.
- **One of four kernel categories reached the pre-registered statistical power floor.** The other
  three are reported with their exact achieved power and are never described as passed.

What *is* solid is what the tool **refuses** to do. Those refusals are measured and tested.

---

## Install prerequisites — honestly

cytune does not measure on your machine directly. Every build and every timed run happens inside a
**pinned container image**, because an unpinned toolchain makes results incomparable between runs.

You need:

| requirement | why |
|---|---|
| `podman` (rootless is fine) | runs the pinned image |
| the pinned image `localhost/motifbo-env:phase1` | the toolchain; without it nothing runs |
| Python ≥ 3.9 on the host | the CLI itself is host-side orchestration only |
| **optional:** a quiesced rig (`scripts/host_prep.sh`, needs sudo) | without it, measurements are best-effort and small speedups are indistinguishable from noise |

Check all of it in one command:

```
cytune doctor
```

It prints a line per check and, for anything failing, what to do about it. Failures are split into
**BLOCKING** (cytune cannot run) and **DEGRADED** (it runs, but a specific guarantee is weaker and
the certificate will say so). Nothing degrades silently.

---

## Quickstart

You need two files: the `.pyx` module you want tuned, and a small **driver** that tells cytune how
to call it and what "correct" means.

```python
# driver.py
import numpy as np

N = 100_000
REPS = 50                      # cytune calibrates this so the reference run lands near 65 ms
OUTPUT_CLASS = "float"         # "float" -> compared with a tolerance; "int"/"bool" -> bit-exact

def make_inputs(seed):
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(N), REPS)

def call(mod, inputs):
    return mod.run(*inputs)

def canon(result):
    return np.asarray(result, dtype=np.float64).reshape(-1)
```

Then:

```
cytune tune path/to/kernel.pyx --driver path/to/driver.py
```

It runs six stages — ingest → probe → route → tune → verify → certify — and writes a certificate.

Useful flags:

```
--workspace DIR        where raw measurements land (default .cytune)
--rig portable         skip the quiesced-rig requirement; measurements become best-effort
--target-ms 65         calibrate the driver's REPS/SCALE knob so the reference lands here
--allow-fast-math      let fast-math configs be SELECTED (they are still oracle-checked)
```

**`--allow-fast-math` is off by default and should usually stay off.** Fast-math permits the
compiler to reorder floating-point arithmetic, so results can differ from what your code specifies.
cytune holds those configs to the same correctness check as everything else, but "passes our oracle
on our inputs" is not "safe for your numerics."

---

## What the certificate guarantees

- **It will not recommend a config that produces wrong output.** Every candidate is re-measured at
  the endpoint tier and re-checked against a golden result; a config that passes the fast screen
  and fails here is never emitted.
- **It will not recommend a config that reads memory it does not own.** Before certification the
  emitted config is rebuilt under ASan+UBSan and run. If it reports, the recommendation is
  withdrawn and cytune falls back to the reference. (This exists because our own study found 1,296
  configs that read out of bounds while passing an output check — see `logs/defects/D23.md`.)
- **It will say "no improvement found" rather than invent one.** On a flat landscape it declines to
  tune and reports the fastest probe config as an *observation, explicitly not a recommendation* —
  because the minimum of a small sample is biased low when nothing really differs.
- **`-ffp-contract` is always explicit** in the emitted flags. GCC's default is `fast`, which can
  silently fuse operations and change results.

## What it does not guarantee

- **A clean sanitizer check is not proof of memory safety.** It means no error was detected on the
  inputs tested.
- **The recommendation is not optimal** — it is the best found within the budget.
- **There may be no speedup at all.** That is a legitimate result and the tool reports it as one.
- **Without the pinned image the sanitizer gate cannot run.** The certificate then records it as
  **not-run**, which is not the same as passed. That distinction is the main lesson of this phase.

---

## Where the evidence lives

| what | where |
|---|---|
| Full phase report | `results/PHASEP_REPORT.md` |
| One-page plain-language summary | `results/DEFENSE_SUMMARY.md` |
| Every deviation from the plan | `results/fleet/DEVIATIONS_REGISTER.md` |
| Defect records | `logs/defects/D*.md` |
| Auditor verdicts, verbatim | `results/fleet/AUDIT_VERDICTS.json` |
| Raw measurements | `results/fleet/<kernel>/table.jsonl` |

Every number in those documents carries a raw pointer and a recompute command.
