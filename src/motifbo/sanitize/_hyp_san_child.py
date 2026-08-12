"""Fresh-subprocess child for the Hypothesis property sanitizer pass (Step 0.P / G1).

argv: <kind> <so_path> <corpus_path> <idx>. Loads the committed Hypothesis corpus,
materialises spec[idx] via the SAME validation_inputs.materialize_*, loads the
ASan+UBSan-instrumented kernel .so, and calls the kernel once. Mirrors _san_child.py
exactly except the spec source is the committed corpus file (Hypothesis-generated)
rather than validation_inputs.CASES. A sanitizer report aborts this child
(halt_on_error=1) with a non-zero exit + report on stderr; a clean call prints OK.
"""
import importlib.util
import json
import sys
from pathlib import Path

from motifbo.sanitize import validation_inputs as vi


def main(kind, so_path, corpus_path, idx):
    spec = json.loads(Path(corpus_path).read_text())[idx]
    args = vi.MATERIALIZE[kind](spec)
    stem = Path(so_path).stem                      # must match PyInit_<stem>
    ml = importlib.util.spec_from_file_location(stem, so_path)
    mod = importlib.util.module_from_spec(ml)
    ml.loader.exec_module(mod)
    mod.kernel(*args)
    print(f"OK {kind}[{idx}] {spec['name']}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]))
