# The container, the vendored rig, and the drift checks

## The image

`motifbo-env:phase1`, pinned **by content**: `rig.PINNED_IMAGE_DIGEST = "sha256:d45e33b0…"`. Every
published number was measured in this image. `rig.image_digest()` resolves the local id and never
raises; `doctor` reports a mismatch as BLOCKING, and `doctor --build-image` builds it and **verifies
the digest**, refusing if it differs.

A CLEAN sanitizer verdict from an unpinned image is recorded as **non-authoritative** rather than
rejected (path V-8): the verdict stands, `sanitizer_gate_authoritative` goes false, safety wording
is downgraded, and `--apply` refuses.

## Two mounts, and no more

`rig._mounts()`: the package read-only at `/opt/cytune/cytune`, and the workspace read-write at
`/work`. `--network=none` everywhere. Measurement containers additionally get
`<ws>/<name>/_so` **read-only**, so a measure phase cannot rewrite the artifact it is timing.

It used to also mount the repo's `scripts/` at `/probe` and `results/` at `/results`. Removing those
is what the one-way dependency rule *is*: the product no longer reaches into the study to run.

For a quiesced measure phase the whole `podman run` is prefixed by `bash scripts/measure_wrap.sh`,
which supplies its own `--cpuset-cpus=3 --memory=12g --memory-swap=12g --network=none` and injects
`RIG_FINGERPRINT`.

**`measure_wrap.sh` is deliberately NOT vendored.** Vendoring it broke it: it resolves a sibling
`scripts/thermal_log.sh` through `REPO_ROOT="$(dirname $0)/.."`, so the package copy died with
rc=127 mid-run. A pip-installed cytune therefore has no quiesced rig available and runs `portable`,
which is the honest outcome — the host asserts are about the *host*, and a wheel cannot carry them.

## `_vendor/` — the study's rig, copied and pinned

The product ships standalone, so the measurement machinery is copied in. The cost of a copy is
drift, in both directions: a bug fixed in the study and not the copy, or a copy "tidied" so the
product stops measuring the way every published number was measured.

Twelve files. Seven are **byte-identical** whole-file copies (`theta`, `build`, `seeds`,
`measure_child`, `san_child`, `classify`, `profiles`). Three are **trimmed** to what the product
reaches, with the kept functions pinned character-for-character (`campaign` 9 functions,
`algorithms` 3, `sanitizer_build` 1). One data file (`doe_designs_theta.json`). `__init__.py` is
product-authored packaging glue and is the only exemption.

### The manifest, and why it exists (B2)

Until the launch pass the drift check compared against `scripts/phasep/*` and called `pytest.skip`
when it was absent. On a product-only branch that is **every comparison, forever**: 12 of 14
collected items skipped, and the two that ran tested nothing about drift. This project named that
failure mode itself in D23 — *a check that never runs leaves no trace* — and had not pointed it at
the check.

`_vendor/VENDOR_MANIFEST.json` now ships 23 pins as data:

* **Tier 1** runs everywhere and cannot skip: `_vendor/*` against the manifest.
* **Tier 2** runs where the study tree exists: the manifest against the study source, so the
  manifest cannot drift from what it claims to represent either.

Anti-vacuity: `test_the_manifest_covers_every_vendored_module` fails if a new vendored file is
unpinned, and `test_tier_1_is_not_vacuous` fails if the manifest is empty or its counts disagree
with the mapping tables. On a product-only tree this took the vendor suite from 2 passing to 18.

### The constants pin, and the false claim it replaced

`sanitizer_build.py`'s docstring named a test that had been renamed away and an assertion on
`SAN_TOKENS` / `CORNERS` that existed **nowhere**. Those two constants decide what counts as an
AddressSanitizer report, so dropping a token would turn a real memory-safety report into a CLEAN
verdict with every drift test still green. They are now pinned **by value** — reformatting a literal
is not a false alarm, changing a token is — and the claim was made true rather than deleted.

Regenerate with `scripts/release/build_vendor_manifest.py`, and commit the manifest in the same
commit as the files it pins.
