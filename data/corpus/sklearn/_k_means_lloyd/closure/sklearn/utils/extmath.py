# Vendored-closure helper (Step 1.1.1) — FAITHFUL MINIMAL impl of sklearn.utils.extmath.row_norms.
#
# _k_means_lloyd.pyx and _k_means_common.pyx do `from ..utils.extmath import row_norms` at module
# scope (runtime Python import). Only row_norms is needed by the closure. The heavyweight upstream
# extmath.py pulls array-api dispatch, sparsefuncs_fast.csr_row_norms, validation, etc. — none of
# which the closure import requires — so we vendor only row_norms.
#
# Faithfulness: upstream numpy path is `np.einsum("ij,ij->i", X, X)` then optional sqrt; the sparse
# path is the per-row sum of squares of the CSR data (== upstream csr_row_norms). Both reproduced
# exactly here. No input validation (upstream row_norms also performs none).
import numpy as np
from scipy import sparse


def row_norms(X, squared=False):
    """Row-wise (squared) Euclidean norm of X.

    Equivalent to np.sqrt((X * X).sum(axis=1)); supports dense and CSR-sparse X.
    """
    if sparse.issparse(X):
        X = X.tocsr()
        # per-row sum of squares of the CSR data == upstream csr_row_norms
        data_sq = np.asarray(X.data) ** 2
        dtype = X.data.dtype if X.data.size else np.float64
        norms = np.zeros(X.shape[0], dtype=dtype)
        for i in range(X.shape[0]):
            start, end = X.indptr[i], X.indptr[i + 1]
            norms[i] = data_sq[start:end].sum()
        if not squared:
            norms = np.sqrt(norms)
    else:
        X = np.asarray(X)
        norms = np.einsum("ij,ij->i", X, X)
        if not squared:
            norms = np.sqrt(norms)
    return norms
