"""Generator v2 (Amendment A-2d/g/h/i) — diversity-mandated fleet kernel generator.

Emits self-contained kernels DESIGNED toward a taxonomy-v2 regime via measured, real compiler
mechanisms — never asserted-by-construction: each fleet kernel's regime membership is its OWN
full-table v2 classification (rider R3; intended-vs-measured goes to the P-2 confusion table).

DIVERSITY MANDATE (A-2d): ≥ 6 distinct TEMPLATES per confirmatory regime; a template is a distinct
mechanism (loop shape × payoff mechanism), parameterized over ranges (size tier, dtype, degree,
distribution) wide enough that measured properties spread. The anti-clone acceptance check
(anti_clone_check below; rider R2: REJECT iff ALL five |Δp| < 0.05, strict, within template)
runs AFTER a candidate's full table is measured, against previously ACCEPTED same-template
kernels; rejections are ledgered with distances and the slot re-parameterizes (≤ 3 attempts,
then the template is flagged and the slot draws a different template).

FEAS VARIANTS (rider R1): 15 of 30 kernels per regime are FEAS+ BY DESIGN, target
infeas_frac ≥ 0.30 (comfortably above the 0.25 knife-edge, rider R2):
  - trap_wrap  : a negative index reached on real iterations — wraparound=True wraps it (legal),
                 wraparound=False dereferences out-of-bounds → crash/garbage → infeasible.
                 Design infeas ≈ 1/2 (every wrap=False config). Mechanism-orthogonal to fm and to
                 bc/opt gates → usable INSIDE FM+ regimes (an fm-cliff would kill the FM wedge).
  - fm_cliff   : Kahan compensation over dynamic-range data — every fast_math=on config fails the
                 oracle. Design infeas = 1/3 (576/1728). Never combined with FM-flag templates.
Mechanism coverage stays a FLEET-level property (roadmap §3.2-1); per-kernel spec.json records the
kernel's actual mechanism set.

Measured provenance per regime (raw pointers):
  FLAT+FM   — B-family float reductions: Δ_strict 1.003–1.057, fm_ratio ≈ 3.95 (pilot_B_*).
  MID       — A-family gather-poly Δs≈1.21/IF≈.48; bcprobe histogram 1.41/.34 (pilot_A_*, ctrl).
  LEVER-SEP — csr row-gather Δs=2.016/IF=.092 (pilot_R_01); cdiv-const map ≈1.56× separable
              (probe P3, S=1.004 = additive).
  INT       — probe P1 sum64 bc×opt S=2.35/Δ16=5.29; P2 min32 S=5.17/Δ16=11.40; P4 rev64 wrap×opt
              S=1.80/Δ16=5.22; planted float-map Δs=10.18/IF=.41 (results/probes/int/, ctrl_planted).
  NULL      — pointer-chase Δ=1.045 (ctrl_flat); pava in-place Δs=1.096 (pilot_R_02).
"""
from __future__ import annotations
import json
import os

_HEADER = "# generated Phase-P v2 kernel — directives controlled by the build matrix (no in-source pins)\n"

EPS_CLONE = 0.05          # rider R2: strict < on ALL five components ⇒ clone
BOUNDARY_FLAG_TOL = 0.01  # rider R2: |stat − class threshold| ≤ 0.01 ⇒ ledger-flag


# ---------------------------------------------------------------------------
# pyx template builders — each returns Cython source; params make instances distinct.
# Every hot function is run(...); drivers below know each recipe's signature.
# ---------------------------------------------------------------------------

def _pyx_float_reduce(op, dtype_c, trap):
    """FLAT+FM: contiguous FP reduction — vectorization requires reassociation (fast-math);
    strict axis stays scalar-flat. op ∈ sum|dot|sumsq|absmax_sum|alt_sum|running_mean."""
    body = {
        "sum": "acc += a[j]",
        "dot": "acc += a[j] * b[j]",
        "sumsq": "acc += a[j] * a[j]",
        "absmax_sum": "acc += (a[j] if a[j] >= 0 else -a[j])",
        "alt_sum": "acc += a[j] if (i & 1) == 0 else -a[j]",
        "running_mean": "acc += (a[j] - acc) * inv",
    }[op]
    idx = "i - off" if trap == "trap_wrap" else "i"
    return _HEADER + f'''
import numpy as np
cimport numpy as cnp

def run({dtype_c}[::1] a, {dtype_c}[::1] b, long reps, guard):
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef {dtype_c} acc = 0.0
    cdef {dtype_c} inv = <{dtype_c}>(1.0 / n)
    cdef Py_ssize_t off = 0
    cdef Py_ssize_t j
    if guard is not None:
        off = <Py_ssize_t>guard          # trap variants pass off=1: i-off = -1 on the first lap
    for r in range(reps):
        for i in range(n):
            j = {idx}
            {body}
    return <double>acc
'''


def _pyx_mid_gather_poly(degree, trap):
    """MID: gather + short polynomial — bounds-dominated with modest vectorization payoff."""
    poly = "x"
    for k in range(degree):
        poly = f"({poly}) * x + {0.11 + 0.07 * k:.2f}"
    idx = "(idx[i] - off)" if trap == "trap_wrap" else "idx[i]"
    return _HEADER + f'''
import numpy as np
cimport numpy as cnp

def run(double[::1] a, long[::1] idx, long reps, guard):
    cdef Py_ssize_t i, r, n = idx.shape[0]
    cdef double acc = 0.0, x
    cdef Py_ssize_t off = 0
    cdef Py_ssize_t j
    if guard is not None:
        off = <Py_ssize_t>guard
    for r in range(reps):
        for i in range(n):
            j = {idx}
            x = a[j]
            acc += {poly}
    return acc
'''


def _pyx_mid_histogram(nbins_expr, trap):
    """MID: histogram scatter (bcprobe mechanism) — data-dependent write index."""
    idx = "(col[i] - off)" if trap == "trap_wrap" else "col[i]"
    return _HEADER + f'''
import numpy as np
cimport numpy as cnp

def run(long[::1] col, double[::1] s1, long reps, guard):
    cdef Py_ssize_t i, r, n = col.shape[0]
    cdef double g = 1.0
    cdef Py_ssize_t off = 0
    if guard is not None:
        off = <Py_ssize_t>guard
    for r in range(reps):
        for i in range(n):
            s1[{idx}] += g
    return s1
'''


def _pyx_mid_branchy(threshold, trap):
    """MID: data-dependent branch caps the vectorization payoff (cmov-vs-branch territory)."""
    idx = "i - off" if trap == "trap_wrap" else "i"
    return _HEADER + f'''
import numpy as np
cimport numpy as cnp

def run(double[::1] a, double[::1] out, long reps, guard):
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef double x
    cdef Py_ssize_t off = 0
    cdef Py_ssize_t j
    if guard is not None:
        off = <Py_ssize_t>guard
    for r in range(reps):
        for i in range(n):
            j = {idx}
            x = a[j]
            if x > {threshold}:
                out[j] = x * 0.5 + 1.0
            else:
                out[j] = x * x - 0.25
    return out
'''


