#!/bin/bash
# Step 1.1.1 — vendored-closure build+IMPORT-confirm for sklearn.manifold._barnes_hut_tsne.
# Most-coupled unit: _barnes_hut_tsne -> _quad_tree (cdef class) -> tree/_utils (safe_realloc), with the
# tree cluster (_criterion/_splitter/_tree) reachable via the cimport graph. So the runtime .so closure is
# the FULL tree cluster + _quad_tree + the unit. Build-confirm = standalone IMPORT (§4), REFERENCE sklearn
# directives (cdivision=True). Manifold's FOLD membership is additionally gated on the 1.1.3 t-SNE
# determinism proof (kernel-level driving; init='pca' + fixed seed) — that gate is NOT discharged here.
#   podman run --rm -v <unit_dir>:/unit:ro,Z localhost/motifbo-env:phase1 bash /unit/build_from_closure.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
R=/tmp/bht_unit; rm -rf "$R"; mkdir -p "$R"; cp -r "$HERE/closure" "$R/closure"; cd "$R/closure"
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')
DIRS="-X language_level=3 -X boundscheck=False -X wraparound=False -X initializedcheck=False -X nonecheck=False -X cdivision=True"
echo "tools: $(python3 --version 2>&1) | $(gcc-13 --version|head -1) | Cython $(python3 -c 'import Cython;print(Cython.__version__)') | numpy $(python3 -c 'import numpy;print(numpy.__version__)')"
echo "reference directives: $DIRS"
b () { local pyx="$1" mode="$2"; local d; d="$(dirname "$pyx")"; local m; m="$(basename "$pyx" .pyx)"
  if [ "$mode" = cpp ]; then
    cython -3 $DIRS --cplus -I . "$pyx" -o "$d/$m.cpp" 2>/dev/null || { echo "  CYTHONIZE-FAIL $m"; return 3; }
    g++-13 -shared -fPIC -O1 -std=c++14 -ffp-contract=fast -fopenmp -I"$PYINC" -I"$NPINC" "$d/$m.cpp" -o "$d/$m.so" 2>&1 | tail -3
  else
    cython -3 $DIRS -I . "$pyx" -o "$d/$m.c" 2>/dev/null || { echo "  CYTHONIZE-FAIL $m"; return 3; }
    gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp -I"$PYINC" -I"$NPINC" "$d/$m.c" -o "$d/$m.so" 2>&1 | tail -3
  fi
  [ -f "$d/$m.so" ] && echo "  built $m.so ($(stat -c%s "$d/$m.so") B)" || { echo "  COMPILE-FAIL $m"; return 4; }
}
echo "=== build the runtime .so closure (dep order) ==="
b sklearn/utils/_random.pyx c        || exit 1
b sklearn/tree/_utils.pyx c          || exit 1
b sklearn/neighbors/_quad_tree.pyx c || exit 1
b sklearn/tree/_criterion.pyx cpp    || exit 1
b sklearn/tree/_splitter.pyx cpp     || exit 1
b sklearn/tree/_tree.pyx cpp         || exit 1
b sklearn/manifold/_barnes_hut_tsne.pyx c || exit 1
echo "=== IMPORT-CONFIRM sklearn.manifold._barnes_hut_tsne (the §4 gate) ==="
if OMP_NUM_THREADS=1 PYTHONPATH="$R/closure" python3 -c "
import sklearn.manifold._barnes_hut_tsne as m
assert callable(getattr(m,'gradient',None)), 'gradient missing'
print('  unit .so:', m.__file__); print('  IMPORT-OK sklearn.manifold._barnes_hut_tsne; gradient callable')
"; then
  echo "=== MANIFOLD BUILD-CONFIRM: PASS (fold membership still pending 1.1.3 t-SNE determinism) ==="
else
  echo "=== MANIFOLD BUILD-CONFIRM: FAIL ==="; exit 5
fi
