#!/bin/bash
# Step 0.1.5 in-container probe (run inside the pinned image; /probe = scripts ro,
# /out = logs/env rw). Produces every raw artifact behind data/env/GCC_SEMANTICS.md.
set -euo pipefail
OUT=/out/step_0.1.5
PINNED_PKG_VER="13.3.0-6ubuntu2~24.04.1"
mkdir -p "$OUT"

# Guard: this evidence is only valid for the pinned toolchain.
[ "$(gcc -dumpfullversion)" = "13.3.0" ] || { echo "wrong gcc"; exit 1; }
[ "$(dpkg-query -W -f '${Version}' gcc-13)" = "$PINNED_PKG_VER" ] || { echo "wrong gcc-13 pkg"; exit 1; }

# ---- A. Flag-state dumps (gcc -Q --help=...) under each relevant option set ----
dump() { # name flags...
  local name="$1"; shift
  gcc "$@" -Q --help=optimizers > "$OUT/opt_$name.txt" 2> "$OUT/opt_$name.stderr" || true
  gcc "$@" -Q --help=common    > "$OUT/common_$name.txt" 2>/dev/null || true
}
dump default
dump O0 -O0
dump O1 -O1
dump O2 -O2
dump O3 -O3
dump Os -Os
dump Ofast -Ofast
dump ffastmath -ffast-math
dump unsafe -funsafe-math-optimizations
dump c17 -std=c17
dump gnu17 -std=gnu17

diff "$OUT/opt_default.txt" "$OUT/opt_ffastmath.txt" > "$OUT/diff_opt_default_vs_ffastmath.txt" || true
diff "$OUT/common_default.txt" "$OUT/common_ffastmath.txt" > "$OUT/diff_common_default_vs_ffastmath.txt" || true
diff "$OUT/opt_default.txt" "$OUT/opt_unsafe.txt" > "$OUT/diff_opt_default_vs_unsafe.txt" || true
diff "$OUT/opt_O3.txt" "$OUT/opt_Ofast.txt" > "$OUT/diff_opt_O3_vs_Ofast.txt" || true
diff "$OUT/common_O3.txt" "$OUT/common_Ofast.txt" > "$OUT/diff_common_O3_vs_Ofast.txt" || true

{ for lvl in O0 O1 O2 O3 Os Ofast default; do
    printf '%-8s %s\n' "$lvl" "$(grep -E '^\s+-ffast-math\b' "$OUT/opt_$lvl.txt" | tr -s ' ')"
  done; } > "$OUT/ffastmath_state_by_level.txt"

{ for n in default c17 gnu17 O2 Ofast; do
    printf '%-8s %s\n' "$n" "$(grep -E '^\s+-ffp-contract=' "$OUT/opt_$n.txt" | tr -s ' ')"
  done; } > "$OUT/ffp_contract_states.txt"

# ---- B. Predefined macros ----
mac() { echo | gcc "$@" -dM -E - | sort; }
mac                > "$OUT/macros_default.txt"
mac -ffast-math    > "$OUT/macros_ffastmath.txt"
mac -O3            > "$OUT/macros_O3.txt"
mac -Ofast         > "$OUT/macros_Ofast.txt" 2> "$OUT/macros_Ofast.stderr" || true
diff "$OUT/macros_default.txt" "$OUT/macros_ffastmath.txt" > "$OUT/diff_macros_default_vs_ffastmath.txt" || true
grep -l __FAST_MATH__ "$OUT"/macros_*.txt | sed 's#.*/##' > "$OUT/fast_math_macro_where.txt" || true

# ---- C. Contraction codegen (FMA emission). The 'default' compile deliberately
# omits -ffp-contract: measuring the default IS this experiment. ----
printf 'double f(double a,double b,double c){return a*b+c;}\n' > /tmp/fma.c
gcc -O2 -mfma -S -o "$OUT/fma_default.s" /tmp/fma.c
gcc -O2 -mfma -std=c17 -S -o "$OUT/fma_c17.s" /tmp/fma.c
gcc -O2 -mfma -ffp-contract=off -S -o "$OUT/fma_contract_off.s" /tmp/fma.c
gcc -O2 -mfma -ffp-contract=fast -S -o "$OUT/fma_contract_fast.s" /tmp/fma.c
{ for f in fma_default fma_c17 fma_contract_off fma_contract_fast; do
    printf '%-18s fmadd_count=%s\n' "$f" "$(grep -c 'fmadd' "$OUT/$f.s" || true)"
  done; } > "$OUT/fma_emission_summary.txt"