def _pyx_mid_stencil(width, trap):
    """MID: small stencil — partial vectorization (unaligned neighbor loads). The loop stops
    width-1 short of n so the forward window a[j+width-1] stays in bounds (D9: iterating the full
    n overran the N-sized array on the tail — IndexError on every call)."""
    terms = " + ".join(f"a[j + {k}]" for k in range(width))
    idx = "i - off" if trap == "trap_wrap" else "i"
    return _HEADER + f'''
import numpy as np
cimport numpy as cnp

def run(double[::1] a, double[::1] out, long reps, guard):
    cdef Py_ssize_t i, r, n = out.shape[0]
    cdef Py_ssize_t off = 0
    cdef Py_ssize_t j
    if guard is not None:
        off = <Py_ssize_t>guard
    for r in range(reps):
        for i in range(n - {width - 1}):
            j = {idx}
            out[j] = {terms}
    return out
'''


def _pyx_mid_convert(trap):
    """MID: int→float convert + scale loop (cvt port pressure, modest opt payoff)."""
    idx = "i - off" if trap == "trap_wrap" else "i"
    return _HEADER + f'''
import numpy as np
cimport numpy as cnp

def run(long[::1] x, double[::1] out, long reps, guard):
    cdef Py_ssize_t i, r, n = x.shape[0]
    cdef Py_ssize_t off = 0
    cdef Py_ssize_t j
    if guard is not None:
        off = <Py_ssize_t>guard
    for r in range(reps):
        for i in range(n):
            j = {idx}
            out[j] = <double>x[j] * 1.0000001 + 0.5
    return out
'''


def _pyx_lever_csr(trap):
    """LEVER-SEP: csr-like row-gather reduction (measured separable, R_01 Δs=2.0/IF=.09)."""
    idx = "(cols[k] - off)" if trap == "trap_wrap" else "cols[k]"
    return _HEADER + f'''
import numpy as np
cimport numpy as cnp

def run(double[::1] data, long[::1] cols, long[::1] rowptr, double[::1] x, double[::1] y,
        long reps, guard):
    cdef Py_ssize_t i, k, r, nrows = rowptr.shape[0] - 1
    cdef double acc
    cdef Py_ssize_t off = 0
    if guard is not None:
        off = <Py_ssize_t>guard
    for r in range(reps):
        for i in range(nrows):
            acc = 0.0
            for k in range(rowptr[i], rowptr[i + 1]):
                acc += data[k] * x[{idx}]
            y[i] = acc
    return y
'''


def _pyx_lever_modconst(divisor, trap):
    """LEVER-SEP: int %-by-constant map — cdivision main effect ≈1.56× (probe P3, additive)."""
    idx = "i - off" if trap == "trap_wrap" else "i"
    return _HEADER + f'''
import numpy as np
cimport numpy as cnp

def run(long[::1] x, long[::1] out, long reps, guard):
    cdef Py_ssize_t i, r, n = x.shape[0]
    cdef Py_ssize_t off = 0
    cdef Py_ssize_t j
    if guard is not None:
        off = <Py_ssize_t>guard
    for r in range(reps):
        for i in range(n):
            j = {idx}
            out[j] = x[j] % {divisor}
    return out[n - 1]
'''


def _pyx_lever_sqrtmap(trap):
    """LEVER-SEP: sqrt map — libm-call-vs-vsqrtpd lever at opt/march."""
    idx = "i - off" if trap == "trap_wrap" else "i"
    return _HEADER + f'''
import numpy as np
cimport numpy as cnp
from libc.math cimport sqrt

def run(double[::1] a, double[::1] out, long reps, guard):
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef Py_ssize_t off = 0
    cdef Py_ssize_t j
    if guard is not None:
        off = <Py_ssize_t>guard
    for r in range(reps):
        for i in range(n):
            j = {idx}
            out[j] = sqrt(a[j] * a[j] + 1.0)
    return out
'''


def _pyx_lever_clipmap(trap):
    """LEVER-SEP: abs/clip map — cmov/maxsd lever."""
    idx = "i - off" if trap == "trap_wrap" else "i"
    return _HEADER + f'''
import numpy as np
cimport numpy as cnp

def run(double[::1] a, double[::1] out, long reps, guard):
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef double x
    cdef Py_ssize_t off = 0
    cdef Py_ssize_t j
    if guard is not None:
        off = <Py_ssize_t>guard
    for r in range(reps):
        for i in range(n):
            j = {idx}
            x = a[j]
            if x < -1.0:
                x = -1.0
            if x > 1.0:
                x = 1.0
            out[j] = x
    return out
'''


def _pyx_lever_strided(stride, trap):
    """LEVER-SEP: strided gather sum — stride defeats vectorization; bc removal is the clean lever."""
    idx = "((i * {s}) % n - off)".replace("{s}", str(stride)) if trap == "trap_wrap" \
        else "(i * {s}) % n".replace("{s}", str(stride))
    return _HEADER + f'''
import numpy as np
cimport numpy as cnp

def run(double[::1] a, long reps, guard):
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef double acc = 0.0
    cdef Py_ssize_t off = 0
    cdef Py_ssize_t j
    if guard is not None:
        off = <Py_ssize_t>guard
    for r in range(reps):
        for i in range(n):
            j = {idx}
            acc += a[j]
    return acc
'''


def _pyx_lever_axpy(trap):
    """LEVER-SEP: saxpy map — vectorizes from -O2; march width is the residual lever."""
    idx = "i - off" if trap == "trap_wrap" else "i"
    return _HEADER + f'''
import numpy as np
cimport numpy as cnp

def run(double[::1] a, double[::1] b, double[::1] out, long reps, guard):
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef Py_ssize_t off = 0
    cdef Py_ssize_t j
    if guard is not None:
        off = <Py_ssize_t>guard
    for r in range(reps):
        for i in range(n):
            j = {idx}
            out[j] = 2.5 * a[j] + b[j]
    return out
'''


def _pyx_int_reduce(op, dtype_c, trap):
    """INT: integer reduction — associative ⇒ vectorizes WITHOUT fast-math, but only bc=off ∧ -O3
    (probe P1 S=2.35, P2 S=5.17). op ∈ sum|minv|sumsq|maxv."""
    init = {"sum": "0", "sumsq": "0", "minv": "a[0]", "maxv": "a[0]"}[op]
    body = {
        "sum": "acc += a[j]",
        "sumsq": "acc += a[j] * a[j]",
        "minv": "acc = a[j] if a[j] < acc else acc",
        "maxv": "acc = a[j] if a[j] > acc else acc",
    }[op]
    idx = "i - off" if trap == "trap_wrap" else "i"
    return _HEADER + f'''
import numpy as np
cimport numpy as cnp

def run({dtype_c}[::1] a, long reps, guard):
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef {dtype_c} acc
    cdef Py_ssize_t off = 0
    cdef Py_ssize_t j
    if guard is not None:
        off = <Py_ssize_t>guard
    acc = {init}
    for r in range(reps):
        for i in range(n):
            j = {idx}
            {body}
    return <double>acc
'''


