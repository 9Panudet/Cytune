"""Criterion-3 (>=90% kernel share, roadmap §4.4 / Step 1.2.1) profiler.

Measured at the FASTEST build config (-O3 -march=native; worst-case for kernel share —
a faster kernel makes any fixed wrapper overhead a relatively larger fraction). cProfile cannot see inside a cython `def` (not compiled with profile=True): the cdef hot
loop is INVISIBLE, so cProfile's total_tt captures ONLY the Python/numpy-visible overhead
(numpy reductions, the def-wrapper prologue), while the true kernel time lives in the
unprofiled wall. We therefore measure BOTH on the same N: wall_total (unprofiled) and
cprofile_total (Python-visible overhead, conservatively ALL counted as non-kernel since it
is not the directive-tuned cython), and report kernel_share = (wall_total - cprofile_total)
/ wall_total. Counting numpy reductions as non-kernel is correct for criterion-3: tuning
the Cython Θ directives cannot speed up numpy's C reduce. Wrapper-driven units (tree via
fit) need perf symbol profiling instead (the C build is invisible to cProfile) — per-archetype.

Usage: crit3_probe.py <unit_key> <so_path> <N>
"""
import cProfile
import importlib.util
import pstats
import sys
import time

sys.path.insert(0, "/probe/corpus")
import corpus_drivers as cd


def load(so, mod):
    spec = importlib.util.spec_from_file_location(mod, so)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    unit_key, so, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
    u = cd.UNITS[unit_key]
    scale = dict(u["trial"])
    if len(sys.argv) >= 7:                    # optional golden-scale override: ns nf dens
        scale = {"n_samples": int(sys.argv[4]), "n_features": int(sys.argv[5]),
                 "density": float(sys.argv[6])}
    ns = {}
    exec(u["setup"](scale), ns)
    args = tuple(ns["args"]); kwargs = dict(ns.get("kwargs", {}))
    m = load(so, u["mod"]); fn = getattr(m, u["kernel"])

    for _ in range(3):                       # warmup (outside the measured region)
        fn(*args, **kwargs)

    t0 = time.perf_counter_ns()
    for _ in range(N):
        fn(*args, **kwargs)
    wall_total = (time.perf_counter_ns() - t0) / 1e9
    per_call_ms = wall_total / N * 1e3

    pr = cProfile.Profile(); pr.enable()
    for _ in range(N):
        fn(*args, **kwargs)
    pr.disable()
    st = pstats.Stats(pr); cprofile_total = st.total_tt   # Python/numpy-visible overhead only

    rows = sorted(((tt, ct, file, name)
                   for (file, line, name), (cc, nc, tt, ct, callers) in st.stats.items()),
                  reverse=True)
    print(f"unit={unit_key} kernel={u['kernel']} N={N} per-call={per_call_ms:.3f}ms "
          f"scale={scale}")
    print(f"  wall_total={wall_total:.4f}s  cprofile_visible(non-kernel)={cprofile_total:.4f}s")
    print("  top Python/numpy-visible frames (the non-kernel overhead; cdef kernel is invisible):")
    for tt, ct, file, name in rows[:8]:
        print(f"    tot={tt:.4f}s cum={ct:.4f}s  {name}  [{file.split('/')[-1]}]")
    share = (wall_total - cprofile_total) / wall_total if wall_total > 0 else 0.0
    print(f"KERNEL-SHARE = (wall - python_visible)/wall = {share*100:.2f}%  "
          f"=> {'PASS' if share >= 0.90 else 'DROP'} (>=90%, worst-case config -O3 -march=native)")


if __name__ == "__main__":
    main()
