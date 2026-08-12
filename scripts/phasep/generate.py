"""Kernel generator (PREREG §9.1, roadmap §3.2/§3.3).

Emits self-contained single-module Cython kernels DESIGNED toward a landscape class via REAL
compiler mechanisms (never asserted-by-construction — the measured class is decided later by
classify.py). Each kernel dir gets: kernel.pyx, driver.py, spec.json. Determinism: inputs come
from a committed integer seed via a fixed recipe; the harness regenerates them per-rep (D6).

Families (design intent):
  A  streaming_gather  — bounds-dominated gather/reduce; boundscheck removal is a clean SEPARABLE
                         lever (the real-code finding). Expect low interaction.
  B  vector_reduce     — contiguous FP reduction; boundscheck INHIBITS auto-vectorization, so the
                         payoff appears only under bc=off × -O3 × march=native → bc×opt INTERACTION.
  C  compensated_cliff — order-sensitive (compensated) reduction: -ffast-math reassociates and breaks
                         the result → every fast_math config is INFEASIBLE (feasibility-cliff islands
                         shaping a deceptive feasible landscape), roadmap §3.3-C.
Controls (instruments, never fleet members):
  planted  — known ~2× boundscheck lever, separable (must measure Δ_all≥1.6, bc top effect).
  flat     — register-only arithmetic, no array indexing (must measure Δ_all≤1.1, IF<0.10).

Directive-mechanism coverage is a FLEET-LEVEL property (roadmap §3.2-1: "no directive may be
trivially dead across the whole fleet"), not a per-kernel one. Per family:
  A / planted : boundscheck (a[j]), wraparound (idx<0), cdivision (%m), nonecheck (Optional arg),
                initializedcheck (typed memoryview), FP loop.
  B           : boundscheck (a[i]/b[i]), initializedcheck, nonecheck (Optional `scale`), FP loop,
                fast_math/vectorization (contiguous FMA reduction) — INTENTIONALLY no wraparound/
                cdivision (a negative index or modulo in the hot loop would defeat the vectorization
                the family exists to probe; those two directives are covered by A/C/planted).
  C           : boundscheck (a[i]), initializedcheck, nonecheck (Optional `comp`), FP loop,
                fast_math (the compensation-elimination cliff) — wraparound/cdivision covered elsewhere.
The per-kernel spec.json records that kernel's actual mechanism set (not a blanket claim).
"""
from __future__ import annotations
import json
import os

# ---------------------------------------------------------------------------
# Cython source templates. Directive values are supplied EXTERNALLY via `cython -X ...`
# (the harness controls Θ); no in-source `# cython:` pins (β policy).
# Every template's hot function is `run(...)`; the driver knows its argument recipe.
# ---------------------------------------------------------------------------

_HEADER = "# generated Phase-P kernel — directives controlled by the build matrix (no in-source pins)\n"

FAMILY_A = _HEADER + '''
import numpy as np
cimport numpy as cnp

def run(double[::1] a, long[::1] idx, long reps, wrap):
    # gather/reduce: indexing (boundscheck), idx may be negative (wraparound),
    # a modulo folds indices (cdivision), `wrap` is an Optional None-typed guard (nonecheck).
    cdef Py_ssize_t i, r
    cdef Py_ssize_t n = idx.shape[0]
    cdef Py_ssize_t m = a.shape[0]
    cdef double acc = 0.0
    cdef long j, off = 0
    if wrap is not None:
        off = <long>wrap
    for r in range(reps):
        for i in range(n):
            j = (idx[i] + off) % m          # cdivision; wraparound if negative
            acc += a[j] * a[j]              # boundscheck on a[]
    return acc
'''

FAMILY_B = _HEADER + '''
import numpy as np
cimport numpy as cnp

def run(double[::1] a, double[::1] b, long reps, scale):
    # contiguous FP reduction: boundscheck on a[i]/b[i] inhibits vectorization; bc=off × -O3 ×
    # march=native lets it FMA-vectorize -> bc×opt interaction. scale: Optional None (nonecheck).
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef double acc = 0.0, s = 1.0
    if scale is not None:
        s = <double>scale
    for r in range(reps):
        for i in range(n):
            acc += a[i] * b[i] * s          # vectorizable multiply-add
    return acc
'''

