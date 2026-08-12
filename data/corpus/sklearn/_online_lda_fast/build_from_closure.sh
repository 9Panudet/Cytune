#!/bin/bash
# Step 1.1.1 (margin / 11th fold) — VENDORED-CLOSURE build-confirm for decomposition/_online_lda_fast.
# Compiles from the vendored closure ALONE in X' (:phase1) — not the sdist root, not installed sklearn.
# NEGATIVE CONTROL: hide the vendored _typedefs.pxd -> build MUST fail (proves the vendored closure is
# the real source). Run:
#   podman run --rm -v <unit_dir>:/unit:ro,Z localhost/motifbo-env:phase1 bash /unit/build_from_closure.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK=/tmp/olf_build
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$HERE/closure" "$WORK/closure"
cd "$WORK/closure"
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')
PYX=sklearn/decomposition/_online_lda_fast.pyx
MOD=_online_lda_fast
echo "tools: $(python3 --version 2>&1) | $(gcc-13 --version|head -1) | Cython $(python3 -c 'import Cython;print(Cython.__version__)') | numpy $(python3 -c 'import numpy;print(numpy.__version__)')"

build () {  # $1 = label
  rm -f /tmp/$MOD.c /tmp/$MOD.so
  echo "--- cythonize ($1) ---"
  cython -3 -I . "$PYX" -o /tmp/$MOD.c 2>&1 | grep -vE 'performance hint' | tail -8
  [ -f /tmp/$MOD.c ] || { echo "[$1] CYTHONIZE FAILED (no .c)"; return 3; }
  gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp \
      -I"$PYINC" -I"$NPINC" /tmp/$MOD.c -o /tmp/$MOD.so 2>&1 | tail -10
  [ -f /tmp/$MOD.so ] || { echo "[$1] COMPILE FAILED (no .so)"; return 4; }
  return 0
}

echo
echo "=== (1) POSITIVE: build from the complete vendored closure ==="
if build positive; then
  echo "so-bytes: $(stat -c%s /tmp/$MOD.so)"
  OMP_NUM_THREADS=1 python3 -c "
import importlib.util
s=importlib.util.spec_from_file_location('$MOD','/tmp/$MOD.so')
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
print('IMPORT OK; exported callables:', [x for x in dir(m) if not x.startswith('__')])
" || { echo "IMPORT FAILED"; exit 5; }
else
  echo "POSITIVE BUILD FAILED — closure incomplete"; exit 1
fi

echo
echo "=== (2) DETERMINISM SMOKE (kernel-level, fixed inputs, OMP_NUM_THREADS=1) ==="
echo "    drive mean_change + _dirichlet_expectation_2d twice with identical fixed arrays -> bit-identical"
OMP_NUM_THREADS=1 python3 -c "
import importlib.util, numpy as np
s=importlib.util.spec_from_file_location('$MOD','/tmp/$MOD.so')
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
rng=np.random.RandomState(0)                      # fixed seed -> fixed INPUT (not kernel RNG)
a=rng.rand(5000).astype(np.float64); b=rng.rand(5000).astype(np.float64)
M=rng.rand(64,128).astype(np.float64)+0.01
r1=(m.mean_change(a,b), m.mean_change(a,b))
import numpy as _np
d1=m._dirichlet_expectation_2d(M); d2=m._dirichlet_expectation_2d(M)
assert r1[0]==r1[1], 'mean_change non-deterministic'
assert _np.array_equal(d1,d2), '_dirichlet_expectation_2d non-deterministic'
print('mean_change repeat bit-identical:', r1[0]==r1[1], '(',r1[0],')')
print('_dirichlet_expectation_2d repeat bit-identical:', _np.array_equal(d1,d2))
print('DETERMINISM SMOKE: PASS (no RNG, no prange — serial kernel)')
" || { echo "DETERMINISM SMOKE FAILED"; exit 7; }

echo
echo "=== (3) NEGATIVE CONTROL: hide vendored _typedefs.pxd -> build MUST fail ==="
mv sklearn/utils/_typedefs.pxd /tmp/_typedefs.pxd.hidden
if build negative-control; then
  echo "!!! NEGATIVE CONTROL FAILED: built without vendored _typedefs.pxd — STOP."
  mv /tmp/_typedefs.pxd.hidden sklearn/utils/_typedefs.pxd; exit 6
else
  echo "NEGATIVE CONTROL PASSED: build fails without the vendored _typedefs.pxd."
fi
mv /tmp/_typedefs.pxd.hidden sklearn/utils/_typedefs.pxd

echo
echo "=== VENDORED-CLOSURE BUILD-CONFIRM + DETERMINISM SMOKE: PASS ==="
