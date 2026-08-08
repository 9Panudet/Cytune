"""Vendored measurement machinery — the product's copy of the study's audited rig.

WHY THESE FILES ARE HERE AND NOT IMPORTED FROM scripts/phasep.

`cytune` must ship standalone: a user who installs the package gets a working tuner without the
study's `scripts/` or `results/` directories, and without the possibility that editing a study
script silently changes what the product measures. That is the one-way dependency rule
(ARCHITECTURE.md §"Dependency rule"), enforced by
`test_cytune_architecture.py::test_no_product_module_imports_study_code`.

WHY THEY ARE VERBATIM COPIES RATHER THAN A REWRITE.

CLAUDE.md: "Inherited machinery binds: v1.4 timing rig (median-of-3, per-rep regen, K_final=30
endpoint), CF-1 phase-split, CF-4 measure_wrap asserts". A reimplementation of the timing rig or
the builder could silently weaken a hard gate, and it would break the one comparison that makes
the product's accuracy checkable at all — the ground-truth dogfood in
`results/release/V1_RELEASE_REPORT.md`, which measures cytune's answer against frozen exhaustive
tables produced by exactly this code. So these are byte-for-byte copies.

HOW DRIFT IS PREVENTED.

`test_cytune_vendor.py` sha256s every file here against its `scripts/phasep` original and fails on
any difference, in either direction. If the study source is absent (an installed wheel), the test
skips and says so rather than passing quietly. `sanitizer_build.py` is the one file that is an
EXTRACTION rather than a whole-file copy; its drift test compares the extracted function's source
text, not the file's.

WHAT IS NOT VENDORED: the study's roster/replay/report code (`san_overlay`, `run_study`,
`run_fleet`, `generate*`, `analyze_study`, `replay`). None of it is reachable from a CLI entry
point, so under A3 it stays out of the package.

The bare `import theta` / `import seeds` inside these files is how the study wrote them and is part
of what "verbatim" means, so this package puts its own directory on `sys.path` to resolve them.
That is the same mechanism the previous `_phasep.py` bridge used — pointed inside the package
instead of outside it.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

DATA = os.path.join(_HERE, "data")

# `algorithms._designs` resolves the frozen DOE design file by probing, in order, this env var and
# then three study-tree paths (`../../results/prereg/`, `/results/`, `/work/prereg/`). None of
# those exist for a standalone install, so the shim points it at the packaged copy. Set here rather
# than by editing algorithms.py, because that file is byte-pinned to the study original and the env
# var is the escape hatch it already provides. An externally-set value is respected.
os.environ.setdefault("PHASEP_DOE_DESIGNS", os.path.join(DATA, "doe_designs_theta.json"))

# Imported after the path insert so the vendored modules' bare imports resolve to each other.
import theta  # noqa: E402,F401


def designs_path():
    """The committed DOE/probe designs, as package data.

    Previously resolved from `results/prereg/` or a `/results` container mount, which made a
    product run depend on the study's results tree being present and mounted read-only. It is a
    frozen input to the search, so it ships with the code.
    """
    p = os.path.join(DATA, "doe_designs_theta.json")
    if not os.path.exists(p):
        raise FileNotFoundError(f"vendored DOE designs missing: {p}")
    return p
