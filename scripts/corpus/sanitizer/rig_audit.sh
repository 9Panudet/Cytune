#!/bin/bash
# Mini-I-3 C++ RIG audit (Step 1.1.1 cond 3). Run in X' (:phase1):
#   podman run --rm -v <dir-with-cpp_rig_probe.pyx>:/work:Z \
#     -v $PWD/data/env/sanitizer:/supp:ro,Z localhost/motifbo-env:phase1 bash /work/rig_audit.sh
# Validates: (a) clean STL no FP, (b) C++->Python exception map, (c) NON-VACUITY (rig catches
# heap-OOB / iterator-invalidation UAF / UBSan vptr), (d) leak policy (detect_leaks=1 +
# CPython suppressed detects STL leaks). KEY: LD_PRELOAD must include libstdc++.so.6 so ASan's
# __cxa_throw interceptor binds at init (else first C++ throw aborts ASan).
set -uo pipefail
cd /work
PYINC=$(python3 -c 'import sysconfig;print(sysconfig.get_path("include"))')
NPINC=$(python3 -c 'import numpy;print(numpy.get_include())')
echo "=== build (cython --cplus -> g++-13 ASan+UBSan, -ffp-contract explicit) ==="
cython -3 --cplus cpp_rig_probe.pyx -o cpp_rig_probe.cpp 2>&1 | grep -ivE 'hint|warning' | head -3
g++-13 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -ffp-contract=fast \
    -shared -fPIC -std=c++14 -I"$PYINC" -I"$NPINC" cpp_rig_probe.cpp -o cpp_rig_probe.so 2>&1 | head -6
echo "BUILD: $([ -f cpp_rig_probe.so ] && echo OK || echo FAIL)"
LIBASAN=$(gcc-13 -print-file-name=libasan.so)
LIBSTDCPP=$(g++-13 -print-file-name=libstdc++.so.6)
PRE="$LIBASAN:$LIBSTDCPP"
call(){ # python-snippet  detect_leaks  lsan_supp(optional)
  local snip="$1" dl="$2" supp="${3:-}"
  local lsan=""; [ -n "$supp" ] && lsan="LSAN_OPTIONS=suppressions=$supp"
  env ASAN_OPTIONS=detect_leaks=$dl:halt_on_error=1:exitcode=1 \
      UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1 $lsan \
      OMP_NUM_THREADS=1 LD_PRELOAD="$PRE" \
      python3 -c "
import importlib.util
s=importlib.util.spec_from_file_location('cpp_rig_probe','/work/cpp_rig_probe.so')
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
$snip
" 2>&1; echo "[exit=$?]"
}
echo; echo "===== (a)(b) CLEAN operational run (detect_leaks=0) ====="
call "
print('clean_stl =', m.clean_stl())
for fn in ['raise_out_of_range','raise_length_error','raise_invalid_argument']:
    try: getattr(m,fn)()
    except BaseException as e: print(fn,'->',type(e).__module__+'.'+type(e).__qualname__)
" 0 | grep -E 'clean_stl|raise_|exit=|ERROR|CHECK|runtime error'
echo; echo "===== (c) NON-VACUITY: rig must CATCH each real C++ bug ====="
for b in bug_oob:heap-buffer-overflow bug_uaf:heap-use-after-free bug_vptr:'runtime error|vptr|member call'; do
  fn="${b%%:*}"; pat="${b##*:}"
  out=$(call "m.$fn()" 0)
  if echo "$out" | grep -qiE "$pat"; then verdict="CAUGHT"; else verdict="*** MISSED ***"; fi
  ec=$(echo "$out" | grep -oE 'exit=[0-9]+' | tail -1)
  hit=$(echo "$out" | grep -oiE "$pat" | head -1)
  printf "  %-9s -> %-14s (%s, %s)\n" "$fn" "$verdict" "$hit" "$ec"
done
echo; echo "===== (d) LEAK POLICY: detect_leaks=1 + CPython suppressed ====="
echo "-- clean run (expect 0 UNsuppressed leaks if CPython fully covered) --"
call "print('clean_stl =', m.clean_stl())" 1 /supp/lsan_cpython.supp | grep -E 'clean_stl|SUMMARY|exit=|Direct leak|Indirect leak' | head -8
echo "-- stl_leak() (expect LSan to REPORT the STL operator-new leak) --"
call "print('stl_leak =', m.stl_leak())" 1 /supp/lsan_cpython.supp | grep -E 'stl_leak|SUMMARY|Direct leak of|operator new|exit=' | head -10
