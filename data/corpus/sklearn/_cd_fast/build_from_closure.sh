#!/bin/bash
# Step 1.1.1 — VENDORED-CLOSURE build-confirm for sklearn.linear_model._cd_fast.
#
# BUILD-CONFIRM = STANDALONE IMPORT (binding, §4). Compiles _cd_fast FROM THE VENDORED
# CLOSURE ALONE — NOT the extracted sdist root, NOT the container's installed scikit-learn.
# Only the deliberately-vendored files exist on the cython include path.
#
# Closure dependency structure (why two .so are co-built):
#   _cd_fast.pyx cimports NON-INLINE cdef BLAS wrappers (_axpy,_dot,_asum,_gemv,_nrm2,
#   _copy,_scal) + cpdef enums (ColMajor,Trans,NoTrans) from ..utils._cython_blas.
#   Non-inline cdef => the symbols live in _cython_blas's runtime __pyx_capi__, so
#   _cython_blas.so MUST be co-built and importable as sklearn.utils._cython_blas at the
#   moment _cd_fast is imported. _cython_blas.pyx itself only cimports BLAS symbols from
#   scipy.linalg.cython_blas (a scipy builtin, provided by the image's scipy) — no further
#   sklearn vendoring.
#   our_rand_r (..utils._random) is cdef INLINE so its CODE inlines into _cd_fast, BUT
#   Cython 3.x still emits a runtime `import sklearn.utils._random` at _cd_fast module init
#   (because _random.pxd declares a module-level `cdef uint32_t DEFAULT_SEED`). Empirically
#   confirmed: a bare-loader import raised `ModuleNotFoundError: No module named
#   'sklearn.utils._random'`. So _random.so IS in the runtime closure and is co-built.
#   _random.pyx does `from . import check_random_state` -> resolved from the vendored
#   faithful-minimal sklearn/utils/__init__.py; and `from ._typedefs cimport intp_t`.
#   uint32_t/intp_t (..utils._typedefs) are ctypedefs only => _typedefs.pxd suffices, no .so
#   (no module-level cdef var / cdef class => no runtime import emitted for it).
#   `from ..exceptions import ConvergenceWarning` is a module-scope python import resolved
#   from the vendored faithful-minimal sklearn/exceptions.py.
#
# Import is done as a REAL package submodule (sklearn.linear_model._cd_fast) because the
# cross-module cdef cimport linkage resolves through sklearn.utils._cython_blas's CAPI — a
# bare spec_from_file_location loader would NOT satisfy it.
#
# Run in-container X' (:phase1):
#   podman run --rm -v <unit_dir>:/unit:ro,Z localhost/motifbo-env:phase1 bash /unit/build_from_closure.sh
#
# NEGATIVE CONTROL: with the vendored _cython_blas.pxd removed the _cd_fast cythonize MUST
# fail. That proves the compile resolves `from ..utils._cython_blas cimport ...` against the
# VENDORED closure, not silently leaning on installed sklearn.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK=/tmp/cdfast_build
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$HERE/closure" "$WORK/closure"      # copy ONLY the vendored closure into scratch
cd "$WORK/closure"
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')

# sklearn reference (as-shipped) explicit -X directive set
XDIR=(-X language_level=3 -X boundscheck=False -X wraparound=False -X initializedcheck=False -X nonecheck=False -X cdivision=True)

echo "tools: $(python3 --version 2>&1) | $(gcc-13 --version|head -1) | Cython $(python3 -c 'import Cython;print(Cython.__version__)') | numpy $(python3 -c 'import numpy;print(numpy.__version__)') | scipy $(python3 -c 'import scipy;print(scipy.__version__)')"
echo "installed sklearn (must be IRRELEVANT to this build): $(python3 -c 'import sklearn;print(sklearn.__version__, sklearn.__file__)' 2>&1)"
echo "reference -X: ${XDIR[*]}"

