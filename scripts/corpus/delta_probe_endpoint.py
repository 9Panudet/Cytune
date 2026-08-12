"""Step-1.3 GAP-2: re-measure BORDERLINE-Δ survivors on the v1.4 ENDPOINT rig.

The screen-grade Δ-probe (delta_probe.py) times each config with a single in-process median
(scale-probe). For units whose Δ sits near the 1.5 admission line, that can mis-rank the ratio
across the threshold. This script re-times the SAME 16 pre-registered configs with the PRODUCTION
endpoint rig (gate_runner endpoint mode -> measure_endpoint: median-of-N-subprocess, the v1.4
rig the real corpus uses), so the admission verdict rests on the production measurement.

Same configs() and build() as delta_probe.py (single source of truth). Writes the per-config
endpoint_ns + Δ_all/Δ_strict to /out/<unit>__endpoint.json, alongside the screen-grade file for a
screen-vs-endpoint comparison. Runs INSIDE :phase1 with the closure mounted at /unit/closure.

Usage (in-container): delta_probe_endpoint.py <unit_key> [reps=15] [nsub=3]
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, "/probe/corpus")
sys.path.insert(0, "/src")
import corpus_drivers as cd  # noqa: E402
from delta_probe import build, configs, delta  # noqa: E402
from motifbo.timing.endpoint import measure_endpoint  # noqa: E402


def endpoint_ns(u, so, scale, reps, nsub):
    # Call the validated median-of-nsub-subprocess rig DIRECTLY (not via gate_runner endpoint
    # mode, whose post-timing input_manifest.fingerprint_args refuses binning's list arg — the
    # fingerprint is golden-provenance, irrelevant to a Δ ratio).
    setup_code = u["setup"](scale)
    mutated = u.get("mutated_arg_indices") or []
    per_rep_regen = bool(mutated) and not u.get("recallable", False)
    try:
        res = measure_endpoint(module_path=so, kernel=u["kernel"], setup_code=setup_code,
                               reps=reps, n_subproc=nsub, policy=None,
                               mutated_arg_indices=mutated, per_rep_regen=per_rep_regen,
                               preimport=u.get("preimport"))
        return res["endpoint_ns"], res.get("subproc_medians_ns"), None
    except Exception as e:  # noqa: BLE001
        return None, None, f"measure_endpoint: {e}"


def main():
    unit_key = sys.argv[1]
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    nsub = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    u = cd.UNITS[unit_key]
    scale = u.get("endpoint_scale", u["delta_scale"])   # sub-band units (elkan) override to reach the band
    results = []
    for cfg in configs():
        so, ok, rc, log = build(u, cfg)
        rec = {"label": cfg["label"], "fp": cfg["fp"], "opt_flags": cfg["opt_flags"],
               "ffp": cfg["ffp"], "cydirs": cfg["cydirs"], "build_ok": ok}
        if ok:
            ep, subs, err = endpoint_ns(u, so, scale, reps, nsub)
            rec["median_ns"] = ep              # key name kept = delta() reuse
            rec["subproc_medians_ns"] = subs
            if ep is None:
                rec["time_err"] = err
        else:
            rec["build_log"] = log
        results.append(rec)
        print(json.dumps({"label": rec["label"], "build_ok": ok,
                          "endpoint_ns": rec.get("median_ns")}), flush=True)

    timed = [r for r in results if r.get("median_ns")]
    feasible = [r for r in timed if r["fp"] == "T"]
    summ = {"unit": unit_key, "module": u["module"], "fold": u["fold"],
            "archetype": u.get("archetype"), "scale": scale, "reps": reps, "nsub": nsub,
            "rig": "v1.4 endpoint (median-of-%d-subprocess)" % nsub,
            "n_built": sum(r["build_ok"] for r in results), "n_timed": len(timed),
            "delta_all": delta(timed), "delta_feasible_strict": delta(feasible),
            "t_best_ns": min((r["median_ns"] for r in timed), default=None),
            "t_worst_ns": max((r["median_ns"] for r in timed), default=None),
            "best_label": min(timed, key=lambda r: r["median_ns"])["label"] if timed else None,
            "worst_label": max(timed, key=lambda r: r["median_ns"])["label"] if timed else None,
            "configs": results}
    os.makedirs("/out", exist_ok=True)
    with open(f"/out/{unit_key}__endpoint.json", "w") as fh:
        json.dump(summ, fh, indent=2)
    print(json.dumps({k: summ[k] for k in ("unit", "delta_all", "delta_feasible_strict",
                                           "t_best_ns", "t_worst_ns", "best_label",
                                           "worst_label", "n_built", "n_timed")}, indent=2))


if __name__ == "__main__":
    main()
