"""Sanitizer spot-audit CHILD — run ONE kernel under ASan+UBSan in a fresh process.

Mirrors `measure_child.py`'s import mechanics exactly (driver.py, PREIMPORT, PKG_MODULE) so the
audited code path is the SAME path the campaign measured; a spot audit of a different import path
would audit the auditor. No timing here — the only verdict is "did the sanitizer report".

The sanitizer's own verdict arrives via stderr text and the process exit code (halt_on_error=1,
exitcode=1); this child therefore does nothing clever with exceptions — it lets them kill it, and
the parent classifies. A driver-level Python exception (rc!=0, no sanitizer token) is reported
separately from a sanitizer report: they are different findings.

argv: kdir so_path n_reps input_seed [--module NAME]
"""
import argparse
import importlib
import importlib.util
import os
import sys


_HERE = os.path.dirname(os.path.abspath(__file__))
# Dataset-R drivers `import corpus_drivers`, which lives in the sibling scripts/corpus package.
# measure_phase.py gets it via its own sys.path setup; this child must do the same or every R
# anchor fails to import and reads as "unaudited" — which is not the same as "clean".
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "corpus"))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kdir")
    ap.add_argument("so_path")
    ap.add_argument("n_reps", type=int)
    ap.add_argument("input_seed", type=int)
    ap.add_argument("--module", default="kernel")
    a = ap.parse_args()

    driver = _load(os.path.join(a.kdir, "driver.py"), "driver")
    module_name = getattr(driver, "KERNEL_MODULE", a.module)
    preimport = getattr(driver, "PREIMPORT", None)
    if preimport:
        importlib.import_module(preimport)
    pkg_module = getattr(driver, "PKG_MODULE", None)
    if pkg_module:
        root = a.so_path
        for _ in pkg_module.split("."):
            root = os.path.dirname(root)
        sys.path.insert(0, root)
        kernel = importlib.import_module(pkg_module)
    else:
        kernel = _load(a.so_path, module_name)

    # Vary the input seed per rep: the UB surface of a gather/branch kernel is input-dependent,
    # and re-running one fixed input N times re-executes one path N times.
    for r in range(a.n_reps):
        driver.call(kernel, driver.make_inputs(a.input_seed + r))
    print("SAN_CHILD_OK")


if __name__ == "__main__":
    main()
