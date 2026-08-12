"""W3 — build the design sizes `plan._design` asks for and the frozen set does not contain.

`N_d = min(24, B−1)` can be any value in 7..24, but only {7,15,24} were ever built, so budgets
17..24 fall back to a 24-point design and lose their reserved walk point (PREREG_DOE_V2 A-2).

Only the sizes a ROUTED budget can actually produce are built: routing emits 16, 24, 32 and 40
(BUDGET_DOE / BUDGET_INTERACTION, each optionally + BUDGET_FEAS_BONUS), giving N_d ∈ {15,23,24}.
`doe_23` is the only one missing. Building all eighteen sizes would be work no routed budget can
reach, and a design nothing selects is a design nothing audits.

Over the SAME candidate set as the study's frozen designs (all 1,728, 13 parameters) and with the
study's own seed key convention, so this is an extension of that set rather than a competing one.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))

import designs_v2 as D                                     # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "results", "doe_v2", "shipped_extra_sizes.json")
SIZES = (23,)


def main():
    allc = D.candidates(D.POLICIES["fastmath"])            # all 1,728 — the study's candidate set
    print(f"candidates {len(allc)}  params {len(D.live_columns(allc))}  (study: 1728 / 13)")
    out = {}
    for nd in SIZES:
        d = D.build(nd, allc, ("doe", nd))                 # the STUDY's seed key convention
        out[f"doe_{nd}"] = d
        print(f"  doe_{nd}: rank {d['rank']}/{d['n_params']} logdet {d['logdet']:.4f} "
              f"{'FULL RANK' if d['full_rank'] else 'supersaturated'}")
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
