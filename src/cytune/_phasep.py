"""Import bridge to the study modules (theta / classify / algorithms / campaign).

cytune deliberately imports these from scripts/phasep rather than vendoring copies. The product
must use the SAME config_id space, the SAME main-effects coding and the SAME algorithm
implementations as the study — a forked copy would silently drift and its numbers would stop
meaning what the study's numbers mean.

The directory sits at different paths on the host and inside the container (where scripts/ is
mounted read-only at /probe), so candidates are probed in order, exactly as algorithms._designs
already does for the DOE design file.
"""
from __future__ import annotations
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_CANDIDATES = [
    os.environ.get("CYTUNE_PHASEP"),
    os.path.abspath(os.path.join(_HERE, "..", "..", "scripts", "phasep")),  # host checkout
    "/probe/phasep",                                                        # in-container mount
]

_PHASEP = None
for _c in _CANDIDATES:
    if _c and os.path.isdir(_c):
        _PHASEP = _c
        break
if _PHASEP is None:
    raise ImportError(f"cannot locate scripts/phasep (tried {_CANDIDATES}); set CYTUNE_PHASEP")
if _PHASEP not in sys.path:
    sys.path.insert(0, _PHASEP)

# theta is numpy-free at import (design_matrix imports numpy lazily), so it is safe to import on
# the HOST, which has no numpy. classify/algorithms/campaign import numpy at module scope and are
# therefore imported only by container-side code.
import theta  # noqa: E402,F401


def designs_path():
    """The committed DOE/probe designs. Same resolution problem, same fix."""
    for p in (os.environ.get("PHASEP_DOE_DESIGNS"),
              os.path.abspath(os.path.join(_PHASEP, "..", "..", "results", "prereg",
                                           "doe_designs_theta.json")),
              "/results/prereg/doe_designs_theta.json"):
        if p and os.path.exists(p):
            return p
    raise FileNotFoundError("doe_designs_theta.json not found; set PHASEP_DOE_DESIGNS")
