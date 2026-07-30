"""Motif extractor hard-fail contract (§0.6/§5.5) + LOKO warm-start + motifbo fallback."""
import os
import numpy as np
import pytest
import theta
import generate
import motif
import replay


def test_hard_fail_missing_file():
    with pytest.raises(motif.MotifExtractionError):
        motif.extract_features("/nonexistent/kernel.pyx")


def test_hard_fail_degenerate(tmp_path):
    p = tmp_path / "empty.pyx"
    p.write_text("# only a comment\n\n")
    with pytest.raises(motif.MotifExtractionError):
        motif.extract_features(str(p))


def test_extract_real_kernel_nonzero(tmp_path):
    kdir = generate.generate_kernel(str(tmp_path), "k_A", "A", "A", 0, 1000, 10)
    feat = motif.extract_features(os.path.join(kdir, "kernel.pyx"))
    v = motif.feature_vector(feat)
    assert np.any(v > 0)
    assert feat["n_for"] > 0 and feat["n_index"] > 0 and feat["n_cdef"] > 0


def test_warmstart_deterministic_and_bounded(tmp_path):
    # three source kernels with distinct feature vectors + their best feasible configs
    def mk(name, fam):
        kd = generate.generate_kernel(str(tmp_path), name, fam, fam, 0, 1000, 10)
        return motif.extract_features(os.path.join(kd, "kernel.pyx"))
    fa, fb, fc = mk("A1", "A"), mk("B1", "B"), mk("C1", "C")
    sources = [("A1", fa, [100, 200]), ("B1", fb, [300]), ("C1", fc, [400, 500])]
    target = fa
    w1 = motif.motif_warmstart(target, sources, k=8)
    w2 = motif.motif_warmstart(target, sources, k=8)
    assert w1 == w2 and len(w1) <= 8 and len(set(w1)) == len(w1)


def test_motifbo_fallback_no_prior():
    tbl = {c: (c % 5 != 0, (90.0 + c % 40 if c % 5 != 0 else None), "ok") for c in range(theta.N_CONFIGS)}
    tbl[theta.REFERENCE_ID] = (True, 110.0, "ok")
    r = replay.run_algorithm(lambda s, b, seed: motif.motifbo(s, b, seed, warmstart_configs=None), tbl, 16, 2)
    assert r["cheated"] is False and r["best_ns"] is not None and r["budget_used"] <= 16


def test_motifbo_with_warmstart_respects_budget():
    tbl = {c: (c % 5 != 0, (90.0 + c % 40 if c % 5 != 0 else None), "ok") for c in range(theta.N_CONFIGS)}
    tbl[theta.REFERENCE_ID] = (True, 110.0, "ok")
    ws = [10, 20, 30, 40, 50, 60, 70, 80]
    r = replay.run_algorithm(lambda s, b, seed: motif.motifbo(s, b, seed, warmstart_configs=ws), tbl, 16, 2)
    assert r["best_ns"] is not None and r["budget_used"] <= 16
