"""DOE planning (PREREG §8.2) — the same math as algorithms.doe, executed in host-driven rounds.

WHY NOT JUST CALL algorithms.doe(). That function drives its own adaptive loop against a sealed
table, which works when every answer is already in memory. Here each answer costs a compile and a
timed run, and compiles must happen in a different container from measurements (CF-1). So the loop
is turned inside out: the host asks this module WHAT to measure next, runs a build container and a
measure container, and asks again.

algorithms.doe queries (1) the reference, (2) the pre-registered design in order, then fits ONCE
and (3) walks the predicted ranking best-first, skipping already-queried configs. Because there is
exactly one fit, the trajectory is determined by two batches, so batching cannot change which
configs are queried nor which wins.

ONE DELIBERATE DIFFERENCE, stated because "equivalent" would be an over-claim. Given the SAME
observation set, this module reproduces algorithms.doe's trajectory exactly — pinned by
`test_cytune_plan.py::test_walk_plan_reproduces_algorithms_doe_trajectory`. But in a real run the
product conditions the fit on the probe rows too, which it has already paid for and which the study
arm never has. More observations, same estimator. That is better product behaviour and it means
cytune's DOE is NOT bit-identical to the study's DOE arm; it is the same method on a larger
observation set. Nothing here feeds the study, so this cannot affect any P3 comparison.

Fast-math policy (frozen routing policy §4): fixed pre-registered designs are measured AS
SPECIFIED — measuring is not emitting, and it is what makes the fast-math signal reportable at all.
Fast-math configs are excluded from the ADAPTIVE walk and from WINNER SELECTION unless the user
passed --allow-fast-math. Even then the oracle still decides.
"""
from __future__ import annotations
import json
import math

from ._phasep import designs_path, theta


def is_fast_math(cid):
    return theta.config_of(cid)[8][0] == "on"


def _design(budget):
    """N_d = min(24, B-1); committed designs cover N_d in {7,15,24} (PREREG §8.2 / §12-D2)."""
    designs = json.load(open(designs_path()))["designs"]
    nd = min(24, budget - 1)
    key = f"doe_{nd}" if f"doe_{nd}" in designs else "doe_24"
    return key, designs[key]["config_ids"]


def screen_plan(budget):
    """Batch 1: the pre-registered screen design, in order, up to budget (reference is free)."""
    key, design = _design(budget)
    ids, seen = [], {theta.REFERENCE_ID}
    for cid in design:
        if len(ids) >= budget:
            break
        if cid in seen:
            continue
        seen.add(cid)
        ids.append(cid)
    return {"design_key": key, "ids": ids, "reference_id": theta.REFERENCE_ID}


def walk_plan(feasible_medians, queried_ids, budget_remaining, allow_fast_math=False):
    """Batch 2: fit main effects on what the screen returned, then take the predicted-best
    unqueried configs. Mirrors algorithms.doe's post-screen ranking walk."""
    import algorithms
    if budget_remaining <= 0 or not feasible_medians:
        return {"ids": [], "fit": None}
    obs_ids = sorted(feasible_medians)
    obs_logm = [math.log(feasible_medians[c]) for c in obs_ids]
    beta, used_ols = algorithms._fit(obs_ids, obs_logm)
    ranking, _pred = algorithms._pred_rank(beta)
    out, skipped_fm = [], 0
    for cid in ranking:
        if len(out) >= budget_remaining:
            break
        if cid in queried_ids:
            continue
        if not allow_fast_math and is_fast_math(cid):
            skipped_fm += 1
            continue
        out.append(cid)
    return {"ids": out, "fit": {"n_obs": len(obs_ids), "used_ols": bool(used_ols),
                                "fast_math_skipped": skipped_fm}}


def confirm_winner(winner_id, reference_id, endpoints):
    """The second half of the never-emit-an-oracle-failing-config guarantee.

    The screen tier said this config was correct. The endpoint tier re-runs it at K=30 and
    re-checks the oracle. If it fails THERE, it must not be emitted no matter how fast it looked —
    correctness is absolute and a screen pass is not a licence. Returns (final_id, rejection).

    Extracted as a pure function precisely because it is the safety-critical branch: buried inside
    the CLI's orchestration it would be reachable only by a full container run, and a guarantee
    that is awkward to test is a guarantee that silently rots.
    """
    if winner_id is None:
        return None, None
    ep = endpoints.get(str(winner_id)) or {}
    if ep.get("feasible") and ep.get("endpoint_ns"):
        return winner_id, None
    return reference_id, {
        "rejected_config_id": winner_id,
        "reason": ep.get("reason", "endpoint measurement did not confirm the config"),
        "action": "fell back to the reference configuration",
    }


def select_winner(feasible_medians, allow_fast_math=False):
    """The best feasible config the run is allowed to emit.

    Only feasible configs are ever in `feasible_medians` — an oracle-failing config never reaches
    this function, which is the structural half of the never-emit-an-oracle-failing-config
    guarantee. The other half is the endpoint re-check in the verify step.
    """
    cands = {c: m for c, m in feasible_medians.items()
             if allow_fast_math or not is_fast_math(c)}
    if not cands:
        return None, {"n_candidates": 0}
    best = min(cands, key=lambda c: (cands[c], c))
    return best, {"n_candidates": len(cands),
                  "n_excluded_fast_math": len(feasible_medians) - len(cands)}
