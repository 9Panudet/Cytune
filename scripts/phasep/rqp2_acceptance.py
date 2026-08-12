"""RQ-P2 acceptance (PREREG §3.5) — replay-mode, on the HELD-OUT sets the study never saw.

THE QUESTION: does routing per the P3 matrix beat just picking one algorithm and always using it?
Answered on holdout H (11 kernels, sealed since the campaign) + Dataset R (9 real anchors), i.e.
kernels no arm was tuned on and no routing rule was fitted to.

THREE COMPARATORS, because "routing wins" is only meaningful against a stated alternative:
  - ROUTED       — the engine the P3 matrix installs for that kernel's measured cell × budget.
  - ORACLE-ROUTED— the engine that turns out best FOR THAT KERNEL. Not attainable; it is the
                   ceiling, and the gap to it is what routing leaves on the table.
  - BEST-FIXED   — the single engine with the lowest mean regret across the WHOLE held-out set.
                   This is the honest baseline: if routing cannot beat "always use DOE", the
                   routing matrix is decoration.

EXCLUSIONS, per the deviations register:
  - `directive-partial` anchors (ppoly, floyd) — 3-4 search axes are inert, so a search result
    there measures the adapter, not the algorithm (DEV-3).
  - Motif+BO is not a comparator: it is not installed (no sibling corpus at the point of use) and
    on H/R it would have no LOKO sources anyway.

The firewall lifts here and ONLY here: H and R are the acceptance sets and this is the sanctioned
acceptance step. Everything is replay over frozen tables with the §1.4 overlay applied.
"""
from __future__ import annotations
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import algorithms                                          # noqa: E402
import bo as bomod                                         # noqa: E402
import replay                                              # noqa: E402
import run_fleet as rf                                     # noqa: E402
import run_study as rst                                    # noqa: E402
import san_overlay                                         # noqa: E402
import seeds as seedmod                                    # noqa: E402

FLEET = os.path.join(REPO, "results", "fleet")
STUDY = os.path.join(REPO, "results", "study")
OUT = os.path.join(STUDY, "RQP2_ACCEPTANCE.json")
BUDGETS = (8, 16, 32, 64, 128)
N_SEEDS = 20                                               # A-10: the same prefix the study used
ARMS = ("rs", "doe", "bo")                                 # product-runnable arms only
# DEV-3: inert directive axes ⇒ a search result measures the adapter, not the algorithm.
DIRECTIVE_PARTIAL = {"fleet_R_05_ppoly", "fleet_R_06_floyd"}


def _matrix():
    return json.load(open(os.path.join(STUDY, "ROUTING_MATRIX.json")))["cells"]


def _held_out():
    """H + R, with their MEASURED cell (D23-corrected) and provenance."""
    led = [json.loads(l) for l in open(os.path.join(FLEET, "fleet_ledger.jsonl"))]
    out = []
    for e in led:
        if e.get("status") != "ACCEPTED":
            continue
        is_h = bool(e.get("holdout")) and e.get("dataset", "synthetic") != "R"
        is_r = e.get("dataset") == "R"
        if not (is_h or is_r):
            continue
        kid = e["kernel_id"]
        if kid in DIRECTIVE_PARTIAL:
            continue
        out.append({"kernel_id": kid, "cell": rf._cell_of(e),
                    "set": "H" if is_h else "R",
                    "provenance": e.get("provenance") or ("real-code" if is_r else None),
                    "conformant": rf._inference_conformant(e)})
    return sorted(out, key=lambda x: x["kernel_id"])


def _run_arm(arm, tbl, hash_k, budgets, n_seeds):
    """Mean regret over seeds at each budget, for one arm on one kernel."""
    if arm == "doe":
        return {B: replay.run_algorithm(algorithms.doe, tbl, B, 0)["regret"] for B in budgets}
    acc = {B: [] for B in budgets}
    for i in range(n_seeds):
        if arm == "rs":
            algo = (lambda s, b, _sd, _i=i:
                    algorithms.rs(s, b, seedmod.seq(hash_k, rst.ALG["rs"], _i)))
        else:
            algo = (lambda s, b, _sd, _i=i:
                    bomod.bo(s, b, _i, hash_k=hash_k, seed_i=_i, alg_id=rst.ALG["bo"]))
        pref = replay.run_algorithm_prefixes(algo, tbl, budgets, 0)
        for B in budgets:
            acc[B].append(pref[B]["regret"])
    return {B: float(np.mean(v)) for B, v in acc.items()}