def _pyx_int_revsum(trap):
    """INT: reversed-index sum — wrap handling blocks vectorization (probe P4 S=1.80).
    NOTE: never combined with trap_wrap (the gate IS wraparound); FEAS− only."""
    assert trap is None
    return _HEADER + '''
import numpy as np
cimport numpy as cnp

def run(long[::1] a, long reps, guard):
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef long acc = 0
    cdef long g = 0
    if guard is not None:
        g = <long>guard
    for r in range(reps):
        for i in range(n):
            acc += a[n - 1 - i]
    return <double>(acc + g)
'''


def _pyx_int_hornermap(degree, dtype_c, trap):
    """INT-regime float map: Horner polynomial (planted mechanism, Δs=10.18/IF=.41) — map
    vectorization gates strictly on bc/opt×march; degree/dtype are the spread knobs."""
    poly = "0.013"
    for k in range(degree):
        poly = f"({poly}) * x + {0.11 + 0.06 * k:.2f}"
    idx = "i - off" if trap == "trap_wrap" else "i"
    return _HEADER + f'''
import numpy as np
cimport numpy as cnp

def run({dtype_c}[::1] a, {dtype_c}[::1] out, long reps, guard):
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef {dtype_c} x, p
    cdef Py_ssize_t off = 0
    cdef Py_ssize_t j
    if guard is not None:
        off = <Py_ssize_t>guard
    for r in range(reps):
        for i in range(n):
            j = {idx}
            x = a[j]
            p = <{dtype_c}>({poly})
            out[j] = p
    return out
'''


def _pyx_null_chase():
    """NULL (FLAT∧FM−): pointer chase — serial dependent loads, flat everywhere (ctrl_flat 1.045)."""
    return _HEADER + '''
import numpy as np
cimport numpy as cnp

def run(long[::1] nxt, long reps, guard):
    cdef Py_ssize_t r
    cdef long j = 0, N = reps * nxt.shape[0], g = 0
    if guard is not None:
        g = <long>guard
    for r in range(N):
        j = nxt[j]
    return <double>(j + g)
'''


def _pyx_null_inplace():
    """NULL: in-place monotone pass (pava-like, R_02 Δs=1.096) — dependent updates, latency-bound."""
    return _HEADER + '''
import numpy as np
cimport numpy as cnp

def run(double[::1] a, long reps, guard):
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef double g = 0.0
    if guard is not None:
        g = <double>guard
    for r in range(reps):
        for i in range(1, n):
            if a[i] < a[i - 1]:
                a[i] = a[i - 1]
    return a[n - 1] + g
'''


def _pyx_null_chase_payload():
    """NULL: pointer chase with a payload add — still latency-bound (payload hidden under loads)."""
    return _HEADER + '''
import numpy as np
cimport numpy as cnp

def run(long[::1] nxt, double[::1] w, long reps, guard):
    cdef Py_ssize_t r
    cdef long j = 0, N = reps * nxt.shape[0]
    cdef double acc = 0.0
    if guard is not None:
        acc = <double>guard
    for r in range(N):
        acc += w[j]
        j = nxt[j]
    return acc
'''


def _pyx_null_fpchain():
    """NULL: serial dependent FP chain — division latency chain, no ILP, no vectorization surface."""
    return _HEADER + '''
import numpy as np
cimport numpy as cnp

def run(double[::1] a, long reps, guard):
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef double acc = 1.0
    if guard is not None:
        acc = <double>guard + 1.0
    for r in range(reps):
        for i in range(n):
            acc = acc / (1.0 + acc * acc) + a[i] * 1e-9
    return acc
'''


def _fm_cliff_wrap(inner_pyx):
    """FEAS via fm-cliff: append a Kahan-compensated checksum pass whose result enters the output —
    fast_math reassociates the compensation away over dynamic-range data ⇒ oracle-fail on fm-on."""
    return inner_pyx + '''

def run_cliff(double[::1] cliff, long reps_unused, guard_unused):
    cdef Py_ssize_t i, n = cliff.shape[0]
    cdef double acc = 0.0, c = 0.0, y, t
    for i in range(n):
        y = cliff[i] - c
        t = acc + y
        c = (t - acc) - y
        acc = t
    return acc
'''


# ---------------------------------------------------------------------------
# Driver builders — REPS is the calibrate knob (harness rewrites the "REPS = " line).
# Trap variants pass guard=1 (off=1 → index −1 reached on real iterations); wraparound=True wraps
# it legally (a[-1] = last element, deterministic), wraparound=False reads out of bounds → crash/
# garbage → infeasible ≈ every wrap=False config (design infeas ≈ 0.5 ≥ 0.30, rider R1).
# fm-cliff drivers call run_cliff on dynamic-range data and fold it into the canonical output.
# ---------------------------------------------------------------------------

_DRV = '''"""Driver for {kid} — template {template}, intended {regime}{feas_note}."""
import numpy as np

N = {n}
REPS = {reps}
OUTPUT_CLASS = "{output_class}"

def make_inputs(seed):
    rng = np.random.default_rng(seed)
{inputs_body}
    return ({args})

def call(mod, inputs):
{call_body}

def canon(result):
    return np.asarray(result, dtype=np.float64).reshape(-1)
'''


def _driver(kid, template, regime, n, output_class, inputs_body, args, call_body, feas):
    note = {"trap_wrap": " (FEAS+ trap_wrap)", "fm_cliff": " (FEAS+ fm_cliff)", None: ""}[feas]
    return _DRV.format(kid=kid, template=template, regime=regime, feas_note=note, n=n, reps=200,
                       output_class=output_class, inputs_body=inputs_body, args=args,
                       call_body=call_body)


_CLIFF_INPUT = ('    cliff = np.ones(4096, dtype=np.float64) + rng.standard_normal(4096) * 1e-3\n'
                '    cliff[0] = 1e16; cliff[-1] = -1e16\n')
_CALL_PLAIN = "    return mod.run(*inputs)"
_CALL_CLIFF = ('    *core, cliff = inputs\n'
               '    r = mod.run(*core)\n'
               '    k = mod.run_cliff(cliff, 0, None)\n'
               '    return np.concatenate([np.asarray(r, dtype=np.float64).reshape(-1), [k]])')


# ---------------------------------------------------------------------------
# Template registry: regime -> [ (template_name, builder(params, trap), param_space, driver_fn,
#                                 feas_variants_allowed) ]
# param_space entries are drawn round-robin per generation index (deterministic via seeds §0.4).
# N tiers: L1 ≈ 4k, L2 ≈ 48k, L3 ≈ 600k doubles.
# ---------------------------------------------------------------------------

N_TIERS = {"L1": 4096, "L2": 49152, "L3": 589824}


def _drv_two_arrays(kid, t, regime, n, feas, params=None, extra=""):
    # D8: the array dtype MUST match the template's {dtype_c} memoryview — a float64 array into
    # float[::1] raises "Buffer dtype mismatch" on every call (fm_dot_r1 MEASURE_FAIL).
    np_dt = {"float": "float32"}.get((params or {}).get("dt"), "float64")
    if feas == "fm_cliff":
        body = (f"    a = rng.standard_normal(N).astype(np.{np_dt})\n"
                f"    b = rng.standard_normal(N).astype(np.{np_dt})\n{extra}{_CLIFF_INPUT}")
        return _driver(kid, t, regime, n, "float", body,
                       "a, b, REPS, None, cliff", _CALL_CLIFF, feas)
    g = "1" if feas == "trap_wrap" else "None"
    body = (f"    a = rng.standard_normal(N).astype(np.{np_dt})\n"
            f"    b = rng.standard_normal(N).astype(np.{np_dt})\n{extra}")
    return _driver(kid, t, regime, n, "float", body, f"a, b, REPS, {g}", _CALL_PLAIN, feas)


