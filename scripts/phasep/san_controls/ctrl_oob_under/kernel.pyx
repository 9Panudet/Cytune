# POSITIVE CONTROL #2 — an UNDER-read, matching the direction of the defect actually audited.
#
# ctrl_oob plants an OVER-read (a[n..n+15]); the D23 defect is an UNDER-read (a[-1], because a
# typed memoryview with wraparound=False does not translate a negative index). The
# validation-auditor noted that the instrument was therefore validated for the direction it was
# used in only by the INT_14/INT_16 readings, not by a control of its own. This closes that: it
# plants the exact shape of the real defect, so a rig that detects it is demonstrably sensitive to
# the LEFT redzone and not only the right.
#
# Never built by the campaign — reachable only via `sanitizer_spot_audit.py --controls`.

def run(double[::1] a, long reps):
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef double acc = 0.0
    cdef Py_ssize_t j
    for r in range(reps):
        for i in range(n):
            j = i - 1                  # <-- planted: j == -1 on the first lap, reads BEFORE a[0]
            acc += a[j]
    return acc
