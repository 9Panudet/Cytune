# cytune

**Your Cython kernel is probably leaving 10–50 % on the table in compiler settings. cytune finds
which settings, proves the answer still computes what you wrote, and refuses to recommend anything
it cannot stand behind.**

Research preview. One machine, x86-64 Linux, rootless podman.

```bash
pip install cytune
cytune init kernel.pyx                                 # writes a driver.py you can run
cytune doctor                                          # is this machine ready?
cytune tune kernel.pyx --driver driver.py              # the answer
```

That is the whole thing. Three commands, no configuration file, no prior knowledge.

`init` writes the driver by reading your function signature. A driver is four names, and this is
all of them:

```python
def make_inputs(seed):  ...   # build the arguments your kernel takes
def call(mod, inputs):  ...   # mod.your_function(*inputs)
def canon(result):      ...   # -> a numpy array, so two runs can be compared
OUTPUT_CLASS = "float"        # or "int" / "bool" — "int" and "bool" buy a bit-exact check
```

**Check what `init` wrote before you trust the answer.** If it had to invent an input for you, that
input is the workload every number describes. cytune refuses to tune when the inputs make your
kernel's output constant — its correctness check would be unfalsifiable — but it cannot tell that
an input is merely *unrepresentative*.

In a hurry: `--target-ms 5 --preset quick` gives a rougher answer in about a minute.

Want to see it work before pointing it at your own code? The package ships a kernel and a driver:

```bash
python -c "import cytune, os; print(os.path.dirname(cytune.__file__) + '/examples')"
cytune tune <that path>/running_max.pyx --driver <that path>/running_max_driver.py
```

---

## The problem

`boundscheck`, `wraparound`, `cdivision`, `initializedcheck`, `nonecheck`, `-O2` vs `-O3`,
`-march=native`, `-funroll-loops`. Everyone knows these matter. Almost nobody measures them,
because measuring them properly means 1,728 builds, a quiet machine, and a way to check that each
build still produces your answer.

So the usual approach is folklore: turn off boundscheck, use `-O3`, hope. Sometimes that is 2×
faster. Sometimes `-O3` is *slower* than `-O2` for your kernel. Sometimes turning off boundscheck
silently converts a latent off-by-one into an out-of-bounds read that your tests do not catch,
because the garbage element happened not to change the answer.

## What cytune does

It builds your kernel about 35 different ways, times them on an isolated CPU core, checks every one
against a golden output produced by your own comparison function, rebuilds the winner under
AddressSanitizer, and hands you a certificate.

```
VERDICT: IMPROVEMENT
  1.967x faster than the reference configuration, verified at the endpoint tier and re-checked
  against the oracle.

EMIT — paste this at the top of the .pyx:
  # cython: boundscheck=False, wraparound=False, cdivision=True, initializedcheck=True, nonecheck=False
```

Or with `--apply`, it writes that header for you.

## What makes it different

**It refuses to recommend a configuration that changes your output.** Every configuration is
re-checked against a golden output, twice — once at the screening tier and again at the heavier
verification tier, because passing a quick check is not a licence. A configuration that fails is
*infeasible* no matter how fast it was.

**It refuses to recommend a configuration that reads memory it does not own.** Before emitting
anything, cytune rebuilds that exact configuration under AddressSanitizer and UBSan and runs it. A
report means refusal. And a gate that could not run is recorded as *not run* — never as a pass.

**It says "no improvement" instead of inventing one.** The most common honest answer on real code
is that your kernel is not directive-bound. Three separate mechanisms produce that answer, and any
gain below `max(2 × measured noise, 2 %)` is not claimed at all. Exit code 2 means "nothing is
reliably faster than what you have" — an answer, not a failure.

**It finds bugs.** `cytune audit` runs a fixed set of risky directive corners under a sanitizer and
tells you if your kernel reads out of bounds. Same verdict every time, no timing involved. This is
not hypothetical: in this project's own benchmark, 1,296 kernel-configuration pairs were recorded
as *correct* by an output check while executing an out-of-bounds read — a reduction absorbs one
garbage element without changing its result. The sanitizer found them. The output check could not.

**And the one nobody else can say: its accuracy has been measured against exhaustively-known
optima on real library code.**

## The number, with its conditions

Nine kernels taken from real libraries — sparse matrix-vector multiply, isotonic regression, LDA,
Floyd-Warshall, connected components, k-means with the Elkan bound, piecewise polynomial
evaluation, binning, a predictor. For each, **all 1,728 configurations were measured exhaustively**,
so the best possible answer is known rather than estimated.

