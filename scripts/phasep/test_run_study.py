"""run_study TDD — freeze guard (structural), hash verification, LOKO set, checkpoint resume,
DOE single-trajectory, motif hard-fail exclusion. Fixture tables only; no measured data."""
import json
import os
import tempfile
import pytest
import run_study as rst
import theta

_PYX = "def run(a):\n    cdef int i\n    for i in range(3):\n        a[i] = a[i] * 2\n    return a\n"


def _mk_kernel(fleet, kid, opt_cid=200, opt=40.0, with_pyx=True):
    kdir = os.path.join(fleet, kid)
    os.makedirs(kdir, exist_ok=True)
    with open(os.path.join(kdir, "table.jsonl"), "w") as f:
        for c in range(theta.N_CONFIGS):
            m = 40.0 if c == opt_cid else (110.0 if c == theta.REFERENCE_ID else 90.0 + (c % 40))
            f.write(json.dumps({"config_id": c, "feasible": 1, "reason": "ok",
                                "screen": {"median_ns": m}}) + "\n")
    json.dump({"v2_class": "MID"}, open(os.path.join(kdir, "class_v2.json"), "w"))
    kd = os.path.join(fleet, "_kernels", kid)
    os.makedirs(kd, exist_ok=True)
    if with_pyx:
        open(os.path.join(kd, "kernel.pyx"), "w").write(_PYX)
    json.dump({"generation_index": int(kid.split("_")[-1]) if kid.split("_")[-1].isdigit() else 0},
              open(os.path.join(kd, "spec.json"), "w"))


def _mk_fleet(td, kids, holdout=(), dataset_r=(), rejected=()):
    fleet = os.path.join(td, "fleet")
    os.makedirs(fleet, exist_ok=True)
    with open(os.path.join(fleet, "fleet_ledger.jsonl"), "w") as f:
        for kid in kids:
            _mk_kernel(fleet, kid, with_pyx=(kid not in rejected))
            f.write(json.dumps({"kernel_id": kid, "status": "ACCEPTED",
                                "holdout": kid in holdout,
                                "dataset": "R" if kid in dataset_r else "synthetic"}) + "\n")
        f.write(json.dumps({"kernel_id": "ghost", "status": "REJECTED_CLONE"}) + "\n")
    # D23/A-9: run_study refuses to search a fleet whose §1.4 sanitizer verdict was never computed.
    # A fixture fleet has no trap kernels, so its overlay is legitimately EMPTY — but the file must
    # exist, because "no file" means "the gate never ran", not "nothing to correct".
    json.dump({"schema": "phasep-sanitizer-infeasible-overlay-v1", "defect": "D23",
               "n_cells_overlaid": 0, "n_kernels_affected": 0, "kernels": {}},
              open(os.path.join(fleet, "SANITIZER_INFEASIBLE_OVERLAY.json"), "w"))
    return fleet


def test_freeze_guard_refuses_without_manifest():
    with tempfile.TemporaryDirectory() as td:
        fleet = _mk_fleet(td, ["k_1"])
        with pytest.raises(SystemExit, match="FREEZE GUARD"):
            rst.run_study(fleet, os.path.join(td, "study"), budgets=(8,), n_seeds=1, arms=("rs",))


def test_manifest_freeze_is_immutable_and_excludes_rejected():
    with tempfile.TemporaryDirectory() as td:
        fleet = _mk_fleet(td, ["k_1", "k_2"])
        _p, man = rst.make_freeze_manifest(fleet)
        assert set(man["kernels"]) == {"k_1", "k_2"}       # REJECTED 'ghost' never frozen
        with pytest.raises(SystemExit, match="immutable"):
            rst.make_freeze_manifest(fleet)


def test_hash_verify_catches_tamper():
    with tempfile.TemporaryDirectory() as td:
        fleet = _mk_fleet(td, ["k_1"])
        rst.make_freeze_manifest(fleet)
        with open(os.path.join(fleet, "k_1", "table.jsonl"), "a") as f:
            f.write("\n")                                   # post-freeze tamper
        with pytest.raises(SystemExit, match="hash mismatch"):
            rst.run_study(fleet, os.path.join(td, "study"), budgets=(8,), n_seeds=1, arms=("rs",))


def test_study_set_excludes_holdout_and_R():
    with tempfile.TemporaryDirectory() as td:
        fleet = _mk_fleet(td, ["k_1", "k_2", "h_1", "r_1"], holdout=("h_1",), dataset_r=("r_1",))
        rst.make_freeze_manifest(fleet)
        man = rst.load_manifest(fleet)
        assert rst.study_set(man) == ["k_1", "k_2"]


