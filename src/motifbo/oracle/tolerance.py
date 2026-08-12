"""Tolerance comparator for numerically-approximate outputs (Step 0.3.3, §3.1).

compare_tolerance(golden, candidate, tolerance) -> None when the candidate
satisfies the manifest-declared tolerance, else a mismatch-reason string
naming the worst violating element and the violation count (feeds the §3.5
oracle-diff artifact). `tolerance` is the motifbo-oracle-v1 dict:
{"mode": "atol_rtol", "atol": a, "rtol": r} or {"mode": "ulp", "max_ulp": n}.

- atol_rtol: |candidate - golden| <= atol + rtol*|golden|, elementwise,
  scaled by the GOLDEN side (the reference). Floating + complex dtypes.
- ulp: IEEE-754 ordered-integer distance (sign + magnitude bits), float32/
  float64 only — ULP is dtype-relative. Signed zeros are 0 ULPs apart; the
  opposite-sign distance is mag_a + mag_b in unsigned arithmetic, immune to
  the int64 wraparound that would let -1e300 vs 1e300 pass a small max_ulp.
- NaN/Inf policy (both modes): non-finite values must match positionally and
  identically (NaN<->NaN, +inf<->+inf, -inf<->-inf). Tolerance arithmetic
  applies to finite pairs only — "within N ULPs of inf" does not exist.
- Shape/dtype mismatches are comparison outcomes (reasons). Integer/bool
  golden dtype raises TypeError: §3.1 makes integers correctness-critical,
  so an approximate declaration on them is a manifest error, not a mismatch.
"""
import numpy as np

_ULP_DTYPES = {np.dtype(np.float32): np.uint32, np.dtype(np.float64): np.uint64}


def compare_tolerance(golden, candidate, tolerance, where="output"):
    """Compare against a declared tolerance; None on pass, else the reason."""
    mode = tolerance.get("mode") if isinstance(tolerance, dict) else None
    if mode == "atol_rtol":
        return _compare_atol_rtol(golden, candidate,
                                  tolerance["atol"], tolerance["rtol"], where)
    if mode == "ulp":
        return _compare_ulp(golden, candidate, tolerance["max_ulp"], where)
    raise ValueError(f"{where}: unknown tolerance mode in {tolerance!r}")


def derive_tolerance(reps, *, atol_floor, rtol_floor, slack=10.0):
    """§3.1 tolerance DERIVATION (Step 1.1.3) — deferred from Phase 0.

    tolerance = max(slack * observed cross-repetition deviation, domain floor),
    with slack = 10 (§3.1). Returns a "motifbo-oracle-v1" atol_rtol tolerance
    dict (consumed by `compare_tolerance` and validated by `oracle.manifest`).

    `reps`: a sequence of K >= 2 reference-config repetitions of ONE
    numerically-approximate output — same shape, same float dtype. The cross-rep
    deviation is the worst element spread about the per-element median:
        abs_dev = max over (rep, element) of |x_rep - x_med|
        rel_dev = max over (rep, element with x_med != 0) of |x_rep - x_med|/|x_med|
    then atol = max(slack*abs_dev, atol_floor), rtol = max(slack*rel_dev, rtol_floor).
    A deterministic kernel (spread 0) yields EXACTLY the domain floor.

    Non-finite elements (e.g. legitimate inf graph distances) are excluded from
    the deviation — the comparator enforces NaN/Inf positional identity and
    tolerance arithmetic is finite-only. An element non-finite in SOME reps but
    not all is a reference-config non-determinism and raises (resolve first).

    `atol_floor`/`rtol_floor` are the per-unit domain-justified floors and MUST
    be > 0: a 0 floor on a deterministic kernel would yield atol=rtol=0, a
    "bitwise in disguise" tolerance the manifest rejects — declare the output
    correctness-critical instead. Float dtypes only (integers are bit-exact §3.1).
    """
    if not isinstance(reps, (list, tuple)) or len(reps) < 2:
        raise ValueError("derive_tolerance: need >= 2 reference-config repetitions "
                         "to observe cross-rep deviation")
    arrs = [np.asarray(r) for r in reps]
    g0 = arrs[0]
    if g0.dtype.kind != "f":
        raise TypeError(f"derive_tolerance: dtype {g0.dtype} is not tolerance-derivable "
                        "— §3.1 makes non-float outputs correctness-critical (use the "
                        "bitwise comparator); complex is out of scope for v1")
    for j, a in enumerate(arrs[1:], 1):
        if a.dtype != g0.dtype:
            raise TypeError(f"derive_tolerance: rep {j} dtype {a.dtype} != rep 0 {g0.dtype}")
        if a.shape != g0.shape:
            raise ValueError(f"derive_tolerance: rep {j} shape {a.shape} != rep 0 {g0.shape}")
    for name, fl in (("atol_floor", atol_floor), ("rtol_floor", rtol_floor)):
        if not (isinstance(fl, (int, float)) and not isinstance(fl, bool)
                and np.isfinite(fl) and fl > 0):
            raise ValueError(f"derive_tolerance: {name} must be a finite number > 0, got "
                             f"{fl!r} (a 0 floor yields a 'bitwise in disguise' tolerance; "
                             "declare the output correctness-critical instead)")
    stack = np.stack(arrs, axis=0)                          # (K, *shape)
    finite = np.isfinite(stack)
    all_finite = finite.all(axis=0)
    if (finite.any(axis=0) & ~all_finite).any():
        raise ValueError("derive_tolerance: an element is non-finite in some reps but not "
                         "all — the reference config is non-deterministic; resolve before "
                         "deriving a tolerance")
    if not all_finite.any():
        abs_dev = rel_dev = 0.0
    else:
        fin = stack[:, all_finite]                          # (K, n_finite)
        med = np.median(fin, axis=0)                        # (n_finite,)
        dev = np.abs(fin - med)
        abs_dev = float(dev.max())
        nz = med != 0
        rel_dev = float((dev[:, nz] / np.abs(med[nz])).max()) if nz.any() else 0.0
    return {"mode": "atol_rtol",
            "atol": max(slack * abs_dev, float(atol_floor)),
            "rtol": max(slack * rel_dev, float(rtol_floor))}