FAMILY_C = _HEADER + '''
import numpy as np
cimport numpy as cnp

def run(double[::1] a, long reps, comp):
    # Kahan-compensated sum over DYNAMIC-RANGE data (a large +/-1e16 spike straddling many 1.0's).
    # Strict IEEE (fast_math=off): compensation preserves the small terms -> acc ~ (#small values).
    # -ffast-math reassociates `(t-acc)-y` to 0, killing the compensation -> naive sum LOSES every
    # small term under the spike -> acc ~ 0, a ~O(1) RELATIVE error >> tolerance => fast_math configs
    # are INFEASIBLE (feasibility-cliff islands, roadmap §3.3-C). boundscheck on a[i]; comp Optional
    # None -> nonecheck; initializedcheck on the typed memoryview.
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef double acc = 0.0, c = 0.0, y, t
    cdef int use_comp = 1
    if comp is not None:
        use_comp = <int>comp
    for r in range(reps):
        acc = 0.0; c = 0.0
        for i in range(n):
            if use_comp:
                y = a[i] - c
                t = acc + y
                c = (t - acc) - y                 # compensation — algebraically 0, killed by fast-math
                acc = t
            else:
                acc += a[i]
    return acc
'''

CONTROL_PLANTED = _HEADER + '''
import numpy as np
cimport numpy as cnp

def run(double[::1] a, double[::1] out, long reps, guard):
    # PLANTED VECTORIZATION lever (Amendment A-1a): a COMPUTE-BOUND ELEMENTWISE ~12-term Horner
    # polynomial over L1-resident arrays. High arithmetic intensity per load/store makes it
    # compute-bound; being elementwise (NO reduction) it auto-vectorizes at -O2/-O3 (and -O3 enables
    # FMA), while -O1 stays scalar -> opt_level (-O1 scalar vs -O3 SIMD-FMA) is the LARGEST main
    # effect, with -O3 faster than -O1 (the pre-stated sign). march (SSE2 vs AVX2 width) is a smaller
    # secondary effect; boundscheck is negligible (Cython3/GCC vectorize through the check on a
    # monotonic index). guard Optional None -> nonecheck; typed memoryviews -> initializedcheck.
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef double x, p, s = 1.0
    if guard is not None:
        s = <double>guard
    for r in range(reps):
        for i in range(n):
            x = a[i]
            p = 0.013
            p = p * x + 0.11
            p = p * x + 0.29
            p = p * x + 0.37
            p = p * x + 0.53
            p = p * x + 0.61
            p = p * x + 0.71
            p = p * x + 0.83
            p = p * x + 0.97
            p = p * x + 1.09
            p = p * x + 1.13
            p = p * x + 1.27
            out[i] = p * s
    return out
'''

CONTROL_FLAT = _HEADER + '''
import numpy as np
cimport numpy as cnp

def run(long[::1] nxt, long reps, guard):
    # KNOWN-FLAT: POINTER CHASE over a random permutation -> j = nxt[j] is a SERIAL dependent-load
    # chain, memory-latency-bound. There is NO floating point (fast_math irrelevant), NO reduction or
    # vectorizable compute (opt/march cannot reorder dependent loads), and the bounds check on nxt[j]
    # is hidden by the ~100-cycle load latency -> flat across EVERY directive & flag. (A float sum is
    # NOT flat: -O3+native+fast_math vectorizes the reduction ~3x — the measured defect this replaces.)
    # guard Optional None -> nonecheck; nxt[::1] -> initializedcheck.
    cdef Py_ssize_t r
    cdef long j = 0, N = reps * nxt.shape[0], g = 0
    if guard is not None:
        g = <long>guard
    for r in range(N):
        j = nxt[j]
    return <double>(j + g)
'''

CONTROL_BCPROBE = _HEADER + '''
import numpy as np
cimport numpy as cnp

def run(long[::1] col, double[::1] s1, long reps, guard):
    # A-1c bc-CEILING CHARACTERIZATION PROBE (record, NOT a gate): a pure histogram scatter
    # s1[col[i]] += g with MINIMAL vectorizable compute, so the boundscheck on the data-dependent
    # write index col[i] is the largest available per-access fraction. Measures the boundscheck
    # ceiling on this machine (expected ~1.3-1.4x, never dominant over -O3/march). col in [0,len(s1)).
    cdef Py_ssize_t i, r, n = col.shape[0]
    cdef double g = 1.0
    if guard is not None:
        g = <double>guard
    for r in range(reps):
        for i in range(n):
            s1[col[i]] += g
    return s1
'''

