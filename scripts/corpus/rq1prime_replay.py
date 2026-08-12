#!/usr/bin/env python3
"""RQ1' offline-replay: RS (uniform, no replacement) vs deterministic DOE screening,
computed ONLY on the already-measured endpoint Δ-probe tables. Frozen protocol —
see results/prereg/PREREG_RQ1PRIME_REPLAY.md. No new timing; pure computation on
committed raw. stdlib only (json/statistics/itertools/random/math).

Modes:
  --emit-tau   : print ONLY the per-unit tau inputs (for the pre-registration). No outcomes.
  (default)    : full replay -> results/characterization/rq1prime/*.json

Metric: evals-to-first-near-optimum. RS expectation E=(N+1)/(K+1) exact + 10k-seed MC.
DOE: resolution-IV 8-run half fraction (I = CHK*DIV*OPT*FP) -> additive main-effect
predicted-best -> +1 confirmation. cost = 9 (sensitivity: 8). success iff predicted in near-opt.
"""
import json, os, sys, math, random, statistics
from itertools import product

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DP = os.path.join(ROOT, "results/characterization/delta_probe")
SEP = os.path.join(ROOT, "results/characterization/separability")
OUT = os.path.join(ROOT, "results/characterization/rq1prime")

# 16-config units (module -> endpoint file stem). Order = report §4.
UNITS16 = [
    ("_k_means_elkan", "elkan_iter_chunked_dense"),
    ("sparsefuncs_fast", "csr_mean_variance_axis0"),
    ("_binning", "_map_to_bins"),
    ("_predictor", "_predict_from_raw_data"),
    ("_shortest_path", "floyd_warshall"),
    ("_online_lda_fast", "_dirichlet_expectation_2d"),
    ("_traversal", "connected_components"),
    ("_isotonic", "_inplace_contiguous_isotonic_regression"),
    ("_ppoly", "ppoly_evaluate"),
]
EXPECT_LABELS = ["SPLT","SPLA","SPHT","SPHA","SCLT","SCLA","SCHT","SCHA",
                 "UPLT","UPLA","UPHT","UPHA","UCLT","UCLA","UCHT","UCHA"]
# label char -> (+1/-1) sign per factor. Sign convention arbitrary; effect estimated.
#  pos0 CHK: S=+1 (checks on) U=-1 ;  pos1 DIV: P=+1 (cdivision False) C=-1
#  pos2 OPT: L=+1 (-O1)        H=-1 ;  pos3 FP : T=+1 (strict)         A=-1
SIGN = [ {"S":1,"U":-1}, {"P":1,"C":-1}, {"L":1,"H":-1}, {"T":1,"A":-1} ]
# resolution-IV half fraction: runs with product(signs)=+1  (defining relation I=CHK*DIV*OPT*FP)
def signs(label):
    return [SIGN[i][label[i]] for i in range(4)]
RESIV8 = [lab for lab in EXPECT_LABELS if math.prod(signs(lab)) == 1]

MC_SEED = 20260706
MC_TRIALS = 10000
TAU_FLOOR = 0.02
FLAT_FRAC = 0.5     # K >= FLAT_FRAC * N -> flatness certificate (excluded from paired test)

def load16(stem):
    with open(os.path.join(DP, stem + "__endpoint.json")) as f:
        d = json.load(f)
    cfgs = {c["label"]: c for c in d["configs"]}
    assert set(cfgs) == set(EXPECT_LABELS), f"{stem}: labels {sorted(cfgs)}"
    return d, cfgs

def unit_tau(cfgs):
    """measured endpoint CI = median over configs of per-config relative subproc range."""
    rr = []
    for lab in EXPECT_LABELS:
        s = cfgs[lab]["subproc_medians_ns"]
        med = statistics.median(s)
        rr.append((max(s) - min(s)) / med)
    ci = statistics.median(rr)
    return max(ci, TAU_FLOOR), ci

