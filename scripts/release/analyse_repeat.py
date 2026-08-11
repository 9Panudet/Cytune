#!/usr/bin/env python3
"""A1/A2/A3 — score the repeated dogfood and derive the ship bound. PREREG_LAUNCH.md §2-§4.

Scores every certificate the repeated campaign produced through `analyse_dogfood.analyse_cert`,
so there is ONE definition of regret across the whole project rather than a second one written
here. Then it computes, by the formula fixed in PREREG_LAUNCH.md §3 before any replicate existed:

    s[a]     = per-anchor spread over replicates          (percentage points)
    S        = max_a s[a]                                 the instrument's reproducibility
    B_anchor = max(S, 1.0 pp)                             the re-derived per-anchor ship bound
    S_fleet  = spread of the per-replicate fleet median
    B_fleet  = max(S_fleet, 0.0 pp)

REGRET IS DISCRETE, and the report says so. It changes between two runs if and only if the search
emits a different config, so the honest description of the instrument is the MULTISET OF EMITTED
CONFIG IDS per anchor, not only a range. A 0.0-3.6 pp range over two configs and the same range
over seven configs are different instruments, and a reader who sees only the range cannot tell them
apart.

Reads results/fleet/*/table.jsonl READ-ONLY. Writes only under the campaign directory.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys
from collections import Counter

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analyse_dogfood as A                                                # noqa: E402


def score(outdir):
    """One row per (arm, replicate, anchor)."""
    man = os.path.join(outdir, "MANIFEST.jsonl")
    rows = []
    for line in open(man):
        m = json.loads(line)
        arm, k, kid = m["arm"], m["replicate"], m["kernel_id"]
        cert = os.path.join(REPO, m["workspace"], kid, "certificate.json")
        r = A.analyse_cert(kid, cert, m.get("wall_s"))
        r.update({"arm": arm, "replicate": k, "exit": m["exit"], "wall_s": m.get("wall_s")})
        rows.append(r)
    return rows


def per_anchor(rows, arm):
    """anchor -> {regrets, configs, medians, spread, distinct}."""
    out = {}
    for r in rows:
        if r["arm"] != arm or r.get("regret") is None:
            continue
        d = out.setdefault(r["kernel_id"], {"regret": [], "emitted": [], "cfg": [],
                                            "verdict": [], "wall": []})
        d["regret"].append(r["regret"])
        d["emitted"].append(r["emitted_config"])
        d["cfg"].append(r["configs_measured"])
        d["verdict"].append(r["verdict"])
        d["wall"].append(r.get("wall_s"))
    for kid, d in out.items():
        d["k"] = len(d["regret"])
        d["median"] = st.median(d["regret"])
        d["min"], d["max"] = min(d["regret"]), max(d["regret"])
        d["spread_pp"] = (d["max"] - d["min"]) * 100
        d["config_counts"] = dict(Counter(d["emitted"]))
        d["n_distinct_configs"] = len(d["config_counts"])
        d["cfg_median"] = st.median(d["cfg"])
        d["cfg_range"] = (min(d["cfg"]), max(d["cfg"]))
        d["verdict_stable"] = len(set(d["verdict"])) == 1
    return out


def fleet_medians(rows, arm):
    """replicate -> median regret over the anchors present in that replicate."""
    by_k = {}
    for r in rows:
        if r["arm"] != arm or r.get("regret") is None:
            continue
        by_k.setdefault(r["replicate"], []).append(r["regret"])
    return {k: st.median(v) for k, v in sorted(by_k.items())}


def derive_bound(pa, fm):
    """PREREG_LAUNCH.md §3.1, applied to the DEFAULT arm only."""
    spreads = {kid: d["spread_pp"] for kid, d in pa.items()}
    S = max(spreads.values()) if spreads else 0.0
    S_median = st.median(spreads.values()) if spreads else 0.0
    M = list(fm.values())
    S_fleet = (max(M) - min(M)) * 100 if M else 0.0
    return {
        "per_anchor_spread_pp": spreads,
        "S_pp": S, "S_median_pp": S_median, "S_fleet_pp": S_fleet,
        "B_anchor_pp": max(S, 1.0),
        "B_fleet_pp": max(S_fleet, 0.0),
        "bound_loosened": S > 1.0,
        "formula": "B_anchor = max(max_a spread_a, 1.0 pp); B_fleet = max(spread of fleet median, 0)",
    }


def compare_arms(pa_d, pa_p, bound):
    """PREREG_LAUNCH.md §4.1/§4.2, on per-anchor MEDIANS, never on single runs."""
    findings, table = [], []
    for kid in sorted(set(pa_d) & set(pa_p)):
        d, p = pa_d[kid], pa_p[kid]
        dm = (p["median"] - d["median"]) * 100
        dc = p["cfg_median"] - d["cfg_median"]
        table.append({"kernel": kid, "D_median": d["median"], "P_median": p["median"],
                      "delta_pp": dm, "D_cfg": d["cfg_median"], "P_cfg": p["cfg_median"],
                      "delta_cfg": dc})
        if dm > bound["B_anchor_pp"]:
            findings.append(("A3.1", kid, f"median regret worsens {dm:+.3f} pp > "
                                          f"B_anchor {bound['B_anchor_pp']:.3f} pp"))
        if dc > 0:
            findings.append(("A3.2", kid, f"configs_measured median rises {d['cfg_median']} -> "
                                          f"{p['cfg_median']}"))
    return findings, table


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir", default=os.path.join(REPO, "results", "release", "dogfood_repeat"))
    args = ap.parse_args()
    out = args.outdir if os.path.isabs(args.outdir) else os.path.join(REPO, args.outdir)

    rows = score(out)
    arms = sorted({r["arm"] for r in rows})
    with open(os.path.join(out, "SCORED.json"), "w") as f:
        json.dump(rows, f, indent=1)

    report = {"arms": arms, "n_rows": len(rows)}
    print(f"scored {len(rows)} runs over arms {arms}\n")

    pas, fms = {}, {}
    for arm in arms:
        pa, fm = per_anchor(rows, arm), fleet_medians(rows, arm)
        pas[arm], fms[arm] = pa, fm
        M = list(fm.values())
        print(f"=== ARM {arm} ===")
        hdr = (f"{'anchor':<22} {'k':>2} {'median':>9} {'min':>9} {'max':>9} {'spread':>8} "
               f"{'cfgs':>10} {'#cfg ids':>9}")
        print(hdr)
        print("-" * len(hdr))
        for kid in sorted(pa):
            d = pa[kid]
            print(f"{kid:<22} {d['k']:>2} {d['median']:>8.3%} {d['min']:>8.3%} {d['max']:>8.3%} "
                  f"{d['spread_pp']:>7.3f}p {str(d['cfg_range']):>10} "
                  f"{d['n_distinct_configs']:>9}")
        if M:
            print(f"\nfleet median-of-medians {st.median(M):.3%}   "
                  f"range [{min(M):.3%}, {max(M):.3%}]   "
                  f"per-replicate medians {[f'{m:.3%}' for m in M]}")
        worst = {k: max(v) for k, v in
                 ((kk, [r['regret'] for r in rows
                        if r['arm'] == arm and r['replicate'] == kk and r.get('regret') is not None])
                  for kk in sorted(fm))}
        print(f"worst-anchor per replicate {[f'{w:.3%}' for w in worst.values()]}   "
              f"range [{min(worst.values()):.3%}, {max(worst.values()):.3%}]")
        report[f"arm_{arm}"] = {
            "per_anchor": pa, "fleet_medians": fm,
            "median_of_medians": st.median(M) if M else None,
            "fleet_median_range": [min(M), max(M)] if M else None,
            "worst_per_replicate": worst,
        }
        print()

    # ---- A2: the bound, from the DEFAULT arm only
    if "D" in pas:
        bound = derive_bound(pas["D"], fms["D"])
        report["bound"] = bound
        print("=== A2 — the re-derived ship bound (PREREG_LAUNCH.md §3) ===")
        print(f"  per-anchor spread: median {bound['S_median_pp']:.3f} pp, "
              f"worst S = {bound['S_pp']:.3f} pp")
        print(f"  fleet-median spread S_fleet = {bound['S_fleet_pp']:.3f} pp")
        print(f"  B_anchor = max(S, 1.0) = {bound['B_anchor_pp']:.3f} pp   "
              f"({'LOOSENED' if bound['bound_loosened'] else 'the 1.0 pp bound STANDS'})")
        print(f"  B_fleet  = {bound['B_fleet_pp']:.3f} pp\n")

        # ---- A3: probe-as-screen, judged on medians against that bound
        if "P" in pas:
            findings, table = compare_arms(pas["D"], pas["P"], bound)
            report["a3"] = {"findings": findings, "table": table}
            print("=== A3 — --probe-as-screen vs the shipped default, on per-anchor medians ===")
            hdr = f"{'anchor':<22} {'D median':>10} {'P median':>10} {'delta':>9} {'D cfg':>6} {'P cfg':>6}"
            print(hdr)
            print("-" * len(hdr))
            for t in table:
                print(f"{t['kernel']:<22} {t['D_median']:>9.3%} {t['P_median']:>9.3%} "
                      f"{t['delta_pp']:>+8.3f}p {t['D_cfg']:>6} {t['P_cfg']:>6}")
            md = st.median([t["D_median"] for t in table])
            mp = st.median([t["P_median"] for t in table])
            print(f"\n  fleet median of per-anchor medians: D {md:.3%}  P {mp:.3%}  "
                  f"delta {(mp - md) * 100:+.3f} pp  (B_fleet {bound['B_fleet_pp']:.3f} pp)")
            print(f"  total configs measured: D {sum(t['D_cfg'] for t in table):.0f}  "
                  f"P {sum(t['P_cfg'] for t in table):.0f}")
            if findings:
                print(f"\n  A3 LIVE RULES FAIL — {len(findings)} finding(s):")
                for code, kid, why in findings:
                    print(f"    [{code}] {kid}: {why}")
                print("  --probe-as-screen stays OFF by default.")
            else:
                print("\n  A3 live rules (§4.1, §4.2) PASS. The remaining rules — H offline, the "
                      "B1 fleet gate, guarantees, and the strictly-better requirement — decide "
                      "the default.")

    with open(os.path.join(out, "REPEAT_REPORT.json"), "w") as f:
        json.dump(report, f, indent=1, default=str)
    print(f"\nwritten: {os.path.join(out, 'REPEAT_REPORT.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
