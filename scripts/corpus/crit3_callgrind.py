"""Criterion-3 NATIVE-SYMBOL cross-validation via callgrind (perf substitute — perf is
absent from the pinned image + host, host perf_event_paranoid=2). callgrind gives exact,
deterministic per-symbol instruction (Ir) attribution. Run in the :phase1-tools sidecar
under: valgrind --tool=callgrind --collect-atstart=no --toggle-collect=*<kernel>*  so ONLY
the kernel call (+ its callees) is collected; one-time input construction is excluded.
The criterion-3 share = (Ir in the cython __pyx_* kernel symbols) / (total collected Ir);
numpy reductions + malloc inside the call are non-kernel (the Θ directives can't tune them).

Usage: crit3_callgrind.py <unit_key> <so_path> <N>
"""
import importlib.util
import sys

sys.path.insert(0, "/probe/corpus")
import corpus_drivers as cd


def main():
    unit_key, so, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
    u = cd.UNITS[unit_key]
    # trial scale: with construction-subtraction (run B - run A) the per-call kernel .so Ir (millions+)
    # dominates the fixed ~15k python-wrapper dispatch, so the SHARE is scale-robust; trial keeps the
    # callgrind run fast. (N=0 => construction-only baseline; N>0 => construction + N kernel calls.)
    scale = dict(u.get("crit3_scale") or u["trial"])
    ns = {}
    exec(u["setup"](scale), ns)                   # one-time construction
    args = tuple(ns["args"]); kwargs = dict(ns.get("kwargs", {}))
    if u.get("preimport"):                         # wrapper units: break the circular import first
        __import__(u["preimport"])
    spec = importlib.util.spec_from_file_location(u["mod"], so)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    fn = getattr(m, u["kernel"])
    for _ in range(N):    # collection is toggled on the __pyx_pw_<kernel> py-wrapper (run.py); with
        fn(*args, **kwargs)   # N=2, call#1 toggles ON (full kernel collected), call#2 toggles OFF
    print(f"callgrind driver done: {unit_key} N={N} trial={u['trial']}")


if __name__ == "__main__":
    main()