def rs_expectation(N, K):
    return (N + 1) / (K + 1)

def rs_mc(labels, nearset, seed=MC_SEED, trials=MC_TRIALS):
    rng = random.Random(seed)
    tot = 0
    order = list(labels)
    for _ in range(trials):
        rng.shuffle(order)
        for i, lab in enumerate(order, 1):
            if lab in nearset:
                tot += i
                break
    return tot / trials

def doe_predict(cfgs):
    """res-IV 8-run screen -> additive main-effect predicted-best label."""
    runs = [(lab, cfgs[lab]["median_ns"]) for lab in RESIV8]
    pred = ""
    eff = {}
    for fi, chars in enumerate(["SU", "PC", "LH", "TA"]):
        plus = [t for lab, t in runs if signs(lab)[fi] == 1]
        minus = [t for lab, t in runs if signs(lab)[fi] == -1]
        mp, mm = statistics.mean(plus), statistics.mean(minus)
        eff[chars] = mp - mm
        # pick faster (lower mean) level
        best_char = chars[0] if mp <= mm else chars[1]
        pred += best_char
    return pred, eff

def analyze16(module, stem):
    d, cfgs = load16(stem)
    N = 16
    tau, ci = unit_tau(cfgs)
    meds = {lab: cfgs[lab]["median_ns"] for lab in EXPECT_LABELS}
    t_best = min(meds.values())
    best_label = min(meds, key=meds.get)
    thresh = t_best * (1 + tau)
    nearset = {lab for lab in EXPECT_LABELS if meds[lab] <= thresh}
    K = len(nearset)
    flat = K >= FLAT_FRAC * N
    rs_e = rs_expectation(N, K)
    rs_mc_e = rs_mc(EXPECT_LABELS, nearset)
    pred, eff = doe_predict(cfgs)
    doe_success = pred in nearset
    doe_cost = 9          # 8 screen + 1 confirm
    doe_cost_sens = 8     # sensitivity: no separate confirm
    # winner (non-flat only): RS wins if fewer expected evals OR DOE failed
    if doe_success:
        winner = "RS" if rs_e < doe_cost else ("DOE" if doe_cost < rs_e else "tie")
    else:
        winner = "RS"     # DOE failed to reach near-opt within its fixed protocol
    return {
        "module": module, "unit": stem, "grid": "16-config Δ-probe (2^4 CHK·DIV·OPT·FP)",
        "N": N, "tau": round(tau, 5), "endpoint_CI": round(ci, 5), "tau_floor_used": tau == TAU_FLOOR,
        "t_best_ns": t_best, "best_label": best_label,
        "near_opt_set": sorted(nearset), "K": K, "near_opt_frac": round(K / N, 4),
        "flat_certificate": flat,
        "rs_expected_evals": round(rs_e, 4), "rs_mc_evals": round(rs_mc_e, 4),
        "doe_screen": "res-IV 8-run I=CHK·DIV·OPT·FP", "doe_screen_runs": RESIV8,
        "doe_predicted_best": pred, "doe_main_effects_ns": {k: round(v, 1) for k, v in eff.items()},
        "doe_success": doe_success, "doe_cost": doe_cost, "doe_cost_sensitivity": doe_cost_sens,
        "winner_if_nonflat": None if flat else winner,
        "delta_all": round(t_best and max(meds.values()) / t_best, 4),
    }

