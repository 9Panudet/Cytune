"""STAGE 3 analysis — recomputed from replay_raw.jsonl, never from memory.

Paired over kernels (the same 149 tables see every variant), Wilcoxon signed-rank vs V0 with
Cliff's delta as the effect size, Holm-corrected across variants within each (role x budget)
family. H and R are reported SEPARATELY and never pooled: the class distributions differ (INT: 41
synthetic vs 0 of 9 real) so a pooled number would be the synthetic majority's answer wearing a
real-code label.

Wilcoxon is implemented here rather than imported so the whole chain is stdlib+numpy and an
auditor recomputing it needs nothing this repo does not already pin. The exact-vs-normal switch
and the zero-handling (Pratt: zeros dropped) are stated, not implicit.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, "results", "doe_v2", "replay_raw.jsonl")


# ------------------------------------------------------------------------------- statistics
def wilcoxon(diffs):
    """Two-sided signed-rank p. Zeros dropped (Pratt), ties get average ranks, normal
    approximation with tie + continuity correction. Returns (p, n_used)."""
    d = [x for x in diffs if abs(x) > 1e-12]
    n = len(d)
    if n < 6:
        return None, n                      # too few non-zero pairs for the approximation
    order = sorted(range(n), key=lambda i: abs(d[i]))
    ranks = [0.0] * n
    i = 0
    tie_term = 0.0
    while i < n:
        j = i
        while j + 1 < n and abs(abs(d[order[j + 1]]) - abs(d[order[i]])) < 1e-12:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        t = j - i + 1
        tie_term += t ** 3 - t
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    w_plus = sum(r for r, x in zip(ranks, d) if x > 0)
    mu = n * (n + 1) / 4.0
    sd = math.sqrt(n * (n + 1) * (2 * n + 1) / 24.0 - tie_term / 48.0)
    if sd == 0:
        return None, n
    z = (abs(w_plus - mu) - 0.5) / sd
    return math.erfc(z / math.sqrt(2)), n


def cliffs_delta(a, b):
    """P(a>b) - P(a<b). Sign convention: positive means `a` is LARGER."""
    if not a or not b:
        return None
    gt = lt = 0
    for x in a:
        for y in b:
            if x > y:
                gt += 1
            elif x < y:
                lt += 1
    return (gt - lt) / float(len(a) * len(b))


def holm(pairs):
    """[(key, p)] -> {key: adjusted p}. None p's pass through untouched."""
    live = sorted([kv for kv in pairs if kv[1] is not None], key=lambda kv: kv[1])
    m, out, running = len(live), {}, 0.0
    for i, (k, p) in enumerate(live):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    for k, p in pairs:
        if p is None:
            out[k] = None
    return out


# ------------------------------------------------------------------------------------ loading
def load(path=RAW):
    rows = defaultdict(dict)                    # (role,budget,kernel) -> {variant: row}
    for line in open(path):
        r = json.loads(line)
        rows[(r["role"], r["budget_mode"], r["kernel"])][r["variant"]] = r
    return rows


def _fmt_p(p):
    if p is None:
        return "   n/a"
    return f"{p:6.4f}" if p >= 1e-4 else "<1e-4"


def table(rows, role, budget, metric="regret_emittable", baseline="V0", cells=None):
    keys = [k for k in rows if k[0] == role and k[1] == budget]
    if cells:
        keys = [k for k in keys if rows[k][baseline].get("cell") in cells]
    names = sorted({v for k in keys for v in rows[k]},
                   key=lambda s: (s.rstrip("+s"), s.endswith("+s")))
    out = []
    ps = []
    for v in names:
        pairs = [(rows[k][v][metric], rows[k][baseline][metric])
                 for k in keys if v in rows[k] and baseline in rows[k]]
        pairs = [(a, b) for a, b in pairs if math.isfinite(a) and math.isfinite(b)]
        if not pairs:
            continue
        va = [a for a, _ in pairs]
        vb = [b for _, b in pairs]
        diffs = [a - b for a, b in pairs]
        cost = [rows[k][v]["configs_measured"] for k in keys if v in rows[k]]
        p, n_used = (None, 0) if v == baseline else wilcoxon(diffs)
        ps.append((v, p))
        out.append({
            "variant": v, "n": len(pairs),
            "median": statistics.median(va), "mean": statistics.mean(va),
            "worst": max(va),
            "median_delta": statistics.median(diffs),
            "better": sum(1 for d in diffs if d < -1e-12),
            "worse": sum(1 for d in diffs if d > 1e-12),
            "same": sum(1 for d in diffs if abs(d) <= 1e-12),
            "cliffs": None if v == baseline else cliffs_delta(va, vb),
            "p_raw": p, "n_nonzero": n_used,
            "configs_median": statistics.median(cost), "configs_max": max(cost),
        })
    adj = holm(ps)
    for r in out:
        r["p_holm"] = adj.get(r["variant"])
    return out


def show(rows, role, budget, metric="regret_emittable", cells=None):
    t = table(rows, role, budget, metric, cells=cells)
    if not t:
        return
    label = f"{role}  budget={budget}" + (f"  cells={','.join(cells)}" if cells else "")
    print(f"\n{label}   metric={metric}   (n={t[0]['n']} kernels, paired)")
    print(f"  {'variant':8s} {'median':>8s} {'worst':>8s} {'Δmedian':>9s} "
          f"{'better':>6s} {'worse':>6s} {'same':>5s} {'Cliff δ':>8s} {'p(Holm)':>8s} "
          f"{'cfgs':>6s}")
    for r in t:
        d = f"{r['median_delta']:+.4f}" if r["variant"] != "V0" else "     —"
        cd = f"{r['cliffs']:+.3f}" if r["cliffs"] is not None else "     —"
        p = "     —" if r["variant"] == "V0" else _fmt_p(r["p_holm"])
        print(f"  {r['variant']:8s} {r['median']:8.4f} {r['worst']:8.4f} {d:>9s} "
              f"{r['better']:6d} {r['worse']:6d} {r['same']:5d} {cd:>8s} {p:>8s} "
              f"{r['configs_median']:6.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=RAW)
    ap.add_argument("--metric", default="regret_emittable")
    ap.add_argument("--budgets", default="routed")
    ap.add_argument("--per-cell", action="store_true")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    rows = load(args.raw)
    budgets = [b if b == "routed" else int(b) for b in args.budgets.split(",")]
    dump = {}
    for b in budgets:
        for role in ("training", "holdout-H", "R-anchor"):
            show(rows, role, b, args.metric)
            dump[f"{role}|{b}"] = table(rows, role, b, args.metric)
        if args.per_cell:
            allcells = sorted({r["cell"] for k in rows for r in rows[k].values()})
            for cell in allcells:
                show(rows, "training", b, args.metric, cells=[cell])
                dump[f"training|{b}|{cell}"] = table(rows, "training", b, args.metric,
                                                     cells=[cell])
    if args.json_out:
        json.dump(dump, open(args.json_out, "w"), indent=1)
        print(f"\n-> {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
