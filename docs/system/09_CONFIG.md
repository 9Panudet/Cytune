# Configuration — precedence and provenance

Ten keys, all under `[cytune]` in `.cytune.toml` (`config.FIELDS`):

| key | type | default |
|---|---|---|
| `workspace` | str | `.cytune` |
| `rig` | str | `auto` |
| `target_ms` | float | `65.0` |
| `allow_fast_math` | bool | `false` |
| `allow_fp_contract` | bool | `false` |
| `portable_flags` | bool | `false` |
| `probe_as_screen` | bool | `false` |
| `preset` | str | — |
| `budget_scale` | float | `1.0` |
| `wait` | bool | `false` |

## Precedence, highest first

1. **an explicitly passed flag** — always wins, including over a preset;
2. **`preset`** — but only over `budget_scale` and `target_ms` (`config.PRESET_SETTABLE`);
3. **`.cytune.toml`**;
4. **the built-in default**.

`config.resolve()` implements it, and knows which options were *explicitly* passed rather than
merely present with their default — which is the whole reason rule 1 can be honoured.

## Why a preset may move only two things

`PRESET_SETTABLE = {"budget_scale", "target_ms"}`. A preset scales **how much searching** and **how
big the workload is**. It cannot touch the oracle, the sanitizer gate, or the emit margin.

That restriction is deliberate and is the same rule as G5: *no flag can loosen G1, G2 or G3*. A
`--preset thorough` that quietly relaxed the emit margin would make the presets a back door into the
guarantees.

| preset | budget_scale | target_ms |
|---|---|---|
| `quick` | 0.5 | 30 |
| `standard` | 1.0 | 65 |
| `thorough` | 2.0 | 65 |

## Provenance

The certificate records **which file supplied the defaults**, so a run is reproducible from the
document rather than from your shell history. `--no-config` ignores every `.cytune.toml` — use it in
scripts you want to behave the same on someone else's machine.

`cytune init` writes a `.cytune.toml` alongside the driver. Note it is written whether or not you
asked; `init --help` documents `--driver` and `--force` only, which a first-time tester flagged as a
gap.