def _drv_map(kid, t, regime, n, feas, params=None, dtype="float64"):
    g = "1" if feas == "trap_wrap" else "None"
    if feas == "fm_cliff":
        body = (f"    a = rng.standard_normal(N).astype(np.{dtype})\n"
                f"    out = np.zeros(N, dtype=np.{dtype})\n{_CLIFF_INPUT}")
        return _driver(kid, t, regime, n, "float", body, "a, out, REPS, None, cliff",
                       _CALL_CLIFF, feas)
    body = (f"    a = rng.standard_normal(N).astype(np.{dtype})\n"
            f"    out = np.zeros(N, dtype=np.{dtype})\n")
    return _driver(kid, t, regime, n, "float", body, f"a, out, REPS, {g}", _CALL_PLAIN, feas)


def _drv_gather(kid, t, regime, n, feas, params=None):
    g = "1" if feas == "trap_wrap" else "None"
    body = ("    a = rng.standard_normal(N).astype(np.float64)\n"
            "    idx = rng.integers(0, N, size=N, dtype=np.int64)\n")
    if feas == "fm_cliff":
        return _driver(kid, t, regime, n, "float", body + _CLIFF_INPUT,
                       "a, idx, REPS, None, cliff", _CALL_CLIFF, feas)
    return _driver(kid, t, regime, n, "float", body, f"a, idx, REPS, {g}", _CALL_PLAIN, feas)


def _drv_hist(kid, t, regime, n, feas, nbins, params=None):
    g = "1" if feas == "trap_wrap" else "None"
    body = (f"    col = rng.integers(0, {nbins}, size=N, dtype=np.int64)\n"
            f"    s1 = np.zeros({nbins}, dtype=np.float64)\n")
    if feas == "fm_cliff":
        return _driver(kid, t, regime, n, "float", body + _CLIFF_INPUT,
                       "col, s1, REPS, None, cliff", _CALL_CLIFF, feas)
    return _driver(kid, t, regime, n, "float", body, f"col, s1, REPS, {g}", _CALL_PLAIN, feas)


def _drv_csr(kid, t, regime, n, feas, row_nnz, params=None):
    g = "1" if feas == "trap_wrap" else "None"
    body = (f"    nrows = N // {row_nnz}\n"
            f"    nnz = nrows * {row_nnz}\n"
            f"    data = rng.standard_normal(nnz).astype(np.float64)\n"
            f"    cols = rng.integers(0, nrows, size=nnz, dtype=np.int64)\n"
            f"    rowptr = (np.arange(nrows + 1, dtype=np.int64) * {row_nnz})\n"
            f"    x = rng.standard_normal(nrows).astype(np.float64)\n"
            f"    y = np.zeros(nrows, dtype=np.float64)\n")
    if feas == "fm_cliff":
        return _driver(kid, t, regime, n, "float", body + _CLIFF_INPUT,
                       "data, cols, rowptr, x, y, REPS, None, cliff", _CALL_CLIFF, feas)
    return _driver(kid, t, regime, n, "float", body,
                   f"data, cols, rowptr, x, y, REPS, {g}", _CALL_PLAIN, feas)


def _drv_int_array(kid, t, regime, n, feas, params=None, dtype="int64", lo=-2**40, hi=2**40):
    g = "1" if feas == "trap_wrap" else "None"
    body = f"    a = rng.integers({lo}, {hi}, size=N, dtype=np.{dtype})\n"
    return _driver(kid, t, regime, n, "int", body, f"a, REPS, {g}", _CALL_PLAIN, feas)


def _drv_int_map(kid, t, regime, n, feas, params=None, dtype="int64", lo=0, hi=2**40,
                 out_dtype=None):
    # D9: out's dtype must match the pyx out memoryview (mid_convert writes double[::1])
    out_dtype = out_dtype or dtype
    oc = "float" if out_dtype.startswith("float") else "int"
    g = "1" if feas == "trap_wrap" else "None"
    body = (f"    x = rng.integers({lo}, {hi}, size=N, dtype=np.{dtype})\n"
            f"    out = np.zeros(N, dtype=np.{out_dtype})\n")
    return _driver(kid, t, regime, n, oc, body, f"x, out, REPS, {g}", _CALL_PLAIN, feas)


def _drv_axpy(kid, t, regime, n, feas, params=None):
    # D9: lev_axpy's pyx takes THREE arrays (a, b, out) — _drv_map's two-array recipe mis-called it
    g = "1" if feas == "trap_wrap" else "None"
    body = ("    a = rng.standard_normal(N).astype(np.float64)\n"
            "    b = rng.standard_normal(N).astype(np.float64)\n"
            "    out = np.zeros(N, dtype=np.float64)\n")
    if feas == "fm_cliff":
        return _driver(kid, t, regime, n, "float", body + _CLIFF_INPUT,
                       "a, b, out, REPS, None, cliff", _CALL_CLIFF, feas)
    return _driver(kid, t, regime, n, "float", body, f"a, b, out, REPS, {g}", _CALL_PLAIN, feas)


def _drv_chase(kid, t, regime, n, feas, params=None, payload=False):
    body = (f"    perm = rng.permutation(N).astype(np.int64)\n" +
            ("    w = rng.standard_normal(N).astype(np.float64)\n" if payload else ""))
    args = ("perm, w, REPS, None" if payload else "perm, REPS, None")
    return _driver(kid, t, regime, n, "float", body, args, _CALL_PLAIN, feas)


def _drv_float_array(kid, t, regime, n, feas, params=None):
    body = "    a = rng.standard_normal(N).astype(np.float64)\n"
    return _driver(kid, t, regime, n, "float", body, "a, REPS, None", _CALL_PLAIN, feas)


