"""The PRODUCT search engine, replayed against a frozen table through the sealed interface.

WHY THIS EXISTS AND WHY IT IS NOT scripts/phasep/algorithms.doe.

`algorithms.doe` is the STUDY's DOE arm. The product is a different trajectory: it pays for a
17-point probe first, routes on those features to a budget, runs the frozen screen design, and then
fits on probe+screen together before the ranking walk. `cytune/plan.py`'s own docstring says so —
"the product conditions the fit on the probe rows too, which it has already paid for and which the
study arm never has". Evaluating a change to the product's engine against the study's arm would be
measuring the wrong thing.

V0 IS NOT A REIMPLEMENTATION. It calls `cytune.probe.features`, `cytune.routing.route`,
`cytune.plan.screen_plan`, `cytune.plan.walk_plan`, `cytune.plan.select_winner` and
`cytune.plan.confirm_winner` — the shipped functions, imported from the package. A variant
overrides exactly one seam and inherits the rest. So a V0-vs-Vn difference cannot come from a
transcription error in the baseline, because there is no transcription.

WHAT THE TABLE CAN AND CANNOT ANSWER. The frozen tables record, per config: feasible, and the
SCREEN-tier median. They do not record an endpoint-tier median. So the endpoint re-check
(`confirm_winner`) is modelled as "feasible in the table confirms" — which is how the study's
replay treats it, and is the honest limit of offline replay. It is recorded in the prereg as such.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))

from cytune import plan, probe, routing                      # noqa: E402
from cytune._vendor import theta                             # noqa: E402


# --------------------------------------------------------------------------- sealed table access
class Sealed:
    """Ask-tell over a frozen table. The table lives in a closure; the engine may only query().

    Deliberately a separate class from `replay.SealedTable` rather than an import: this file must
    run without the study's scripts/ on the path (it is evaluated from the product side), and the
    contract it needs is four lines. The cheat property is the same one and
    `test_doe_v2.py::test_the_engine_cannot_reach_the_table` pins it.
    """

    def __init__(self, tbl, reference_id=None):
        ref = theta.REFERENCE_ID if reference_id is None else reference_id
        queried, order = {ref}, []

        def _query(cid):
            if cid not in tbl:
                raise KeyError(f"config_id {cid} not in Θ")
            if cid not in queried:
                queried.add(cid)
                order.append(cid)
            return tbl[cid]

        object.__setattr__(self, "_q", _query)
        object.__setattr__(self, "_m", {"queried": queried, "order": order, "ref": ref})

    def query(self, cid):
        return self._q(cid)

    @property
    def reference_id(self):
        return self._m["ref"]

    @property
    def queried_ids(self):
        return set(self._m["queried"])

    @property
    def paid(self):
        return len(self._m["order"])

    def paid_order(self):
        return list(self._m["order"])

    def __getattr__(self, name):
        raise AttributeError(f"sealed: '{name}' is not part of the ask-tell interface")

    def __getitem__(self, k):
        raise AttributeError("sealed: subscripting the table is forbidden")


def _row(obs):
    """A frozen-table observation (feasible, median_ns, reason) as the row shape probe.features
    consumes. Keeping the shape identical is what lets V0 call the shipped feature code."""
    feas, med, reason = obs
    return {"feasible": bool(feas), "reason": reason,
            "screen": ({"median_ns": med} if (feas and med is not None) else None)}


# ------------------------------------------------------------------------------------- variants
class V0:
    """The shipped engine. Every hook delegates to the product module."""

    name = "V0"
    label = "current engine (frozen 1728-candidate designs)"

    def probe_ids(self, policy):
        return probe.probe_config_ids()

    def screen_plan(self, budget, policy, probe_rows):
        return plan.screen_plan(budget)

    def walk_plan(self, remaining, feasible_medians, queried, policy, probe_rows):
        return plan.walk_plan(feasible_medians, queried, remaining, policy=policy)

    def select_winner(self, feasible_medians, policy):
        return plan.select_winner(feasible_medians, policy=policy)


# ---------------------------------------------------------------------------------- the run loop
def run(tbl, variant=None, policy=None, budget_override=None, reference_id=None):
    """Replay one cytune tune against one frozen table. Returns a result record.

    The stage order mirrors `cli.py::cmd_tune` steps 2-5 exactly: probe -> route -> screen -> walk
    -> select -> endpoint confirm, including the honest-flat rule that refuses to recommend a
    winner spotted incidentally in the probe.
    """
    variant = variant or V0()
    policy = policy or plan.STRICT
    sealed = Sealed(tbl, reference_id)
    ref = sealed.reference_id

    # ---- [2/6] probe
    rows = {}
    for cid in variant.probe_ids(policy):
        rows[cid] = _row(sealed.query(cid))
    if ref not in rows:
        rows[ref] = _row(sealed.query(ref))
    feat = probe.features(rows)
    n_probe_paid = sealed.paid

    # ---- [3/6] route
    route = routing.route(feat, bo_available=False)
    if budget_override is not None and route["budget"]:
        route = dict(route, budget=budget_override, budget_routed=route["budget"])
    if route["route"] == routing.ABORT:
        return _record(sealed, tbl, policy, route, feat, None, None, "abort", n_probe_paid, 0, 0)

    # ---- [4/6] tune
    n_screen = n_walk = 0
    design_key = None
    if route["route"] != routing.HONEST_FLAT:
        sp = variant.screen_plan(route["budget"], policy, rows)
        design_key = sp.get("design_key")
        for cid in sp["ids"]:
            rows[cid] = _row(sealed.query(cid))
        n_screen = len(sp["ids"])
        remaining = route["budget"] - n_screen
        if remaining > 0:
            feas = {c: r["screen"]["median_ns"] for c, r in rows.items() if r["screen"]}
            wp = variant.walk_plan(remaining, feas, set(rows), policy, rows)
            for cid in wp["ids"]:
                rows[cid] = _row(sealed.query(cid))
            n_walk = len(wp["ids"])

    # ---- [5/6] select + endpoint confirm
    feas = {c: r["screen"]["median_ns"] for c, r in rows.items() if r["screen"]}
    observed, detail = variant.select_winner(feas, policy)
    flat_observation = None
    if route["route"] == routing.HONEST_FLAT and observed is not None and observed != ref:
        # cli.py: the route declined to tune, so the best-of-17 probe config is a selection-biased
        # claim and is measured but not recommended.
        flat_observation, winner = observed, ref
    else:
        winner = observed

    endpoints = {str(c): {"feasible": tbl[c][0], "endpoint_ns": tbl[c][1]}
                 for c in ({winner, ref} - {None})}
    final, rejection = plan.confirm_winner(winner, ref, endpoints)
    return _record(sealed, tbl, policy, route, feat, final, rejection, design_key,
                   n_probe_paid, n_screen, n_walk, flat_observation, detail)


def _record(sealed, tbl, policy, route, feat, final, rejection, design_key,
            n_probe, n_screen, n_walk, flat_observation=None, detail=None):
    ref = sealed.reference_id
    t_ref = tbl[ref][1] if tbl[ref][0] else None

    feasible = {c: m for c, (f, m, _r) in tbl.items() if f and m is not None}
    true_opt_all = min(feasible.values()) if feasible else None
    emittable = {c: m for c, m in feasible.items() if policy.allows(c)}
    true_opt_emit = min(emittable.values()) if emittable else None

    emitted_ns = tbl[final][1] if (final is not None and tbl[final][0]) else t_ref
    return {
        "route": route["route"], "rule": route["rule"], "budget": route["budget"],
        "design_key": design_key,
        "emitted_id": final,
        "emitted_ns": emitted_ns,
        "t_ref_ns": t_ref,
        "true_opt_all_ns": true_opt_all,
        "true_opt_emittable_ns": true_opt_emit,
        # PRIMARY: what this run could possibly have achieved under its own emission policy.
        "regret_emittable": (emitted_ns / true_opt_emit - 1.0
                             if (emitted_ns and true_opt_emit) else math.inf),
        # SECONDARY, always reported alongside (the Δ_strict/Δ_all discipline).
        "regret_all": (emitted_ns / true_opt_all - 1.0
                       if (emitted_ns and true_opt_all) else math.inf),
        "configs_measured": sealed.paid,
        "n_probe": n_probe, "n_screen": n_screen, "n_walk": n_walk,
        "n_paid_emittable": len([c for c in sealed.paid_order() if policy.allows(c)]),
        "delta_probe": feat.get("delta_probe"),
        "if_probe": feat.get("if_probe"),
        "rejected": bool(rejection),
        "flat_observation": flat_observation,
        "speedup": (t_ref / emitted_ns if (t_ref and emitted_ns) else None),
    }
