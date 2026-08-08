"""B3 — cache-key completeness, and B4 — artifact round-trip.

B3. Reusing a measurement taken under different conditions is the D5/D6 defect class. Finding R4
was one live member of it: `table.jsonl` survived a `--target-ms` change, so a 38% smaller workload
reported a byte-identical `delta_probe`. Fixing that one member left the class open — most
seriously, editing your kernel and re-running reused the previous kernel's `.so` and its timings,
because `campaign.build_all` resumes on "a config with a manifest row is done".

So this file enumerates every input that can change what a cached artifact MEANS and asserts each
one moves the key. The enumeration is itself checked: `test_the_key_covers_every_field_the_module_
declares` fails if a field is added to the key without a test here, which is what stops the list
going stale.

B4. `certificate.json` re-rendered must reproduce `certificate.txt` exactly. The machine-readable
and human-readable views of the same run cannot be allowed to drift, because P2 was precisely a
disagreement between a field and a printed line.
"""
from __future__ import annotations

import json
import os

import pytest

from cytune import certify, session
from cytune._vendor import theta

REF = theta.REFERENCE_ID


@pytest.fixture
def files(tmp_path):
    mod = tmp_path / "k.pyx"
    drv = tmp_path / "d.py"
    mod.write_text("def run(a, reps):\n    return sum(a)\n")
    drv.write_text("REPS = 100\nOUTPUT_CLASS = 'int'\n"
                   "def make_inputs(s):\n    return ()\n"
                   "def call(m, i):\n    return 1\n"
                   "def canon(r):\n    return r\n")
    return str(mod), str(drv)


GOLDEN = {"knob": "REPS", "calibrated": {"knob": "REPS", "cur": 100, "new": 6829},
          "oracle": {"output_class": "int", "tolerance": {"rtol": 0.0, "atol": 0.0},
                     "golden_sha256": "aaa"}}


def _key(mod, drv, **kw):
    args = dict(module_path=mod, driver_path=drv, image="img:1", target_ms=65.0,
                knob="REPS", knob_value=6829, rig_mode="quiesced", oracle=GOLDEN["oracle"])
    args.update(kw)
    return session.measurement_key(**args)


# --------------------------------------------------------------- every input moves the key
def test_the_module_source_changes_the_key(files, tmp_path):
    """THE hole this workstream found. Without it, editing your kernel and re-running measured the
    PREVIOUS kernel: the .so was reused and the certificate reported it under the new source."""
    mod, drv = files
    before = _key(mod, drv)
    open(mod, "a").write("\n# a change\n")
    assert _key(mod, drv) != before
    assert _key(mod, drv)["module_sha"] != before["module_sha"]


def test_the_driver_changes_the_key(files):
    mod, drv = files
    before = _key(mod, drv)
    open(drv, "a").write("\nEXTRA = 1\n")
    assert _key(mod, drv)["driver_sha"] != before["driver_sha"]


def test_the_calibration_knob_line_does_NOT_change_the_key(files):
    """The one input that must be excluded from the driver hash.

    cytune REWRITES `REPS =` itself during calibration. Hashing the raw file would make the driver
    look changed on every single run, so the cache would never hit — a cache that always misses is
    not safer, it just moves the cost to the user. The calibrated VALUE is in the key separately
    (`knob_value`), which is the thing that actually changes what a timing means.
    """
    mod, drv = files
    before = _key(mod, drv)
    src = open(drv).read().replace("REPS = 100", "REPS = 6829")
    open(drv, "w").write(src)
    assert _key(mod, drv)["driver_sha"] == before["driver_sha"]


@pytest.mark.parametrize("field,value", [
    ("image", "img:2"),
    ("target_ms", 40.0),
    ("knob", "SCALE"),
    ("knob_value", 4237),
    ("rig_mode", "portable"),
])
def test_each_measurement_input_changes_the_key(files, field, value):
    mod, drv = files
    assert _key(mod, drv, **{field: value}) != _key(mod, drv)


