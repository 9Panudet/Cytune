# NEGATIVE CONTROL for the Stage-B sanitizer spot audit — deliberately ORDINARY.
#
# Same shape as ctrl_oob but with correct bounds. It must read CLEAN at every corner. A rig that
# reports on this one is over-triggering (e.g. picking up a CPython teardown artifact as a
# finding), and its reports on real kernels could not be trusted either.

def run(double[::1] a, long reps):
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef double acc = 0.0
    for r in range(reps):
        for i in range(n):
            acc += a[i]
    return acc
