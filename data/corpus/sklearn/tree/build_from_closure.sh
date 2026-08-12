#!/bin/bash
# Step 1.1.1 — FOLD-LEVEL vendored-closure build+IMPORT-confirm for the sklearn.tree fold.
# The 3 tree corpus units (_tree, _criterion, _splitter) share ONE runtime .so cluster
# (_utils, _quad_tree, _random + _typedefs) and cannot be built independently, so they are
# vendored as a fold-level closure. Build-confirm = standalone IMPORT (§4), under the
# REFERENCE sklearn directive set (the as-shipped meson config: cdivision=True etc.).
# Run in-container X' (:phase1):
#   podman run --rm -v <tree_dir>:/unit:ro,Z localhost/motifbo-env:phase1 bash /unit/build_from_closure.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
R=/tmp/tree_build; rm -rf "$R"; mkdir -p "$R"; cp -r "$HERE/closure" "$R/closure"; cd "$R/closure"
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')
# sklearn as-shipped reference directives (sklearn/meson.build:184-185). cdivision=True is REQUIRED:
# the tree kernels index with integer division (feature_values[n/2]); cdivision=False is infeasible
# (a real §3.5 feasibility-0 of the kernel, not patched).
DIRS="-X language_level=3 -X boundscheck=False -X wraparound=False -X initializedcheck=False -X nonecheck=False -X cdivision=True"
echo "tools: $(python3 --version 2>&1) | $(gcc-13 --version|head -1) | Cython $(python3 -c 'import Cython;print(Cython.__version__)') | numpy $(python3 -c 'import numpy;print(numpy.__version__)')"
echo "reference directives: $DIRS"

b () {  # $1 = pyx rel path ; $2 = c|cpp  (.so lands next to the .pyx)
  local pyx="$1" mode="$2"; local d; d="$(dirname "$pyx")"; local m; m="$(basename "$pyx" .pyx)"
  if [ "$mode" = cpp ]; then
    cython -3 $DIRS --cplus -I . "$pyx" -o "$d/$m.cpp" 2>/dev/null || { echo "  CYTHONIZE-FAIL $m"; return 3; }
    g++-13 -shared -fPIC -O1 -std=c++14 -ffp-contract=fast -fopenmp -I"$PYINC" -I"$NPINC" "$d/$m.cpp" -o "$d/$m.so" 2>&1 | tail -3
  else
    cython -3 $DIRS -I . "$pyx" -o "$d/$m.c" 2>/dev/null || { echo "  CYTHONIZE-FAIL $m"; return 3; }
    gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp -I"$PYINC" -I"$NPINC" "$d/$m.c" -o "$d/$m.so" 2>&1 | tail -3
  fi
  [ -f "$d/$m.so" ] && echo "  built $m.so ($(stat -c%s "$d/$m.so") B)" || { echo "  COMPILE-FAIL $m"; return 4; }
}

echo "=== build the runtime .so cluster (dep order) ==="
b sklearn/utils/_random.pyx c          || exit 1
b sklearn/tree/_utils.pyx c             || exit 1
b sklearn/neighbors/_quad_tree.pyx c    || exit 1
b sklearn/tree/_criterion.pyx cpp       || exit 1
b sklearn/tree/_splitter.pyx cpp        || exit 1
b sklearn/tree/_tree.pyx cpp            || exit 1

echo "=== IMPORT-CONFIRM the 3 tree-fold units (the §4 gate) ==="
fail=0
for mod in sklearn.tree._tree sklearn.tree._criterion sklearn.tree._splitter; do
  if OMP_NUM_THREADS=1 PYTHONPATH="$R/closure" python3 -c "import $mod" 2>/tmp/imperr; then
    echo "  IMPORT-OK  $mod"
  else
    echo "  IMPORT-FAIL $mod :: $(tail -1 /tmp/imperr)"; fail=1
  fi
done
[ "$fail" = 0 ] && echo "=== TREE FOLD BUILD-CONFIRM: PASS (3 units import from the vendored cluster) ===" || { echo "=== TREE FOLD BUILD-CONFIRM: FAIL ==="; exit 5; }
