"""Hypothesis property-based input corpus for the Phase-0 reference-kernel
sanitizer pass (Step 0.P / close-out G1, §3.3).

`hypothesis` was pinned at re-pin 0.4.2b, AFTER the 0.4.2 known-good ASan/UBSan run
used a fixed-seed numpy stand-in (`validation_inputs.py`). §3.3 names Hypothesis
property cases as part of the validation input set, so the known-good build must also
be shown clean over Hypothesis-generated inputs before Phase-0 exit item 3 is green.

These strategies emit SPEC dicts in the EXACT schema `validation_inputs.materialize_csr`
/ `materialize_pava` consume, so a generated case flows through the same materialize +
sanitizer build + fresh-subprocess child as the 0.4.2 numpy corpus — no new kernel-call
path. The corpus is deterministic (`derandomize=True`, no example DB, generate-only) and
committed, satisfying §3.3 "property-based cases (Hypothesis, fixed seed per unit,
committed corpus)".
"""
import hypothesis.strategies as st
from hypothesis import Phase, given, settings

# value modes accepted by validation_inputs._values
_VALUE_MODES = ["uniform", "signed", "extreme", "nan_inf", "zeros"]


@st.composite
def csr_spec(draw):
    """A csr_scale spec honouring the materialize_csr contract (len(factor)=nrows;
    indptr derived from nnz; passes >= 0)."""
    nrows = draw(st.integers(min_value=0, max_value=400))
    spec = {
        "name": "hyp",
        "nrows": nrows,
        "data": draw(st.sampled_from(_VALUE_MODES)),
        "factor": draw(st.sampled_from(["uniform", "zero"])),
        # csr_scale contract (csr_scale.pyx L20): passes must be EVEN (multiply/divide
        # pairs) — odd passes are a malformed input, not a kernel defect, so the
        # memory-safety corpus stays in-contract (§3.3 non-vacuity).
        "passes": 2 * draw(st.integers(min_value=0, max_value=4)),
        "offset": draw(st.booleans()),
        "seed": draw(st.integers(min_value=0, max_value=2**31 - 1)),
    }
    # nnz given either as an explicit per-row list (exact length = nrows) or a range
    if nrows and draw(st.booleans()):
        spec["nnz_rows"] = draw(st.lists(st.integers(0, 48),
                                         min_size=nrows, max_size=nrows))
    else:
        lo = draw(st.integers(min_value=0, max_value=8))
        spec["nnz_lo"] = lo
        spec["nnz_hi"] = draw(st.integers(min_value=lo, max_value=lo + 16))
    return spec


@st.composite
def pava_spec(draw):
    """A pava spec honouring the materialize_pava contract (all arrays length n)."""
    return {
        "name": "hyp",
        "n": draw(st.integers(min_value=0, max_value=600)),
        "shape": draw(st.sampled_from(["random", "decreasing", "increasing", "equal"])),
        "data": draw(st.sampled_from(_VALUE_MODES)),
        "weight": draw(st.sampled_from(["uniform", "zero", "negative"])),
        "offset": draw(st.booleans()),
        "seed": draw(st.integers(min_value=0, max_value=2**31 - 1)),
    }


STRATEGY = {"csr": csr_spec, "pava": pava_spec}


def generate_corpus(kind, n):
    """Deterministically draw up to `n` property specs for `kind`.

    derandomize=True + database=None + phases=[generate] => the SAME committable
    sequence every run (no host-RNG, no example-DB influence, no shrinking)."""
    collected = []
    strat = STRATEGY[kind]()

    @settings(max_examples=n, derandomize=True, database=None,
              deadline=None, phases=[Phase.generate])
    @given(strat)
    def _collect(spec):
        collected.append(spec)

    _collect()
    for i, s in enumerate(collected):
        s["name"] = f"hyp_{kind}_{i:03d}"
    return collected