# ---- 12-config strict factorial (csr, elkan): descriptive corroboration ----
def analyze12(stem):
    with open(os.path.join(SEP, stem + "__separability.json")) as f:
        d = json.load(f)
    cfgs = d["configs"]
    N = len(cfgs)
    meds = {c["label"]: c["endpoint_ns"] for c in cfgs}
    # per-config relative subproc range -> CI
    rr = []
    for c in cfgs:
        s = c["subproc_medians_ns"]; med = statistics.median(s)
        rr.append((max(s) - min(s)) / med)
    ci = statistics.median(rr); tau = max(ci, TAU_FLOOR)
    t_best = min(meds.values()); thresh = t_best * (1 + tau)
    nearset = {lab for lab, t in meds.items() if t <= thresh}
    K = len(nearset)
    rs_e = rs_expectation(N, K)
    # additive prediction from FULL 12-run factorial (this IS the §5 characterize screen)
    def level_means(key):
        vals = {}
        for c in cfgs:
            vals.setdefault(c[key], []).append(c["endpoint_ns"])
        return {lv: statistics.mean(v) for lv, v in vals.items()}
    bc_m = level_means("bc"); opt_m = level_means("opt_level"); mar_m = level_means("march")
    pred_bc = min(bc_m, key=bc_m.get); pred_opt = min(opt_m, key=opt_m.get); pred_mar = min(mar_m, key=mar_m.get)
    # find the config matching predicted levels
    pred_label = None
    for c in cfgs:
        if c["bc"] == pred_bc and c["opt_level"] == pred_opt and c["march"] == pred_mar:
            pred_label = c["label"]; break
    doe_success = pred_label in nearset
    return {
        "unit": stem, "grid": "12-config strict factorial (2 bc × 3 opt × 2 march)",
        "N": N, "tau": round(tau, 5), "endpoint_CI": round(ci, 5),
        "t_best_ns": t_best, "near_opt_set": sorted(nearset), "K": K,
        "rs_expected_evals": round(rs_e, 4),
        "doe_full_screen_evals": N + 1,
        "doe_predicted": {"bc": pred_bc, "opt_level": pred_opt, "march": pred_mar, "label": pred_label},
        "doe_success": doe_success,
        "note": "full 12-run factorial = the §5 separability screen; predicted-best from additive main effects.",
    }

def sign_test(wins, losses):
    n = wins + losses
    if n == 0:
        return None
    k = min(wins, losses)
    p = 2 * sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(p, 1.0)

