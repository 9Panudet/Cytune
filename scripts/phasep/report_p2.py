"""CHECKPOINT P-2 report generator — reads committed fleet artifacts only (no measurement).

Emits results/fleet/P2_REPORT.md per the signed A-2 directive: (1) freeze + per-regime counts vs
the 26 floor, (2) v2 confusion table with the R3 INT screen-vs-table scrutiny, (3) diversity/spread
evidence + anti-clone rejection log, (4) measurement validity (agreement watch, suspicious,
controls), (5) envelope actuals vs the verbatim PREREG §10 band, (6) auditor verdict slots (folded
verbatim at checkpoint time), (7) P3/freeze-guard status + H manifest. Robust to partial data (can
run mid-campaign for progress snapshots; the FREEZE section states plainly when no freeze exists).
Every number carries its raw pointer; recompute = rerun this script.
"""
from __future__ import annotations
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_v2 as g2   # noqa: E402
import run_fleet as rf     # noqa: E402  — THE cell rule lives there; never re-derived here (D11)

FLOOR_N = 26               # PREREG §2: per-cell power floor (δ=0.4)
# PREREG §12 A-2c (verbatim): "confirmatory families = (regime × budget), regimes {FLAT+FM, MID,
# LEVER-SEP, INT — fielded per the probe verdict}; FLAT∧FM− is descriptive-only." The confirmatory
# FLAT family is therefore the FLAGGED CELL (measured FLAT ∧ FM+), NOT the bare measured class —
# `measured_v2` never takes the value "FLAT+FM", so counting it directly renders 0 (D11).
REGIMES = ("FLAT+FM", "MID", "LEVER-SEP", "INT")
DESCRIPTIVE_CELL = "FLAT∧FM− (descriptive)"


def _cell(e):
    """Confirmatory CELL of an ACCEPTED ledger entry — `run_fleet._cell_of` is THE definition
    (A-2c/A-2a); this only relabels bare measured-FLAT with its descriptive-only name so the
    report table reads unambiguously. Counts toward a floor only if it is one of REGIMES."""
    c = rf._cell_of(e)
    return DESCRIPTIVE_CELL if c == "FLAT" else c


def _conformant(e):
    """PREREG §4, verbatim and unconditional, PLUS the endpoint-voided ruling — `run_fleet` holds
    THE definition (see `_inference_conformant`); this only forwards to it so the report and the
    power computation can never drift apart. D22 was caused by a second copy of a rule."""
    return rf._inference_conformant(e)
# R3 scrutiny: fleet INT template -> (probe mechanism, screen Δ figure, raw pointer)
_PROBE_SCREEN = {
    "int_sum64": ("probe_P1_sum64_bc_x_opt", 5.29), "int_sumsq": ("probe_P1_sum64_bc_x_opt", 5.29),
    "int_min32": ("probe_P2_min32_bc_x_opt", 11.40), "int_max32": ("probe_P2_min32_bc_x_opt", 11.40),
    "int_revsum": ("probe_P4_rev64_wrap_x_opt", 5.22),
    "int_horner64": ("ctrl_planted (map)", 10.18), "int_horner32": ("ctrl_planted (map)", 10.18),
}


# Dataset-R anchor -> the v1 delta_probe unit that characterised the SAME physical kernel.
# Pinned explicitly rather than fuzzy-matched: `ppoly`'s Phase-P symbol is bare `evaluate`, which
# substring-matches several unrelated units, and a silent mismatch here would fabricate a
# cross-version comparison between two different kernels.
_R_V1_UNIT = {
    "csr": "csr_mean_variance_axis0",
    "pava": "_inplace_contiguous_isotonic_regression",
    "lda": "_dirichlet_expectation_2d",
    "binning": "_map_to_bins",
    "ppoly": "ppoly_evaluate",
    "floyd": "floyd_warshall",
    "cc": "connected_components",
    "elkan": "elkan_iter_chunked_dense",
    "predictor": "_predict_from_raw_data",
}


def _load(p, default=None):
    return json.load(open(p)) if os.path.exists(p) else default


def _ledger(fleet):
    p = os.path.join(fleet, "fleet_ledger.jsonl")
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def _r(x, n=4):
    return round(x, n) if isinstance(x, (int, float)) else x


