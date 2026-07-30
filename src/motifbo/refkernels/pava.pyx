# cython: language_level=3
"""Reference kernel (b) — numeric-loop path: PAVA isotonic regression (Step 0.5.1,
used from 0.2.4 on). Pool-adjacent-violators pass structured after sklearn's
_inplace_contiguous_isotonic_regression.

The kernel COPIES the pristine inputs into work arrays itself (inside the timed
region, deliberately): PAVA pools in place, so without the copy rep 2+ would see
already-monotone data and do trivial work. The copy is part of the kernel's cost,
identical every rep. Directives deliberately NOT set here (build config decides).
"""


def kernel(double[::1] y_src, double[::1] w_src,
           double[::1] y, double[::1] w, long long[::1] target):
    cdef Py_ssize_t n = y_src.shape[0]
    cdef Py_ssize_t i, j, k
    cdef double prev_y, sum_wy, sum_w

    for i in range(n):                      # fresh work state, every rep
        y[i] = y_src[i]
        w[i] = w_src[i]
        target[i] = i

    i = 0
    while i < n:
        k = target[i] + 1
        if k == n:
            break
        if y[i] < y[k]:
            i = k
            continue
        sum_wy = w[i] * y[i]
        sum_w = w[i]
        while True:                          # pool the decreasing run
            prev_y = y[k]
            sum_wy += w[k] * y[k]
            sum_w += w[k]
            k = target[k] + 1
            if k == n or prev_y < y[k]:
                y[i] = sum_wy / sum_w
                w[i] = sum_w
                target[i] = k - 1
                target[k - 1] = i
                if i > 0:
                    i = target[i - 1]        # back-pool if new violation appeared
                break

    i = 0                                    # expand pooled values
    while i < n:
        k = target[i] + 1
        for j in range(i + 1, k):
            y[j] = y[i]
        i = k
    return None
