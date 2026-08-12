"""Θ — the 1,728-config space, canonical config_id, factor coding, neighborhood.

THE SOLE SOURCE OF config_ids (PREREG_PHASEP §0.1). Everything downstream — tables, DOE/probe
designs, class assignment, replay, the CLI — imports config_id and the factor coding from here.

Coding (PREREG §0.1): 9 factors; the conditional fast_math×ffp_contract pair is a single 3-level
composite `fmffp` ∈ {(off,off),(off,fast),(on,NA)}. This is FULL RANK (the v1 "NA as its own
level" coding was rank-deficient — NA collinear with fast_math=on). config_id = the 0-based index
in the lexicographic product of the 9 factors in the order below (first = most significant); this
is PROVABLY identical to roadmap Appendix A's 10-dim tuple with the conditional collapse
(scripts/phasep/test_theta.py::test_matches_appendix_a).

Build translation (mirrors scripts/corpus/build_unit.sh args): fast_math=on adds `-ffast-math` to
opt_flags and the ffp build-arg is "fast" (contraction is moot under fast-math, roadmap §2).
"""
from __future__ import annotations
import itertools

# (name, canonical-ordered levels).  Booleans: True before False (Appendix A).
FACTORS = [
    ("boundscheck", (True, False)),
    ("wraparound", (True, False)),
    ("cdivision", (True, False)),
    ("initializedcheck", (True, False)),
    ("nonecheck", (True, False)),
    ("opt_level", ("-O1", "-O2", "-O3")),
    ("march", ("x86-64", "native")),
    ("funroll", ("omit", "on", "off")),
    ("fmffp", (("off", "off"), ("off", "fast"), ("on", "NA"))),
]
FACTOR_NAMES = [n for n, _ in FACTORS]
N_CONFIGS = 1
for _, lv in FACTORS:
    N_CONFIGS *= len(lv)  # 32 * 54 = 1728

# Reference / golden config (PREREG §0.2): as-shipped Cython defaults, -O2 x86-64, no unroll, no contract.
REFERENCE = (True, True, False, True, False, "-O2", "x86-64", "omit", ("off", "off"))


def all_configs():
    """Yield every config tuple in canonical config_id order (index == config_id)."""
    yield from itertools.product(*[lv for _, lv in FACTORS])


_CONFIG_LIST = list(all_configs())
_CONFIG_INDEX = {c: i for i, c in enumerate(_CONFIG_LIST)}
assert len(_CONFIG_LIST) == N_CONFIGS == 1728, (len(_CONFIG_LIST), N_CONFIGS)
REFERENCE_ID = _CONFIG_INDEX[REFERENCE]


def config_of(cid: int):
    return _CONFIG_LIST[cid]


def id_of(config) -> int:
    return _CONFIG_INDEX[tuple(config)]


def as_dict(config):
    return dict(zip(FACTOR_NAMES, config))


def build_flags(config):
    """Return (cython_dirs, opt_flags, ffp_contract, language) for build_unit.sh / the harness.

    cython_dirs: `-X name=Bool ...` for the 5 directives (Cython default_level=3).
    opt_flags:   e.g. "-O3 -march=native -funroll-loops -ffast-math"  (NO -ffp-contract here).
    ffp_contract: off | fast   (the build-arg; "fast" under fast_math, where it is moot).
    """
    bc, wa, cd, ic, nc, opt, march, fun, (fm, ffp) = config
    dirs = (f"-X boundscheck={bc} -X wraparound={wa} -X cdivision={cd} "
            f"-X initializedcheck={ic} -X nonecheck={nc}")
    parts = [opt, f"-march={march}"]
    if fun == "on":
        parts.append("-funroll-loops")
    elif fun == "off":
        parts.append("-fno-unroll-loops")
    if fm == "on":
        parts.append("-ffast-math")
    opt_flags = " ".join(parts)
    ffp_build = "fast" if fm == "on" else ffp  # (on,NA) builds with contraction permitted
    return dirs, opt_flags, ffp_build, "c"


def directive_combo(config):
    """The 5-tuple of Cython directives — the cythonize cache key (32 combos, §4.4)."""
    return config[:5]


def safety_class(config):
    """6-dim sanitizer memoization key (PREREG §5 / v1 §3.3): bc,wa,ic,nc,cd,fast_math."""
    bc, wa, cd, ic, nc, _opt, _march, _fun, (fm, _ffp) = config
    return (bc, wa, ic, nc, cd, fm == "on")


def neighbors(cid: int):
    """1-flip neighborhood N(c): configs differing in exactly one of the 9 factors (|N|=12)."""
    cfg = list(_CONFIG_LIST[cid])
    out = []
    for k, (_name, levels) in enumerate(FACTORS):
        for lv in levels:
            if lv != cfg[k]:
                nb = tuple(cfg[:k] + [lv] + cfg[k + 1:])
                out.append(_CONFIG_INDEX[nb])
    return out


# ---- Main-effects design matrix (drop-first one-hot), the SINGLE coding for IF/DOE/probe ----
def _dropfirst_columns():
    """Column spec: list of (factor_index, level) for every non-baseline level (12 dummies)."""
    cols = []
    for k, (_name, levels) in enumerate(FACTORS):
        for lv in levels[1:]:  # drop first (baseline)
            cols.append((k, lv))
    return cols


DESIGN_COLUMNS = _dropfirst_columns()          # 12 dummies
N_PARAMS = 1 + len(DESIGN_COLUMNS)             # + intercept = 13


def design_row(config):
    """13-vector: [1, dummy_1..dummy_12] for a single config (numpy-free list)."""
    row = [1.0]
    for (k, lv) in DESIGN_COLUMNS:
        row.append(1.0 if config[k] == lv else 0.0)
    return row


def design_matrix(config_ids):
    import numpy as np
    return np.array([design_row(_CONFIG_LIST[c]) for c in config_ids], dtype=float)


if __name__ == "__main__":
    import numpy as np
    assert N_CONFIGS == 1728
    # bijection
    assert all(id_of(config_of(i)) == i for i in range(N_CONFIGS))
    # neighborhood size + symmetry
    for cid in (0, REFERENCE_ID, 999, 1727):
        nb = neighbors(cid)
        assert len(nb) == 12, (cid, len(nb))
        assert all(cid in neighbors(n) for n in nb), f"asymmetric N at {cid}"
    # full-rank main-effects model over all of Θ
    X = design_matrix(range(N_CONFIGS))
    assert X.shape == (1728, 13)
    assert np.linalg.matrix_rank(X) == 13, np.linalg.matrix_rank(X)
    # reference sanity
    print(f"|Θ|={N_CONFIGS}  N_PARAMS={N_PARAMS}  rank={np.linalg.matrix_rank(X)}")
    print(f"REFERENCE_ID={REFERENCE_ID}  ref build_flags={build_flags(REFERENCE)}")
    print("theta.py self-check: OK")
