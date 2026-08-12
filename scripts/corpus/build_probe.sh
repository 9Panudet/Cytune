#!/bin/bash
# Step 1.1.1 — per-unit build-isolatability probe (criterion §4.2-3).
# Compile ONE vendored unit in true isolation, IN-CONTAINER, against the pinned
# numpy 2.4.6 + Cython 3.2.5 + gcc-13, with OMP_NUM_THREADS=1 and explicit -ffp-contract.
# Run via: podman run --rm -v <sdist_scratch>:/dl:Z localhost/motifbo-env:phase0 \
#            bash /dl/build_probe.sh <pyx_rel_path> <sdist_root_dir_under_/dl> [--cplus]
#
# Proven (1.1.1): sklearn 1.5.2 utils/sparsefuncs_fast.pyx builds + standalone-imports clean.
# Coupled units additionally need their sibling-Cython-module .so closure built and a minimal
# importable package context (stub sklearn/__check_build; provide sklearn/exceptions.py); C++
# units (e.g. tree/_tree.pyx: libcpp + cdef extern "<algorithm>") require --cplus + g++.
set -uo pipefail
PYX="${1:?need .pyx rel path}"
ROOT="${2:?need sdist root dir under /dl}"
CPLUS="${3:-}"
MOD="$(basename "$PYX" .pyx)"
cd "/dl/$ROOT" || exit 2
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')
echo "PYINC=$PYINC"
echo "NPINC=$NPINC"
echo "tools: $(python3 --version 2>&1) | $(gcc --version|head -1) | Cython $(python3 -c 'import Cython;print(Cython.__version__)') numpy $(python3 -c 'import numpy;print(numpy.__version__)')"
if command -v cython >/dev/null 2>&1; then CY="cython"; else CY="python3 -m cython"; fi
mkdir -p /tmp/cbuild && rm -f /tmp/cbuild/$MOD.*

if [ "$CPLUS" = "--cplus" ]; then
  EXT=cpp; CYFLAGS="--cplus"; CC=g++-13; STD="-std=c++14"
else
  EXT=c; CYFLAGS=""; CC=gcc-13; STD=""
fi
echo "=== 1) cythonize $PYX (mode=${EXT}, -I . resolves relative cimports) ==="
$CY -3 $CYFLAGS -I . "$PYX" -o /tmp/cbuild/$MOD.$EXT 2>&1 | grep -vE "performance hint" | tail -12
ls -l /tmp/cbuild/$MOD.$EXT 2>/dev/null | awk '{print "  gen-bytes",$5}'
echo "=== 2) $CC -O3 -march=native -ffp-contract=fast -fopenmp $STD ==="
$CC -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp $STD \
    -I"$PYINC" -I"$NPINC" /tmp/cbuild/$MOD.$EXT -o /tmp/cbuild/$MOD.so 2>&1 | tail -15
ls -l /tmp/cbuild/$MOD.so 2>/dev/null | awk '{print "  so-bytes",$5}'
echo "=== 3) STANDALONE import (bare loader; coupled units may need a minimal package ctx) ==="
OMP_NUM_THREADS=1 python3 -c "
import importlib.util, os
p='/tmp/cbuild/$MOD.so'
assert os.path.exists(p), 'NO .so BUILT'
s=importlib.util.spec_from_file_location('$MOD', p)
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
print('IMPORT OK; exported:', [x for x in dir(m) if not x.startswith('_')][:12])
"
