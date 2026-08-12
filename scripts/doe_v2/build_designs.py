"""Emit the frozen DOE-v2 design file: one design set per (variant, emission policy, size).

Deterministic and committed, for the reason designs_v2.py's docstring gives: a design computed at
run time would make what cytune measures depend on the host's numpy and RNG. An auditor recomputes
this file from this script + designs_v2.py + theta.py + prior_K.json.

SIZES stay {7, 15, 24}, matching `plan._design`'s existing rule N_d = min(24, B-1) with its
fallback to doe_24. Keeping the sizes identical means a variant changes WHICH configs are measured
and never HOW MANY, so a regret difference cannot be a budget difference in disguise.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))

import designs_v2 as D                                     # noqa: E402
from cytune import probe                                   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "results", "doe_v2", "designs_v2.json")
PRIOR = os.path.join(ROOT, "results", "doe_v2", "prior_K.json")
SIZES = (7, 15, 24)


def main():
    prior = json.load(open(PRIOR))
    probe_ids = probe.probe_config_ids()
    doc = {
        "schema": "cytune-doe-designs-v2",
        "eps": D.EPS, "restarts": D.RESTARTS, "max_iter": D.MAX_ITER,
        "sizes": list(SIZES),
        "criterion": ("D-optimal, det(Xd'Xd + A) where A = X0'X0 + K, Fedorov single-best-swap "
                      "exchange (Cook & Nachtsheim 1980 rank-1 delta)"),
        "probe_ids": probe_ids,
        "prior_source": "results/doe_v2/prior_K.json",
        "variants": {},
    }

    for pol_name, pol in D.POLICIES.items():
        cand = D.candidates(pol)
        strict_probe = sorted(c for c in probe_ids if pol.allows(c))
        n_live = len(D.live_columns(cand))
        print(f"\npolicy {pol_name}: |C|={len(cand)} params={n_live} "
              f"probe-rows-in-policy={len(strict_probe)}")

        for variant, kw in (
            ("V1", {}),                                                 # policy-matched only
            ("V2", {"prior_rows": strict_probe}),                       # + probe augmentation
            ("V3", {"prior_rows": strict_probe, "K": None}),            # + measured prior (below)
            ("V4", {"prior_rows": strict_probe, "coding": "ordinal"}),  # + ordinal coding
        ):
            kw = dict(kw)
            if variant == "V3":
                if pol_name != prior["policy"]:
                    print(f"  {variant}: skipped — prior_K.json is for policy "
                          f"{prior['policy']!r}, not {pol_name!r}")
                    continue
                kw["K"] = prior["K"]
            for nd in SIZES:
                d = D.build(nd, cand, ("doe_v2", variant, pol_name, nd), **kw)
                doc["variants"].setdefault(variant, {}).setdefault(pol_name, {})[f"doe_{nd}"] = d
                print(f"  {variant} doe_{nd}: rank {d['rank']}/{d['n_params']} "
                      f"logdet {d['logdet']:8.4f} "
                      f"{'FULL RANK' if d['full_rank'] else 'supersaturated'}"
                      f"{'  (+%d prior rows)' % d['n_prior_rows'] if d['n_prior_rows'] else ''}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(doc, open(OUT, "w"), indent=1)
    print(f"\n-> {OUT}")

    # ---- invariants, checked here rather than trusted -------------------------------------
    for variant, pols in doc["variants"].items():
        for pol_name, designs in pols.items():
            pol = D.POLICIES[pol_name]
            for key, d in designs.items():
                assert len(d["config_ids"]) == d["N_d"], (variant, pol_name, key)
                assert len(set(d["config_ids"])) == d["N_d"], f"{variant}/{pol_name}/{key} dupes"
                bad = [c for c in d["config_ids"] if not pol.allows(c)]
                assert not bad, (f"{variant}/{pol_name}/{key} contains {len(bad)} configs the "
                                 f"policy cannot emit — this is the defect being fixed")
    print("invariants: every design point is emittable under its own policy; no duplicates. OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