FAMILIES = {
    "A": ("streaming_gather", FAMILY_A, "float"),
    "B": ("vector_reduce", FAMILY_B, "float"),
    "C": ("compensated_cliff", FAMILY_C, "float"),
}
CONTROLS = {
    "planted": ("planted_vec_lever", CONTROL_PLANTED, "float"),
    "flat": ("bandwidth_flat", CONTROL_FLAT, "float"),
    "bcprobe": ("bc_ceiling_probe", CONTROL_BCPROBE, "float"),
}

# Per-family driver recipe: build inputs from a seed (untimed), call run(), canonicalize output.
_DRIVER = '''"""Driver for {kid} (family {family}, intended class {klass})."""
import numpy as np

N = {n}
REPS = {reps}
OUTPUT_CLASS = "{output_class}"

def make_inputs(seed):
    rng = np.random.default_rng(seed)
    a = rng.standard_normal(N).astype(np.float64)
    # idx spans [-N, N) so negative indices exercise wraparound; long dtype
    idx = rng.integers(-N, N, size=N, dtype=np.int64)
    opt = {opt_arg}                      # Optional/None-typed 4th arg (nonecheck path)
    return (a, idx, REPS, opt)

def call(mod, inputs):
    return mod.run(*inputs)

def canon(result):
    return np.asarray(result, dtype=np.float64).reshape(-1)
'''

# Family B needs (a, b) not (a, idx); give it its own recipe.
_DRIVER_B = '''"""Driver for {kid} (family B vector_reduce, intended class {klass})."""
import numpy as np

N = {n}
REPS = {reps}
OUTPUT_CLASS = "{output_class}"

def make_inputs(seed):
    rng = np.random.default_rng(seed)
    a = rng.standard_normal(N).astype(np.float64)
    b = rng.standard_normal(N).astype(np.float64)
    return (a, b, REPS, None)

def call(mod, inputs):
    return mod.run(*inputs)

def canon(result):
    return np.asarray(result, dtype=np.float64).reshape(-1)
'''


_DRIVER_C = '''"""Driver for {kid} (family C compensated_cliff, intended class {klass})."""
import numpy as np

N = {n}
REPS = {reps}
OUTPUT_CLASS = "{output_class}"

def make_inputs(seed):
    rng = np.random.default_rng(seed)
    a = np.ones(N, dtype=np.float64) + rng.standard_normal(N) * 1e-3
    a[0] = 1e16          # large spike straddling the small terms: naive sum loses them, Kahan keeps them
    a[N - 1] = -1e16     # cancels the spike -> strict result ~ sum of small terms; fast-math -> ~0
    comp = {comp_arg}    # Optional/None 3rd arg (nonecheck); None or 1 both keep compensation ON
    return (a, REPS, comp)

def call(mod, inputs):
    return mod.run(*inputs)

def canon(result):
    return np.asarray(result, dtype=np.float64).reshape(-1)
'''


_MECHANISMS_FULL = ["boundscheck(index)", "wraparound(neg-index)", "cdivision(%)",
                    "initializedcheck(memoryview)", "nonecheck(Optional arg)", "fp-loop"]
_MECHANISMS_B = ["boundscheck(index)", "initializedcheck(memoryview)", "nonecheck(Optional arg)",
                 "fp-loop", "fast_math(vectorization)"]
_MECHANISMS_C = ["boundscheck(index)", "initializedcheck(memoryview)", "nonecheck(Optional arg)",
                 "fp-loop", "fast_math(compensation-cliff)"]
_MECHANISMS_CTRL = ["boundscheck(index)", "initializedcheck(memoryview)", "nonecheck(Optional arg)", "reduce-loop"]


_DRIVER_PLANTED = '''"""Driver for {kid} (planted boundscheck lever) — compute-bound elementwise map."""
import numpy as np

N = {n}
REPS = {reps}
OUTPUT_CLASS = "float"

def make_inputs(seed):
    rng = np.random.default_rng(seed)
    a = rng.standard_normal(N).astype(np.float64)             # L1-resident -> compute-bound
    out = np.zeros(N, dtype=np.float64)
    return (a, out, REPS, {guard_arg})                        # Optional guard -> nonecheck

def call(mod, inputs):
    return mod.run(*inputs)

def canon(result):
    return np.asarray(result, dtype=np.float64).reshape(-1)
'''

