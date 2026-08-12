"""Phase-P oracle (PREREG §5 / v1 §3.1). Correctness is absolute: oracle-fail ⇒ feasible=0.

derive(): from the golden reference run + a few repeat runs, fix the oracle: output class,
golden values/hash/shape, and tolerance = max(10×observed cross-rep relative deviation, floor).
compare(): bit-exact for int/bool classes (hash), toleranced (rtol/atol, NaN==NaN) for float.
"""
from __future__ import annotations
import numpy as np

RTOL_FLOOR = 1e-9
ATOL_FLOOR = 1e-12


def derive(golden_reps):
    """golden_reps: list of measure_child result dicts from the REFERENCE config (≥2). Returns oracle."""
    g0 = golden_reps[0]
    cls = g0["output_class"]
    vals = [np.asarray(r["output_values"], float) for r in golden_reps if r["output_values"] is not None]
    reldev = 0.0
    if len(vals) >= 2 and cls == "float":
        stack = np.vstack(vals)
        base = np.abs(stack[0])
        spread = stack.max(0) - stack.min(0)
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = np.where(base > 0, spread / base, spread)
        reldev = float(np.nanmax(rel)) if rel.size else 0.0
    rtol = max(10.0 * reldev, RTOL_FLOOR) if cls == "float" else 0.0
    atol = ATOL_FLOOR if cls == "float" else 0.0
    return {
        "output_class": cls, "golden_sha256": g0["output_sha256"],
        "golden_values": g0["output_values"], "golden_shape": g0["output_shape"],
        "tolerance": {"rtol": rtol, "atol": atol},
        "cross_rep_reldev": reldev, "n_golden_reps": len(golden_reps),
    }


def compare(oracle, cand):
    """cand: a measure_child result dict. Returns (feasible_bit, reason)."""
    if cand.get("output_shape") != oracle["golden_shape"]:
        return 0, "oracle_mismatch"
    if oracle["output_class"] in ("int", "bool"):
        return (1, "ok") if cand["output_sha256"] == oracle["golden_sha256"] else (0, "oracle_mismatch")
    g = np.asarray(oracle["golden_values"], float)
    c = np.asarray(cand["output_values"], float)
    rtol, atol = oracle["tolerance"]["rtol"], oracle["tolerance"]["atol"]
    if np.allclose(c, g, rtol=rtol, atol=atol, equal_nan=True):
        return 1, "ok"
    return 0, "oracle_mismatch"
