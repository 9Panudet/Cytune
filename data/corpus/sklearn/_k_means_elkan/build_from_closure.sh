#!/bin/bash
# Step 1.1.1 — VENDORED-CLOSURE build-confirm for sklearn.cluster._k_means_elkan.
#
# BUILD-CONFIRM = STANDALONE IMPORT (§4): the unit counts ONLY if sklearn.cluster._k_means_elkan
# standalone-IMPORTs from its vendored closure in X' (full cimport + runtime-import cascade).
# cythonize-OK / compile-OK do NOT count.
#
# Closure (resolved from the sdist .pyx/.pxd, NOT from installed sklearn):
#   sklearn/cluster/_k_means_elkan.pyx   - the unit
#   sklearn/cluster/_k_means_common.{pyx,pxd} - cimported cdef/cpdef kernels -> .so CO-BUILT first
#   sklearn/utils/_openmp_helpers.pxd    - `cdef extern from *` omp_* decls -> link-time (libgomp), NO .so
#   sklearn/utils/extmath.py             - FAITHFUL minimal row_norms helper stub (rule 5; runtime import)
#   sklearn/{,cluster/,utils/}__init__.py - empty pkg markers (NOT upstream __init__)
#
# Reference directives (sklearn, as-shipped):
#   -X language_level=3 -X boundscheck=False -X wraparound=False -X initializedcheck=False
#   -X nonecheck=False -X cdivision=True
# Compile (C): gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp
#
# Run in-container X' (:phase1):
#   podman run --rm -v <unit_dir>:/unit:ro,Z localhost/motifbo-env:phase1 bash /unit/build_from_closure.sh
#
# NEGATIVE CONTROL: with the vendored _k_means_common.pxd hidden the build MUST fail (proves the
# cimport resolves against the VENDORED closure, not installed sklearn).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK=/tmp/kme_build
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$HERE/closure" "$WORK/closure"      # copy ONLY the vendored closure into scratch
cd "$WORK/closure"
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')

XDIRS="-X language_level=3 -X boundscheck=False -X wraparound=False -X initializedcheck=False -X nonecheck=False -X cdivision=True"
GCC="gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp -I$PYINC -I$NPINC"

echo "tools: $(python3 --version 2>&1) | $(gcc-13 --version|head -1) | Cython $(python3 -c 'import Cython;print(Cython.__version__)') | numpy $(python3 -c 'import numpy;print(numpy.__version__)')"
echo "installed sklearn (must be IRRELEVANT to this build): $(python3 -c 'import sklearn;print(sklearn.__version__, sklearn.__file__)' 2>&1)"

# build_one PYX_RELPATH MODNAME LABEL  -> emits the .so IN PLACE next to the .pyx (so package import finds it)
build_one () {
  local pyx="$1" mod="$2" label="$3" cbase
  cbase="${pyx%.pyx}"
  rm -f "$cbase.c" "$cbase"*.so
  echo "--- cythonize $mod ($label) ---"
  cython -3 $XDIRS -I . "$pyx" -o "$cbase.c" 2>&1 | grep -vE 'performance hint' | tail -8
  [ -f "$cbase.c" ] || { echo "[$label] CYTHONIZE FAILED for $mod (no .c)"; return 3; }
  echo "--- compile $mod ($label) ---"
  $GCC "$cbase.c" -o "$cbase.cpython.so" 2>&1 | tail -12
  [ -f "$cbase.cpython.so" ] || { echo "[$label] COMPILE FAILED for $mod (no .so)"; return 4; }
  # name the .so so CPython's import machinery loads it as <mod> inside the package
  mv "$cbase.cpython.so" "${cbase}.so"
  echo "[$label] $mod .so bytes: $(stat -c%s ${cbase}.so)"
  return 0
}

build_closure () {  # $1 = label ; build dep first, then the unit, in dep order
  build_one sklearn/cluster/_k_means_common.pyx _k_means_common "$1" || return $?
  build_one sklearn/cluster/_k_means_elkan.pyx  _k_means_elkan  "$1" || return $?
  return 0
}

echo
echo "=== (1) POSITIVE: build the full runtime .so closure from the vendored closure ==="
if build_closure positive; then
  echo "--- STANDALONE IMPORT (binding §4 build-confirm; package import; OMP_NUM_THREADS=1) ---"
  OMP_NUM_THREADS=1 PYTHONPATH="$WORK/closure" python3 -c "
import importlib
m = importlib.import_module('sklearn.cluster._k_means_elkan')
fns=[x for x in dir(m) if not x.startswith('__')]
print('exported:', fns)
assert 'elkan_iter_chunked_dense' in fns and 'elkan_iter_chunked_sparse' in fns
assert 'init_bounds_dense' in fns and 'init_bounds_sparse' in fns
print('IMPORT-OK sklearn.cluster._k_means_elkan')
" || { echo "IMPORT FAILED"; exit 5; }
else
  echo "POSITIVE BUILD FAILED — vendored closure is incomplete"; exit 1
fi

echo
echo "=== (2) NEGATIVE CONTROL: hide the vendored _k_means_common.pxd -> build MUST fail ==="
echo "    (proves the cimport resolves from the VENDORED closure, not installed sklearn)"
# clean prior artifacts so cython is forced to re-resolve the cimport
rm -f sklearn/cluster/_k_means_common.c sklearn/cluster/_k_means_common.so sklearn/cluster/_k_means_elkan.c sklearn/cluster/_k_means_elkan.so
mv sklearn/cluster/_k_means_common.pxd /tmp/_k_means_common.pxd.hidden
if build_closure negative-control; then
  echo "!!! NEGATIVE CONTROL FAILED: build SUCCEEDED without the vendored _k_means_common.pxd"
  mv /tmp/_k_means_common.pxd.hidden sklearn/cluster/_k_means_common.pxd
  exit 6
else
  echo "NEGATIVE CONTROL PASSED: build fails without the vendored _k_means_common.pxd (closure is the real source)."
fi
mv /tmp/_k_means_common.pxd.hidden sklearn/cluster/_k_means_common.pxd

echo
echo "=== VENDORED-CLOSURE BUILD-CONFIRM: PASS (positive build+STANDALONE-IMPORT OK; negative control fails as required) ==="
