#!/bin/bash
# Step 1.1.1 — VENDORED-CLOSURE build-confirm for scipy.sparse.csgraph._shortest_path.
#
# BUILD-CONFIRM == STANDALONE IMPORT (binding, §4). Compiles _shortest_path FROM THE VENDORED
# CLOSURE ALONE — NOT the extracted sdist root, NOT the container's installed scipy (1.17.1).
# Only the deliberately-vendored files exist on the cython include path (-I .).
#
# Closure for this unit (C, not C++):
#   scipy/sparse/csgraph/_shortest_path.pyx   (the kernel; plain .pyx, NOT Tempita)
#   scipy/sparse/csgraph/parameters.pxi       (textual `include 'parameters.pxi'` — DTYPE/ITYPE/fused/DEFs)
# cimports are ALL Cython/stdlib/numpy builtins (cython, libc.stdlib, libc.math, cimport numpy)
#   -> NO repo .pxd to vendor, NO sibling .so cluster to co-build.
# Module-scope Python imports (numpy, scipy.sparse csr_matrix/issparse,
#   scipy.sparse.csgraph._validation validate_graph, scipy.sparse._sputils
#   convert_pydata_sparse_to_scipy) resolve against the IMAGE's scipy at runtime (closure-walk rule 5).
#
# Run in-container X' (:phase1):
#   podman run --rm -v <unit_dir>:/unit:ro,Z localhost/motifbo-env:phase1 bash /unit/build_from_closure.sh
#
# NEGATIVE CONTROL: with the vendored parameters.pxi removed the cythonize MUST fail. That proves the
# compile resolves `include 'parameters.pxi'` against the VENDORED closure, not anything installed.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK=/tmp/sp_build
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$HERE/closure" "$WORK/closure"      # copy ONLY the vendored closure into scratch
cd "$WORK/closure"
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')
PYX=scipy/sparse/csgraph/_shortest_path.pyx
MOD=_shortest_path
FQMOD=scipy.sparse.csgraph._shortest_path
echo "tools: $(python3 --version 2>&1) | $(gcc-13 --version|head -1) | Cython $(python3 -c 'import Cython;print(Cython.__version__)') | numpy $(python3 -c 'import numpy;print(numpy.__version__)')"
echo "installed scipy (IRRELEVANT to the COMPILE; image-scipy only services runtime py-imports): $(cd /tmp && python3 -c 'import scipy,importlib.metadata as M;print(M.version("scipy"), scipy.__file__)' 2>&1)"

build () {  # $1 = label ; returns 0 on full .so, non-zero otherwise
  rm -f /tmp/$MOD.c /tmp/$MOD.so
  echo "--- cythonize ($1): scipy bare -3 reference directive (per-fn @cython pins are as-shipped) ---"
  # scipy units: -3 bare (reference directive set). -I . so `include 'parameters.pxi'` resolves
  # against the vendored csgraph dir only.
  cython -3 -I scipy/sparse/csgraph "$PYX" -o /tmp/$MOD.c 2>&1 | grep -vE 'performance hint' | tail -12
  [ -f /tmp/$MOD.c ] || { echo "[$1] CYTHONIZE FAILED (no .c emitted)"; return 3; }
  # C unit -> gcc-13. -ffp-contract=fast explicit (GCC default is fast; we pin it per §3.2).
  gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp \
      -I"$PYINC" -I"$NPINC" /tmp/$MOD.c -o /tmp/$MOD.so 2>&1 | tail -12
  [ -f /tmp/$MOD.so ] || { echo "[$1] COMPILE FAILED (no .so emitted)"; return 4; }
  return 0
}

echo
echo "=== (1) POSITIVE: build from the complete vendored closure ==="
if build positive; then
  echo "so-bytes: $(stat -c%s /tmp/$MOD.so)"
  echo "--- STANDALONE IMPORT as the real dotted name '$FQMOD' (bare loader; OMP_NUM_THREADS=1) ---"
  # Load the freshly-built .so (already at /tmp/$MOD.so) under its TRUE fully-qualified name so its
  # module-init `from scipy.sparse import csr_matrix` / `...csgraph._validation import validate_graph`
  # (and friends) resolve against the IMAGE scipy. The .so IS our vendored-closure build (loaded by
  # explicit file path), not the installed _shortest_path.
  # CRUCIAL: run from a NEUTRAL cwd (/tmp), NOT from $WORK/closure — otherwise the empty vendored
  # `scipy/__init__.py` shim shadows the image's real scipy on sys.path[0] and `csr_matrix` vanishes.
  ( cd /tmp && OMP_NUM_THREADS=1 python3 -c "
import sys, importlib, importlib.util
# ensure parent packages exist (image scipy provides them) before binding our .so under the FQ name
import scipy, scipy.sparse, scipy.sparse.csgraph
spec = importlib.util.spec_from_file_location('$FQMOD', '/tmp/$MOD.so')
m = importlib.util.module_from_spec(spec)
sys.modules['$FQMOD'] = m
spec.loader.exec_module(m)
fns = [x for x in dir(m) if not x.startswith('__')]
assert hasattr(m, 'shortest_path'), 'shortest_path missing from built module'
assert hasattr(m, 'dijkstra'), 'dijkstra missing from built module'
print('module file:', m.__file__)
print('exported names:', fns)
print('IMPORT-OK $FQMOD')
" ) || { echo "STANDALONE IMPORT FAILED"; exit 5; }
else
  echo "POSITIVE BUILD FAILED — vendored closure is incomplete"; exit 1
fi

echo
echo "=== (2) NEGATIVE CONTROL: hide the vendored parameters.pxi -> cythonize MUST fail ==="
echo "    (proves the compile resolves include 'parameters.pxi' from the VENDORED closure, not elsewhere)"
mv scipy/sparse/csgraph/parameters.pxi /tmp/parameters.pxi.hidden
if build negative-control; then
  echo "!!! NEGATIVE CONTROL FAILED: build SUCCEEDED without the vendored parameters.pxi"
  mv /tmp/parameters.pxi.hidden scipy/sparse/csgraph/parameters.pxi
  exit 6
else
  echo "NEGATIVE CONTROL PASSED: build fails without the vendored parameters.pxi (closure is the real source)."
fi
mv /tmp/parameters.pxi.hidden scipy/sparse/csgraph/parameters.pxi

echo
echo "=== VENDORED-CLOSURE BUILD-CONFIRM: PASS (positive build+STANDALONE-IMPORT OK; negative control fails as required) ==="
