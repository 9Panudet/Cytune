"""Step-1.3 A1 — parse callgrind_annotate output into the criterion-3 kernel-share.

callgrind (run with --collect-atstart=no --toggle-collect=*<kernel>*) collects Ir ONLY inside the
kernel call subtree; one-time input construction is excluded. The §4.2 criterion-3 share is

    kernel_share = Σ Ir[functions in the unit's cython .so(s)] / Ir[PROGRAM TOTALS]

i.e. the fraction of in-kernel instructions that live in the Θ-tunable cython code (__pyx_*), vs
non-tunable callees (numpy reductions, libc malloc/memset, libopenblas, libm). Measured at the
FASTEST config (-O3 -march=native) — the worst case for share (the compiler shrinks the cython side
most, inflating the relative non-kernel cost), so the golden-config share is >= this.

Recompute: callgrind_annotate --threshold=100 --inclusive=no <callgrind.out> | \
           crit3_callgrind_share.py <unit> <so_basename[,so2,...]>
Reads the annotate text on stdin; prints the share + a JSON line for committing.
"""
import json
import re
import sys


def main():
    unit = sys.argv[1]
    so_names = sys.argv[2].split(",")        # cython .so basenames that count as "kernel"
    total = None
    kernel_ir = 0
    nonkernel = []
    for line in sys.stdin:
        # PROGRAM TOTALS line: "12,345,678  (100.0%)  PROGRAM TOTALS"  (or without pct)
        if "PROGRAM TOTALS" in line:
            m = re.search(r"([\d,]+)", line)
            if m:
                total = int(m.group(1).replace(",", ""))
            continue
        # per-function line: "  50,000,000  (40.5%)  file:function [object]"
        m = re.match(r"\s*([\d,]+)\s+(?:\([\d.]+%\)\s+)?(\S.*)$", line)
        if not m:
            continue
        ir = int(m.group(1).replace(",", ""))
        desc = m.group(2)
        is_kernel = ("__pyx_" in desc) or any(s in desc for s in so_names)
        if is_kernel:
            kernel_ir += ir
        elif ir > 0:
            nonkernel.append((ir, desc.strip()[:80]))

    if not total:
        print("ERROR: no PROGRAM TOTALS found", file=sys.stderr)
        sys.exit(2)
    share = kernel_ir / total
    nonkernel.sort(reverse=True)
    verdict = "PASS" if share >= 0.90 else ("BORDERLINE" if share >= 0.85 else "DROP")
    print(f"unit={unit} kernel_Ir={kernel_ir:,} total_Ir={total:,} "
          f"KERNEL-SHARE={share:.2%} => {verdict} (>=90% PASS; -O3 -march=native worst-case)")
    print("top non-kernel callees (non-tunable Ir):")
    for ir, desc in nonkernel[:6]:
        print(f"  {ir:>15,}  ({ir/total:5.1%})  {desc}")
    print("JSON " + json.dumps({"unit": unit, "kernel_ir": kernel_ir, "total_ir": total,
                                "kernel_share": share, "verdict": verdict,
                                "config": "-O3 -march=native (fastest; worst-case share)",
                                "so_names": so_names,
                                "top_nonkernel": [{"ir": ir, "fn": d} for ir, d in nonkernel[:8]]}))


if __name__ == "__main__":
    main()