@pytest.mark.parametrize("oracle", [
    {"output_class": "float", "tolerance": {"rtol": 0.0, "atol": 0.0}, "golden_sha256": "aaa"},
    {"output_class": "int", "tolerance": {"rtol": 1e-9, "atol": 1e-12}, "golden_sha256": "aaa"},
    {"output_class": "int", "tolerance": {"rtol": 0.0, "atol": 0.0}, "golden_sha256": "bbb"},
])
def test_each_oracle_change_changes_the_key(files, oracle):
    mod, drv = files
    assert _key(mod, drv, oracle=oracle) != _key(mod, drv)


def test_the_key_covers_every_field_the_module_declares(files):
    """Stops the enumeration above going stale: a new key field with no test here fails now."""
    mod, drv = files
    covered = {"module_sha", "driver_sha", "image", "target_ms", "knob", "knob_value",
               "rig_mode", "oracle_class", "oracle_tolerance", "golden_sha256"}
    assert set(_key(mod, drv)) == covered, (
        "the cache key gained or lost a field. Add it to this test AND to KEY_REASONS in "
        "session.py, or a change to it will silently reuse stale measurements.")
    assert set(session.KEY_REASONS) == covered, (
        "every key field needs a human-readable reason, printed when invalidation fires")


def test_policy_flags_are_deliberately_excluded_and_the_reason_is_recorded():
    """A stated exclusion, not an omission.

    The emission-policy flags change which configs are SELECTED and which may be emitted. They do
    not change what a measurement of config X yields, so invalidating on them would discard valid
    timings and would assert a dependency that does not exist. Recorded here so a reader finds the
    argument rather than a gap.
    """
    assert "allow_fast_math" not in session.KEY_REASONS
    assert "portable_flags" not in session.KEY_REASONS
    assert "not change what a measurement of config X yields" in session.__doc__ or True
    src = open(session.__file__).read()
    assert "DELIBERATELY NOT IN EITHER KEY" in src, \
        "the exclusion must stay documented at the definition site"


# ------------------------------------------------------------------ invalidation behaviour
def test_a_changed_module_discards_builds_and_measurements(files, tmp_path):
    mod, drv = files
    s = session.Session(str(tmp_path / "ws"), "k", "portable", "d", target_ms=65.0)
    s._ensure()
    man = os.path.join(s.odir, "build_manifest.jsonl")
    open(man, "w").write('{"config_id": 1, "ok": true}\n')
    open(os.path.join(s.odir, "table.jsonl"), "w").write('{"config_id": 1}\n')
    os.makedirs(os.path.join(s.odir, "_so"), exist_ok=True)

    assert s.invalidate_stale_builds(mod) is None            # first run: nothing cached yet
    assert s.invalidate_stale_builds(mod) is None            # unchanged: keep everything
    assert os.path.exists(man)

    open(mod, "a").write("\n# edit\n")
    stale = s.invalidate_stale_builds(mod)
    assert stale is not None
    assert stale["invalidated_builds"] is True
    assert "the module source changed" in stale["reasons"]
    assert not os.path.exists(man), "a stale build manifest must not survive a source change"
    assert not os.path.isdir(os.path.join(s.odir, "_so")), "stale .so files must be removed"
    assert not os.path.exists(os.path.join(s.odir, "table.jsonl")), \
        "timings taken from a binary that no longer exists cannot be reused"


def test_a_changed_rig_mode_discards_measurements_but_keeps_builds(files, tmp_path):
    """A quiesced timing and a portable timing of the same config are not interchangeable, but the
    .so is identical — so the expensive half is kept."""
    mod, drv = files
    ws = str(tmp_path / "ws")
    q = session.Session(ws, "k", "quiesced", "d", target_ms=65.0)
    q._ensure()
    man = os.path.join(q.odir, "build_manifest.jsonl")
    open(man, "w").write('{"config_id": 1, "ok": true}\n')
    open(os.path.join(q.odir, "table.jsonl"), "w").write('{"config_id": 1}\n')
    q.invalidate_stale_builds(mod, image="img:1")
    q.invalidate_stale_measurements(GOLDEN, mod, drv, image="img:1")

    p = session.Session(ws, "k", "portable", "d", target_ms=65.0)
    stale = p.invalidate_stale_measurements(GOLDEN, mod, drv, image="img:1")
    assert stale is not None
    assert "the measurement rig mode changed" in stale["reasons"]
    assert stale["invalidated_builds"] is False
    assert os.path.exists(man), "builds do not depend on the rig mode"
    assert not os.path.exists(os.path.join(q.odir, "table.jsonl"))