def test_rows_doe_single_trajectory_and_resume():
    with tempfile.TemporaryDirectory() as td:
        fleet = _mk_fleet(td, ["k_1", "k_2"])
        rst.make_freeze_manifest(fleet)
        out = os.path.join(td, "study")
        res = rst.run_study(fleet, out, budgets=(8,), n_seeds=2, arms=("rs", "doe"))
        rows = [json.loads(l) for l in open(os.path.join(out, "regret.jsonl"))]
        assert res["rows_written"] == len(rows) == 2 * (2 + 1)      # 2 kernels × (rs×2 + doe×1)
        assert all(r["cheated"] is False and r["regret"] is not None for r in rows)
        res2 = rst.run_study(fleet, out, budgets=(8,), n_seeds=2, arms=("rs", "doe"))
        assert res2["rows_written"] == 0                             # checkpoint resume: no dupes


def test_motif_hard_fail_excluded_with_reason_and_loko_runs():
    with tempfile.TemporaryDirectory() as td:
        fleet = _mk_fleet(td, ["k_1", "k_2", "k_3"], rejected=("k_3",))  # k_3 has no kernel.pyx
        rst.make_freeze_manifest(fleet)
        out = os.path.join(td, "study")
        res = rst.run_study(fleet, out, budgets=(8,), n_seeds=1, arms=("motifbo",))
        rows = [json.loads(l) for l in open(os.path.join(out, "regret.jsonl"))]
        assert {r["kernel_id"] for r in rows} == {"k_1", "k_2"}      # k_3 excluded, others ran
        excl = [json.loads(l) for l in open(os.path.join(out, "motif_exclusions.jsonl"))]
        assert excl and excl[0]["kernel_id"] == "k_3" and "cannot read" in excl[0]["reason"]
        assert res["motif_excluded"] == 1 and res["rqp3_evaluable"] is False  # 1/3 ≥ 20%


def test_bo_arm_runs_at_init_budget():
    with tempfile.TemporaryDirectory() as td:
        fleet = _mk_fleet(td, ["k_1"])
        rst.make_freeze_manifest(fleet)
        out = os.path.join(td, "study")
        res = rst.run_study(fleet, out, budgets=(8,), n_seeds=1, arms=("bo",))
        rows = [json.loads(l) for l in open(os.path.join(out, "regret.jsonl"))]
        assert res["rows_written"] == 1 and rows[0]["budget_used"] <= 8


def test_freeze_manifest_records_classifier_provenance(tmp_path):
    """The freeze is write-once: anything absent here can never be added.

    class_v2.json contents are only interpretable against the classifier that produced them, and
    E4 changed that classifier's flag_FEAS predicate at the freeze boundary — so the manifest must
    pin the classifier hash and its predicates, not only the data hashes.
    """
    import json as _json, os as _os
    fleet = tmp_path / "fleet"
    (fleet / "k1").mkdir(parents=True)
    (fleet / "k1" / "table.jsonl").write_text('{"config_id": 0}\n')
    (fleet / "k1" / "class_v2.json").write_text('{"v2_class": "FLAT"}')
    (fleet / "fleet_ledger.jsonl").write_text(_json.dumps({
        "status": "ACCEPTED", "kernel_id": "k1", "template": "t", "measured_v2": "FLAT",
        "wave": 2, "flag_FM": True, "flag_FEAS": False}) + "\n")
    out, man = rst.make_freeze_manifest(str(fleet))
    c = man["classifier"]
    assert c["source"] == "scripts/phasep/a2_reclassify.py"
    assert len(c["sha256"]) == 64
    assert "4 * n_infeasible >= n_total" in c["flag_FEAS_predicate"], "E4 predicate must be pinned"
    assert "FLAT+FM" in man["cell_rule"]
    assert man["kernels"]["k1"]["wave"] == 2, "A-3b wave label must be frozen with the dataset"
    # write-once
    import pytest as _pytest
    with _pytest.raises(rst.FreezeViolation):
        rst.make_freeze_manifest(str(fleet))


def test_study_refuses_when_the_sanitizer_verdict_was_never_computed():
    """D23: the oracle alone passed 1,296 configs that read out of bounds. A study run against a
    fleet whose §1.4 verdict has not been computed would optimize into them, so it is refused
    structurally — the same posture as the freeze guard, for the same reason."""
    with tempfile.TemporaryDirectory() as td:
        fleet = _mk_fleet(td, ["k_1"])
        rst.make_freeze_manifest(fleet)
        os.remove(os.path.join(fleet, "SANITIZER_INFEASIBLE_OVERLAY.json"))
        with pytest.raises(SystemExit, match="SANITIZER GUARD"):
            rst.run_study(fleet, os.path.join(td, "study"), budgets=(8,), n_seeds=1, arms=("rs",))


