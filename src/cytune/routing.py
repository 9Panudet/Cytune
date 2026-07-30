"""The INTERIM routing policy, as frozen in results/prereg/CYTUNE_V0_ROUTING_INTERIM.md.

This module is a direct transcription of that document's §2 table. If the two ever disagree, the
DOCUMENT is authoritative — it was committed before the first run, and this file is only its
executable form (test_cytune_routing.py asserts the transcription against the frozen thresholds).

Nothing here is validated. The thresholds are inherited from the study's full-table classifier and
applied to a 16-point probe estimate; §9.2 itself calls the probe coarse and defers validation to
RQ-P2, which has not run. Hence the label on every output.
"""
from __future__ import annotations

LABEL = ("routing: P3-VALIDATED on the Phase-P synthetic benchmark (20-seed prefix, amendment "
         "A-10) — NOT validated on real code; RQ-P2 acceptance has not run")

# ---------------------------------------------------------------------------------------------
# P3 RESULT, and why the engine choice barely moved.
#
# The study measured every (cell x budget) with all four arms. Two findings decide what ships:
#
# 1. DOE — a deterministic D-optimal screen — is the best PRODUCT-RUNNABLE arm in 18 of 20 cells.
#    BO loses to DOE in 18 of 20 and is worse than RANDOM SEARCH in several. The expensive
#    Bayesian arm does not earn its cost on this benchmark. That is a negative result and it ships
#    as one.
#
# 2. Motif+BO won 13 of 20 cells and passes the §3.4 gate (p=3.46e-17, Cliff's delta 0.772) — and
#    is NOT INSTALLED, for two independent reasons:
#      - STRUCTURAL: it needs a corpus of previously-tuned SIBLING kernels to warm start from.
#        `cytune tune <one module>` has no such corpus. The LOKO setting that produced the win
#        does not exist at the point of use.
#      - VALIDITY: its warm-start sources are 9.7x enriched for kernels of the target's OWN
#        generated template (3.74 of 8 vs a 0.39 baseline). The advantage is substantially
#        warm-starting from a near-copy of the target's own landscape — an artifact of a synthetic
#        corpus with ~4 kernels per template. Dataset R's 9 real anchors have no siblings at all.
#
# So the routed engine stays DOE, which is what the interim policy already chose on other grounds.
# The study did not change the recommendation; it supplied the evidence for it, and killed BO's
# and Motif's claims to replace it. Full matrix: results/study/ROUTING_MATRIX.json.
#
# POWER: only INT reaches the pre-registered n=26 floor (n=29, power 0.853). FLAT+FM (n=20, 0.708),
# MID (n=24, 0.776) and LEVER-SEP (n=20, 0.708) are UNDERPOWERED at delta=0.4 and every certificate
# says so.
# ---------------------------------------------------------------------------------------------
ROUTING_MATRIX = "results/study/ROUTING_MATRIX.json"
POWERED_CELLS = ("INT",)
UNDERPOWERED_CELLS = {"FLAT+FM": 0.708, "MID": 0.776, "LEVER-SEP": 0.708}

# Inherited thresholds — see the frozen policy §3. None of these was invented for v0.
FLAT_DELTA = 1.10    # A-1b IF-evaluation floor: 5x the ~2% measured rig noise floor
LEVER_DELTA = 1.50   # A-2a MID | LEVER-SEP/INT boundary
INT_IF = 0.25        # A-2a LEVER-SEP | INT boundary
FEAS_FRAC = 0.75     # complement of A-2a's FEAS flag (infeas_frac >= 0.25)
MIN_FEASIBLE_PROBE_ROWS = 4

BUDGET_DOE = 16
BUDGET_INTERACTION = 32
BUDGET_FEAS_BONUS = 8

ABORT = "abort"
HONEST_FLAT = "honest-flat"
DOE = "doe"
INTERACTION = "interaction"


