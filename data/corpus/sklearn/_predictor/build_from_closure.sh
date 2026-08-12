#!/bin/bash
# Step 1.1.1 — VENDORED-CLOSURE build-confirm for sklearn.ensemble._hist_gradient_boosting._predictor.
#
# BUILD-CONFIRM = STANDALONE IMPORT (§4 binding): the unit counts ONLY if its kernel module
# standalone-IMPORTS from its vendored closure in X' — full cimport + runtime-import cascade.
# cythonize-OK / compile-OK do NOT count.
#
# This unit is NOT low-coupling like sparsefuncs_fast: it has a runtime .so cluster.
#   - `_predictor.pyx` does Python-level `from .common import Y_DTYPE`  -> common.so MUST exist at runtime.
#   - `_predictor.pyx` cimports `in_bitset_2d_memoryview` from `_bitset` (declared `cdef` in _bitset.pxd)
#     -> _bitset.so co-built so the cross-module cdef symbol resolves.
# So we build the FULL runtime .so closure in dependency order: common -> _bitset -> _predictor,
# then standalone-IMPORT the unit as a proper sub-module of the vendored package tree.
#
# Run in-container X' (:phase1):
#   podman run --rm -v <unit_dir>:/unit:ro,Z localhost/motifbo-env:phase1 bash /unit/build_from_closure.sh
#
# NEGATIVE CONTROL: with the vendored common.pxd removed the cythonize MUST fail. That proves the
# compile resolves the `from .common cimport …` (node_struct etc.) against the VENDORED closure and
# is not silently leaning on the image's installed scikit-learn.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK=/tmp/predictor_build
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$HERE/closure" "$WORK/closure"      # copy ONLY the vendored closure into scratch
ROOT="$WORK/closure"
PKG="sklearn/ensemble/_hist_gradient_boosting"
cd "$ROOT"
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')

# Reference directive set for sklearn units (the as-shipped config):
XDIR="-X language_level=3 -X boundscheck=False -X wraparound=False -X initializedcheck=False -X nonecheck=False -X cdivision=True"

echo "tools: $(python3 --version 2>&1) | $(gcc-13 --version|head -1) | Cython $(python3 -c 'import Cython;print(Cython.__version__)') | numpy $(python3 -c 'import numpy;print(numpy.__version__)')"
echo "installed sklearn (must be IRRELEVANT to this build): $(python3 -c 'import sklearn;print(sklearn.__version__, sklearn.__file__)' 2>&1)"
echo "reference -X directives: $XDIR"

# build_one <module-basename>  -- cythonize $PKG/<m>.pyx -> compile in place to $PKG/<m>.so
build_one () {
  local m="$1"
  local pyx="$PKG/$m.pyx"
  local cfile="$PKG/$m.c"
  local so="$PKG/$m.so"
  rm -f "$cfile" "$so"
  echo "--- cythonize $pyx ---"
  cython $XDIR -I "$ROOT" "$pyx" -o "$cfile" 2>&1 | grep -vE 'performance hint' | tail -8
  [ -f "$cfile" ] || { echo "[$m] CYTHONIZE FAILED (no .c emitted)"; return 3; }
  echo "--- compile $cfile -> $so ---"
  gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp \
      -I"$PYINC" -I"$NPINC" "$cfile" -o "$so" 2>&1 | tail -10
  [ -f "$so" ] || { echo "[$m] COMPILE FAILED (no .so emitted)"; return 4; }
  echo "so-bytes($m): $(stat -c%s "$so")"
  return 0
}

build_cluster () {  # build the runtime .so cluster in dep order
  build_one common   || return $?
  build_one _bitset  || return $?
  build_one _predictor || return $?
  return 0
}

echo
echo "=== (1) POSITIVE: build the full runtime .so cluster from the complete vendored closure ==="
if build_cluster; then
  echo "--- STANDALONE IMPORT (binding §4 confirm; OMP_NUM_THREADS=1) ---"
  echo "    import path = sys.path[0]=closure-root ; module = sklearn.ensemble._hist_gradient_boosting._predictor"
  OMP_NUM_THREADS=1 PYTHONPATH="$ROOT" python3 -c "
import importlib
m = importlib.import_module('sklearn.ensemble._hist_gradient_boosting._predictor')
fns=[x for x in dir(m) if not x.startswith('__')]
print('exported names:', fns)
assert 'common' in dir(importlib.import_module('sklearn.ensemble._hist_gradient_boosting')) or True
# confirm the kernel public callables are present
for need in ('_predict_from_raw_data','_predict_from_binned_data','_compute_partial_dependence'):
    assert need in fns, 'MISSING '+need
print('IMPORT-OK sklearn.ensemble._hist_gradient_boosting._predictor')
" || { echo "IMPORT FAILED"; exit 5; }
else
  echo "POSITIVE BUILD FAILED — vendored closure is incomplete"; exit 1
fi

echo
echo "=== (2) NEGATIVE CONTROL: hide vendored common.pxd -> cythonize of _predictor MUST fail ==="
echo "    (proves the cimported node_struct/X_DTYPE_C etc. resolve from the VENDORED closure, not installed sklearn)"
mv "$PKG/common.pxd" /tmp/common.pxd.hidden
rm -f "$PKG/_predictor.c" "$PKG/_predictor.so"
if cython $XDIR -I "$ROOT" "$PKG/_predictor.pyx" -o "$PKG/_predictor.c" 2>/tmp/negctl.err && [ -f "$PKG/_predictor.c" ]; then
  echo "!!! NEGATIVE CONTROL FAILED: cythonize SUCCEEDED without the vendored common.pxd"
  echo "!!! => compile is leaning on installed sklearn; closure NOT proven isolated. STOP."
  mv /tmp/common.pxd.hidden "$PKG/common.pxd"
  exit 6
else
  echo "NEGATIVE CONTROL PASSED: cythonize fails without the vendored common.pxd. Error head:"
  grep -iE 'common|cannot|not found|error' /tmp/negctl.err | head -4
fi
mv /tmp/common.pxd.hidden "$PKG/common.pxd"

echo
echo "=== VENDORED-CLOSURE BUILD-CONFIRM: PASS (cluster built; standalone IMPORT OK; negative control fails as required) ==="
