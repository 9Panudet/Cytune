"""A-3g — EXACT power at the achieved per-cell n, from the COMMITTED power-table generator.

The P-2 report must state, for every confirmatory cell, the power actually achieved at its final n
— never hand-interpolated from the n=6..17 preview table and never asserted. This wrapper imports
`scripts/power/clustered_power_preview.py` (the committed generator, unmodified) and calls its
`power(n, delta, rng, n_sim)` on the pre-registered extended-scan stream, so the numbers are
reproducible from the same code that produced the committed n80 thresholds
(results/power/power_table_extended.json: δ=0.4 → n80=26, power 0.8137; n80−1=25 → 0.7939).

Determinism: one fresh Generator(SEED_EXT) per invocation, n's consumed in ASCENDING order, so a
given set of n's always yields the same table. The stream is shared with the committed extended
scan by construction; this does NOT reproduce that scan's per-n values (different draw order) — it
reproduces the same ESTIMATOR at N_SIM_THRESH, whose Monte-Carlo SE is ≈0.0016 near 0.8.

Run in the pinned container (scipy):
  podman run --rm --network=none --security-opt label=disable -v <repo>:/repo:ro -v <out>:/out \
    localhost/motifbo-env:phase1 python3 /repo/scripts/phasep/power_at.py 11 18 23 37
"""
from __future__ import annotations
import json
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "power"))
import clustered_power_preview as cpp   # noqa: E402  (the committed generator, unmodified)

DELTA = 0.4        # PREREG §2 confirmatory MDE
FLOOR_N = 26


def power_at(ns, delta=DELTA, n_sim=None):
    """{n: power} for the given n's, ascending, from the committed generator."""
    n_sim = n_sim or cpp.N_SIM_THRESH
    rng = np.random.default_rng(cpp.SEED_EXT)
    return {int(n): round(float(cpp.power(int(n), delta, rng, n_sim=n_sim)), 4)
            for n in sorted(set(int(x) for x in ns))}


def main():
    ns = [int(x) for x in sys.argv[1:]] or [FLOOR_N]
    tbl = power_at(ns)
    out = {
        "delta": DELTA, "alpha": cpp.ALPHA, "n_sim": cpp.N_SIM_THRESH, "seed": cpp.SEED_EXT,
        "power_at_n": tbl,
        "floor": {"n": FLOOR_N, "committed_power_at_floor": 0.8137,
                  "source": "results/power/power_table_extended.json (thresholds['0.4'])"},
        "generator": "scripts/power/clustered_power_preview.py::power (committed, unmodified)",
        "recompute": "python3 scripts/phasep/power_at.py " + " ".join(str(n) for n in ns),
        "note": "Monte-Carlo SE ≈ 0.0016 near power 0.8 at this N_SIM; values are estimates of "
                "E[power] under the §5.3 cluster model, not exact analytic power.",
    }
    dst = sys.argv[0] and os.environ.get("POWER_AT_OUT", "/out/power_at_achieved_n.json")
    try:
        with open(dst, "w") as f:
            json.dump(out, f, indent=2)
        print(f"wrote {dst}")
    except OSError:
        pass
    print(json.dumps(out["power_at_n"], indent=2))


if __name__ == "__main__":
    main()
