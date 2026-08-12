#!/usr/bin/env python3
"""B1 — the fleet-wide offline replay gate. PREREG_LAUNCH.md §5.

Replays the SHIPPED search engine over all 149 frozen kernel tables at every budget the product can
route to, and compares the result against a committed baseline. Zero live measurement.

WHY THIS GATE EXISTS, in one number: defect D-2 starved the adaptive walk for every budget in
[17, 24]. It moved 58 of 149 kernels, took the worst case from 516 % to 46 % regret, and reached
**0 of the 9 Dataset-R anchors**. The nine-anchor live dogfood — the project's flagship validation —
could not see it, and did not. Nine live anchors are validation; they are not coverage.

The gate is a pre-tag gate, not a one-off. It fails on:

  F1  any budget's MEDIAN regret_emittable worsens by more than 0.10 pp
  F2  any budget's WORST-CASE regret_emittable worsens by more than max(1.0 pp, 10 % relative)
  F3  any INDIVIDUAL kernel x budget cell worsens by more than 5.0 pp      <- the D-2 detector
  F4  total configs_measured over the population increases at any budget
  F5  the emittable fraction of paid measurements (n_paid_emittable / configs_measured) decreases
  F6  the freeze-hash guard or the sanitizer overlay fails to apply

F3 is the one that matters most and the one a median cannot express. A defect confined to a budget
band, or to a class of kernel the anchors do not contain, moves few enough cells that the median
and the anchors both stay quiet.

BASELINE PROVENANCE. `--record` rewrites the baseline and is an explicit, recorded act — a release,
or a numbered amendment to PREREG_LAUNCH.md. It is never a response to a failing gate. A gate whose
baseline can be refreshed to make it pass is not a gate, and this script will not help you do it:
`--record` refuses unless you also pass `--i-am-establishing-a-new-baseline` and a `--reason`.

Reads results/fleet/**/table.jsonl READ-ONLY through the freeze-hash guard. Writes only the
baseline (when asked) and the report file.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics as st
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "doe_v2"))

import engine                                                             # noqa: E402
import fleet                                                              # noqa: E402
from cytune import plan                                                   # noqa: E402

BASELINE = os.path.join(REPO, "scripts", "release", "FLEET_GATE_BASELINE.json")

# Every budget the product can route to (16/24/32/40 -- routing.py R1-R5 plus the +8 feasibility
# bonus), plus the DOE-v2 registered grid {8, 64, 128} so the gate covers the extremes the router
# does not reach today but a future routing change could.
BUDGETS = ("routed", 8, 16, 17, 24, 32, 40, 64, 128)

# PREREG_LAUNCH.md §5, fixed before the first run.
F1_MEDIAN_PP = 0.10
F2_WORST_PP = 1.00
F2_WORST_REL = 0.10
F3_CELL_PP = 5.00


def replay(budgets=BUDGETS, policy=None, engine_note=""):
    """One row per (kernel, budget) for the shipped engine. Deterministic."""
    policy = policy or plan.STRICT
    man, ov = fleet.manifest(), fleet.overlay()                            # F6: raises on drift
    roster = fleet.roster(man)
    rows, t0 = [], time.time()
    for role, entries in roster.items():
        for kid, cell in entries:
            tbl = fleet.load_table(kid, man, ov)
            for b in budgets:
                r = engine.run(tbl, policy=policy,
                               budget_override=(None if b == "routed" else b))
                rows.append({
                    "kernel": kid, "role": role, "cell": cell, "budget": b,
                    "emitted_id": r["emitted_id"],
                    "regret_emittable": (None if r["regret_emittable"] == math.inf
                                         else round(r["regret_emittable"], 12)),
                    "configs_measured": r["configs_measured"],
                    "n_paid_emittable": r["n_paid_emittable"],
                    "route": r["route"],
                })
        print(f"  {role}: {len(entries)} kernels  [{time.time() - t0:.0f}s]", flush=True)
    return {"engine_note": engine_note, "budgets": list(budgets), "n_rows": len(rows),
            "rows": rows}


def _by_budget(rows):
    out = {}
    for r in rows:
        out.setdefault(str(r["budget"]), {})[r["kernel"]] = r
    return out


def _finite(vals):
    return [v for v in vals if v is not None]


def compare(base, cur):
    """Apply F1-F5. Returns (failures, table) -- table is per-budget summary either way."""
    b_by, c_by = _by_budget(base["rows"]), _by_budget(cur["rows"])
    failures, table = [], []

    for budget in cur["budgets"]:
        k = str(budget)
        if k not in b_by:
            failures.append(("F0", budget, None,
                             f"budget {budget} is absent from the baseline; re-record deliberately"))
            continue
        bb, cc = b_by[k], c_by.get(k, {})

        shared = sorted(set(bb) & set(cc))
        missing = sorted(set(bb) - set(cc))
        if missing:
            failures.append(("F0", budget, None,
                             f"{len(missing)} kernels present in the baseline are absent now "
                             f"(first: {missing[:3]})"))

        b_reg = _finite([bb[x]["regret_emittable"] for x in shared])
        c_reg = _finite([cc[x]["regret_emittable"] for x in shared])
        if not b_reg or not c_reg:
            failures.append(("F0", budget, None, "no finite regret values to compare"))
            continue

        b_med, c_med = st.median(b_reg), st.median(c_reg)
        b_max, c_max = max(b_reg), max(c_reg)
        b_cfg = sum(bb[x]["configs_measured"] for x in shared)
        c_cfg = sum(cc[x]["configs_measured"] for x in shared)
        b_emit = sum(bb[x]["n_paid_emittable"] for x in shared)
        c_emit = sum(cc[x]["n_paid_emittable"] for x in shared)
        b_frac = b_emit / b_cfg if b_cfg else 0.0
        c_frac = c_emit / c_cfg if c_cfg else 0.0

        # F1 -- median
        if (c_med - b_med) * 100 > F1_MEDIAN_PP:
            failures.append(("F1", budget, None,
                             f"median regret {b_med:.4%} -> {c_med:.4%} "
                             f"(+{(c_med - b_med) * 100:.3f} pp > {F1_MEDIAN_PP} pp)"))
        # F2 -- worst case, absolute OR relative, whichever is larger
        allow = max(F2_WORST_PP / 100.0, b_max * F2_WORST_REL)
        if c_max - b_max > allow:
            failures.append(("F2", budget, None,
                             f"worst-case regret {b_max:.4%} -> {c_max:.4%} "
                             f"(+{(c_max - b_max) * 100:.3f} pp, allowance {allow * 100:.3f} pp)"))
        # F3 -- per cell. THE D-2 DETECTOR.
        worst_cell = None
        for x in shared:
            bv, cv = bb[x]["regret_emittable"], cc[x]["regret_emittable"]
            if bv is None or cv is None:
                if bv is None and cv is not None:
                    continue                                   # infeasible -> feasible is progress
                failures.append(("F3", budget, x,
                                 f"{x}: regret became unavailable ({bv} -> {cv})"))
                continue
            d = (cv - bv) * 100
            if worst_cell is None or d > worst_cell[1]:
                worst_cell = (x, d)
            if d > F3_CELL_PP:
                failures.append(("F3", budget, x,
                                 f"{x}: {bv:.4%} -> {cv:.4%} (+{d:.3f} pp > {F3_CELL_PP} pp)"))
        # F4 -- total cost
        if c_cfg > b_cfg:
            failures.append(("F4", budget, None,
                             f"configs_measured {b_cfg} -> {c_cfg} (+{c_cfg - b_cfg})"))
        # F5 -- emittable fraction may not decrease (D-1 as a ratchet; see PREREG A-1)
        if c_frac < b_frac - 1e-12:
            failures.append(("F5", budget, None,
                             f"emittable fraction of paid budget {b_frac:.4f} -> {c_frac:.4f}"))

        table.append({"budget": budget, "n": len(shared),
                      "median_base": b_med, "median_cur": c_med,
                      "worst_base": b_max, "worst_cur": c_max,
                      "cfg_base": b_cfg, "cfg_cur": c_cfg,
                      "frac_base": b_frac, "frac_cur": c_frac,
                      "worst_cell": worst_cell})
    return failures, table


def render(table, failures, out=sys.stdout):
    hdr = (f"{'budget':>7} {'n':>4} {'median base':>12} {'median cur':>12} "
           f"{'worst base':>11} {'worst cur':>11} {'cfgs base':>10} {'cfgs cur':>9} "
           f"{'emit frac':>10}")
    print(hdr, file=out)
    print("-" * len(hdr), file=out)
    for r in table:
        print(f"{str(r['budget']):>7} {r['n']:>4} {r['median_base']:>11.4%} {r['median_cur']:>11.4%} "
              f"{r['worst_base']:>10.3%} {r['worst_cur']:>10.3%} {r['cfg_base']:>10} "
              f"{r['cfg_cur']:>9} {r['frac_base']:>5.3f}->{r['frac_cur']:.3f}", file=out)
    print(file=out)
    if failures:
        print(f"FLEET GATE: FAIL — {len(failures)} finding(s)", file=out)
        for code, budget, kernel, why in failures[:60]:
            print(f"  [{code}] budget={budget} {kernel or ''} {why}", file=out)
        if len(failures) > 60:
            print(f"  ... and {len(failures) - 60} more", file=out)
    else:
        print("FLEET GATE: PASS — no budget regressed beyond its pre-stated bound", file=out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baseline", default=BASELINE)
    ap.add_argument("--record", action="store_true", help="write a NEW baseline")
    ap.add_argument("--i-am-establishing-a-new-baseline", action="store_true")
    ap.add_argument("--reason", default="", help="required with --record; goes into the file")
    ap.add_argument("--budgets", default=None, help="comma-separated; 'routed' allowed")
    ap.add_argument("--report", default=None, help="also write the rendered table here")
    args = ap.parse_args()

    budgets = BUDGETS
    if args.budgets:
        budgets = tuple(b if b == "routed" else int(b) for b in args.budgets.split(","))

    if args.record:
        if not args.i_am_establishing_a_new_baseline or not args.reason.strip():
            print("REFUSING: --record needs --i-am-establishing-a-new-baseline and --reason.\n"
                  "A baseline refreshed in response to a failing gate is not a baseline.",
                  file=sys.stderr)
            return 2
        cur = replay(budgets)
        cur["recorded_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        cur["reason"] = args.reason.strip()
        with open(args.baseline, "w") as f:
            json.dump(cur, f, indent=1, sort_keys=True)
        print(f"baseline written: {args.baseline}  ({cur['n_rows']} rows)")
        return 0

    if not os.path.exists(args.baseline):
        print(f"no baseline at {args.baseline}; record one first", file=sys.stderr)
        return 2
    base = json.load(open(args.baseline))
    cur = replay(budgets)
    failures, table = compare(base, cur)
    render(table, failures)
    if args.report:
        with open(args.report, "w") as f:
            print(f"# B1 fleet gate — {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}", file=f)
            print(f"baseline recorded {base.get('recorded_utc')}: {base.get('reason')}\n", file=f)
            print("```", file=f)
            render(table, failures, out=f)
            print("```", file=f)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
