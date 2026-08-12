# Vendored-closure helper stub — NOT the upstream sklearn/utils/extmath.py.
#
# Step 1.1.1 closure-walk rule 5: `_k_means_elkan.pyx` and `_k_means_common.pyx` both run, at
# module-import time, `from ..utils.extmath import row_norms`. The upstream extmath.py drags in a
# heavyweight cascade (_param_validation, deprecation, _array_api, sparsefuncs_fast, validation,
# get_namespace, ...) that is irrelevant to the elkan kernel. Per the directive we provide a FAITHFUL
# minimal `row_norms` using only numpy / scipy.sparse (both present in the image), preserving upstream
# semantics for the numpy-namespace path that the kernel actually exercises.
#
# Upstream row_norms (scikit-learn 1.5.2, sklearn/utils/extmath.py): for a numpy array it computes
# np.einsum("ij,ij->i", X, X) (== row-wise squared L2 norm), sqrt'd unless squared=True; for a sparse
# matrix it tocsr()'s and calls csr_row_norms (== row-wise squared L2 norm over CSR data), sqrt'd unless
# squared. This stub reproduces both, computing the sparse squared norm directly from the CSR data via
# numpy (mathematically identical to csr_row_norms) instead of re-vendoring sparsefuncs_fast.
import numpy as np
from scipy import sparse


def row_norms(X, squared=False):
    """Row-wise (squared) Euclidean norm of X. Faithful minimal vendored stub (see header)."""
    if sparse.issparse(X):
        X = X.tocsr()
        data = np.asarray(X.data)
        indptr = np.asarray(X.indptr)
        sq = data * data
        # row-wise sum of squared CSR data == csr_row_norms(X)
        norms = np.add.reduceat(
            np.concatenate([sq, [0.0]]),
            indptr[:-1],
        )[: X.shape[0]].astype(data.dtype, copy=False)
        # reduceat mishandles empty rows (indptr[i] == indptr[i+1]); zero them explicitly.
        empty = indptr[1:] == indptr[:-1]
        if empty.any():
            norms = norms.copy()
            norms[empty] = 0.0
        if not squared:
            norms = np.sqrt(norms)
    else:
        X = np.asarray(X)
        norms = np.einsum("ij,ij->i", X, X)
        if not squared:
            norms = np.sqrt(norms)
    return norms
