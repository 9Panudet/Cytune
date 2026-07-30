"""A-2 Part-1 recompute — taxonomy v2 re-classification of the pilot (DEVELOPMENT data).

Reads ONLY committed pilot tables (results/pilot/pilot_*/{table.jsonl,class_record.json}); no new
measurement. For every kernel: strict-axis statistics (Δ_strict re-derived + asserted against the
committed value; IF_strict = 1−R² of the §0.1 main-effects OLS restricted to STRICT feasible rows,
same degenerate-fit rules as PREREG §1.1: drop constant columns, lstsq rcond=1e-12, SS_tot=0 ⇒ 0),
the v2 primary class and FM/FEAS flags (A2_DECISION_MEMO.md Part 1), and the infeasibility-reason
histogram (FEAS structure).

Also computes the pre-registered INSTRUMENT CONTROLS for the Part-3 probe's S statistic
(super-additivity of a hypothesized AND-gate pair) on committed tables where the answer is known:
  positive-1: B_01 (fmffp × opt on the all-axis — the known fast-math AND-gate, Δ_all≈4.0)
  positive-2: ctrl_planted strict (bc × opt — the A-1-documented bc-vectorization coupling:
              controls_gate.json bc effect 0.343, full payoff only at −O3∧native per
              CONTROLS_DEBUG.md; IF_strict=0.41 ⇒ genuinely interactive on the strict axis)
  negative:   R_01_csr strict (bc × opt — the known-separable real kernel, IF=0.084).
(Transparency: an earlier draft mislabeled ctrl_planted as a negative control on the assumption
"separable opt lever"; the committed A-1 evidence contradicts that assumption — the mislabel was in
the EXPECTATION, found on first run and corrected here before the probe protocol was committed. The
S math is unchanged; A2_DECISION_MEMO.md §P3.4 records the sequence.)
S = [t̂(x1,y0)·t̂(x0,y1)] / [t̂(x0,y0)·t̂(x1,y1)], t̂ = geometric mean of screen medians over feasible
rows in the cell, marginalized over all other factors. S > 1 ⇔ super-additive payoff at (x1,y1).

Run (pinned container, repo ro; stdout = JSON, stderr = human table):
  podman run --rm --network=none --security-opt label=disable \
    -v <repo>:/repo:ro localhost/motifbo-env:phase1 \
    python3 /repo/scripts/phasep/a2_reclassify.py /repo/results/pilot \
    > results/pilot/a2_reclassify_v2.json
"""
import json
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import theta  # noqa: E402

STRICT_FMFFP = (("off", "off"), ("off", "fast"))   # PREREG §1.2: fast_math=off axis
V2_FLAT_CEIL = 1.10        # A-1b floor, reused: FLAT ⇔ Δ_strict < 1.10
V2_MID_CEIL = 1.5          # MID ⇔ 1.10 ≤ Δ_strict < 1.5
V2_IF_SPLIT = 0.25         # LEVER-SEP ⇔ Δ≥1.5 ∧ IF_strict<0.25 · INT ⇔ Δ≥1.5 ∧ IF_strict≥0.25
FM_RATIO = 1.5             # FM flag ⇔ Δ_all/Δ_strict ≥ 1.5
FEAS_FRAC = 0.25           # FEAS flag ⇔ infeasible fraction ≥ 0.25


def _rows(kdir):
    return [json.loads(l) for l in open(os.path.join(kdir, "table.jsonl"))]


def _is_strict(cid):
    return theta.config_of(cid)[8] in STRICT_FMFFP