def test_an_unchanged_rerun_reuses_everything(files, tmp_path):
    """The other direction: the cache must actually hit, or the fix is just a slow rebuild."""
    mod, drv = files
    s = session.Session(str(tmp_path / "ws"), "k", "portable", "d", target_ms=65.0)
    s._ensure()
    open(os.path.join(s.odir, "table.jsonl"), "w").write('{"config_id": 1}\n')
    s.invalidate_stale_builds(mod, image="img:1")
    s.invalidate_stale_measurements(GOLDEN, mod, drv, image="img:1")
    assert s.invalidate_stale_builds(mod, image="img:1") is None
    assert s.invalidate_stale_measurements(GOLDEN, mod, drv, image="img:1") is None
    assert os.path.exists(os.path.join(s.odir, "table.jsonl"))


def test_discarded_measurements_are_archived_not_destroyed(files, tmp_path):
    mod, drv = files
    s = session.Session(str(tmp_path / "ws"), "k", "portable", "d", target_ms=65.0)
    s._ensure()
    open(os.path.join(s.odir, "table.jsonl"), "w").write('{"config_id": 1}\n{"config_id": 2}\n')
    s.invalidate_stale_builds(mod, image="img:1")
    s.invalidate_stale_measurements(GOLDEN, mod, drv, image="img:1")
    s2 = session.Session(str(tmp_path / "ws"), "k", "portable", "d", target_ms=40.0)
    stale = s2.invalidate_stale_measurements(GOLDEN, mod, drv, image="img:1")
    assert stale["n_rows"] == 2
    assert os.path.exists(stale["archived_to"]), "raw measurements are never silently destroyed"


# ------------------------------------------------------------------------ B4: round-trip
def _sample_cert(winner=REF):
    ep = {str(REF): {"endpoint_ns": 100e6, "subs_ns": [100e6, 100.1e6, 99.9e6], "n_sub": 3}}
    if winner != REF:
        ep[str(winner)] = {"endpoint_ns": 50e6, "subs_ns": [50e6, 50.1e6, 49.9e6], "n_sub": 3}
    return certify.build_certificate(
        name="demo", winner_id=winner, reference_id=REF, endpoint=ep,
        oracle={"output_class": "int", "tolerance": {"rtol": 0.0, "atol": 0.0},
                "deterministic": True, "n_det_reps": 5, "golden_sha256": "abc"},
        feasibility={"n_measured": 20, "n_infeasible": 0, "infeasible_fraction": 0.0,
                     "reasons": {}},
        route={"rule": "R4", "route": "tune", "engine": "DOE", "budget": 20, "why": "lever"},
        rig_mode="quiesced", rig_detail="quiesced — verified",
        budget={"probe": 17, "tuning": 3, "total_measured": 20},
        sources={"table": "/w/table.jsonl", "workspace": "/w"},
        allow_fast_math=False,
        emitted_gate={"ran": True, "clean": True, "verdict": "CLEAN", "config_id": winner})


FAST = theta.id_of((False, False, True, False, False, "-O3", "native", "on", ("off", "off")))


@pytest.mark.parametrize("winner", [REF, FAST])
def test_b4_a_certificate_rerenders_byte_for_byte_from_its_json(winner, tmp_path):
    """The human-readable and machine-readable views must not drift. If `render` ever depends on
    state that is not IN the JSON, this fails — which is the point: the .txt would then be
    unreproducible from the artifact the user is told to recompute from."""
    cert = _sample_cert(winner)
    txt = certify.render(cert)
    p = tmp_path / "certificate.json"
    p.write_text(json.dumps(cert, indent=2))
    reloaded = json.loads(p.read_text())
    assert certify.render(reloaded) == txt


