"""§8.4-conformance TDD for the warm-start fixes (S-only z-score, reference exclusion,
generation-index ties, motifbo fill-to-8 incl. seed-randoms — bo-math note (b))."""
import numpy as np
import theta
import bo as bomod
import motif
import replay


def _feat(**kw):
    f = {k: 0.0 for k in list(motif._PATTERNS) + ["n_lines"]}
    f.update(kw)
    return f


def test_standardize_fit_on_S_only():
    # DISCRIMINATING: an extreme target must not shift S's mu/sd. With S = two points symmetric
    # around 0 on one feature, z_S must be ±1 regardless of the target's magnitude.
    S = np.array([[1.0, 5.0], [3.0, 5.0]])
    for target in (np.array([2.0, 5.0]), np.array([1e6, 5.0])):
        zs, zt, keep = motif._standardize_S(S, target)
        assert np.allclose(zs[:, 0], [-1.0, 1.0])          # unchanged by the target (S-only fit)
        assert list(keep) == [True, False]                 # zero-variance feature dropped over S
    zs, zt, _ = motif._standardize_S(S, np.array([2.0, 5.0]))
    assert np.allclose(zt, [0.0])                          # target transformed with S's mu/sd


def test_warmstart_never_hands_out_the_reference():
    # §8.4: "not already in the init set (including the reference)" — a source whose best config
    # IS the reference must yield its second-best instead.
    src = [("k1", _feat(n_for=1.0, n_mul=2.0), [theta.REFERENCE_ID, 7], 1)]
    init = motif.motif_warmstart(_feat(n_for=1.0, n_mul=2.0), src, k=8)
    assert theta.REFERENCE_ID not in init and init[0] == 7


def test_warmstart_tie_break_by_generation_index():
    # two sources with IDENTICAL features (cosine ties): ascending gen_index must win
    f = _feat(n_for=2.0, n_add=3.0)
    src = [("z_kernel", f, [11], 1), ("a_kernel", f, [22], 2)]
    init = motif.motif_warmstart(f, src, k=1)
    assert init == [11]                                    # gen_index 1 beats 2 despite 'a_'<'z_'


def _fake_table():
    tbl = {}
    for c in range(theta.N_CONFIGS):
        tbl[c] = (True, 90.0 + (c % 40), "ok")
    tbl[theta.REFERENCE_ID] = (True, 110.0, "ok")
    return tbl


def test_motifbo_fills_partial_warmstart_to_8():
    # bo-math note (b): with a 3-config warm start, motifbo must complete the init to 8 slots via
    # the §8.3 default order (ref free, expert, known-bad, seed-randoms) BEFORE proposing.
    tbl = _fake_table()
    sealed = replay.SealedTable(tbl)
    best = motif.motifbo(sealed, budget=8, seed=5, warmstart_configs=[3, 5, 9])
    assert best is not None
    q = sealed.queried_ids
    assert {3, 5, 9} <= q                                  # the warm slots were queried
    assert theta.id_of(bomod.EXPERT) in q                  # fill reached the §8.3 order
    assert sealed.budget_used == 8                         # exactly the 8-slot init budget
