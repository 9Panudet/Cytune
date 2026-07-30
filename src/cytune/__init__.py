"""cytune v0 (P4-alpha) — Cython-directive x GCC-flag autotuner with a correctness certificate.

Status: v0, built under PREREG §12 Amendment A-4 BEFORE the P-2 freeze. Its routing is an INTERIM
heuristic pending the P3 study (results/prereg/CYTUNE_V0_ROUTING_INTERIM.md) and every output says
so. It touches development data only — the study's fleet, holdout H and R anchors are off limits
(A-4d).

Hard guarantees (roadmap §8.2), enforced and tested, not aspirational:
  1. Never emits a config that failed the oracle — under any flag, objective or budget.
  2. Fast-math is opt-in and still oracle-gated; the tolerance report always accompanies it.
  3. "No worthwhile speedup; best safe config = reference" is a first-class, tested output.
"""
# v1.0-rc0, RESEARCH PREVIEW. The label is deliberate and load-bearing: the P-3 algorithm study
# did NOT complete (13 of 200 seeds), so the routing policy shipped here is the INTERIM one, not a
# measured routing matrix. Everything the product REFUSES to do — emit an oracle-failing config,
# emit a config the sanitizer reports on, invent a speedup on a flat landscape — is measured and
# tested. Everything it CHOOSES is provisional. See results/PHASEP_REPORT.md §5 and §6.
__version__ = "1.0.0-rc0+research-preview"
