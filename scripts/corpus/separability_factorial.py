"""Step-1.3 A3 — SEPARABILITY factorial for the 2 high-Δ units (csr, elkan).

Grounds the (INFERRED) BO≤RS expectation with a MEASURED interaction-structure decomposition.
The 16-config Δ-probe bundled opt_level+march+funroll into one OPT factor; this sweep SEPARATES the
active knobs so main effects and interactions can be isolated:

    boundscheck ∈ {True, False}   (the csr lever; other 3 checks held at as-shipped False)
    opt_level   ∈ {-O1, -O2, -O3} (no -funroll, so opt_level is pure)
    march       ∈ {x86-64, native}
  => 2×3×2 = 12 configs, all FP=strict (-ffp-contract=off, NO fast-math), cdivision=True (as-shipped).

Each cell is timed on the v1.4 median-of-3-subprocess ENDPOINT rig (bare unit -> measure_endpoint;
package-import unit -> delta_probe_pkg median-of-nsub). elkan's _k_means_common (where the hot
_euclidean_dense_dense distance loop lives) is REBUILT under each directive config (cobuild), so the
boundscheck sweep reaches the real hot loop, not an installed helper. Raw -> /out/<unit>__separability.json;
decompose with separability_decompose.py (ANOVA-style, recomputed from this raw).

Usage (in-container): separability_factorial.py <unit_key> [reps=15] [nsub=3]
"""
import json
import os
import sys

sys.path.insert(0, "/probe/corpus")
sys.path.insert(0, "/src")
import corpus_drivers as cd  # noqa: E402
from delta_probe import build as build_bare  # noqa: E402
from delta_probe_pkg import build_pkg, time_pkg  # noqa: E402
from motifbo.timing.endpoint import measure_endpoint  # noqa: E402

OPT = ["-O1", "-O2", "-O3"]
MARCH = ["x86-64", "native"]
BC = ["True", "False"]
CYDIRS = ("-X boundscheck={bc} -X wraparound=False -X initializedcheck=False "
          "-X nonecheck=False -X cdivision=True")


def configs_sep():
    out = []
    for bc in BC:
        for opt in OPT:
            for march in MARCH:
                label = f"BC{bc[0]}_{opt}_{'N' if march=='native' else 'G'}"
                out.append({"label": label, "bc": bc, "opt_level": opt, "march": march,
                            "cydirs": CYDIRS.format(bc=bc),
                            "opt_flags": f"{opt} -march={march}", "ffp": "off"})
    return out


def time_bare(u, so, scale, reps, nsub):
    mutated = u.get("mutated_arg_indices") or []
    per_rep_regen = bool(mutated) and not u.get("recallable", False)
    res = measure_endpoint(module_path=so, kernel=u["kernel"], setup_code=u["setup"](scale),
                           reps=reps, n_subproc=nsub, policy=None,
                           mutated_arg_indices=mutated, per_rep_regen=per_rep_regen,
                           preimport=u.get("preimport"))
    return res["endpoint_ns"], res.get("subproc_medians_ns")


def time_pkg_endpoint(unit_key, work, scale, reps, nsub):
    import statistics
    subs = []
    for _ in range(nsub):
        med, _ = time_pkg(unit_key, work, scale, reps)
        if med is not None:
            subs.append(med)
    return (statistics.median(subs) if subs else None), subs


def main():
    unit_key = sys.argv[1]
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    nsub = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    u = cd.UNITS[unit_key]
    is_pkg = bool(u.get("cobuild"))
    scale = u.get("endpoint_scale", u["delta_scale"])
    results = []
    for cfg in configs_sep():
        if is_pkg:
            work, ok, err = build_pkg(u, cfg)
            ep, subs = (time_pkg_endpoint(unit_key, work, scale, reps, nsub) if ok else (None, None))
        else:
            so, ok, rc, err = build_bare(u, cfg)
            ep, subs = (time_bare(u, so, scale, reps, nsub) if ok else (None, None))
        rec = {"label": cfg["label"], "bc": cfg["bc"], "opt_level": cfg["opt_level"],
               "march": cfg["march"], "build_ok": ok, "endpoint_ns": ep,
               "subproc_medians_ns": subs}
        if not ok:
            rec["build_err"] = str(err)[-300:]
        results.append(rec)
        print(json.dumps({"label": rec["label"], "build_ok": ok, "endpoint_ns": ep}), flush=True)

    summ = {"unit": unit_key, "module": u["module"], "design": "2(boundscheck)x3(opt_level)x2(march)",
            "fp": "strict (-ffp-contract=off, no fast-math)", "cydirs_template": CYDIRS,
            "scale": scale, "reps": reps, "nsub": nsub, "rig": "v1.4 endpoint median-of-%d" % nsub,
            "build_path": "pkg cobuild" if is_pkg else "bare build_unit.sh", "configs": results}
    os.makedirs("/out", exist_ok=True)
    with open(f"/out/{unit_key}__separability.json", "w") as fh:
        json.dump(summ, fh, indent=2)
    print(json.dumps({"unit": unit_key, "n_cells": len(results),
                      "n_timed": sum(1 for r in results if r.get("endpoint_ns"))}, indent=2))


if __name__ == "__main__":
    main()
