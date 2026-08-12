# Troubleshooting

Errors people actually hit, with the fix. Install and prerequisites are on the
[front page](../README.md).

---

## `cytune: command not found`

Either install the console script, or use the module form. Both work:

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -e .   # then: cytune ...
PYTHONPATH=src python3 -m cytune doctor                             # no install needed
```

`PYTHONPATH=src` is relative, so it only resolves **from the repository root** — and your kernel
lives somewhere else. From your own project directory, use the absolute path:

```bash
PYTHONPATH=/path/to/Motif+BO/src python3 -m cytune tune mykernel.pyx --driver driver.py
```

If your system Python has no `pip` (`No module named pip`), the venv route above still works —
`python3 -m venv` bootstraps its own pip. `cytune doctor` includes an **entry point** check that
tells you which state you are in.

---

## `cytune doctor` — reading the output

Seven checks, two tiers of failure:

| tier | marker | meaning |
|---|---|---|
| BLOCKING | `[FAIL]` | cytune cannot run at all; exit code 1 |
| DEGRADED | `[warn]` | it runs, but a specific guarantee is weaker **and the certificate will say so** |
| pass/info | `[ok  ]` | — |

| check | verifies | if it fails |
|---|---|---|
| `podman` | on PATH and reports a version | **BLOCKING.** Install podman. |
| `pinned image` | `localhost/motifbo-env:phase1` exists; prints its ID and whether it matches the reference | **BLOCKING.** `podman build -f Containerfile -t localhost/motifbo-env:phase1 .` |
| `sanitizer gate` | the ASan+UBSan gate can run | **DEGRADED.** Tuning continues but the emitted config is not memory-checked; the certificate records `NOT RUN`, which is not a pass. |
| `measurement rig` | `measure_wrap.sh` verifies the host asserts | **DEGRADED.** Falls back to portable; small speedups become indistinguishable from noise. `sudo scripts/host_prep.sh`. |
| `python` | host Python ≥ 3.9 | **BLOCKING.** The suite is run on CPython 3.9 – 3.14 before every release, so the bound is measured rather than assumed — see `KNOWN_ISSUES.md`, "the environments this release was actually run in". |
| `entry point` | `cytune` is on PATH | info only — the module form works regardless. |
| `workspace` | the workspace directory exists or can be created | **BLOCKING** if not writable. |

Exit `0` when nothing blocks, `1` otherwise. `cytune doctor --json` gives the same result
machine-readably.

---

## `[FAIL] pinned image ... is absent`

`doctor` now prints the exact command:

```bash
podman build -f Containerfile -t localhost/motifbo-env:phase1 .
```

Run it from the repository root. It needs network access and takes a few minutes. The
`Containerfile` pins its base image by digest and GCC by apt version. The reference image ID starts
`d45e33b08bad`; a different ID means your toolchain differs from the one every number in
`../results/` was measured on, and `doctor` will show the mismatch next to the ID.

---

## `cytune: your module did not compile`

```
cytune: your module did not compile — 17 of 17 configurations failed (cythonize_fail).

  first failure, config 0:
    kernel.pyx:2:31: Expected ':', found 'return'

  full build log: .cytune/<name>/build_failure.log
```

The run aborts at ingest and shows the compiler's own words plus the full log path. Common causes:
a syntax error in the `.pyx`, a `cimport` of a module not on the include path, or a typed-memoryview
declaration that does not match the dtype your driver produces.

A **partial** failure (`built 14/17`) is normal and not an error: those configs are recorded as
infeasible and the run continues.

---

## `cytune: bad arguments:`

```
cytune: bad arguments:
  module: /path/k.pyx does not exist
  --driver: /path/d.py does not exist (the directory /path does not exist either)
```

Both paths are checked **before** any directory is created, and each problem names which argument
it belongs to. Swapping the two is diagnosed specifically (`does not end in .pyx`). A run that fails
here leaves nothing behind in your working directory.

---

## `cytune: driver does not satisfy the measurement contract`

```
cytune: driver does not satisfy the measurement contract, missing: canon, OUTPUT_CLASS
  a cytune driver must define: make_inputs(seed) -> inputs, call(mod, inputs) -> result,
  canon(result) -> numpy array, and OUTPUT_CLASS in {float,int,bool}
  see docs/USER_GUIDE.md for a driver template you can copy