_DRIVER_FLAT = '''"""Driver for {kid} (latency-flat control) — pointer chase over a random permutation."""
import numpy as np

SCALE = {n}                                                   # permutation size = chase length knob
OUTPUT_CLASS = "float"
_CACHE = {{}}

def make_inputs(seed):
    key = (seed, SCALE)
    if key not in _CACHE:                                     # read-only kernel: cache the >>L3 perm
        rng = np.random.default_rng(seed)
        _CACHE.clear(); _CACHE[key] = rng.permutation(SCALE).astype(np.int64)
    return (_CACHE[key], 1, {guard_arg})                      # reps=1; runtime set by SCALE

def call(mod, inputs):
    return mod.run(*inputs)

def canon(result):
    return np.asarray(result, dtype=np.float64).reshape(-1)
'''


_DRIVER_BCPROBE = '''"""Driver for {kid} (A-1c bc-ceiling probe) — histogram scatter."""
import numpy as np

N = {n}
REPS = {reps}
M = 256
OUTPUT_CLASS = "float"

def make_inputs(seed):
    rng = np.random.default_rng(seed)
    col = rng.integers(0, M, size=N, dtype=np.int64)          # data-dependent write index in [0,M)
    s1 = np.zeros(M, dtype=np.float64)                         # per-rep regen (scatter accumulates)
    return (col, s1, REPS, {guard_arg})

def call(mod, inputs):
    return mod.run(*inputs)

def canon(result):
    return np.asarray(result, dtype=np.float64).reshape(-1)
'''


def generate_kernel(out_root, kid, klass, family_key, gen_index, n, reps, is_control=False):
    fam = CONTROLS[family_key] if is_control else FAMILIES[family_key]
    fam_name, src, output_class = fam
    kdir = os.path.join(out_root, kid)
    os.makedirs(kdir, exist_ok=True)
    with open(os.path.join(kdir, "kernel.pyx"), "w") as f:
        f.write(src)
    guard_arg = "None" if (gen_index % 2 == 0) else "1"
    if family_key == "planted":
        driver = _DRIVER_PLANTED.format(kid=kid, n=n, reps=reps, guard_arg=guard_arg)
    elif family_key == "flat":
        driver = _DRIVER_FLAT.format(kid=kid, n=n, reps=reps, guard_arg=guard_arg)
    elif family_key == "bcprobe":
        driver = _DRIVER_BCPROBE.format(kid=kid, n=n, reps=reps, guard_arg=guard_arg)
    elif family_key == "B":
        driver = _DRIVER_B.format(kid=kid, klass=klass, n=n, reps=reps, output_class=output_class)
    elif family_key == "C":
        comp_arg = "None" if (gen_index % 2 == 0) else "1"
        driver = _DRIVER_C.format(kid=kid, klass=klass, n=n, reps=reps,
                                  output_class=output_class, comp_arg=comp_arg)
    else:
        opt_arg = "None" if (gen_index % 2 == 0) else "1"
        driver = _DRIVER.format(kid=kid, family=fam_name, klass=klass, n=n, reps=reps,
                                output_class=output_class, opt_arg=opt_arg)
    with open(os.path.join(kdir, "driver.py"), "w") as f:
        f.write(driver)
    spec = {
        "kernel_id": kid, "intended_class": klass, "family": fam_name, "family_key": family_key,
        "generation_index": gen_index, "is_control": is_control,
        "n": n, "reps": reps, "output_class": output_class,
        "gen_seed_key": ["gen", {"A": 1, "B": 2, "C": 3}.get(klass, 0), gen_index],
        "mechanisms": _MECHANISMS_CTRL if is_control else (
            _MECHANISMS_B if family_key == "B" else (
                _MECHANISMS_C if family_key == "C" else _MECHANISMS_FULL)),
        "scale_note": "reps is the 50-80ms scale knob; calibrated by the harness before freeze",
    }
    with open(os.path.join(kdir, "spec.json"), "w") as f:
        json.dump(spec, f, indent=2)
    return kdir
