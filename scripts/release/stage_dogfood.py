#!/usr/bin/env python3
"""Stage the nine Dataset-R anchors so `cytune tune` can be pointed at them (F1).

This is HARNESS code, not product code. It does two things and nothing else:

  1. copies each anchor's module tree (`kernel_meta.json` + `closure/`) into a staging directory,
     so the run reads nothing from `results/fleet/` while it executes;
  2. rewrites the anchor driver's `sys.path` preamble.

WHY (2). The study's R-anchor drivers begin with

    for _p in ("/probe/corpus", "<repo>/scripts/corpus"):
        sys.path.insert(0, _p)
    import corpus_drivers as cd

`/probe` was the study tree mounted into the measurement container. cytune no longer mounts it —
that mount is exactly what the v1.0.0 one-way dependency rule removed — so the driver is pointed at
its own directory instead and `corpus_drivers.py` is staged beside it. The driver's LOGIC is
untouched: same inputs, same call, same canon, same OUTPUT_CLASS, same knob.

Nothing here writes to results/fleet or to any frozen table.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
KROOT = os.path.join(REPO, "results", "fleet", "_kernels")
CORPUS = os.path.join(REPO, "scripts", "corpus", "corpus_drivers.py")
OUT = os.path.join(REPO, "results", "release", "dogfood", "staging")

ANCHORS = ["fleet_R_01_csr", "fleet_R_02_pava", "fleet_R_03_lda", "fleet_R_04_binning",
           "fleet_R_05_ppoly", "fleet_R_06_floyd", "fleet_R_07_cc", "fleet_R_08_elkan",
           "fleet_R_09_predictor"]

_PREAMBLE = re.compile(
    r'for _p in \([^)]*\):\n(?:\s+if _p not in sys\.path:\n)?\s+sys\.path\.insert\(0, _p\)\n')

_REPLACEMENT = (
    "# staged for the cytune dogfood: corpus_drivers.py sits beside this file, because cytune\n"
    "# does not mount the study tree into its measurement containers.\n"
    "_here = os.path.dirname(os.path.abspath(__file__))\n"
    "if _here not in sys.path:\n"
    "    sys.path.insert(0, _here)\n")


def stage(kid):
    src = os.path.join(KROOT, kid)
    dst = os.path.join(OUT, kid)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)

    shutil.copy2(os.path.join(src, "kernel_meta.json"), os.path.join(dst, "kernel_meta.json"))
    shutil.copytree(os.path.join(src, "closure"), os.path.join(dst, "closure"))
    shutil.copy2(CORPUS, os.path.join(dst, "corpus_drivers.py"))

    drv = open(os.path.join(src, "driver.py")).read()
    if "import os" not in drv.split("import numpy")[0]:
        drv = drv.replace("import sys", "import os\nimport sys", 1)
    patched, n = _PREAMBLE.subn(_REPLACEMENT, drv)
    if n != 1:
        raise SystemExit(f"{kid}: expected exactly one sys.path preamble, patched {n}. "
                         f"Refusing to guess — inspect the driver.")
    open(os.path.join(dst, "driver.py"), "w").write(patched)

    meta = json.load(open(os.path.join(dst, "kernel_meta.json")))
    return {"kernel_id": kid, "staged_to": dst, "module": meta["module"],
            "pyx": meta["pyx_relpath"], "cobuild": bool(meta.get("cobuild")),
            "openmp": bool(meta.get("openmp")), "preimport": meta.get("preimport")}


def main():
    os.makedirs(OUT, exist_ok=True)
    which = sys.argv[1:] or ANCHORS
    rows = [stage(k) for k in which]
    with open(os.path.join(OUT, "staged.json"), "w") as f:
        json.dump(rows, f, indent=2)
    for r in rows:
        print(f"{r['kernel_id']:<22} {r['module']:<24} cobuild={r['cobuild']} "
              f"openmp={r['openmp']} preimport={r['preimport']}")
    print(f"\nstaged {len(rows)} anchors -> {OUT}")


if __name__ == "__main__":
    main()
