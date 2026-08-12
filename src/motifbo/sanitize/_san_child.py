"""Fresh-subprocess child for the known-good sanitizer clean run (§3.2(2)).

argv: <kind> <so_path> <case_index>. Rebuilds the validation case deterministically
from its spec (no array serialisation across the process boundary), loads the
ASan+UBSan-instrumented kernel .so, and calls it once. A sanitizer report aborts
this child (halt_on_error=1) with a non-zero exit + report on stderr; a clean call
prints OK and exits 0.
"""
import importlib.util
import sys
from pathlib import Path

from motifbo.sanitize import validation_inputs as vi


def main(kind, so_path, idx):
    spec = vi.CASES[kind][idx]
    args = vi.MATERIALIZE[kind](spec)
    stem = Path(so_path).stem                      # must match PyInit_<stem>
    ml = importlib.util.spec_from_file_location(stem, so_path)
    mod = importlib.util.module_from_spec(ml)
    ml.loader.exec_module(mod)
    mod.kernel(*args)
    print(f"OK {kind}[{idx}] {spec['name']}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
