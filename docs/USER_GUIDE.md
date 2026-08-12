# cytune user guide

Install and quickstart are on the [front page](../README.md). This is the detail.

Everything here was observed from the CLI. Where a behaviour was not exercised, it says so.

---

## 0. Getting started: `cytune init`

```
cytune init KERNEL.pyx [--driver PATH] [--force]
```

Writes a `driver.py` beside your module (or inside a module tree), a starter `.cytune.toml` if you
have none, and then runs the same contract check `tune` uses at ingest, so you see it pass before
you spend any measurement time.

It reads your kernel's first public `def`/`cpdef` and fills in `make_inputs` from the argument
types:

| declared as | scaffolded as |
|---|---|
| `double[::1] a` | `np.ascontiguousarray(rng.standard_normal((N,)).astype(np.float64))` |
| `long[:, ::1] m` | a 2-D `np.int64` array |
| `Py_ssize_t n`, `long reps` | an integer literal |
| `object payload`, or untyped | **`TODO`**, with a banner at the top of the file |

`SCALE` — the calibration knob `tune` rewrites — starts at 4096 for 1-D work and drops with
dimensionality, so a 2-D kernel does not open with a 134 MB array.

**It does not guess.** An input cytune invented would become the workload the oracle is derived
from, and every number downstream would describe a run you never intended. A `TODO` you have to
fill in is the honest failure direction.

---

## 1. The pipeline

```
cytune tune KERNEL.pyx --driver DRIVER.py [flags]
```

Six stages. The CLI prints each as `[n/6]`, with elapsed time and — once the probe has measured a
per-config cost on *your* kernel — an estimate for the rest.

### `[1/6] ingest`

Copies your `.pyx` and driver into the workspace, builds the reference configuration plus the probe
design (17 builds), runs the reference to capture the **golden output**, and derives the **oracle**
from it. It also **calibrates**: it rewrites the `REPS` knob in your driver so the reference lands
near `--target-ms`. The numbers can move a lot (`calibrated REPS: 300 -> 1077`). The knob is named `REPS` or `SCALE`, whichever your driver defines — cytune prints the one it found, so §0's scaffolded `SCALE` and this example's `REPS` are the same mechanism.

The reference is fixed — config 288: `boundscheck=True, wraparound=True, cdivision=False,
initializedcheck=True, nonecheck=False` with `-O2 -march=x86-64 -ffp-contract=off`. Cython's safe
defaults, and what cytune falls back to whenever it will not recommend anything else.

**If nothing compiles, this stage aborts and shows you the compiler's own words**, plus the path to
the full build log. A *partial* build failure is normal — those configs are simply infeasible and
the run continues.

### `[2/6] probe`

A 16-config pre-registered screen plus the reference. Three numbers you will see again:

| number | meaning |
|---|---|
| `feasible n/17` | how many probe configs produced correct output at all |
| `delta_probe` | slowest ÷ fastest **feasible** probe config — the apparent headroom |
| `IF_probe` | interaction fraction: how much variation is *not* explained by independent single-factor effects. Low ⇒ factors act separately. `NA (degenerate)` ⇒ too few feasible rows to fit it |

`delta_probe` is a **screening-tier** number and is routinely much larger than the final speedup.
The certificate now reconciles the two explicitly, in a section called *WHY THE PROBE NUMBER AND
THE SPEEDUP DIFFER*. Trust the endpoint number.

### `[3/6] route`

Picks a search budget from those features, and decides whether to search at all.

| rule | condition | outcome |
|---|---|---|
| `R0` | reference infeasible, or < 4 feasible probe rows | abort — nothing to compare against |
| `R1` | `delta_probe <= 1.10` | **honest-flat** — tuning is skipped entirely |
| `R2` | `IF_probe` degenerate | DOE, conservatively |
| `R3` | `delta_probe >= 1.5` and `IF_probe >= 0.25` | interaction-dominated → DOE (BO is not installed) |
| `R4` | `delta_probe >= 1.5`, `IF_probe < 0.25` | DOE — "separable lever" |
| `R5` | between 1.10 and 1.5 | DOE — modest but above the noise floor |

Feasibility below 75% raises the budget by 8 and is reported prominently.