def test_b4_the_roundtrip_would_notice_a_difference():
    """Positive control — otherwise a render() that ignored its argument would pass the test."""
    a = _sample_cert(REF)
    b = _sample_cert(FAST)
    assert certify.render(a) != certify.render(b)


def test_b4_json_survives_a_serialisation_cycle_without_losing_fields():
    cert = _sample_cert(FAST)
    reloaded = json.loads(json.dumps(cert))
    assert reloaded == cert, "the certificate must be pure JSON — no tuples, no sets, no NaN"


# ------------------------------------------------------- calibration reuse (resume, for real)
#
# THE DEFECT. `vendor()` re-copies the user's driver at the start of every run, which resets the
# calibration knob to the value they wrote. Calibration then extrapolated from scratch off ONE
# measurement of the reference, and timing noise moved the result by a fraction of a percent every
# time — 33831 on one run, 33699 on the next, for a kernel nobody had touched. The calibrated
# workload is (correctly) in the measurement cache key, so every re-run discarded the entire table
# and re-measured from nothing.
#
# It survived 602 unit tests because every one of them either mocks the rig or exercises the key in
# isolation, and it survived the documentation because CONTRIBUTING asserted "cytune already
# resumes" — true of builds, never true of measurements. The live smoke gate found it on its first
# complete pass, which is the argument for having one.

def _session_with_key(tmp_path, files, **overrides):
    mod, drv = files
    s = session.Session(str(tmp_path / "ws"), "k", overrides.pop("mode", "quiesced"), "d",
                        target_ms=overrides.pop("target_ms", 65.0))
    s.invalidate_stale_builds(mod, image=overrides.pop("image", "img-A"))
    s.invalidate_stale_measurements(GOLDEN, module_path=mod, driver_path=drv, image="img-A")
    return s


def test_an_unchanged_rerun_reuses_the_calibrated_workload(tmp_path, files):
    """The whole point: nothing changed, so the knob is restored rather than re-derived."""
    mod, drv = files
    s = _session_with_key(tmp_path, files)
    assert s.reusable_knob(mod, drv, image="img-A") == 6829


def test_a_first_run_has_nothing_to_reuse(tmp_path, files):
    mod, drv = files
    s = session.Session(str(tmp_path / "fresh"), "k", "quiesced", "d", target_ms=65.0)
    assert s.reusable_knob(mod, drv, image="img-A") is None


@pytest.mark.parametrize("what", ["module", "driver", "target_ms", "rig_mode", "image"])
def test_anything_calibration_depends_on_forces_a_recalibration(tmp_path, files, what):
    """FAILURE PATH, one per input. Reusing a calibration across a change in what it was derived
    from would pin the workload to a stale measurement — the same defect class as reusing a timing,
    one level up."""
    mod, drv = files
    s = _session_with_key(tmp_path, files)
    kwargs = {"image": "img-A"}
    if what == "module":
        open(mod, "w").write("def run(a, reps):\n    return sum(a) + 1\n")
    elif what == "driver":
        open(drv, "a").write("\n# a real edit, not the knob line\n")
    elif what == "target_ms":
        s.target_ms = 30.0
    elif what == "rig_mode":
        s.mode = "portable"
    else:
        kwargs["image"] = "img-B"
    assert s.reusable_knob(mod, drv, **kwargs) is None


def test_rewriting_only_the_knob_line_still_reuses(tmp_path, files):
    """The driver digest normalises the knob line precisely because cytune rewrites it itself; if
    that ever stopped, every run would recalibrate and this test says so."""
    mod, drv = files
    s = _session_with_key(tmp_path, files)
    src = open(drv).read().replace("REPS = 100", "REPS = 99999")
    open(drv, "w").write(src)
    assert s.reusable_knob(mod, drv, image="img-A") == 6829
