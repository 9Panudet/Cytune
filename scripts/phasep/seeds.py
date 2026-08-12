"""Deterministic seed derivation for all of Phase P (PREREG §0.4).

Every random operation derives from base seed 20260708 via numpy SeedSequence. A spawn key
written ['k1', k2, ...] denotes SeedSequence([20260708, enc('k1'), enc(k2), ...]) — the base seed
is always prepended; string elements are encoded by 64-bit FNV-1a of their UTF-8 bytes; integer
elements pass through. This is the ONLY permitted entropy source in Phase P.
"""
from __future__ import annotations
import json
import numpy as np

BASE_SEED = 20260708
_FNV_OFFSET = 14695981039346656037
_FNV_PRIME = 1099511628211
_MASK = (1 << 64) - 1


def fnv1a64(s: str) -> int:
    h = _FNV_OFFSET
    for b in s.encode("utf-8"):
        h = ((h ^ b) * _FNV_PRIME) & _MASK
    return h


def _enc(x):
    if isinstance(x, bool):  # guard: bool is an int subclass; treat as int 0/1
        return int(x)
    if isinstance(x, int):
        return x
    if isinstance(x, str):
        return fnv1a64(x)
    raise TypeError(f"seed key element must be int or str, got {type(x)}: {x!r}")


def seq(*key) -> np.random.SeedSequence:
    """SeedSequence for a spawn key (base seed prepended, elements encoded)."""
    return np.random.SeedSequence([BASE_SEED] + [_enc(k) for k in key])


def rng(*key) -> np.random.Generator:
    return np.random.default_rng(seq(*key))


def state_int(*key) -> int:
    """A single 64-bit integer (e.g. sklearn random_state) from a spawn key."""
    return int(seq(*key).generate_state(1, dtype=np.uint64)[0])


def kernel_hash(kernel_id: str) -> int:
    """hash_k for a kernel_id (PREREG §0.4): 64-bit FNV-1a of the id string."""
    return fnv1a64(kernel_id)


def pair_key(alg_a: int, alg_b: int) -> int:
    lo, hi = sorted((alg_a, alg_b))
    return 10 * lo + hi


CLASS_INT = {"A": 1, "B": 2, "C": 3}


def emit_fixtures(path: str):
    """Commit worked seed-fixture values so an auditor can recompute (PREREG §0.4)."""
    fx = {
        "base_seed": BASE_SEED,
        "fnv1a64": {s: fnv1a64(s) for s in
                    ("screen", "doe", "doe-aug", "probe", "bca", "gen", "bo-init", "bo-rf",
                     "audit", "example_kernel_id")},
        "class_int": CLASS_INT,
        "examples": {
            "screen[kernel=example_kernel_id, cid=288]":
                seq("screen", kernel_hash("example_kernel_id"), 288).generate_state(2).tolist(),
            "doe[N_d=24]": seq("doe", 24).generate_state(2).tolist(),
            "probe[16]": seq("probe", 16).generate_state(2).tolist(),
            "bca[class=A, budget=8, pair=(3,4)]":
                seq("bca", CLASS_INT["A"], 8, pair_key(3, 4)).generate_state(2).tolist(),
            "bo-rf[kernel=example_kernel_id, alg=3, seed=0]":
                state_int("bo-rf", kernel_hash("example_kernel_id"), 3, 0),
        },
    }
    with open(path, "w") as f:
        json.dump(fx, f, indent=2)
    return fx


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "/out/seed_fixtures.json"
    fx = emit_fixtures(out)
    # invariants
    assert fnv1a64("screen") == 10080399746057843313, fnv1a64("screen")
    assert fnv1a64("doe") == 14604954895929079171, fnv1a64("doe")
    assert _enc(True) == 1 and _enc(False) == 0
    # distinct keys sharing an int give independent streams
    a = rng("bo-init", 111, 0).random(3)
    b = rng("bo-rf", 111, 0).random(3)
    assert not np.allclose(a, b)
    # determinism
    assert seq("screen", 111, 288).generate_state(1)[0] == seq("screen", 111, 288).generate_state(1)[0]
    print("seeds.py self-check: OK  ->", out)
    print("fnv1a64(screen)=", fx["fnv1a64"]["screen"])