**The engine is always DOE.** See [GUARANTEES.md § routing](GUARANTEES.md#n4--routing-is-doe-unconditional-and-here-is-why).

### `[4/6] tune`

Runs DOE within its budget: the fixed pre-registered screen design first, then a predicted-best
walk over the fitted main effects. The walk only visits configs this run could actually **emit** —
spending budget on a config the policy forbids emitting would buy a number the certificate must
then refuse to act on.

`--probe-as-screen` (**experimental, off by default**) skips the screen design and spends the whole
budget on the walk, on the grounds that the 17-config probe is already a D-optimal screen. It
measured better on the frozen kernel tables and on real code, and it did **not** clear its
pre-registered acceptance rule — one anchor regressed past the bound, and that bound turned out to
be tighter than the measurement's own run-to-run spread. The full evidence, including why it is not
the default, is in `results/release/DOE_V2_REPORT.md`. The certificate's `search` block always
records which of the two ran.

### `[5/6] verify`

The gate. Three independent checks on the candidate:

1. **Endpoint re-measurement** — the winner *and* the reference are re-timed (median-of-3 at K=30,
   escalating to at most 5 while CV > 0.05) and the winner's output is re-checked against the
   oracle. A config that passes the fast screen and fails here is never emitted.
2. **The §1.4 sanitizer gate** — the candidate is rebuilt under ASan+UBSan inside the pinned image
   and run. If it reports, the recommendation is withdrawn and cytune falls back to the reference.
3. **The gate again, on whatever is actually being emitted** — including the reference fallback.
   The certificate's `sanitizer_gate` field always describes the config you are being handed.

If even the reference reports, cytune emits **nothing** and says so. A memory error at your
baseline is not something a compiler flag can make safe.

### `[6/6] certify`

Writes the certificate to stdout, to `<workspace>/<name>/certificate.txt`, and as
`certificate.json`, alongside the raw `table.jsonl` every number recomputes from.

---

## 2. Flags

`cytune tune MODULE --driver DRIVER [options]`

| flag | default | what it does |
|---|---|---|
| `MODULE` | *(required)* | path to the `.pyx`, **or** to a directory holding `kernel_meta.json` + `closure/` for a multi-file module (see §2.1) |
| `--driver PATH` | *(required)* | the driver (see §3) |
| `--preset {quick,standard,thorough}` | `standard` | how much measurement to buy: `quick` halves the routed search budget on a ~30 ms workload, `thorough` doubles it. Any flag you also pass wins over the preset |
| `--explain` | off | after the verdict, print why this route and budget were chosen, what the bar was, and what would have to change for the answer to differ |
| `--workspace DIR` | `.cytune` | where builds, raw measurements and the certificate land |
| `--name NAME` | module basename | names the subdirectory and the certificate |
| `--rig {auto,quiesced,portable}` | `auto` | `auto` uses the quiesced rig if available, else portable. `quiesced` **requires** it and refuses to run without it. `portable` forces best-effort. |
| `--target-ms MS` | `65` | calibrate the driver knob so the reference lands near this. `0` disables (**untested**) |
| `--allow-fast-math` | **off** | permit `-ffast-math` configs to be selected and emitted (still oracle-gated) |
| `--allow-fp-contract` | **off** | permit FMA contraction (`-ffp-contract=fast`) to be selected and emitted |
| `--portable-flags` | off | restrict the recommendation to `-march=x86-64`, so the emitted flags are safe on other machines |
| `--dry-run` | off | ingest + probe only: the landscape, what cytune would do, and an estimated cost. No tuning budget spent |
| `--json` | off | certificate as JSON on **stdout**; all narration moves to stderr |
| `--apply` | off | write the emitted directive header to `<module>.tuned.pyx` |
| `--in-place` | off | with `--apply`, edit the module itself (keeps a `.cytune-backup`) |
| `--config PATH` / `--no-config` | nearest `.cytune.toml` | see §4 |

`cytune init MODULE [--driver PATH] [--force]` — scaffold a driver. See §0.
`cytune doctor [--json] [--build-image]` — check the environment; `--build-image` builds the pinned
toolchain and verifies its digest. See §7.
`cytune audit MODULE --driver DRIVER [--workspace DIR] [--name NAME] [--json]` — see §2.2.

### 2.1 Multi-file modules

Real library code is rarely one file: a `.pyx` that `cimport`s a sibling `.pxd` needs the
surrounding package on the include path to compile at all. Point cytune at a **directory** instead
of a file:

```
mymodule/
  kernel_meta.json      {"module": "_isotonic", "pyx_relpath": "sklearn/_isotonic.pyx", "mode": "closure"}
  closure/
    sklearn/_isotonic.pyx
    sklearn/utils/_typedefs.pxd
    ...
```

`pyx_relpath` is relative to `closure/` and names the module to build; everything else in `closure/`
is available to it. `--driver` is still a separate argument, so a `driver.py` inside the tree cannot
silently override the one you named.

This is how the nine real scipy/scikit-learn modules in the ground-truth dogfood were tuned.

### 2.2 `cytune audit` — which directives are safe to disable?

```bash
cytune audit kernel.pyx --driver driver.py
```

It does **not** tune, does not time anything, and needs no quiesced rig. It rebuilds your kernel in
a **pre-registered set of eight configurations** under AddressSanitizer + UndefinedBehaviorSanitizer
and runs your driver on each, then tells you, per directive, whether disabling it is safe *for this
kernel*.

Use it when `tune` returns `NO-SAFE-IMPROVEMENT`, or before you disable checks by hand.

The set is: your reference; each of `boundscheck`, `wraparound`, `cdivision`, `initializedcheck`
flipped singly; **`boundscheck` and `wraparound` off together**; and the two all-checks-off corners.

> The pair matters and is not implied by the singles. With `boundscheck=False` but
> `wraparound=True`, `a[-1]` is rewritten to `a[n-1]` — legal. With `wraparound=False` but
> `boundscheck=True`, it raises before reading. Only both-off reads before the buffer.

Rows come back as `CLEAN`, `REPORTED`, `RAISED` (your kernel threw — with `boundscheck` on, usually
Cython catching a bad index, which is itself a finding), `NOT RUN`, or `NO BUILD`. Exit `0` clean,
`3` defects found, `1` the audit could not complete. **A clean audit is evidence, not proof** — it
checks eight configurations on the inputs your driver generates.

### Floating-point consent — both axes are opt-in

There are two ways a config can change floating-point results, and **both** now require you to say
so:

| flag | what it permits | how strong |
|---|---|---|
| `--allow-fast-math` | `-ffast-math`: reassociation, no-NaN/no-Inf assumptions, flushed denormals | large |
| `--allow-fp-contract` | `-ffp-contract=fast`: the compiler may fuse a multiply and an add and round once instead of twice | small but real |

By default cytune is **FP-strict**: neither is eligible for emission, and the certificate says
`FLOATING-POINT CONSENT: strict (default)`.

*This changed after cold-user finding F19.* Contraction used to be emitted by default while
`-ffast-math` required a flag — two semantic changes, two consent models, one README sentence
describing both. Opting in changes what is **tried** and what may be **emitted**; it never changes
what is **accepted** — such a config is still emitted only if it passes the same oracle.

Independently, **`-ffp-contract` is always explicit** in the emitted flags, because GCC's default
is `fast` and leaving it implicit would make the flags mean something other than what they say.

**`-ffast-math` subsumes contraction.** GCC's `-ffast-math` already permits multiply-add fusion, so
a config emitted under `--allow-fast-math` alone will contain `-ffp-contract=fast` in its flag
string. That is a restatement of what you already consented to, not a second undisclosed change —
and the certificate says so explicitly rather than reporting `fma_contraction_permitted: false`
next to a flag string containing it. If you need contraction **off**, do not use
`--allow-fast-math`.

### `-march=native` and `--portable-flags`

`-march` is a search factor and `native` is one of its levels, so an emitted flag string can
contain `-march=native`. That hard-codes the compiling machine's ISA: a binary built with it may
fault with an illegal instruction, or be silently detuned, elsewhere. cytune now prints a
**PORTABILITY WARNING** whenever it emits one.

`--portable-flags` restricts *selection* to `-march=x86-64`, so the answer you get is one that was
actually measured under baseline flags. It does not rewrite the flags after the fact — that would
hand you a configuration nobody timed.

### What is optimised, and the raw data for what is not

cytune optimises exactly one thing: **wall-clock time** of the driver's `call()`, measured inside
the pinned image at the endpoint tier. There is no flag to change that, because there is nothing
else it could certify — endpoint re-measure, separation and the emit margin are all defined over
time and over nothing else.

Compile time and object size are still **recorded for every configuration it builds**, in
`<workspace>/<name>/build_manifest.jsonl`:

```json
{"config_id": 1392, "ok": true, "reason": "ok", "compile_s": 15.89, "so_size_b": 128312, ...}
```

so you can rank on them yourself:

```bash
jq -s 'map(select(.ok)) | sort_by(.so_size_b) | .[0]' .cytune/mymod/build_manifest.jsonl
```

Each row's binary is identified in `artifacts.jsonl` beside it (`artifact_sha256`, `build_argv`),
so a size you read there is the size of a file you can point at.

The **feasible set** is not part of the objective — it is a hard constraint. Oracle failure and
sanitizer report are both absolute.

---

## 3. The driver contract

Copy this and edit it — the error message points here, so here it is:

```python
# driver.py
import numpy as np

N = 100_000
REPS = 50                      # cytune rewrites this to hit --target-ms, in ITS OWN copy
OUTPUT_CLASS = "int"           # "float" -> tolerance;  "int"/"bool" -> bit-exact

def make_inputs(seed):
    rng = np.random.default_rng(seed)
    return (rng.integers(0, 1000, size=N, dtype=np.int64), REPS)

def call(mod, inputs):
    return mod.run(*inputs)

def canon(result):             # must return a numpy array; wrap a scalar
    return np.asarray([result], dtype=np.int64)
```


Four names, in a plain Python file:

| name | contract |
|---|---|
| `make_inputs(seed)` | returns the argument tuple for `call`. Must be deterministic given the seed and must not mutate global state — it is re-run per repetition |
| `call(mod, inputs)` | invokes your module: `return mod.run(*inputs)` |
| `canon(result)` | returns a **numpy array**. Wrap a scalar: `np.asarray([x], dtype=np.int64)` |
| `OUTPUT_CLASS` | `"float"`, `"int"` or `"bool"` |

Optionally a module-level `REPS` (or `SCALE`) integer — the calibration knob. Without one, cytune
measures the workload as written and says so.

`OUTPUT_CLASS` decides the oracle: `int`/`bool` compare **bit-exactly** (sha256 of the canonical
array); `float` compares with a tolerance. Omit any of the four and cytune names exactly which are
missing and restates the whole contract.

Your driver is **never imported on the host** — only inside the container. The contract is checked
by source inspection, because importing a stranger's driver on the host would run arbitrary code
outside the sandbox.

---

## 4. `.cytune.toml`

Project defaults, so you stop retyping the flags that matter. Nearest file at or above the CWD;
`--config` names one explicitly, `--no-config` ignores them.

```toml
[cytune]
workspace         = ".cytune"
rig               = "auto"        # auto | quiesced | portable
target_ms         = 65
allow_fast_math   = false
allow_fp_contract = false
portable_flags    = false
```

**Precedence: CLI flag > `.cytune.toml` > built-in default.** The certificate records the effective
value *and where each came from* (`effective_config.provenance`), so a reader never has to guess
whether `--allow-fp-contract` was on.

An unknown key is an **error**, not a warning: a typo'd `allow_fastmath = true` that was silently
ignored would leave you believing you had opted in.

---

## 5. Rig modes

| | `quiesced` | `portable` |
|---|---|---|
| how you get it | `--rig auto` (default) when `measure_wrap` verifies the host, or `--rig quiesced` to require it | `--rig portable`, or `auto` when the host cannot be verified |
| controlled | turbo off, governor pinned, a core isolated, THP asserted | nothing |
| certificate says | `quiesced — host asserts verified by measure_wrap (…fingerprint…)` | `portable measurement — INDICATIVE, not decision-grade` |
| emit margin OBSERVED on the acceptance runs | 0.0200 | 0.0808 on an unquiesced host; 0.0200 when `--rig portable` was forced on a quiesced one |

> **Those are measurements, not properties of the rig mode.** The emit margin is
> `max(2 × combined endpoint CV, tau=0.02)` and is computed from the noise **this run** measured.
> A quiesced rig that is idle usually bottoms out at the `tau` floor — but a quiesced host doing
> something else at the time does not: a user running other work alongside cytune measured
> **0.2196**, a 22% bar, on a rig `doctor` correctly called quiesced. Read the margin the
> certificate prints, never the number in this table. If it is far above 0.02, check the
> certificate's `escalation` block too — it will usually say the endpoint tier ran out of
> sub-measures before reaching its CV target, which is the same story told twice.

The degradation is **quantitative, not a caveat**. On a genuinely unquiesced host the CV was ~10×
larger, so the bar rose from 2% to 8%: portable mode does not report noisier improvements — it
reports **fewer**, and refuses the ones it cannot resolve.

**But `--rig portable` does not un-quiesce your machine.** Forcing it on a quiesced host relabels
the claim — the certificate stops asserting a verified rig — without adding any noise, so you will
see the same 0.0200 margin. The 0.0808 figure is a property of an unquiesced *host*, not of the
flag.

**Correctness guarantees are identical in both modes.** Only the timing claim degrades.

To get quiesced: `sudo scripts/host_prep.sh`, then `cytune doctor`.

---

## 6. Provenance: what a certificate is bound to

Every certificate carries a `PROVENANCE` block, and every line of it is a hash of a file this run
produced — not a value derived from the configuration id:

```
PROVENANCE — what these claims are bound to
  emitted artifact      : 410578f8e36d (timed: 410578f8e36d)
  toolchain image       : d45e33b08bad
  rig fingerprint       : no_turbo=1 gov_cpu3=performance isolated=3,7 thp=madvise
  measured              : 33 configs, 33 distinct binaries from 22 distinct generated sources
                          (22 directive combinations)
```

`emitted artifact` and `timed` must be equal — the `.so` cytune describes is the one the endpoint
tier ran. **If they had differed, nothing would have been emitted.** The same applies to the
reference, because a forged baseline manufactures a speedup as well as a forged winner.

If any directive turns out not to change the generated code for your kernel, the certificate says
so by name:

```
FACTOR DEGENERACY — directives that do nothing to THIS kernel
  initializedcheck never changed the generated C in any pair of configurations this run built
  that differed only in it. Turning it off cannot make your kernel faster.
```

That is a real finding about your code, not a warning. If **every** directive combination produces
identical C, cytune refuses the run: it cannot tell whether something is overriding the directives
(in which case every claim about them would be false) or your kernel simply has no code they
affect, and it will not guess.

### What the certificate attests

The last block before the exit code states the scope, because a certificate is a document people
forward:

> **IT ATTESTS** that cytune built, oracle-checked, sanitizer-gated and timed the configuration
> named above, in the pinned toolchain, and that every claim is bound to the hashes in PROVENANCE.
>
> **IT DOES NOT ATTEST** that the timings are what the kernel really takes. The measurement child
> loads your own driver into the process that owns the clock.

cytune corroborates the reported ratio against the parent process's wall clock and withholds the
speedup when they disagree — see `measurement.timing_corroboration` — but a driver that genuinely
does different work for different configurations is outside what any timing check can see.

---

## 7. Building the pinned image

```
cytune doctor --build-image
```

Runs `podman build` for you and then **verifies the digest** of what came out against the toolchain
every number in `results/` was measured on. A build that succeeds and produces a different image is
reported as a failure, not a checkmark: a clean sanitizer verdict from an unpinned image is not
treated as a pass, the "safe" wording is withheld, and `--apply` refuses.

---

## 8. Exit codes

Scriptable. `0`, `2` and `3` are all **successful** runs — cytune answered the question.

| code | verdict | meaning |
|---|---|---|
| `0` | `improvement` | a verified speedup; the emitted config is safe to use |
| `2` | `honest-flat` | no speedup worth acting on |
| `3` | `no-safe-improvement` | a faster config existed and was refused, **or** even the emitted config reports. Read the certificate |
| `1` | — | **any error**: bad arguments, an unrecognised flag, a bad config file, a build failure, `--rig quiesced` on an unquiesced host |
| `0` | — | a successful `--dry-run`. A dry run produces **no verdict**, so it does not borrow one's code; branch on `--dry-run` yourself, not on the exit status |

There is no code collision: usage errors exit `1`, not argparse's default `2`, precisely so that
`2` means only `honest-flat`.

```bash
cytune tune k.pyx --driver d.py --json > cert.json
case $? in
  0) jq -r .emitted_config.directive_header cert.json ;;   # NB: not for --dry-run, see above
  2) echo "nothing to gain" ;;
  3) echo "UNSAFE — read the certificate"; exit 1 ;;
  *) echo "cytune failed"; exit 1 ;;
esac
```

---

## 9. `--dry-run`

Runs ingest and probe only, then reports the landscape, the routing decision, how many configs a
full run would measure, and an estimated cost derived from *this kernel's* measured per-config
time. It spends no tuning budget, and the probe measurements it did pay for are written to
`table.jsonl` and **reused** by a later full run.

The cheapest way to decide whether tuning is worth it.

---

## 10. `--apply`

Writes the emitted `# cython:` header into your source, so five booleans are not hand-transcribed.

- `--apply` writes a sibling copy: `kernel.pyx` → `kernel.tuned.pyx`. Your file is untouched.
- `--apply --in-place` edits the original and keeps `kernel.pyx.cytune-backup`.
- It replaces an existing `# cython:` line, or inserts one after any shebang/coding line.
- It also prints a ready-to-paste `setup.py` fragment carrying the GCC flags.

**It refuses** unless the verdict is `improvement` **and** the emitted config's sanitizer gate came
back `CLEAN`. Not "did not report" — CLEAN. A gate that could not run leaves `clean = null`, and
null is not a pass; `--apply` writes checks-off directives into source, and doing that on a config
whose memory safety was never confirmed would be D23 rebuilt at the last possible step.

---

## 11. The certificate, field by field

### `VERDICT`

- **`IMPROVEMENT`** — followed by the speedup, the directive header, the `cythonize -X` form, and
  the GCC flags.
- **`HONEST-FLAT`** — no speedup worth acting on, and **nothing was refused**. Since F4 this word
  means only what it says.
- **`NO-SAFE-IMPROVEMENT`** — either a faster config was found and refused, or the emitted config
  itself reports. This is the verdict that used to be buried under "honest-flat".

### The memory-safety block

When the sanitizer refuses something, the block goes **above** the recommendation, in `!!!` rules,
with the config id, how much faster it looked, the ASan/UBSan summary, the path to the full report,
and a statement that this is a bug in *your* kernel that an output check cannot see. If both the
candidate and the emitted config report, both are listed and the verdict becomes
**NO SAFE RECOMMENDATION**.

### `EMIT`

The directive header, the `cythonize -X` arguments, and the GCC flags — three forms, so you can
wire it into whatever build you have. On the flat path, your reference configuration unchanged. If
the emitted config is itself unsafe: `EMIT: NOTHING`, with the configuration shown only so you know
what was checked, explicitly labelled *not a recommendation*.

### `OBSERVED BUT NOT RECOMMENDED`

Flat path only. The fastest probe config and its measured ratio, flagged as an observation. This is
the **selection-bias guard**: on a flat landscape the minimum of a small sample is biased low, so
"the fastest one I happened to try" is not evidence. On the acceptance fixture it declined a config
that had measured 1.0029× faster.

### `MEASURED SPEEDUP`

- **separation** — not a p-value; the literal statement that the winner's worst sub-measure beat
  the reference's best. If they overlap, the gain is not claimed. Suppressed as *not applicable*
  when the emitted config is the reference (there is no comparison to make).
- **emit margin** — the bar, computed from this run's own measured noise; never below 2%.

### `CORRECTNESS CERTIFICATE`

Oracle class, tolerance and its basis, the determinism gate (5 reference reps, bit-identical), how
many configs were measured, how many were rejected as incorrect and why, and:

```
emittable candidates  : 10 of 29 feasible (19 excluded by policy: fast_math=12, fp_contract=7)
```

The counts name their denominator and sum — finding F18.

### `SANITIZER GATE (on the config being emitted)`

`CLEAN`, `REPORTED`, or `NOT RUN`. **NOT RUN IS NOT A PASS** and the certificate says so in those
words, with the D23 explanation. `clean` in the JSON is `true`, `false`, or `null`.

### `ROUTING`, `RIG MODE`, `FLOATING-POINT CONSENT`, `PORTABILITY WARNING`
See §1, §5, §2.

### `GLOSSARY`
Every insider term the certificate uses — `delta_probe`, `IF_probe`, `tau`, `emit margin`,
`endpoint tier`, `separation`, `the reference`, `§1.4 sanitizer gate`, `rule R0..R5` — defined
inside the certificate, so it needs no other document (finding F16).

### JSON-only fields

`sanitizer_gate` (with `stderr_excerpt`), `winner_rejection`, `memory_safety_finding`,
`memory_safety_finding_emitted`, `emitted_config_unsafe`, `probe_features`, `probe_vs_endpoint`,
`selection`, `emission_policy`, `effective_config`, `portability`, `exit_code`,
`emitted_config.factors`.

---

## 12. "Honest-flat" is a real answer

The most common outcome on real code is that there is no speedup. Three mechanisms produce it, all
refusals rather than failures:

1. **The flat route (R1).** Probe spread at or below the noise floor ⇒ tuning is skipped. A search
   on a flat landscape does not find a winner; it finds the luckiest measurement.
2. **The selection-bias guard.** Even on the flat path the best probe config is measured at the
   endpoint tier and reported — as an observation, explicitly not a recommendation.
3. **The emit margin.** Any gain below `max(2 × measured CV, 2%)` is not claimed at all.

If you get `HONEST-FLAT`, the useful information is: *your kernel is not directive-bound.* The time
is going somewhere a compiler flag cannot reach — memory latency, a syscall, the interpreter
boundary, an algorithm. That is worth knowing, and it took under two minutes to learn.

And note what it now does **not** mean: if a faster config existed and was refused, you get
`NO-SAFE-IMPROVEMENT` instead, because "no headroom exists" and "all the headroom was unsafe" are
different answers.

---

## 13. The complete surface (reference)

Everything cytune exposes, in one place. Sections 0–12 above are the guide; this is the reference,
kept separate on purpose — a beginner needs three commands and should not have to read this table
to find them, and a senior needs the table and should not have to reconstruct it from `--help`.

**Counts, so leanness is measured rather than asserted:** 4 commands · 27 flags · 10 config keys ·
3 verdicts (+2 non-verdict exit codes) · 23 enforced invariants · 24 registered decision paths.
`src/cytune/test_cytune_ux.py::test_every_flag_and_config_key_is_documented_here` fails if a flag
or key exists without a line in this section, so the table cannot silently fall behind the code.

### 13.1 The three-command path

```
cytune init kernel.pyx                                 # write a driver.py you can run
cytune doctor                                          # is this machine ready?
cytune tune kernel.pyx --driver driver.py              # the answer
```

`tune` runs `doctor`'s blocking checks itself, so you can skip step 2 and still be told what to
install rather than being handed an internal error three stages in.

### 13.2 Commands

| command | what it does | exits |
|---|---|---|
| `cytune init MODULE` | writes `driver.py` and `.cytune.toml` beside the module, from the function signature, and checks the driver against the contract before returning | 0 / 1 |
| `cytune doctor` | every environment check with its fix line | 0 if nothing blocking |
| `cytune tune MODULE --driver D` | ingest → probe → route → tune → verify → certify | 0 / 2 / 3 verdicts, 1 error |
| `cytune audit MODULE --driver D` | memory-safety audit of the pre-registered risk set. No search, no timing, same verdict every run | 0 / 3 / 1 |

### 13.3 `tune` flags

| flag | why it exists |
|---|---|
| `--driver PATH` | required: the contract that makes correctness checkable — inputs, call, canon, output class |
| `--workspace DIR` | where builds and measurements live (default `.cytune`); point it at scratch space on a small disk |
| `--name NAME` | the session name, and the certificate's subject (default: module basename) |
| `--rig {auto,quiesced,portable}` | `quiesced` REFUSES to run without the verified host rig; `portable` accepts indicative timings knowingly |
| `--target-ms MS` | calibrate the driver knob so the reference lands near this. `0` disables calibration and measures your workload as written |
| `--preset {quick,standard,thorough}` | scales the routed search budget and the workload size together. Cannot change the oracle, the gate, or the emit margin |
| `--allow-fast-math` | opt in to `-ffast-math` candidates being **emitted**. Still oracle-checked; changes FP results |
| `--allow-fp-contract` | opt in to FMA contraction. Weaker than fast-math, still changes FP results — a separate axis, and separately consented |
| `--portable-flags` | restrict to `-march=x86-64`, so the emitted flags are safe on machines other than this one |
| `--probe-as-screen` | EXPERIMENTAL, off by default. Skip the second D-optimal screen and spend the whole budget on the walk. See §13.7 |
| `--wait` | queue behind another cytune measurement instead of refusing. See §13.6 |
| `--dry-run` | ingest + probe only: the landscape, the plan, and an estimated cost. Spends no tuning budget |
| `--explain` | after the verdict: why this route, this budget, this margin, and what would have to change for the answer to change |
| `--json` | the certificate as JSON on stdout; all narration to stderr |
| `--apply` | write the emitted header into `MODULE.tuned.pyx`. Refuses unless the verdict is an improvement whose gate was CLEAN |
| `--in-place` | with `--apply`, edit the module itself; a `.cytune-backup` is kept |
| `--config PATH` | use this `.cytune.toml` instead of the nearest one at or above the CWD |
| `--no-config` | ignore every `.cytune.toml`. Use this in scripts you want reproducible on someone else's machine |

`audit` takes `--driver`, `--workspace`, `--name`, `--wait`, `--json` with the same meanings.
`doctor` takes `--json` and `--build-image` (build the pinned image and verify its digest).
`init` takes `--driver PATH` (where to write it) and `--force` (overwrite an existing driver).

### 13.4 `.cytune.toml` keys and precedence

Ten keys, all under `[cytune]`: `workspace`, `rig`, `target_ms`, `allow_fast_math`,
`allow_fp_contract`, `portable_flags`, `probe_as_screen`, `preset`, `budget_scale`, `wait`.

Precedence, highest first:

1. **an explicitly passed flag** — always wins, including over a preset;
2. **`preset`** — but only over `budget_scale` and `target_ms`, the two things a preset is allowed
   to move;
3. **`.cytune.toml`**;
4. **the built-in default.**

The certificate records which file supplied the defaults, so a run is reproducible from the
document rather than from your shell history.

### 13.5 Exit codes

| code | meaning | is it an error? |
|---|---|---|
| `0` | `improvement` — a faster config was found, gated and certified. Also `--dry-run`'s success | no |
| `2` | `honest-flat` — no configuration is reliably faster than yours | **no**: a real answer |
| `3` | `no-safe-improvement` — headroom existed and could not be safely claimed. Read the REJECTED block | **no**: a real answer |
| `1` | error — bad arguments, a broken environment, a refused certificate, or a held measurement lock | yes |

In a script: `0`, `2` and `3` all mean cytune finished and stands behind its answer. Only `1` means
it could not.

### 13.6 The measurement lock

cytune takes a machine-wide lock for the whole of a `tune` or `audit` run. A second run refuses,
naming the holder, its workspace and how long it has been going. `--wait` queues instead.

This is not politeness. Two runs measuring at once produce **wrong numbers with no warning**: a
contended machine measures slower, and because config id order correlates with the `-O1`/`-O3`
factor, a time-correlated slowdown can alias onto a factor and look like a result. This project
discarded 626 measured rows to exactly that on 2026-07-24.

### 13.7 Why `--probe-as-screen` is off by default

**It is better on average and worse in the tail, and the tail is on kernels the live validation
set does not contain.**

Measured, five runs per arm on the nine real-code anchors: it improves median regret from 1.409 %
to 0.802 %, improves the worst anchor from 9.791 % to 2.664 %, measures exactly the same number of
configurations, and is *more stable* run to run. On that evidence alone it should be the default.

Then the fleet-wide replay — all 149 frozen kernels at nine budgets — says no. Nine kernels regress
past 5 percentage points, one by **+28.4 pp**, and the worst case at budget 64 goes from 5.9 % to
17.2 %. **None of the nine is a live anchor.** The affected kernels are mostly the interaction-heavy
`INT` class and some `MID` gather kernels, and the mechanism is visible: without the second screen
the walk's main-effect fit is seeded by the 17-point probe alone, which on those landscapes ranks
the space wrongly and the walk then follows that ranking all the way down.

So the second screen is insurance against a tail that a median hides and that nine anchors cannot
see. Keeping it is choosing a worse average for a better worst case, deliberately.

If your kernels look like the ones it helps — and the safest way to find that out is to run both
and compare — the flag is there. The full evidence is in `results/release/LAUNCH_REPORT.md`.
