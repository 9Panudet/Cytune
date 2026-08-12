# CLAUDE.md — cytune (Phase P)

Production Cython-directive × GCC-flag autotuner, decided by a fair, fully-measured 4-algorithm
study (RS / DOE / BO / Motif+BO) on a controlled benchmark (Datasets A/B/C synthetic + R real
anchors, exhaustive 1,728-config tables, offline replay). Hardware: i3-10100F, 16 GB, GPU unused.

**`PRODUCT_ROADMAP.md` is the spec. It is law.** This file tells you how to work; the roadmap
tells you what is true. On any conflict, the roadmap wins. Phase-1 (paper) is CLOSED — its
negative result stands and is never re-litigated (roadmap §0.1); do not touch its artifacts.

## Session start — every session
1. Read `STATE_PHASEP.md`. It names the exact next Step. Do that Step, nothing else.
2. Update STATE at every Step boundary (v1 §6.4 schema; cold-start resumable).
3. Any red gate/test: invoke `debug-mantra` before touching anything.

## Hard gates — never bypass, never reinterpret
- **Correctness absolute:** oracle-fail ⇒ infeasible, regardless of speed. The table records it;
  search never leaves feasible space; `cytune` never emits it. Fast-math is feasibility-gated;
  Δ_strict is always reported alongside Δ_all.
- **Class labels are MEASURED** (roadmap §3.4 thresholds, pre-registered) — never
  asserted-by-construction. Intended-vs-measured is a committed ledger.
- **Prereg before measure:** PREREG_PHASEP.md governs thresholds/tiers/metrics/tests/budgets/
  seeds. Changes are numbered, human-approved amendments — never silent.
- **Sealed-replay fairness:** algorithms compare only via the frozen tables through the ask–tell
  interface; the cheat-test must pass; no live measurement inside the study.
- **Human checkpoints P-1 / P-2 / P-3 / P-4** (pilot, dataset freeze, routing matrix, release):
  STOP and present; never self-pass. Honest negatives (a class that won't populate, an algorithm
  that never wins, Motif adding nothing) are valid, reportable outcomes.
- Inherited machinery binds: v1.4 timing rig (median-of-3, per-rep regen, K_final=30 endpoint),
  CF-1 phase-split, CF-4 measure_wrap asserts, CF-5 if any C++ kernel, β directive policy,
  cythonize-fail ⇒ whole-combo feasibility-0 cached once.

## Empirical honesty — mechanism, not vibes
- Every raw measurement → `/results/**` (or the kernel table), committed **before** any aggregate
  is quoted. A number without a raw pointer + recompute command does not exist.
- Statistics are recomputed from raw by `stats-auditor` — never hand-entered, never from memory.
- Worst-case, not representative; count before "all"; partials stated as partials.
- Never proxy-as-proof. Favorable surprises are alarms: investigate before celebrating.
- New instruments (generator, replay harness, probe) get positive AND negative controls before
  their readings count (a planted 2× lever must be detected; a known-flat kernel must read flat).
- Negative results are results.

## Environment
- All builds and runs inside the pinned Podman image X′ (`motifbo-env:phase1`, d45e33b0…). Never
  on the host. Image changes only via the additive-layer + byte-identity procedure, recorded.
- `-ffp-contract` always explicit (GCC's default is fast). 12 GB container ceiling.
- Every timed run goes through `measure_wrap.sh` (no_turbo, governor, cpu3 isolation, THP assert —
  it refuses to measure otherwise). Compile and measure phases never overlap (CF-1).
- Verify work with `pytest -q` on touched modules. A phase ends only at 100% of its exit criteria.

## Tools
- **graphify** — query the knowledge graph instead of grepping; hook rebuilds on commit.
- **9arm-skills**
  - `debug-mantra`: on any red gate, before any fix — reproduce → trace → falsify the hypothesis →
    cross-reference every breadcrumb. In that order.
  - `post-mortem`: after a validated fix (repro + root cause + validated fix) → `/logs/defects/D<n>.md`.
  - `scrutinize`: at every checkpoint and before any report leaves the repo.
- **Auditor subagents** (read-only, §6.5): `validation-auditor`, `bo-math-reviewer`,
  `stats-auditor`, `measurement-auditor`. Independent recompute, zero-diff required, at every
  checkpoint; verdicts recorded in STATE. BO does not enter the study without a bo-math-reviewer
  pass on the TDD fixtures.

## How to code here
- State assumptions before implementing. Unclear → stop and ask; never pick an interpretation
  silently. Decision-type blocks (spend/scope/irreversible) go to the human with a decision memo;
  information-type blocks get the cheapest discriminating probe instead of a question.
- Minimum code that completes the Step. Nothing speculative; no unrequested flexibility.
- Every change ends with a verifiable check (test or gate). TDD where the roadmap mandates it
  (BO math, oracle, rig changes). No vacuous tests — verify the failure path once.
- Keep the ledger: verified (evidence) / assumed (risk) / pending. Trust the ledger over memory.

## Where to look — read on demand, not upfront
| Task touches… | Read first |
|---|---|
| Goal change, standing v1 results, hard rules | roadmap §0 |
| Rig, CF ledger, oracle, sanitizer, environment | roadmap §1 |
| Search space Θ | roadmap §2 + Appendix A |
| Dataset A/B/C/R/H, kernel specs, class thresholds | roadmap §3 |
| Measurement tiers, table schema, golden-scale policy | roadmap §4 |
| Algorithms, replay interface, study design | roadmap §5 |
| Governance: STATE, prereg, auditors, ledger | roadmap §6 |
| Current phase steps + exit criteria + checkpoints | roadmap §7 |
| Product pipeline + hard guarantees | roadmap §8 |
| Risks | roadmap §9 |
