#!/bin/bash
# Step 1.1.1 — VENDORED-CLOSURE build-confirm for sklearn _binning
# (the real §4.2 criterion-3 isolatability gate = STANDALONE IMPORT, §4).
#
# Compiles sklearn.ensemble._hist_gradient_boosting._binning FROM THE VENDORED CLOSURE ALONE
# — NOT the extracted sdist root, NOT the container's installed scikit-learn. Only the
# deliberately-vendored files exist on the include path.
#
# Closure for _binning:
#   sklearn/ensemble/_hist_gradient_boosting/_binning.pyx   (the unit -> built to .so)
#   sklearn/ensemble/_hist_gradient_boosting/common.pxd     (ctypedefs X_DTYPE_C/X_BINNED_DTYPE_C — compile-time)
#   sklearn/utils/_typedefs.pxd                             (ctypedefs float64_t/uint8_t/... — compile-time)
# _binning cimports ONLY ctypedefs (compile-time only) from common; common cimports ONLY ctypedefs
# from _typedefs. No cdef class / non-inline cdef/cpdef is cimported -> NO sibling .so is required;
# .pxd headers suffice for the whole closure. Module-scope imports are only `cython.parallel.prange`
# and `libc.math.isnan` -> Cython/stdlib builtins, nothing to vendor.
#
# REFERENCE DIRECTIVES (sklearn as-shipped):
#   -X language_level=3 -X boundscheck=False -X wraparound=False -X initializedcheck=False
#   -X nonecheck=False -X cdivision=True
# COMPILE (C): gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp -I<pyinc> -I<npinc>
#
# Run in-container X' (:phase1):
#   podman run --rm -v <unit_dir>:/unit:ro,Z localhost/motifbo-env:phase1 bash /unit/build_from_closure.sh
#
# NEGATIVE CONTROL: with the vendored common.pxd removed the build MUST fail. That proves the compile
# resolves `from .common cimport ...` against the VENDORED closure (package-tree-local relative cimport)
# and is complete — not silently leaning on the container's installed scikit-learn.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK=/tmp/binning_build
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$HERE/closure" "$WORK/closure"      # copy ONLY the vendored closure into scratch
cd "$WORK/closure"
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')
PYX=sklearn/ensemble/_hist_gradient_boosting/_binning.pyx
MOD=_binning
TARGET=sklearn.ensemble._hist_gradient_boosting._binning
DIRECTIVES="-X language_level=3 -X boundscheck=False -X wraparound=False -X initializedcheck=False -X nonecheck=False -X cdivision=True"
echo "tools: $(python3 --version 2>&1) | $(gcc-13 --version|head -1) | Cython $(python3 -c 'import Cython;print(Cython.__version__)') | numpy $(python3 -c 'import numpy;print(numpy.__version__)')"
echo "installed sklearn (must be IRRELEVANT to this build): $(python3 -c 'import sklearn;print(sklearn.__version__, sklearn.__file__)' 2>&1)"
echo "reference directives: $DIRECTIVES"

build () {  # $1 = label ; returns 0 on full .so, non-zero otherwise
  rm -f /tmp/$MOD.c /tmp/$MOD.so
  echo "--- cythonize ($1) ---"
  cython $DIRECTIVES -I . "$PYX" -o /tmp/$MOD.c 2>&1 | grep -vE 'performance hint' | tail -8
  [ -f /tmp/$MOD.c ] || { echo "[$1] CYTHONIZE FAILED (no .c emitted)"; return 3; }
  echo "--- compile ($1): gcc-13 C ---"
  gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp \
      -I"$PYINC" -I"$NPINC" /tmp/$MOD.c -o /tmp/$MOD.so 2>&1 | tail -10
  [ -f /tmp/$MOD.so ] || { echo "[$1] COMPILE FAILED (no .so emitted)"; return 4; }
  return 0
}

echo
echo "=== (1) POSITIVE: build from the complete vendored closure ==="
if build positive; then
  echo "so-bytes: $(stat -c%s /tmp/$MOD.so)"
  echo "--- STANDALONE IMPORT (binding build-confirm; OMP_NUM_THREADS=1) ---"
  # Install the freshly-built .so at its true package path so the import is the
  # real fully-qualified module, exercising the full cimport+runtime cascade.
  cp /tmp/$MOD.so "sklearn/ensemble/_hist_gradient_boosting/$MOD.so"
  OMP_NUM_THREADS=1 PYTHONPATH="$WORK/closure" python3 -c "
import importlib
m = importlib.import_module('$TARGET')
fns=[x for x in dir(m) if not x.startswith('__')]
assert 'pyx' not in m.__file__, m.__file__
print('module file:', m.__file__)
print('exported:', fns)
assert '_map_to_bins' in fns, 'expected _map_to_bins export'
print('IMPORT-OK $TARGET')
" || { echo "IMPORT FAILED"; exit 5; }
  rm -f "sklearn/ensemble/_hist_gradient_boosting/$MOD.so"
else
  echo "POSITIVE BUILD FAILED — vendored closure is incomplete"; exit 1
fi

echo
echo "=== (2) NEGATIVE CONTROL: hide the vendored common.pxd -> build MUST fail ==="
echo "    (proves the compile resolves the cimport from the VENDORED closure, not installed sklearn)"
mv sklearn/ensemble/_hist_gradient_boosting/common.pxd /tmp/common.pxd.hidden
if build negative-control; then
  echo "!!! NEGATIVE CONTROL FAILED: build SUCCEEDED without the vendored common.pxd"
  echo "!!! => compile is leaning on installed sklearn; closure NOT proven isolated. STOP."
  mv /tmp/common.pxd.hidden sklearn/ensemble/_hist_gradient_boosting/common.pxd
  exit 6
else
  echo "NEGATIVE CONTROL PASSED: build fails without the vendored common.pxd (closure is the real source)."
fi
mv /tmp/common.pxd.hidden sklearn/ensemble/_hist_gradient_boosting/common.pxd

echo
echo "=== VENDORED-CLOSURE BUILD-CONFIRM: PASS (positive build+STANDALONE IMPORT OK; negative control fails as required) ==="
