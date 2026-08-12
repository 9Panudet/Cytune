"""The Tier-1 variants (PREREG_DOE_V2 §2 + amendment A-1).

Each variant overrides exactly one seam of the shipped engine and inherits the rest from
`engine.V0`, which calls the product's own functions. Nothing here reimplements the baseline.

TWO INDEPENDENT SEAMS, because the fast-math rows reach the engine through two doors (A-1):

  DESIGN  which configs get measured        -> `screen_plan`
  FIT     which measured rows inform the walk -> `walk_plan`

The `+s` suffix closes the FIT door and is implemented in one line, because `algorithms._fit`
already drops columns that are constant over the observations: hand it only policy-allowed rows
and the two fmffp dummies vanish on their own, giving the 11-parameter strict model with no new
fit code and therefore no new place for the two to disagree.
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))

import designs_v2 as D                                     # noqa: E402
import engine                                              # noqa: E402
from cytune import plan, probe                             # noqa: E402
from cytune._vendor import theta                           # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DESIGNS = os.path.join(ROOT, "results", "doe_v2", "designs_v2.json")
EXTRA_SIZES = os.path.join(ROOT, "results", "doe_v2", "shipped_extra_sizes.json")
PRIOR = os.path.join(ROOT, "results", "doe_v2", "prior_K.json")

_CACHE = {}


def designs():
    if "d" not in _CACHE:
        _CACHE["d"] = json.load(open(DESIGNS))
    return _CACHE["d"]


def prior():
    if "k" not in _CACHE:
        _CACHE["k"] = json.load(open(PRIOR))
    return _CACHE["k"]


def policy_name(policy):
    if policy.allow_fast_math:
        return "fastmath"
    if policy.portable_flags:
        return "portable"
    if policy.allow_fp_contract:
        return "contract"
    return "strict"


# ------------------------------------------------------------------------------- design lookup
def _design_for(variant, policy, budget):
    """Same rule as plan._design: N_d = min(24, B-1), fall back to doe_24 when absent."""
    sets = designs()["variants"][variant][policy_name(policy)]
    nd = min(24, budget - 1)
    key = f"doe_{nd}" if f"doe_{nd}" in sets else "doe_24"
    return key, sets[key]["config_ids"]


def _take(design, cap):
    ids, seen = [], {theta.REFERENCE_ID}
    for cid in design:
        if len(ids) >= cap:
            break
        if cid in seen:
            continue
        seen.add(cid)
        ids.append(cid)
    return ids


# ------------------------------------------------------------ A-2: the walk-reserve fixes
def walk_reserve_screen(sets, budget, mode):
    """A-2. Choose the screen design and its cap so the adaptive walk is never starved.

    `mode` is one of:
      "none"  the shipped behaviour — design falls back to doe_24 and the cap is `budget`,
              so every budget in [17,24] leaves walk = 0. This is the defect.
      "W1"    cap at min(budget, N_d). Smallest diff. Drops points by config_id order, which is
              arbitrary — an honest cost of the cheapest fix, stated rather than hidden.
      "W2"    use the largest AVAILABLE design of size <= N_d. Needs no new design, and every
              point it keeps belongs to a genuine D-optimal design for its own size.
      "W3"    use the design of size exactly N_d, which must have been built.
    """
    nd = min(24, budget - 1)
    exact = f"doe_{nd}"
    if mode == "none":
        key = exact if exact in sets else "doe_24"
        return key, _take(sets[key]["config_ids"], budget)
    if mode == "W3" and exact in sets:
        return exact, _take(sets[exact]["config_ids"], nd)
    if mode == "W2":
        # `doe_` prefix, deliberately. The design dict also holds `probe_16`, and picking it here
        # would silently make the screen FREE — those 16 rows are already measured by the probe
        # before the tune stage begins — so the variant would appear 25% cheaper while having no
        # screen design at all. Caught by tracing an unexplained configs_measured drop; kept as
        # its own registered variant (W4) rather than as an accident inside this one.
        sizes = sorted((s["N_d"], k) for k, s in sets.items()
                       if s["N_d"] <= nd and k.startswith("doe_"))
        if sizes:
            key = sizes[-1][1]
            return key, _take(sets[key]["config_ids"], nd)
    if mode == "W4":
        # A-3: the probe IS a 17-point design and it is already paid for. Rather than buy a second
        # screen, treat it as the screen and spend the entire tune budget on the adaptive walk.
        return "probe-as-screen", []
    key = exact if exact in sets else "doe_24"
    return key, _take(sets[key]["config_ids"], min(budget, nd))


class _Base(engine.V0):
    """A frozen policy-matched design set, plus the shared screen/walk plumbing."""

    design_variant = "V1"
    strict_fit = False
    walk_reserve = "none"

    # PREREG_DOE_V2 §6: a prior that is unavailable for this run falls back down a fixed chain,
    # and the run RECORDS which prior it actually used. A missing prior must degrade to a weaker
    # design, never to a crash and never to a silently different guarantee. V3's K is derived for
    # the strict policy only (build_prior.py), so a `--allow-fp-contract` run legitimately has no
    # prior and must land on V2's classical augmented design.
    FALLBACK = {"V3": "V2", "V2": "V1", "V4": "V2", "V1": None}

    def _sets(self, policy):
        want = self.design_variant
        pname = policy_name(policy)
        chain = []
        while want is not None:
            chain.append(want)
            sets = designs()["variants"].get(want, {}).get(pname)
            if sets:
                self._used_design = want
                self._prior_chain = chain
                return sets
            want = self.FALLBACK.get(want)
        raise KeyError(f"no design for {self.design_variant}/{pname}; tried {chain}")

    def screen_plan(self, budget, policy, probe_rows):
        sets = self._sets(policy)
        key, ids = walk_reserve_screen(sets, budget, self.walk_reserve)
        used = getattr(self, "_used_design", self.design_variant)
        tag = f"{used}/{policy_name(policy)}/{key}"
        if used != self.design_variant:
            tag += f"(fallback from {self.design_variant})"
        return {"design_key": tag + (f"/{self.walk_reserve}" if self.walk_reserve != "none"
                                     else ""), "ids": ids}

    def walk_plan(self, remaining, feasible_medians, queried, policy, probe_rows):
        feas = feasible_medians
        if self.strict_fit:
            # A-1: fit only on rows this run could emit. No additivity assumption.
            feas = {c: m for c, m in feas.items() if policy.allows(c)}
            if len(feas) < 2:
                feas = feasible_medians
        return plan.walk_plan(feas, queried, remaining, policy=policy)


# --------------------------------------------------------------------------------- the variants
class V1(_Base):
    name = "V1"
    label = "policy-matched design (Stage-0 fix)"
    design_variant = "V1"


class V2(_Base):
    name = "V2"
    label = "V1 + D-optimal augmentation of the probe design"
    design_variant = "V2"


class V3(_Base):
    name = "V3"
    label = "V2 + Bayesian-D with the measured fleet prior K"
    design_variant = "V3"


class V4(_Base):
    """Ordinal coding changes the DESIGN criterion and the FIT together — a design built under
    polynomial contrasts fitted with dummies would be optimal for a model nobody is using."""

    name = "V4"
    label = "V2 + orthogonal-polynomial coding for opt_level and funroll"
    design_variant = "V4"

    def walk_plan(self, remaining, feasible_medians, queried, policy, probe_rows):
        feas = feasible_medians
        if self.strict_fit:
            feas = {c: m for c, m in feas.items() if policy.allows(c)} or feasible_medians
        if remaining <= 0 or len(feas) < 2:
            return {"ids": [], "fit": None}
        obs = sorted(feas)
        cand = D.candidates(policy)
        keep = D.live_columns(cand, "ordinal")
        X = D.model_matrix(obs, "ordinal")[:, keep]
        y = np.log(np.array([feas[c] for c in obs], float))
        # Same estimator switch as algorithms._fit: OLS once identified, ridge before that.
        if len(obs) >= 16 and np.linalg.matrix_rank(X) == X.shape[1]:
            beta, *_ = np.linalg.lstsq(X, y, rcond=1e-12)
        else:
            Z = X.copy()
            mu, sd = X.mean(0), X.std(0)
            scale = np.where(sd > 0, sd, 1.0)
            Z = (X - mu) / scale
            Z[:, 0] = 1.0
            P = np.eye(X.shape[1])
            P[0, 0] = 0.0
            b = np.linalg.solve(Z.T @ Z + P, Z.T @ y)
            beta = np.zeros(X.shape[1])
            beta[1:] = b[1:] / scale[1:]
            beta[0] = b[0] - float(np.sum(b[1:] * mu[1:] / scale[1:]))
        pred = D.model_matrix(cand, "ordinal")[:, keep] @ beta
        order = sorted(range(len(cand)), key=lambda i: (pred[i], cand[i]))
        out = []
        for i in order:
            if len(out) >= remaining:
                break
            if cand[i] not in queried:
                out.append(cand[i])
        return {"ids": out, "fit": {"n_obs": len(obs), "coding": "ordinal"}}


class V5(_Base):
    """Low-budget axis pinning. At B <= 16 the near-dead axes are pinned to their safe level
    UNLESS the probe shows signal on that axis.

    'Near-dead' is MEASURED, not assumed: build_prior.py reports the between-kernel sd of each
    effect, and only `initializedcheck=False` (sd 0.0016) and `funroll=off` (sd 0.0160) are an
    order of magnitude below the rest. `nonecheck` is NOT near-dead (sd 0.073, mean effect -4.4%)
    — the pre-registered guess named it and the measurement refused it.

    The probe rescue matters and is counted, not assumed away: pinning an axis the probe says is
    live would forfeit a real lever, so `n_rescued` is reported per run.
    """

    name = "V5"
    label = "V2 + measured-dead axis pinning at B<=16 (probe can rescue)"
    design_variant = "V2"
    PIN_SD = 0.02                       # between-kernel sd below which an axis is 'near-dead'
    PROBE_SIGNAL = 1.02                 # ratio above which the probe rescues an axis

    def _dead_axes(self):
        """Factors ALL of whose non-baseline levels are measured-dead.

        The all-levels test is not pedantry. `funroll` has two non-baseline levels: `off` is dead
        (between-kernel sd 0.0160, mean effect +0.2%) but `on` is a real 6.2% lever (sd 0.1059).
        Testing levels independently — as the first version of this function did — would have
        pinned funroll to `omit` on the strength of the dead level and thrown the live lever away
        on every low-budget run. A factor is pinnable only if nothing it can do matters.
        """
        p = prior()
        sd = {}
        for name, var in zip(p["param_names"], p["var_between"]):
            if name != "intercept":
                fac, _, lv = name.partition("=")
                sd.setdefault(theta.FACTOR_NAMES.index(fac), []).append(math.sqrt(var))
        return [(fi, None) for fi, vals in sorted(sd.items())
                if all(v < self.PIN_SD for v in vals)]

    def _live_by_probe_factor(self, probe_rows, fi):
        """Signal on ANY level of this factor rescues the whole factor."""
        levels = theta.FACTORS[fi][1]
        return any(self._live_by_probe(probe_rows, fi, str(lv)) for lv in levels[1:])

    def _live_by_probe(self, probe_rows, fi, lv):
        """Does the probe show a real difference across this factor's levels?"""
        med = {c: r["screen"]["median_ns"] for c, r in probe_rows.items() if r.get("screen")}
        on = [m for c, m in med.items() if str(theta.config_of(c)[fi]) == lv]
        off = [m for c, m in med.items() if str(theta.config_of(c)[fi]) != lv]
        if not on or not off:
            return True                          # cannot tell -> do not pin
        r = max(np.median(on), np.median(off)) / min(np.median(on), np.median(off))
        return r >= self.PROBE_SIGNAL

    def screen_plan(self, budget, policy, probe_rows):
        base = super().screen_plan(budget, policy, probe_rows)
        if budget > 16:
            return base
        pins, rescued = [], 0
        for fi, _lv in self._dead_axes():
            if self._live_by_probe_factor(probe_rows, fi):
                rescued += 1
            else:
                pins.append(fi)
        if not pins:
            base["design_key"] += f"/nopin(rescued={rescued})"
            return base
        # Pin by projecting each design point onto the safe (baseline) level of every pinned
        # factor. The design SIZE is unchanged — a variant never changes how many (build_designs).
        safe = {fi: theta.FACTORS[fi][1][0] for fi in pins}
        ids, seen = [], set()
        for cid in base["ids"]:
            cfg = list(theta.config_of(cid))
            for fi in safe:
                cfg[fi] = safe[fi]
            nid = theta.id_of(tuple(cfg))
            if nid in seen or nid == theta.REFERENCE_ID or not policy.allows(nid):
                continue          # collapsed onto something already measured -> keep the original
            seen.add(nid)
            ids.append(nid)
        # Refill from the unpinned design so the budget is spent, not surrendered.
        for cid in base["ids"]:
            if len(ids) >= len(base["ids"]):
                break
            if cid not in seen:
                seen.add(cid)
                ids.append(cid)
        base["ids"] = ids
        base["design_key"] += f"/pin{len(pins)}(rescued={rescued})"
        return base


