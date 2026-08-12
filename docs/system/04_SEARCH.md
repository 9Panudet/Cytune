# The search — Θ, the designs, and why the engine is what it is

## Θ

1,728 configurations = 5 Cython directives (2 levels each) × `opt_level` (3) × `march` (2) ×
`funroll` (3) × `fmffp` (3). `_vendor/theta.py` is the **sole source** of config ids; the reference
is **288**.

`fmffp` is one composite factor with three levels — `(off,off)` strict, `(off,fast)` FMA
contraction, `(on,NA)` fast-math — because `-ffast-math` implies contraction, so treating them as
independent axes would encode a state that cannot exist.

**Emission policy** decides what may be emitted, and therefore what the walk may spend budget on:

| policy | emittable | non-constant parameters |
|---|---|---|
| FP-strict (default) | 576 | 11 |
| `--allow-fp-contract` | 1,152 | 12 |
| `--allow-fast-math` | 1,728 | 13 |
| `--portable-flags` | 288 | 10 |

## The designs

`_vendor/data/doe_designs_theta.json` holds pre-registered D-optimal designs built by Fedorov
exchange (Cook & Nachtsheim rank-1 update, `det(X'X + εI)`, ε=1e-6, 50 seeded restarts, ties broken
by lexicographically-lowest sorted config-id tuple). `probe_16` + the reference is the 17-point
probe; `doe_24` and friends are the screen.

They are **frozen inputs to the search**, pinned by the vendor manifest, and shipping a different
one would change which configurations are measured while every document still claimed the
pre-registered design.

## Screen, walk, select

`plan.screen_plan(budget)` takes the design, capped at `min(24, budget - 1)`. The `- 1` reserves
budget for the walk. Capping at `budget` was **D-2**: for every budget in [17, 24] the fallback
24-point design ate the whole budget and the walk got nothing. Measured cost of that one line:
median regret 3.95 % vs 1.46 %, worst 516 % vs 46 %, on 58 of 149 kernels — and **0 of the 9 real-
code anchors**, which is why nine live anchors did not see it and the fleet-wide gate does.

`plan.walk_plan` fits main effects on what the screen returned (ridge, `_vendor/algorithms.py`) and
takes the predicted-best unqueried configurations. It visits **only configurations this run could
emit**.

## D-1 — a known defect, deliberately not fixed

`walk_plan` obeys the emittable-only rule. **`screen_plan` does not.** Under the default policy the
screen spends 86 % / 73 % / 67 % of `doe_7` / `doe_15` / `doe_24` on configurations the run cannot
emit. `docs/CONTRIBUTING.md` states the rule this breaks.

It is a defect, it was reported as one, and the obvious fix was measured and **rejected**: every
policy-matched variant made real-code regret *worse*. The mechanism, measured on one anchor: the
policy-matched screen is strictly better *as a screen* (15/15 legal, best rank 21/576 vs 83/576) and
its final answer is worse (rank 20 vs 5). At these budgets the screen barely contributes winners;
the walk does.

So the defect stands, and the B1 fleet gate measures it as a **ratchet** — the emittable fraction of
paid budget may not decrease. D-1 cannot get worse, and a future fix shows up as the gate improving.

## Routing, installed as a negative result

`routing.py` rules R0–R5. Only two earned their place:

* **R0** abort — the reference is infeasible, or fewer than 4 probe rows are feasible.
* **R1** honest-flat — `delta_probe <= 1.10`, five times the measured ~2 % rig noise floor.

The rest route to DOE. **The study measured that per-cell engine switching does not beat
always-DOE on held-out kernels** (RQ-P2), so cytune routes to DOE unconditionally and every
certificate says the routing policy is an engineering default and not a validated router. The study
changed the *status* of that choice, not the choice.

## Why DOE and not Bayesian optimisation

Four algorithms were compared under one pre-registration on frozen tables through a sealed ask–tell
interface, with a cheat-test proving no algorithm could see more than its budget.

* **DOE wins.** Best product-runnable arm in 18 of 20 cells.
* **BO loses to DOE in 18 of 20, and is worse than random search on flat landscapes.** The
  Bayesian arm does not earn its cost.
* **Motif+BO passed its statistical gate (p=3.46e-17, δ=0.772) and was NOT shipped.** Its warm-start
  sources were 9.7× enriched for siblings of the target's own template, and the corpus it needs does
  not exist at the point of use. A win by leakage is not a win.

## DOE-v2, and `--probe-as-screen`

Six Tier-1 variants were pre-registered and evaluated offline: policy-matched designs, probe
augmentation, Bayesian-D with a measured fleet prior, ordinal coding, axis pinning, sequential
augmentation. **All six failed the ship rule on real code.** Tier 2 (a model over the effect vector)
was gated on there being headroom left and was never built, because there was not.

`--probe-as-screen` — skip the second screen, spend everything on the walk — is the one change that
measured better. Live, five runs per arm on the anchors: median regret 1.409 % → 0.802 %, worst
9.791 % → 2.664 %, same cost, *more* stable. It is **off by default** because the fleet gate finds
nine kernels it regresses past 5 pp, one by 28 pp, **none of them an anchor**. The second screen is
insurance against a tail that the median hides and the anchors cannot see.

Full evidence: `results/release/DOE_V2_REPORT.md` and `results/release/LAUNCH_REPORT.md`
(`research` branch).
