"""P-3 analysis — PREREG §3.3 (RQ-P1) and §3.4 (RQ-P3), computed from the study's raw rows only.

Written BEFORE any study result was read, so the tests are fixed independently of the answers.

WHAT THE UNIT OF ANALYSIS IS, because it decides everything downstream: the per-kernel summary is
the MEAN REGRET OVER SEEDS at each (algorithm, budget) (§3.2). The Friedman/Wilcoxon n is therefore
the number of KERNELS in the cell, not the number of seeds. Seeds reduce the noise in each kernel's
mean; they do not enter any test's n. That is why a short seed schedule costs PRECISION but not the
pre-registered floors — and why this script reports the achieved seed count and the seed-mean
standard error alongside every result rather than burying them.

MEMBERSHIP is the §4-conformant confirmatory CELL (`run_fleet._cell_of` + `_inference_conformant`,
which apply the D23 sanitizer class corrections and the DEV-1b endpoint-voided exclusion).
agreement_fail and endpoint-voided kernels are carried as DESCRIPTIVE-ONLY and reported in their
own table, never merged into the inferential one.

Run (pinned container, needs scipy):
  podman run --rm --security-opt label=disable -v "$PWD":/w -w /w -e PYTHONPATH=/w/src \\
      localhost/motifbo-env:phase1 python3 scripts/phasep/analyze_study.py
"""
from __future__ import annotations
import glob
import json
import os
import sys
from collections import defaultdict

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import run_fleet as rf                                     # noqa: E402  THE cell + conformance rules
import seeds as seedmod                                    # noqa: E402

FLEET = os.path.join(REPO, "results", "fleet")
STUDY = os.path.join(REPO, "results", "study")
OUT = os.path.join(STUDY, "P3_ANALYSIS.json")
ALPHA = 0.05
ARMS = ("rs", "doe", "bo", "motifbo")                      # §3.3 fixed order
BUDGETS = (8, 16, 32, 64, 128)
CONFIRMATORY = ("FLAT+FM", "MID", "LEVER-SEP", "INT")
MOTIF_GATE_BUDGETS = (8, 16)                               # §3.4
MOTIF_GATE_DELTA = 0.2


def load_rows():
    """Every regret*.jsonl shard. A (kernel, alg, budget, seed) appearing twice is a bug, not a
    duplicate to average — shards partition by kernel, so overlap means the sharding broke."""
    rows, seen = [], set()
    dupes = 0
    for p in sorted(glob.glob(os.path.join(STUDY, "regret*.jsonl"))):
        for line in open(p):
            r = json.loads(line)
            k = (r["kernel_id"], r["alg"], r["budget"], r["seed_i"])
            if k in seen:
                dupes += 1
                continue
            seen.add(k)
            rows.append(r)
    return rows, dupes


def ledger_index():
    led = [json.loads(l) for l in open(os.path.join(FLEET, "fleet_ledger.jsonl"))]
    return {e["kernel_id"]: e for e in led if e.get("status") == "ACCEPTED"}


def common_seed_prefix(rows, arms=("bo", "motifbo", "rs")):
    """The largest K such that seeds 0..K-1 are present for EVERY (kernel, arm) among `arms`.

    A-10 truncates all stochastic arms to this prefix. Detected from the data rather than passed
    in, so the reported seed count cannot drift from the seed count actually analysed."""
    have = {}
    for r in rows:
        if r["alg"] in arms and r["budget"] == max(BUDGETS):
            have.setdefault((r["kernel_id"], r["alg"]), set()).add(r["seed_i"])
    if not have:
        return 0
    k = 0
    while all(k in v for v in have.values()):
        k += 1
    return k


def per_kernel_means(rows, metric="regret", max_seeds=None):
    """{(kernel, alg, budget): (mean, n_seeds, sem)} — §3.2's per-kernel summary.

    `sem` is carried so a short seed schedule is visible in the output rather than inferred: it is
    the standard error of the very quantity the tests consume."""
    acc = defaultdict(list)
    for r in rows:
        if r.get("cheated"):
            continue                                       # §9.3: a cheating arm contributes nothing
        # A-10: all stochastic arms share ONE seed prefix. Letting RS keep 200 seeds while BO has
        # 20 would give the arms unequal precision inside a PAIRED test — an artifact of which arm
        # happened to finish, not of the algorithms.
        if max_seeds is not None and r["seed_i"] >= 0 and r["seed_i"] >= max_seeds:
            continue
        v = r.get(metric)
        if v is None or not np.isfinite(v):
            continue
        acc[(r["kernel_id"], r["alg"], r["budget"])].append(v)
    out = {}
    for k, v in acc.items():
        a = np.asarray(v, float)
        out[k] = (float(a.mean()), len(a),
                  float(a.std(ddof=1) / np.sqrt(len(a))) if len(a) > 1 else 0.0)
    return out


