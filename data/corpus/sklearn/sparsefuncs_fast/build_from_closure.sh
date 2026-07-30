#!/bin/bash
# Step 1.1.1 — VENDORED-CLOSURE build-confirm (the real §4.2 criterion-3 isolatability gate).
#
# Compiles sparsefuncs_fast FROM THE VENDORED CLOSURE ALONE — NOT the extracted sdist root,
# NOT the container's installed scikit-learn (1.8.0). This is stricter than the earlier
# build_probe.sh sweep, which cythonized the .pyx from inside the FULL extracted sdist tree
# (`cd /dl/<sdist>; cython -I .`) so cimports could resolve against any sibling present in the
# sdist. Here only the deliberately-vendored files exist on the include path.
#
# Run in-container X' (:phase1):
#   podman run --rm -v <unit_dir>:/unit:ro,Z localhost/motifbo-env:phase1 bash /unit/build_from_closure.sh
#
# NEGATIVE CONTROL: with the vendored _typedefs.pxd removed the build MUST fail. That proves the
# compile resolves the `from ..utils._typedefs cimport ...` against the VENDORED closure (relative
# cimport, package-tree-local) and is complete — not silently leaning on installed sklearn.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK=/tmp/sff_build
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$HERE/closure" "$WORK/closure"      # copy ONLY the vendored closure into scratch
cd "$WORK/closure"
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')
PYX=sklearn/utils/sparsefuncs_fast.pyx
MOD=sparsefuncs_fast
echo "tools: $(python3 --version 2>&1) | $(gcc-13 --version|head -1) | Cython $(python3 -c 'import Cython;print(Cython.__version__)') | numpy $(python3 -c 'import numpy;print(numpy.__version__)')"
echo "installed sklearn (must be IRRELEVANT to this build): $(python3 -c 'import sklearn;print(sklearn.__version__, sklearn.__file__)' 2>&1)"

build () {  # $1 = label ; returns 0 on full .so, non-zero otherwise
  rm -f /tmp/$MOD.c /tmp/$MOD.so
  echo "--- cythonize ($1) ---"
  cython -3 -I . "$PYX" -o /tmp/$MOD.c 2>&1 | grep -vE 'performance hint' | tail -8
  [ -f /tmp/$MOD.c ] || { echo "[$1] CYTHONIZE FAILED (no .c emitted)"; return 3; }
  gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp \
      -I"$PYINC" -I"$NPINC" /tmp/$MOD.c -o /tmp/$MOD.so 2>&1 | tail -10
  [ -f /tmp/$MOD.so ] || { echo "[$1] COMPILE FAILED (no .so emitted)"; return 4; }
  return 0
}

echo
echo "=== (1) POSITIVE: build from the complete vendored closure ==="
if build positive; then
  echo "so-bytes: $(stat -c%s /tmp/$MOD.so)"
  echo "--- import-smoke (bare loader; OMP_NUM_THREADS=1) ---"
  OMP_NUM_THREADS=1 python3 -c "
import importlib.util
s=importlib.util.spec_from_file_location('$MOD','/tmp/$MOD.so')
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
fns=[x for x in dir(m) if not x.startswith('__')]
print('IMPORT OK; exported callables:', fns)
" || { echo "IMPORT FAILED"; exit 5; }
else
  echo "POSITIVE BUILD FAILED — vendored closure is incomplete"; exit 1
fi

echo
echo "=== (2) NEGATIVE CONTROL: hide the vendored _typedefs.pxd -> build MUST fail ==="
echo "    (proves the compile resolves the cimport from the VENDORED closure, not installed sklearn 1.8.0)"
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
echo "=== VENDORED-CLOSURE BUILD-CONFIRM: PASS (positive build+import OK; negative control fails as required) ==="
