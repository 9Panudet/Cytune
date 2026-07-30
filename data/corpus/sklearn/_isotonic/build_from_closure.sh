#!/bin/bash
# Step 1.1.1 — VENDORED-CLOSURE build-confirm for sklearn._isotonic (the §4.2 criterion-3 gate).
#
# BUILD-CONFIRM = STANDALONE IMPORT (binding, §4). The unit counts ONLY if its kernel module
# standalone-IMPORTS from its vendored closure in X' (full cimport + runtime-import cascade).
# cythonize-OK / compile-OK do NOT count.
#
# _isotonic is the lowest-coupling kind of unit: its cimport closure is EMPTY. The .pyx cimports
# only `from cython cimport floating` (a Cython builtin -> no vendoring) and `import numpy as np`
# (image-provided). There is no sibling .pxd, no repo cimport, no `from . import` helper, and no
# co-built .so cluster. The vendored closure is therefore exactly: the unit .pyx + one empty
# `sklearn/__init__.py` package marker.
#
# Builds with the sklearn AS-SHIPPED reference directive set:
#   -X language_level=3 -X boundscheck=False -X wraparound=False -X initializedcheck=False
#   -X nonecheck=False -X cdivision=True
# C unit -> gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp.
#
# Run in-container X' (:phase1):
#   podman run --rm -v <unit_dir>:/unit:ro,Z localhost/motifbo-env:phase1 bash /unit/build_from_closure.sh
#
# NEGATIVE CONTROL (non-vacuity): with the empty closure, the only vendored source IS the unit .pyx.
# Hiding it MUST make the build fail -> proves the .so is produced FROM the vendored closure, not from
# the container's installed scikit-learn. (There is no cimported .pxd to hide here; the unit .pyx is
# the sole closure member, so it is the correct negative-control target.)
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK=/tmp/isotonic_build
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$HERE/closure" "$WORK/closure"      # copy ONLY the vendored closure into scratch
cd "$WORK/closure"
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')
PYX=sklearn/_isotonic.pyx
MOD=_isotonic
DIRECTIVES="-X language_level=3 -X boundscheck=False -X wraparound=False -X initializedcheck=False -X nonecheck=False -X cdivision=True"
echo "tools: $(python3 --version 2>&1) | $(gcc-13 --version|head -1) | Cython $(python3 -c 'import Cython;print(Cython.__version__)') | numpy $(python3 -c 'import numpy;print(numpy.__version__)')"
echo "installed sklearn (must be IRRELEVANT to this build): $(python3 -c 'import sklearn;print(sklearn.__version__, sklearn.__file__)' 2>&1)"
echo "reference directives: $DIRECTIVES"

build () {  # $1 = label ; emits the .so INTO the vendored package dir so the real import path works
  rm -f /tmp/$MOD.c sklearn/$MOD*.so
  echo "--- cythonize ($1) ---"
  cython -3 $DIRECTIVES -I . "$PYX" -o /tmp/$MOD.c 2>&1 | grep -vE 'performance hint' | tail -8
  [ -f /tmp/$MOD.c ] || { echo "[$1] CYTHONIZE FAILED (no .c emitted)"; return 3; }
  gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp \
      -I"$PYINC" -I"$NPINC" /tmp/$MOD.c -o sklearn/$MOD.so 2>&1 | tail -10
  [ -f sklearn/$MOD.so ] || { echo "[$1] COMPILE FAILED (no .so emitted)"; return 4; }
  return 0
}

echo
echo "=== (1) POSITIVE: build from the complete vendored closure + STANDALONE IMPORT sklearn._isotonic ==="
if build positive; then
  echo "so-bytes: $(stat -c%s sklearn/$MOD.so)"
  echo "--- standalone import (real package path sklearn._isotonic; OMP_NUM_THREADS=1) ---"
  # Put the vendored-closure scratch on sys.path FRONT so `import sklearn._isotonic` resolves to the
  # vendored package (empty __init__) + freshly-built .so, NOT the installed sklearn.
  OMP_NUM_THREADS=1 PYTHONPATH="$WORK/closure" python3 -c "
import sys, sklearn
# Assert the resolved sklearn is the VENDORED empty-marker package, not the installed one.
assert sklearn.__file__.startswith('$WORK/closure'), ('wrong sklearn: %r' % sklearn.__file__)
import sklearn._isotonic as m
fns=[x for x in dir(m) if not x.startswith('__')]
assert '_inplace_contiguous_isotonic_regression' in fns and '_make_unique' in fns, fns
print('vendored sklearn pkg:', sklearn.__file__)
print('unit .so          :', m.__file__)
print('exported callables:', fns)
print('IMPORT-OK sklearn._isotonic')
" || { echo "IMPORT FAILED"; exit 5; }
else
  echo "POSITIVE BUILD FAILED — vendored closure is incomplete"; exit 1
fi

echo
echo "=== (2) NEGATIVE CONTROL: hide the vendored unit .pyx (the sole closure source) -> build MUST fail ==="
echo "    (proves the .so is produced from the VENDORED closure, not the container's installed sklearn)"
mv sklearn/$MOD.pyx /tmp/$MOD.pyx.hidden
if build negative-control; then
  echo "!!! NEGATIVE CONTROL FAILED: build SUCCEEDED without the vendored unit .pyx"
  echo "!!! => build is leaning on installed sklearn; closure NOT proven isolated. STOP."
  mv /tmp/$MOD.pyx.hidden sklearn/$MOD.pyx
  exit 6
else
  echo "NEGATIVE CONTROL PASSED: build fails without the vendored unit .pyx (closure is the real source)."
fi
mv /tmp/$MOD.pyx.hidden sklearn/$MOD.pyx

echo
echo "=== VENDORED-CLOSURE BUILD-CONFIRM: PASS (positive build+STANDALONE-IMPORT OK; negative control fails as required) ==="
