"""Input-manifest / pairing mechanism (Step 1.2.2; roadmap §5.1 lines 320, 337).

Pairing lives at the INPUT level: ONE manifest-hashed input per unit at the chosen
~480-500 ms golden scale, IDENTICAL across all configs / methods / seeds / and all 3
endpoint subprocesses. The optimizer seed varies which configs BO/RS PROPOSE — never the
measurement input (§5.1 line 131). The input is REGENERATED in each fresh subprocess from
a committed deterministic recipe (the `setup_code`); the materialized bytes are NOT
committed (a corpus input can be ~400 MB). What is committed is the MANIFEST — the recipe
hash + seed + a content fingerprint of the materialized args — and the driver
VERIFIES-OR-REFUSES against it before any timed run, so input drift (a recipe edit, a numpy
RNG-stream skew, or non-determinism) can never silently break pairing.

The fingerprint is taken on the args AS `setup_code` CONSTRUCTS them (pre-kernel); it is
computed at manifest-build time and at verify time only — never inside the timed region.
"""
import hashlib
import struct

from motifbo.timing.endpoint import measure_endpoint

SCHEMA = "motifbo-input-manifest-v1"


class InputDriftError(RuntimeError):
    """Raised by verify_input when the regenerated input does not match the committed
    manifest — a fail-closed guard against silent input drift (a pairing break)."""


def _feed(h, tag, obj):
    """Feed one argument into the hasher: dtype + shape + C-contiguous bytes for arrays;
    a type-tagged exact value for scalars/strings. FAIL-CLOSED on any other type — never
    weak-hash an unknown object by repr (pairing safety > permissiveness)."""
    h.update(tag)
    if hasattr(obj, "dtype") and hasattr(obj, "shape") and hasattr(obj, "tobytes"):
        import numpy as np
        shape = tuple(obj.shape)         # ORIGINAL shape — np.ascontiguousarray promotes a
        a = np.ascontiguousarray(obj)    # 0-d input to (1,), which would collapse 0-d vs (1,)
        h.update(str(a.dtype.str).encode()); h.update(b"|")
        h.update(repr(shape).encode()); h.update(b"|")     # records () distinct from (1,)
        h.update(a.tobytes())
    elif isinstance(obj, bool):                      # bool before int (bool subclasses int)
        h.update(b"bool|"); h.update(b"\x01" if obj else b"\x00")
    elif isinstance(obj, int):
        h.update(b"int|"); h.update(str(obj).encode())     # str() — no int64 overflow
    elif isinstance(obj, float):
        h.update(b"float|"); h.update(struct.pack("<d", obj))   # exact IEEE-754 bits
    elif isinstance(obj, str):
        h.update(b"str|"); h.update(obj.encode("utf-8"))
    elif isinstance(obj, (bytes, bytearray)):
        h.update(b"bytes|"); h.update(bytes(obj))
    elif (hasattr(obj, "format") and hasattr(obj, "shape") and hasattr(obj, "data")
          and type(obj).__module__.startswith("scipy.sparse")):
        # scipy sparse matrix: hash format + shape + every constituent array (CSR/CSC:
        # data/indices/indptr; COO: data/row/col) so a pairing break in ANY component is
        # caught. Each array recurses through the ndarray branch (dtype+shape+bytes).
        h.update(b"sparse|"); h.update(str(obj.format).encode()); h.update(b"|")
        h.update(repr(tuple(obj.shape)).encode()); h.update(b"|")
        fed = []
        for name in ("data", "indices", "indptr", "row", "col"):
            arr = getattr(obj, name, None)
            if arr is not None:
                fed.append(name); _feed(h, f"{name}:".encode(), arr)
        if not fed:
            raise TypeError(
                f"sparse matrix {type(obj).__name__!r} exposed no recognized component "
                f"arrays (data/indices/indptr/row/col) — refusing to weak-hash")
    else:
        raise TypeError(
            f"un-fingerprintable kernel-input type {type(obj).__name__!r}: add explicit "
            f"handling to input_manifest._feed — refusing to weak-hash by repr (pairing safety)")
    h.update(b";")


