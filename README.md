# cytune — v1.0.0, **research preview**

cytune takes one Cython module and searches 1,728 combinations of Cython directives and GCC flags
for a faster one. Every candidate is compiled and timed inside a pinned container image and checked
against a golden output; the configuration it is about to hand you is then rebuilt under
AddressSanitizer + UndefinedBehaviorSanitizer, and if that reports, the recommendation is withdrawn.
It emits a certificate stating what it tried, what it refused and why, what it measured, and what
it will not promise.

**It runs from a checkout, not from PyPI.** You need podman and a pinned image. That is a real
limitation and this page does not hide it.

---

## Install (5 minutes)

```bash
git clone <this repo> && cd Motif+BO

# 1. the toolchain image — BLOCKING prerequisite, takes a few minutes
podman build -f Containerfile -t localhost/motifbo-env:phase1 .

# 2. the CLI
python3 -m venv .venv
. .venv/bin/activate
pip install -e .

# 3. check it
cytune doctor
```

`cytune doctor` prints one line per check and, for anything failing, **what to do about it**.
Failures are split into **BLOCKING** (cytune cannot run) and **DEGRADED** (it runs, but a specific
guarantee is weaker and the certificate will say so). Nothing degrades silently.

<details>
<summary>No venv? No pip?</summary>

`python3 -m cytune ...` works without installing anything, as long as `src/` is importable:

```bash
PYTHONPATH=src python3 -m cytune doctor                              # from the repo root
PYTHONPATH=/path/to/Motif+BO/src python3 -m cytune tune k.pyx --driver d.py   # from anywhere
```

`PYTHONPATH=src` is relative and resolves only from the repository root; your own kernel lives
elsewhere, so use the absolute form there. Both invocation styles behave identically.
</details>

| requirement | why | if missing |
|---|---|---|
| `podman` (rootless is fine) | runs the pinned image | **BLOCKING** |
| `localhost/motifbo-env:phase1` | the toolchain: Cython, GCC 13.x, ASan/UBSan | **BLOCKING** |
| Python ≥ 3.9 on the host | the CLI is host-side orchestration only, no runtime deps | **BLOCKING** |
| a quiesced rig (`sudo scripts/host_prep.sh`) | pins the governor, disables turbo, isolates a core | **DEGRADED** — timings become indicative |

The image is pinned by digest in `Containerfile`. The reference image ID starts `d45e33b08bad`; a
different ID means your toolchain differs from the one every number in `results/` was measured on.

**Is a different ID fatal?** No — cytune runs, and every correctness guarantee (G1, G2, G4) holds,
because they are properties of what it refuses rather than of which compiler build it used. What you
lose is comparability: your timings are no longer measured on the toolchain behind `results/`, so
this project's published numbers are not a baseline for yours. `doctor` prints both IDs and flags
the mismatch rather than failing.

---

## Quickstart

### Run the shipped example first (no files to write)

A working kernel + driver pair ships inside the package, so you can confirm the whole pipeline
before writing anything of your own:

```bash
cytune tune --dry-run "$(python3 -c 'import cytune,os;print(os.path.dirname(cytune.__file__))')/examples/running_max.pyx" \
            --driver  "$(python3 -c 'import cytune,os;print(os.path.dirname(cytune.__file__))')/examples/running_max_driver.py"
```

`examples/running_max_driver.py` is also the shortest complete driver to copy from.

### Then your own module — `cytune init` writes the driver

You need two files: the `.pyx` you want tuned, and a small **driver** that says how to call it and
what "correct" means. cytune will write the driver for you by reading your kernel's signature:

```bash
cytune init mykernel.pyx        # writes driver.py + .cytune.toml, then checks the contract
```

It fills in `make_inputs` for every typed argument it can read (`double[::1]`, `long[:, ::1]`,
`Py_ssize_t`) and leaves a loud `TODO` for anything it cannot — an untyped or `object` parameter.
It deliberately does not guess: an input it invented would become the workload your oracle is
derived from, and every number after that would be about a run you never asked for.

The rest of this section is what that driver contains, so you can write or edit one by hand.

```cython
# kernel.pyx  — an ordinary Cython module. Nothing cytune-specific in it.
def run(long long[::1] a, int reps):
    cdef Py_ssize_t n = a.shape[0]
    cdef Py_ssize_t i, r
    cdef long long acc = 0
    for r in range(reps):
        for i in range(n):
            acc += a[i]
    return acc
```

```python
# driver.py
import numpy as np

N = 100_000
REPS = 50                      # cytune rewrites this so the reference run lands near --target-ms
OUTPUT_CLASS = "int"           # "float" -> tolerance;  "int"/"bool" -> bit-exact

def make_inputs(seed):
    rng = np.random.default_rng(seed)
    return (rng.integers(0, 1000, size=N, dtype=np.int64), REPS)

def call(mod, inputs):
    return mod.run(*inputs)

def canon(result):
    return np.asarray([result], dtype=np.int64)
```