# regime -> list of (template_name, pyx_fn(params, trap), driver_fn, param_space, allowed_feas)
# pyx_fn takes (params_dict, trap) ; param_space is a list of dicts cycled per index.
REGISTRY = {
    "FLAT_FM": [
        ("fm_sum", lambda p, t: _pyx_float_reduce("sum", p["dt"], t), _drv_two_arrays,
         [{"dt": "double", "n": N_TIERS["L2"]}, {"dt": "double", "n": N_TIERS["L3"]},
          {"dt": "float", "n": N_TIERS["L2"]}], ("trap_wrap",)),
        ("fm_dot", lambda p, t: _pyx_float_reduce("dot", p["dt"], t), _drv_two_arrays,
         [{"dt": "double", "n": N_TIERS["L2"]}, {"dt": "double", "n": N_TIERS["L1"]},
          {"dt": "float", "n": N_TIERS["L3"]}], ("trap_wrap",)),
        ("fm_sumsq", lambda p, t: _pyx_float_reduce("sumsq", p["dt"], t), _drv_two_arrays,
         [{"dt": "double", "n": N_TIERS["L2"]}, {"dt": "float", "n": N_TIERS["L2"]}], ("trap_wrap",)),
        ("fm_abssum", lambda p, t: _pyx_float_reduce("absmax_sum", p["dt"], t), _drv_two_arrays,
         [{"dt": "double", "n": N_TIERS["L2"]}, {"dt": "double", "n": N_TIERS["L3"]}], ("trap_wrap",)),
        ("fm_altsum", lambda p, t: _pyx_float_reduce("alt_sum", p["dt"], t), _drv_two_arrays,
         [{"dt": "double", "n": N_TIERS["L2"]}, {"dt": "float", "n": N_TIERS["L1"]}], ("trap_wrap",)),
        ("fm_runmean", lambda p, t: _pyx_float_reduce("running_mean", p["dt"], t), _drv_two_arrays,
         [{"dt": "double", "n": N_TIERS["L2"]}, {"dt": "double", "n": N_TIERS["L1"]}], ("trap_wrap",)),
    ],
    "MID": [
        ("mid_gatherpoly", lambda p, t: _pyx_mid_gather_poly(p["deg"], t), _drv_gather,
         [{"deg": 2, "n": N_TIERS["L2"]}, {"deg": 3, "n": N_TIERS["L1"]},
          {"deg": 4, "n": N_TIERS["L3"]}], ("trap_wrap", "fm_cliff")),
        ("mid_hist", lambda p, t: _pyx_mid_histogram(p["bins"], t),
         lambda kid, t, r, n, f, p=None: _drv_hist(kid, t, r, n, f, 256, params=p),
         [{"bins": 256, "n": N_TIERS["L2"]}, {"bins": 256, "n": N_TIERS["L1"]}],
         ("trap_wrap", "fm_cliff")),
        ("mid_branchy", lambda p, t: _pyx_mid_branchy(p["thr"], t), _drv_map,
         [{"thr": 0.0, "n": N_TIERS["L2"]}, {"thr": 0.8, "n": N_TIERS["L1"]},
          {"thr": -0.8, "n": N_TIERS["L3"]}], ("trap_wrap", "fm_cliff")),
        ("mid_stencil", lambda p, t: _pyx_mid_stencil(p["w"], t), _drv_map,
         [{"w": 3, "n": N_TIERS["L2"]}, {"w": 5, "n": N_TIERS["L1"]}], ("trap_wrap", "fm_cliff")),
        ("mid_convert", lambda p, t: _pyx_mid_convert(t),
         lambda kid, t, r, n, f, p=None: _drv_int_map(kid, t, r, n, f, params=p,
                                                      dtype="int64", lo=-2**30, hi=2**30,
                                                      out_dtype="float64"),
         [{"n": N_TIERS["L2"]}, {"n": N_TIERS["L3"]}], ("trap_wrap",)),
        ("mid_gatherpoly_deep", lambda p, t: _pyx_mid_gather_poly(p["deg"], t), _drv_gather,
         [{"deg": 6, "n": N_TIERS["L2"]}, {"deg": 8, "n": N_TIERS["L1"]}],
         ("trap_wrap", "fm_cliff")),
    ],
    "LEVER_SEP": [
        ("lev_csr", lambda p, t: _pyx_lever_csr(t),
         lambda kid, t, r, n, f, p=None: _drv_csr(kid, t, r, n, f, 16, params=p),
         [{"n": N_TIERS["L2"]}, {"n": N_TIERS["L3"]}], ("trap_wrap", "fm_cliff")),
        ("lev_modconst", lambda p, t: _pyx_lever_modconst(p["d"], t), _drv_int_map,
         [{"d": 7, "n": N_TIERS["L2"]}, {"d": 641, "n": N_TIERS["L1"]},
          {"d": 9973, "n": N_TIERS["L3"]}], ("trap_wrap",)),
        ("lev_sqrtmap", lambda p, t: _pyx_lever_sqrtmap(t), _drv_map,
         [{"n": N_TIERS["L2"]}, {"n": N_TIERS["L1"]}], ("trap_wrap", "fm_cliff")),
        ("lev_clipmap", lambda p, t: _pyx_lever_clipmap(t), _drv_map,
         [{"n": N_TIERS["L2"]}, {"n": N_TIERS["L3"]}], ("trap_wrap", "fm_cliff")),
        ("lev_strided", lambda p, t: _pyx_lever_strided(p["s"], t), _drv_float_array,
         [{"s": 7, "n": N_TIERS["L2"]}, {"s": 17, "n": N_TIERS["L3"]}], ()),
        ("lev_axpy", lambda p, t: _pyx_lever_axpy(t), _drv_axpy,
         [{"n": N_TIERS["L2"]}, {"n": N_TIERS["L1"]}], ("trap_wrap", "fm_cliff")),
    ],
    "INT": [
        ("int_sum64", lambda p, t: _pyx_int_reduce("sum", "long", t), _drv_int_array,
         [{"n": N_TIERS["L1"] * 2}, {"n": N_TIERS["L2"]}], ("trap_wrap",)),
        ("int_min32", lambda p, t: _pyx_int_reduce("minv", "int", t),
         lambda kid, t, r, n, f, p=None: _drv_int_array(kid, t, r, n, f, params=p,
                                                        dtype="int32", lo=-2**30, hi=2**30),
         [{"n": N_TIERS["L2"]}, {"n": N_TIERS["L1"] * 4}], ("trap_wrap",)),
        ("int_sumsq", lambda p, t: _pyx_int_reduce("sumsq", "long", t), _drv_int_array,
         [{"n": N_TIERS["L1"] * 2}, {"n": N_TIERS["L2"]}], ("trap_wrap",)),
        ("int_max32", lambda p, t: _pyx_int_reduce("maxv", "int", t),
         lambda kid, t, r, n, f, p=None: _drv_int_array(kid, t, r, n, f, params=p,
                                                        dtype="int32", lo=-2**30, hi=2**30),
         [{"n": N_TIERS["L2"]}], ("trap_wrap",)),
        ("int_revsum", lambda p, t: _pyx_int_revsum(None), _drv_int_array,
         [{"n": N_TIERS["L1"] * 2}, {"n": N_TIERS["L2"]}], ()),
        ("int_horner64", lambda p, t: _pyx_int_hornermap(p["deg"], "double", t), _drv_map,
         [{"deg": 10, "n": N_TIERS["L1"]}, {"deg": 14, "n": N_TIERS["L2"]}],
         ("trap_wrap",)),
        ("int_horner32", lambda p, t: _pyx_int_hornermap(p["deg"], "float", t),
         lambda kid, t, r, n, f, p=None: _drv_map(kid, t, r, n, f, params=p, dtype="float32"),
         [{"deg": 10, "n": N_TIERS["L1"]}, {"deg": 12, "n": N_TIERS["L2"]}], ("trap_wrap",)),
    ],
    "NULL": [
        ("null_chase", lambda p, t: _pyx_null_chase(),
         lambda kid, t, r, n, f, p=None: _drv_chase(kid, t, r, n, f, params=p),
         [{"n": 1000000}, {"n": 4000000}], ()),
        ("null_inplace", lambda p, t: _pyx_null_inplace(), _drv_float_array,
         [{"n": N_TIERS["L3"]}, {"n": N_TIERS["L2"]}], ()),
        ("null_chasepay", lambda p, t: _pyx_null_chase_payload(),
         lambda kid, t, r, n, f, p=None: _drv_chase(kid, t, r, n, f, params=p, payload=True),
         [{"n": 1000000}], ()),
        ("null_fpchain", lambda p, t: _pyx_null_fpchain(), _drv_float_array,
         [{"n": N_TIERS["L1"]}, {"n": N_TIERS["L2"]}], ()),
    ],
}

