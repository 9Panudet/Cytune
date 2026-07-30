"""Step-1.3 A1 — criterion-3 kernel-share via callgrind CONSTRUCTION-SUBTRACTION (robust).

callgrind --toggle-collect cannot cleanly isolate a fused-cython kernel (the __pyx_fuse_* worker name
contains __pyx_pw, so any wrapper-matching toggle double-fires and cancels). Instead we attribute Ir by
OBJECT (.so / library) over a full-collection run, and subtract a construction-only baseline:

    per-call kernel Ir on object X = (Ir_X[run B: construct + N kernel calls] - Ir_X[run A: construct only]) / N

The kernel-share = Σ Ir on the unit's own cython .so(s) / Σ Ir over ALL objects (per call). The
NON-TUNABLE breakdown is reported by object: libopenblas* = BLAS (the lloyd/cd_fast/bglu DROP signature),
libm = transcendental, libpython/numpy-object = the per-call boundary. A pure-cython survivor → ~all Ir on
its .so, ~0 BLAS; a BLAS-bound DROP → large libopenblas Ir. Robust to fused dispatch AND to memory-bound
kernels (low absolute Ir is fine — the SHARE is what crit-3 asks). Measured at -O3 -march=native (worst case
for share). Recompute: callgrind_annotate the two committed .out files | this script.

Usage: crit3_callgrind_delta.py <unit> <so_basename[,..]> <N> <annotate_A.txt> <annotate_B.txt>
"""
import json
import re
import sys


def parse_objects(path):
    """Return {object_basename: total_self_Ir} + program_total from a callgrind_annotate file."""
    objs = {}
    total = None
    for line in open(path):
        if "PROGRAM TOTALS" in line:
            m = re.search(r"([\d,]+)", line)
            if m:
                total = int(m.group(1).replace(",", ""))
            continue
        m = re.match(r"\s*([\d,]+)\s+(?:\([\d.]+%\)\s+)?\S.*\[([^\]]+)\]\s*$", line)
        if not m:
            continue
        ir = int(m.group(1).replace(",", ""))
        obj = m.group(2).split("/")[-1]          # basename of the .so/exe
        objs[obj] = objs.get(obj, 0) + ir
    return objs, total


def classify(obj):
    o = obj.lower()
    if "openblas" in o or "blas" in o or "lapack" in o:
        return "BLAS"
    if o.startswith("libm") or o == "libm.so.6":
        return "libm"
    if "python" in o or o.startswith("libc") or "ld-linux" in o:
        return "py/libc"
    if "numpy" in o or "scipy" in o:
        return "numpy/scipy"
    return "other"


def main():
    unit, so_csv, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
    so_names = so_csv.split(",")
    A, tA = parse_objects(sys.argv[4])
    B, tB = parse_objects(sys.argv[5])
    objs = set(A) | set(B)
    delta = {o: max(0, B.get(o, 0) - A.get(o, 0)) for o in objs}     # per-N kernel-phase Ir by object
    total_delta = sum(delta.values())
    if total_delta <= 0:
        print("ERROR: empty kernel delta", file=sys.stderr); sys.exit(2)

    def is_unit_so(o):
        return any(s in o for s in so_names)
    so_ir = sum(ir for o, ir in delta.items() if is_unit_so(o))
    by_class = {}
    for o, ir in delta.items():
        if is_unit_so(o):
            continue
        by_class[classify(o)] = by_class.get(classify(o), 0) + ir
    # DIRECTIVE-TUNABLE = cython .so + libm transcendentals (exp/log/lgamma are tuned by the Θ flags
    # fast_math + march=native libmvec; the §1.3 Δ-probe empirically confirms the libm-heavy units
    # respond to flags). NON-tunable DROP signatures: BLAS (pre-compiled libopenblas _gemm/_dot) and
    # Python-OBJECT per-element overhead (py/libc dominating a memoryview-of-object hot loop).
    libm_ir = by_class.get("libm", 0)
    tunable = (so_ir + libm_ir) / total_delta
    so_share = so_ir / total_delta
    blas = by_class.get("BLAS", 0) / total_delta
    pyobj = by_class.get("py/libc", 0) / total_delta
    if blas >= 0.30 or tunable < 0.50:
        verdict = "DROP"
    elif tunable >= 0.90 and blas < 0.05:
        verdict = "PASS"
    else:
        verdict = "BORDERLINE"
    print(f"unit={unit} tunable_share={tunable:.2%} (.so {so_share:.2%} + libm {libm_ir/total_delta:.2%}) "
          f"BLAS={blas:.2%} pyobj={pyobj:.2%} => {verdict} "
          f"(tunable>=90%&BLAS<5%=PASS; BLAS>=30% or tunable<50%=DROP; -O3 -march=native; N={N})")
    print(f"  per-call kernel-phase Ir = {total_delta:,} ; .so = {so_ir:,} ; libm = {libm_ir:,}")
    print("  non-kernel Ir by class:")
    for c, ir in sorted(by_class.items(), key=lambda x: -x[1]):
        print(f"    {c:14} {ir:>14,}  ({ir/total_delta:5.1%})")
    print("JSON " + json.dumps({
        "unit": unit, "tunable_share": tunable, "kernel_so_share": so_share,
        "libm_share": libm_ir / total_delta, "blas_share": blas, "pyobj_share": pyobj,
        "verdict": verdict, "per_call_total_ir": total_delta, "unit_so_ir": so_ir, "libm_ir": libm_ir,
        "so_names": so_names, "N": N, "nonkernel_by_class": by_class,
        "config": "-O3 -march=native (worst-case share)",
        "method": "callgrind full-collection, construction-subtracted (run B[N calls] - run A[0 calls])"}))


if __name__ == "__main__":
    main()
