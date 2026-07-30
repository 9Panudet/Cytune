"""Step 1.2.2 TDD — input-manifest / pairing mechanism (verify-or-refuse).

Pairing must not be able to break silently: ONE manifest-hashed input per unit, identical
across all configs / methods / seeds / and all 3 endpoint subprocesses. These tests pin
(a) the content fingerprint is deterministic + sensitive to dtype/shape/bytes/order/kwargs,
(b) verify_input REFUSES on recipe or content drift, (c) the driver verifies BEFORE any timed
run, and (d) pairing is preserved byte-identically through the median-of-3 endpoint and across
configs. Run inside the pinned container (needs numpy).
"""
import numpy as np
import pytest

from motifbo.timing.input_manifest import (
    InputDriftError, build_manifest, fingerprint_args, materialize,
    measure_paired_endpoint, recipe_sha256, verify_input,
)

SLEEP_KERNEL = "ignored-by-fake"
RECIPE = "import numpy as np\nargs = (np.arange(5.0),)\nkwargs = {}\n"


def canned_fake(record_fps=None, called=None):
    """Fake single-subprocess primitive. If record_fps is given, it materializes the
    setup_code it receives and records the input fingerprint (to prove what each subprocess
    actually saw). If called is given, it counts invocations (to prove refuse-before-timing)."""
    def _fake(*, module_path, kernel, setup_code, reps, warmup, timeout_s, cycles,
              mutated_arg_indices=None, per_rep_regen=None, preimport=None):
        if called is not None:
            called["n"] += 1
        if record_fps is not None:
            args, kwargs = materialize(setup_code)
            record_fps.append(fingerprint_args(args, kwargs))
        n = (called or {}).get("n", len(record_fps or [1]))
        return {"samples_ns": [100.0] * reps, "child_pid": 100000 + n, "reps": reps,
                "warmup": warmup, "import_ns": 0, "setup_ns": 0, "cycles": None}
    return _fake


# ---------- content fingerprint: deterministic + sensitive ----------

def test_fingerprint_is_deterministic():
    a = np.arange(10, dtype=np.float64)
    assert fingerprint_args((a,)) == fingerprint_args((a.copy(),))


def test_fingerprint_sensitive_to_a_single_byte():
    a = np.arange(10, dtype=np.float64)
    b = a.copy(); b[3] = np.nextafter(b[3], np.inf)     # one ULP
    assert fingerprint_args((a,)) != fingerprint_args((b,))


def test_fingerprint_sensitive_to_dtype_at_equal_bytes():
    # 16 zero bytes either way, same shape (4,), only dtype differs (<i4 vs <f4).
    x = np.zeros(4, dtype=np.int32)
    y = np.zeros(4, dtype=np.float32)
    assert x.tobytes() == y.tobytes()
    assert fingerprint_args((x,)) != fingerprint_args((y,))


def test_fingerprint_sensitive_to_shape_at_equal_bytes():
    a = np.zeros(12, dtype=np.float64)
    assert a.tobytes() == a.reshape(3, 4).tobytes()
    assert fingerprint_args((a,)) != fingerprint_args((a.reshape(3, 4),))


def test_fingerprint_distinguishes_0d_and_scalar_from_1element_array():
    # REGRESSION: np.ascontiguousarray promotes a 0-d input to shape (1,); recording the
    # PROMOTED shape would collapse a 0-d array / numpy scalar and a 1-element (1,) array to
    # the same fingerprint (a false-equal -> silent pairing break). Original shape is recorded.
    one_d = np.array([5], dtype=np.int64)          # shape (1,)
    zero_d = np.array(5, dtype=np.int64)           # shape ()
    scalar = np.int64(5)                           # shape ()
    assert fingerprint_args((zero_d,)) != fingerprint_args((one_d,))
    assert fingerprint_args((scalar,)) != fingerprint_args((one_d,))


def test_fingerprint_fails_closed_on_an_unfingerprintable_type():
    class Opaque:
        def __repr__(self): return "Opaque()"      # constant repr would have collided
    with pytest.raises(TypeError, match="un-fingerprintable"):
        fingerprint_args((Opaque(),))


def test_fingerprint_handles_scipy_csr_and_is_sensitive_to_every_component():
    # The csr corpus inputs are scipy sparse matrices, not plain ndarrays: _feed must hash
    # format + shape + EVERY component array (data/indices/indptr) so a pairing break in any
    # one is caught, and never fall through to the fail-closed TypeError.
    from scipy.sparse import csr_matrix
    data = np.arange(1, 7, dtype=np.float64)
    indices = np.array([0, 2, 1, 0, 2, 1], dtype=np.int32)
    indptr = np.array([0, 2, 4, 6], dtype=np.int32)
    base = csr_matrix((data.copy(), indices.copy(), indptr.copy()), shape=(3, 3))
    assert fingerprint_args((base,)) == fingerprint_args(
        (csr_matrix((data.copy(), indices.copy(), indptr.copy()), shape=(3, 3)),))
    # sensitive to a single data byte
    d2 = data.copy(); d2[0] = 99.0
    assert fingerprint_args((base,)) != fingerprint_args(
        (csr_matrix((d2, indices.copy(), indptr.copy()), shape=(3, 3)),))
    # sensitive to column indices (same data, different structure)
    i2 = indices.copy(); i2[0] = 1
    assert fingerprint_args((base,)) != fingerprint_args(
        (csr_matrix((data.copy(), i2, indptr.copy()), shape=(3, 3)),))


