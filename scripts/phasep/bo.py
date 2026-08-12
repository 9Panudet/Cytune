"""BO — SMAC-style RF surrogate + feasibility-weighted EI (PREREG §8.3, roadmap §5.4 / v1 §2.1-2.2).

y = log(median runtime). EI(θ) = (y* − μ)Φ(z) + σφ(z), z = (y* − μ)/σ; σ floored at 1e-3 log-units.
α(θ) = EI(θ) · P̂(feasible | θ). μ, σ are the mean and population std of the per-tree predictions over
FEASIBLE observations only (infeasible runtimes NEVER imputed). P̂ is a separate RF classifier's
feasible-tree fraction with add-one Laplace smoothing (never exactly 0/1). Exhaustive α scoring over
all 1,728 configs. 1-in-4 random interleave. 8-config initial design [reference, expert, known-bad,
5 seed-random]. RF hyperparameters pinned (PREREG §8.3). Conditional-fmffp is native in the design
coding (theta.py) — every proposal is a valid Θ config by construction.

TDD-gated (test_bo.py hand-computed fixtures) + bo-math-reviewer before entering the study. NO study
runs here; nothing touches a pilot table before P-2.
"""
from __future__ import annotations
import math
import numpy as np
from scipy.special import ndtr           # Φ, the standard-normal CDF (vectorized)
import theta

RF_PARAMS = dict(n_estimators=100, max_features=0.5, min_samples_leaf=3, min_samples_split=3,
                 max_depth=None, bootstrap=True, n_jobs=1)
SIGMA_FLOOR = 1e-3
EXPERT = (False, False, True, False, False, "-O3", "native", "on", ("off", "fast"))
KNOWN_BAD = (True, True, False, True, True, "-O1", "x86-64", "off", ("off", "off"))
_SQRT2PI = math.sqrt(2 * math.pi)


def _phi(z):
    return np.exp(-0.5 * z * z) / _SQRT2PI


def ei(y_star, mu, sigma):
    """Expected improvement for a MINIMIZATION target y (lower = better). Vectorized.

    EI = (y* − μ)·Φ(z) + σ·φ(z), z = (y* − μ)/σ, σ floored at SIGMA_FLOOR. Never negative."""
    mu = np.asarray(mu, float)
    sigma = np.maximum(np.asarray(sigma, float), SIGMA_FLOOR)
    z = (y_star - mu) / sigma
    val = (y_star - mu) * ndtr(z) + sigma * _phi(z)
    return np.maximum(val, 0.0)


def laplace_pfeasible(tree_votes_feasible, n_trees):
    """add-one Laplace: (feasible votes + 1)/(n_trees + 2) — strictly in (0,1) (PREREG §8.3)."""
    return (np.asarray(tree_votes_feasible, float) + 1.0) / (n_trees + 2.0)


def _surrogate_mu_sigma(reg, Xall):
    per_tree = np.stack([t.predict(Xall) for t in reg.estimators_])   # (n_trees, N)
    return per_tree.mean(0), np.maximum(per_tree.std(0), SIGMA_FLOOR)


def _init_design(sealed, rng):
    ref = sealed.reference_id
    base = [ref, theta.id_of(EXPERT), theta.id_of(KNOWN_BAD)]
    picks, seen = [], set(base)
    while len(picks) < 5:
        c = int(rng.integers(theta.N_CONFIGS))
        if c not in seen:
            picks.append(c); seen.add(c)
    return base + picks


def _is_random_step(step):
    """1-in-4 interleave schedule (§8.3): with the loop's `step` starting at 8, this is True at
    steps 11,15,19,… = the 4th, 8th, 12th proposals after the 8-config init."""
    return step % 4 == 3


