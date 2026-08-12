#!/bin/bash
# Mini-I-3 C++ extension probe (Step 1.1.1, condition 3). Run in image X' (:phase1):
#   podman run --rm -v <dir-with-cpp_probe.pyx>:/work:Z localhost/motifbo-env:phase1 \
#     bash /work/run_cpp_sanitizer_probe.sh
# Builds the C++ Cython probe with the §3.5 sanitizer profile via g++-13 and runs it
# under ASan+UBSan, BOTH operationally (detect_leaks=0) and in leak-audit (detect_leaks=1).
# KEY: LD_PRELOAD must include libstdc++.so.6 so ASan's __cxa_throw interceptor resolves
# at init (without it, the first C++ exception aborts ASan: CHECK real___cxa_throw != 0).
set -uo pipefail
cd /work
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')
echo "=== build (cython --cplus -> g++-13 ASan+UBSan; §3.5 profile, -ffp-contract explicit) ==="
cython -3 --cplus cpp_probe.pyx -o cpp_probe.cpp 2>&1 | grep -ivE 'hint|warning' | head -3
g++-13 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -ffp-contract=fast \
    -shared -fPIC -std=c++14 -I"$PYINC" -I"$NPINC" cpp_probe.cpp -o cpp_probe.so 2>&1 | head -8
echo "BUILD: $([ -f cpp_probe.so ] && echo OK $(stat -c%s cpp_probe.so) bytes || echo FAIL)"
LIBASAN=$(gcc-13 -print-file-name=libasan.so)
LIBSTDCPP=$(g++-13 -print-file-name=libstdc++.so.6)
echo "libasan: $LIBASAN"; echo "libstdc++: $LIBSTDCPP"
run(){
  echo "===== RUN (detect_leaks=$2, preload asan+libstdc++) ====="
  ASAN_OPTIONS=detect_leaks=$2:halt_on_error=1:exitcode=1 \
  UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1 \
  OMP_NUM_THREADS=1 LD_PRELOAD="$LIBASAN:$LIBSTDCPP" \
  python3 -c "
import importlib.util
s=importlib.util.spec_from_file_location('cpp_probe','/work/cpp_probe.so')
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
print('use_vector(1_000_000) sum =', m.use_vector(1000000))
for fn in ['raise_out_of_range','raise_length_error','raise_invalid_argument']:
    try:
        getattr(m,fn)(); print(fn,'-> NO EXCEPTION (!)')
    except BaseException as e:
        print(fn,'->', type(e).__module__+'.'+type(e).__qualname__)
" 2>&1 | tail -40
  echo "exit=$?"
}
run operational 0
run leak-audit 1