def main():
    mat = _matrix()
    overlay = san_overlay.load(FLEET)
    kernels = _held_out()
    print(f"held-out acceptance set: {len(kernels)} kernels "
          f"({sum(1 for k in kernels if k['set']=='H')} H + "
          f"{sum(1 for k in kernels if k['set']=='R')} R; "
          f"{len(DIRECTIVE_PARTIAL)} directive-partial anchors excluded)", flush=True)

    per_kernel = []
    for k in kernels:
        kid = k["kernel_id"]
        tpath = os.path.join(FLEET, kid, "table.jsonl")
        tbl, _opt = replay.load_frozen_table(tpath, overlay=overlay.get(kid))
        hash_k = seedmod.kernel_hash(kid)
        arms = {a: _run_arm(a, tbl, hash_k, BUDGETS, N_SEEDS) for a in ARMS}
        rec = {**k, "regret_by_arm": {a: {str(B): arms[a][B] for B in BUDGETS} for a in ARMS}}
        rec["routed_engine"] = {}
        rec["routed"], rec["oracle"], rec["gap_to_oracle"] = {}, {}, {}
        for B in BUDGETS:
            cellmat = mat.get(k["cell"], {}).get(str(B))
            # A cell with no matrix row (bare FLAT is descriptive-only) falls back to the routing
            # policy's own default rather than being silently dropped — the product must route
            # SOMETHING for every kernel it is handed.
            eng = cellmat["installed_engine"] if cellmat else "doe"
            rec["routed_engine"][str(B)] = eng
            rec["routed"][str(B)] = arms[eng][B]
            best = min(ARMS, key=lambda a: arms[a][B])
            rec["oracle"][str(B)] = arms[best][B]
            rec["gap_to_oracle"][str(B)] = arms[eng][B] - arms[best][B]
        per_kernel.append(rec)
        print(f"  {kid:44s} cell={k['cell']:<10s} {k['set']}", flush=True)

    # BEST-FIXED: one engine for everything, chosen on this held-out set (generous to the baseline).
    fixed_mean = {a: {str(B): float(np.mean([r["regret_by_arm"][a][str(B)] for r in per_kernel]))
                      for B in BUDGETS} for a in ARMS}
    verdict = {}
    for B in BUDGETS:
        b = str(B)
        best_fixed = min(ARMS, key=lambda a: fixed_mean[a][b])
        routed_mean = float(np.mean([r["routed"][b] for r in per_kernel]))
        oracle_mean = float(np.mean([r["oracle"][b] for r in per_kernel]))
        verdict[b] = {
            "routed_mean_regret": routed_mean,
            "best_fixed_engine": best_fixed,
            "best_fixed_mean_regret": fixed_mean[best_fixed][b],
            "oracle_routed_mean_regret": oracle_mean,
            "routed_beats_best_fixed": routed_mean < fixed_mean[best_fixed][b],
            "routed_minus_best_fixed": routed_mean - fixed_mean[best_fixed][b],
            "routed_minus_oracle": routed_mean - oracle_mean,
            "n_kernels": len(per_kernel),
        }

    prov = {}
    for r in per_kernel:
        p = r["provenance"] or "unlabelled"
        prov.setdefault(p, []).append(r)
    prov_slice = {p: {str(B): float(np.mean([r["routed"][str(B)] for r in rs])) for B in BUDGETS}
                  | {"n": len(rs)} for p, rs in sorted(prov.items())}

    beats = [b for b, v in verdict.items() if v["routed_beats_best_fixed"]]
    out = {
        "schema": "phasep-rqp2-acceptance-v1",
        "question": "does routing per the P3 matrix beat a single fixed algorithm on kernels the "
                    "study never saw?",
        "sets": "holdout H + Dataset R, minus the directive-partial anchors (DEV-3)",
        "arms": list(ARMS),
        "motif_excluded": "not installed — no sibling corpus at the point of use, and on H/R it "
                          "would have no LOKO sources at all",
        "seeds": N_SEEDS, "seeds_prereg": 200, "amendment": "A-10",
        "n_kernels": len(per_kernel),
        "verdict_by_budget": verdict,
        "routed_beats_best_fixed_at": beats,
        "ANSWER": ("ROUTING ADDS NOTHING over the best fixed algorithm at any budget"
                   if not beats else
                   f"routing beats the best fixed algorithm at budgets {beats}"),
        "provenance_slice_routed_mean_regret": prov_slice,
        "per_kernel": per_kernel,
        "recompute": ("podman run --rm --security-opt label=disable -v \"$PWD\":/w -w /w "
                      "-e PYTHONPATH=/w/src localhost/motifbo-env:phase1 python3 "
                      "scripts/phasep/rqp2_acceptance.py"),
    }
    os.makedirs(STUDY, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(f"\n{'B':>5} {'routed':>10} {'best-fixed':>12} {'engine':>8} {'oracle':>10}  beats?")
    for B in BUDGETS:
        v = verdict[str(B)]
        print(f"{B:>5} {v['routed_mean_regret']:>10.5f} {v['best_fixed_mean_regret']:>12.5f} "
              f"{v['best_fixed_engine']:>8} {v['oracle_routed_mean_regret']:>10.5f}  "
              f"{v['routed_beats_best_fixed']}")
    print(f"\nANSWER: {out['ANSWER']}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