class V6(_Base):
    """Sequential augmentation. Replaces the fixed screen+walk escalation at B >= 32 with a second
    D-optimal batch conditioned on everything already measured, then the walk on what remains.

    Only bites at B >= 32, where the routed budget leaves 8 points after the 24-point design. The
    current engine spends all 8 on the predicted-best ranking, which is pure exploitation of a fit
    that has just become identified; V6 spends half of them reducing the variance of that fit
    first. Whether that trade pays is the measurement.
    """

    name = "V6"
    label = "V2 + budget-aware sequential D-optimal augmentation at B>=32"
    design_variant = "V2"
    SPLIT = 0.5

    def walk_plan(self, remaining, feasible_medians, queried, policy, probe_rows):
        if remaining < 4:
            return super().walk_plan(remaining, feasible_medians, queried, policy, probe_rows)
        n_aug = max(1, int(round(remaining * self.SPLIT)))
        cand = [c for c in D.candidates(policy) if c not in queried]
        if len(cand) <= n_aug:
            return super().walk_plan(remaining, feasible_medians, queried, policy, probe_rows)
        prior_rows = sorted(c for c in queried if policy.allows(c))
        aug = D.build(n_aug, cand, ("doe_v2", "V6", policy_name(policy), n_aug, len(prior_rows)),
                      prior_rows=prior_rows)["config_ids"]
        rest = super().walk_plan(remaining - len(aug), feasible_medians,
                                 set(queried) | set(aug), policy, probe_rows)
        return {"ids": list(aug) + rest["ids"], "fit": rest.get("fit")}


