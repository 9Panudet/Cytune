"""A-2 harness TDD: N1 rig-fingerprint stamp, config_set ids:, INT-probe design validity."""
import os
import campaign
import theta
import run_probe_int as probe


def test_config_set_ids_sorted_dedup():
    assert campaign.config_set("ids:5,3,3,7") == [3, 5, 7]


def test_config_set_ids_range_checked():
    try:
        campaign.config_set(f"ids:{theta.N_CONFIGS}")
        assert False, "out-of-range id accepted"
    except AssertionError as e:
        assert "out of range" in str(e)


def test_rig_stamp_from_env():
    os.environ["RIG_FINGERPRINT"] = "no_turbo=1 gov_cpu3=performance test"
    try:
        assert campaign._rig() == "no_turbo=1 gov_cpu3=performance test"
    finally:
        del os.environ["RIG_FINGERPRINT"]
    assert campaign._rig() == "UNGATED"   # rows written outside measure_wrap are marked, not silent


def test_probe_designs_valid_strict_16():
    for name, c in probe.CANDIDATES.items():
        f, g0, g1 = c["gate"]
        ids16, ids17 = probe.design(f, g0, g1)
        assert len(ids16) == 16 and len(set(ids16)) == 16, name
        assert set(ids17) == set(ids16) | {theta.REFERENCE_ID}, name
        gi = list(theta.FACTOR_NAMES).index(f)
        oi = list(theta.FACTOR_NAMES).index("opt_level")
        n_g1 = sum(1 for i in ids16 if theta.config_of(i)[gi] == g1)
        n_o3 = sum(1 for i in ids16 if theta.config_of(i)[oi] == "-O3")
        assert n_g1 == 8 and n_o3 == 8, name                     # balanced 2^4
        for i in ids16:
            assert theta.config_of(i)[8] == ("off", "off"), name  # STRICT by construction


def test_probe_kill_criterion_constants_pinned():
    # the pre-registered bars are load-bearing; a silent edit must fail a test
    assert probe.DELTA_BAR == 1.3 and probe.S_BAR == 1.15
