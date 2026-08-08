# Compatibility promise — cytune 1.x

What you may build against, and what may move under you. This page is the human-readable copy of
`src/cytune/schema.py`; `test_cytune_api.py` enforces it.

---

## The promise

Within the `1.x` series:

- **A field that exists in 1.0 still exists**, with the same type and the same meaning, in every
  later 1.x release.
- **New fields may be added.** A consumer must ignore keys it does not recognise. cytune's own
  validator does, deliberately — a contract test that rejected added fields would fail on every
  release that honoured the promise.
- **Exit codes do not change meaning.**
- **Flag names are not repurposed.** A flag that exists keeps its spelling and its sense.
- **A deprecation warns for at least one minor release** before anything is removed, and removal
  waits for 2.0.

What is explicitly *not* promised: the **wording** of prose fields (`summary`, `note`,
`explanation`, the glossary text), the exact set of configs a search visits, and any measured
number. Those are outputs, not interfaces. Branch on `verdict` and `exit_code`, not on English.

---

## The four public artifacts

| schema | produced by | also written to |
|---|---|---|
| `cytune-certificate/1.0` | `cytune tune --json` | `<workspace>/<name>/certificate.json` |
| `cytune-dry-run/1.0` | `cytune tune --dry-run --json` | — |
| `cytune-audit/1.0` | `cytune audit --json` | `<workspace>/<name>/audit.json` |
| `cytune-doctor/1.0` | `cytune doctor --json` | — |

Every document carries `schema` and `cytune_version`. **Check `schema` before parsing** — it is the
first field, and an unknown value means a version you were not written against.

With `--json`, **stdout carries the document and nothing else**; all narration goes to stderr.

---

## Exit codes

One table, for every subcommand.

| code | meaning | which commands |
|---|---|---|
| `0` | **improvement** — a measured, endpoint-verified, sanitizer-clean speedup | `tune` |
| `0` | **clean** — nothing in the risk set reported | `audit` |
| `0` | dry run completed; **no verdict was produced** | `tune --dry-run` |
| `0` | environment OK | `doctor` |
| `1` | **error** — cytune could not answer: bad arguments, build failure, no image, incomplete audit | all |
| `2` | **honest-flat** — no speedup worth acting on. A real answer, not a failure | `tune` |
| `3` | **no-safe-improvement** — a faster config existed and was **refused** | `tune` |
| `3` | **defects-found** — the sanitizer reported on at least one audited config | `audit` |

Two rules that make this scriptable:

- **`0`, `2` and `3` are all successful runs.** The tool answered. Only `1` means it could not.
- **A usage error never collides with a verdict.** argparse exits `2` by default, which would have
  made `$? -eq 2` mean either "no speedup worth having" or "you typed the flag wrong". cytune
  overrides it to `1` (`test_a_usage_error_can_never_collide_with_a_verdict_code`).

A dry run does **not** borrow a verdict's code. It returns `0` because it completed, and its
document sets `"verdict": null`. Branching on `$?` after `--dry-run` and treating `0` as "safe to
use" was finding R3 — check `dry_run` in the JSON, or do not use `--dry-run` in a decision script.

```bash
cytune tune k.pyx --driver d.py
case $? in
  0) echo "verified speedup — paste the emitted header" ;;
  2) echo "no worthwhile speedup; keep your current config" ;;
  3) echo "REFUSED — read the certificate before shipping anything" ; exit 1 ;;
  *) echo "cytune could not answer" ; exit 1 ;;
esac
```

---

## Fields you can rely on

The full specification is `src/cytune/schema.py`. The load-bearing ones:

**`cytune-certificate/1.0`**

| field | type | meaning |
|---|---|---|
| `verdict` | `"improvement"` \| `"honest-flat"` \| `"no-safe-improvement"` | the answer |
| `exit_code` | int | always agrees with `verdict` (invariant I1.1) |
| `emitted_config` | object \| null | `config_id`, `factors`, `directive_header`, `cython_x_flags`, `gcc_flags` |
| `emitted_config.gcc_flags` | str | **ground truth for FP semantics.** `-ffp-contract` is always explicit |
| `speedup` | number \| null | endpoint-tier ratio; claimed only when `verdict == "improvement"` |
| `sanitizer_gate.clean` | `true` \| `false` \| **`null`** | `null` is **not** a pass |
| `sanitizer_gate_ran` | bool | false whenever `clean` is null |
| `emitted_config_unsafe` | bool | the gate reported on the emitted config |
| `emission_policy` | object | the FP consent this run was given |
| `fp_semantics` | object | always agrees with `gcc_flags`, including fast-math implying contraction |
| `measurement.rig_mode` | `"quiesced"` \| `"portable"` | portable timings are indicative only |

**`cytune-audit/1.0`** — `verdict` is `"clean"` / `"defects-found"` / `"incomplete"`;
`directive_verdicts` maps each directive to `"safe to disable"` / `"UNSAFE to disable"` /
`"unknown (the gate did not run)"`; each row in `results` carries an `outcome` of `clean`,
`reported`, `raised`, `not-run` or `build-fail`.

---

## Three things a consumer should never do

1. **Treat `sanitizer_gate.clean == null` as a pass.** It means the gate could not run. The
   certificate says so in words too, and `--apply` refuses.
2. **Read `fp_semantics` instead of `gcc_flags`.** They agree — invariant I1.3 enforces it — but
   the flags are what your compiler sees. (They disagreed once: finding R2.)
3. **Parse the prose.** `summary` wording is not part of the contract.

---

## Version numbers

`cytune.__version__` is the single source; the CLI banner, `--version`, `doctor` and every artifact
read it, and a test asserts they agree. `pyproject.toml` derives its version from the same constant
rather than repeating it — a literal there drifted within one release.

`1.0.0` freezes the **interface**. It does not claim the study behind the routing policy is
complete; the "research preview" label describes the evidence and stays until the evidence changes.
See `GUARANTEES.md` N5.
