#!/usr/bin/env bash
# Motif+BO Step 0.4.1 — sanitizer grounding probe. Reproducible evidence for the
# CPython suppression policy (data/env/sanitizer/SANITIZER_POLICY.md). Runs INSIDE
# the pinned container:
#   podman run --rm -v ./scripts:/probe:ro,Z localhost/motifbo-env:phase0 \
#     bash /probe/sanitizer_probe.sh
# Builds three Cython kernels (clean / candidate-leak / out-of-bounds) with the
# ASan+UBSan profile and exercises the leak/safety behaviour the policy rests on.
set -uo pipefail
cd "$(mktemp -d)"
PYINC="$(python3.12 -c 'import sysconfig; print(sysconfig.get_paths()["include"])')"
ASANLIB="$(gcc -print-file-name=libasan.so)"
SAN="-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -shared -fPIC"

build() {  # build <stem> ; reads <stem>.pyx
  cython -3 "$1.pyx" -o "$1.c" 2>/dev/null
  gcc $SAN -I"$PYINC" "$1.c" -o "$1.so"
}
loader() {  # loader <stem> -> writes run_<stem>.py
  cat > "run_$1.py" <<PY
import importlib.util, numpy as np
spec = importlib.util.spec_from_file_location("$1", "$PWD/$1.so")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
$2
PY
}

cat > clean.pyx <<'PYX'
# cython: language_level=3
cimport cython
@cython.boundscheck(False)
@cython.wraparound(False)
def kernel(double[::1] x):
    cdef Py_ssize_t i
    cdef double s = 0.0
    for i in range(x.shape[0]):
        s += x[i] * 2.0
    return s
PYX
cat > leaky.pyx <<'PYX'
# cython: language_level=3
from libc.stdlib cimport malloc
def kernel(int n):
    cdef void* p = malloc(n * 1024)   # never freed: a genuine candidate leak
    return n
PYX
cat > oob.pyx <<'PYX'
# cython: language_level=3
cimport cython
@cython.boundscheck(False)
@cython.wraparound(False)
def kernel(double[::1] x):
    x[x.shape[0] + 3] = 1.0           # deliberate out-of-bounds write
    return 0
PYX
build clean; build leaky; build oob
loader clean 'print("clean result:", m.kernel(np.arange(8, dtype=np.float64)))'
loader leaky 'm.kernel(64)'
loader oob   'm.kernel(np.zeros(8, dtype=np.float64))'

cat > lsan_module.supp <<'S'
leak:python3.12
S
cat > lsan_fn.supp <<'S'
leak:PyObject_Malloc
leak:PyMem_
leak:PyUnicode_
leak:_PyObject_GC
S

echo "### A. CPython by-design leaks (detect_leaks=1, no suppression)"
LD_PRELOAD="$ASANLIB" ASAN_OPTIONS=detect_leaks=1 python3.12 run_clean.py 2>&1 \
  | grep -iE "ERROR: LeakSanitizer|SUMMARY|PyUnicode|PyImport|_PyEval" | head -6
echo
echo "### D. operational mode detect_leaks=0 -> clean (full stderr)"
LD_PRELOAD="$ASANLIB" ASAN_OPTIONS=detect_leaks=0 python3.12 run_clean.py 2>&1
echo
echo "### C. UBSan on the candidate C (detect_leaks=0, halt_on_error=0)"
LD_PRELOAD="$ASANLIB" ASAN_OPTIONS=detect_leaks=0 \
  UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=0 python3.12 run_clean.py 2>&1 \
  | grep -iE "runtime error|undefined" | head -5 || true
echo "(UBSan: no reports if nothing printed above)"
echo
echo "### F. module-level leak:python3.12 OVER-suppresses the candidate leak"
echo -n "  candidate leak reported? "
LD_PRELOAD="$ASANLIB" ASAN_OPTIONS=detect_leaks=1 LSAN_OPTIONS=suppressions=lsan_module.supp \
  python3.12 run_leaky.py 2>&1 | grep -qiE "Direct leak" && echo YES || echo "NO (over-suppressed)"
echo
echo "### H. function-level patterns UNDER-suppress CPython (residual remains)"
LD_PRELOAD="$ASANLIB" ASAN_OPTIONS=detect_leaks=1 LSAN_OPTIONS=suppressions=lsan_fn.supp \
  python3.12 run_clean.py 2>&1 | grep -iE "SUMMARY" | head -2
echo
echo "### G. memory-safety gate: heap-buffer-overflow is CAUGHT (detect_leaks=0)"
LD_PRELOAD="$ASANLIB" ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 python3.12 run_oob.py 2>&1 \
  | grep -iE "ERROR: AddressSanitizer|SUMMARY.*overflow" | head -3
echo "  oob child exit code: $(LD_PRELOAD="$ASANLIB" ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 python3.12 run_oob.py >/dev/null 2>&1; echo $?)"