def _compare_atol_rtol(golden, candidate, atol, rtol, where):
    g, c, err = _prep(golden, candidate, "fc", where)
    if err:
        return err
    reason, both = _check_nonfinite(g, c, where)
    if reason:
        return reason
    gv, cv = g[both], c[both]
    with np.errstate(over="ignore"):
        diff = np.abs(cv - gv)
        bound = atol + rtol * np.abs(gv)
    viol = diff > bound
    if viol.any():
        w = int(np.argmax(np.where(viol, diff - bound, -np.inf)))
        idx = _orig_index(both, w, g.shape)
        return (f"{where}: tolerance violated at {idx}: |candidate - golden| "
                f"= {diff[w]:.6g} > atol + rtol*|golden| = {bound[w]:.6g} "
                f"(golden {gv[w]}, candidate {cv[w]}); "
                f"{int(viol.sum())} of {gv.size} elements out of tolerance")
    return None


def _compare_ulp(golden, candidate, max_ulp, where):
    g, c, err = _prep(golden, candidate, "f", where)
    if err:
        return err
    uint = _ULP_DTYPES.get(g.dtype)
    if uint is None:
        raise TypeError(f"{where}: ULP mode supports float32/float64 only, "
                        f"got {g.dtype}")
    reason, both = _check_nonfinite(g, c, where)
    if reason:
        return reason
    nbits = g.dtype.itemsize * 8
    gv, cv = g[both], c[both]
    ug, uc = gv.view(uint), cv.view(uint)
    mag_mask = uint((1 << (nbits - 1)) - 1)
    mg, mc = ug & mag_mask, uc & mag_mask
    same_sign = (ug >> (nbits - 1)) == (uc >> (nbits - 1))
    # same sign: |mag difference| (subtract larger-first, stays unsigned);
    # opposite sign: distance passes through zero = mag_g + mag_c — computed
    # in the unsigned domain, where float64 magnitudes cannot overflow.
    dist = np.where(same_sign,
                    np.where(mg >= mc, mg - mc, mc - mg),
                    mg + mc)
    viol = dist > max_ulp
    if viol.any():
        w = int(np.argmax(np.where(viol, dist, 0)))
        idx = _orig_index(both, w, g.shape)
        return (f"{where}: ULP distance violated at {idx}: {int(dist[w])} ULPs "
                f"> max_ulp = {max_ulp} (golden {gv[w]}, candidate {cv[w]}); "
                f"{int(viol.sum())} of {dist.size} elements out of tolerance")
    return None


def _prep(golden, candidate, allowed_kinds, where):
    """Coerce to arrays; gate dtype kind (manifest error) and dtype/shape
    agreement (comparison outcomes). Returns (g, c, reason|None)."""
    g, c = np.asarray(golden), np.asarray(candidate)
    if g.dtype.kind not in allowed_kinds:
        raise TypeError(
            f"{where}: dtype {g.dtype} is not tolerance-comparable — §3.1 "
            f"makes non-float outputs correctness-critical (use the bitwise "
            f"comparator)")
    if g.dtype != c.dtype:
        return None, None, (f"{where}: dtype mismatch — golden {g.dtype}, "
                            f"candidate {c.dtype}")
    if g.shape != c.shape:
        return None, None, (f"{where}: shape mismatch — golden {g.shape}, "
                            f"candidate {c.shape}")
    return g, c, None


def _check_nonfinite(g, c, where):
    """Enforce the NaN/Inf identity policy; return (reason|None, both-finite
    mask). Boolean indexing with the mask yields the finite pairs."""
    both = np.isfinite(g) & np.isfinite(c)
    rest = ~both
    if rest.any():
        ok = (np.isnan(g) & np.isnan(c)) | (rest & (g == c))
        bad = rest & ~ok
        if bad.any():
            i = int(np.argmax(bad.ravel()))
            idx = _plain_index(i, g.shape)
            return (f"{where}: non-finite mismatch at {idx}: golden "
                    f"{g.flat[i]}, candidate {c.flat[i]} (NaN/Inf must match "
                    f"positionally and identically)"), both
    return None, both


def _orig_index(both, w, shape):
    """Map index w within the finite-compacted arrays back to the original
    (C-order boolean extraction preserves flat order)."""
    return _plain_index(int(np.flatnonzero(both.ravel())[w]), shape)


def _plain_index(flat_i, shape):
    """unravel_index as a tuple of Python ints — keeps np.int64 reprs out of
    the oracle-diff reason strings."""
    return tuple(int(x) for x in np.unravel_index(flat_i, shape))