# ---------------------------------------------------------------------------
# Wave-2 registries (Amendment A-3c — SUPPLY ONLY). Producer templates only, parameter regions
# drawn from the committed wave-1 producer/non-producer analysis
# (results/fleet/template_analysis_final.json):
#   FLAT_FM_W2   — fm_sum/fm_dot/fm_sumsq restricted to dt=double (measured: double → FM+ 8/9,
#                  float → FM+ 0/6), new n values only.
#   MID_W2       — mid_hist with the bins dimension OPENED (was fixed 256) + mid_gatherpoly
#                  corridor deg 2–3 (L2-tier corridor measured MID 6/6; L1 overshoots INT,
#                  deg3/L1 undershoots FLAT).
#   LEVER_SEP_W2 — lev_csr with row_nnz OPENED (was fixed 16), lev_modconst new divisors,
#                  lev_axpy small-n (L1 3/3), int_sum64 cross-listed (measured LEVER-SEP 4/4).
# Every param point is NEW vs wave-1 spaces/uses (D8 pre-guard keys (template, params, trap)
# across waves; anti-clone keys template across waves ⇒ wave-2 is checked vs the ENTIRE fleet).
# Template names are SHARED with wave-1 deliberately so both checks see one template lineage.
# ---------------------------------------------------------------------------

REGISTRY["FLAT_FM_W2"] = [
    ("fm_sum", lambda p, t: _pyx_float_reduce("sum", p["dt"], t), _drv_two_arrays,
     [{"dt": "double", "n": 4096}, {"dt": "double", "n": 16384}, {"dt": "double", "n": 98304},
      {"dt": "double", "n": 294912}, {"dt": "double", "n": 1179648}], ("trap_wrap",)),
    ("fm_dot", lambda p, t: _pyx_float_reduce("dot", p["dt"], t), _drv_two_arrays,
     [{"dt": "double", "n": 8192}, {"dt": "double", "n": 24576}, {"dt": "double", "n": 196608},
      {"dt": "double", "n": 1179648}], ("trap_wrap",)),
    ("fm_sumsq", lambda p, t: _pyx_float_reduce("sumsq", p["dt"], t), _drv_two_arrays,
     [{"dt": "double", "n": 4096}, {"dt": "double", "n": 24576}, {"dt": "double", "n": 98304},
      {"dt": "double", "n": 589824}], ("trap_wrap",)),
]
# A-6e (A-4 resume): REORDERED, not narrowed. mid_gatherpoly leads because it is the working
# producer the resume directive names: wave-2 it accepted on 4/4 paying cycles (3 MID, 1 INT
# overshoot) with ZERO clone rejections, while mid_hist cost 6 REJECTED_CLONE cycles. mid_hist is
# KEPT as second supply on purpose — it carries 6 distinct parameter points and mid_gatherpoly
# alone would exhaust its own space against the D8 pre-guard before delivering +4. Ordering buys
# the cheap accepts first; removing mid_hist would trade a clone-rate problem for a supply problem.
REGISTRY["MID_W2"] = [
    ("mid_gatherpoly", lambda p, t: _pyx_mid_gather_poly(p["deg"], t), _drv_gather,
     [{"deg": 3, "n": 49152}, {"deg": 2, "n": 98304}, {"deg": 2, "n": 24576},
      {"deg": 3, "n": 98304}, {"deg": 3, "n": 24576}, {"deg": 2, "n": 196608}],
     ("trap_wrap", "fm_cliff")),
    ("mid_hist", lambda p, t: _pyx_mid_histogram(p["bins"], t),
     lambda kid, t, r, n, f, p=None: _drv_hist(kid, t, r, n, f, (p or {}).get("bins", 256),
                                               params=p),
     [{"bins": 512, "n": 49152}, {"bins": 1024, "n": 49152}, {"bins": 256, "n": 98304},
      {"bins": 512, "n": 24576}, {"bins": 256, "n": 24576}, {"bins": 1024, "n": 98304}],
     ("trap_wrap", "fm_cliff")),
]
# A-6 (A-4 resume): NARROWED to the proven-separable lever pool on wave-2 producer evidence.
# lev_modconst leads: it is the separable cdivision lever from the A-2e INT probe (P3, S=1.004)
# and the only template producing LEVER-SEP in BOTH waves (wave-1 4/4, wave-2 1/1). lev_csr is
# retained as the strongest wave-1 producer (6/6) even though its single wave-2 accept spilled to
# MID — a spill is a miss, not a drift to the neighbouring lever class.
# DROPPED, on measured evidence, per the resume directive:
#   lev_axpy   wave-1 4/6 but wave-2 measured INT — an INT-ward drifter.
#   int_sum64  wave-1 4/4 but INT-flavoured by construction; its wave-2 slot drifted and cost
#              1608.5 s as a CYCLE_ORPHAN for nothing. Their wave-2 behaviour is EVIDENCE for the
#              P-2 report, not roster supply.
# Supply-only narrowing: no threshold, cell definition or cap changes. See PREREG §12 A-6.
REGISTRY["LEVER_SEP_W2"] = [
    ("lev_modconst", lambda p, t: _pyx_lever_modconst(p["d"], t), _drv_int_map,
     [{"d": 3, "n": 49152}, {"d": 21, "n": 98304}, {"d": 65521, "n": 4096},
      {"d": 127, "n": 589824}], ("trap_wrap",)),
    ("lev_csr", lambda p, t: _pyx_lever_csr(t),
     lambda kid, t, r, n, f, p=None: _drv_csr(kid, t, r, n, f, (p or {}).get("nnz", 16),
                                              params=p),
     [{"nnz": 4, "n": 49152}, {"nnz": 64, "n": 49152}, {"nnz": 8, "n": 589824},
      {"nnz": 32, "n": 4096}], ("trap_wrap", "fm_cliff")),
]