```

All four are required. `canon` must return a numpy array — wrap a scalar as
`np.asarray([x], dtype=...)`. `OUTPUT_CLASS` must be exactly `"float"`, `"int"` or `"bool"`.
Nothing is vendored into the workspace until the driver passes this check.

---

## `error: unrecognized arguments: --fast-math`

You get `cytune tune`'s usage, not the top-level one, so the real spelling is visible. It is
`--allow-fast-math`. `cytune tune --help` lists every flag and its default.

---

## `--rig quiesced was requested but the host is not quiesced`

`--rig quiesced` **requires** the quiesced rig and refuses rather than silently degrading. Either:

```bash
sudo scripts/host_prep.sh && cytune doctor    # measurement rig should read [ok]
```

or pass `--rig portable` to accept indicative timings. `--rig auto` (the default) picks whichever
is available and states which on the certificate.

---

## `unknown setting(s) under [cytune]`

A `.cytune.toml` key that cytune does not recognise is an error, not a warning — a typo'd
`allow_fastmath = true` that was silently ignored would leave you believing you had opted in. The
message lists the known settings. `--no-config` ignores the file entirely.

If you are on Python < 3.11 without `tomli`, only simple `key = value` lines parse; `pip install
tomli` for full TOML.

---

## The verdict says `NO-SAFE-IMPROVEMENT`

**This is not a failure.** It means a faster configuration existed and cytune refused it — read the
reason:

- **`WINNER REJECTED AT VERIFY ... sanitizer_report`** — the faster config reads memory it does not
  own. There will be a `!!!` block above the recommendation and a full report at
  `<workspace>/<name>/sanitizer_report_<id>.log`. This is a latent bug in **your** kernel that only
  manifests with `boundscheck`/`wraparound` off; your output check cannot see it because a
  reduction absorbs the garbage element. Fix the indexing before disabling those directives — by
  hand or otherwise.
- **`... oracle_mismatch`** — the faster config produced wrong output at the endpoint tier.
- **`EMIT: NOTHING`** — the sanitizer reported on the configuration that would have been emitted,
  i.e. on your own baseline. There is no configuration cytune can call safe. Fix the defect first.

---

## The certificate says `NOT RUN (IMAGE_UNAVAILABLE)`

The sanitizer gate could not run, so the recommendation is oracle-checked but **not**
memory-checked. The verdict summary says so too, and `--apply` will refuse. `cytune doctor` will
tell you why the image is unreachable. If `CYTUNE_SANITIZER_IMAGE` is set, unset it.

**Not-run is not a pass.**

---

## The probe said 2.65× and the certificate says 1.27×

Expected, and the certificate now explains it in a section called *WHY THE PROBE NUMBER AND THE
SPEEDUP DIFFER*. `delta_probe` is a screening-tier ratio over one fast measurement per config, and
its fastest member is a sample minimum, so it is biased low. The speedup is an endpoint-tier
median-of-3 at K=30 that had to clear the separation test and the emit margin. Trust the endpoint
number.

---

## Portable mode says my speedup is not an improvement

The emit margin is `max(2 × combined endpoint CV, 0.02)`. **It is computed from the noise THIS RUN
measured, not from the rig mode** — a quiesced rig usually bottoms out at the `tau = 0.02` floor,
but a quiesced host that is busy with something else will produce a much larger bar. A user whose
machine was running other work saw **0.2196** on a rig `doctor` called quiesced, and no document
prepared them for it. If the margin is far above 0.02, the certificate's `escalation` block will
also say the endpoint tier did not reach its CV target: that is the same story told twice, and the
answer is to re-run on an idle machine.

The figures below are what the acceptance runs happened to measure — examples, not properties of
the flag: 0.0200 on an idle quiesced rig, **0.0808** in
portable mode on the acceptance runs, because the measured noise was ~10× larger. By design:
portable mode reports *fewer* improvements, not noisier ones. Get the quiesced rig and re-run.
Correctness guarantees are identical in both modes.

---

## `--apply` refused

```
NOT APPLIED — refusing to apply: the §1.4 sanitizer gate on the emitted config is
IMAGE_UNAVAILABLE (clean=None), not CLEAN.
```

`--apply` writes checks-off directives into your source. It requires an `improvement` verdict whose
gate came back **CLEAN** — not merely "did not report". Fix the environment (`cytune doctor`) and
re-run, or apply the header by hand having read the certificate.

It also refuses on a non-improvement verdict, because the recommendation *is* your existing
configuration and applying it would change nothing.

---

## A run is taking minutes and printing nothing

It shouldn't any more — each stage prints elapsed time, and once the probe has measured a
per-config cost on your kernel the tune stage prints an estimate. Typical end-to-end on the
acceptance fixtures is **2–3.5 minutes**. Use `--dry-run` (~90 s) to see the landscape and a cost
estimate before committing to a full run.

The full container log is at `<workspace>/<name>.log`.

---

## Nothing here matches

- Raw per-config measurements: `<workspace>/<name>/table.jsonl`, one JSON object per config.
- Machine-readable certificate: `<workspace>/<name>/certificate.json`; rendered copy
  `certificate.txt`.
- Container transcript: `<workspace>/<name>.log`.
- Build failures: `<workspace>/<name>/build_failure.log`.
- Sanitizer reports: `<workspace>/<name>/sanitizer_report_<id>.log`.
- Open problems: [KNOWN_ISSUES.md](KNOWN_ISSUES.md).
