# cython: language_level=3
"""Reference kernel (a) — raw-pointer path: CSR row scaling (Step 0.5.1, used from
0.2.4 on). Modeled on sklearn's inplace_csr_row_scale hot loop: per row, scale the
nnz slice data[indptr[i]:indptr[i+1]].

`passes` must be EVEN: passes alternate multiply / divide by the same factor, so the
data returns to its original values (modulo FP rounding) after every call — rep k
does bit-identical work to rep 0 (timing consistency across the K reps).
Directives deliberately NOT set here: the build config decides them (that is the
experiment); under the pilot reference config all checks stay on.
"""


def kernel(double[::1] data, long long[::1] indptr, double[::1] row_factor,
           int passes):
    cdef Py_ssize_t i, j, nrows
    cdef int p
    cdef double f
    nrows = row_factor.shape[0]
    if passes % 2 != 0:
        raise ValueError("passes must be even (multiply/divide pairs)")
    for p in range(passes):
        for i in range(nrows):
            f = row_factor[i] if p % 2 == 0 else 1.0 / row_factor[i]
            for j in range(indptr[i], indptr[i + 1]):
                data[j] *= f
    return None