cytune measures ~35 of the 1,728 and picks one. How much slower is its pick than the best pick it
was allowed to make?

| | |
|---|---|
| **median across the nine kernels** | **1.409 %** (range 1.409–1.719 %) |
| **worst kernel** | **5.412 %** (range 5.412–9.791 %) |
| configurations measured | 313 total, ~35 per kernel |

**Conditions, which are part of the number:** nine kernels · one machine (i3-10100F, quiesced) ·
five repeated runs · default floating-point-strict policy, so 576 of the 1,728 were eligible.
Ranges are across the five runs, because a single run is one draw and this project has measured
runs of the *same unchanged engine* disagreeing by up to 6.7 percentage points on one kernel.

Every figure above: [`evidence/repeated_dogfood.json`](evidence/repeated_dogfood.json).

## Limitations — the same page, not a link

**Nothing transfers to other hardware.** The recommendation is measured on *your* machine and is
about your machine. `-march=native` in particular is not portable; `--portable-flags` restricts it.

**A clean sanitizer run is not proof of memory safety.** It proves that on the inputs your driver
generated, nothing was detected. Different inputs may reach different code.

**The recommendation is not optimal, and the table above is what that costs.** cytune measures ~2 %
of the space. It usually lands within about 1.4 % of the best allowed configuration and has been
measured as far off as 9.8 %.

**Timing claims are rig-dependent.** Without a quiesced host cytune still runs, and labels its
numbers `portable` and indicative rather than decision-grade. It tells you which it used.

**Your driver is inside the trust boundary.** If your comparison function says two different
answers are the same, cytune will believe it.

**The search engine's routing is an engineering default, not a validated per-kernel router.** The
study behind cytune measured that per-kernel engine switching does *not* beat always-using-DOE on
held-out kernels, and the tool says so on every certificate.

The full, numbered list — eight guarantees and nine non-guarantees — is
[`docs/GUARANTEES.md`](docs/GUARANTEES.md). It is written to be read by someone trying to catch us
out.

## The three answers, and what to do about each

| exit | verdict | what to do |
|---|---|---|
| `0` | **improvement** | paste the header, or re-run with `--apply` |
| `2` | **honest-flat** | nothing. Your kernel is not directive-bound — the time is going somewhere a compiler flag cannot reach. That is worth knowing, and it took two minutes |
| `3` | **no-safe-improvement** | read the `WINNER REJECTED` / `OBSERVED BUT NOT RECOMMENDED` block on the certificate. Something faster existed and could not be claimed — often because the sanitizer reported on it, which means you have a bug |
| `1` | error | bad arguments or an environment problem. `cytune doctor` names the fix |

`0`, `2` and `3` all mean cytune finished and stands behind its answer.

## Requirements

x86-64 Linux · Python 3.9+ · podman (rootless is fine) · a Cython module with a driver.
`cytune doctor` checks all of it and prints the fix line for anything missing;
`cytune doctor --build-image` builds the pinned toolchain image and verifies its digest.

The best results need a quiesced host (turbo off, performance governor, an isolated core). Without
one, cytune runs in `portable` mode and labels its numbers as indicative.

## Going deeper

| | |
|---|---|
| [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) | the pipeline stage by stage, the driver contract, the certificate field by field. §13 is the complete flag/config/exit-code reference |
| [`docs/GUARANTEES.md`](docs/GUARANTEES.md) | what is guaranteed and what explicitly is not |
| [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) | when something goes wrong |
| [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) | what is broken and known |
| [`evidence/`](evidence/) | every number on this page, with its conditions and how to recompute it |

**Other branches:** `dev` carries the development harnesses, the release tooling and a deep
system-documentation set. `research` carries the study this is built on — the pre-registrations,
the frozen benchmark, and the negative results, including the two algorithms that were measured and
not shipped.

## Status

Research preview, version 1.0.0. It is used, it is tested (900+ tests, a live end-to-end gate before
every tag), and its own defect ledger is public.

Before this release, four testers — a first-time user, an adversary, a QA engineer and a senior
reviewer — were pointed at it with instructions to break it. **They found five defects in a few
hours, four of which produced a confident wrong answer rather than an error.** All five are fixed;
six further issues are open and published. The whole account, including what held:
[`evidence/adversarial_campaign.md`](evidence/adversarial_campaign.md).

That is the honest state of it: the machinery is careful, and it has not yet been run by many people
on many machines. That is the main thing standing between "research preview" and 1.0.
