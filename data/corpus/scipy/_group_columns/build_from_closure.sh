#!/bin/bash
# Step 1.1.1 — scipy unit vendored-closure build+IMPORT-confirm (by-file import).
# These scipy units cimport stable scipy.linalg BLAS/LAPACK bindings (cython_blas/cython_lapack) that are
# NOT in the sdist (image-provided, version-stable C bindings — analogous to numpy headers). So the unit is
# imported BY FILE (not dotted name): the corpus UNIT is vendored; the stable external bindings come from the
# image's scipy. Build-confirm = the unit module IMPORTS + its init cascade runs (incl. `from scipy.linalg
# import ...`). Reference (as-shipped) directives: scipy pins via in-source @cython decorators, honored by
# bare `cython -3`. Run in-container X' (:phase1):
#   podman run --rm -v <unit_dir>:/unit:ro,Z localhost/motifbo-env:phase1 bash /unit/build_from_closure.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
W=/tmp/scipy_unit_build; rm -rf "$W"; mkdir -p "$W"; cp -r "$HERE/closure" "$W/closure"; cd "$W/closure"
MOD="$(basename "$(ls *.pyx)" .pyx)"
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')
echo "tools: $(python3 --version 2>&1) | $(gcc-13 --version|head -1) | Cython $(python3 -c 'import Cython;print(Cython.__version__)') | scipy $(python3 -c 'import scipy;print(scipy.__version__)') (image, provides cython_blas/lapack)"
echo "unit: $MOD  (reference directives: scipy bare -3, in-source @cython decorators honored)"
build () {  # $1 = label
  rm -f "$MOD.c" "$MOD.so"
  cython -3 -I . "$MOD.pyx" -o "$MOD.c" 2>&1 | grep -vE 'performance hint' | tail -6
  [ -f "$MOD.c" ] || { echo "[$1] CYTHONIZE FAILED"; return 3; }
  gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp -I"$PYINC" -I"$NPINC" "$MOD.c" -o "$MOD.so" 2>&1 | tail -8
  [ -f "$MOD.so" ] || { echo "[$1] COMPILE FAILED"; return 4; }
}
echo "=== (1) POSITIVE: build from vendored closure + standalone IMPORT (by file) ==="
if build positive; then
  echo "so-bytes: $(stat -c%s "$MOD.so")"
  OMP_NUM_THREADS=1 python3 -c "
import importlib.util
s=importlib.util.spec_from_file_location('$MOD','$W/closure/$MOD.so'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
print('exported:', [x for x in dir(m) if not x.startswith('_')][:10]); print('IMPORT-OK $MOD')
" || { echo "IMPORT FAILED"; exit 5; }
else echo "POSITIVE BUILD FAILED"; exit 1; fi
echo "=== (2) NEGATIVE CONTROL: hide the vendored unit .pyx -> build MUST fail ==="
mv "$MOD.pyx" "/tmp/$MOD.pyx.hidden"
if build negative-control; then echo "!!! NEGATIVE CONTROL FAILED: built without the vendored .pyx"; mv "/tmp/$MOD.pyx.hidden" "$MOD.pyx"; exit 6
else echo "NEGATIVE CONTROL PASSED: build fails without the vendored unit .pyx."; fi
mv "/tmp/$MOD.pyx.hidden" "$MOD.pyx"
echo "=== VENDORED-CLOSURE BUILD-CONFIRM: PASS ($MOD: by-file IMPORT-OK; negative control fails as required) ==="
