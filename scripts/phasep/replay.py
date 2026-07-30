"""Sealed ask-tell replay interface (PREREG §3.1, roadmap §5.1) — the fairness mechanism.

An algorithm may ONLY call `sealed.query(config_id)`. The frozen table's contents live in a closure,
NOT in any attribute, and every non-whitelisted attribute access raises CheatDetected (the §9.3
conformance cheat-test — a peeking stub is caught). Regret is against the exhaustively-known true
feasible optimum. The reference config is observation 0, free, and counts as already-queried for
budget memoization + init dedup, uniformly for all arms (PREREG §3.1).

NO replay STUDY runs here and nothing touches a pilot table before the P-2 freeze — this is the
interface + harness only, tested against synthetic frozen tables.
"""
from __future__ import annotations
import json
import math
import theta


class CheatDetected(Exception):
    pass


def load_frozen_table(table_path, overlay=None):
    """Read a committed table.jsonl -> {config_id: (feasible, median_ns|None, reason)} + true opt.

    `overlay` (D23 / amendment A-9) is the set of config_ids roadmap §1.4 forces to infeasible
    because the sanitizer reports on them — the oracle passed them, ASan did not. Applying it HERE,
    at the single point where the study reads a table, is what makes *correctness absolute* hold
    for the search: an overlaid config is not merely penalised, it is not in feasible space, so no
    algorithm can select it, it can never become `true_opt`, and `cytune` can never emit it.
    Passing `overlay=None` when an overlay exists would let the study optimise into an
    out-of-bounds read — hence run_study loads it unconditionally rather than optionally."""
    overlay = set(overlay or ())
    tbl, true_opt = {}, math.inf
    for line in open(table_path):
        r = json.loads(line)
        cid = r["config_id"]
        feas = bool(r.get("feasible")) and cid not in overlay
        reason = ("sanitizer_oob" if (cid in overlay and r.get("feasible"))
                  else r.get("reason", "ok"))
        m = r["screen"]["median_ns"] if (feas and r.get("screen")) else None
        tbl[cid] = (feas, m, reason)
        if feas and m is not None and m < true_opt:
            true_opt = m
    return tbl, (None if true_opt == math.inf else true_opt)


_ALLOWED = {"query", "n_configs", "reference_id", "reference_obs", "budget_used", "queried_ids"}


class SealedTable:
    """Exposes query()/reference only. Table data is captured in a closure — unreachable by attr."""

    def __init__(self, tbl, reference_id=None):
        reference_id = theta.REFERENCE_ID if reference_id is None else reference_id
        queried = set([reference_id])          # reference is observation 0 (free, already-queried)
        counter = {"paid": 0}

        def _query(cid):
            if cid not in tbl:
                raise KeyError(f"config_id {cid} not in Θ table")
            if cid not in queried:
                queried.add(cid)
                counter["paid"] += 1            # each distinct non-reference config costs 1 budget unit
                paid_order.append(cid)          # ORDER, for nested-budget prefix reads
            return tbl[cid]

        paid_order = []
        object.__setattr__(self, "_q", _query)
        object.__setattr__(self, "_meta", {
            "n_configs": len(tbl), "reference_id": reference_id,
            "reference_obs": (reference_id,) + tbl[reference_id],
            "queried": queried, "counter": counter, "paid_order": paid_order})

    def query(self, cid):
        return self._q(cid)

    @property
    def n_configs(self):
        return self._meta["n_configs"]

    @property
    def reference_id(self):
        return self._meta["reference_id"]

    @property
    def reference_obs(self):
        return self._meta["reference_obs"]

    @property
    def budget_used(self):
        return self._meta["counter"]["paid"]

    @property
    def queried_ids(self):
        return set(self._meta["queried"])

    def _paid_order(self):
        """Paid queries in the order they were made. NOT a property and NOT reachable through the
        sealed interface — `__getattr__` still refuses every non-whitelisted attribute, so an ARM
        calling `sealed._paid_order` gets its own history back, which tells it nothing it did not
        already know. The harness reads it after the arm returns, to cut nested-budget prefixes."""
        return list(self._meta["paid_order"])

    def __getattr__(self, name):
        # any attribute not explicitly whitelisted above is a cheat attempt (peeking at the table)
        raise CheatDetected(f"sealed interface: access to '{name}' is forbidden — only query() is permitted")

    def __getitem__(self, k):
        raise CheatDetected("sealed interface: subscripting the table is forbidden")


def regret_at(best_feasible_ns, true_opt_ns, t_ref_ns, floor=True):
    """regret@B = best_found/true_opt - 1, best_found = min(t_ref, best feasible found) if floor."""
    best = best_feasible_ns
    if floor:
        best = t_ref_ns if best is None else min(t_ref_ns, best)
    if best is None:
        return math.inf
    return best / true_opt_ns - 1.0


def emittable_ids(tbl):
    """PREREG §12 A-5a: configs cytune may emit with no --allow-fast-math, i.e. feasible AND
    fast_math=off. This is exactly the set over which §1-v2 defines t_strict."""
    return {c for c, (f, m, _r) in tbl.items()
            if f and m is not None and theta.config_of(c)[8][0] == "off"}


