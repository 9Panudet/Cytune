#!/usr/bin/env bash
# Parameterized corpus-unit build from the VENDORED CLOSURE under a SPECIFIED config
# (Step 1.2 per-unit campaign). Generalizes data/corpus/**/build_from_closure.sh (which
# pins one config) so a unit can be built at the GOLDEN reference config (-O2 -march=x86-64
# -ffp-contract=off) AND the crit-3/fastest config (-O3 -march=native -ffp-contract=off),
# both with the as-shipped sklearn Cython directive set, for the opt-invariance check and
# the worst-case-kernel-share criterion-3 profile.
#
# Cython directives default to the sklearn as-shipped meson set (the golden reference
# directive side, THETA_DIRECTIVE_POLICY.md / sklearn meson.build:184-185):
#   -X cdivision=True -X wraparound=False -X initializedcheck=False -X nonecheck=False -X boundscheck=False
# -ffp-contract is ALWAYS explicit (§3.2 item 3; GCC default is fast). No fast-math.
#
# Usage (in-container :phase1, closure mounted at /unit):
#   build_unit.sh <pyx_relpath> <mod_name> <out_so> <opt_flags> <ffp_contract> [language] [cython_dirs]
#     pyx_relpath  : path of the .pyx inside the closure (e.g. sklearn/utils/sparsefuncs_fast.pyx)
#     opt_flags    : e.g. "-O2 -march=x86-64"  or  "-O3 -march=native"   (NO -ffp-contract here)
#     ffp_contract : off | on | fast
#     language     : c (default) | c++
#     cython_dirs  : override the default directive string (optional)
set -uo pipefail
PYX="$1"; MOD="$2"; OUT="$3"; OPT_FLAGS="$4"; FFP="$5"
LANG_="${6:-c}"; CYDIRS="${7:--X cdivision=True -X wraparound=False -X initializedcheck=False -X nonecheck=False -X boundscheck=False}"

case "$FFP" in off|on|fast) ;; *) echo "build_unit: ffp_contract must be off|on|fast (got $FFP)"; exit 2;; esac
CLOSURE="${UNIT_CLOSURE:-/unit/closure}"
WORK=/tmp/cu_build; rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$CLOSURE" "$WORK/closure"; cd "$WORK/closure"

PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')

if [ "$LANG_" = "c++" ]; then CC=g++-13; CPLUS="--cplus"; STD="-std=c++14"; else CC=gcc-13; CPLUS=""; STD=""; fi
CSRC=/tmp/${MOD}.c; [ "$LANG_" = "c++" ] && CSRC=/tmp/${MOD}.cpp

echo "build_unit: $MOD  opt=[$OPT_FLAGS] ffp=$FFP lang=$LANG_"
echo "  cython dirs: $CYDIRS"
rm -f "$CSRC" "$OUT"
# shellcheck disable=SC2086
cython -3 $CPLUS $CYDIRS -I . "$PYX" -o "$CSRC" 2>&1 | grep -vE 'performance hint' | tail -6
[ -f "$CSRC" ] || { echo "CYTHONIZE FAILED (no source emitted) -> feasibility-0 for this combo"; exit 3; }

# shellcheck disable=SC2086
$CC -shared -fPIC $OPT_FLAGS -ffp-contract=$FFP $STD -g0 -pipe \
    -I"$PYINC" -I"$NPINC" "$CSRC" -o "$OUT" 2>&1 | tail -8
[ -f "$OUT" ] || { echo "COMPILE FAILED (no .so emitted)"; exit 4; }
echo "  -> $OUT  ($(stat -c%s "$OUT") bytes)  sha256=$(sha256sum "$OUT" | cut -c1-16)"
