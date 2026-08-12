"""Step-1.3 A1 — aggregate the callgrind criterion-3 kernel-shares into the survive/drop table.

Reads results/characterization/crit3/*__crit3.json (committed callgrind construction-subtracted shares)
and prints the per-unit directive-tunable share (cython .so + flag-tunable libm), the non-tunable
breakdown (BLAS = libopenblas, pyobj = per-element Python-object overhead), and the §4.2 criterion-3
verdict. Survivors should be tunable (PASS/BORDERLINE, ~0 BLAS); BLAS/object DROPs show the library
signature. All MEASURED at -O3 -march=native (worst case for share). Recompute: this script over the raw.

Usage: crit3_aggregate.py [dir=results/characterization/crit3]
"""
import glob
import json
import os
import sys


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "results/characterization/crit3"
    units = []
    for p in sorted(glob.glob(os.path.join(d, "*__crit3.json"))):
        units.append(json.load(open(p)))
    units.sort(key=lambda x: -x.get("tunable_share", 0))
    hdr = f"{'module':24} {'tunable%':>8} {'.so%':>6} {'libm%':>6} {'BLAS%':>6} {'pyobj%':>7} {'verdict':>10}"
    print(hdr); print("-" * len(hdr))
    for u in units:
        print(f"{u['module']:24} {u['tunable_share']*100:7.1f}% {u['kernel_so_share']*100:5.1f}% "
              f"{u['libm_share']*100:5.1f}% {u['blas_share']*100:5.1f}% {u['pyobj_share']*100:6.1f}% "
              f"{u['verdict']:>10}")
    surv = [u for u in units if u["verdict"] in ("PASS", "BORDERLINE")]
    drop = [u for u in units if u["verdict"] == "DROP"]
    print(f"\n  tunable (PASS/BORDERLINE): {len(surv)}  |  DROP: {len(drop)}")
    print(f"  config: -O3 -march=native (worst-case share); construction-subtracted; threads pinned")
    if drop:
        print("  DROP mechanisms:")
        for u in drop:
            sig = "BLAS" if u["blas_share"] >= 0.30 else "object/py" if u["tunable_share"] < 0.5 else "?"
            print(f"    {u['module']:22} tunable {u['tunable_share']:.0%}, BLAS {u['blas_share']:.0%} -> {sig}")


if __name__ == "__main__":
    main()
