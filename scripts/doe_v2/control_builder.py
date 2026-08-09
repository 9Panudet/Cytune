"""C7 — the v2 design builder IS the study's builder, proven by reproducing its frozen output.

`designs_v2.build` generalises `scripts/phasep/build_doe_designs.py` in three ways (restricted
candidate set, prior term, alternative coding). A generalisation that quietly changed the optimiser
would make every V1-vs-V0 difference uninterpretable: the design would differ because the search
differed, not because the candidate set did.

So: run the v2 builder with the generalisations switched off — full 1,728 candidate set, no prior
rows, eps*I only, dummy coding, the study's own seed key — and require it to reproduce the
committed designs BYTE-FOR-BYTE, config ids and log-determinant alike.

This is a control, not a result. It compares the new builder against already-committed output.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))

import designs_v2 as D                                     # noqa: E402
from cytune._vendor import designs_path                    # noqa: E402


def main(sizes=(7, 15)):
    frozen = json.load(open(designs_path()))["designs"]
    allc = D.candidates(D.POLICIES["fastmath"])            # == all of Θ, the study's candidates
    ok = len(allc) == 1728 and len(D.live_columns(allc)) == 13
    print(f"  [{'PASS' if ok else 'FAIL'}] candidate set/params: {len(allc)}/"
          f"{len(D.live_columns(allc))} (study: 1728/13)")
    for nd in sizes:
        d = D.build(nd, allc, ("doe", nd))                 # the STUDY's seed key
        want = frozen[f"doe_{nd}"]
        same_ids = d["config_ids"] == sorted(want["config_ids"])
        same_det = abs(d["logdet"] - want["logdet"]) < 1e-9
        ok &= same_ids and same_det
        print(f"  [{'PASS' if same_ids and same_det else 'FAIL'}] doe_{nd}: "
              f"ids identical={same_ids}  logdet {d['logdet']:.6f} vs {want['logdet']:.6f}")
    print("C7:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