def test_overlay_reaches_the_loaded_table():
    """Non-vacuity for the guard above: a NON-empty overlay must actually strip the config from the
    table run_study hands to the arms, not merely satisfy a file-exists check."""
    with tempfile.TemporaryDirectory() as td:
        fleet = _mk_fleet(td, ["k_1"])
        _p, man = rst.make_freeze_manifest(fleet)
        assert rst.load_frozen(fleet, man, "k_1")[200][0] is True     # the fixture optimum
        json.dump({"schema": "phasep-sanitizer-infeasible-overlay-v1", "defect": "D23",
                   "n_cells_overlaid": 1, "n_kernels_affected": 1, "kernels": {"k_1": [200]}},
                  open(os.path.join(fleet, "SANITIZER_INFEASIBLE_OVERLAY.json"), "w"))
        rst._OVERLAY_CACHE.clear()
        tbl = rst.load_frozen(fleet, man, "k_1")
        assert tbl[200][0] is False and tbl[200][2] == "sanitizer_oob"
        rst._OVERLAY_CACHE.clear()


def test_resume_never_recomputes_a_completed_row():
    """The whole value of a checkpointed study is that an interrupted run is BANKABLE. If resume
    silently recomputed, a 36-hour rerun would discover it at the end — so it is pinned here.
    Verified live against the real shard 0 (3,500 rows): 0 recomputed, file byte-unchanged."""
    with tempfile.TemporaryDirectory() as td:
        fleet = _mk_fleet(td, ["k_1", "k_2"])
        rst.make_freeze_manifest(fleet)
        out = os.path.join(td, "study")
        first = rst.run_study(fleet, out, budgets=(8,), n_seeds=2, arms=("rs",))
        assert first["rows_written"] > 0
        path = os.path.join(out, "regret.jsonl")
        rows_before = open(path).read()

        second = rst.run_study(fleet, out, budgets=(8,), n_seeds=2, arms=("rs",))
        assert second["rows_written"] == 0, "resume recomputed completed work"
        assert open(path).read() == rows_before, "resume mutated the committed rows"


def test_failure_path_extending_the_seed_schedule_does_add_rows():
    """Non-vacuity: resume must skip what is DONE without also refusing new work. Without this,
    a resume that skipped everything unconditionally would pass the test above."""
    with tempfile.TemporaryDirectory() as td:
        fleet = _mk_fleet(td, ["k_1"])
        rst.make_freeze_manifest(fleet)
        out = os.path.join(td, "study")
        rst.run_study(fleet, out, budgets=(8,), n_seeds=2, arms=("rs",))
        more = rst.run_study(fleet, out, budgets=(8,), n_seeds=4, arms=("rs",))
        assert more["rows_written"] > 0, "extending the seed schedule produced no new work"


def test_seed_major_order_leaves_a_uniform_prefix():
    """An interrupted run must leave ALL kernels at seeds 0..j, not some kernels finished and
    others untouched — otherwise the survivors are a biased subset and the row count hides it."""
    with tempfile.TemporaryDirectory() as td:
        fleet = _mk_fleet(td, ["k_1", "k_2", "k_3"])
        rst.make_freeze_manifest(fleet)
        out = os.path.join(td, "study")
        rst.run_study(fleet, out, budgets=(8,), n_seeds=3, arms=("rs",))
        rows = [json.loads(l) for l in open(os.path.join(out, "regret.jsonl"))]
        by_seed = {}
        for r in rows:
            by_seed.setdefault(r["seed_i"], set()).add(r["kernel_id"])
        # every seed that appears at all covers every kernel
        for s, ks in by_seed.items():
            assert len(ks) == 3, f"seed {s} covers only {sorted(ks)} — not a uniform prefix"


def test_resume_index_spans_all_shards_so_the_study_is_reshardable():
    """A row is done regardless of which shard wrote it. If the index read only its own file,
    changing --n-shards would orphan every existing row and recompute work already on disk —
    a silent 36-hour waste. This makes the shard count a free parameter."""
    with tempfile.TemporaryDirectory() as td:
        fleet = _mk_fleet(td, ["k_1", "k_2", "k_3", "k_4"])
        rst.make_freeze_manifest(fleet)
        out = os.path.join(td, "study")
        # write it as 2 shards ...
        for sh in (0, 1):
            rst.run_study(fleet, out, budgets=(8,), n_seeds=2, arms=("rs",),
                          shard=sh, n_shards=2, tag=f"_a{sh}")
        total = sum(sum(1 for _ in open(os.path.join(out, f"regret_a{sh}.jsonl")))
                    for sh in (0, 1))
        assert total > 0
        # ... then re-run the SAME work as 4 shards under new tags: nothing may be recomputed
        wrote = 0
        for sh in range(4):
            wrote += rst.run_study(fleet, out, budgets=(8,), n_seeds=2, arms=("rs",),
                                   shard=sh, n_shards=4, tag=f"_b{sh}")["rows_written"]
        assert wrote == 0, f"re-sharding recomputed {wrote} rows that were already on disk"