def wilcoxon(diffs):
    """paired Wilcoxon signed-rank two-sided exact-ish; diffs of RS_E - DOE_cost."""
    d = [x for x in diffs if x != 0]
    n = len(d)
    if n == 0:
        return None, n
    order = sorted(range(n), key=lambda i: abs(d[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(d[order[j + 1]]) == abs(d[order[i]]):
            j += 1
        avg = (i + 1 + j + 1) / 2
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    wp = sum(ranks[i] for i in range(n) if d[i] > 0)
    wm = sum(ranks[i] for i in range(n) if d[i] < 0)
    W = min(wp, wm)
    return {"W": W, "W_plus": wp, "W_minus": wm, "n_nonzero": n}, n

def main():
    tau_only = "--emit-tau" in sys.argv
    tau_rows = []
    for module, stem in UNITS16:
        _, cfgs = load16(stem)
        tau, ci = unit_tau(cfgs)
        tau_rows.append((module, stem, round(ci, 5), round(tau, 5), tau == TAU_FLOOR))
    if tau_only:
        print("# per-unit tau INPUTS (endpoint CI = median per-config relative subproc range; tau = max(CI, 0.02))")
        print(f"{'module':22} {'unit':40} {'CI':>8} {'tau':>8}  floor?")
        for m, s, ci, tau, fl in tau_rows:
            print(f"{m:22} {s:40} {ci:8.5f} {tau:8.5f}  {fl}")
        return

    os.makedirs(OUT, exist_ok=True)
    per_unit = [analyze16(m, s) for m, s in UNITS16]
    sec = {stem: analyze12(stem) for stem in ["csr_mean_variance_axis0", "elkan_iter_chunked_dense"]}

    nonflat = [u for u in per_unit if not u["flat_certificate"]]
    flatc = [u for u in per_unit if u["flat_certificate"]]
    # paired: RS_E vs DOE_cost (censor DOE failures to +inf so RS wins the sign)
    diffs, wins_rs, wins_doe, ties = [], 0, 0, 0
    for u in nonflat:
        doe_cost = u["doe_cost"] if u["doe_success"] else math.inf
        d = u["rs_expected_evals"] - doe_cost
        diffs.append(d if math.isfinite(d) else -1e9)  # -inf -> strongly RS-favoring
        if u["winner_if_nonflat"] == "RS": wins_rs += 1
        elif u["winner_if_nonflat"] == "DOE": wins_doe += 1
        else: ties += 1
    st = sign_test(wins_rs, wins_doe)
    wil, nnz = wilcoxon([d for d in diffs if abs(d) < 1e8] + [(-100.0) for d in diffs if abs(d) >= 1e8])

    # pre-registered sensitivity: DOE cost = 8 (no separate confirmation eval)
    s_rs, s_doe, s_tie = 0, 0, 0
    for u in nonflat:
        doe_cost = u["doe_cost_sensitivity"] if u["doe_success"] else math.inf
        if u["rs_expected_evals"] < doe_cost: s_rs += 1
        elif doe_cost < u["rs_expected_evals"]: s_doe += 1
        else: s_tie += 1
    st_sens = sign_test(s_rs, s_doe)

    summary = {
        "prereg": "results/prereg/PREREG_RQ1PRIME_REPLAY.md",
        "n_units_total": len(per_unit),
        "n_flat_certificate": len(flatc),
        "flat_certificate_units": [u["unit"] for u in flatc],
        "n_nonflat_paired": len(nonflat),
        "nonflat_units": [u["unit"] for u in nonflat],
        "paired_wins_RS": wins_rs, "paired_wins_DOE": wins_doe, "paired_ties": ties,
        "sign_test_p_two_sided": None if st is None else round(st, 5),
        "wilcoxon": wil,
        "sensitivity_doe_cost8": {
            "paired_wins_RS": s_rs, "paired_wins_DOE": s_doe, "paired_ties": s_tie,
            "sign_test_p_two_sided": None if st_sens is None else round(st_sens, 5),
            "note": "DOE cost=8 (no separate confirmation eval); direction robust, significance is not.",
        },
        "alpha": 0.05,
        "interpretation_axis": "RS ties/wins -> RS hard to beat on measured grids (data for §7); DOE wins -> structure pays.",
        "scope": "MEASURED-REPLAY: holds on the measured 16-config grids only, NOT full Θ=1728.",
    }
    payload = {"per_unit_16": per_unit, "secondary_12": sec, "summary": summary,
               "mc_seed": MC_SEED, "mc_trials": MC_TRIALS}
    with open(os.path.join(OUT, "rq1prime_replay.json"), "w") as f:
        json.dump(payload, f, indent=2)
    # human-readable paired table
    with open(os.path.join(OUT, "rq1prime_paired_table.txt"), "w") as f:
        f.write(f"{'unit':40} {'N':>2} {'K':>2} {'tau':>6} {'flat':>5} {'RS_E':>6} {'RS_MC':>6} {'DOE':>4} {'DOEok':>6} {'win':>4}\n")
        for u in per_unit:
            f.write(f"{u['unit']:40} {u['N']:>2} {u['K']:>2} {u['tau']:>6.3f} "
                    f"{str(u['flat_certificate']):>5} {u['rs_expected_evals']:>6.2f} {u['rs_mc_evals']:>6.2f} "
                    f"{u['doe_cost']:>4} {str(u['doe_success']):>6} {str(u['winner_if_nonflat']):>4}\n")
        f.write(f"\nnon-flat paired: RS wins {wins_rs}, DOE wins {wins_doe}, ties {ties}; "
                f"sign-test p={summary['sign_test_p_two_sided']}\n")
    print(json.dumps(summary, indent=2))
    print("\nwrote", os.path.join(OUT, "rq1prime_replay.json"))

if __name__ == "__main__":
    main()
