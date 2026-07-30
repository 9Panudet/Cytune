"""Θ enumerator tests — config_id ↔ Appendix A, coding full-rank, neighborhood symmetric."""
import itertools
import numpy as np
import theta


def test_count_and_bijection():
    assert theta.N_CONFIGS == 1728
    assert len(theta._CONFIG_LIST) == 1728
    assert all(theta.id_of(theta.config_of(i)) == i for i in range(1728))


def test_matches_appendix_a():
    """config_id over the 9-factor composite == Appendix A's 10-dim tuple with conditional collapse."""
    ten = []
    for bc in (True, False):
        for wa in (True, False):
            for cd in (True, False):
                for ic in (True, False):
                    for nc in (True, False):
                        for opt in ("-O1", "-O2", "-O3"):
                            for march in ("x86-64", "native"):
                                for fun in ("omit", "on", "off"):
                                    for fm in ("off", "on"):
                                        ffps = ("off", "fast") if fm == "off" else ("NA",)
                                        for ffp in ffps:
                                            ten.append((bc, wa, cd, ic, nc, opt, march, fun, (fm, ffp)))
    assert ten == theta._CONFIG_LIST


def test_design_full_rank():
    X = theta.design_matrix(range(1728))
    assert X.shape == (1728, 13)
    assert np.linalg.matrix_rank(X) == 13


def test_neighbors_symmetric_size12():
    for cid in range(0, 1728, 137):  # sample
        nb = theta.neighbors(cid)
        assert len(nb) == 12
        assert len(set(nb)) == 12
        for n in nb:
            assert cid in theta.neighbors(n)


def test_reference_and_flags():
    assert theta.config_of(theta.REFERENCE_ID) == theta.REFERENCE
    dirs, opt, ffp, lang = theta.build_flags(theta.REFERENCE)
    assert "boundscheck=True" in dirs and "cdivision=False" in dirs
    assert opt == "-O2 -march=x86-64" and ffp == "off" and lang == "c"
    # a fast-math config builds with -ffast-math and ffp=fast (moot)
    fm_cfg = (False, False, True, False, False, "-O3", "native", "on", ("on", "NA"))
    d2, o2, f2, _ = theta.build_flags(fm_cfg)
    assert "-ffast-math" in o2 and "-funroll-loops" in o2 and f2 == "fast"


def test_safety_class_and_directive_combo():
    # 64 distinct safety classes, 32 directive combos over Θ
    assert len({theta.safety_class(c) for c in theta.all_configs()}) == 64
    assert len({theta.directive_combo(c) for c in theta.all_configs()}) == 32
