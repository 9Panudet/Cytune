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

from ._vendor import designs_path, theta


def is_fast_math(cid):
    return theta.config_of(cid)[8][0] == "on"


def is_fp_contract(cid):
    """Permits FMA contraction WITHOUT being -ffast-math.

    The composite fmffp factor has three levels: (off,off) strict, (off,fast) contraction,
    (on,NA) fast-math. Contraction is a real floating-point semantics change — the compiler may
    fuse a multiply and an add and round once instead of twice — and cold-user finding F19 was
    that cytune emitted it by default while requiring an opt-in for -ffast-math. Two semantic
    changes, two different consent models, one README sentence describing both.
    """
    fm, ffp = theta.config_of(cid)[8]
    return fm == "off" and ffp == "fast"


def fp_semantics(cid):
    """'fast-math' | 'contract' | 'strict' — what this config does to floating-point results."""
    fm, ffp = theta.config_of(cid)[8]
    if fm == "on":
        return "fast-math"
    return "contract" if ffp == "fast" else "strict"


def march_of(cid):
    return theta.config_of(cid)[6]


BASELINE_MARCH = "x86-64"


class EmissionPolicy:
    """What this run is ALLOWED to emit, and why anything else is excluded.

    Every exclusion here narrows the candidate set, so no policy setting can ever make cytune
    emit something a stricter policy would have refused. That direction is the whole point: the
    guarantees (G1 oracle, G2 sanitizer, G3 honest-flat) are enforced downstream of selection and
    are untouched by this class, and every flag that reaches it can only REMOVE candidates.
    `test_cytune_plan.py::test_policy_flags_only_ever_narrow_the_candidate_set` pins that.

    Defaults are the strict ones: FP-strict, no fast-math, any -march.
    """

    __slots__ = ("allow_fast_math", "allow_fp_contract", "portable_flags")

    def __init__(self, allow_fast_math=False, allow_fp_contract=False, portable_flags=False):
        self.allow_fast_math = bool(allow_fast_math)
        # -ffast-math implies contraction (theta.build_flags forces ffp=fast when fm=on), so
        # opting into fast-math necessarily opts into contraction for those configs. Opting into
        # contraction alone does NOT opt into fast-math.
        self.allow_fp_contract = bool(allow_fp_contract)
        self.portable_flags = bool(portable_flags)

    def excluded_reason(self, cid):
        """None if the config may be emitted, else a short machine-readable reason."""
        if is_fast_math(cid) and not self.allow_fast_math:
            return "fast_math"
        if is_fp_contract(cid) and not self.allow_fp_contract:
            return "fp_contract"
        if self.portable_flags and march_of(cid) != BASELINE_MARCH:
            return "non_baseline_march"
        return None

    def allows(self, cid):
        return self.excluded_reason(cid) is None

    def as_dict(self):
        return {"allow_fast_math": self.allow_fast_math,
                "allow_fp_contract": self.allow_fp_contract,
                "portable_flags": self.portable_flags,
                "default_is_strict": True}


STRICT = EmissionPolicy()


def _policy(policy, allow_fast_math):
    """Accept either an EmissionPolicy or the legacy allow_fast_math bool."""
    if policy is not None:
        return policy
    return EmissionPolicy(allow_fast_math=allow_fast_math)


def _design(budget):
    """N_d = min(24, B-1); committed designs cover N_d in {7,15,24} (PREREG §8.2 / §12-D2).

    Retained for `--second-screen` and for the tests that pin the pre-1.1 trajectory. Note the
    fallback: when N_d is not one of the three committed sizes this returns the 24-point design,
    which is what defect D-2 was made of — see `screen_plan`.
    """
    designs = json.load(open(designs_path()))["designs"]
    nd = min(24, budget - 1)
    key = f"doe_{nd}" if f"doe_{nd}" in designs else "doe_24"
    return key, designs[key]["config_ids"]


# THE SECOND SCREEN STAYS ON BY DEFAULT, and the reason is a measurement, not an omission.
#
# The product runs a 17-point D-optimal probe BEFORE routing and then buys a SECOND D-optimal
# screen out of the tuning budget. `--probe-as-screen` skips that second buy and spends the whole
# tuning budget on the predicted-best walk. Offline on all 149 frozen tables it looks strongly
# better (training median regret 1.87% -> 0.14%, 97 kernels better and 9 worse, at an identical
# measured-config count), and live on the nine real anchors it improved the median (1.41% ->
# 0.94%) and the worst case (5.41% -> 2.17%).
#
# It is NOT the default anyway, because the pre-registered ship rule failed:
#   * one anchor (`_ppoly`) worsened by 1.37pp against a bound of 1.00pp (PREREG_DOE_V2 §5.1c);
#   * two live runs of the UNCHANGED 1.0.0 engine differ by 3.60pp on `_predictor`, so that bound
#     is tighter than the instrument at one live run per anchor and neither the pass nor the fail
#     is resolvable;
#   * the offline replay that motivated the change agrees with the live run on only 4 of 9 emitted
#     configs, so it is not predictive on the set the rule acts on;
#   * and the advantage is budget-dependent — it wins at B in {8,16,24} and is neutral-to-worse at
#     B in {32,40}, where the screen's information starts to pay for itself.
#
# Any one of those is enough to keep the default where it is. Shipping it anyway would be
# renegotiating a rule after seeing the data, which §5 forbids in those words.
#
# Evidence: results/release/DOE_V2_REPORT.md; pre-registration results/prereg/PREREG_DOE_V2.md.
SECOND_SCREEN = True