def test_fingerprint_distinguishes_csr_from_a_dense_array_of_the_same_values():
    # A sparse matrix and a dense ndarray holding the same logical values must not collide.
    from scipy.sparse import csr_matrix
    dense = np.array([[1.0, 0.0], [0.0, 2.0]])
    sp = csr_matrix(dense)
    assert fingerprint_args((sp,)) != fingerprint_args((dense,))


def test_fingerprint_sensitive_to_argument_order():
    a = np.arange(4, dtype=np.float64); b = np.arange(4, dtype=np.int64)
    assert fingerprint_args((a, b)) != fingerprint_args((b, a))


def test_fingerprint_includes_kwargs():
    a = np.arange(4, dtype=np.float64)
    assert fingerprint_args((a,), {"passes": 6}) != fingerprint_args((a,), {"passes": 8})
    assert fingerprint_args((a,), {"passes": 6}) != fingerprint_args((a,))


def test_recipe_hash_changes_with_the_recipe_string():
    assert recipe_sha256("x = 1\n") != recipe_sha256("x = 2\n")


# ---------- manifest + verify-or-refuse ----------

def test_build_manifest_records_seed_schema_and_fingerprint():
    m = build_manifest("unit_x", RECIPE, seed=20260625)
    assert m["unit"] == "unit_x" and m["seed"] == 20260625
    assert m["schema"] == "motifbo-input-manifest-v1"
    assert len(m["content_fingerprint"]) == 64 and m["n_args"] == 1


def test_verify_roundtrips_on_the_committed_recipe():
    m = build_manifest("unit_x", RECIPE, seed=1)
    assert verify_input(RECIPE, m) is True


def test_verify_refuses_on_recipe_drift():
    m = build_manifest("unit_x", RECIPE, seed=1)
    with pytest.raises(InputDriftError, match="recipe hash drift"):
        verify_input(RECIPE + "# a harmless-looking edit\n", m)


def test_verify_refuses_on_content_drift():
    # recipe hash still matches (so we reach the content check), but the committed
    # fingerprint differs — simulates a numpy RNG-stream skew / non-determinism.
    m = build_manifest("unit_x", RECIPE, seed=1)
    tampered = dict(m, content_fingerprint="0" * 64)
    with pytest.raises(InputDriftError, match="fingerprint drift"):
        verify_input(RECIPE, tampered)


# ---------- driver: verify BEFORE any timed run ----------

def test_measure_paired_endpoint_refuses_before_spawning_a_subprocess():
    called = {"n": 0}
    bad = dict(build_manifest("u", RECIPE, 1), content_fingerprint="0" * 64)
    with pytest.raises(InputDriftError):
        measure_paired_endpoint(SLEEP_KERNEL, "kernel", RECIPE, 4, bad,
                                _measure=canned_fake(called=called), n_subproc=3, policy=None)
    assert called["n"] == 0                 # NO subprocess was spawned — refused before timing


def test_measure_paired_endpoint_runs_and_stamps_manifest_when_input_matches():
    called = {"n": 0}
    m = build_manifest("u", RECIPE, 1)
    res = measure_paired_endpoint(SLEEP_KERNEL, "kernel", RECIPE, 4, m,
                                  _measure=canned_fake(called=called), n_subproc=3, policy=None)
    assert called["n"] == 3
    assert res["endpoint_ns"] == 100.0
    assert res["input_manifest"]["content_fingerprint"] == m["content_fingerprint"]


# ---------- pairing preserved through median-of-3 + across configs ----------

def test_all_three_subprocesses_see_byte_identical_input():
    fps = []
    m = build_manifest("u", RECIPE, 1)
    measure_paired_endpoint(SLEEP_KERNEL, "kernel", RECIPE, 4, m,
                            _measure=canned_fake(record_fps=fps), n_subproc=3, policy=None)
    assert len(fps) == 3 and len(set(fps)) == 1            # all 3 subprocesses: same input bytes
    assert fps[0] == m["content_fingerprint"]


def test_input_is_config_independent_so_pairing_holds_across_configs():
    # The "config" is the compiler-directive .so build, NOT the input. The same recipe must
    # yield the same input fingerprint for config A and config B -> paired comparison is valid.
    m = build_manifest("u", RECIPE, 1)
    fp_a, fp_b = [], []
    measure_paired_endpoint("config_A.so", "kernel", RECIPE, 4, m,
                            _measure=canned_fake(record_fps=fp_a), n_subproc=3, policy=None)
    measure_paired_endpoint("config_B.so", "kernel", RECIPE, 4, m,
                            _measure=canned_fake(record_fps=fp_b), n_subproc=3, policy=None)
    assert set(fp_a) == set(fp_b) == {m["content_fingerprint"]}


# ---------- integration: real numpy recipe determinism (what pairing relies on) ----------

def test_real_driver_recipe_regenerates_byte_identically():
    # The pairing guarantee rests on the recipe regenerating bit-identically in every fresh
    # subprocess. Prove it on the real drivers.py recipe (numpy default_rng is reproducible).
    from motifbo.timing.drivers import setup_code
    sc = setup_code("pava", {"n": 50_000})
    m = build_manifest("pava", sc, seed=20260611)
    assert verify_input(sc, m) is True                    # second materialization == first
    a1, _ = materialize(sc); a2, _ = materialize(sc)
    assert fingerprint_args(a1) == fingerprint_args(a2)   # deterministic across re-exec