def route(feat, bo_available=False):
    """feat: the dict from probe.features(). Returns the routing decision record.

    First match wins, top to bottom, exactly as the frozen table is written.
    """
    delta = feat.get("delta_probe")
    if_probe = feat.get("if_probe")
    na = feat.get("if_probe_na")
    feas_frac = feat.get("feas_frac", 0.0)

    # R0 — cannot certify anything without a feasible reference to compare against.
    if not feat.get("reference_feasible"):
        return _rec(ABORT, 0, "R0", "the reference config is infeasible — there is no correct "
                                    "baseline to measure a speedup against", feat, bo_available)
    if feat.get("n_probe_feasible", 0) < MIN_FEASIBLE_PROBE_ROWS or delta is None:
        return _rec(ABORT, 0, "R0", f"only {feat.get('n_probe_feasible', 0)} feasible probe rows "
                                    f"(need >= {MIN_FEASIBLE_PROBE_ROWS}) — too little signal to "
                                    f"route on", feat, bo_available)

    # R1 — the honest-flat exit. Expected to be the common outcome on real code (v1 finding).
    if delta <= FLAT_DELTA:
        return _rec(HONEST_FLAT, 0, "R1",
                    f"probe spread {delta:.4f} <= {FLAT_DELTA} — at or below the noise floor, so "
                    f"any apparent speedup here is not distinguishable from measurement noise",
                    feat, bo_available)

    # R2 — degenerate probe: IF is NA, so we cannot tell separable from interaction-dominated.
    if na:
        return _rec(DOE, BUDGET_DOE, "R2",
                    "IF_probe is NA under the §9.2 degenerate-probe rule — too few feasible rows "
                    "to fit main effects, so route conservatively to DOE", feat, bo_available)

    # R3 — interaction-dominated.
    if delta >= LEVER_DELTA and if_probe >= INT_IF:
        return _rec(INTERACTION, BUDGET_INTERACTION, "R3",
                    f"probe spread {delta:.4f} >= {LEVER_DELTA} with IF_probe {if_probe:.4f} >= "
                    f"{INT_IF} — looks interaction-dominated", feat, bo_available)

    # R4 — separable lever.
    if delta >= LEVER_DELTA:
        return _rec(DOE, BUDGET_DOE, "R4",
                    f"probe spread {delta:.4f} >= {LEVER_DELTA} with IF_probe {if_probe:.4f} < "
                    f"{INT_IF} — looks like a separable lever", feat, bo_available)

    # R5 — modest but real spread.
    return _rec(DOE, BUDGET_DOE, "R5",
                f"probe spread {delta:.4f} is between {FLAT_DELTA} and {LEVER_DELTA} — modest but "
                f"above the noise floor", feat, bo_available)


def _rec(kind, budget, rule, why, feat, bo_available):
    engine, fallback = None, None
    if kind == DOE:
        engine = "DOE"
    elif kind == INTERACTION:
        if bo_available:
            engine = "BO"
        else:
            engine = "DOE"
            fallback = ("BO was selected by rule R3 but is not available in this build "
                        "(the bo-math-reviewer gate did not pass); falling back to DOE at the same "
                        "budget. This is printed, not hidden.")

    feas_bonus = 0
    if budget > 0 and feat.get("feas_frac", 1.0) < FEAS_FRAC:
        feas_bonus = BUDGET_FEAS_BONUS

    return {
        "label": LABEL,
        "route": kind,
        "rule": rule,
        "engine": engine,
        "budget": budget + feas_bonus,
        "budget_base": budget,
        "feasibility_bonus": feas_bonus,
        "why": why,
        "fallback_note": fallback,
        "feasibility_note": (
            f"only {feat.get('feas_frac', 0):.1%} of probe configs were feasible (< "
            f"{FEAS_FRAC:.0%}) — budget raised by {BUDGET_FEAS_BONUS} and the infeasible fraction "
            f"is reported prominently" if feas_bonus else None),
    }
