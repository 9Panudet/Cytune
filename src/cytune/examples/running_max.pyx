# A fresh toy kernel written for the cytune v0 smoke test (2026-07-25).
#
# Deliberately NOT drawn from any dataset: it is not a generator v2 template (fm_*, mid_*, lev_*,
# int_*, null_*), not a pilot kernel, and not an R anchor. A decaying running maximum with a
# data-dependent branch and a serial loop-carried dependency — chosen because it exercises the
# branch/bounds-check directives and float arithmetic without resembling anything the study
# measured.
#
# Contract: run(a, reps) -> float64 array of the same length as `a`.

import numpy as np


def run(double[::1] a, long reps):
    cdef Py_ssize_t n = a.shape[0]
    cdef Py_ssize_t i, r
    cdef double cur

    out = np.empty(n, dtype=np.float64)
    cdef double[::1] o = out

    for r in range(reps):
        cur = a[0]
        for i in range(n):
            if a[i] > cur:
                cur = a[i]
            else:
                cur = cur * 0.999 + a[i] * 0.001
            o[i] = cur
    return out