# -------------------------------------------------------------------------- the +s fit variants
def _strict_fit(cls):
    ns = {"name": cls.name + "+s", "label": cls.label + " + strict-only fit (A-1)",
          "strict_fit": True}
    return type(cls.__name__ + "s", (cls,), ns)


V1s, V2s, V3s, V4s, V5s, V6s = (_strict_fit(c) for c in (V1, V2, V3, V4, V5, V6))


class V0s(engine.V0):
    """The FIT fix ALONE, on the shipped design. Isolates which of A-1's two doors matters."""

    name = "V0+s"
    label = "shipped design + strict-only fit (A-1 fit door only)"

    def walk_plan(self, remaining, feasible_medians, queried, policy, probe_rows):
        feas = {c: m for c, m in feasible_medians.items() if policy.allows(c)}
        return plan.walk_plan(feas or feasible_medians, queried, remaining, policy=policy)


# ------------------------------------------------- A-2 on the SHIPPED design (fix in isolation)
class _V0W(engine.V0):
    """The walk-reserve fix alone, on the shipped 1,728-candidate designs. Isolating it from the
    Stage-0 design fix is what makes the two attributable — composed, either could take credit."""

    walk_reserve = "W1"

    def _sets(self):
        if "shipped" not in _CACHE:
            from cytune._vendor import designs_path
            _CACHE["shipped"] = json.load(open(designs_path()))["designs"]
        return _CACHE["shipped"]

    def screen_plan(self, budget, policy, probe_rows):
        key, ids = walk_reserve_screen(self._sets(), budget, self.walk_reserve)
        return {"design_key": f"shipped/{key}/{self.walk_reserve}", "ids": ids}


