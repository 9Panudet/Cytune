# GCC_SEMANTICS — verified FP/optimization semantics of the pinned GCC (Step 0.1.5)

**Toolchain:** gcc 13.3.0 (Ubuntu `13.3.0-6ubuntu2~24.04.1`), image `f9328a8a92f8…`
(see `TOOLCHAIN.lock`). **Sources:** the pinned package's own man page (extracted from the
exact pinned .debs; `gcc-13` man1 is a symlink into `gcc-13-x86-64-linux-gnu`, same
version) + `gcc -Q --help=optimizers/common` state dumps + macro dumps + codegen +
linker `-###` dumps + the MXCSR dlopen probe. **Raw evidence:** `/logs/env/step_0.1.5/`
(committed). **Recompute:** `podman run --rm -v ./scripts:/probe:ro,Z -v ./logs/env:/out:Z
localhost/motifbo-env:phase0 bash /probe/gcc_semantics_probe.sh`. Date: 2026-06-11.

## F1 — `-ffast-math` sub-flag composition: §3.2 set CONFIRMED

Manual (man lines 11789–11801): sets `-fno-math-errno, -funsafe-math-optimizations,
-ffinite-math-only, -fno-rounding-math, -fno-signaling-nans, -fcx-limited-range,
-fexcess-precision=fast`; defines `__FAST_MATH__`; "not turned on by any -O option
besides -Ofast".

Behavior (`diff_opt_default_vs_ffastmath.txt`, `diff_common_default_vs_ffastmath.txt`):
flips exactly math-errno→off, unsafe-math-optimizations→on, finite-math-only→on,
cx-limited-range→on, excess-precision→fast, plus the transitive F3 set
(associative/reciprocal on, signed-zeros/trapping off). `-frounding-math` and
`-fsignaling-nans` are already `[disabled]` at default and stay disabled
(no-ops relative to defaults — why they produce no diff line).

## F2 — `__FAST_MATH__`: defined by `-ffast-math` and `-Ofast` only

`fast_math_macro_where.txt`: present in `macros_ffastmath.txt` and `macros_Ofast.txt`;
absent at default and `-O3`. The full macro footprint of `-ffast-math`
(`diff_macros_default_vs_ffastmath.txt`) additionally sets `__ASSOCIATIVE_MATH__`,
`__RECIPROCAL_MATH__`, `__NO_MATH_ERRNO__`, `__NO_SIGNED_ZEROS__`,
`__NO_TRAPPING_MATH__`, `__FINITE_MATH_ONLY__ 1`, and downgrades `__GCC_IEC_559` 2→0,
dropping the `__STDC_IEC_559__*` conformance macros.

## F3 — `-funsafe-math-optimizations` transitive set: CONFIRMED

Manual (11821–11834): "Enables -fno-signed-zeros, -fno-trapping-math, -fassociative-math
and -freciprocal-math" and, at link time, "may include libraries or startup files that
change the default FPU control word" (the crtfastmath mechanism, F7).
Behavior (`diff_opt_default_vs_unsafe.txt`): flips exactly those four + itself.

## F4 — `-Ofast` composition

Manual (9643–9649): "all -O3 optimizations… turns on -ffast-math,
-fallow-store-data-races and the Fortran-specific -fstack-arrays… and
-fno-protect-parens. It turns off -fsemantic-interposition."
Behavior (`diff_opt_O3_vs_Ofast.txt`): O3→Ofast flips the full fast-math set (F1/F3) +
`-fallow-store-data-races`→enabled + `-fsemantic-interposition`→disabled. The
semantic-interposition detail goes beyond §3.2's summary and is recorded here.

## F5 — `-Ofast` deprecation status: NOT deprecated on the pinned GCC (resolves §0.7 item 9)

- Manual: no deprecation wording anywhere in the `-Ofast` entry; the only "deprecat"
  hits in the entire rendered man page are unrelated warning-option names and the
  `c9x`/`iso9899:199x` naming note.
- Compiler: `-Ofast` compile+link emits zero diagnostics (`ofast_diagnostics.txt`).

