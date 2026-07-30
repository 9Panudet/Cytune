"""Step-1.3 A1 — package-import callgrind driver for multi-module units (elkan, predictor).

Same role as crit3_callgrind.py but the kernel is reached via a PACKAGE import from the cobuilt
closure (its .so relative-imports a sibling vendored .so, so it cannot be bare-loaded). The cython
hot work for these units spans the unit .so AND its co-built helper (elkan: _k_means_common's
_euclidean_dense_dense; predictor: _bitset/common) — all __pyx_* symbols count as kernel in the share.

Usage (under valgrind, in tools image): crit3_callgrind_pkg.py <unit_key> <closure_dir> <N>
"""
import sys

sys.path.insert(0, "/probe/corpus")


def main():
    unit_key, closure_dir, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
    sys.path.insert(0, closure_dir)
    import importlib
    import corpus_drivers as cd
    u = cd.UNITS[unit_key]
    m = importlib.import_module(u["pkg_module"])
    fn = getattr(m, u["kernel"])
    ns = {}
    scale = dict(u.get("crit3_scale") or u["trial"])   # trial; construction-subtracted in run.py
    exec(u["setup"](scale), ns)                        # construction (the N=0 baseline isolates it)
    args = tuple(ns["args"]); kwargs = dict(ns.get("kwargs", {}))
    for _ in range(N):    # toggle on __pyx_pw_<kernel> py-wrapper (run.py); N=2 => collect call#1
        fn(*args, **kwargs)
    print(f"callgrind pkg driver done: {unit_key} N={N} trial={u['trial']}")


if __name__ == "__main__":
    main()
