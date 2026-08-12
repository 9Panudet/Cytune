"""Bitwise comparator for correctness-critical outputs (Step 0.3.2, §3.1/§3.5).

compare_bitwise(golden, candidate) -> None on a bit-exact match, else a
mismatch-reason string carrying the container path (feeds the per-evaluation
oracle-diff artifact, §3.5). Bitwise means bitwise:

- Exact type first: bool != int, np.float64 != float, list != tuple — the
  correctness-critical class tolerates no representational drift.
- ndarray: dtype, shape, then tobytes() (C-order canonicalization makes a
  non-contiguous view equal to its copy). Object dtype raises TypeError —
  pointer bytes are meaningless and the corpus kernels are numeric.
- float/complex: IEEE-754 bit pattern (struct), so 0.0 != -0.0 and NaN
  payloads must match exactly.
- dict: exact key set + per-key recursion (insertion order not compared);
  list/tuple: order IS the layout.
- Unsupported types raise TypeError — fail loudly, never guess (§6.1).

Exception identity (§3.1: raised-exception type is correctness-critical;
§3.5: wrong/missing exception => infeasible): Outcome wraps a run's result —
a returned value or a raised exception. Exceptions are canonicalized to
"module.QualName" strings, because candidate runs happen in fresh
subprocesses (§3.2(2)) where type objects cannot be compared by identity.
Equality is on the canonical name: a subclass never satisfies identity.
"""
import re
import struct

import numpy as np

_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_DOTTED_RE = re.compile(rf"^{_NAME}(\.{_NAME})+$")


class Outcome:
    """Result of running a kernel: a value, or a raised exception's identity."""

    __slots__ = ("kind", "payload")

    def __init__(self, kind, payload):
        self.kind = kind
        self.payload = payload

    @classmethod
    def value(cls, v):
        return cls("value", v)

    @classmethod
    def exception(cls, exc):
        """Accept a BaseException instance, an exception type, or a canonical
        dotted "module.QualName" string; store the canonical name."""
        if isinstance(exc, BaseException):
            exc = type(exc)
        if isinstance(exc, type) and issubclass(exc, BaseException):
            name = f"{exc.__module__}.{exc.__qualname__}"
        elif isinstance(exc, str) and _DOTTED_RE.match(exc):
            name = exc
        else:
            raise TypeError(f"not an exception type/instance/dotted name: {exc!r}")
        return cls("exception", name)


def compare_outcomes(golden, candidate, where="output"):
    """Compare two Outcomes; None on match, else the §3.5 mismatch reason."""
    if golden.kind == "exception":
        if candidate.kind != "exception":
            return (f"{where}: missing exception — golden raised "
                    f"{golden.payload}, candidate returned a value")
        if golden.payload != candidate.payload:
            return (f"{where}: wrong exception type — golden raised "
                    f"{golden.payload}, candidate raised {candidate.payload}")
        return None
    if candidate.kind == "exception":
        return (f"{where}: unexpected exception — golden returned a value, "
                f"candidate raised {candidate.payload}")
    return compare_bitwise(golden.payload, candidate.payload, where)


def compare_bitwise(golden, candidate, where="output"):
    """Bit-exact comparison; None on match, else a mismatch-reason string."""
    if type(golden) is not type(candidate):
        return (f"{where}: type mismatch — golden {type(golden).__name__}, "
                f"candidate {type(candidate).__name__}")
    if isinstance(golden, np.ndarray):
        return _compare_arrays(golden, candidate, where)
    if isinstance(golden, np.generic):
        if golden.tobytes() != candidate.tobytes():
            return (f"{where}: scalar bit pattern differs — golden "
                    f"{golden!r}, candidate {candidate!r}")
        return None
    if isinstance(golden, float):
        return _compare_bits(struct.pack("<d", golden),
                             struct.pack("<d", candidate),
                             golden, candidate, where)
    if isinstance(golden, complex):
        return _compare_bits(struct.pack("<dd", golden.real, golden.imag),
                             struct.pack("<dd", candidate.real, candidate.imag),
                             golden, candidate, where)
    if golden is None or isinstance(golden, (bool, int, str, bytes)):
        # exact type already guaranteed above, so bool-vs-int cannot reach
        # here and plain equality is the bit-exact comparison for these types
        if golden != candidate:
            return (f"{where}: value mismatch — golden {golden!r}, "
                    f"candidate {candidate!r}")
        return None
    if isinstance(golden, (list, tuple)):
        if len(golden) != len(candidate):
            return (f"{where}: length mismatch — golden {len(golden)}, "
                    f"candidate {len(candidate)}")
        for i, (g, c) in enumerate(zip(golden, candidate)):
            reason = compare_bitwise(g, c, f"{where}[{i}]")
            if reason:
                return reason
        return None
    if isinstance(golden, dict):
        if set(golden) != set(candidate):
            missing = sorted(map(repr, set(golden) - set(candidate)))
            extra = sorted(map(repr, set(candidate) - set(golden)))
            return (f"{where}: key set mismatch — missing {missing}, "
                    f"extra {extra}")
        for k in golden:  # insertion order not compared (§3.1 layout = contents)
            reason = compare_bitwise(golden[k], candidate[k], f"{where}[{k!r}]")
            if reason:
                return reason
        return None
    raise TypeError(f"{where}: unsupported type for bitwise comparison: "
                    f"{type(golden).__name__}")


def _compare_arrays(golden, candidate, where):
    if golden.dtype.hasobject or candidate.dtype.hasobject:
        raise TypeError(f"{where}: object-dtype arrays are not bitwise-"
                        f"comparable (pointer bytes)")
    if golden.dtype != candidate.dtype:
        return (f"{where}: dtype mismatch — golden {golden.dtype}, "
                f"candidate {candidate.dtype}")
    if golden.shape != candidate.shape:
        return (f"{where}: shape mismatch — golden {golden.shape}, "
                f"candidate {candidate.shape}")
    gb, cb = golden.tobytes(), candidate.tobytes()  # C-order canonical copies
    if gb != cb:
        ga = np.frombuffer(gb, dtype=np.uint8)
        ca = np.frombuffer(cb, dtype=np.uint8)
        off = int(np.nonzero(ga != ca)[0][0])
        return (f"{where}: bytes differ (first differing byte offset {off} "
                f"of {len(gb)}, ~element index {off // golden.itemsize})")
    return None


def _compare_bits(gbits, cbits, golden, candidate, where):
    if gbits != cbits:
        return (f"{where}: bit pattern differs — golden {golden!r} "
                f"({gbits.hex()}), candidate {candidate!r} ({cbits.hex()})")
    return None