def fingerprint_args(args, kwargs=None):
    """Stable SHA-256 over the materialized kernel inputs, in argument order (kwargs by
    sorted key). Sensitive to dtype, shape, bytes, argument order, and kwargs."""
    h = hashlib.sha256()
    for i, a in enumerate(args):
        _feed(h, f"arg{i}:".encode(), a)
    if kwargs:
        for k in sorted(kwargs):
            _feed(h, f"kw:{k}:".encode(), kwargs[k])
    return h.hexdigest()


def recipe_sha256(setup_code):
    """SHA-256 of the recipe STRING itself (catches a setup_code edit before any bytes run)."""
    return hashlib.sha256(setup_code.encode()).hexdigest()


def materialize(setup_code):
    """Exec the recipe in an isolated namespace and return (args, kwargs) — the same
    construction the timing _child does, UNTIMED. Trusted in-repo recipes only."""
    ns = {}
    exec(setup_code, ns)
    if "args" not in ns:
        raise KeyError("setup_code must define `args`")
    return tuple(ns["args"]), dict(ns.get("kwargs", {}))


def _arg_spec(a):
    if hasattr(a, "dtype") and hasattr(a, "shape"):
        return {"dtype": str(a.dtype.str), "shape": list(a.shape)}
    return {"type": type(a).__name__}


def build_manifest(unit, setup_code, seed):
    """Build the committed input manifest for a unit: recipe hash + seed + content
    fingerprint of the materialized args (+ per-arg dtype/shape specs for readability)."""
    args, kwargs = materialize(setup_code)
    return {
        "schema": SCHEMA,
        "unit": unit,
        "seed": seed,
        "recipe_sha256": recipe_sha256(setup_code),
        "content_fingerprint": fingerprint_args(args, kwargs),
        "arg_specs": [_arg_spec(a) for a in args],
        "n_args": len(args),
        "n_kwargs": len(kwargs),
    }


def verify_input(setup_code, manifest):
    """VERIFY-OR-REFUSE: re-materialize the recipe and re-fingerprint; raise InputDriftError
    if EITHER the recipe hash OR the content fingerprint differs from the committed manifest.
    Called by the driver BEFORE any timed run so input drift cannot silently break pairing."""
    got_recipe = recipe_sha256(setup_code)
    if got_recipe != manifest["recipe_sha256"]:
        raise InputDriftError(
            f"recipe hash drift for unit {manifest.get('unit')!r}: setup_code changed "
            f"(committed {manifest['recipe_sha256'][:12]}, got {got_recipe[:12]}) — refusing")
    args, kwargs = materialize(setup_code)
    got_fp = fingerprint_args(args, kwargs)
    if got_fp != manifest["content_fingerprint"]:
        raise InputDriftError(
            f"input fingerprint drift for unit {manifest.get('unit')!r}: materialized args "
            f"differ (committed {manifest['content_fingerprint'][:12]}, got {got_fp[:12]}) — "
            f"refusing to measure (pairing would be broken)")
    return True


def measure_paired_endpoint(module_path, kernel, setup_code, reps, manifest, **kw):
    """Driver entry: VERIFY-OR-REFUSE the input against its committed manifest, THEN run the
    median-of-N endpoint. The verify happens before any subprocess is spawned, so a drifted
    input never reaches a timed run. All n_subproc subprocesses re-run this same paired input.
    Extra kwargs (n_subproc, warmup, policy, _measure, ...) pass through to measure_endpoint."""
    verify_input(setup_code, manifest)
    result = measure_endpoint(module_path, kernel, setup_code, reps, **kw)
    result["input_manifest"] = {"unit": manifest.get("unit"),
                                "content_fingerprint": manifest["content_fingerprint"],
                                "recipe_sha256": manifest["recipe_sha256"]}
    return result