def _if_strict(rows):
    """IF on the STRICT feasible sub-table, PREREG §1.1 degenerate-fit rules."""
    feas = [(r["config_id"], r["screen"]["median_ns"]) for r in rows
            if r["feasible"] and r.get("screen") and _is_strict(r["config_id"])]
    if len(feas) < 2:
        return None, {"n_strict_feasible": len(feas)}
    ids = [c for c, _ in feas]
    y = np.log(np.array([m for _, m in feas], float))
    X = theta.design_matrix(ids)
    keep = [j for j in range(X.shape[1]) if not np.all(X[:, j] == X[0, j])]
    Xk = np.column_stack([np.ones(len(ids)), X[:, keep]])
    beta, *_ = np.linalg.lstsq(Xk, y, rcond=1e-12)
    ss_res = float(np.sum((y - Xk @ beta) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    if ss_tot == 0.0:
        return 0.0, {"n_strict_feasible": len(feas), "dropped_cols": X.shape[1] - len(keep),
                     "ss_tot": 0.0}
    r2 = 1.0 - ss_res / ss_tot
    return 1.0 - r2, {"n_strict_feasible": len(feas), "dropped_cols": X.shape[1] - len(keep),
                      "ss_res": ss_res, "ss_tot": ss_tot, "r2": r2}


def _v2(delta_strict, if_strict):
    if delta_strict < V2_FLAT_CEIL:
        return "FLAT", True          # IF_strict gated out (A-1b analog on the strict axis)
    if delta_strict < V2_MID_CEIL:
        return "MID", False
    if if_strict is None:
        return "MID", False          # degenerate strict table; conservative, recorded
    return ("LEVER-SEP" if if_strict < V2_IF_SPLIT else "INT"), False


def s_statistic(rows, fx, x0, x1, fy, y0, y1, strict_only=False):
    """Super-additivity S of the (fx,fy) AND-gate over feasible (optionally strict) rows."""
    names = list(theta.FACTOR_NAMES)
    ix, iy = names.index(fx), names.index(fy)
    cells = {(a, b): [] for a in (0, 1) for b in (0, 1)}
    for r in rows:
        if not r["feasible"] or not r.get("screen"):
            continue
        if strict_only and not _is_strict(r["config_id"]):
            continue
        cfg = theta.config_of(r["config_id"])
        vx, vy = cfg[ix], cfg[iy]
        a = 0 if vx == x0 else (1 if vx == x1 else None)
        b = 0 if vy == y0 else (1 if vy == y1 else None)
        if a is None or b is None:
            continue
        cells[(a, b)].append(np.log(r["screen"]["median_ns"]))
    if any(len(v) == 0 for v in cells.values()):
        return None, {k: len(v) for k, v in ((str(k), v) for k, v in cells.items())}
    g = {k: float(np.mean(v)) for k, v in cells.items()}
    S = float(np.exp(g[(1, 0)] + g[(0, 1)] - g[(0, 0)] - g[(1, 1)]))
    return S, {"cell_n": {str(k): len(v) for k, v in cells.items()},
               "cell_geomean_ns": {str(k): float(np.exp(v)) for k, v in g.items()}}


def reclassify(kdir, overlay=None):
    """v2 classification from the kernel's own frozen table.

    `overlay` (D23) is a set of config_ids whose feasible bit roadmap §1.4 forces to 0 because the
    sanitizer reports on them — the oracle passed them, ASan did not. The raw table is NOT
    modified; the bit is overridden in memory here, and `delta_all`/`delta_strict` are RECOMPUTED
    rather than read from `class_record.json`, because the committed values were derived from the
    uncorrected feasible set. With no overlay the function is byte-for-byte its previous self,
    including the self-check against the committed Δ_strict."""
    rows = _rows(kdir)
    rec = json.load(open(os.path.join(kdir, "class_record.json")))
    cl = rec["classification"]
    overlay = set(overlay or ())
    if overlay:
        rows = [dict(r, feasible=0, reason="sanitizer_oob")
                if r.get("config_id") in overlay and r.get("feasible") else r for r in rows]
    feas = [r for r in rows if r["feasible"] and r.get("screen")]
    strict_feas = [r for r in feas if _is_strict(r["config_id"])]
    t_ref = cl["t_ref_ns"]
    t_star_strict = min(r["screen"]["median_ns"] for r in strict_feas)
    d_strict = t_ref / t_star_strict
    if overlay:
        # Δ_all must be recomputed too: the committed value's argmin may itself be an overlaid
        # config, in which case quoting it would credit the kernel with a speedup the product is
        # forbidden to emit.
        cl = dict(cl, delta_all=t_ref / min(r["screen"]["median_ns"] for r in feas))
    else:
        assert abs(d_strict - cl["delta_strict"]) / cl["delta_strict"] < 1e-9, \
            (kdir, d_strict, cl["delta_strict"])   # self-check vs committed (auditor-verified)
    if_s, if_detail = (None, {"gated": True}) if d_strict < V2_FLAT_CEIL else _if_strict(rows)
    v2, gated = _v2(d_strict, if_s)
    n_inf = sum(1 for r in rows if not r["feasible"])
    reasons = {}
    for r in rows:
        if not r["feasible"]:
            reasons[r.get("reason")] = reasons.get(r.get("reason"), 0) + 1
    fm_ratio = cl["delta_all"] / d_strict
    return {
        "kernel_id": rec["kernel_id"], "intended_class": rec.get("intended_class"),
        "v1_measured_class": cl["measured_class"],
        "delta_all": cl["delta_all"], "delta_strict": d_strict,
        "if_strict": if_s, "if_strict_detail": if_detail, "if_strict_gated": gated,
        "greedy_gap_v1_all_axis": cl["greedy_gap"],
        "n_feasible": len(feas), "n_strict_feasible": len(strict_feas),
        "infeasible_frac": n_inf / len(rows), "infeasible_reasons": reasons,
        "fm_ratio": fm_ratio,
        "v2_class": v2, "flag_FM": fm_ratio >= FM_RATIO,
        # ERRATUM E4 (human ruling 2026-07-24, applied at the freeze boundary 2026-07-28):
        # PREREG §12 A-2h promises the flag fractions are "compared in integer arithmetic
        # (FEAS+ ⇔ 4·n_infeasible ≥ n_total)". The shipped form was the float
        # `(n_inf / len(rows)) >= 0.25`, a prose-vs-code drift. CODE IS NOW ALIGNED TO THE
        # DOCUMENTED FORM. The two agree exhaustively over the whole reachable domain — all
        # 1,495,656 (n, k) pairs with n ≤ 1728 — including the knife-edge 432/1728 = 0.25 that
        # A-2h names explicitly (exactly representable as 2⁻², so both predicates fire).
        # Proof + zero-label-change evidence: scripts/phasep/e4_align_verify.py ->
        # results/fleet/E4_ALIGNMENT_EVIDENCE.json.
        "flag_FEAS": (4 * n_inf) >= len(rows),
    }


def main():
    pilot = sys.argv[1] if len(sys.argv) > 1 else "results/pilot"
    out = {"taxonomy_v2": {"FLAT": f"delta_strict < {V2_FLAT_CEIL}",
                           "MID": f"{V2_FLAT_CEIL} <= delta_strict < {V2_MID_CEIL}",
                           "LEVER-SEP": f"delta_strict >= {V2_MID_CEIL} and IF_strict < {V2_IF_SPLIT}",
                           "INT": f"delta_strict >= {V2_MID_CEIL} and IF_strict >= {V2_IF_SPLIT}",
                           "flag_FM": f"delta_all/delta_strict >= {FM_RATIO}",
                           "flag_FEAS": "4 * n_infeasible >= n_total (E4: integer-exact, "
                                        f"equivalent to infeasible_frac >= {FEAS_FRAC})"},
           "kernels": [], "s_statistic_controls": {}}
    for d in sorted(os.listdir(pilot)):
        kdir = os.path.join(pilot, d)
        if d.startswith("pilot_") and os.path.exists(os.path.join(kdir, "class_record.json")):
            k = reclassify(kdir)
            out["kernels"].append(k)
            print(f"{k['kernel_id']:22s} v1={k['v1_measured_class']:9s} -> v2={k['v2_class']:9s} "
                  f"Δs={k['delta_strict']:.3f} IFs={('%.3f' % k['if_strict']) if k['if_strict'] is not None else 'gated'} "
                  f"FM={'+' if k['flag_FM'] else '-'}({k['fm_ratio']:.2f}) "
                  f"FEAS={'+' if k['flag_FEAS'] else '-'}({k['infeasible_frac']:.2f})", file=sys.stderr)

    # Pre-registered S-statistic instrument controls (Part-3 protocol §P3.4) — committed data only.
    ctl = out["s_statistic_controls"]
    b01 = _rows(os.path.join(pilot, "pilot_B_01"))
    S, det = s_statistic(b01, "fmffp", ("off", "off"), ("on", "NA"), "opt_level", "-O1", "-O3")
    ctl["positive_B01_fmffp_x_opt_all_axis"] = {"S": S, "expect": ">= 1.15", **det}
    pl = _rows(os.path.join(pilot, "pilot_ctrl_planted"))
    S, det = s_statistic(pl, "boundscheck", True, False, "opt_level", "-O1", "-O3", strict_only=True)
    ctl["positive2_planted_bc_x_opt_strict"] = {
        "S": S, "expect": ">= 1.15 (A-1-documented bc-vectorization coupling)", **det}
    csr = _rows(os.path.join(pilot, "pilot_R_01_csr"))
    S, det = s_statistic(csr, "boundscheck", True, False, "opt_level", "-O1", "-O3", strict_only=True)
    ctl["negative_csr_bc_x_opt_strict"] = {"S": S, "expect": "< 1.15 (separable, IF=0.084)", **det}
    for k, v in ctl.items():
        print(f"S-control {k}: S={v['S']:.4f} ({v['expect']})", file=sys.stderr)

    json.dump(out, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