def run_algorithm(algo, tbl, budget, seed, reference_id=None):
    """Run an algorithm(sealed, budget, seed) -> best_feasible_ns, guarding against cheating.

    Returns dict(best_ns, regret, regret_nofloor, budget_used, cheated:bool) plus the A-5 SECONDARY
    slice (regret_emittable*). The algorithm receives ONLY the SealedTable; any peek raises
    CheatDetected which is caught and flagged.

    A-5d: the secondary slice is computed AFTER the algorithm returns, from the configs it actually
    queried (`sealed.queried_ids`, already whitelisted) intersected with the frozen table. No arm
    is re-run, no arm can observe it, and the sealed interface is untouched — so this cannot affect
    the primary metric or the §9.3 cheat-test.
    """
    reference_id = theta.REFERENCE_ID if reference_id is None else reference_id
    _, true_opt = None, min(m for f, m, _ in tbl.values() if f and m is not None)
    t_ref = tbl[reference_id][1]
    sealed = SealedTable(tbl, reference_id)
    try:
        best = algo(sealed, budget, seed)
    except CheatDetected:
        return {"best_ns": None, "regret": None, "cheated": True, "budget_used": sealed.budget_used}

    emittable = emittable_ids(tbl)
    t_strict = min((tbl[c][1] for c in emittable), default=None)
    queried = sealed.queried_ids
    # best-found may use the reference (it is observation 0, free, and legitimately emittable).
    found = [tbl[c][1] for c in queried if c in emittable]
    best_emittable = min(found) if found else None
    # ...but the BUDGET fraction must count PAID queries only. `queried_ids` is seeded with the
    # reference while `budget_used` excludes it, so counting both together yields fractions > 1.
    # The E3 figure this slice exists to generalise ("37.0% of paid budget on ineligible
    # candidates") is defined over paid queries, and the two must be commensurable.
    paid_emittable = len([c for c in queried if c in emittable and c != reference_id])
    return {"best_ns": best, "cheated": False, "budget_used": sealed.budget_used,
            "regret": regret_at(best, true_opt, t_ref, floor=True),
            "regret_nofloor": regret_at(best, true_opt, t_ref, floor=False),
            # ---- A-5 SECONDARY slice (descriptive; never substituted for the primary) ----
            "best_emittable_ns": best_emittable,
            "n_emittable_queried": paid_emittable,
            "emittable_budget_frac": ((paid_emittable / sealed.budget_used)
                                      if sealed.budget_used else None),
            "regret_emittable": (regret_at(best_emittable, t_strict, t_ref, floor=True)
                                 if t_strict is not None else None),
            "regret_emittable_nofloor": (regret_at(best_emittable, t_strict, t_ref, floor=False)
                                         if t_strict is not None else None)}


def run_algorithm_prefixes(algo, tbl, budgets, seed, reference_id=None):
    """NESTED-BUDGET evaluation: run ONE trajectory to max(budgets) and read regret@b off the
    prefixes, returning {b: row} in the same shape `run_algorithm` returns.

    This is exact, not an approximation, for every arm whose `budget` argument is only a STOPPING
    CONDITION — RS, BO and Motif+BO all loop `while sealed.budget_used < budget`, so the first b
    paid queries of a B=max run are byte-identical to the whole of a B=b run at the same seed.
    `test_prefix_equals_independent_runs` pins that claim rather than asserting it.

    It is NOT valid for DOE, whose design SIZE is `min(24, B-1)` — a different budget means a
    different design, not a truncation of one. DOE therefore stays per-budget, and
    `run_study` routes it that way.

    Two reasons this is the right shape beyond saving 5x the compute: the budgets become PAIRED
    (the same trajectory is being observed at five points, so a budget-to-budget comparison is
    within-trajectory), and it matches PREREG §3.2, which defines 200 seeds per
    (algorithm x kernel) — not per (algorithm x kernel x budget).
    """
    budgets = sorted(budgets)
    reference_id = theta.REFERENCE_ID if reference_id is None else reference_id
    true_opt = min(m for f, m, _ in tbl.values() if f and m is not None)
    t_ref = tbl[reference_id][1]
    emittable = emittable_ids(tbl)
    t_strict = min((tbl[c][1] for c in emittable), default=None)

    sealed = SealedTable(tbl, reference_id)
    try:
        algo(sealed, budgets[-1], seed)
    except CheatDetected:
        return {b: {"best_ns": None, "regret": None, "cheated": True,
                    "budget_used": min(b, sealed.budget_used)} for b in budgets}

    order = sealed._paid_order()
    out = {}
    for b in budgets:
        pre = order[:b]
        feas_ns = [tbl[c][1] for c in pre if tbl[c][0] and tbl[c][1] is not None]
        # The arms all seed `best` from the reference observation (`algorithms._ref_best`), which
        # is free and already-queried. Excluding it here would make `regret_nofloor` disagree with
        # `run_algorithm` on the same trajectory — the floored metric would still match, which is
        # exactly the kind of near-agreement that hides a real difference.
        if tbl[reference_id][0] and tbl[reference_id][1] is not None:
            feas_ns.append(tbl[reference_id][1])
        best = min(feas_ns) if feas_ns else None
        emit_ns = [tbl[c][1] for c in pre if c in emittable]
        # The reference is observation 0 — free, already-queried, and legitimately emittable — so
        # it joins the emittable pool at every prefix, exactly as run_algorithm has it.
        if reference_id in emittable:
            emit_ns.append(tbl[reference_id][1])
        best_emit = min(emit_ns) if emit_ns else None
        paid_emit = len([c for c in pre if c in emittable and c != reference_id])
        out[b] = {
            "best_ns": best, "cheated": False, "budget_used": len(pre),
            "regret": regret_at(best, true_opt, t_ref, floor=True),
            "regret_nofloor": regret_at(best, true_opt, t_ref, floor=False),
            "best_emittable_ns": best_emit,
            "n_emittable_queried": paid_emit,
            "emittable_budget_frac": (paid_emit / len(pre)) if pre else None,
            "regret_emittable": (regret_at(best_emit, t_strict, t_ref, floor=True)
                                 if t_strict is not None else None),
            "regret_emittable_nofloor": (regret_at(best_emit, t_strict, t_ref, floor=False)
                                         if t_strict is not None else None),
        }
    return out
