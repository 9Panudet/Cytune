"""In-place fixture for the v1.4 per-rep-regen TDD (Step 1.2.4).

The kernel MUTATES its array arg, so under args-built-once reps 2..K would observe the
already-mutated (degenerate) state. Each call appends the OBSERVED first element to a
trace file, then increments it in place. The trace therefore reveals what each rep saw:
  - per-rep regen ON  -> every call sees a FRESH arr (arr[0]==0) -> trace is all zeros.
  - per-rep regen OFF -> arr accumulates across calls            -> trace counts 0,1,2,...
"""


def kernel(arr, trace_path):
    with open(trace_path, "a") as fh:
        fh.write(f"{int(arr[0])}\n")
    arr[0] += 1            # in-place mutation (the degeneracy source)
