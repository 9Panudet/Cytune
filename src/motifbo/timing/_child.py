"""RUNTIME_NS subprocess driver (Step 0.2.2; roadmap §5.1, §4.4, §3.2(2)).

Runs in a FRESH process per candidate (FTZ/DAZ containment, §3.2(2)) and is invoked
by file path, stdlib-only, so it needs no package on sys.path. Protocol: argv[1] is a
JSON spec file; the result JSON is written to spec["out"] — stdout is never the data
channel (kernel prints must not corrupt results).

spec: module_path, kernel, setup_code (defines `args` tuple and optional `kwargs`
      dict), reps, warmup (default 5), out.
result: samples_ns[reps], reps, warmup, import_ns, setup_ns, child_pid.

Timing-region law (D2 guard): perf_counter_ns is read IMMEDIATELY around the kernel
call and nothing else. Import and input construction are measured separately, for
evidence that they happened outside the region. No bare imports timed, ever.
"""
import gc
import importlib.util
import json
import os
import sys
import time


def main(spec_path):
    with open(spec_path) as fh:
        spec = json.load(fh)

    t0 = time.perf_counter_ns()                      # import: recorded, NOT a sample
    # Wrapper units (lloyd/elkan/tree): the variant .so init triggers the installed parent
    # package, whose __init__ re-imports the kernel from the half-initialized variant ->
    # circular ImportError. Pre-importing the parent package FIRST breaks the cycle (v1.4
    # Decision C). Recorded in import_ns, not a sample.
    if spec.get("preimport"):
        __import__(spec["preimport"])
    # Extension modules (.so) export PyInit_<stem>: the module name MUST be the file
    # stem, or create_module fails (caught at Step 0.2.4 first .so load).
    mod_name = os.path.splitext(os.path.basename(spec["module_path"]))[0]
    mspec = importlib.util.spec_from_file_location(mod_name, spec["module_path"])
    module = importlib.util.module_from_spec(mspec)
    mspec.loader.exec_module(module)
    import_ns = time.perf_counter_ns() - t0

    t0 = time.perf_counter_ns()                      # setup: recorded, NOT a sample
    def build_args():
        ns = {}
        exec(spec["setup_code"], ns)
        return tuple(ns["args"]), dict(ns.get("kwargs", {}))
    args, kwargs = build_args()
    setup_ns = time.perf_counter_ns() - t0

    # v1.4 per-rep input refresh (Step 1.2.4): in-place kernels mutate their inputs, so
    # reps 2..K on args-built-once would time a DEGENERATE path (PAVA: already-isotonic;
    # dbscan: labels already filled). When the driver declares mutated_arg_indices, the
    # input is REGENERATED from the committed deterministic recipe before EACH rep (warmup
    # + timed), UNTIMED — perf_counter still wraps ONLY the kernel call (timing-region law
    # preserved). Regen (vs snapshot-restore) gives fresh-written data each rep = production
    # cache state; byte-identical by the recipe's determinism (input_manifest TDD). Pure
    # kernels (no mutated args) keep args-once: the input is invariant and regen would be
    # pure cost (csr's ~1 GB build would dominate). per_rep_regen overrides if given.
    mutated = list(spec.get("mutated_arg_indices") or [])
    _prr = spec.get("per_rep_regen")        # explicit None -> default = (kernel mutates inputs)
    per_rep_regen = bool(mutated) if _prr is None else bool(_prr)

    fn = getattr(module, spec["kernel"])

    counter = None
    if spec.get("cycles"):                           # 10%-subsample cross-check (§5.1)
        # The child is launched by file path; put the src root on sys.path explicitly
        # rather than relying on an inherited PYTHONPATH.
        src_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if src_root not in sys.path:
            sys.path.insert(0, src_root)
        from motifbo.timing.perf_cycles import PerfCycleCounter
        counter = PerfCycleCounter()

    for _ in range(int(spec.get("warmup", 5))):      # executed, never reported
        if per_rep_regen:
            args, kwargs = build_args()              # UNTIMED fresh input (warmup too)
        fn(*args, **kwargs)

    reps = int(spec["reps"])
    samples = []
    cycles = [] if counter else None
    gc_was_enabled = gc.isenabled()
    gc.disable()                                     # no GC pauses inside the region
    try:
        for _ in range(reps):
            # v1.4: regenerate the input BEFORE the perf_counter bracket (UNTIMED) for
            # mutating kernels, so each timed rep sees a fresh pristine input. The timed
            # region is still EXACTLY the kernel call (timing-region law, D2 guard).
            if per_rep_regen:
                args, kwargs = build_args()
            # Cycle reads nest INSIDE the wall brackets: both regions contain exactly
            # the kernel call. The read-syscall pair (~us) lands in the wall sample
            # only on cycle-subsample runs — negligible vs 50-500 ms kernels (§4.2).
            if counter is None:
                t0 = time.perf_counter_ns()
                fn(*args, **kwargs)
                t1 = time.perf_counter_ns()
            else:
                t0 = time.perf_counter_ns()
                c0 = counter.read()
                fn(*args, **kwargs)
                c1 = counter.read()
                t1 = time.perf_counter_ns()
                cycles.append(c1 - c0)
            samples.append(t1 - t0)
    finally:
        if gc_was_enabled:
            gc.enable()
        if counter is not None:
            counter.close()

    with open(spec["out"], "w") as fh:
        json.dump({"samples_ns": samples, "reps": reps,
                   "warmup": int(spec.get("warmup", 5)),
                   "import_ns": import_ns, "setup_ns": setup_ns,
                   "cycles": cycles, "child_pid": os.getpid(),
                   "per_rep_regen": per_rep_regen,
                   "mutated_arg_indices": mutated}, fh)


if __name__ == "__main__":
    main(sys.argv[1])
