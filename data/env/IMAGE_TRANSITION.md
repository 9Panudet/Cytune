# Image transition X → X′ (Phase-0 → Phase-1) — Step 1.1.1

**Reason.** Phase-1 corpus curation (§4.3) includes **C++ Cython units** (sklearn
`tree/_tree`,`_splitter`,`_criterion`; `cluster/_dbscan_inner`,`_hierarchical_fast`). The
Phase-0 pinned image was built for **C** Cython only — it had **no C++ compiler** (`cc1plus`
absent, `libstdc++` headers absent, no `g++`). Without C++ the tree fold is unbuildable and the
corpus drops to 9 codebases < §4.1b's ≥10. Human decision (Option A): add the C++ toolchain as an
**additive** image layer.

## Transition

| | Image | ID | Tag |
|---|---|---|---|
| **X** (Phase 0) | pre-C++ | `sha256:3bbe69a1d8f8c3ec8ae7d6b19a0c586f4fe79b3b8f8925f7e1dee9adb6fb67d2` | `localhost/motifbo-env:phase0` (retained) |
| **X′** (Phase 1) | + C++ | `sha256:d45e33b08bad0020bcf0d04eefe50c04e7e1f36e3ccb4d55daf655e9900295d2` | `localhost/motifbo-env:phase1` (canonical) |

- **Base image pin UNCHANGED:** `ubuntu:24.04@sha256:023f8a75…` (data/env/IMAGE_DIGEST). The C++
  layer is appended **last** in the Containerfile, so every layer above (gcc/cc1/libc6-dev/libasan,
  python3.12, pip deps) stays cache-identical.
- **Additive only:** `podman build` reported `0 upgraded, 0 to remove, 3 newly installed`
  (`g++-13`, `g++-13-x86-64-linux-gnu`, `libstdc++-13-dev`, all `=13.3.0-6ubuntu2~24.04.1`,
  gcc-13-matched). No existing package upgraded or removed.
- **`:phase0` (X) is retained** for Phase-0 reproducibility. **No RQ1 / endpoint / measurement data
  predates X′** — the entire Phase-1 experiment (corpus builds, drivers, RQ1) runs on X′. X was used
  only for Phase-0 instrument validation (I-1, I-3 C rig, pilot), which remains valid on X and (by
  the byte-identity below) would be bit-identical on X′ for the C path.

## Condition-2 proof — C binaries byte-identical (X vs X′)

Recomputed fresh from BOTH images (`logs/env/STEP_1.1.1_cpp_toolchain.log`). Required: zero diff.

| binary | sha256 (X and X′ — identical) |
|---|---|
| `cc1` (`gcc-13 -print-prog-name=cc1`) | `5d1679131184e2de4435b426eb264bf13472fe026db8e5c6bc97445814e8e2f4` |
| `gcc-13` (`/usr/bin/gcc-13`) | `1b99826121ae6682a634e5efe09bd3e3df58ce58e0b28f849114ab5b89139c26` |
| `libasan.so.8.0.0` | `8d5845bdf056b5db4cfb9fff40ad5eeea8f6da05a8ca6f5935a7d1c138ed2558` |
| `python3.12` | `e1efa562c2cc2e35521a5c9c9b9939921001ff8ca9708a13ef15ace68cc2ccd7` |

**VERDICT: byte-identical** — Phase-0 reproducibility undisturbed. (`cc1`/`libasan`/`python3.12`
also match the prior validation-auditor digests recorded at the E close, `results/audit/0.P-E-resign/`.)

**New in X′ (C++ backend):** `cc1plus` sha256 `840b332fb62ec6f694ac77d91fe69ef7f80b0d69512ed89374af0ee7a506255d`,
`g++-13 (Ubuntu 13.3.0-6ubuntu2~24.04.1)`. Re-pin recorded in TOOLCHAIN.lock (`[apt-pinned-cpp]`,
`image_id_1.1.1`, `image_tag=…:phase1`); asserted by `scripts/check_toolchain.sh`.

## Gating not yet satisfied (C++ units do NOT count until done)

- **Condition 3 (mini-I-3 C++ extension):** extend ASan/UBSan suppressions for libstdc++ allocation +
  exception unwinding (each line justified, validation-auditor reviewed); confirm the oracle handles
  C++ exception-identity (§3.1). Until this passes, no C++ unit enters the corpus.
- **Condition 4:** per-unit standalone-build confirmation for every C-classified unit (no
  generalizing from the one proven build).
