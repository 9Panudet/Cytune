#!/usr/bin/env python3
"""F1 — cytune's answer against the exhaustively-known optimum.

The nine Dataset-R anchors have frozen 1,728-config tables. cytune measures ~35 of those configs.
This computes what its answer actually cost.

HOW REGRET IS DEFINED, and why this way:

  * Both the numerator and the denominator come from the SAME frozen table, at the SAME measurement
    tier (screen). cytune re-calibrated each anchor to its own 65 ms target, so its absolute times
    are not comparable with the study's — but a ratio computed entirely inside the frozen table is,
    and that is the only comparison being made here.

  * The candidate set is the configs cytune was ALLOWED to emit: feasible in the frozen table, and
    permitted by the default FP-strict policy (no -ffast-math, no -ffp-contract=fast). Comparing
    against an optimum cytune was forbidden from choosing would measure the policy, not the search.
    The unrestricted optimum is reported alongside, so the cost of the policy is visible rather
    than hidden.

        regret = table_time(cytune's emitted config) / table_time(best allowed config) - 1

  * A `honest-flat` verdict emits the REFERENCE. Its regret is therefore the reference's regret —
    which is the honest number: it is what a user who ran cytune and followed its advice got.

Reads results/fleet/*/table.jsonl READ-ONLY. Writes only under results/release/.
"""
from __future__ import annotations

import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))

from cytune._vendor import theta  # noqa: E402

FLEET = os.path.join(REPO, "results", "fleet")
# Which dogfood directory to analyse. The 1.0.0 pass re-ran the nine anchors after the parallel
# build scheduler landed, so there are two: `dogfood` (the rc-era baseline) and `dogfood2` (the
# released build). Passed as argv[1] rather than hard-coded, so the before/after comparison uses
# ONE analyser over both and cannot drift into two definitions of regret.
DOG = os.path.join(REPO, "results", "release",
                   sys.argv[1] if len(sys.argv) > 1 else "dogfood")
REF = theta.REFERENCE_ID


def strict_ok(cid):
    """Emittable under cytune's default FP policy: no fast-math, no contraction."""
    return theta.config_of(cid)[8] == ("off", "off")


def load_table(kid):
    """{config_id: screen_median_ns} for every FEASIBLE config in the frozen table."""
    path = os.path.join(FLEET, kid, "table.jsonl")
    out = {}
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if r.get("feasible") and r.get("screen") and r["screen"].get("median_ns"):
                out[r["config_id"]] = r["screen"]["median_ns"]
    return out


def wall_times():
    times = {}
    p = os.path.join(DOG, "RUNLOG.txt")
    if os.path.exists(p):
        for line in open(p):
            if " exit=" in line and " wall_s=" in line:
                kid, rest = line.split(" exit=", 1)
                times[kid.strip()] = int(rest.split("wall_s=")[1].strip())
    return times