def screen_plan(budget, second_screen=None):
    """Batch 1: the pre-registered screen design, in order, up to N_d (the reference is free).

    With `second_screen=False` (CLI `--probe-as-screen`) no second design is bought and the whole
    tuning budget goes to the predicted-best walk. That path is measured, tested and NOT the
    default — see the block above for the four reasons.
    """
    if not (SECOND_SCREEN if second_screen is None else second_screen):
        return {"design_key": "probe-as-screen", "ids": [],
                "reference_id": theta.REFERENCE_ID,
                "why": ("the 17-point probe is the D-optimal screen and is already measured; the "
                        "whole tuning budget goes to the predicted-best walk")}
    key, design = _design(budget)
    ids, seen = [], {theta.REFERENCE_ID}
    # Cap at N_d, not at `budget`. Capping at `budget` was defect D-2: for every budget in [17,24]
    # the fallback 24-point design consumed the entire budget and the adaptive walk — which the
    # `B-1` in N_d exists to reserve — got nothing. Measured cost of that one line: median regret
    # 3.95% vs 1.46%, worst 516% vs 46%, on 58 of 149 frozen kernels.
    cap = min(budget, min(24, budget - 1))
    for cid in design:
        if len(ids) >= cap:
            break
        if cid in seen:
            continue
        seen.add(cid)
        ids.append(cid)
    return {"design_key": key, "ids": ids, "reference_id": theta.REFERENCE_ID}


def walk_plan(feasible_medians, queried_ids, budget_remaining, allow_fast_math=False,
              policy=None):
    """Batch 2: fit main effects on what the screen returned, then take the predicted-best
    unqueried configs. Mirrors algorithms.doe's post-screen ranking walk.

    The walk spends measurement budget, so it only visits configs this run could actually EMIT.
    Measuring a config the policy forbids emitting would burn budget to produce a number the
    certificate must then refuse to act on — which is how the probe's fast-math signal is
    reported (that comes free from the fixed design) but is not how the adaptive budget is spent.
    """
    import algorithms
    pol = _policy(policy, allow_fast_math)
    if budget_remaining <= 0 or not feasible_medians:
        return {"ids": [], "fit": None}
    obs_ids = sorted(feasible_medians)
    obs_logm = [math.log(feasible_medians[c]) for c in obs_ids]
    beta, used_ols = algorithms._fit(obs_ids, obs_logm)
    ranking, _pred = algorithms._pred_rank(beta)
    out, skipped = [], {}
    for cid in ranking:
        if len(out) >= budget_remaining:
            break
        if cid in queried_ids:
            continue
        why = pol.excluded_reason(cid)
        if why:
            skipped[why] = skipped.get(why, 0) + 1
            continue
        out.append(cid)
    return {"ids": out, "fit": {"n_obs": len(obs_ids), "used_ols": bool(used_ols),
                                # kept for backwards compatibility with the existing CLI line
                                "fast_math_skipped": skipped.get("fast_math", 0),
                                "skipped_by_policy": skipped,
                                "policy": pol.as_dict()}}


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


def select_winner(feasible_medians, allow_fast_math=False, policy=None):
    """The best feasible config the run is allowed to emit.

    Only feasible configs are ever in `feasible_medians` — an oracle-failing config never reaches
    this function, which is the structural half of the never-emit-an-oracle-failing-config
    guarantee. The other half is the endpoint re-check in the verify step.

    The exclusion counts name their DENOMINATOR explicitly (finding F18: the certificate reported
    `n_candidates: 17, n_excluded_fast_math: 12` with no statement of which population the 12 came
    from, and the two do not sum to anything a reader can check).
    """
    pol = _policy(policy, allow_fast_math)
    n_feasible = len(feasible_medians)
    excluded = {}
    cands = {}
    for c, m in feasible_medians.items():
        why = pol.excluded_reason(c)
        if why:
            excluded[why] = excluded.get(why, 0) + 1
        else:
            cands[c] = m
    detail = {
        "n_feasible_measured": n_feasible,
        "n_candidates": len(cands),
        "n_excluded_by_policy": n_feasible - len(cands),
        "excluded_by_reason": excluded,
        "denominator": ("n_feasible_measured = n_candidates + n_excluded_by_policy; every count "
                        "here is over the configs THIS RUN measured and found feasible, not over "
                        "the 1,728-config space"),
        "policy": pol.as_dict(),
        # legacy key, kept so older certificate readers do not break
        "n_excluded_fast_math": excluded.get("fast_math", 0),
    }
    if not cands:
        return None, detail
    best = min(cands, key=lambda c: (cands[c], c))
    return best, detail
