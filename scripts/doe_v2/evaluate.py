"""STAGE 3 — run every variant through the sealed replay on the frozen tables. Emits raw JSONL.

Writes one row per (variant, kernel, budget). No aggregation happens here: the raw file is written
first and the statistics are computed from it by `analyse.py`, so a reported number always has a
raw pointer and a recompute command, and `stats-auditor` can recompute independently from the same
file (CLAUDE.md: "Statistics are recomputed from raw by stats-auditor — never hand-entered").

Budgets: `routed` is what production actually spends and is PRIMARY. The forced sweep is
secondary and covers the range the router and --preset can produce.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))

import engine                                              # noqa: E402
import fleet                                               # noqa: E402
import variants                                            # noqa: E402
from cytune import plan                                    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "results", "doe_v2", "replay_raw.jsonl")
BUDGETS = (None, 8, 16, 24, 32, 40)                        # None = the routed budget (PRIMARY)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--only", default=None, help="comma-separated variant names")
    ap.add_argument("--budgets", default=None, help="comma-separated; 'routed' for the routed one")
    args = ap.parse_args()

    budgets = BUDGETS
    if args.budgets:
        budgets = tuple(None if b == "routed" else int(b) for b in args.budgets.split(","))
    vs = variants.ALL
    if args.only:
        want = set(args.only.split(","))
        vs = [v for v in vs if v.name in want]

    man, ov = fleet.manifest(), fleet.overlay()
    roster = fleet.roster(man)
    policy = plan.STRICT                                   # the DEFAULT policy; the product's own

    tables = {}
    for role, entries in roster.items():
        for kid, _cell in entries:
            tables[kid] = fleet.load_table(kid, man, ov)
    print(f"loaded {len(tables)} freeze-verified, overlay-applied tables")

    n, t0 = 0, time.time()
    with open(args.out, "w") as f:
        for role, entries in roster.items():
            for kid, cell in entries:
                tbl = tables[kid]
                for v in vs:
                    for b in budgets:
                        r = engine.run(tbl, variant=v, policy=policy, budget_override=b)
                        f.write(json.dumps({
                            "variant": v.name, "kernel": kid, "role": role, "cell": cell,
                            "budget_mode": "routed" if b is None else b, **r}) + "\n")
                        n += 1
            print(f"  {role}: {len(entries)} kernels done  [{time.time() - t0:.0f}s]")
    print(f"{n} rows -> {args.out}   [{time.time() - t0:.0f}s]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
