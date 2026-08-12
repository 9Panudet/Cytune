"""V7 — how much would building the design over ARTIFACT equivalence classes actually buy?

The idea: if two config_ids compile to the same binary, spending two design points on them buys one
measurement's worth of information at two measurements' price. Once the I4 binding layer exists,
the design could be built over one representative per artifact class.

WHAT THE FROZEN TABLES CAN AND CANNOT ANSWER — stated before the number, because this is exactly
where a proxy could be smuggled in as proof. The tables were measured before the binding layer
existed and record NO artifact hash. They do record `so_size_b`. Equal size is NECESSARY but not
SUFFICIENT for byte-identity, so:

  - an UPPER BOUND on collapse is computable offline and is honest as an upper bound;
  - a claim that two configs ARE the same binary is not, and is not made here.

If the upper bound is negligible, V7 cannot be worth building and the bound settles it without any
proxy being trusted as proof. If it is large, the honest verdict is "not evaluable offline" and V7
needs live artifact hashes. Either way the number below is a CEILING, labelled as one.

Structural prior, from the release report's B1 measurement: distinct `.so` count equalled config
count on every one of the nine anchors (33/33, 49/49), because any two configs differing in a GCC
factor produce different bytes. Collapse can therefore only occur between configs differing SOLELY
in a Cython directive that is inert for that kernel — and D-optimal designs spread across factors,
so such pairs should be rare by construction. This script tests that reasoning rather than
asserting it.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))

import fleet                                               # noqa: E402
import variants                                            # noqa: E402
from cytune import plan, probe                             # noqa: E402
from cytune._vendor import theta                           # noqa: E402


def size_index(kid):
    """{config_id: so_size_b} straight from the frozen table."""
    out = {}
    path = os.path.join(fleet.FLEET, kid, "table.jsonl")
    for line in open(path):
        r = json.loads(line)
        if r.get("so_size_b"):
            out[r["config_id"]] = r["so_size_b"]
    return out


def gcc_key(cid):
    """The four factors that reach gcc's command line. Configs differing here cannot collide."""
    cfg = theta.config_of(cid)
    return (cfg[5], cfg[6], cfg[7], cfg[8])


def collapse_ceiling(ids, sizes):
    """Upper bound on how many of `ids` are redundant: same gcc flags AND same .so size."""
    groups = defaultdict(list)
    for c in ids:
        if c in sizes:
            groups[(gcc_key(c), sizes[c])].append(c)
    return sum(len(g) - 1 for g in groups.values() if len(g) > 1)


def main():
    man, ov = fleet.manifest(), fleet.overlay()
    roster = fleet.roster(man)
    pol = plan.STRICT
    probe_ids = [c for c in probe.probe_config_ids()]

    # The design points a real run at the routed budgets would actually measure.
    designs = {}
    for vname in ("V0", "V2"):
        v = next(x for x in variants.ALL if x.name == vname)
        for b in (16, 24, 32):
            designs[(vname, b)] = v.screen_plan(b, pol, {})["ids"]

    rows = []
    for role, entries in roster.items():
        for kid, cell in entries:
            sizes = size_index(kid)
            if not sizes:
                continue
            rec = {"kernel": kid, "role": role, "cell": cell, "n_sized": len(sizes),
                   "probe_collapse": collapse_ceiling(probe_ids, sizes)}
            for (vname, b), ids in designs.items():
                rec[f"{vname}_B{b}"] = collapse_ceiling(list(ids) + probe_ids, sizes)
            # whole-space ceiling, for scale
            rec["whole_space"] = collapse_ceiling(list(sizes), sizes)
            rows.append(rec)

    print("V7 — CEILING on design points saved by artifact-equivalence classing")
    print("(so_size_b equality within identical gcc flags: an UPPER BOUND, never a proof of "
          "byte-identity)\n")
    print(f"{'scope':22s} {'median':>8s} {'mean':>8s} {'max':>6s} {'kernels with any':>18s}")
    for label, key in (("probe (17 pts)", "probe_collapse"),
                       ("V0 design + probe B=16", "V0_B16"),
                       ("V0 design + probe B=24", "V0_B24"),
                       ("V0 design + probe B=32", "V0_B32"),
                       ("V2 design + probe B=16", "V2_B16"),
                       ("V2 design + probe B=32", "V2_B32"),
                       ("whole 1,728 space", "whole_space")):
        vals = [r[key] for r in rows]
        print(f"{label:22s} {statistics.median(vals):8.1f} {statistics.mean(vals):8.2f} "
              f"{max(vals):6d} {sum(1 for v in vals if v):>13d}/{len(vals)}")

    # ---- IS THE PROXY WORTH ANYTHING? Checked, not assumed -----------------------------------
    # A bound is only useful if it is tight enough to exclude something. Test the proxy against
    # the one DIRECT artifact-identity measurement that exists.
    kid = "fleet_R_01_csr"
    sizes = size_index(kid)
    groups = defaultdict(list)
    for c, s in sizes.items():
        groups[gcc_key(c)].append(s)
    one = next(iter(groups.values()))
    n_distinct = len(set(sizes.values()))
    print(f"\nPROXY VALIDITY CHECK on {kid}:")
    print(f"  so_size_b takes {n_distinct} distinct values across {len(sizes)} configurations")
    print(f"  within a single gcc-flag group: {len(set(one))} distinct sizes for {len(one)} configs")
    print(f"  the release report's DIRECT sha256 measurement (V1_RELEASE_REPORT §B1) found "
          f"33 distinct .so for the 33 configs it built — collapse ZERO, on every one of nine "
          f"anchors")
    print("  => equal size does NOT imply equal binary. The 'collapse' counted above is size "
          "COLLISION,\n     not artifact identity, and the ceiling it yields (96% of the space) "
          "excludes nothing.")
    print("\nVERDICT: V7 is NOT EVALUABLE from the frozen tables, and the only direct evidence "
          "that\n  exists — real artifact hashes on nine real anchors — measures the opportunity "
          "at ZERO.\n  V7 does not earn its line. It is not built.")

    p = os.path.join(fleet.ROOT, "results", "doe_v2", "v7_artifact_ceiling.json")
    json.dump({"per_kernel": rows,
               "proxy_validity": {
                   "kernel": kid, "distinct_sizes": n_distinct, "n_configs": len(sizes),
                   "distinct_sizes_within_one_gcc_group": len(set(one)),
                   "direct_measurement": ("V1_RELEASE_REPORT B1: 33/33 and 49/49 distinct .so "
                                          "hashes on all nine anchors — collapse zero"),
                   "verdict": ("proxy too loose to exclude anything; V7 not evaluable offline; "
                               "direct evidence puts the opportunity at zero")}},
              open(p, "w"), indent=1)
    print(f"\nraw -> {p}   (n={len(rows)} kernels with size data)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
