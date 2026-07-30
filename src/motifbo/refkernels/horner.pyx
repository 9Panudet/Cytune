# cython: language_level=3
"""Numeric-loop I-1 reference kernel (Step 0.5.3-R): elementwise degree-11 Horner
polynomial evaluation. Replaces PAVA as the numeric-loop reference because PAVA's
pooling is sequential/division-bound and structurally cannot clear the §0.3 1.5x
numeric margin (debug-mantra: STEP_0.5.3_i1_gate_RED.log; finding preserved in
results/characterization/).

Each out[i] = horner(x[i], c) is INDEPENDENT, so the outer loop vectorises under
-O3 -march=native WITHOUT reassociation (no -ffast-math needed); the per-element
Horner chain is 11 FMAs under -ffp-contract=fast. The >=1.5x known-good-vs-known-bad
headroom is therefore derivable a priori from AVX2 vectorisation + FMA + boundscheck
removal, robust to the I-3 oracle (the only good/bad difference is FMA rounding).

`c` must have length >= 12 (degree-11 polynomial = 12 coefficients). Directives are
NOT set here — the build config decides them (the experiment).
"""


def kernel(double[::1] x, double[::1] c, double[::1] out):
    cdef Py_ssize_t i, n = x.shape[0]
    cdef int j
    cdef double xi, acc
    for i in range(n):
        xi = x[i]
        acc = c[0]
        for j in range(1, 12):          # constant bound -> GCC unrolls; outer i-loop vectorises
            acc = acc * xi + c[j]
        out[i] = acc
    return None