# cythonize+compile one module in-place next to its .pyx (so the .so lands in the package tree).
# $1 = pyx path (relative to closure root) ; $2 = output module basename
build_mod () {
  local pyx="$1" base="$2" outdir cfile sofile
  outdir=$(dirname "$pyx")
  cfile="$outdir/${base}.c"
  sofile="$outdir/${base}.cpython"
  echo "--- cythonize $pyx ---"
  cython -3 "${XDIR[@]}" -I . "$pyx" -o "$cfile" 2>&1 | grep -vE 'performance hint' | tail -8
  [ -f "$cfile" ] || { echo "CYTHONIZE FAILED ($pyx) — no .c emitted"; return 3; }
  echo "--- gcc-13 compile $cfile ---"
  # name the .so with the cpython tag so import machinery picks it up
  local tag
  tag=$(python3 -c 'import sysconfig;print(sysconfig.get_config_var("EXT_SUFFIX"))')
  gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp \
      -I"$PYINC" -I"$NPINC" "$cfile" -o "$outdir/${base}${tag}" 2>&1 | tail -12
  [ -f "$outdir/${base}${tag}" ] || { echo "COMPILE FAILED ($pyx) — no .so emitted"; return 4; }
  echo "so-bytes ($base): $(stat -c%s "$outdir/${base}${tag}")"
  return 0
}

echo
echo "=== (1) POSITIVE: build the full runtime .so closure in dep order ==="
echo "    [dep 1/3] sklearn.utils._cython_blas (BLAS wrapper .so; cdef-capi provider)"
build_mod sklearn/utils/_cython_blas.pyx _cython_blas || { echo "POSITIVE BUILD FAILED at _cython_blas"; exit 1; }
echo "    [dep 2/3] sklearn.utils._random (runtime-import dep; cdef DEFAULT_SEED module state)"
build_mod sklearn/utils/_random.pyx _random || { echo "POSITIVE BUILD FAILED at _random"; exit 1; }
echo "    [dep 3/3] sklearn.linear_model._cd_fast (unit)"
build_mod sklearn/linear_model/_cd_fast.pyx _cd_fast || { echo "POSITIVE BUILD FAILED at _cd_fast"; exit 1; }

echo
echo "--- STANDALONE IMPORT (real package submodule; OMP_NUM_THREADS=1) ---"
OMP_NUM_THREADS=1 PYTHONPATH="$WORK/closure" python3 -c "
import importlib
m = importlib.import_module('sklearn.linear_model._cd_fast')
fns=[x for x in dir(m) if not x.startswith('__')]
print('exported:', fns)
for need in ('enet_coordinate_descent','sparse_enet_coordinate_descent','enet_coordinate_descent_gram','enet_coordinate_descent_multi_task'):
    assert need in fns, 'MISSING entry point: '+need
print('IMPORT-OK sklearn.linear_model._cd_fast')
" || { echo "IMPORT FAILED"; exit 5; }

echo
echo "=== (2) NEGATIVE CONTROL: hide vendored _cython_blas.pxd -> _cd_fast cythonize MUST fail ==="
echo "    (proves the compile resolves ..utils._cython_blas cimport from the VENDORED closure)"
mv sklearn/utils/_cython_blas.pxd /tmp/_cython_blas.pxd.hidden
rm -f sklearn/linear_model/_cd_fast.c
if cython -3 "${XDIR[@]}" -I . sklearn/linear_model/_cd_fast.pyx -o sklearn/linear_model/_cd_fast.c 2>/tmp/nc.err && [ -f sklearn/linear_model/_cd_fast.c ]; then
  echo "!!! NEGATIVE CONTROL FAILED: _cd_fast cythonize SUCCEEDED without vendored _cython_blas.pxd"
  mv /tmp/_cython_blas.pxd.hidden sklearn/utils/_cython_blas.pxd
  exit 6
else
  echo "NEGATIVE CONTROL PASSED: cythonize fails without vendored _cython_blas.pxd (closure is the real source)."
  echo "  err tail: $(grep -iE 'not found|cannot|error' /tmp/nc.err | head -2)"
fi
mv /tmp/_cython_blas.pxd.hidden sklearn/utils/_cython_blas.pxd

echo
echo "=== VENDORED-CLOSURE BUILD-CONFIRM: PASS (positive build+standalone import OK; negative control fails as required) ==="