# ---- D. -Ofast diagnostics on the pinned 13.3 (deprecation status, §0.7 item 9) ----
printf 'int main(void){return 0;}\n' > /tmp/triv.c
gcc -Ofast -ffp-contract=fast -o /tmp/triv /tmp/triv.c 2> "$OUT/ofast_diagnostics.txt" || true
gcc -Ofast -ffp-contract=fast -c -o /tmp/triv.o /tmp/triv.c 2>> "$OUT/ofast_diagnostics.txt" || true
[ -s "$OUT/ofast_diagnostics.txt" ] || echo "(no diagnostics emitted by gcc 13.3.0 for -Ofast)" > "$OUT/ofast_diagnostics.txt"

# ---- E. crtfastmath.o linkage: executable vs shared object ----
gcc -ffast-math -ffp-contract=fast -### -o /tmp/exe /tmp/triv.c 2> "$OUT/link_cmd_exe_fastmath.txt" || true
gcc -shared -fPIC -ffast-math -ffp-contract=fast -### -o /tmp/x.so /tmp/fma.c 2> "$OUT/link_cmd_shared_fastmath.txt" || true
{ printf 'executable link: crtfastmath mentions = %s\n' "$(grep -c crtfastmath "$OUT/link_cmd_exe_fastmath.txt" || true)"
  printf 'shared-obj link: crtfastmath mentions = %s\n' "$(grep -c crtfastmath "$OUT/link_cmd_shared_fastmath.txt" || true)"
} > "$OUT/crtfastmath_linkage_summary.txt"

# ---- F. MXCSR probe (the mandated empirical evidence) ----
gcc -O2 -ffast-math -ffp-contract=fast -shared -fPIC -o /tmp/fastmath_kernel.so /probe/mxcsr/fastmath_kernel.c
gcc -O2 -ffp-contract=off -shared -fPIC -o /tmp/plain_kernel.so /probe/mxcsr/fastmath_kernel.c
gcc -O2 -ffp-contract=off -o /tmp/probe /probe/mxcsr/probe.c
gcc -O2 -ffast-math -ffp-contract=fast -o /tmp/probe_fast /probe/mxcsr/probe.c
/tmp/probe /tmp/plain_kernel.so      > "$OUT/mxcsr_ieee_exe_plain_so.txt"
/tmp/probe /tmp/fastmath_kernel.so   > "$OUT/mxcsr_ieee_exe_fastmath_so.txt"
/tmp/probe_fast /tmp/plain_kernel.so > "$OUT/mxcsr_fastmath_exe.txt"

# ---- G. The pinned GCC's own manual (extracted from the exact pinned .debs) ----
# gcc-13's man1/gcc-13.1.gz is a symlink to x86_64-linux-gnu-gcc-13.1.gz, which ships
# in gcc-13-x86-64-linux-gnu (same pinned src version) — extract both into one root.
apt-get update -qq
( cd /tmp && apt-get download -y "gcc-13=$PINNED_PKG_VER" \
    "gcc-13-x86-64-linux-gnu=$PINNED_PKG_VER" >/dev/null 2>&1 )
dpkg -x /tmp/gcc-13_*.deb /tmp/gx
dpkg -x /tmp/gcc-13-x86-64-linux-gnu_*.deb /tmp/gx
ls -l /tmp/gx/usr/share/man/man1/ > "$OUT/man_contents.txt" 2>&1 || true
MAN_GZ=/tmp/gx/usr/share/man/man1/gcc-13.1.gz
if [ -r "$MAN_GZ" ]; then
  zcat "$MAN_GZ" > "$OUT/gcc-13.man.troff"
  if apt-get install -y -qq --no-install-recommends groff-base >/dev/null 2>&1; then
    groff -man -Tutf8 "$OUT/gcc-13.man.troff" 2>/dev/null \
      | python3 -c 'import re,sys;t=sys.stdin.read();t=re.sub("\x1b\\[[0-9;]*m","",t);t=re.sub(".\x08","",t);sys.stdout.write(t)' \
      > "$OUT/gcc-13.man.txt" || echo "groff render failed" > "$OUT/man_render_note.txt"
  else
    echo "groff-base unavailable; raw troff only" > "$OUT/man_render_note.txt"
  fi
else
  echo "gcc-13.1.gz not found in pinned .deb" > "$OUT/man_render_note.txt"
fi

echo "PROBE COMPLETE"
ls -1 "$OUT" | sed 's/^/  /'