def cliffs_delta(d):
    """§3.3 verbatim: δ = (#{dᵢ<0} − #{dᵢ>0}) / n over per-kernel mean-regret differences, so
    δ > 0 means the FIRST-named algorithm has lower regret. Zero differences count in n."""
    d = np.asarray(d, float)
    n = len(d)
    return float(((d < 0).sum() - (d > 0).sum()) / n) if n else float("nan")


def bca_ci(d, seed_key, n_boot=10000):
    """BCa 95% CI on the MEAN paired difference. Degenerate (all dᵢ equal) ⇒ the point interval,
    flagged — a bootstrap of a constant is a constant, and silently reporting [d,d] as a CI would
    read as implausible precision rather than as no variation."""
    d = np.asarray(d, float)
    n = len(d)
    if n < 2:
        return None, None, "n<2"
    if np.allclose(d, d[0]):
        return float(d[0]), float(d[0]), "degenerate (all differences equal)"
    rng = np.random.default_rng(seedmod.state_int(*seed_key) % (2 ** 32))
    boot = np.array([d[rng.integers(0, n, n)].mean() for _ in range(n_boot)])
    theta = d.mean()
    z0 = stats.norm.ppf(np.clip((boot < theta).mean(), 1e-9, 1 - 1e-9))
    jack = np.array([np.delete(d, i).mean() for i in range(n)])
    jm = jack.mean()
    denom = 6.0 * ((jm - jack) ** 2).sum() ** 1.5
    a = ((jm - jack) ** 3).sum() / denom if denom != 0 else 0.0
    lo_z, hi_z = stats.norm.ppf(0.025), stats.norm.ppf(0.975)
    def _adj(z):
        return stats.norm.cdf(z0 + (z0 + z) / (1 - a * (z0 + z)))
    ql, qh = _adj(lo_z), _adj(hi_z)
    return float(np.quantile(boot, ql)), float(np.quantile(boot, qh)), None


def wilcoxon(x, y, alternative="two-sided"):
    """§3.3: paired Wilcoxon, zero_method='pratt', EXACT iff n<=25 and no zero differences and no
    tied absolute differences — the pinned scipy's 'auto' behaviour, spelled out so the choice is
    deterministic and recorded rather than a library default that could change."""
    d = np.asarray(x, float) - np.asarray(y, float)
    n = len(d)
    if n == 0 or np.all(d == 0):
        return None, None, "all differences zero"
    nz = d[d != 0]
    exact = (n <= 25 and len(nz) == n
             and len(np.unique(np.abs(nz))) == len(nz))
    method = "exact" if exact else "approx"
    try:
        res = stats.wilcoxon(x, y, alternative=alternative, zero_method="pratt", method=method)
    except ValueError as e:
        return None, method, f"wilcoxon failed: {e}"
    return float(res.pvalue), method, None


def holm(pairs):
    """Holm step-down within a family. Returns {key: adjusted_p}, monotone-enforced."""
    items = sorted(((k, p) for k, p in pairs.items() if p is not None), key=lambda kv: kv[1])
    m, out, prev = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        adj = min(1.0, max(prev, (m - i) * p))
        out[k] = adj
        prev = adj
    for k, p in pairs.items():
        if p is None:
            out[k] = None
    return out