class V0W1(_V0W):
    name = "V0+W1"
    label = "shipped design, screen capped at min(budget, N_d)"
    walk_reserve = "W1"


class V0W2(_V0W):
    name = "V0+W2"
    label = "shipped design, largest available design of size <= N_d"
    walk_reserve = "W2"


class V0W3(_V0W):
    name = "V0+W3"
    label = "shipped design + the missing doe_23 built exactly"
    walk_reserve = "W3"

    def _sets(self):
        sets = dict(super()._sets())
        if "extra" not in _CACHE:
            _CACHE["extra"] = (json.load(open(EXTRA_SIZES))
                               if os.path.exists(EXTRA_SIZES) else {})
        sets.update(_CACHE["extra"])
        return sets


class V0W4(_V0W):
    """A-3. Found by accident inside a W2 bug and kept because the question it asks is real:
    the probe is a 17-point D-optimal design that has ALREADY been paid for. Is a second screen
    design worth buying at all, or should the whole tune budget go to the adaptive walk?"""

    name = "V0+W4"
    label = "probe-as-screen: no second design, entire tune budget on the walk"
    walk_reserve = "W4"


# ------------------------------------------------------------------- A-4: the SPLIT family
class _Split(_Base):
    """Screen size as a parameter. `n_screen` points of the V2 policy-matched, probe-augmented
    design; everything else goes to the predicted-best walk.

    SPLIT(0) is W4 with D-1 fixed — no second screen, and the walk's candidates are policy-matched.
    SPLIT(15)/SPLIT(24) reproduce V0's split with a design that is legal to emit. The budget is
    identical across the family by construction, so this axis cannot buy regret with spend.
    """

    design_variant = "V2"
    n_screen = 0

    def screen_plan(self, budget, policy, probe_rows):
        if self.n_screen <= 0:
            return {"design_key": f"SPLIT0/{policy_name(policy)}", "ids": []}
        sets = self._sets(policy)
        sizes = sorted((s["N_d"], k) for k, s in sets.items() if s["N_d"] <= self.n_screen)
        key = sizes[-1][1] if sizes else min(sets, key=lambda k: sets[k]["N_d"])
        cap = min(self.n_screen, budget - 1)               # A-2: never starve the walk
        return {"design_key": f"SPLIT{self.n_screen}/{policy_name(policy)}/{key}",
                "ids": _take(sets[key]["config_ids"], cap)}


def _split(n):
    return type(f"Split{n}", (_Split,),
                {"name": f"SPLIT{n}", "n_screen": n,
                 "label": f"policy-matched probe-augmented screen of {n}, rest on the walk"})


SPLIT0, SPLIT7, SPLIT15, SPLIT24 = (_split(n) for n in (0, 7, 15, 24))

ALL = [engine.V0(), V0s(), V0W1(), V0W2(), V0W3(), V0W4(),
       V1(), V1s(), V2(), V2s(), V3(), V3s(), V4(), V4s(), V5(), V5s(), V6(), V6s(),
       SPLIT0(), SPLIT7(), SPLIT15(), SPLIT24()]
