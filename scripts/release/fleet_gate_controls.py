#!/usr/bin/env python3
"""Controls L6 / L7 for the B1 fleet gate. PREREG_LAUNCH.md §6.

A gate's value is that it CAN fail. This proves it can, and proves it does not cry wolf, using the
positive/negative control pair this project requires of every new instrument:

  L7 NEGATIVE CONTROL — the unmodified engine must PASS against its own baseline, zero diff.
  L6 POSITIVE CONTROL — a deliberately regressed engine must FAIL. The regression used is not a
     synthetic mutation: it is defect **D-2 exactly as it shipped**, `screen_plan` capping the
     design at `budget` instead of at N_d, which starved the adaptive walk for every budget in
     [17, 24]. Replaying the real defect is a stronger control than planting an artificial one,
     because it also proves the gate would have caught the defect the nine anchors missed.

If L6 passes (i.e. the gate stays green against a known-broken engine) the gate is vacuous and its
verdict means nothing. That is a hard failure of this script.
"""
from __future__ import annotations

import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "doe_v2"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fleet_gate                                                         # noqa: E402
from cytune import plan                                                   # noqa: E402
from cytune._vendor import theta                                          # noqa: E402


def d2_screen_plan(budget, second_screen=None):
    """`plan.screen_plan` EXACTLY as it was before the D-2 fix: `cap = budget`.

    Byte-for-byte the shipped function apart from that one line, so the control measures the
    defect and not the transcription.
    """
    if not (plan.SECOND_SCREEN if second_screen is None else second_screen):
        return {"design_key": "probe-as-screen", "ids": [],
                "reference_id": theta.REFERENCE_ID, "why": "probe-as-screen"}
    key, design = plan._design(budget)
    ids, seen = [], {theta.REFERENCE_ID}
    cap = budget                                                # <-- D-2: the whole defect
    for cid in design:
        if len(ids) >= cap:
            break
        if cid in seen:
            continue
        seen.add(cid)
        ids.append(cid)
    return {"design_key": key, "ids": ids, "reference_id": theta.REFERENCE_ID}


def main():
    base = json.load(open(fleet_gate.BASELINE))
    rc = 0

    print("=" * 96)
    print("L7 NEGATIVE CONTROL — unmodified engine vs its own baseline (must PASS, zero diff)")
    print("=" * 96)
    cur = fleet_gate.replay(engine_note="unmodified")
    failures, table = fleet_gate.compare(base, cur)
    fleet_gate.render(table, failures)
    if failures:
        print("\nL7 FAILED: the unmodified engine does not reproduce its own baseline. The gate is "
              "non-deterministic and cannot be trusted.")
        rc = 1
    else:
        print("\nL7 PASS.")

    print()
    print("=" * 96)
    print("L6 POSITIVE CONTROL — D-2 reintroduced (`cap = budget`); the gate MUST fail")
    print("=" * 96)
    original = plan.screen_plan
    plan.screen_plan = d2_screen_plan
    try:
        import importlib
        import engine as eng
        importlib.reload(eng)                       # rebind V0.screen_plan to the patched function
        broken = fleet_gate.replay(engine_note="D-2 reintroduced")
    finally:
        plan.screen_plan = original
        import engine as eng
        importlib.reload(eng)

    f2, t2 = fleet_gate.compare(base, broken)
    fleet_gate.render(t2, f2)
    codes = sorted({c for c, _b, _k, _w in f2})
    if not f2:
        print("\nL6 FAILED — THE GATE IS VACUOUS. It stayed green against the engine that shipped "
              "defect D-2 (median regret 3.95% vs 1.46%, worst 516% vs 46%, on 58 of 149 kernels).")
        rc = 1
    else:
        print(f"\nL6 PASS — {len(f2)} finding(s), codes {codes}. The gate detects the real defect "
              f"that the nine live anchors could not (D-2 reached 0 of 9 anchors).")

    print()
    print("CONTROLS: " + ("PASS" if rc == 0 else "FAIL"))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
