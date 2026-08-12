#!/bin/bash
# Step 1.1.1 — VENDORED-CLOSURE build-confirm for sklearn.cluster._dbscan_inner (C++ unit).
#
# BUILD-CONFIRM = STANDALONE IMPORT (§4 binding). Compiles _dbscan_inner FROM THE VENDORED
# CLOSURE ALONE — NOT the extracted sdist root, NOT the container's installed scikit-learn.
# Only the deliberately-vendored files are on the include path.
#
# This is a C++ unit: `from libcpp.vector cimport vector`. So cythonize emits a .cpp and we
# compile with g++-13 --cplus -std=c++14 (NOT gcc). The cimported `..utils._typedefs` symbols
# (uint8_t, intp_t) are pure ctypedefs (compile-time only) -> the .pxd suffices, NO co-built .so.
# Closure is therefore the unit .pyx + _typedefs.pxd + empty package markers.
#
# Run in-container X' (:phase1):
#   podman run --rm -v <unit_dir>:/unit:ro,Z localhost/motifbo-env:phase1 bash /unit/build_from_closure.sh
#
# Reference directive set (sklearn, as-shipped):
#   -X language_level=3 -X boundscheck=False -X wraparound=False -X initializedcheck=False
#   -X nonecheck=False -X cdivision=True
#
# NEGATIVE CONTROL: with the vendored _typedefs.pxd removed the build MUST fail. Proves the compile
# resolves `from ..utils._typedefs cimport ...` against the VENDORED closure, not installed sklearn.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK=/tmp/dbscan_inner_build
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$HERE/closure" "$WORK/closure"      # copy ONLY the vendored closure into scratch
cd "$WORK/closure"
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')
PYX=sklearn/cluster/_dbscan_inner.pyx
MOD=_dbscan_inner
DIRECTIVES="-X language_level=3 -X boundscheck=False -X wraparound=False -X initializedcheck=False -X nonecheck=False -X cdivision=True"
echo "tools: $(python3 --version 2>&1) | $(g++-13 --version|head -1) | Cython $(python3 -c 'import Cython;print(Cython.__version__)') | numpy $(python3 -c 'import numpy;print(numpy.__version__)')"
echo "installed sklearn (must be IRRELEVANT to this build): $(python3 -c 'import sklearn;print(sklearn.__version__, sklearn.__file__)' 2>&1)"
echo "reference directives: $DIRECTIVES"

build () {  # $1 = label ; returns 0 on full .so, non-zero otherwise
  rm -f /tmp/$MOD.cpp /tmp/$MOD.so
  echo "--- cythonize --cplus ($1) ---"
  cython --cplus $DIRECTIVES -I . "$PYX" -o /tmp/$MOD.cpp 2>&1 | grep -vE 'performance hint' | tail -8
  [ -f /tmp/$MOD.cpp ] || { echo "[$1] CYTHONIZE FAILED (no .cpp emitted)"; return 3; }
  # C++ -> g++-13 --cplus -std=c++14 ; C++ may use -O1 for faster compile.
  g++-13 -std=c++14 -shared -fPIC -O1 -march=native -ffp-contract=fast -fopenmp \
      -I"$PYINC" -I"$NPINC" /tmp/$MOD.cpp -o /tmp/$MOD.so 2>&1 | tail -12
  [ -f /tmp/$MOD.so ] || { echo "[$1] COMPILE FAILED (no .so emitted)"; return 4; }
  return 0
}

echo
echo "=== (1) POSITIVE: build from the complete vendored closure ==="
if build positive; then
  echo "so-bytes: $(stat -c%s /tmp/$MOD.so)"
  echo "--- STANDALONE IMPORT (bare loader; OMP_NUM_THREADS=1) ---"
  OMP_NUM_THREADS=1 python3 -c "
import importlib.util
s=importlib.util.spec_from_file_location('$MOD','/tmp/$MOD.so')
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
fns=[x for x in dir(m) if not x.startswith('__')]
assert 'dbscan_inner' in fns, ('dbscan_inner missing from module', fns)
print('IMPORT-OK sklearn.cluster._dbscan_inner; exported callables:', fns)
" || { echo "IMPORT FAILED"; exit 5; }
else
  echo "POSITIVE BUILD FAILED — vendored closure is incomplete"; exit 1
fi

echo
echo "=== (2) NEGATIVE CONTROL: hide the vendored _typedefs.pxd -> build MUST fail ==="
echo "    (proves the compile resolves the cimport from the VENDORED closure, not installed sklearn)"
mv sklearn/utils/_typedefs.pxd /tmp/_typedefs.pxd.hidden
if build negative-control; then
  echo "!!! NEGATIVE CONTROL FAILED: build SUCCEEDED without the vendored _typedefs.pxd"
  echo "!!! => compile is leaning on installed sklearn; closure NOT proven isolated. STOP."
  mv /tmp/_typedefs.pxd.hidden sklearn/utils/_typedefs.pxd
  exit 6
else
  echo "NEGATIVE CONTROL PASSED: build fails without the vendored _typedefs.pxd (closure is the real source)."
fi
mv /tmp/_typedefs.pxd.hidden sklearn/utils/_typedefs.pxd

echo
echo "=== VENDORED-CLOSURE BUILD-CONFIRM: PASS (positive build+IMPORT OK; negative control fails as required) ==="