def build_report(fleet):
    led = _ledger(fleet)
    acc = [e for e in led if e.get("status") == "ACCEPTED"]
    synth = [e for e in acc if e.get("dataset", "synthetic") != "R" and not e.get("holdout")]
    hold = [e for e in acc if e.get("holdout") and e.get("dataset", "synthetic") != "R"]
    anchors = [e for e in acc if e.get("dataset") == "R"]
    # REJECTED_CLONE is NOT deduped: one slot may legitimately accrue several distinct
    # clone-rejections (different parameterizations) before it accepts — each is a real attempt.
    rejected = [e for e in led if e.get("status") == "REJECTED_CLONE"]
    # SLOT_EXHAUSTED is terminal per slot, but a relaunch re-walks an already-exhausted slot and
    # re-ledgers it (every re-attempt hits the free PARAMS_DUPLICATE pre-guard, no measurement).
    # Attrition is a count of DISTINCT slots, so dedupe by slot identity — an undeduped count
    # scales with the number of relaunches, not with the data.
    exhausted = list({(e.get("kernel_id") or e.get("slot")): e
                      for e in led if e.get("status") == "SLOT_EXHAUSTED"}.values())
    man = _load(os.path.join(fleet, "FREEZE_MANIFEST.json"))
    controls = _load(os.path.join(fleet, "controls", "controls_gate.json"))

    L = ["# CHECKPOINT P-2 — Fleet Report (decision-grade)", "",
         "STOP-for-human. Taxonomy v2 per the frozen A-2 (PREREG §12 A-2a–i); membership is each",
         "kernel's OWN full-table class (rider R3). Raw: `results/fleet/<kernel>/{table.jsonl,",
         "class_v2.json,endpoint.json}`, ledger `results/fleet/fleet_ledger.jsonl`. Recompute: this",
         "script + `scripts/phasep/a2_reclassify.py` per kernel.", ""]

    # ---- 1 freeze + counts ----
    L += ["## 1. Freeze + per-regime counts (vs the n=26 power floor, PREREG §2)"]
    if man:
        L += [f"- **FROZEN**: {man['n_kernels']} kernels in `FREEZE_MANIFEST.json` "
              f"(sha256 per table + class_v2; §11 hash-verified at every study load)."]
    else:
        L += ["- **NOT FROZEN YET** — no FREEZE_MANIFEST.json; this is a progress snapshot and "
              "no study may run (structural guard, run_study.py)."]
    counts, by_wave = {}, {}
    for e in synth:
        c = _cell(e)
        counts[c] = counts.get(c, 0) + 1
        w = e.get("wave", 1)
        by_wave.setdefault(c, {})[w] = by_wave.setdefault(c, {}).get(w, 0) + 1
    L += ["", "Membership is the MEASURED confirmatory CELL (A-2c verbatim; the FLAT family is the",
          "FM-FLAGGED cell — bare measured-FLAT with FM− is descriptive-only and counts toward no",
          "floor). Wave 1 = original campaign; wave 2 = Amendment A-3 top-up supply.", "",
          "**The floor and the power are evaluated on the §4-CONFORMANT n**, i.e. after removing the",
          "`agreement_fail` kernels that PREREG §4 excludes from per-class inference. Power at the",
          "as-measured n would be the power of an inference that is never run.", "",
          "The `excluded` column is `agreement_fail` (PREREG §4) PLUS the endpoint-voided kernels "
          "(DEV-1b): three kernels whose entire endpoint tier sits inside the D23 sanitizer "
          "overlay, so their agreement bit was computed on a landscape the product may not emit "
          "and is NOT EVALUABLE. A check that could not be performed is not a check that passed.", "",
          "| confirmatory cell | n as-measured | excluded (§4 + voided) | **n conformant** | wave 1 | "
          "wave 2 | exact power @δ=0.4 (at conformant n) | vs floor 26 |",
          "|---|---|---|---|---|---|---|---|"]
    pw = _load(os.path.join(fleet, "exact_power.json"))
    pw_by_n = (pw or {}).get("power_by_n", {})

    def _power(n):
        """A-3g: exact power at the ACHIEVED n from the COMMITTED generator — never interpolated,
        never hand-entered. Absent file ⇒ say so, never guess."""
        v = pw_by_n.get(str(n))
        return f"{v:.3f}" if isinstance(v, (int, float)) else "**PENDING**"

    # PREREG §4 (verbatim): a kernel failing the binary agreement check "is flagged agreement_fail;
    # ... at P-2/fleet it is EXCLUDED FROM PER-CLASS INFERENCE (moved to descriptive-only) and the
    # count is presented at the P-2 STOP". Unconditional — no threshold. The n's reported here are
    # therefore shown BOTH ways: as measured, and on the pre-registered inference set.
    agfail, cf_wave = {}, {}
    for e in synth:
        c = _cell(e)
        if not _conformant(e):
            agfail[c] = agfail.get(c, 0) + 1
        else:
            cf_wave.setdefault(c, {})
            w = e.get("wave", 1)
            cf_wave[c][w] = cf_wave[c].get(w, 0) + 1
    n_met = 0
    for reg in REGIMES:
        n = counts.get(reg, 0)
        w = cf_wave.get(reg, {})
        naf = agfail.get(reg, 0)
        nc = n - naf
        if nc >= FLOOR_N:
            note, n_met = "OK", n_met + 1
        else:
            note = (f"**BELOW FLOOR by {FLOOR_N - nc}** "
                    + (f"(as-measured n={n} would read OK — the whole gap is the {naf} "
                       f"§4/voided exclusions)" if n >= FLOOR_N else
                       f"(as-measured n={n} is also below)"))
        L.append(f"| {reg} | {n} | {naf} | **{nc}** | {w.get(1, 0)} | {w.get(2, 0)} | "
                 f"{_power(nc)} | {note} |")
    dn = counts.get(DESCRIPTIVE_CELL, 0)
    dw = cf_wave.get(DESCRIPTIVE_CELL, {})
    daf = agfail.get(DESCRIPTIVE_CELL, 0)
    L.append(f"| {DESCRIPTIVE_CELL} | {dn} | {daf} | {dn - daf} | {dw.get(1, 0)} | "
             f"{dw.get(2, 0)} | — | — | not confirmatory |")
    L += ["", f"**{n_met} of {len(REGIMES)} confirmatory cells meet the pre-registered n=26 floor.** "
          "Wave columns are counted on the conformant set, so they sum to the conformant n."]
    if pw:
        g = pw["generator"]
        L += ["", f"_Exact power: `{g['source']}` at N_SIM={g['n_sim']}, seed={g['seed']}, "
              f"α={g['alpha']}, {g['test']}. Raw `results/fleet/exact_power.json`; recompute: "
              f"`{pw['recompute']}`. Target at the floor is 0.80._"]
    else:
        L += ["", "_Exact power: **NOT YET COMPUTED** — run `scripts/phasep/exact_power.py` in the "
              "pinned image (A-3g forbids hand-interpolation, so the column stays PENDING rather "
              "than being filled from the n=6..17 preview table)._"]

    # ---- 1b. Holdout H, per provenance (A-7e) ----
    L += ["", "### 1b. Holdout H — cells × provenance (A-7e)", ""]
    if hold:
        hcells, hprov = {}, {}
        for e in hold:
            c = _cell(e)
            p = e.get("provenance") or "unlabelled (pre-A-7)"
            hcells.setdefault(c, {}).setdefault(p, 0)
            hcells[c][p] += 1
            hprov[p] = hprov.get(p, 0) + 1
        provs = sorted(hprov)
        L += ["H is the P4 acceptance set and is NEVER in the P3 study set. Ruling: ≥3 per "
              "confirmatory cell, ≥15 total. **H-ext** kernels are drawn from the A-7 extended "
              "registries — parameterizations OUTSIDE the training grid — so H is a MILD "
              "EXTRAPOLATION of the training distribution, which makes RQ-P2 a harder and more "
              "realistic generalization test, not a weaker one. A-7e PRE-REGISTERS that RQ-P2 "
              "acceptance at P4 is reported SLICED by this column, never only pooled.", "",
              "| cell | " + " | ".join(provs) + " | total | vs ≥3 |",
              "|---|" + "---|" * (len(provs) + 2)]
        for reg in REGIMES:
            row = hcells.get(reg, {})
            tot_c = sum(row.values())
            L.append(f"| {reg} | " + " | ".join(str(row.get(p, 0)) for p in provs)
                     + f" | {tot_c} | {'OK' if tot_c >= 3 else f'**SHORT by {3 - tot_c}**'} |")
        L += [f"| **total** | " + " | ".join(str(hprov[p]) for p in provs)
              + f" | **{len(hold)}** | {'OK' if len(hold) >= 15 else f'**SHORT by {15 - len(hold)}**'} |"]
    else:
        L += ["- No accepted H kernels on the ledger yet."]
    # ---- 1c. FEAS contrast on the §4-conformant sets (A-2g rider R1) ----
    # This is the PRODUCT's key question — "does letting the search enter infeasible space help?" —
    # so its n is verified on the inference set before it is called powered, never assumed from the
    # as-measured counts.
    fp = [e for e in synth if e.get("flag_FEAS")]
    fn_ = [e for e in synth if not e.get("flag_FEAS")]
    fpc = [e for e in fp if _conformant(e)]
    fnc = [e for e in fn_ if _conformant(e)]
    L += ["", "### 1c. FEAS contrast — conformant n (A-2g rider R1)", "",
          "The FEAS+/FEAS− contrast is POOLED across cells, so its n is the ARM size. Verified on "
          "the §4-conformant set:", "",
          "| arm | n as-measured | agreement_fail | **n conformant** | exact power @δ=0.4 | vs floor 26 |",
          "|---|---|---|---|---|---|"]
    for nm, allr, cfr in (("FEAS+", fp, fpc), ("FEAS−", fn_, fnc)):
        L.append(f"| {nm} | {len(allr)} | {len(allr) - len(cfr)} | **{len(cfr)}** | "
                 f"{_power(len(cfr))} | "
                 f"{'POWERED' if len(cfr) >= FLOOR_N else '**BELOW FLOOR**'} |")
    L += ["", f"Both arms clear the floor on the conformant set "
          f"({len(fpc)} / {len(fnc)}), so the FEAS contrast is the one confirmatory comparison in "
          "this checkpoint that is powered at δ=0.4."
          if (len(fpc) >= FLOOR_N and len(fnc) >= FLOOR_N) else
          "", "",
          "Per-cell conformant split of the arms (for the P-3 stratified read; small cells are "
          "stated as small, never pooled away):", "",
          "| cell | FEAS+ conformant | FEAS− conformant |", "|---|---|---|"]
    for reg in REGIMES + (DESCRIPTIVE_CELL,):
        L.append(f"| {reg} | {sum(1 for e in fpc if _cell(e) == reg)} | "
                 f"{sum(1 for e in fnc if _cell(e) == reg)} |")
    L += ["", f"Holdout H: {len(hold)} synth (sealed, P4 only) · Dataset R: {len(anchors)}/9 anchors "
          f"· rejected clones: {len(rejected)} · exhausted slots: {len(exhausted)}", ""]

    # ---- 2 confusion + R3 ----
    cols = REGIMES + (DESCRIPTIVE_CELL,)
    L += ["## 2. Intended-vs-measured v2 confusion (all fleet kernels, measured CELLS)", "",
          "| intended \\ measured | " + " | ".join(cols + ("other",)) + " |",
          "|---|" + "---|" * (len(cols) + 1)]
    conf = {}
    for e in synth + hold:
        i, m = e.get("intended_regime"), _cell(e)
        conf.setdefault(i, {}).setdefault(m, 0)
        conf[i][m] += 1
    for i in ("FLAT+FM", "MID", "LEVER-SEP", "INT", "FLAT"):
        row = conf.get(i, {})
        cells = [str(row.get(m, 0)) for m in cols]
        other = sum(v for k, v in row.items() if k not in cols)
        L.append(f"| {i} | " + " | ".join(cells) + f" | {other} |")
    L += ["", "_Row 'FLAT' = the honest-null stratum (intended FLAT∧FM−). Diagonal for the FLAT+FM_",
          "_family is the FM-flagged cell only._"]
    L += ["", "**R3 INT scrutiny (screen-vs-table inflation, D5 lesson):**", "",
          "| kernel | template | probe/screen Δ | full-table Δ_strict | ratio | ≥2× flag |",
          "|---|---|---|---|---|---|"]
    for e in synth + hold:
        if e.get("intended_regime") != "INT":
            continue
        cv = _load(os.path.join(fleet, e["kernel_id"], "class_v2.json"), {})
        ds = cv.get("delta_strict")
        probe = _PROBE_SCREEN.get(e.get("template"), ("?", None))
        ratio = (probe[1] / ds) if (ds and probe[1]) else None
        flag = "**INVESTIGATE**" if (ratio and ratio >= 2.0) else ("ok" if ratio else "?")
        L.append(f"| {e['kernel_id']} | {e.get('template')} | {probe[1]} ({probe[0]}) | "
                 f"{_r(ds)} | {_r(ratio, 2)} | {flag} |")
    L.append("")

    # ---- 3 diversity ----
    L += ["## 3. Diversity evidence (the power claim's foundation — A-2d/R2)", ""]
    recs = [{"regime_key": e.get("slot", "")[6:].rsplit("_", 2)[0] if e.get("slot") else "?",
             "template": e.get("template"), "p": e.get("p")}
            for e in synth if e.get("p")]
    if recs:
        rep = g2.spread_report(recs)
        for reg, r in sorted(rep.items()):
            L.append(f"- **{reg}**: n={r['n']}, templates={len(r['templates'])} "
                     f"({', '.join(r['templates'])}); min within-template max|Δp| = "
                     f"{_r(r['min_within_template_distance'])} (must be ≥ {g2.EPS_CLONE}).")
    L += ["", f"**Anti-clone rejection log** ({len(rejected)} rejections, distances in the ledger):"]
    for e in rejected[:20]:
        L.append(f"- {e.get('kernel_id')} (template {e.get('template')}): max|Δp|="
                 f"{_r(max(e.get('clone_distances', [0])))} < {g2.EPS_CLONE}")
    if len(rejected) > 20:
        L.append(f"- … {len(rejected) - 20} more (ledger).")
    L.append("")

    # ---- 4 validity ----
    L += ["## 4. Measurement validity", ""]
    ag = [e.get("agreement_ok") for e in acc if e.get("agreement_ok") is not None]
    n_fail = sum(1 for x in ag if x is False)
    if ag:
        frac = n_fail / len(ag)
        L += ["> **PREREG §4, VERBATIM, IS THE ONLY RULE APPLIED HERE.** *\"a kernel failing the "
              "binary check is flagged `agreement_fail`; … at P-2/fleet it is **excluded from "
              "per-class inference (moved to descriptive-only)** and the count is presented at the "
              "P-2 STOP (so the human approves a rule, not a case-by-case call).\"* It is "
              "**unconditional — there is no threshold in it.** Earlier drafts of this report "
              "applied a *\">10% ⇒ measurement-auditor investigation\"* rule attributed to "
              "\"B_02\"; that string does not occur anywhere in `PREREG_PHASEP.md` — it is from "
              "`results/pilot/A2_DECISION_MEMO.md:400`, a decision memo, and it had been hardcoded "
              "into this generator. Found by the stats-auditor; the generator defect is **D22**. "
              "The threshold has been DELETED from the code: it now governs nothing, and is "
              "recorded only in `DEVIATIONS_REGISTER.md`.", ""]
        L.append(f"- Agreement watch: {n_fail}/{len(ag)} kernels with agreement_binary_ok=False "
                 f"({frac:.1%}). Each is `agreement_fail`, is excluded from per-class inference by "
                 f"§4, and is retained as descriptive-only. This is the count §4 requires be "
                 f"presented at the STOP.")
        # The POOLED rate is misleading in both directions, so it is never reported alone.
        # agreement_binary_ok asks whether the SCREEN's argmin lands within 2% of the ENDPOINT's
        # argmin. On a flat landscape every config sits inside the ~2% noise floor, so any argmin
        # passes trivially; only a landscape with a real ranking can fail it. The rate therefore
        # TRACKS RUGGEDNESS by construction — P-1 recorded the same pattern for τ_b and noted that
        # uniformly HIGH agreement would be the alarm.
        by_cell = {}
        for e in acc:
            if e.get("agreement_ok") is None:
                continue
            c = _cell(e)
            s = by_cell.setdefault(c, [0, 0])
            s[0] += 0 if e["agreement_ok"] else 1
            s[1] += 1
        L += ["", "| measured cell | agreement failures / n | rate |", "|---|---|---|"]
        for c in REGIMES + (DESCRIPTIVE_CELL, "FLAT"):
            if c in by_cell:
                f_, n_ = by_cell[c]
                L.append(f"| {c} | {f_}/{n_} | {100 * f_ / n_:.1f}% |")
        L += ["", "**MEASUREMENT-AUDITOR REFERRAL — NOT SELF-DISCHARGED.** §4's exclusion rule "
              "handles the INFERENCE consequence, but it does not answer whether the failures are "
              "a RIG fault; that question is routed to the measurement-auditor unconditionally, "
              "and is NOT closed by the ruggedness explanation above — that explanation is a "
              "hypothesis to be tested, not a discharge. Three questions it must answer:", "",
                  "1. Is the pooled rate explained by regime composition alone, or is there "
                  "residual time-correlation after conditioning on measured cell?",
                  "2. Does any single run_id show excess failures beyond what its regime mix "
                  "predicts?",
                  "3. Do failing kernels show endpoint anomalies (n_sub inflation from the >5% CV "
                  "retry loop, rig-fingerprint drift, thermal) that passing kernels of the SAME "
                  "cell do not?", "",
                  "_Scheduling caution for the period slice: the apparent 6/6 failure window at "
                  "20260722 is `fleet_INT_12`–`17` — the day the INT block was scheduled. Split by "
                  "regime or a scheduling artifact reads as a rig artifact._",
                  "", "_The freeze is write-once, which prevents silent mutation, not "
                  "investigation. A confirmed rig fault escalates to the human; it is never "
                  "self-resolved._"]
    bflags = [(e["kernel_id"], e["boundary_flags"]) for e in acc if e.get("boundary_flags")]
    L.append(f"- Boundary-adjacent kernels (rider R2, ±0.01): {len(bflags)}"
             + (f" — {', '.join(k for k, _ in bflags[:10])}" if bflags else ""))
    if controls:
        p, f = controls.get("planted", {}), controls.get("flat", {})
        L.append(f"- Controls re-gate (fresh, results/fleet/controls/): planted Δ={_r(p.get('delta_all'))} "
                 f"opt_top={p.get('opt_top')} → {'PASS' if p.get('ok') else 'FAIL'}; "
                 f"flat Δ={_r(f.get('delta_all'))} → {'PASS' if f.get('ok') else 'FAIL'}.")
    else:
        L.append("- Controls re-gate: NOT YET RUN (results/fleet/controls/ absent).")
    L.append("")

    # ---- 5 envelope ----
    L += ["## 5. Envelope actuals vs PREREG §10 (verbatim: \"≈ 55–105 min/kernel … Fleet ≈ 120 "
          "synthetic + 9 R ⇒ ≈ 5–9.5 days machine time\")", ""]
    tot = [(e.get("build_s") or 0) + (e.get("measure_s") or 0) for e in acc
           if (e.get("build_s") or e.get("measure_s"))]
    if tot:
        L.append(f"- measured kernels n={len(tot)}: min={min(tot)/60:.0f}m "
                 f"median={st.median(tot)/60:.0f}m max={max(tot)/60:.0f}m; campaign total so far "
                 f"= {sum(tot)/3600:.1f} h.")

    # Per-cap actuals. Both caps are defined over Σ(build_s+measure_s+orphan_s) across their own
    # ledger cycles, ANY status — failures and reconciled deaths charge in full.
    def _spend(pred):
        return sum((e.get("build_s") or 0) + (e.get("measure_s") or 0) + (e.get("orphan_s") or 0)
                   for e in led if pred(e))
    w2 = _spend(lambda e: e.get("wave") == 2)
    h = _spend(lambda e: e.get("run_kind") == "holdout")
    r = _spend(lambda e: e.get("run_kind") == "anchors" or e.get("dataset") == "R")
    L += ["", "| budget | cap | charged | % of cap | stop record |", "|---|---|---|---|---|"]
    for name, spent, cap, status in (("A-3d wave-2 top-up", w2, 172800, "TOPUP_CAP_STOP"),
                                     ("A-7d holdout H", h, 86400, "H_CAP_STOP")):
        fired = any(e.get("status") == status for e in led)
        L.append(f"| {name} | {cap:,} s | {spent:,.1f} s | {100 * spent / cap:.2f}% | "
                 f"{status if fired else 'not fired'} |")
    L.append(f"| Dataset R anchors | (uncapped) | {r:,.1f} s | — | — |")

    # D20: three wave-2 CYCLE_ORPHAN rows charged 0.0 s (build-phase deaths the pre-fix reconciler
    # could not see). The charged figure is therefore a LOWER bound and must be reported as one.
    zero_orph = [e for e in led if e.get("status") == "CYCLE_ORPHAN"
                 and (e.get("orphan_s") or 0) == 0.0]
    if zero_orph:
        L += ["", f"**D20 — the wave-2 figure above is a LOWER bound.** {len(zero_orph)} "
              f"`CYCLE_ORPHAN` rows carry `orphan_s == 0.0` exactly: builds killed before the "
              f"pre-fix reconciler could see them (it watched the run log, whose mtime never "
              f"advances during a build because the child's stdout is block-buffered). The exact "
              f"undercharge is NOT recoverable — those kernel dirs were later resumed to "
              f"completion, overwriting the bounding mtimes. The recoverable UPPER bound from the "
              f"run_id windows is **≤ 7,266 s (2.02 h)**, so true wave-2 rig time lies in "
              f"**[{w2:,.1f} , {w2 + 7266:,.1f}] s** and the overrun past the 172,800 s cap lies in "
              f"**[{(w2 - 172800) / 3600:.2f} h , {(w2 + 7266 - 172800) / 3600:.2f} h]**. An "
              f"undercharge stops the runner LATE, never early, so no kernel was denied a cycle, "
              f"and no measured value is affected — `orphan_s` feeds the cap gate and nothing "
              f"else. Fixed and regression-tested; post-mortem `logs/defects/D20.md`."]
    L.append("")

    # ---- 5b. The H supply story (A-7) ----
    L += ["## 5b. Holdout-H supply: exhaustion evidence, the amendment, the attempt ledger", ""]
    hrows = [e for e in led if e.get("run_kind") == "holdout"]
    if hrows:
        by_status = {}
        for e in hrows:
            by_status[e.get("status")] = by_status.get(e.get("status"), 0) + 1
        L += [f"H ledger rows: {len(hrows)} — "
              + " · ".join(f"{k} {v}" for k, v in sorted(by_status.items())), "",
              "**Why A-7 exists.** The D8 pre-guard keys on `(template, params, feas_variant)` "
              "fleet-wide, and the training campaign consumed 169 such keys. `H_START_INDEX` "
              "renumbers slots but does not refill the pool. Fresh supply for H at the blocker was "
              "MID 14 · LEVER-SEP 13 · FLAT+FM 5 · **INT 0** — the ≥3-per-cell ruling was "
              "structurally unsatisfiable for INT, and the original non-W2 registries did not "
              "rescue it (FLAT_FM 0, INT 0). H's first slot PROVED it rather than projecting it: "
              "nine consecutive `PARAMS_DUPLICATE` skips then `SLOT_EXHAUSTED`, at **zero** "
              "measurement cost.", "",
              "**Two distinct SLOT_EXHAUSTED modes, both P-2 findings and not the same finding:** "
              "*supply-driven* (every candidate hit the free dup-skip pre-guard — costs nothing, "
              "means the parameter space is spent) and *clone-driven* (candidates were measured "
              "and rejected as clones — costs full cycles, means the landscape space is spent). "
              "Counting them together would report a budget problem as a diversity problem.", "",
              "Amendment: PREREG §12 **A-7** + `results/fleet/A7_H_SUPPLY_AMENDMENT.md` "
              "(supply-only; 102 extended keys verified 0-collision BEFORE commit; ONE-SHOT — "
              "A-7c forbids a second extension). Ordering evidence: the amendment commit precedes "
              "any `FLAT_FM_H`/`INT_H` registry code, which precedes any extended kernel."]
        # A-7f may only be DECLARED once H has actually terminated. A cell reading short while the
        # walk is still filling it is not a structural finding, it is an unfinished campaign — and
        # "INT cannot reach 3" is precisely the claim that must never be made prematurely. The
        # sealed H manifest is the unambiguous terminal marker.
        h_sealed = os.path.exists(os.path.join(fleet, "H_MANIFEST.json"))
        short_h = [c for c in REGIMES if sum(1 for e in hold if _cell(e) == c) < 3]
        if not h_sealed:
            L += ["", f"_H is **still running** (not sealed). Cells below floor right now "
                  f"({', '.join(short_h) if short_h else 'none'}) are an unfinished walk, NOT a "
                  f"finding — A-7f can only be declared after H stops._"]
        elif "INT" in short_h:
            L += ["", "**A-7f STRUCTURAL FINDING — INT did not reach 3 even on fresh extended "
                  "parameters.** Reported with the attempt ledger above and NOT iterated (A-7c). "
                  "This is consistent with v1's real-code evidence that strict directive×flag "
                  "interactions are rare: the INT-producing parameter region is narrow."]
        elif short_h:
            L += ["", f"**H SHORT at stop: {', '.join(short_h)}** — reported as measured, with the "
                  f"attempt ledger. A-7c forbids a second extension."]
    else:
        L += ["- No H rows on the ledger yet."]
    L.append("")

    # ---- 5c. Defect series ----
    L += ["## 5c. Defect series (complete)", ""]
    ddir = os.path.join(os.path.dirname(os.path.dirname(fleet.rstrip("/"))), "logs", "defects")
    if os.path.isdir(ddir):
        ds = sorted((f for f in os.listdir(ddir) if f.startswith("D") and f.endswith(".md")),
                    key=lambda f: int(f[1:-3]))
        for f in ds:
            first = ""
            with open(os.path.join(ddir, f)) as fh:
                for line in fh:
                    if line.startswith("# "):
                        first = line[2:].strip()
                        break
            # D-file titles already begin with their own "Dn — "; do not prefix it twice.
            L.append(f"- {first if first.startswith(f[:-3]) else f'**{f[:-3]}** — {first}'}")
        L += ["", f"_{len(ds)} post-mortems, `logs/defects/`. Silent defects (found by inspection "
              f"rather than a red gate) are marked as such in their own files._"]
    else:
        L += ["- defects directory not found."]
    L.append("")

    # ---- 5d. Dataset R (real code) ----
    # R currently appeared only as a COUNT in §1, which wastes the one part of the dataset that is
    # not synthetic. R is also the only independent check on the v1 -> v2 taxonomy transfer: these
    # are the same physical kernels v1 characterised, re-measured under a different classifier.
    L += ["## 5d. Dataset R — real-code anchors (all 9 v1 survivors, full 1728 tables)", ""]
    if anchors:
        L += ["| anchor | measured v2 | Δ_all | Δ_strict | IF_strict | FM | FEAS | agree | cycle |",
              "|---|---|---|---|---|---|---|---|---|"]
        for e in sorted(anchors, key=lambda x: x.get("kernel_id", "")):
            cv = _load(os.path.join(fleet, e["kernel_id"], "class_v2.json"), {})
            hrs = ((e.get("build_s") or 0) + (e.get("measure_s") or 0)) / 3600
            iff = cv.get("if_strict")
            L.append(f"| {e.get('anchor')} | **{e.get('measured_v2')}** | {_r(cv.get('delta_all'))} "
                     f"| {_r(cv.get('delta_strict'))} | {_r(iff) if iff is not None else 'null'} "
                     f"| {e.get('flag_FM')} | {e.get('flag_FEAS')} | {e.get('agreement_ok')} "
                     f"| {hrs:.2f} h |")
        dist = {}
        for e in anchors:
            c = _cell(e)
            dist[c] = dist.get(c, 0) + 1
        L += ["", f"Measured-class distribution across real code: **{dist}** "
              f"({len(anchors)}/9 complete).", ""]
        # Cross-version transfer. v1's delta_probe is a 16-CONFIG SCREEN at v1's ~500 ms scale;
        # Phase P is the FULL 1728 table at the 50-80 ms band. The comparison is therefore
        # scale- AND breadth-confounded and is reported as a transfer check, never as agreement
        # between two estimates of the same quantity. The R3 rider's >=2x screen-vs-table
        # inflation bar (the D5 lesson) is applied here exactly as it is applied to INT.
        L += ["**v1 → v2 transfer check** (R3 discipline). Phase P is the **full 1728 table at "
              "50–80 ms**; v1 is scale- and breadth-confounded against it, so this is a transfer "
              "check, not an agreement test between two estimates of one quantity. Bar: a ratio "
              "≥ 2× is INVESTIGATED before the freeze (D5 lesson).", "",
              "**The v1 comparator is the CLEAN ENDPOINT record, not the screen.** D5 established "
              "that the v1 16-config *screen* rig was contaminated for `floyd`: two of its 16 "
              "configs timed at 786/810 ms against a true ~296 ms, a 2.6× inflation on exactly "
              "the two points that set the worst/best ratio, giving a spurious Δ_all 3.188 where "
              "the clean median-of-3-subprocess endpoint gives 1.338. Comparing Phase P against "
              "the screen would resurrect a number this repo already knows is wrong and flag a "
              "false INVESTIGATE. The screen/endpoint spread is shown alongside because it is "
              "itself the evidence: **8 of 9 units agree within 1–9%; `floyd` alone is 2.38× off.**",
              "",
              "| anchor | v1 screen span | v1 **endpoint** span | screen/endpt | P span (1728) "
              "| v1/P span | ≥2× |",
              "|---|---|---|---|---|---|---|"]
        # NOTE: the columns below are SPAN vs SPAN (worst/best), NOT Phase P's committed Δ_all.
        # See the "metric identity" paragraph after the table — comparing v1's worst/best against
        # P's t_ref/t_star is a category error that manufactured a false 2.41x flag on elkan.
        dpdir = os.path.join(os.path.dirname(os.path.dirname(fleet.rstrip("/"))),
                             "results", "characterization", "delta_probe")
        for e in sorted(anchors, key=lambda x: x.get("kernel_id", "")):
            unit = _R_V1_UNIT.get(e.get("anchor"))
            scr = _load(os.path.join(dpdir, f"{unit}.json"), {}) if unit else {}
            end = _load(os.path.join(dpdir, f"{unit}__endpoint.json"), {}) if unit else {}
            # LIKE FOR LIKE: v1's delta_all IS t_worst/t_best. Phase P's committed delta_all is
            # t_ref/t_star (speedup over the DEFAULT config) — a different quantity. The
            # comparable Phase P figure is therefore its own worst/best span, recomputed here
            # from the frozen table.
            ms = []
            tpath = os.path.join(fleet, e["kernel_id"], "table.jsonl")
            if os.path.exists(tpath):
                for line in open(tpath):
                    r = json.loads(line)
                    if r.get("feasible") and r.get("screen", {}).get("median_ns"):
                        ms.append(r["screen"]["median_ns"])
            s, a = scr.get("delta_all"), end.get("delta_all")
            b = (max(ms) / min(ms)) if ms else None
            se = (s / a) if (s and a) else None
            ratio = (a / b) if (a and b) else None
            flag = "**INVESTIGATE**" if (ratio and ratio >= 2.0) else ("ok" if ratio else "?")
            note = " ⚠D5" if (se and se >= 2.0) else ""
            L.append(f"| {e.get('anchor')}{note} | {_r(s)} | {_r(a)} | {_r(se, 2)} | {_r(b)} "
                     f"| {_r(ratio, 2)} | {flag} |")
        L += ["", "_⚠D5 marks a unit whose v1 SCREEN was contamination-inflated; its screen column "
              "is retained only as the evidence for that finding and is never the comparator._", "",
              "**METRIC IDENTITY — the columns above are SPAN vs SPAN, and this matters.** v1's "
              "`delta_all` is `t_worst / t_best` (the full landscape span). Phase P's **committed** "
              "`delta_all` is `t_ref / t_star` (`classify.py`) — the speedup of the best config "
              "over the **REFERENCE/default** config, which is a different quantity and is always "
              "the smaller of the two. Comparing v1's span against P's committed Δ therefore "
              "measures `t_worst / t_ref` — how much slower the worst config is than the default — "
              "and has nothing to do with cross-version agreement. Doing exactly that manufactured "
              "a spurious **2.41× INVESTIGATE flag on `elkan`**; on the like-for-like span "
              "comparison elkan is **1.009**, the closest transfer of all nine. The column above "
              "recomputes P's own worst/best span from the frozen table for this reason. "
              "Post-mortem: `logs/defects/D21.md`.", "",
              "_P's span runs consistently ≥ v1's (ratios ≤ 1) because P sweeps 1728 configs "
              "against v1's 16 and therefore finds wider extremes — the expected direction._", "",
              "**OpenMP, corrected.** An earlier draft of this section asserted that `elkan` and "
              "`predictor` are compiled WITHOUT `-fopenmp` and therefore measured on a serial "
              "path. **That was wrong.** `build.py` does consume the flag — "
              "`omp = [\"-fopenmp\"] if meta.get(\"openmp\") else []` — and both anchors carry "
              "`openmp: true` in `kernel_meta.json`, so both are built WITH OpenMP, exactly as v1 "
              "built them (`delta_probe_pkg.py` passes `-fopenmp` too). The earlier claim came "
              "from grepping `build_phase.py`, `measure_phase.py`, `measure_child.py` and "
              "`measure_wrap.sh` and concluding from four misses that nothing read the flag — "
              "without checking `build.py`, where it is actually consumed. What remains true is "
              "narrower and is a property of the DRIVER, not the build: "
              "`corpus_drivers.elkan_setup`/`predictor_setup` pass `n_threads=1`, so the kernels "
              "run single-threaded on the isolated core as the timing discipline requires. v1 did "
              "the same, so the two versions are directly comparable on this axis.", ""]
    else:
        L += ["- No R anchors measured yet.", ""]

    # ---- 6 auditors ----
    L += ["## 6. Auditor verdicts", ""]
    # Fixed roster, rendered from the committed verdict file. An auditor with no entry renders
    # NOT RUN — a checkpoint report whose audit section reads like a plan must never be
    # indistinguishable, at a glance, from one whose audits passed.
    ver = _load(os.path.join(fleet, "AUDIT_VERDICTS.json"), {}) or {}
    roster = [
        ("stats-auditor", "independent recompute of all 149 classifications, the A-2c cell table, "
         "confusion, FEAS in integer arithmetic, wave + provenance slices, exact power. Zero diff "
         "required."),
        ("measurement-auditor", "≥20% seeded sample spanning waves/H-orig/H-ext/R/fat-tail; rig "
         "fingerprints; the period slice; the three §2c questions on the agreement watch."),
        ("validation-auditor", "oracle + determinism recompute, 100% across Dataset R, where 7 of "
         "9 adapters had never executed before this phase."),
        ("scrutinize", "final pass before this report leaves the repo."),
    ]
    L += ["| auditor | scope | verdict |", "|---|---|---|"]
    for name, scope in roster:
        v = ver.get(name)
        L.append(f"| {name} | {scope} | "
                 + (f"**{v.get('verdict', '?')}** — {v.get('summary', '')} "
                    f"({v.get('ref', 'no ref')})" if isinstance(v, dict)
                    else (f"**{v}**" if v else "**NOT RUN**")) + " |")
    missing = [n for n, _ in roster if not ver.get(n)]
    failed = [n for n, _ in roster
              if isinstance(ver.get(n), dict) and "FAIL" in str(ver[n].get("verdict", ""))]
    if missing or failed:
        L += ["", "> **THIS REPORT IS NOT SIGN-OFF READY.**"
              + (f" Not run: {', '.join(missing)}." if missing else "")
              + (f" FAIL verdicts outstanding: {', '.join(failed)}." if failed else "")]
    L += ["", "**Standing consequence, stated explicitly:** *correctness absolute* is a hard gate. "
          "The pre-R smoke was build-only by design and closed \"do these compile\", never \"is the "
          "output right\" — so no claim in §5d is correctness-backed except through the "
          "validation-auditor's recompute. The agreement watch of §4 is an inference rule, not a "
          "rig clearance; the rig question is the measurement-auditor's.", ""]

    # ---- 7 P3 status ----
    L += ["## 7. P3 status + guards", "",
          "- run_study.py freeze guard: no FREEZE_MANIFEST ⇒ no study (structural; sha256 at load).",
          "- CONFIRMED: no algorithm has touched any measured table (guard + this report's freeze "
          "state above).",
          "- Motif §8.4 conformance fixed + TDD; ORCA census = P3.2-full (post-freeze, own TDD)."]
    # The two seals are SEPARATE. FREEZE_MANIFEST is write-once and was committed before H existed,
    # so H could not be folded into it — and must not be: the P3 firewall depends on the training
    # set and the acceptance set being distinguishable at load time.
    n_hold_in_freeze = sum(1 for v in (man or {}).get("kernels", {}).values() if v.get("holdout"))
    if man:
        L.append(f"- FREEZE_MANIFEST.json: {man['n_kernels']} TRAINING kernels, of which "
                 f"{n_hold_in_freeze} holdout "
                 f"({'correct — the freeze contains no H' if n_hold_in_freeze == 0 else '**H LEAKED INTO THE FREEZE**'}).")
    hman = _load(os.path.join(fleet, "H_MANIFEST.json"))
    if hman:
        L.append(f"- H_MANIFEST.json (A-7 §7, write-once, SEPARATE from the freeze): "
                 f"{hman['n_kernels']} kernels, cells {hman.get('cells')}, provenance "
                 f"{hman.get('provenance_counts')}; per-kernel sha256 of table.jsonl + "
                 f"class_v2.json. P4 acceptance only — never the P3 study set.")
    else:
        L.append("- H_MANIFEST.json: **NOT SEALED YET** (`run_study.py --make-h-manifest`).")
    L += ["", "---", "_STOP for the human. Not self-passed._"]
    return "\n".join(L)


if __name__ == "__main__":
    fleet = sys.argv[1] if len(sys.argv) > 1 else "results/fleet"
    out = os.path.join(fleet, "P2_REPORT.md")
    open(out, "w").write(build_report(fleet))
    print(f"P2 report -> {out}")