def analyse(kid, walls):
    cert_path = os.path.join(DOG, "runs", kid, kid, "certificate.json")
    if not os.path.exists(cert_path):
        return {"kernel_id": kid, "error": f"no certificate at {cert_path}"}
    cert = json.load(open(cert_path))
    table = load_table(kid)
    if not table:
        return {"kernel_id": kid, "error": "frozen table has no feasible rows"}

    allowed = {c: t for c, t in table.items() if strict_ok(c)}
    best_allowed = min(allowed, key=allowed.get)
    best_any = min(table, key=table.get)

    emitted = (cert.get("emitted_config") or {}).get("config_id")
    t_emitted = table.get(emitted)

    ranked = sorted(allowed, key=allowed.get)
    rank = (ranked.index(emitted) + 1) if emitted in allowed else None

    row = {
        "kernel_id": kid,
        "verdict": cert["verdict"],
        "emitted_config": emitted,
        "emitted_is_reference": emitted == REF,
        "configs_measured": cert.get("budget", {}).get("total_measured"),
        "wall_s": walls.get(kid),
        "cytune_reported_speedup": cert.get("speedup"),
        "sanitizer_gate": (cert.get("sanitizer_gate") or {}).get("verdict"),
        # 1.0.0 provenance, absent from the rc-era certificates and reported as None for them.
        "distinct_artifacts": (cert.get("factor_degeneracy") or {}).get("n_distinct_artifacts"),
        "distinct_sources": (cert.get("factor_degeneracy") or {}).get(
            "n_distinct_generated_sources"),
        "directives_inert": (cert.get("factor_degeneracy") or {}).get("directives_inert"),
        "timing_corroborated": ((cert.get("measurement") or {}).get("timing_corroboration")
                                or {}).get("corroborated"),
        "emitted_artifact": ((cert.get("provenance") or {}).get("emitted_artifact_sha256") or "")[:12],
        "artifact_bound": (
            (cert.get("provenance") or {}).get("emitted_artifact_sha256")
            == (cert.get("provenance") or {}).get("endpoint_artifact_sha256")
            if (cert.get("provenance") or {}).get("emitted_artifact_sha256") else None),

        "n_feasible_in_table": len(table),
        "n_allowed_by_policy": len(allowed),
        "true_best_allowed_config": best_allowed,
        "true_best_any_config": best_any,

        # everything below in frozen-table screen-tier ns
        "t_emitted_ns": t_emitted,
        "t_best_allowed_ns": allowed[best_allowed],
        "t_reference_ns": table.get(REF),
        "t_best_any_ns": table[best_any],
    }

    if t_emitted and allowed[best_allowed]:
        row["regret"] = t_emitted / allowed[best_allowed] - 1.0
        row["rank_of_emitted_among_allowed"] = rank
    else:
        row["regret"] = None
        row["note_regret"] = ("the emitted config is not feasible in the frozen table — cytune "
                              "measured it live and the study did not, or vice versa")

    if table.get(REF):
        row["headroom_available"] = table[REF] / allowed[best_allowed] - 1.0
        row["headroom_captured"] = (table[REF] / t_emitted - 1.0) if t_emitted else None
        row["fastmath_only_extra"] = allowed[best_allowed] / table[best_any] - 1.0
    return row


def main():
    walls = wall_times()
    kids = sorted(d for d in os.listdir(os.path.join(DOG, "runs"))
                  if os.path.isdir(os.path.join(DOG, "runs", d)))
    rows = [analyse(k, walls) for k in kids]
    out = os.path.join(DOG, "REGRET.json")
    with open(out, "w") as f:
        json.dump(rows, f, indent=2)

    hdr = (f"{'anchor':<22} {'verdict':<20} {'emit':>5} {'rank':>5} {'regret':>9} "
           f"{'headroom':>9} {'captured':>9} {'meas':>5} {'wall_s':>7}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        if r.get("error"):
            print(f"{r['kernel_id']:<22} ERROR: {r['error']}")
            continue
        reg = f"{r['regret']:+.2%}" if r.get("regret") is not None else "n/a"
        hd = f"{r['headroom_available']:+.2%}" if r.get("headroom_available") is not None else "n/a"
        cap = f"{r['headroom_captured']:+.2%}" if r.get("headroom_captured") is not None else "n/a"
        rank = r.get("rank_of_emitted_among_allowed")
        print(f"{r['kernel_id']:<22} {r['verdict']:<20} {r['emitted_config']!s:>5} "
              f"{rank!s:>5} {reg:>9} {hd:>9} {cap:>9} "
              f"{r['configs_measured']!s:>5} {r['wall_s']!s:>7}")

    ok = [r for r in rows if r.get("regret") is not None]
    if ok:
        worst = max(ok, key=lambda r: r["regret"])
        med = sorted(r["regret"] for r in ok)[len(ok) // 2]
        print(f"\nn={len(ok)}  median regret {med:+.2%}  worst {worst['regret']:+.2%} "
              f"({worst['kernel_id']})")
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
