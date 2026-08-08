"""Main-effects fit + predicted-best ranking — the product's half of the study's `algorithms.py`.

TRIMMED, NOT REWRITTEN. The study module also defines `rs`, `doe`, `_designs`, `_ref_best` and
`_upd`, all of which take a `SealedTable` (the replay harness's frozen-table interface). The
product never has one: `cytune` measures live and drives its own rounds, which is exactly what
`cytune/plan.py`'s docstring explains. Vendoring them would put ~70 unreachable lines into the
package and, worse, would drag `_designs`' `../../results/prereg/` fallback in with them — a
product module naming a study path, which `test_cytune_architecture.py` forbids.

So this file keeps the three definitions `plan.py` calls and drops the rest. The bodies below are
character-for-character the study's. `test_cytune_vendor.py::test_vendored_functions_match_the_
study_source` compares each one's source text against `scripts/phasep/algorithms.py` and fails on
any divergence, so "trimmed" cannot quietly become "edited".
"""
from __future__ import annotations

import numpy as np
import theta


# ------------------------------------------------------------------ DOE (§8.2)
def _ridge_fit(X, y, lam=1.0):
    """Ridge on z-scored nonzero-variance dummies (intercept unpenalized). Returns beta in X-space."""
    n, p = X.shape
    mu = X.mean(0); sd = X.std(0)
    scale = np.where(sd > 0, sd, 1.0)
    Z = (X - mu) / scale
    Z[:, 0] = 1.0                                   # keep intercept column as 1
    P = np.eye(p); P[0, 0] = 0.0                    # do not penalize intercept
    b = np.linalg.solve(Z.T @ Z + lam * P, Z.T @ y)
    # map z-space beta back to raw design space so predict uses theta.design_matrix directly
    beta = np.zeros(p)
    beta[1:] = b[1:] / scale[1:]
    beta[0] = b[0] - np.sum(b[1:] * mu[1:] / scale[1:])
    return beta


def _fit(obs_ids, obs_logm):
    X = theta.design_matrix(obs_ids)
    y = np.asarray(obs_logm, float)
    keep = [0] + [k for k in range(1, X.shape[1]) if 0 < X[:, k].sum() < X.shape[0]]
    Xr = X[:, keep]
    use_ols = len(obs_ids) >= 16 and np.linalg.matrix_rank(Xr) == Xr.shape[1]
    beta = np.zeros(X.shape[1])
    if use_ols:
        br, *_ = np.linalg.lstsq(Xr, y, rcond=1e-12)
    else:
        br = _ridge_fit(Xr, y, 1.0)
    for pos, kc in enumerate(keep):
        beta[kc] = br[pos]
    return beta, use_ols


def _pred_rank(beta):
    pred = theta.design_matrix(range(theta.N_CONFIGS)) @ beta
    return sorted(range(theta.N_CONFIGS), key=lambda c: (pred[c], c)), pred
