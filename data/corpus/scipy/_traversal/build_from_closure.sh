#!/bin/bash
# Step 1.1.1 — VENDORED-CLOSURE build-confirm for scipy.sparse.csgraph._traversal.
#
# Builds the unit FROM THE VENDORED CLOSURE ALONE (data/corpus/scipy/_traversal/closure/),
# NOT the extracted sdist root and NOT the container's installed scipy (1.17.1). Only the
# deliberately-vendored files are on the include path.
#
# scipy reference directive set: bare `-3` (scipy's per-function @cython decorators are the
# as-shipped pins; no project-wide -X overrides for scipy units).
#
# Run in-container X' (:phase1):
#   podman run --rm -v <unit_dir>:/unit:ro,Z localhost/motifbo-env:phase1 bash /unit/build_from_closure.sh
#
# CLOSURE (transitive, from the .pyx + its include + module-scope imports):
#   _traversal.pyx        the unit  -> _traversal.so
#   _tools.pyx            module-scope `from ...csgraph._tools import reconstruct_path` (compiled) -> _tools.so
#   _validation.py        module-scope `from ...csgraph._validation import validate_graph` (pure Python)
#   parameters.pxi        `include 'parameters.pxi'` in BOTH .pyx files (DTYPE/ITYPE + fused types + NULL_IDX)
# Image-provided (NOT vendored, per closure-walk rule 5): numpy, scipy.sparse (csr_matrix, issparse),
#   scipy.sparse._sputils (convert_pydata_sparse_to_scipy, is_pydata_spmatrix).
#
# STANDALONE-IMPORT binding: the vendored _tools/_validation/_traversal are registered into
# sys.modules under their REAL dotted names (scipy.sparse.csgraph._tools, ._validation, ._traversal)
# in dependency order, so _traversal's module-init absolute imports
#   `from scipy.sparse.csgraph._validation import validate_graph`
#   `from scipy.sparse.csgraph._tools     import reconstruct_path`
# bind to the VENDORED siblings, while `scipy.sparse` / `scipy.sparse._sputils` resolve to the
# image's real scipy (already in sys.modules). This proves the closure, not installed scipy 1.17.1,
# is the source of the unit's compiled kernels.
#
# NEGATIVE CONTROL: hide the vendored _tools.pyx -> the _tools.so build MUST fail (no kernel to
# co-build), proving _traversal's reconstruct_path dependency really resolves against the vendored
# closure and is not silently satisfied by installed scipy.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK=/tmp/traversal_build
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$HERE/closure" "$WORK/closure"      # copy ONLY the vendored closure into scratch
cd "$WORK/closure"
PKG=scipy/sparse/csgraph
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')

echo "tools: $(python3 --version 2>&1) | $(gcc-13 --version|head -1) | Cython $(python3 -c 'import Cython;print(Cython.__version__)') | numpy $(python3 -c 'import numpy;print(numpy.__version__)')"
# probe from /tmp (NOT the closure dir, which has an empty vendored scipy/ marker that shadows real scipy)
echo "installed scipy (must be IRRELEVANT to the kernel build): $(cd /tmp && python3 -c 'import scipy;print(scipy.__version__, scipy.__file__)' 2>&1)"

build_one () {  # $1 = module basename (no ext) ; cythonize+compile $PKG/$1.pyx -> $PKG/$1.so
  local m="$1"
  rm -f "$PKG/$m.c" "$PKG/$m.so"
  echo "--- cythonize $m (scipy bare -3) ---"
  cython -3 -I "$PKG" "$PKG/$m.pyx" -o "$PKG/$m.c" 2>&1 | grep -vE 'performance hint' | tail -8
  [ -f "$PKG/$m.c" ] || { echo "[$m] CYTHONIZE FAILED (no .c emitted)"; return 3; }
  gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp \
      -I"$PYINC" -I"$NPINC" "$PKG/$m.c" -o "$PKG/$m.so" 2>&1 | tail -12
  [ -f "$PKG/$m.so" ] || { echo "[$m] COMPILE FAILED (no .so emitted)"; return 4; }
  echo "[$m] so-bytes: $(stat -c%s "$PKG/$m.so")"
  return 0
}

