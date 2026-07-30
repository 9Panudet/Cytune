"""DELIBERATELY MIS-PLACED timing region (Step 0.2.2 negative fixture — never use).

Re-executes input construction INSIDE the timed region every rep, and times the
module import into the first rep — the classic D2-style placement error. The
placement tests must detect that this violates the bound the real harness satisfies;
if they ever stop detecting it, the tests are vacuous (§6.3).

Speaks the same spec-file protocol as motifbo/timing/_child.py.
"""
import importlib.util
import json
import sys
import time


def main(spec_path):
    with open(spec_path) as fh:
        spec = json.load(fh)

    samples = []
    module = None
    for _ in range(int(spec["reps"])):
        t0 = time.perf_counter_ns()           # WRONG: region opens before import/setup
        if module is None:
            mspec = importlib.util.spec_from_file_location("candidate", spec["module_path"])
            module = importlib.util.module_from_spec(mspec)
            mspec.loader.exec_module(module)  # WRONG: import inside timed region
        ns = {}
        exec(spec["setup_code"], ns)          # WRONG: input construction timed, every rep
        fn = getattr(module, spec["kernel"])
        fn(*ns["args"], **ns.get("kwargs", {}))
        t1 = time.perf_counter_ns()
        samples.append(t1 - t0)

    with open(spec["out"], "w") as fh:
        json.dump({"samples_ns": samples, "reps": spec["reps"], "warmup": 0,
                   "import_ns": None, "setup_ns": None, "child_pid": None}, fh)


if __name__ == "__main__":
    main(sys.argv[1])