**Resolution recorded:** on GCC 13.3.0 (the pinned toolchain), `-Ofast` is not
deprecated. Scope: this statement is about the pin; GCC 14+ was not assessed and is
irrelevant while the pin holds. Unchanged regardless: `-Ofast` is excluded as a search
dimension (§2.3 design note) — Θ composes -O3/fast-math explicitly instead.

## F6 — `-ffp-contract`: default is `fast`; never infer state from `-Q` under ISO dialects

- Manual (9703–9712): "The default is -ffp-contract=fast." Also: `=on` is "currently not
  implemented and treated equal to -ffp-contract=off". Confirms §0.7 item 1.
- `-Q` reports `fast` under default, `-std=c17`, `-std=gnu17`, `-O2`, `-Ofast`
  (`ffp_contract_states.txt`) — **but codegen disagrees for ISO dialects**
  (`fma_emission_summary.txt`, `-O2 -mfma` on `a*b+c`):
  default(gnu dialect) → 1 fmadd; `-ffp-contract=fast` → 1; `-ffp-contract=off` → 0;
  **`-std=c17` (no explicit flag) → 0 fmadd** despite `-Q` showing `fast`.
- Consequences: (a) the GNU-dialect default truly contracts (§0.7-1 correction stands);
  (b) `gcc -Q --help` is NOT a reliable oracle for effective contraction under ISO
  dialects — the project rule "pass `-ffp-contract` explicitly on every build" (§3.2(3),
  CLAUDE.md) is hereby re-grounded twice over. The probe compiles that measured the
  default deliberately omitted the flag; that is the only sanctioned exception.

## F7 — FTZ/DAZ & crtfastmath.o: empirical containment boundaries (grounds §3.2(2))

Linker evidence (`crtfastmath_linkage_summary.txt`, `link_cmd_*.txt`):
- fast-math **executable** link: `crtfastmath.o` present (1 mention in collect2 line).
- fast-math **shared-object** (`-shared`) link: `crtfastmath.o` ABSENT (0 mentions).

MXCSR probe (probe sources `scripts/mxcsr/`; outputs `mxcsr_*.txt`):
- IEEE executable + dlopen(fast-math `.so`): control word **unchanged** — FTZ=0, DAZ=0
  before and after; subnormal 5e-324*2 preserved (gradual underflow). The observed
  0x1f80→0x1f82→0x1fa2 progression is sticky *status* flags (DE, PE) set by the probe's
  own arithmetic — not control bits. Identical to the plain-`.so` control.
- fast-math **executable**: starts at MXCSR=0x9fc0 → **FTZ=1, DAZ=1**; 5e-324*2 = 0
  (subnormals flushed) — crtfastmath.o's constructor ran at process startup.

**Finding:** on the pinned GCC 13.3.0, the documented "can link crtfastmath.o …
process-wide" contamination (§3.2) is real for *executables* but does NOT occur via
dlopen of candidate `.so`s (GCC 13 stopped linking crtfastmath.o into shared objects).
**The §3.2(2) fresh-subprocess rule stands as mandatory defense in depth:** it also
covers fast-math-linked helper executables, any library calling `_mm_setcsr`, FP-status
pollution (sticky flags do propagate, as measured), and toolchain drift; the empirical
boundary above is a property of this pin, not a guarantee of the policy.

## Raw-file index (all under /logs/env/step_0.1.5/, committed)

`opt_*.txt` / `common_*.txt` (state dumps per option set), `diff_*` (the four diffs),
`ffastmath_state_by_level.txt`, `ffp_contract_states.txt`, `macros_*.txt` +
`diff_macros_default_vs_ffastmath.txt`, `fast_math_macro_where.txt`, `fma_*.s` +
`fma_emission_summary.txt`, `ofast_diagnostics.txt`, `link_cmd_*.txt` +
`crtfastmath_linkage_summary.txt`, `mxcsr_*.txt`, `gcc-13.man.{troff,txt}`,
`man_contents.txt`.