def _rs_precision(means, means_full):
    """What truncation actually cost, MEASURED on the one arm that finished all 200 seeds.

    RS has both a 20-seed and a 200-seed per-kernel mean, so the shift between them is a direct
    empirical read on how much a 20-seed mean moves — rather than the theoretical sqrt(200/20)
    argument alone. This is the positive control on the truncation itself."""
    shifts = [abs(means[k][0] - means_full[k][0])
              for k in means if k[1] == "rs" and k in means_full]
    rel = [abs(means[k][0] - means_full[k][0]) / means_full[k][0]
           for k in means if k[1] == "rs" and k in means_full and means_full[k][0] > 0]
    return {
        "note": "RS completed all 200 seeds, so its 20-seed vs 200-seed per-kernel means are "
                "directly comparable. This measures what truncation cost instead of asserting it.",
        "n_kernel_budget_pairs": len(shifts),
        "mean_abs_shift_in_rs_kernel_mean": float(np.mean(shifts)) if shifts else None,
        "max_abs_shift": float(np.max(shifts)) if shifts else None,
        "mean_rel_shift": float(np.mean(rel)) if rel else None,
        "max_rel_shift": float(np.max(rel)) if rel else None,
    }


def analyze():
    rows, dupes = load_rows()
    led = ledger_index()
    n_seeds_used = common_seed_prefix(rows)
    means = per_kernel_means(rows, max_seeds=n_seeds_used)
    means_full = per_kernel_means(rows)          # untruncated, for the precision check only

    seed_counts = sorted({n for (_k, a, _b), (_m, n, _s) in means.items() if a != "doe"})
    kernels = sorted({k for (k, _a, _b) in means})

    def cell_of(kid):
        e = led.get(kid)
        return rf._cell_of(e) if e else None

    def conformant(kid):
        e = led.get(kid)
        return bool(e) and rf._inference_conformant(e)

    families, routing, descriptive = {}, {}, {}
    for cell in CONFIRMATORY:
        for B in BUDGETS:
            inferential = [k for k in kernels if cell_of(k) == cell and conformant(k)]
            descr = [k for k in kernels if cell_of(k) == cell and not conformant(k)]
            fam = {"cell": cell, "budget": B, "n_inferential": len(inferential),
                   "n_descriptive_only": len(descr)}
            # A-10 makes this mandatory: a truncated study that does not show its own noise looks
            # more precise than it is. This is the SE of the very quantity the tests consume.
            sems = [means[(k, a, B)][2] for a in ARMS for k in inferential if (k, a, B) in means]
            nsd = [means[(k, a, B)][1] for a in ARMS for k in inferential if (k, a, B) in means]
            fam["seed_mean_sem"] = float(np.mean(sems)) if sems else None
            fam["seeds_per_kernel_min"] = int(min(nsd)) if nsd else None
            fam["seeds_per_kernel_max"] = int(max(nsd)) if nsd else None
            # §3.3 complete-block rule: a kernel with no Motif arm leaves the 4-way Friedman and
            # every pairwise test INVOLVING Motif, but stays in the {RS,DOE,BO} pairwise tests.
            have = {a: [k for k in inferential if (k, a, B) in means] for a in ARMS}
            complete4 = [k for k in inferential if all((k, a, B) in means for a in ARMS)]
            fam["n_complete_4way"] = len(complete4)
            fam["n_missing_motif"] = len(inferential) - len(complete4)
            if len(complete4) >= 2:
                cols = [[means[(k, a, B)][0] for k in complete4] for a in ARMS]
                try:
                    fr = stats.friedmanchisquare(*cols)
                    fam["friedman_p"] = float(fr.pvalue)
                    fam["friedman_stat"] = float(fr.statistic)
                except ValueError as e:
                    fam["friedman_p"], fam["friedman_note"] = None, str(e)
            else:
                fam["friedman_p"], fam["friedman_note"] = None, "n<2 complete blocks"

            raw_p, eff = {}, {}
            for i, a in enumerate(ARMS):
                for b in ARMS[i + 1:]:
                    # Motif pairs use the complete-4way set; the rest use their own paired set.
                    ks = complete4 if "motifbo" in (a, b) else \
                        [k for k in inferential if (k, a, B) in means and (k, b, B) in means]
                    if len(ks) < 2:
                        raw_p[f"{a}|{b}"] = None
                        continue
                    xa = [means[(k, a, B)][0] for k in ks]
                    xb = [means[(k, b, B)][0] for k in ks]
                    p, method, note = wilcoxon(xa, xb)
                    raw_p[f"{a}|{b}"] = p
                    d = np.asarray(xa) - np.asarray(xb)
                    lo, hi, cnote = bca_ci(d, ("bca", cell, B, f"{a}|{b}"))
                    eff[f"{a}|{b}"] = {"n": len(ks), "cliffs_delta": cliffs_delta(d),
                                       "mean_diff": float(d.mean()),
                                       "bca_lo": lo, "bca_hi": hi, "bca_note": cnote,
                                       "wilcoxon_method": method, "note": note}
            # Pairwise runs ONLY if Friedman rejects (§3.3). Recording the gate explicitly keeps a
            # non-significant family from being mined for a pairwise win.
            gated = fam.get("friedman_p") is not None and fam["friedman_p"] < ALPHA
            fam["pairwise_gate_open"] = gated
            fam["pairwise_raw_p"] = raw_p
            fam["pairwise_holm_p"] = holm(raw_p) if gated else None
            fam["effect_sizes"] = eff

            # Routing cell: lowest MEDIAN per-kernel mean regret; ties -> lower MEAN; then RS<DOE<BO<Motif.
            med = {a: (float(np.median([means[(k, a, B)][0] for k in have[a]])) if have[a] else None)
                   for a in ARMS}
            mean_ = {a: (float(np.mean([means[(k, a, B)][0] for k in have[a]])) if have[a] else None)
                     for a in ARMS}
            avail = [a for a in ARMS if med[a] is not None]
            if avail:
                best = sorted(avail, key=lambda a: (med[a], mean_[a], ARMS.index(a)))[0]
                tie_med = [a for a in avail if med[a] == med[best]]
                decisive = bool(gated) and all(
                    (fam["pairwise_holm_p"] or {}).get(f"{min(best, o, key=ARMS.index)}|"
                                                       f"{max(best, o, key=ARMS.index)}") is not None
                    and (fam["pairwise_holm_p"] or {})[
                        f"{min(best, o, key=ARMS.index)}|{max(best, o, key=ARMS.index)}"] < ALPHA
                    and med[best] < med[o]
                    for o in avail if o != best)
                routing[f"{cell}|{B}"] = {
                    "winner": best, "decisive": decisive,
                    "verdict": "DECISIVE" if decisive else "TIED",
                    "tied_set": [a for a in avail if not decisive] if not decisive else [],
                    "median_regret": med, "mean_regret": mean_,
                    "tie_break_fired": len(tie_med) > 1,
                    "n": {a: len(have[a]) for a in ARMS},
                }
            families[f"{cell}|{B}"] = fam
            if descr:
                descriptive[f"{cell}|{B}"] = {
                    "kernels": descr,
                    "median_regret": {a: (float(np.median(
                        [means[(k, a, B)][0] for k in descr if (k, a, B) in means]))
                        if any((k, a, B) in means for k in descr) else None) for a in ARMS},
                }

    # ---- RQ-P3 (§3.4): Motif vs BO at B in {8,16}, one-sided 'less', Holm over 2 tests ----
    boundary = {k for k, e in led.items() if e.get("boundary_flags")}
    rqp3_set = [k for k in kernels
                if cell_of(k) in CONFIRMATORY + ("FLAT",) and k not in boundary
                and led.get(k) and not led[k].get("holdout") and led[k].get("dataset") != "R"]
    rqp3_raw, rqp3 = {}, {}
    for B in MOTIF_GATE_BUDGETS:
        ks = [k for k in rqp3_set if (k, "motifbo", B) in means and (k, "bo", B) in means]
        if len(ks) < 2:
            rqp3_raw[str(B)] = None
            rqp3[str(B)] = {"n": len(ks), "note": "n<2"}
            continue
        xm = [means[(k, "motifbo", B)][0] for k in ks]
        xb = [means[(k, "bo", B)][0] for k in ks]
        p, method, note = wilcoxon(xm, xb, alternative="less")
        rqp3_raw[str(B)] = p
        d = np.asarray(xm) - np.asarray(xb)
        rqp3[str(B)] = {"n": len(ks), "raw_p": p, "wilcoxon_method": method, "note": note,
                        "cliffs_delta": cliffs_delta(d), "mean_diff": float(d.mean())}
    holm_p = holm(rqp3_raw)
    for B in MOTIF_GATE_BUDGETS:
        rqp3[str(B)]["holm_p"] = holm_p.get(str(B))
    n_excl = sum(1 for line in open(os.path.join(STUDY, "motif_exclusions_s0.jsonl"))) \
        if os.path.exists(os.path.join(STUDY, "motif_exclusions_s0.jsonl")) else 0
    frac_excl = n_excl / max(1, len(rqp3_set))
    motif_enters = any(
        rqp3[str(B)].get("holm_p") is not None and rqp3[str(B)]["holm_p"] < ALPHA
        and (rqp3[str(B)]["cliffs_delta"] or 0) >= MOTIF_GATE_DELTA
        for B in MOTIF_GATE_BUDGETS)

    # ---- FLAT no-winner harness check (tripwire): on a flat landscape every arm should tie ----
    flat_check = {}
    for B in BUDGETS:
        ks = [k for k in kernels if cell_of(k) == "FLAT" and conformant(k)
              and all((k, a, B) in means for a in ARMS)]
        if len(ks) >= 2:
            m = {a: float(np.median([means[(k, a, B)][0] for k in ks])) for a in ARMS}
            spread = max(m.values()) - min(m.values())
            flat_check[str(B)] = {"n": len(ks), "median_regret": m, "spread": spread,
                                  "tripwire": spread > 0.01}

    return {
        "schema": "phasep-p3-analysis-v1",
        "prereg": "§3.2 (per-kernel mean over seeds), §3.3 (RQ-P1), §3.4 (RQ-P3)",
        "unit_of_analysis": "kernel; the Friedman/Wilcoxon n is the number of KERNELS in the cell, "
                            "not the number of seeds. Seeds reduce each kernel's mean's noise only.",
        "membership": "§4-conformant confirmatory cell via run_fleet._cell_of + "
                      "_inference_conformant (D23 class corrections + DEV-1b endpoint-voided)",
        "sanitizer_overlay_in_force": os.path.exists(
            os.path.join(FLEET, "SANITIZER_INFEASIBLE_OVERLAY.json")),
        "n_rows": len(rows), "duplicate_rows_dropped": dupes,
        "n_kernels_with_rows": len(kernels),
        "seed_counts_observed": seed_counts,
        "seeds_prereg": 200,
        "seeds_used": n_seeds_used,
        "amendment": "A-10 (seed truncation, timeline-driven). All stochastic arms analysed on the "
                     "SAME uniform prefix; DOE is deterministic and unaffected.",
        "sem_inflation_vs_prereg": round((200 / n_seeds_used) ** 0.5, 3) if n_seeds_used else None,
        "null_result_interpretation":
            "UNDERPOWERED-NULL. Truncation multiplies each kernel's seed-mean SE by "
            "sqrt(200/seeds_used), so a real effect is likelier to be MISSED than under the "
            "pre-registration. A non-significant result here is NOT evidence of no difference. A "
            "SIGNIFICANT result is not weakened: extra noise raises the bar for rejection.",
        "rs_full_seed_precision_check": _rs_precision(means, means_full),
        "families": families,
        "routing_matrix": routing,
        "descriptive_only": descriptive,
        "rqp3": {"per_budget": rqp3, "motif_enters_product": motif_enters,
                 "extractor_excluded": n_excl, "extractor_excluded_frac": frac_excl,
                 "evaluable": frac_excl < 0.20,
                 "rule": "§3.4: Holm-corrected one-sided Wilcoxon p<0.05 AND Cliff's δ ≥ 0.2 at "
                         "B ∈ {8,16}; anything else ⇒ Motif is DROPPED and the negative ships"},
        "flat_no_winner_check": flat_check,
        "recompute": ("podman run --rm --security-opt label=disable -v \"$PWD\":/w -w /w "
                      "-e PYTHONPATH=/w/src localhost/motifbo-env:phase1 python3 "
                      "scripts/phasep/analyze_study.py"),
    }


def main():
    res = analyze()
    os.makedirs(STUDY, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(res, f, indent=1)
    print(f"rows {res['n_rows']}  kernels {res['n_kernels_with_rows']}  "
          f"seeds observed {res['seed_counts_observed']} (prereg 200)")
    print(f"RQ-P3 motif_enters_product = {res['rqp3']['motif_enters_product']}  "
          f"evaluable={res['rqp3']['evaluable']}")
    for key, r in sorted(res["routing_matrix"].items()):
        print(f"  {key:20s} {r['verdict']:9s} winner={r['winner']:8s} "
              f"n={r['n']['bo']}")
    trip = [k for k, v in res["flat_no_winner_check"].items() if v.get("tripwire")]
    if trip:
        print(f"  !! FLAT no-winner TRIPWIRE at budgets {trip}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
