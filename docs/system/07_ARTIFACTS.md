# Artifacts — what a run writes, and how to read it

## The workspace

```
<workspace>/                       default .cytune
  _kernels/<name>/                 the vendored copy of YOUR module + driver
  <name>/
    build_manifest.jsonl           one row per build: config id, rc, artifact sha256
    artifacts.jsonl                the built .so files and their hashes
    cache_key.json                 every input the cache keys on (I3.1/I3.2)
    oracle.json                    output class, tolerance, determinism, golden_sha256
    golden.npy                     the reference output every build is compared against
    table.jsonl                    ONE ROW PER MEASURED CONFIGURATION — the raw data
    certificate.json               the document
    certificate.txt                exactly what certificate.json renders to (I1.10)
    sanitizer_report_<id>.log      written only when the gate reported
    _so/  _ccache/                 build caches — safe to delete, 99% of the disk
```

`_so` and `_ccache` are ~71 MB per run; everything of evidentiary value is ~120 KB. The repeated
campaign prunes them after verifying the evidence files are present and non-empty, which is the D12
precedent applied per run.

## `table.jsonl` — the row that matters

One row per configuration cytune measured, carrying its `config_id`, feasibility (and the reason if
not), the screen-tier median, and the endpoint record where one exists. **If you doubt a verdict,
this is the file.** Everything in the certificate is derived from it.

## The four schemas

`schema.py` declares them; `evidence/schemas.json` (main branch) ships them.

| schema | written by |
|---|---|
| `cytune-certificate/…` | `cytune tune` |
| `cytune-audit/…` | `cytune audit` |
| `cytune-doctor/…` | `cytune doctor --json` |
| `cytune-dry-run/…` | `cytune tune --dry-run` (its `verdict` is `null`) |

**I1.9** asserts the emitted document honours its own published schema, so a consumer can rely on it.

## Reading a certificate

Top to bottom, and the order is the design:

* **WHAT TO DO** — one sentence, printed above the document (not part of it). Added because the
  document opens with a verdict token and a table, and a first-time user's real question is "so what
  do I do?"
* **VERDICT** — `IMPROVEMENT` / `HONEST-FLAT` / `NO-SAFE-IMPROVEMENT`, with the speedup where one is
  claimed.
* **the memory-safety block**, when the gate reported. It outranks everything below it.
* **EMIT** — the directive header and gcc flags, ready to paste.
* **OBSERVED BUT NOT RECOMMENDED** — a configuration that was measured and deliberately not
  recommended. On the flat route this is the best probe configuration, reported as an observation
  because the minimum of a noisy sample is biased low (D13).
* **WINNER REJECTED** — what was refused and why: sanitizer, endpoint, C1, or margin.
* **MEASURED SPEEDUP** — the endpoint arithmetic, including the margin computation.
* **CORRECTNESS CERTIFICATE** — output class, tolerance, determinism reps, golden hash, how many
  configurations were rejected as incorrect.
* **SANITIZER GATE (on the config being emitted)** — the verdict, and whether it ran.
* **ROUTING / RIG MODE / FLOATING-POINT CONSENT / PORTABILITY WARNING**.
* **PROVENANCE** — the emitted artifact sha256, the endpoint artifact sha256 (they must be equal),
  and the toolchain image digest.
* **WHAT THIS CERTIFICATE ATTESTS — AND WHAT IT DOES NOT.** Reads it. It volunteers its own trust
  boundary, including that it is evidence to whoever controls the driver and not to a third party.
* **GLOSSARY** — self-contained, so the document is readable without this repo.
