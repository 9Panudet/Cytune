"""C6 — the harness's strongest control: reproduce the LIVE nine-anchor dogfood offline.

The release report's ground-truth dogfood measured cytune live on nine real scipy/scikit-learn
modules and scored the answer against the frozen 1,728-config tables: median regret +1.41%,
worst +5.41%, 33-49 configs measured. Those numbers were produced by a completely different path
(containers, a real compiler, a real timer) than this replay harness (a dict lookup).

If the harness reproduces them, its engine transcription, its regret denominator, its policy
filter and its budget accounting are all corroborated at once by an independent measurement.
If it does not, the harness is wrong and every number it would go on to produce is worthless.

This is a CONTROL, not a result: it compares V0 against V0's own already-published behaviour.
"""
from __future__ import annotations

import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))

import engine                                              # noqa: E402
import fleet                                               # noqa: E402

# From results/release/V1_RELEASE_REPORT.md §"Results" (the live run), keyed by fleet kernel id.
LIVE = {
    "fleet_R_01_csr":       {"emitted": 1392, "regret": 0.0000, "configs": 33},
    "fleet_R_02_pava":      {"emitted": 1383, "regret": 0.0141, "configs": 33},
    "fleet_R_03_lda":       {"emitted": 1392, "regret": 0.0094, "configs": 33},
    "fleet_R_04_binning":   {"emitted": 198,  "regret": 0.0185, "configs": 49},
    "fleet_R_05_ppoly":     {"emitted": 1392, "regret": 0.0080, "configs": 33},
    "fleet_R_06_floyd":     {"emitted": 786,  "regret": 0.0540, "configs": 33},
    "fleet_R_07_cc":        {"emitted": 1371, "regret": 0.0079, "configs": 33},
    "fleet_R_08_elkan":     {"emitted": 1389, "regret": 0.0541, "configs": 33},
    "fleet_R_09_predictor": {"emitted": 1398, "regret": 0.0510, "configs": 33},
}


def main():
    man = fleet.manifest()
    ov = fleet.overlay()
    have = {k for k, v in man["kernels"].items() if v["role"] == "R-anchor"}
    missing = set(LIVE) - have
    if missing:
        print(f"C6 SKIPPED — anchor ids not in the manifest: {sorted(missing)}")
        print(f"  manifest R-anchors: {sorted(have)}")
        return 2

    print(f"{'anchor':24s} {'emit(live)':>10s} {'emit(replay)':>12s} "
          f"{'reg(live)':>9s} {'reg(replay)':>11s} {'cfg(live)':>9s} {'cfg(replay)':>11s}")
    rows, agree_emit, agree_cfg = [], 0, 0
    for kid in sorted(LIVE):
        tbl = fleet.load_table(kid, man, ov)
        r = engine.run(tbl)
        live = LIVE[kid]
        agree_emit += int(r["emitted_id"] == live["emitted"])
        agree_cfg += int(r["configs_measured"] == live["configs"])
        rows.append((kid, r, live))
        print(f"{kid:24s} {live['emitted']:>10d} {str(r['emitted_id']):>12s} "
              f"{live['regret']:>8.2%} {r['regret_emittable']:>10.2%} "
              f"{live['configs']:>9d} {r['configs_measured']:>11d}")

    rep = [r["regret_emittable"] for _k, r, _l in rows]
    liv = [l["regret"] for _k, _r, l in rows]
    print()
    print(f"  median regret   live {statistics.median(liv):.2%}   replay {statistics.median(rep):.2%}")
    print(f"  worst  regret   live {max(liv):.2%}   replay {max(rep):.2%}")
    print(f"  emitted config agrees on {agree_emit}/9;  configs-measured agrees on {agree_cfg}/9")

    # ---- the two known, EXPLAINED discrepancies, checked rather than asserted -----------------
    # (a) configs-measured is off by exactly 1 everywhere: the live run builds and times the
    #     reference, the sealed convention makes it observation 0 and free (PREREG §3.1). If the
    #     offset is ever anything but a constant 1, the budget accounting is wrong, not offset.
    offs = {live["configs"] - r["configs_measured"] for _k, r, live in rows}
    print(f"  configs-measured offset: {offs}  "
          f"({'CONSTANT 1 = the free reference, as designed' if offs == {1} else 'NOT CONSTANT — accounting defect'})")

    # (b) a differing emitted config is only benign if the two are a near-tie. cytune re-calibrated
    #     each anchor to its own 65 ms target, so absolute times differ from the study table's and
    #     ties inside the rig noise floor can resolve either way. Anything OUTSIDE the noise floor
    #     would be a real disagreement about which config is faster, and a harness defect.
    NOISE = 0.02
    bad = []
    for kid, r, live in rows:
        if r["emitted_id"] == live["emitted"]:
            continue
        tbl = fleet.load_table(kid, man, ov)
        gap = tbl[live["emitted"]][1] / tbl[r["emitted_id"]][1] - 1.0
        print(f"  differing emit on {kid}: {live['emitted']} vs {r['emitted_id']} "
              f"= {gap:+.3%} apart ({'near-tie, inside the noise floor' if abs(gap) < NOISE else 'OUTSIDE the noise floor'})")
        if abs(gap) >= NOISE:
            bad.append(kid)
    ok = offs == {1} and not bad
    print(f"  C6: {'PASS' if ok else 'FAIL'}")

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "results", "doe_v2", "C6_dogfood_control.json")
    json.dump({"rows": [{"kernel": k, "replay": r, "live": l} for k, r, l in rows],
               "median_live": statistics.median(liv), "median_replay": statistics.median(rep),
               "worst_live": max(liv), "worst_replay": max(rep),
               "emitted_agree": agree_emit, "configs_agree": agree_cfg},
              open(out, "w"), indent=1)
    print(f"  -> {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