def _propose(queried, Xall, best_ns, rng, rf_state):
    """One EI·P̂ proposal (argmax α over unqueried Θ). Feasible-only μ/σ; Laplace P̂. rf_state is the
    pinned RF random_state (§8.3), independent of the init/interleave stream `rng`."""
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
    feas = [c for c, (f, m) in queried.items() if f and m is not None]
    unq = [c for c in range(theta.N_CONFIGS) if c not in queried]
    if not unq:
        return None
    if len(feas) < 1 or best_ns is None:
        return int(rng.choice(unq))
    reg = RandomForestRegressor(random_state=rf_state, **RF_PARAMS).fit(
        Xall[feas], np.log(np.array([queried[c][1] for c in feas], float)))
    mu, sigma = _surrogate_mu_sigma(reg, Xall)
    a = ei(math.log(best_ns), mu, sigma)
    allc = list(queried)
    lab = np.array([1 if queried[c][0] else 0 for c in allc])
    if lab.min() != lab.max():
        clf = RandomForestClassifier(random_state=rf_state, **RF_PARAMS).fit(Xall[allc], lab)
        votes = np.stack([t.predict(Xall) for t in clf.estimators_]).sum(0)  # feasible votes
        pfeas = laplace_pfeasible(votes, len(clf.estimators_))
    else:
        pfeas = np.full(theta.N_CONFIGS, (lab.sum() + 1.0) / (len(lab) + 2.0))
    alpha = a * pfeas
    alpha[list(queried)] = -np.inf
    return int(np.argmax(alpha))


def _streams(seed, hash_k, seed_i, alg_id):
    """Two INDEPENDENT streams per §8.3: init/interleave rng from ['bo-init',hash_k,i] and RF
    random_state from ['bo-rf',hash_k,alg_id,seed_i]. When the study passes hash_k/seed_i the exact
    pinned keys are used; otherwise two sub-streams are spawned from `seed` (deterministic for tests)."""
    import seeds as _s
    if hash_k is not None:
        i = seed if seed_i is None else seed_i
        # PENDING ERRATUM E3 (found by the first pinned-path caller, pre-study; present at P-2):
        # sklearn requires random_state ∈ [0, 2^32-1] but the §8.3/E2 pin derives a full uint64 —
        # the committed derivation stands (seed_fixtures.json unchanged); the RF consumes it
        # reduced mod 2^32. Deterministic, no study data affected (BO has never run in-study).
        return _s.rng("bo-init", hash_k, i), _s.state_int("bo-rf", hash_k, alg_id, i) % (2 ** 32)
    ss = seed if isinstance(seed, np.random.SeedSequence) else np.random.SeedSequence(int(seed))
    c_init, c_rf = ss.spawn(2)
    return np.random.default_rng(c_init), int(np.random.default_rng(c_rf).integers(2**31 - 1))


def bo(sealed, budget, seed, hash_k=None, seed_i=None, alg_id=3):
    """Feasibility-weighted-EI BO over Θ. Reference is obs 0 (free). 1-in-4 random interleave.
    §8.3 seed derivation: the study passes (hash_k, seed_i) for the exact pinned streams; tests pass
    an int `seed` and get two independent spawned sub-streams (init/interleave vs RF)."""
    rng, rf_state = _streams(seed, hash_k, seed_i, alg_id)
    Xall = theta.design_matrix(range(theta.N_CONFIGS))
    queried, best = {}, None
    rid, rfeas, rm, _r = sealed.reference_obs
    queried[rid] = (rfeas, rm)
    if rfeas and rm is not None:
        best = rm

    def observe(cid):
        nonlocal best
        f, m, _r2 = sealed.query(cid)
        queried[cid] = (f, m)
        if f and m is not None:
            best = m if best is None else min(best, m)

    for cid in _init_design(sealed, rng):
        if sealed.budget_used >= budget:
            break
        if cid not in sealed.queried_ids:
            observe(cid)
    step = 8
    while sealed.budget_used < budget:
        if _is_random_step(step):                           # 1-in-4 random interleave
            unq = [c for c in range(theta.N_CONFIGS) if c not in queried]
            cand = int(rng.choice(unq)) if unq else None
        else:
            cand = _propose(queried, Xall, best, rng, rf_state)
        if cand is None:
            break
        observe(cand)
        step += 1
    return best