# ---------------------------------------------------------------------------
# Holdout-H extended registries (Amendment A-7 — SUPPLY ONLY, ONE-SHOT).
#
# Read ONLY by run_fleet --stage holdout. The wave-1 and wave-2 registries above are deliberately
# left byte-untouched: process_slot derives a candidate's params as pspace[(gi + k) % len(pspace)],
# so appending to an existing pspace would silently repoint already-FROZEN slot labels to different
# parameters. New keys keep every frozen (kid → params) map exact.
#
# WHY THIS EXISTS (measured, not projected): the training campaign consumed 169 distinct
# (template, params, feas_variant) keys. H draws on the same finite registries — H_START_INDEX only
# renumbers slots, it does not refill the pool. Fresh supply for H at the blocker was
# MID 14 · LEVER-SEP 13 · FLAT+FM 5 · INT 0, so H's ≥3-per-confirmatory-cell ruling was
# structurally unsatisfiable for INT. H's first slot proved it by exhausting on nine consecutive
# PARAMS_DUPLICATE skips at ZERO measurement cost.
#
# Every point below is FIXED BY THE AMENDMENT before any generation (A-7b anti-sculpting): no
# iterating parameters against measured Δ/IF/greedy-gap. The only filters remain anti-clone (vs the
# ENTIRE fleet and every accepted H kernel) and the MEASURED full-table classification (A-2i).
# Ranges are chosen by the committed producer evidence FOR CELL-TARGETING ONLY. All 102 candidate
# (template, params, trap) keys were verified fresh against the survival ledger: 0 collisions.
# Spec + rationale: PREREG §12 A-7 · results/fleet/A7_H_SUPPLY_AMENDMENT.md
# ---------------------------------------------------------------------------

# dt=double ONLY — dt is the decisive measured axis (double → FM+ 8/9 in wave-1; float → FM+ 0/6).
# Ordered by wave-2 accept rate: fm_sumsq 4/4, fm_sum 3/3, fm_dot 2/3. Every n INTERPOLATES inside
# the demonstrated 4,096–1,179,648 FLAT+FM corridor — the extrapolation is in the parameter grid,
# not in the regime.
REGISTRY["FLAT_FM_H"] = [
    ("fm_sumsq", lambda p, t: _pyx_float_reduce("sumsq", p["dt"], t), _drv_two_arrays,
     [{"dt": "double", "n": 8192}, {"dt": "double", "n": 16384}, {"dt": "double", "n": 65536},
      {"dt": "double", "n": 147456}, {"dt": "double", "n": 393216},
      {"dt": "double", "n": 786432}], ("trap_wrap",)),
    ("fm_sum", lambda p, t: _pyx_float_reduce("sum", p["dt"], t), _drv_two_arrays,
     [{"dt": "double", "n": 8192}, {"dt": "double", "n": 24576}, {"dt": "double", "n": 65536},
      {"dt": "double", "n": 147456}, {"dt": "double", "n": 393216},
      {"dt": "double", "n": 786432}], ("trap_wrap",)),
    ("fm_dot", lambda p, t: _pyx_float_reduce("dot", p["dt"], t), _drv_two_arrays,
     [{"dt": "double", "n": 12288}, {"dt": "double", "n": 16384}, {"dt": "double", "n": 65536},
      {"dt": "double", "n": 98304}, {"dt": "double", "n": 294912},
      {"dt": "double", "n": 786432}], ("trap_wrap",)),
]

# Ordered by MEASURED wave-1 INT rate: int_horner32 3/3 · int_horner64 2/2 · int_revsum 2/2 ·
# int_sumsq 2/3 · int_min32 2/3 · int_max32 1/2. int_sum64 is DROPPED — it measured LEVER-SEP on
# all 4 of its wave-1 kernels and INT on none, exactly the A-6b "evidence, not roster" logic.
# For the horner pair DEGREE is opened as well as n: degree is the demonstrated interaction driver
# (both measured degrees produced INT at both the L1 and L2 tiers). n stays inside the demonstrated
# 4,096–49,152 corridor, widened only to 98,304 — larger n drives toward memory-bound, which
# FLATTENS landscapes and would work against the INT target, so the extension does not chase it.
REGISTRY["INT_H"] = [
    ("int_horner32", lambda p, t: _pyx_int_hornermap(p["deg"], "float", t),
     lambda kid, t, r, n, f, p=None: _drv_map(kid, t, r, n, f, params=p, dtype="float32"),
     [{"deg": 8, "n": 8192}, {"deg": 14, "n": 16384}, {"deg": 16, "n": 24576},
      {"deg": 12, "n": 8192}, {"deg": 10, "n": 24576}, {"deg": 18, "n": 49152}],
     ("trap_wrap",)),
    ("int_horner64", lambda p, t: _pyx_int_hornermap(p["deg"], "double", t), _drv_map,
     [{"deg": 12, "n": 8192}, {"deg": 16, "n": 16384}, {"deg": 18, "n": 24576},
      {"deg": 8, "n": 49152}, {"deg": 20, "n": 24576}, {"deg": 10, "n": 16384}],
     ("trap_wrap",)),
    ("int_revsum", lambda p, t: _pyx_int_revsum(None), _drv_int_array,
     [{"n": 4096}, {"n": 16384}, {"n": 24576}, {"n": 32768}, {"n": 65536}, {"n": 98304}], ()),
    ("int_sumsq", lambda p, t: _pyx_int_reduce("sumsq", "long", t), _drv_int_array,
     [{"n": 4096}, {"n": 16384}, {"n": 24576}, {"n": 32768}, {"n": 65536}, {"n": 98304}],
     ("trap_wrap",)),
    ("int_min32", lambda p, t: _pyx_int_reduce("minv", "int", t),
     lambda kid, t, r, n, f, p=None: _drv_int_array(kid, t, r, n, f, params=p,
                                                    dtype="int32", lo=-2**30, hi=2**30),
     [{"n": 4096}, {"n": 8192}, {"n": 24576}, {"n": 32768}, {"n": 65536}, {"n": 98304}],
     ("trap_wrap",)),
    ("int_max32", lambda p, t: _pyx_int_reduce("maxv", "int", t),
     lambda kid, t, r, n, f, p=None: _drv_int_array(kid, t, r, n, f, params=p,
                                                    dtype="int32", lo=-2**30, hi=2**30),
     [{"n": 4096}, {"n": 8192}, {"n": 16384}, {"n": 24576}, {"n": 32768}, {"n": 65536}],
     ("trap_wrap",)),
]

# A-7e: PERMANENT provenance labels on every H kernel. H-ext = drawn from an A-7 extended registry
# (a parameterization outside the training distribution's grid); H-orig = drawn from a pre-A-7
# registry. RQ-P2 acceptance at P4 is reported SLICED by this field, never only pooled, so routing
# degradation on the mildly out-of-distribution kernels stays visible.
H_EXT_REGIMES = ("FLAT_FM_H", "INT_H")


def provenance(regime):
    """A-7e: H-ext iff the slot draws on an A-7 extended registry."""
    return "H-ext" if regime in H_EXT_REGIMES else "H-orig"


REGIME_INTENDED = {"FLAT_FM": "FLAT+FM", "MID": "MID", "LEVER_SEP": "LEVER-SEP", "INT": "INT",
                   "NULL": "FLAT",
                   # A-3: wave-2 supply keys target the same intended regimes
                   "FLAT_FM_W2": "FLAT+FM", "MID_W2": "MID", "LEVER_SEP_W2": "LEVER-SEP",
                   # A-7: H extended supply keys target the same intended regimes
                   "FLAT_FM_H": "FLAT+FM", "INT_H": "INT"}