import_confirm () {  # standalone-import the unit from the vendored-built kernels
  # The import test MUST run from a CWD with NO shadowing empty `scipy/` package, otherwise
  # `from scipy.sparse import csr_matrix` (in _tools/_validation) would resolve to the empty
  # vendored scipy marker instead of the image's real scipy. So stage the built kernels into a
  # flat dir and load them by ABSOLUTE path; register each under its real dotted name in
  # sys.modules in dependency order. `scipy.sparse` / `scipy.sparse._sputils` then bind to the
  # real installed scipy (already in sys.modules); the three kernels bind to the vendored ones.
  local STAGE=/tmp/traversal_stage
  rm -rf "$STAGE"; mkdir -p "$STAGE"
  cp "$PKG/_tools.so" "$PKG/_traversal.so" "$PKG/_validation.py" "$STAGE/"
  ( cd /tmp && OMP_NUM_THREADS=1 STAGE="$STAGE" python3 - <<'PY'
import importlib.util, sys, os
STAGE = os.environ["STAGE"]
def load(dotted, fname):
    path = os.path.join(STAGE, fname)
    spec = importlib.util.spec_from_file_location(dotted, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[dotted] = mod          # register BEFORE exec so siblings resolve to vendored
    spec.loader.exec_module(mod)
    return mod
# sanity: real scipy.sparse is reachable (image-provided, NOT vendored)
from scipy.sparse import csr_matrix  # noqa
import scipy; print("real scipy:", scipy.__version__, scipy.__file__)
# dependency order: _tools (compiled) -> _validation (pure py) -> _traversal (unit)
load("scipy.sparse.csgraph._tools",      "_tools.so")
load("scipy.sparse.csgraph._validation", "_validation.py")
m = load("scipy.sparse.csgraph._traversal", "_traversal.so")
fns = [x for x in dir(m) if not x.startswith("__")]
assert "connected_components" in fns and "breadth_first_order" in fns, fns
print("IMPORT-OK scipy.sparse.csgraph._traversal")
print("exported callables:", sorted(f for f in fns if not f.startswith("np")))
PY
  )
}

echo
echo "=== (1) POSITIVE: build the runtime .so closure in dep order, then standalone-import ==="
build_one _tools     || { echo "POSITIVE BUILD FAILED (_tools)"; exit 1; }
build_one _traversal || { echo "POSITIVE BUILD FAILED (_traversal)"; exit 1; }
echo "--- standalone-import (bare loader; OMP_NUM_THREADS=1) ---"
if import_confirm; then
  echo "POSITIVE IMPORT: PASS"
else
  echo "IMPORT FAILED"; exit 5
fi

echo
echo "=== (2) NEGATIVE CONTROL: hide vendored _tools.pyx -> _tools.so build MUST fail ==="
echo "    (proves _traversal's reconstruct_path kernel resolves from the VENDORED closure, not scipy 1.17.1)"
mv "$PKG/_tools.pyx" /tmp/_tools.pyx.hidden
rm -f "$PKG/_tools.c" "$PKG/_tools.so"
if build_one _tools; then
  echo "!!! NEGATIVE CONTROL FAILED: _tools.so built without the vendored _tools.pyx"
  mv /tmp/_tools.pyx.hidden "$PKG/_tools.pyx"
  exit 6
else
  echo "NEGATIVE CONTROL PASSED: _tools build fails without the vendored _tools.pyx (closure is the real source)."
fi
mv /tmp/_tools.pyx.hidden "$PKG/_tools.pyx"

echo
echo "=== VENDORED-CLOSURE BUILD-CONFIRM: PASS (positive build+import OK; negative control fails as required) ==="
