# POSITIVE CONTROL for the Stage-B sanitizer spot audit — this kernel is DELIBERATELY BROKEN.
#
# `run` reads a[n] .. a[n+15], i.e. 16 doubles past the end of the buffer. With boundscheck ON
# Cython raises IndexError before the read; with boundscheck OFF the read happens and ASan must
# report a heap-buffer-overflow. If the audit reports this kernel CLEAN at the checks-off corners,
# the instrument is blind and no clean reading from it means anything.
#
# It is never built by the campaign: it lives outside results/fleet/_kernels and is reachable only
# via `sanitizer_spot_audit.py --controls`.

def run(double[::1] a, long reps):
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef double acc = 0.0
    for r in range(reps):
        for i in range(n + 16):        # <-- planted: 16 elements past the end
            acc += a[i]
    return acc