def roster(regime, count, feas_balance=True, start_index=6):
    """Deterministic fleet roster for one regime: `count` slots cycling the ≥6 templates, FEAS+
    on alternating slots (rider R1 15/15 when count=30), parameters cycled per template use.
    Returns [(kid, template_name, params, trap, gen_index)]. Generation indices follow PREREG §2
    (6..35 fleet). Slots whose template forbids FEAS variants swap the FEAS+ assignment with the
    next FEAS-capable slot (balance preserved; swap recorded in the spec)."""
    tmpl = REGISTRY[regime]
    out, uses = [], {t[0]: 0 for t in tmpl}
    feas_flags = []
    for i in range(count):
        feas_flags.append(feas_balance and (i % 2 == 0))
    # swap forward where the template can't take a FEAS variant
    order = [tmpl[i % len(tmpl)] for i in range(count)]
    for i in range(count):
        if feas_flags[i] and not order[i][4]:
            for k in range(i + 1, count):
                if order[k][4] and not feas_flags[k]:
                    feas_flags[i], feas_flags[k] = feas_flags[k], feas_flags[i]
                    break
    for i in range(count):
        name, pyx_fn, drv_fn, pspace, feas_ok = order[i]
        params = pspace[uses[name] % len(pspace)]
        uses[name] += 1
        trap = None
        if feas_flags[i] and feas_ok:
            trap = feas_ok[uses[name] % len(feas_ok)]
        kid = f"fleet_{regime}_{start_index + i:02d}_{name}"
        out.append((kid, name, params, trap, start_index + i))
    return out


def emit_kernel(out_root, regime, kid, template_name, params, trap, gen_index, holdout=False):
    """Write kernel.pyx + driver.py + spec.json for one roster slot.

    holdout (A-7e): H kernels carry a permanent `provenance` label (H-orig / H-ext) and are
    wave-EXEMPT (A-3b: "H and R are wave-exempt"), so `wave` is written null rather than inheriting
    the supplying registry's wave — an H kernel drawn from MID_W2 is not a wave-2 training kernel,
    and an auditor slicing on `wave` must not be able to mistake it for one."""
    tmpl = {t[0]: t for t in REGISTRY[regime]}[template_name]
    _name, pyx_fn, drv_fn, _ps, _feas_ok = tmpl
    src = pyx_fn(params, trap)
    if trap == "fm_cliff":
        src = _fm_cliff_wrap(src)
    kdir = os.path.join(out_root, kid)
    os.makedirs(kdir, exist_ok=True)
    with open(os.path.join(kdir, "kernel.pyx"), "w") as f:
        f.write(src)
    n = params.get("n", N_TIERS["L2"])
    with open(os.path.join(kdir, "driver.py"), "w") as f:
        f.write(drv_fn(kid, template_name, REGIME_INTENDED[regime], n, trap, params))
    spec = {
        "kernel_id": kid, "generator": "v2 (A-2d)", "intended_regime": REGIME_INTENDED[regime],
        # campaign.finalize's spec contract (inherited pilot schema) requires intended_class;
        # for v2 kernels it mirrors the intended regime (measured membership still rules, A-2i)
        "intended_class": REGIME_INTENDED[regime],
        "regime_key": regime, "template": template_name, "params": params,
        "feas_variant": trap, "feas_design_note": (
            None if trap is None else
            ("trap_wrap: wraparound=False configs dereference index -1 out of bounds -> "
             "infeasible by design (~0.5 >= 0.30)" if trap == "trap_wrap" else
             "fm_cliff: fast_math=on configs fail the Kahan checksum oracle (~0.333 >= 0.30)")),
        "generation_index": gen_index,
        "gen_seed_key": ["gen2", regime, gen_index],
        "membership_rule": "v2 class from OWN full table (A-2i; intended label is design intent only)",
        # A-3b: wave label on every kernel (1 = original campaign, 2 = A-3 top-up supply).
        # A-7e: H is wave-exempt — null, never the supplying registry's wave.
        "wave": None if holdout else (2 if regime.endswith("_W2") else 1),
    }
    if holdout:
        spec["provenance"] = provenance(regime)          # A-7e, permanent
        spec["provenance_rule"] = ("H-ext = drawn from an A-7 extended registry (parameterization "
                                   "outside the training grid); H-orig = pre-A-7 registry. RQ-P2 "
                                   "acceptance at P4 is reported SLICED by this field.")
    with open(os.path.join(kdir, "spec.json"), "w") as f:
        json.dump(spec, f, indent=2)
    return kdir


# ---------------------------------------------------------------------------
# Anti-clone acceptance (rider R2) + property spread — operate on MEASURED full-table properties.
# ---------------------------------------------------------------------------

def property_vector(delta_all, delta_strict, if_strict, infeas_frac, greedy_gap):
    import math
    return (math.log(delta_all), math.log(delta_strict),
            (if_strict if if_strict is not None else 0.0), infeas_frac, greedy_gap)


def anti_clone_check(candidate_p, accepted_ps):
    """REJECT iff an accepted same-template kernel has ALL five |Δ| < EPS_CLONE (strict).
    Returns (accept: bool, min_distance_profile: list of the closest kernel's |Δ| components)."""
    closest = None
    for q in accepted_ps:
        d = [abs(a - b) for a, b in zip(candidate_p, q)]
        if closest is None or max(d) < max(closest):
            closest = d
        if all(x < EPS_CLONE for x in d):
            return False, d
    return True, closest


def boundary_flags(delta_strict, if_strict, fm_ratio, n_infeasible, n_total):
    """Rider R2: report any statistic within ±BOUNDARY_FLAG_TOL of a class threshold."""
    flags = []
    for name, val, thr in (("delta_strict~1.10", delta_strict, 1.10),
                           ("delta_strict~1.5", delta_strict, 1.5),
                           ("if_strict~0.25", if_strict, 0.25),
                           ("fm_ratio~1.5", fm_ratio, 1.5),
                           ("infeas_frac~0.25", (n_infeasible / n_total), 0.25)):
        if val is not None and abs(val - thr) <= BOUNDARY_FLAG_TOL:
            flags.append(name)
    return flags


def spread_report(records):
    """P-2 diversity deliverable: per regime, min/median/max of each property component + the
    minimum pairwise max-|Δ| within each template (must be ≥ EPS_CLONE for accepted kernels)."""
    import statistics as st
    by_regime = {}
    for r in records:
        by_regime.setdefault(r["regime_key"], []).append(r)
    rep = {}
    for reg, rs in by_regime.items():
        comps = list(zip(*(r["p"] for r in rs)))
        rep[reg] = {
            "n": len(rs),
            "templates": sorted({r["template"] for r in rs}),
            "per_component_min_med_max": [
                [min(c), st.median(c), max(c)] for c in comps],
            "min_within_template_distance": _min_within_template(rs),
        }
    return rep


def _min_within_template(rs):
    best = None
    for i in range(len(rs)):
        for j in range(i + 1, len(rs)):
            if rs[i]["template"] != rs[j]["template"]:
                continue
            d = max(abs(a - b) for a, b in zip(rs[i]["p"], rs[j]["p"]))
            best = d if best is None or d < best else best
    return best
