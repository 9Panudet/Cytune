#!/bin/bash
# Step 1.1.1 — VENDORED-CLOSURE build-confirm for sklearn.cluster._k_means_lloyd  (C unit).
#
# BUILD-CONFIRM == STANDALONE IMPORT (§4 binding). The unit counts ONLY if its kernel module
# standalone-IMPORTS from its vendored closure in X' — full cimport + runtime-import cascade.
# cythonize-OK / compile-OK do NOT count.
#
# This builds the FULL runtime .so closure FROM THE VENDORED CLOSURE ALONE (not the sdist root,
# not the container's installed scikit-learn). Only the deliberately-vendored files are on the
# include path. Build order is dependency order:
#     (1) sklearn/utils/_cython_blas.so      (_gemm; cimports scipy.linalg.cython_blas from image)
#     (2) sklearn/cluster/_k_means_common.so (_relocate_*, _average_centers, _center_shift, CHUNK_SIZE)
#     (3) sklearn/cluster/_k_means_lloyd.so  (the unit; cimports (1)+(2)+_openmp_helpers.pxd)
# Then: `import sklearn.cluster._k_means_lloyd` with the closure root on sys.path (full package
# import so `from ..utils.extmath import row_norms` and `from ._k_means_common import CHUNK_SIZE`
# resolve against the vendored package). Prints IMPORT-OK sklearn.cluster._k_means_lloyd on success.
#
# Run in-container X' (:phase1):
#   podman run --rm -v <unit_dir>:/unit:ro,Z localhost/motifbo-env:phase1 bash /unit/build_from_closure.sh
#
# REFERENCE DIRECTIVES (sklearn, as-shipped): explicit -X set below.
# COMPILE: gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp.
#
# NEGATIVE CONTROL: with the vendored _k_means_common.pxd hidden, the unit cythonize MUST fail —
# proving the `from ._k_means_common cimport ...` resolves against the VENDORED closure, not the
# installed sklearn.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK=/tmp/kml_build
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$HERE/closure" "$WORK/closure"      # copy ONLY the vendored closure into scratch
ROOT="$WORK/closure"
cd "$ROOT"
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')

# sklearn reference (as-shipped) explicit directive set:
XDIRS="-X language_level=3 -X boundscheck=False -X wraparound=False -X initializedcheck=False -X nonecheck=False -X cdivision=True"

echo "tools: $(python3 --version 2>&1) | $(gcc-13 --version|head -1) | Cython $(python3 -c 'import Cython;print(Cython.__version__)') | numpy $(python3 -c 'import numpy;print(numpy.__version__)') | scipy $(python3 -c 'import scipy;print(scipy.__version__)')"
echo "installed sklearn (must be IRRELEVANT to this build): $(python3 -c 'import sklearn;print(sklearn.__version__, sklearn.__file__)' 2>&1)"
echo "directives: $XDIRS"
echo

# cython_c PYX_REL MOD_NAME  -> cythonize+compile a C .pyx into a .so IN PLACE next to the .pyx
build_c () {
  local pyx_rel="$1" ; local modname="$2"
  local pyx_dir ; pyx_dir="$(dirname "$pyx_rel")"
  local base ; base="$(basename "$pyx_rel" .pyx)"
  local cfile="$ROOT/$pyx_dir/$base.c"
  local sofile="$ROOT/$pyx_dir/$base.so"   # bare-name .so (matches relative cimport / submodule import)
  rm -f "$cfile" "$sofile"
  echo "--- cythonize $pyx_rel ($modname) ---"
  cython -I "$ROOT" $XDIRS "$ROOT/$pyx_rel" -o "$cfile" 2>&1 | grep -vE 'performance hint' | tail -8
  [ -f "$cfile" ] || { echo "[$modname] CYTHONIZE FAILED (no .c emitted)"; return 3; }
  gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp \
      -I"$PYINC" -I"$NPINC" "$cfile" -o "$sofile" 2>&1 | tail -12
  [ -f "$sofile" ] || { echo "[$modname] COMPILE FAILED (no .so emitted)"; return 4; }
  echo "  built $sofile ($(stat -c%s "$sofile") bytes)"
  return 0
}

echo "=== BUILD the runtime .so closure in dependency order ==="
build_c sklearn/utils/_cython_blas.pyx        _cython_blas      || { echo "CLOSURE BUILD FAILED at _cython_blas"; exit 1; }
build_c sklearn/cluster/_k_means_common.pyx   _k_means_common   || { echo "CLOSURE BUILD FAILED at _k_means_common"; exit 1; }
build_c sklearn/cluster/_k_means_lloyd.pyx    _k_means_lloyd    || { echo "CLOSURE BUILD FAILED at _k_means_lloyd"; exit 1; }

echo
echo "=== STANDALONE IMPORT (binding build-confirm; OMP_NUM_THREADS=1) ==="
echo "    full package import: sklearn.cluster._k_means_lloyd  (cascade: ._k_means_common, ..utils.extmath)"
OMP_NUM_THREADS=1 PYTHONPATH="$ROOT" python3 -c "
import importlib
m = importlib.import_module('sklearn.cluster._k_means_lloyd')
fns = [x for x in dir(m) if not x.startswith('__')]
assert 'lloyd_iter_chunked_dense' in fns,  'missing lloyd_iter_chunked_dense'
assert 'lloyd_iter_chunked_sparse' in fns, 'missing lloyd_iter_chunked_sparse'
# prove the runtime-import cascade actually loaded:
import sklearn.cluster._k_means_common as kc
assert kc.CHUNK_SIZE == 256, kc.CHUNK_SIZE
import sklearn.utils.extmath as ex
import numpy as np
print('row_norms smoke:', ex.row_norms(np.ones((2,3)), squared=True).tolist())
print('exported callables:', fns)
print('IMPORT-OK sklearn.cluster._k_means_lloyd')
" || { echo "IMPORT FAILED"; exit 5; }

echo
echo "=== NEGATIVE CONTROL: hide vendored _k_means_common.pxd -> unit cythonize MUST fail ==="
echo '    (proves the `from ._k_means_common cimport ...` resolves against the VENDORED closure)'
mv "$ROOT/sklearn/cluster/_k_means_common.pxd" /tmp/_k_means_common.pxd.hidden
rm -f "$ROOT/sklearn/cluster/_k_means_lloyd.c"
cython -I "$ROOT" $XDIRS "$ROOT/sklearn/cluster/_k_means_lloyd.pyx" -o "$ROOT/sklearn/cluster/_k_means_lloyd.c" 2>&1 | tail -4
if [ -f "$ROOT/sklearn/cluster/_k_means_lloyd.c" ]; then
  echo "!!! NEGATIVE CONTROL FAILED: unit cythonized without the vendored _k_means_common.pxd"
  echo "!!! => leaning on installed sklearn; closure NOT proven isolated. STOP."
  mv /tmp/_k_means_common.pxd.hidden "$ROOT/sklearn/cluster/_k_means_common.pxd"
  exit 6
else
  echo "NEGATIVE CONTROL PASSED: unit cythonize fails without the vendored _k_means_common.pxd."
fi
mv /tmp/_k_means_common.pxd.hidden "$ROOT/sklearn/cluster/_k_means_common.pxd"

echo
echo "=== VENDORED-CLOSURE BUILD-CONFIRM: PASS (full .so closure built + standalone IMPORT-OK; negative control fails as required) ==="