```bash
cytune tune --dry-run kernel.pyx --driver driver.py   # is tuning worth it? ~90s, no budget spent
cytune tune           kernel.pyx --driver driver.py   # the real thing, ~3 min
cytune tune --explain kernel.pyx --driver driver.py   # ...and say why it answered that
cytune audit          kernel.pyx --driver driver.py   # which directives are safe to disable here?
```

Don't put `# cython: boundscheck=False` in your `.pyx` — that pins a factor cytune is varying.

`--preset quick|standard|thorough` buys less or more search. Real library code is rarely one file:
point cytune at a directory holding `kernel_meta.json` + `closure/` to tune a module that `cimport`s
its siblings ([USER_GUIDE §2.1](docs/USER_GUIDE.md)).

### The four answers

| verdict | exit | means |
|---|---|---|
| `IMPROVEMENT` | 0 | a measured, endpoint-verified, sanitizer-clean speedup. Paste the emitted header, or use `--apply`. |
| `HONEST-FLAT` | 2 | no speedup worth acting on. **The common case on real code**, and a real answer. |
| `NO-SAFE-IMPROVEMENT` | 3 | a faster config existed and was **refused** — by the oracle or the sanitizer. Read the reason. |
| *(error)* | 1 | cytune could not answer. |

---

## It finds memory bugs your tests cannot

The most useful thing cytune does is not the speedup. Disabling `boundscheck`/`wraparound` is the
single biggest lever in this search space, and it is also how a latent out-of-bounds read becomes a
live one. An **output** check cannot see that: a min/max reduction absorbs one garbage element
without changing the answer, so the result is right while the read is illegal.

So cytune rebuilds the config it is about to recommend under ASan+UBSan and runs it:

```
!! cytune found a MEMORY-SAFETY DEFECT in your kernel.
   config 1326 was 1.045x faster and was REFUSED by the sanitizer:
     AddressSanitizer, SUMMARY: AddressSanitizer, buffer-overflow

   This is a latent bug in YOUR kernel, not a cytune limitation. It only manifests when
   boundscheck/wraparound are disabled, and the output check could not see it...
```

This is not hypothetical: it is the exact defect (D23) that invalidated 1,296 configurations of
this project's own study, found by an output oracle that passed them all.

**`cytune audit` makes that deterministic.** `tune` gates the configuration it is about to
recommend — two out of 1,728 — so *whether* it finds a latent bug depends on where the search
lands: measured at 3 of 5 runs on the same fixture. `audit` does not tune at all; it gates a
pre-registered risk set and found the same defect **6 of 6**, with an identical verdict every time.

---

## Does it actually find good configurations?

Measured against ground truth, on real library code. The nine Dataset-R anchors are modules from
scipy and scikit-learn whose full 1,728-configuration tables were measured exhaustively. cytune was
run on all nine and its answer compared with the frozen tables:

| | |
|---|---|
| configurations measured | 33–49 of 1,728 (~2%) |
| **median regret vs the known optimum** | **+1.41%** |
| worst | +5.41% |
| best | found the exact optimum (`csr`, rank 1 of 1,152) |
| every emitted config | sanitizer-CLEAN |

Method, caveats and the full table: [`results/release/V1_RELEASE_REPORT.md`](results/release/V1_RELEASE_REPORT.md).

---

## Read before you trust a number

The "research preview" label is load-bearing:

- **The routing policy is an engineering default, not a validated router.** The study measured
  that per-kernel routing does *not* beat always-DOE on held-out kernels. cytune ships one
  algorithm. `results/PHASEP_REPORT.md` §5.
- **Three of four kernel categories are underpowered** (achieved power 0.708/0.776/0.708 against a
  0.80 target), and the study ran 20 of a planned 200 repetitions.
- **On most real code the honest answer is "no improvement."**
- **One machine.** Every number in `results/` was measured on one i3-10100F. Nothing transfers.

What *is* solid is what the tool **refuses** to do, and those refusals are exercised by tests that
drive their failure paths. See [docs/GUARANTEES.md](docs/GUARANTEES.md).

---

## Documentation

| | |
|---|---|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | pipeline, every flag, `.cytune.toml`, the certificate field by field |
| [docs/GUARANTEES.md](docs/GUARANTEES.md) | what is promised and what is not, each with its evidence |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | failures actually hit, with fixes |
| [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) | open findings, and what was fixed |
| [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) | the frozen 1.x API: schemas, exit codes, what may change |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | module map, the one-way dependency rule, the invariants |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | how to extend it, and the obligations that come with each kind of change |
| [SECURITY.md](SECURITY.md) | threat model: what cytune defends, and the one class it cannot |
| [CHANGELOG.md](CHANGELOG.md) | what changed, and what a user must know about |
| `results/PHASEP_REPORT.md` | the full study report |
| `results/DEFENSE_SUMMARY.md` | one page, plain language |
| `results/usertest/` | the cold-user acceptance tests, verbatim |

Run the test suite with `pip install -e ".[test]" && pytest -q` — that covers both `src/cytune`
(the product, which must pass with no `scripts/` and no `results/` present) and `tests/` (the
study-equivalence checks, which skip cleanly without them).
