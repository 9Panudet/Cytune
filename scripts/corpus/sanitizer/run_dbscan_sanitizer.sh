#!/bin/bash
# G7 / CF-5 — per-unit C++ sanitize for dbscan_inner (Step 1.2; roadmap §3.5). First REAL
# per-unit C++ sanitize (the corpus kernel, not the mini-probe). Builds _dbscan_inner FROM
# THE VENDORED CLOSURE with the §3.5 ASan+UBSan profile (g++-13 --cplus, -ffp-contract
# explicit), then drives ONE dbscan_inner call (call#1 = the real DFS; the kernel mutates
# labels in place so a single fresh call is the valid sanitize unit) under ASan+UBSan, both
# operationally (detect_leaks=0) and in leak-audit (detect_leaks=1). LD_PRELOAD libasan +
# libstdc++ so ASan's __cxa_throw interceptor resolves at init.
#   podman run --rm -v ./data/corpus/sklearn/_dbscan_inner:/unit:ro,Z -v ./scripts:/probe:ro,Z \
#     localhost/motifbo-env:phase1 bash /probe/corpus/sanitizer/run_dbscan_sanitizer.sh
set -uo pipefail
WORK=/tmp/dbscan_san; rm -rf "$WORK"; mkdir -p "$WORK"
cp -r /unit/closure "$WORK/closure"; cd "$WORK/closure"
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')
PYX=sklearn/cluster/_dbscan_inner.pyx
echo "=== cythonize --cplus (as-shipped directives) + g++-13 ASan+UBSan (§3.5) ==="
cython -3 --cplus -X cdivision=True -X wraparound=False -X initializedcheck=False \
    -X nonecheck=False -X boundscheck=False -I . "$PYX" -o /tmp/_dbscan_inner.cpp 2>&1 \
    | grep -ivE 'hint|warning' | head -3
g++-13 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -ffp-contract=off \
    -shared -fPIC -std=c++14 -I"$PYINC" -I"$NPINC" /tmp/_dbscan_inner.cpp -o /tmp/_dbscan_inner.so 2>&1 | head -8
echo "BUILD: $([ -f /tmp/_dbscan_inner.so ] && echo OK $(stat -c%s /tmp/_dbscan_inner.so) bytes || echo FAIL)"
[ -f /tmp/_dbscan_inner.so ] || exit 4
LIBASAN=$(gcc-13 -print-file-name=libasan.so); LIBSTDCPP=$(g++-13 -print-file-name=libstdc++.so.6)
run(){
  echo "===== RUN dbscan_inner (detect_leaks=$1) ====="
  ASAN_OPTIONS=detect_leaks=$1:halt_on_error=1:exitcode=1 \
  UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1 \
  OMP_NUM_THREADS=1 LD_PRELOAD="$LIBASAN:$LIBSTDCPP" \
  python3 -c "
import sys; sys.path.insert(0,'/probe/corpus')
import importlib.util, corpus_drivers as cd
s=importlib.util.spec_from_file_location('_dbscan_inner','/tmp/_dbscan_inner.so')
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
ns={}; exec(cd.UNITS['dbscan_inner']['setup']({'n':200000,'avg_deg':10}), ns)
args=tuple(ns['args'])
m.dbscan_inner(*args)                       # the real DFS (call#1)
import numpy as np
lab=args[2]; print('dbscan_inner OK: n_clusters=%d  n_noise=%d'%(lab.max()+1,(lab==-1).sum()))
" 2>&1 | tail -25
  echo "exit=$?"
}
run 0
run 1
