"""P3 sealed replay STUDY runner (PREREG §3) — pure computation on FROZEN tables only.

FREEZE GUARD (structural, §11): this runner refuses to start unless <fleet>/FREEZE_MANIFEST.json
exists, and every table it loads is sha256-verified against that manifest AT LOAD. The manifest is
created exactly once by the P-2 freeze step (make_freeze_manifest, part of the CHECKPOINT P-2
deliverable). Until then no algorithm can touch any measured table through this runner — the
"NO replay before the freeze" guard is code, not convention.

Study set (§3.4): ACCEPTED fleet kernels that are neither holdout H nor Dataset R. Arms in the
§3.3 fixed order — RS=1, DOE=2, BO=3, Motif+BO=4. Budgets B ∈ {8,16,32,64,128}. Seeds (§3.2):
200 per (algorithm × kernel) for RS/BO/Motif via seed_i = SeedSequence([20260708, hash_k, alg_id,
i]) (seeds.seq passes ints through; hash_k = seeds.kernel_hash); DOE is deterministic — ONE
trajectory per kernel × budget, recorded as such.

Motif arm (§8.4): LOKO — sources for target k = study set minus {k} (H and R are never IN the
study set); features via motif.extract_features on the kernel's committed kernel.pyx under the
HARD-FAIL contract: extraction failure ⇒ the kernel is excluded from the Motif arm with a recorded
reason (results/study/motif_exclusions.jsonl), never a zero vector; ≥20% failures ⇒ RQ-P3 NOT
EVALUABLE (§3.4, decided at analysis). Per source, configs are walked in ascending screen-median
order (ties lowest config_id) from the FROZEN table.

Checkpointed + resumable: append-only results/study/regret.jsonl; a (kernel, alg, budget, seed_i)
row already present is never recomputed. §10 pre-registers the multi-day checkpointed runtime.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithms      # noqa: E402
import bo as bomod     # noqa: E402
import motif           # noqa: E402
import replay          # noqa: E402
import san_overlay     # noqa: E402  — D23/A-9: the §1.4 verdict, applied at table load
import seeds           # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
ALG = {"rs": 1, "doe": 2, "bo": 3, "motifbo": 4}          # §3.3 fixed order
BUDGETS = (8, 16, 32, 64, 128)
N_SEEDS = 200


class FreezeViolation(SystemExit):
    pass


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_freeze_manifest(fleet_dir, ledger_name="fleet_ledger.jsonl"):
    """THE P-2 freeze act: hash every ACCEPTED kernel's table.jsonl + class_v2.json. Run once at
    CHECKPOINT P-2 (never before the campaign completes); refuses to overwrite an existing freeze."""
    out = os.path.join(fleet_dir, "FREEZE_MANIFEST.json")
    if os.path.exists(out):
        raise FreezeViolation(f"{out} already exists — the freeze is immutable; refusing overwrite")
    entries = {}
    for line in open(os.path.join(fleet_dir, ledger_name)):
        e = json.loads(line)
        if e.get("status") != "ACCEPTED":
            continue
        kid = e["kernel_id"]
        kdir = os.path.join(fleet_dir, kid)
        entries[kid] = {"table_sha256": _sha(os.path.join(kdir, "table.jsonl")),
                        "class_v2_sha256": _sha(os.path.join(kdir, "class_v2.json")),
                        "holdout": bool(e.get("holdout")), "dataset": e.get("dataset", "synthetic"),
                        "template": e.get("template"), "measured_v2": e.get("measured_v2"),
                        "slot": e.get("slot"),
                        # A-3b: the wave label is FROZEN with the dataset. The freeze is
                        # write-once, so a manifest without it could never carry the
                        # pre-registered with/without-wave-2 robustness slice.
                        "wave": e.get("wave", 1),
                        "flag_FM": e.get("flag_FM"), "flag_FEAS": e.get("flag_FEAS")}
    man = {"n_kernels": len(entries), "kernels": entries}
    man["manifest_sha256_basis"] = "sha256(table.jsonl), sha256(class_v2.json) per ACCEPTED kernel"
    # CLASSIFIER PROVENANCE. The freeze is write-once, so anything not recorded here can never be
    # added. class_v2.json contents are only interpretable against the classifier that produced
    # them, and E4 changed that classifier's flag_FEAS predicate at this very boundary — so the
    # manifest pins the classifier source hash and its thresholds alongside the data hashes.
    here = os.path.dirname(os.path.abspath(__file__))
    man["classifier"] = {
        "source": "scripts/phasep/a2_reclassify.py",
        "sha256": _sha(os.path.join(here, "a2_reclassify.py")),
        "taxonomy": "A-2a v2 (FLAT/MID/LEVER-SEP/INT on the strict axis; orthogonal FM, FEAS flags)",
        "flag_FEAS_predicate": "4 * n_infeasible >= n_total   (ERRATUM E4, integer-exact)",
        "e4_evidence": "results/fleet/E4_ALIGNMENT_EVIDENCE.json",
    }
    man["cell_rule"] = ("cell = 'FLAT+FM' if (measured_v2 == 'FLAT' and flag_FM) else measured_v2; "
                        "bare FLAT and INT are descriptive, not confirmatory floors")
    with open(out, "w") as f:
        json.dump(man, f, indent=2)
    return out, man


def make_h_manifest(fleet_dir, ledger_name="fleet_ledger.jsonl"):
    """Seal holdout H (A-7 §7). Separate from FREEZE_MANIFEST.json by design: the training freeze
    is write-once and was committed at 0540fb2, so H cannot be folded into it — and must not be,
    since H is the P4 acceptance set and the P3 firewall depends on the two being distinguishable.
    Refuses to overwrite an existing seal, exactly like the training freeze."""
    out = os.path.join(fleet_dir, "H_MANIFEST.json")
    if os.path.exists(out):
        raise FreezeViolation(f"{out} already exists — H is sealed; refusing overwrite")
    entries, cells, prov_counts = {}, {}, {}
    # A-7i: the allocation regime in force, recovered from the ledger rows themselves rather than
    # from shell history, plus the cap-stop record. A cell can end short for THREE different
    # reasons and the seal must not blur them: deprioritized (a human ruling), supply-exhausted
    # (the roster is spent), or cap-stopped. Reporting a deprioritized cell as "supply exhausted"
    # would attribute a human decision to the data — the seal is write-once, so this is recorded
    # correctly here or never.
    deprioritized, cap_stop, h_spend = [], None, 0.0
    for line in open(os.path.join(fleet_dir, ledger_name)):
        e = json.loads(line)
        if e.get("run_kind") == "holdout":
            h_spend += ((e.get("build_s") or 0) + (e.get("measure_s") or 0)
                        + (e.get("orphan_s") or 0))
            for r in (e.get("deprioritized") or []):
                if r not in deprioritized:
                    deprioritized.append(r)
            if e.get("status") == "H_CAP_STOP":
                cap_stop = {k: e.get(k) for k in ("spend_s", "cap_s", "cells", "total")}
        if e.get("status") != "ACCEPTED" or not e.get("holdout") or e.get("dataset") == "R":
            continue
        kid = e["kernel_id"]
        kdir = os.path.join(fleet_dir, kid)
        cell = "FLAT+FM" if (e.get("measured_v2") == "FLAT" and e.get("flag_FM")) \
            else e.get("measured_v2")
        p = e.get("provenance")
        entries[kid] = {"table_sha256": _sha(os.path.join(kdir, "table.jsonl")),
                        "class_v2_sha256": _sha(os.path.join(kdir, "class_v2.json")),
                        "provenance": p, "template": e.get("template"), "params": e.get("params"),
                        "feas_variant": e.get("feas_variant"), "slot": e.get("slot"),
                        "intended_regime": e.get("intended_regime"),
                        "measured_v2": e.get("measured_v2"), "cell": cell,
                        "flag_FM": e.get("flag_FM"), "flag_FEAS": e.get("flag_FEAS"),
                        "holdout": True, "dataset": e.get("dataset", "synthetic")}
        cells[cell] = cells.get(cell, 0) + 1
        prov_counts[p] = prov_counts.get(p, 0) + 1
    here = os.path.dirname(os.path.abspath(__file__))
    H_PER_CELL, H_MIN_TOTAL = 3, 15
    dep_cells = {"FLAT_FM_H": "FLAT+FM", "FLAT_FM_W2": "FLAT+FM",
                 "INT_H": "INT", "MID_W2": "MID", "LEVER_SEP_W2": "LEVER-SEP"}
    dep_cell_names = {dep_cells[r] for r in deprioritized if r in dep_cells}
    shortfall = {}
    for c in ("FLAT+FM", "MID", "LEVER-SEP", "INT"):
        n = cells.get(c, 0)
        if n < H_PER_CELL:
            shortfall[c] = {
                "n": n, "required": H_PER_CELL, "short_by": H_PER_CELL - n,
                "cause": ("DEPRIORITIZED (A-7i human allocation ruling) — NOT short by supply"
                          if c in dep_cell_names else
                          "supply/cap — the walk served this cell and it did not fill"),
            }
    man = {
        "n_kernels": len(entries),
        "cells": cells,
        "provenance_counts": prov_counts,
        "ruling": {"per_cell": H_PER_CELL, "min_total": H_MIN_TOTAL,
                   "per_cell_met": {c: cells.get(c, 0) >= H_PER_CELL
                                    for c in ("FLAT+FM", "MID", "LEVER-SEP", "INT")},
                   "total_met": len(entries) >= H_MIN_TOTAL,
                   "shortfall": shortfall},
        "allocation": {
            "deprioritized": deprioritized,
            "amendment": "PREREG §12 A-7i (allocation only; no supply added, A-7c ONE-SHOT intact)",
            "note": ("A deprioritized cell was still COUNTED and REPORTED at its measured value; "
                     "only SERVING stopped. Its shortfall is a human allocation decision and must "
                     "never be reported as supply exhaustion."),
        },
        "cap_stop": cap_stop,
        "h_spend_s": round(h_spend, 1),
        "provenance_rule": (
            "H-ext = drawn from an A-7 extended registry (FLAT_FM_H / INT_H) — a parameterization "
            "OUTSIDE the training distribution's grid. H-orig = drawn from a pre-A-7 registry."),
        "provenance_framing": (
            "The A-7 extension makes H a MILD EXTRAPOLATION of the training parameter "
            "distribution rather than a same-grid resample. This makes RQ-P2 a HARDER and more "
            "realistic generalization test, not a weaker one: real user kernels are out-of-"
            "distribution too. PRE-REGISTERED (A-7e): RQ-P2 acceptance and routed regret at P4 "
            "are reported SLICED by provenance — H-orig and H-ext separately, never only pooled — "
            "so any routing degradation on the OOD kernels is visible instead of averaged away."),
        "membership_rule": "A-2i measured full-table classification; no grandfathering",
        "anti_clone": ("eps=0.05 Chebyshev on (lnD_all, lnD_strict, IF_strict, infeas_frac, "
                       "greedy_gap) within template, keyed across ALL waves AND accepted H"),
        "cap": {"cap_s": 86400, "definition": "A-7d: sum(build_s+measure_s+orphan_s) over ALL "
                                              "holdout ledger rows, any status"},
        "classifier": {"source": "scripts/phasep/a2_reclassify.py",
                       "sha256": _sha(os.path.join(here, "a2_reclassify.py")),
                       "flag_FEAS_predicate": "4 * n_infeasible >= n_total (ERRATUM E4)"},
        "cell_rule": ("cell = 'FLAT+FM' if (measured_v2 == 'FLAT' and flag_FM) else measured_v2"),
        "firewall": "H is NEVER in the P3 study set (run_study.study_set excludes holdout)",
        "kernels": entries,
    }
    with open(out, "w") as f:
        json.dump(man, f, indent=2)
    return out, man


def load_manifest(fleet_dir):
    p = os.path.join(fleet_dir, "FREEZE_MANIFEST.json")
    if not os.path.exists(p):
        raise FreezeViolation(
            "FREEZE GUARD: no FREEZE_MANIFEST.json — the P-2 freeze has not happened; "
            "no algorithm may touch any measured table (PREREG §11)")
    return json.load(open(p))


def load_frozen(fleet_dir, manifest, kid):
    """Hash-verify (§11) then load a frozen table, with the §1.4 sanitizer overlay applied.

    The hash check and the overlay are not in tension: the hash proves the RAW has not moved, the
    overlay corrects a LABEL on top of it (D23 / amendment A-9). Both must happen, in that order —
    an overlay applied to a table that had drifted would be a correction to the wrong data."""
    tpath = os.path.join(fleet_dir, kid, "table.jsonl")
    want = manifest["kernels"][kid]["table_sha256"]
    got = _sha(tpath)
    if got != want:
        raise FreezeViolation(f"FREEZE GUARD: {kid} table.jsonl hash mismatch "
                              f"(frozen {want[:12]}… vs on-disk {got[:12]}…)")
    tbl, _opt = replay.load_frozen_table(tpath, overlay=_overlay(fleet_dir).get(kid))
    return tbl


_OVERLAY_CACHE = {}


def _overlay(fleet_dir):
    """The §1.4 sanitizer infeasibility overlay, loaded once per fleet dir. An ABSENT overlay file
    is treated as empty, which is correct only because its absence is itself checked at study start
    (`assert_overlay_present`) — 'no overlay file' must never silently mean 'nothing to correct'."""
    if fleet_dir not in _OVERLAY_CACHE:
        _OVERLAY_CACHE[fleet_dir] = san_overlay.load(fleet_dir)
    return _OVERLAY_CACHE[fleet_dir]


def assert_overlay_present(fleet_dir):
    """Structural guard, same spirit as the freeze guard: refuse to run a study on tables whose
    §1.4 gate verdict has never been computed. D23 showed the oracle alone passes configs that
    read out of bounds; a study run without the overlay would optimise straight into them."""
    p = os.path.join(fleet_dir, "SANITIZER_INFEASIBLE_OVERLAY.json")
    if not os.path.exists(p):
        raise FreezeViolation(
            "SANITIZER GUARD: no SANITIZER_INFEASIBLE_OVERLAY.json — roadmap §1.4's verdict has "
            "not been computed for this fleet. Run scripts/phasep/san_overlay.py first. "
            "(D23: the oracle passed 1,296 configs that read out of bounds.)")
    return json.load(open(p))


def study_set(manifest, waves=None):
    """§3.4: fleet minus H minus R. `waves` implements the A-3b robustness slice — waves=(1,)
    reproduces the pre-A-3 training set so P3 per-class results can be reported both with and
    without the wave-2 top-up kernels, as pre-registered."""
    return sorted(k for k, v in manifest["kernels"].items()
                  if not v["holdout"] and v["dataset"] != "R"
                  and (waves is None or v.get("wave", 1) in waves))


def _best_by_screen(tbl):
    feas = [(m, c) for c, (f, m, _r) in tbl.items() if f and m is not None]
    return [c for _m, c in sorted(feas)]                   # ascending median, ties lowest cid


def _gen_index(fleet_dir, kid):
    sp = os.path.join(fleet_dir, "_kernels", kid, "spec.json")
    if os.path.exists(sp):
        return json.load(open(sp)).get("generation_index", kid)
    return kid


def motif_sources(fleet_dir, manifest, kids, exclusions_path):
    """Features + best-config walks for every study kernel, hard-fail contract enforced."""
    feats, excl = {}, {}
    for kid in kids:
        pyx = os.path.join(fleet_dir, "_kernels", kid, "kernel.pyx")
        try:
            feats[kid] = motif.extract_features(pyx)
        except motif.MotifExtractionError as e:
            excl[kid] = str(e)
    if excl:
        with open(exclusions_path, "a") as f:
            for kid, why in excl.items():
                f.write(json.dumps({"kernel_id": kid, "reason": why}) + "\n")
    return feats, excl


def _done_set(out_path):
    """Completed (kernel, alg, budget, seed) keys — read from EVERY regret*.jsonl in the output
    directory, not just this shard's own file.

    A row is done regardless of which shard wrote it, and reading only one file makes the study
    NON-RESHARDABLE: changing the shard count would orphan every existing row and silently
    recompute work that is already on disk. Scanning the directory costs one pass over files that
    are being read anyway, and makes `--n-shards` a free parameter instead of a one-way door."""
    done = set()
    d = os.path.dirname(os.path.abspath(out_path)) or "."
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            if not (name.startswith("regret") and name.endswith(".jsonl")):
                continue
            for line in open(os.path.join(d, name)):
                r = json.loads(line)
                done.add((r["kernel_id"], r["alg"], r["budget"], r["seed_i"]))
    return done


def run_study(fleet_dir, out_dir, budgets=BUDGETS, n_seeds=N_SEEDS, arms=("rs", "doe", "bo", "motifbo"),
              shard=0, n_shards=1, tag=""):
    """`shard`/`n_shards` partition the STUDY SET BY KERNEL so N processes can run concurrently on
    one box. Replay is pure computation over frozen tables — no timing, so CF-1 does not apply and
    all cores are fair game. Sharding by kernel (not by seed) keeps each shard's Motif arm able to
    see every OTHER kernel as a LOKO warm-start source, which sharding by seed would not change but
    sharding the study SET would break.

    Each shard writes its own `regret{tag}.jsonl`; the analysis concatenates them. Rows are keyed
    by (kernel, alg, budget, seed_i), so a shard is resumable and shards cannot collide."""
    manifest = load_manifest(fleet_dir)
    ov = assert_overlay_present(fleet_dir)      # §1.4 verdict must exist before any search runs
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"regret{tag}.jsonl")
    all_kids = study_set(manifest)
    kids = [k for i, k in enumerate(all_kids) if i % n_shards == shard]
    if not kids:
        raise FreezeViolation("study set is empty (all kernels are H or R?)")
    done = _done_set(out_path)
    feats, motif_excl = ({}, {})
    if "motifbo" in arms:
        # LOKO sources span the WHOLE study set, never just this shard — a sharded Motif that
        # only saw its own shard's kernels would be a different (weaker) algorithm per shard.
        feats, motif_excl = motif_sources(fleet_dir, manifest, all_kids,
                                          os.path.join(out_dir, f"motif_exclusions{tag}.jsonl"))
    tables = {}          # verified-frozen tables, loaded lazily and kept (≈130 × 1728 tuples)
    best_walks = {}
    fout = open(out_path, "a")

    def tbl_of(kid):
        if kid not in tables:
            tables[kid] = load_frozen(fleet_dir, manifest, kid)
            best_walks[kid] = _best_by_screen(tables[kid])
        return tables[kid]

    # SEED-MAJOR ORDER. The loop is (seed, kernel, arm), not (kernel, arm, seed), so the results on
    # disk are always a UNIFORM PREFIX of the seed schedule across every kernel. If the run is cut
    # short — by wall-clock, a kill, anything — what survives is "all kernels at seeds 0..j", which
    # is an unbiased smaller study. Kernel-major order would leave some kernels at 200 seeds and
    # others at zero, which is not a study at all, and the bias would be invisible in the row count.
    warm_cache = {}

    def _one(kid, arm, i, fout_):
        nonlocal n_rows
        hash_k = seeds.kernel_hash(kid)
        tbl = tbl_of(kid)
        alg_id = ALG[arm]

        def _algo_for(i):
            if arm == "rs":
                return lambda s, b, _sd, _i=i: algorithms.rs(s, b, seeds.seq(hash_k, alg_id, _i))
            if arm == "doe":
                return algorithms.doe
            if arm == "bo":
                return lambda s, b, _sd, _i=i: bomod.bo(s, b, _i, hash_k=hash_k,
                                                        seed_i=_i, alg_id=ALG["bo"])
            # LOKO warm-start depends only on the TARGET kernel, not on the seed — caching it turns
            # a per-seed recompute over ~128 source kernels into one per kernel.
            if kid not in warm_cache:
                src = [(sk, feats[sk], best_walks[sk] if sk in best_walks else
                        _best_by_screen(tbl_of(sk)), _gen_index(fleet_dir, sk))
                       for sk in all_kids if sk != kid and sk in feats]
                warm_cache[kid] = motif.motif_warmstart(feats[kid], src, k=8)
            ws = warm_cache[kid]
            return lambda s, b, _sd, _i=i, _ws=ws: motif.motifbo(
                s, b, _i, warmstart_configs=_ws, hash_k=hash_k, seed_i=_i,
                alg_id=ALG["motifbo"])

        si = -1 if i is None else i
        # NESTED BUDGETS: RS/BO/Motif take `budget` as a stopping condition only, so ONE trajectory
        # to max(budgets) yields every budget by prefix — exact, 5x cheaper, and it makes the
        # budgets PAIRED. DOE cannot: its design size is min(24, B-1), so a smaller budget is a
        # different design, not a truncation. Both claims are pinned by
        # test_replay.py::test_prefix_equals_independent_runs_for_stopping_condition_arms and
        # ::test_failure_path_doe_is_not_prefix_equivalent.
        if arm == "doe":
            for B in budgets:
                if (kid, arm, B, si) in done:
                    continue
                r = replay.run_algorithm(_algo_for(i), tbl, B, 0)
                fout_.write(json.dumps({"kernel_id": kid, "alg": arm, "alg_id": alg_id,
                                        "budget": B, "seed_i": si, "nested": False, **r}) + "\n")
                n_rows += 1
        else:
            todo = [B for B in budgets if (kid, arm, B, si) not in done]
            if not todo:
                return
            pref = replay.run_algorithm_prefixes(_algo_for(i), tbl, budgets, 0)
            for B in todo:
                fout_.write(json.dumps({"kernel_id": kid, "alg": arm, "alg_id": alg_id,
                                        "budget": B, "seed_i": si,
                                        "nested": True, **pref[B]}) + "\n")
                n_rows += 1
        fout_.flush()

    n_rows = 0
    for arm in [a for a in arms if a == "doe"]:              # deterministic: one pass, no seeds
        for kid in kids:
            _one(kid, arm, None, fout)
    for i in range(n_seeds):
        for kid in kids:
            for arm in [a for a in arms if a != "doe"]:
                if arm == "motifbo" and kid in motif_excl:
                    continue                                # excluded, reason ledgered (§8.4/§3.4)
                _one(kid, arm, i, fout)
        print(f"  seed {i} complete across {len(kids)} kernels ({n_rows} rows)", flush=True)
    fout.close()
    return {"rows_written": n_rows, "study_kernels": len(kids),
            "shard": f"{shard}/{n_shards}", "study_set_total": len(all_kids),
            "n_seeds": n_seeds, "arms": list(arms), "budgets": list(budgets),
            "motif_excluded": len(motif_excl),
            "rqp3_evaluable": (len(motif_excl) / max(1, len(kids))) < 0.20,
            # Provenance of the feasible space the study actually searched, so a reader never has
            # to infer whether the §1.4 correction was in force for these rows.
            "sanitizer_overlay": {"defect": ov.get("defect"),
                                  "cells": ov.get("n_cells_overlaid"),
                                  "kernels": ov.get("n_kernels_affected")}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fleet", default=os.path.join(REPO, "results", "fleet"))
    ap.add_argument("--out", default=os.path.join(REPO, "results", "study"))
    ap.add_argument("--make-manifest", action="store_true",
                    help="the P-2 freeze act (once, at CHECKPOINT P-2)")
    ap.add_argument("--make-h-manifest", action="store_true",
                    help="seal holdout H (A-7 §7; once, after the H campaign stops)")
    ap.add_argument("--arms", default="rs,doe,bo,motifbo")
    ap.add_argument("--seeds", type=int, default=N_SEEDS)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--n-shards", type=int, default=1)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    if a.make_manifest:
        out, man = make_freeze_manifest(a.fleet)
        print(f"FROZEN: {man['n_kernels']} kernels -> {out}")
        return
    if a.make_h_manifest:
        out, man = make_h_manifest(a.fleet)
        print(f"H SEALED: {man['n_kernels']} kernels {man['cells']} "
              f"provenance {man['provenance_counts']} -> {out}")
        return
    res = run_study(a.fleet, a.out, n_seeds=a.seeds, arms=tuple(a.arms.split(",")),
                    shard=a.shard, n_shards=a.n_shards, tag=a.tag)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
