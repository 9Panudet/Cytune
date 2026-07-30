"""Build the committed D-optimal designs over Θ (PREREG §8.2 / §9.2).

Kernel-independent. Emits results/prereg/doe_designs_theta.json with the primary DOE screen sizes
N_d ∈ {7,15,24} (= min(24,B-1) for B ∈ {8,16,≥32}) and the 16-point router probe. Each is a
D-optimal exact design on the §0.1 full-rank 13-parameter main-effects coding, built by Fedorov
exchange on the ε-regularized criterion det(XᵀX + εI), ε=1e-6 (so supersaturated N_d<13 is
well-defined). 50 seeded restarts, keep max log-det; ties broken by lexicographically-lowest
sorted config_id tuple. Auditors recompute from this script + theta.py.

Delta formula (Cook & Nachtsheim 1980): for M = XᵀX + εI with inverse Minv, swapping design point
i out and candidate j in multiplies det by 1 + (d_j - d_i) + (d_i·d_j - d_ij²), where
d_a = f_aᵀ Minv f_a and d_ij = f_iᵀ Minv f_j. Holds for any invertible M (matrix determinant
lemma), including the εI-regularized one.
"""
from __future__ import annotations
import json
import sys
import numpy as np
import theta
import seeds

EPS = 1e-6
TOL = 1e-10
RESTARTS = 50
P = theta.N_PARAMS  # 13
XALL = theta.design_matrix(range(theta.N_CONFIGS))  # (1728, 13)


def _fedorov_once(Nd, rng, max_iter=2000):
    n = XALL.shape[0]
    D = rng.choice(n, size=Nd, replace=False)
    for _ in range(max_iter):
        Xd = XALL[D]
        M = Xd.T @ Xd + EPS * np.eye(P)
        Minv = np.linalg.inv(M)
        d_all = np.einsum("ij,jk,ik->i", XALL, Minv, XALL)       # (n,)  f_aᵀ Minv f_a
        d_i = d_all[D]                                           # (Nd,)
        d_ij = (XALL[D] @ Minv) @ XALL.T                         # (Nd, n)
        ratio = 1.0 + (d_all[None, :] - d_i[:, None]) + (d_i[:, None] * d_all[None, :] - d_ij ** 2)
        ratio[:, D] = -np.inf                                    # j must be outside the design
        flat = int(np.argmax(ratio))
        i_star, j_star = divmod(flat, n)
        if ratio[i_star, j_star] <= 1.0 + TOL:
            break
        D[i_star] = j_star
    Xd = XALL[D]
    _, logdet = np.linalg.slogdet(Xd.T @ Xd + EPS * np.eye(P))
    return sorted(int(c) for c in D), float(logdet)


def build_design(Nd, key):
    master = seeds.seq(*key)
    children = master.spawn(RESTARTS)
    best = None  # (logdet, sorted_config_ids)
    for child in children:
        ids, logdet = _fedorov_once(Nd, np.random.default_rng(child))
        cand = (logdet, ids)
        if best is None or logdet > best[0] + 1e-9 or (abs(logdet - best[0]) <= 1e-9 and ids < best[1]):
            best = cand
    logdet, ids = best
    X = theta.design_matrix(ids)
    rank = int(np.linalg.matrix_rank(X))
    return {"N_d": Nd, "key": list(key), "config_ids": ids, "logdet": logdet,
            "rank": rank, "full_rank": rank == min(Nd, P)}


def main(out_path):
    designs = {}
    for Nd in (7, 15, 24):
        designs[f"doe_{Nd}"] = build_design(Nd, ("doe", Nd))
    designs["probe_16"] = build_design(16, ("probe", 16))
    doc = {
        "schema": "phasep-doe-designs-v1",
        "eps": EPS, "restarts": RESTARTS, "n_params": P, "n_candidates": theta.N_CONFIGS,
        "criterion": "D-optimal, det(X'X + eps*I), Fedorov single-best-swap exchange",
        "designs": designs,
    }
    with open(out_path, "w") as f:
        json.dump(doc, f, indent=2)
    # invariants
    for name, d in designs.items():
        assert len(d["config_ids"]) == d["N_d"]
        assert len(set(d["config_ids"])) == d["N_d"], f"{name} has duplicate configs"
        if d["N_d"] >= P:
            assert d["rank"] == P, f"{name} rank {d['rank']} != {P}"
        print(f"  {name}: N_d={d['N_d']} rank={d['rank']} logdet={d['logdet']:.4f}")
    print("build_doe_designs: OK ->", out_path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/out/doe_designs_theta.json")
