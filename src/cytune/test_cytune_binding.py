"""I4 — artifact binding. Every test here drives a FAILURE path.

The class these close was named by the adversary who found it: *every check verifies the DOCUMENT
against the config_id, and nothing verifies the config_id against the ARTIFACT actually built,
gated and timed.* A test that only shows a good run passing would prove nothing about that — the
good run passed before I4 existed too. So each invariant is given a document that is internally
perfect and describes a run that did not happen, and must refuse it.

The two end-to-end tests at the bottom need podman and the pinned image; they skip cleanly without
it and are part of the pre-tag smoke gate (scripts/release/smoke.sh), which is where a green suite
over a broken rig gets caught.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess

import pytest

from cytune import binding, certify, rig, session
from cytune._vendor import theta

REF = theta.REFERENCE_ID


def _rec(cid, artifact="a" * 64, source="s" * 64):
    return {"config_id": cid, "combo": binding.combo_key(cid),
            "artifact_sha256": artifact, "source_sha256": source,
            "so_path": f"/work/_so/kernel_{cid}.so", "build_argv": ["gcc-13", "-o", "x"],
            "image_digest": rig.PINNED_IMAGE_DIGEST}


def _ep(artifact="a" * 64, subs=(1e6, 1e6, 1e6), rig_fp="no_turbo=1 gov_cpu3=performance"):
    return {"feasible": True, "endpoint_ns": 1e6, "subs_ns": list(subs), "n_sub": len(subs),
            "wall_ns": [1e6 * 30 + 2e8] * len(subs), "K": 30,
            "artifact_sha256": artifact, "rig": rig_fp}


# --------------------------------------------------------------------------------- I4.1
def test_i4_1_a_swapped_artifact_is_refused():
    """The document is flawless and describes a binary that was never timed.

    This is the shape of every H-finding: config 1392's directives, config 1392's flags, config
    1392's id — and a measurement of something else. Nothing that reasons from the id can see it.
    """
    artifacts = {1392: _rec(1392, artifact="1" * 64)}
    with pytest.raises(binding.BindingViolation) as e:
        binding.assert_emission_bound(config_id=1392, artifacts=artifacts,
                                      endpoint=_ep(artifact="2" * 64))
    assert e.value.invariant == "I4.1"
    assert "BUILT" in str(e.value) and "timed" in str(e.value)


def test_i4_1_an_unbuilt_config_cannot_be_emitted():
    with pytest.raises(binding.BindingViolation) as e:
        binding.assert_emission_bound(config_id=7, artifacts={}, endpoint=_ep())
    assert e.value.invariant == "I4.1"


def test_i4_1_an_endpoint_that_recorded_no_artifact_is_refused():
    """A workspace from before I4 has measurements with no artifact hash. Reusing one would put a
    speedup in a certificate with nothing tying it to a binary, which is precisely the state this
    release closes — so it refuses rather than accepting the older, weaker record."""
    with pytest.raises(binding.BindingViolation) as e:
        binding.assert_emission_bound(config_id=1392, artifacts={1392: _rec(1392)},
                                      endpoint={"feasible": True, "endpoint_ns": 1.0})
    assert e.value.invariant == "I4.1"


def test_i4_1_passes_when_the_artifact_matches():
    got = binding.assert_emission_bound(config_id=1392, artifacts={1392: _rec(1392)},
                                        endpoint=_ep())
    assert got == "a" * 64


# --------------------------------------------------------------------------------- I4.2
def _collapsed(n_combos):
    """n distinct directive combinations that all produced the SAME generated C."""
    cids = []
    for cid in range(theta.N_CONFIGS):
        k = binding.combo_key(cid)
        if k not in {binding.combo_key(c) for c in cids}:
            cids.append(cid)
        if len(cids) >= n_combos:
            break
    return {c: _rec(c, artifact=f"{c:064d}", source="same" * 16) for c in cids}


def test_i4_2_total_degeneracy_is_refused_with_the_blacklist_off():
    """THE GENERIC CHECK, STANDING ALONE.

    `session.check_pinned_directives` is not called anywhere in this test. The only thing observed
    is the consequence — every directive combination produced byte-identical C — and that is what
    refuses. This is what makes the check cover mechanisms nobody has found yet: a setup.py
    `compiler_directives=` block, an included .pxi with its own header, a cythonize wrapper.
    """
    report = binding.degeneracy(_collapsed(8))
    assert report["total_collapse"] is True
    assert report["n_distinct_generated_sources"] == 1
    with pytest.raises(binding.BindingViolation) as e:
        binding.assert_no_total_degeneracy(report)
    assert e.value.invariant == "I4.2"
    # It must name BOTH causes, because it genuinely cannot tell them apart and saying only the
    # accusatory one would be a claim it cannot support.
    assert "H12" in str(e.value) and "no code these directives affect" in str(e.value)


def test_i4_2_does_not_fire_on_a_single_combination():
    """A build of one directive combination trivially has one source hash. Refusing there would
    make `--preset quick` on a small budget impossible and would say nothing about degeneracy."""
    report = binding.degeneracy(_collapsed(1))
    assert report["total_collapse"] is False
    binding.assert_no_total_degeneracy(report)


def test_i4_2_partial_collapse_is_reported_not_refused():
    """One inert directive is a fact about the user's kernel, not an error. It goes in the
    certificate: `initializedcheck` costs nothing here because there is nothing to check."""
    recs = {}
    for cid in range(theta.N_CONFIGS):
        combo = binding.combo_key(cid)
        if combo in {r["combo"] for r in recs.values()}:
            continue
        # Generated C depends on every directive EXCEPT the fourth (initializedcheck).
        key = combo[:3] + "x" + combo[4:]
        recs[cid] = _rec(cid, artifact=f"{cid:064d}", source=hashlib.sha256(key.encode()).hexdigest())
        if len(recs) >= 32:
            break
    report = binding.degeneracy(recs)
    assert report["total_collapse"] is False
    assert report["directives_inert"] == ["initializedcheck"]
    assert set(report["directives_live"]) == {"boundscheck", "wraparound", "cdivision", "nonecheck"}
    binding.assert_no_total_degeneracy(report)


# --------------------------------------------------------------------------------- I4.3
def test_i4_3_a_gate_on_another_source_tree_is_refused():
    """A CLEAN verdict about a different source is not a verdict about this one."""
    gate = {"ran": True, "clean": True, "config_id": 1392, "source_tree_sha256": "b" * 64,
            "image_digest": rig.PINNED_IMAGE_DIGEST}
    with pytest.raises(binding.BindingViolation) as e:
        binding.assert_gate_bound(config_id=1392, gate=gate, source_tree_sha256="a" * 64,
                                  pinned_image_digest=rig.PINNED_IMAGE_DIGEST)
    assert e.value.invariant == "I4.3"


def test_i4_3_a_gate_on_another_config_is_refused():
    gate = {"ran": True, "clean": True, "config_id": 999, "source_tree_sha256": "a" * 64,
            "image_digest": rig.PINNED_IMAGE_DIGEST}
    with pytest.raises(binding.BindingViolation) as e:
        binding.assert_gate_bound(config_id=1392, gate=gate, source_tree_sha256="a" * 64,
                                  pinned_image_digest=rig.PINNED_IMAGE_DIGEST)
    assert e.value.invariant == "I4.3"


def test_i4_3_a_retagged_image_does_not_buy_a_pass():
    """H6, closed properly.

    The first fix compared the image NAME against the pinned name, which `podman tag stub
    localhost/motifbo-env:phase1` defeats in one command — the name matches and the stub runs. Here
    the name is irrelevant: the digest is not the pinned digest, so the verdict is marked
    non-authoritative no matter what it is called.
    """
    gate = {"ran": True, "clean": True, "config_id": 1392, "source_tree_sha256": "a" * 64,
            "image": "localhost/motifbo-env:phase1",        # the PINNED NAME
            "image_digest": "sha256:" + "f" * 64}           # a different image
    out = binding.assert_gate_bound(config_id=1392, gate=gate, source_tree_sha256="a" * 64,
                                    pinned_image_digest=rig.PINNED_IMAGE_DIGEST)
    assert out["authoritative"] is False
    assert out["image_overridden"] is True
    assert "digest is what is compared" in out["warning"]


# --------------------------------------------------------------------------------- I4.4
def test_i4_4_a_quiesced_claim_over_an_ungated_row_is_refused():
    """`measure_wrap` exports RIG_FINGERPRINT only after its asserts pass. A row stamped UNGATED
    was measured outside it, and reporting that as decision-grade is a claim about the host that
    nothing verified."""
    with pytest.raises(binding.BindingViolation) as e:
        binding.assert_rig_bound(rig_mode="quiesced",
                                 endpoint_records={"288": _ep(rig_fp=binding.UNGATED)})
    assert e.value.invariant == "I4.4"


def test_i4_4_a_portable_claim_over_a_gated_row_is_refused():
    """The other direction is also a document that does not describe its run, and it is a real
    shape: `--rig portable` was forced but the measurement went through the wrapper anyway."""
    with pytest.raises(binding.BindingViolation) as e:
        binding.assert_rig_bound(rig_mode="portable", endpoint_records={"288": _ep()})
    assert e.value.invariant == "I4.4"


def test_i4_4_agreement_passes():
    assert binding.assert_rig_bound(rig_mode="portable",
                                    endpoint_records={"288": _ep(rig_fp=binding.UNGATED)})


# ------------------------------------------------------------------- C1 ratio corroboration
def _endpoint(median_ns, wall_extra_ns, n=3, k=30, warmup=5, ref_median=None):
    """A synthetic endpoint record whose wall clock is internally consistent with `median_ns`."""
    base = ref_median if ref_median is not None else median_ns
    walls = [k * median_ns + warmup * base + wall_extra_ns for _ in range(n)]
    return {"feasible": True, "endpoint_ns": median_ns, "subs_ns": [median_ns] * n,
            "wall_ns": walls, "K": k, "n_sub": n}


def test_c1_an_honest_measurement_corroborates():
    """Winner genuinely 2x faster: its warmup is genuinely cheaper by warmup x (t_win - t_ref)."""
    ref = _endpoint(60e6, 3e8)
    win = _endpoint(30e6, 3e8, ref_median=30e6)
    out = certify.corroborate_ratio(win, ref)
    assert out["corroborated"] is True


def test_c1_a_driver_that_underreports_its_own_time_is_caught():
    """H1's actual attack: the driver reports a fifth of the time it took.

    The wall clock does not move — the work still happened — so the non-timed remainder balloons by
    K x (t_real - t_reported). `worker.implausible_timings` cannot see this: the claim is SMALLER
    than the elapsed time, which is exactly what honest spawn overhead looks like. The overhead
    comparison sees it because the reference's remainder did not balloon.
    """
    ref = _endpoint(60e6, 3e8)
    win = dict(_endpoint(60e6, 3e8, ref_median=60e6))     # really just as slow...
    win["subs_ns"] = [12e6] * 3                            # ...but reports 5x faster
    win["endpoint_ns"] = 12e6
    out = certify.corroborate_ratio(win, ref)
    assert out["corroborated"] is False
    assert out["residual_ns"] > out["budget_ns"]
    assert "NOT consistent with the wall-clock" in out["reason"]


def test_c1_reports_unavailable_rather_than_passing_when_the_wall_is_missing():
    """None is not a pass — the same rule the sanitizer gate lives under."""
    ref = _endpoint(60e6, 3e8)
    win = {k: v for k, v in _endpoint(30e6, 3e8).items() if k != "wall_ns"}
    out = certify.corroborate_ratio(win, ref)
    assert out["corroborated"] is None


def test_c1_warmup_constant_matches_the_measurement_rig():
    """The corroboration arithmetic assumes the child does `warmup` untimed calls before timing.
    If the rig ever changes that, this prediction silently becomes wrong in the direction that
    withholds honest speedups."""
    import campaign
    assert certify.ENDPOINT_WARMUP == campaign.WARMUP


# ------------------------------------------------------------------------- tree/artifact hashing
def test_the_source_tree_digest_ignores_build_output(tmp_path):
    """The host hashes the workspace kernel dir and the container hashes /kdir; if a .so dropped in
    by a build changed the answer, I4.3 could never pass on a real run."""
    d = tmp_path / "k"
    (d / "closure").mkdir(parents=True)
    (d / "closure" / "a.pyx").write_text("def f(): pass\n")
    before = binding.tree_sha256(str(d))
    (d / "closure" / "a.c").write_text("/* generated */\n")
    (d / "_so").mkdir()
    (d / "_so" / "a.so").write_bytes(b"\x7fELF")
    (d / "closure" / "__pycache__").mkdir()
    (d / "closure" / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    assert binding.tree_sha256(str(d)) == before
    (d / "closure" / "a.pyx").write_text("def f(): return 1\n")
    assert binding.tree_sha256(str(d)) != before


def test_the_artifact_record_is_dropped_when_builds_are_invalidated(tmp_path):
    """An artifact record whose .so has been deleted would satisfy I4.1 for a file that is gone."""
    sess = session.Session(str(tmp_path / "ws"), "k", "portable", "test")
    sess._ensure()
    binding.append(sess.odir, [_rec(288)])
    assert binding.read(sess.odir)
    pyx = tmp_path / "k.pyx"
    pyx.write_text("def run(a):\n    return a\n")
    sess.invalidate_stale_builds(str(pyx), image="image-A")
    pyx.write_text("def run(a):\n    return a + 1\n")
    sess.invalidate_stale_builds(str(pyx), image="image-A")
    assert binding.read(sess.odir) == {}


# ===================================================================== end-to-end (needs podman)
HAVE_PODMAN = shutil.which("podman") and subprocess.run(
    ["podman", "image", "exists", rig.IMAGE], capture_output=True).returncode == 0
needs_image = pytest.mark.skipif(not HAVE_PODMAN,
                                 reason="needs podman and the pinned image")

_KERNEL = """
def run(double[::1] a):
    cdef Py_ssize_t i
    cdef double s = 0.0
    for i in range(a.shape[0]):
        s += a[i]
    return s
"""


def _cythonize_in_image(tmp_path, header, combos):
    """Cythonize one .pyx under several directive combinations and return {combo: sha256(.c)}."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "kernel.pyx"
    src.write_text((header + "\n" if header else "") + _KERNEL)
    out = {}
    for combo in combos:
        bc, wa, cd, ic, nc = (v == "1" for v in combo)
        cpath = f"/w/k_{combo}.c"
        cmd = ["podman", "run", "--rm", "--network=none", "--security-opt", "label=disable",
               "-v", f"{tmp_path}:/w", rig.IMAGE, "cython", "-3",
               "-X", f"boundscheck={bc}", "-X", f"wraparound={wa}", "-X", f"cdivision={cd}",
               "-X", f"initializedcheck={ic}", "-X", f"nonecheck={nc}",
               "/w/kernel.pyx", "-o", cpath]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, r.stderr[-500:]
        out[combo] = binding.sha256_file(str(tmp_path / f"k_{combo}.c"))
    return out


# One base combination plus a single flip of each directive, so every directive has exactly one
# pair to be judged on. A sparser set leaves directives "undetermined", which is a different
# statement from "inert" and must not be conflated with it.
_SINGLE_FLIP = ["11111", "01111", "10111", "11011", "11101", "11110"]


def _records_from(sources):
    recs = {}
    for cid in range(theta.N_CONFIGS):
        k = binding.combo_key(cid)
        if k in sources and k not in {r["combo"] for r in recs.values()}:
            recs[cid] = _rec(cid, artifact=f"{cid:064d}", source=sources[k])
    return recs


@needs_image
def test_the_degeneracy_check_names_the_directives_a_header_neutralised(tmp_path):
    """H12's mechanism, MEASURED, and identified without knowing the mechanism.

    WHAT THIS TEST ESTABLISHED, and it is not what was expected. The brief's rule was "all 32
    combinations collapsing to ONE class => refuse". Run against the real H12 header on a real
    kernel, that rule does not fire: `# cython: boundscheck=False, wraparound=False` neutralises
    two directives, and the other three still change the generated C, so the partition has several
    classes and total collapse is False. The rule as stated would have missed the exact defect it
    was written to generalise.

    What DOES work is per-directive: flipping `boundscheck` changes nothing and flipping
    `cdivision` does, and that is observable without knowing why. So the generic detector reports
    which directives were neutralised BY NAME, total collapse remains the refusal condition, and
    `session.check_pinned_directives` — now scanning the whole source tree, not just the named
    .pyx — is what refuses a partial pin outright.

    `check_pinned_directives` is never called here. Everything asserted below comes from hashing
    generated C.
    """
    pinned = _cythonize_in_image(tmp_path / "p", "# cython: boundscheck=False, wraparound=False",
                                 _SINGLE_FLIP)
    report = binding.degeneracy(_records_from(pinned))
    assert "boundscheck" in report["directives_inert"], report
    assert "wraparound" in report["directives_inert"], report
    # ...and the finding that made this test worth writing:
    assert report["total_collapse"] is False, (
        "if this ever becomes True the brief's original rule would have sufficed; it did not")


@needs_image
def test_an_unpinned_module_shows_those_same_directives_live(tmp_path):
    """The NEGATIVE control, and the half that makes the positive one mean anything.

    A detector that reports every directive inert would 'catch' every pin and be worthless. The
    same kernel, same combinations, no header: boundscheck and wraparound must come back LIVE.
    """
    plain = _cythonize_in_image(tmp_path / "n", None, _SINGLE_FLIP)
    report = binding.degeneracy(_records_from(plain))
    assert "boundscheck" in report["directives_live"], report
    assert "wraparound" in report["directives_live"], report
    assert report["total_collapse"] is False
    binding.assert_no_total_degeneracy(report)


@needs_image
def test_total_degeneracy_is_refused_end_to_end(tmp_path):
    """A header pinning ALL FIVE directives — the case the refusal condition is for."""
    header = ("# cython: boundscheck=False, wraparound=False, cdivision=True, "
              "initializedcheck=False, nonecheck=False")
    pinned = _cythonize_in_image(tmp_path / "a", header, _SINGLE_FLIP)
    assert len(set(pinned.values())) == 1, "pinning all five must make every flip identical"
    report = binding.degeneracy(_records_from(pinned))
    assert report["total_collapse"] is True
    with pytest.raises(binding.BindingViolation) as e:
        binding.assert_no_total_degeneracy(report)
    assert e.value.invariant == "I4.2"


@needs_image
def test_the_parallel_scheduler_produces_byte_identical_artifacts(tmp_path):
    """THE POSITIVE CONTROL FOR B3.

    `worker._build_all` reschedules the study's build — it parallelises the cythonize phase that
    `campaign.build_all` runs serially, which is where 71% of a tuning run's wall clock was going.
    Rescheduling a build is only safe if the bytes are the same, and "only if" is not an argument,
    it is a test: the same configs are built both ways into separate workspaces and every artifact
    hash must match.
    """
    kdir = tmp_path / "_kernels" / "k"
    kdir.mkdir(parents=True)
    (kdir / "kernel.pyx").write_text(_KERNEL)
    (kdir / "driver.py").write_text(
        "import numpy as np\nREPS = 1\nOUTPUT_CLASS = 'float'\n"
        "def make_inputs(seed):\n    return np.arange(1000, dtype=np.float64)\n"
        "def call(mod, x):\n    return mod.run(x)\n"
        "def canon(r):\n    return np.asarray([r], dtype=np.float64)\n")

    ids = [REF, 0, 1, 100, 800, 1392]
    hashes = {}
    for label, scheduler in (("study", "campaign"), ("cytune", "worker")):
        out = tmp_path / f"out_{label}"
        out.mkdir()
        code = (
            "import json,sys;sys.path.insert(0,'/opt/cytune');"
            "from cytune import binding, worker;import campaign;"
            f"ids={ids!r};"
            + ("campaign.build_all('/kdir','/out',ids)" if scheduler == "campaign"
               else "worker._build_all('/kdir','/out',ids)") +
            ";import build as B;"
            "man={json.loads(l)['config_id']: json.loads(l) for l in open('/out/build_manifest.jsonl')};"
            "print(json.dumps({str(c): binding.sha256_file(man[c]['so_path']) "
            "for c in ids if man[c]['ok']}))")
        r = subprocess.run(
            ["podman", "run", "--rm", "--network=none", "--security-opt", "label=disable",
             "-e", "PYTHONPATH=/opt/cytune",
             "-v", f"{rig.PKG_DIR}:/opt/cytune/cytune:ro",
             "-v", f"{kdir}:/kdir:ro", "-v", f"{out}:/out",
             rig.IMAGE, "python3", "-c", code],
            capture_output=True, text=True, timeout=1800)
        assert r.returncode == 0, r.stderr[-2000:]
        hashes[label] = json.loads(r.stdout.strip().splitlines()[-1])

    assert hashes["study"], "no artifact was built — the control proves nothing"
    assert hashes["study"] == hashes["cytune"], (
        "the parallel scheduler produced different bytes from the study's serial one:\n"
        + "\n".join(f"  {c}: study={hashes['study'].get(c)} cytune={hashes['cytune'].get(c)}"
                    for c in sorted(set(hashes["study"]) | set(hashes["cytune"]))
                    if hashes["study"].get(c) != hashes["cytune"].get(c)))


# ----------------------------------------------------- C1's POWER, pinned rather than described
#
# The corroboration budget is `TOL x claimed_gain`, and the claimed gain is itself what a lying
# driver controls — so the power has a shape, and the shape has to be pinned rather than implied by
# the word "catches".
#
# For a true speedup `r_true` reported as `r_claim`, with the winner really running at `t_ref/r_true`
# and reporting `t_ref/r_claim`, the WARMUP calls also really run at the true speed, so
#
#     residual       = (K + warmup) x (t_real - t_reported)
#     claimed_gain   = K x (t_ref - t_reported)
#     residual/gain  = (1 + warmup/K) x (1/r_true - 1/r_claim) / (1 - 1/r_claim)
#
# (The `1 + warmup/K` factor is why this is stronger than the naive estimate: the five untimed
# warmup calls pay the real cost too, and a driver cannot separate them from the timed region.)
#
# That ratio is `1 + warmup/K` whenever there is NO real speedup at all, whatever is claimed — so
# the entire "this kernel is flat and the driver says otherwise" class, which is the demonstrated
# H1 attack, is caught with more than a factor of two to spare. Inflating an ALREADY-LARGE real
# gain is not caught: a genuine 2x can be reported as 100x. That limit is stated in GUARANTEES N8
# and KNOWN_ISSUES K10 rather than papered over.
#
# TOL cannot simply be tightened. The novice-user agent's HONEST 9.85x run left 38% of its claimed
# gain unexplained — 53 ms of residual against a 10.2 ms process-noise sigma — so TOL=0.25 would
# have withheld a real speedup, and withholding honest results is the failure direction this
# product cannot take.


def _lie(r_true, r_claim, t_ref_ns=65e6, k=30, n=3, warmup=certify.ENDPOINT_WARMUP):
    """An endpoint pair where the winner REALLY runs at t_ref/r_true and REPORTS t_ref/r_claim."""
    t_real, t_rep = t_ref_ns / r_true, t_ref_ns / r_claim
    ref = {"endpoint_ns": t_ref_ns, "subs_ns": [t_ref_ns] * n, "K": k, "n_sub": n,
           "wall_ns": [k * t_ref_ns + warmup * t_ref_ns + 3e8] * n}
    win = {"endpoint_ns": t_rep, "subs_ns": [t_rep] * n, "K": k, "n_sub": n,
           # the wall reflects the time that ACTUALLY elapsed, which the driver cannot alter
           "wall_ns": [k * t_real + warmup * t_real + 3e8] * n}
    return win, ref


def _boundary(r_claim, k=30, warmup=certify.ENDPOINT_WARMUP):
    """The largest true speedup that would still be caught when `r_claim` is reported.

    Derived from the code's own constants, so this cannot drift away from the implementation the
    way a hard-coded table would.
    """
    tol = certify.CORROBORATION_TOL * k / (k + warmup)
    return 1.0 / (tol * (1 - 1 / r_claim) + 1 / r_claim)


@pytest.mark.parametrize("r_claim", [2.0, 5.0, 10.0, 100.0])
def test_c1_catches_any_claim_on_a_kernel_with_no_real_speedup(r_claim):
    """The class the demonstrated attack belongs to, across the whole range of lies."""
    out = certify.corroborate_ratio(*_lie(1.0, r_claim))
    assert out["corroborated"] is False, (r_claim, out["unexplained_fraction_of_claimed_gain"])


@pytest.mark.parametrize("r_claim,r_true,caught", [
    (5.0, 1.0, True),      # flat kernel, 5x claimed — H1 verbatim
    (5.0, 1.5, True),      # a small real gain inflated to 5x
    (5.0, 1.8, True),      # still caught: the boundary at 5x sits at ~1.84
    (5.0, 2.5, False),     # a genuine 2.5x reported as 5x — NOT detected, and stated as such
    (2.0, 1.2, True),
    (100.0, 3.0, False),   # a genuine 3x reported as 100x — the documented blind spot
])
def test_c1_power_curve_is_what_the_documentation_claims(r_claim, r_true, caught):
    """Pins the boundary so it cannot drift away from what GUARANTEES N8 says it is."""
    out = certify.corroborate_ratio(*_lie(r_true, r_claim))
    assert out["corroborated"] is (not caught), (r_true, r_claim, _boundary(r_claim), out)


def test_c1_the_stated_boundary_matches_the_arithmetic():
    """The formula above, checked against the implementation rather than trusted."""
    for r_claim in (1.5, 2.0, 5.0, 10.0, 100.0):
        b = _boundary(r_claim)
        assert certify.corroborate_ratio(*_lie(b * 0.95, r_claim))["corroborated"] is False, b
        assert certify.corroborate_ratio(*_lie(b * 1.05, r_claim))["corroborated"] is True, b


def test_c1_the_blind_spot_is_real_and_is_not_hidden():
    """The honest half of the claim: state the limit as a test so nobody has to take it on trust."""
    assert _boundary(100.0) > 2.0, "a genuine 2x reported as 100x must be documented as UNCAUGHT"
    out = certify.corroborate_ratio(*_lie(2.6, 100.0))
    assert out["corroborated"] is True
    assert out["unexplained_fraction_of_claimed_gain"] < certify.CORROBORATION_TOL


def test_c1_the_noise_floor_comes_from_the_runs_own_measurements():
    """The budget's floor is 3 sigma of the per-process overhead spread this run SAMPLED, not a
    constant. A flat 5%-of-overhead constant left an honest 9.85x run with 24% headroom."""
    win, ref = _lie(1.0, 1.0)                    # identical configs: nothing to explain
    noisy = [1.0e9 + (i % 7) * 4e7 for i in range(30)]
    out = certify.corroborate_ratio(win, ref, screen_overheads=noisy)
    assert out["n_overhead_samples"] == 30
    assert out["noise_sigma_ns"] > 0
    assert out["budget_ns"] >= certify.CORROBORATION_SIGMA * out["noise_sigma_ns"]


# ============================================================ Attack A (focused adversarial re-run)
#
# THE DEFECT, and it was introduced by the fix for H6. `rig.image_digest` memoises {name: digest},
# and the cache is filled by the FIRST container spawn of a run — stage [1/6]. The sanitizer gate
# then asked `is_pinned_image()` minutes later and got that cached, honest digest, while
# `podman run <NAME>` resolved the tag LIVE. One `podman tag stub localhost/motifbo-env:phase1`
# placed between those two moments made the pin answer True while the stub executed: H6 rebuilt on
# top of its own fix, by a cache added for speed.
#
# THE FIX IS NOT "DO NOT CACHE". Resolving fresh at every use has the same gap, just narrower — the
# compare and the run are still two separate resolutions. The fix is to resolve ONCE and then run
# THAT ID, so the image whose digest was compared is by construction the image that executed. A tag
# moved afterwards points somewhere cytune is no longer looking.

def test_attack_a_a_retag_after_resolution_cannot_redirect_the_run(monkeypatch):
    """FAILURE PATH. The tag moves between resolution and use; the run must not follow it."""
    real, stub = rig.PINNED_IMAGE_DIGEST, "sha256:" + "4a" * 32
    live = {"digest": real}
    monkeypatch.setattr(rig, "_DIGEST_CACHE", {})
    monkeypatch.setattr(rig, "_probe_digest", lambda name: live["digest"], raising=False)

    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        class R:
            returncode, stdout, stderr = 0, live["digest"].split(":", 1)[1], ""
        return R()
    monkeypatch.setattr(rig.subprocess, "run", fake_run)

    # t0 — the first container spawn of the run resolves the pin, as `_mounts` does.
    assert rig.image_digest() == real
    # t1 — the attacker re-points the tag. One command, no root, no rebuild.
    live["digest"] = stub
    # t2 — every later container must still be launched by the ID resolved at t0.
    ref = rig.image_ref()
    assert ref == real, "a re-tag redirected the run — this is Attack A"
    assert ref != rig.IMAGE, "the run is launched by tag, so a re-tag can redirect it"


def test_the_image_that_is_compared_is_the_image_that_runs(monkeypatch):
    """The invariant underneath the fix, stated on its own: whatever `is_pinned_image()` answered
    about, `podman run` must have been handed exactly that."""
    from cytune import sanitize_gate
    monkeypatch.setattr(rig, "_DIGEST_CACHE", {})
    monkeypatch.setattr(rig, "image_digest", lambda image=None: rig.PINNED_IMAGE_DIGEST)
    assert sanitize_gate.is_pinned_image() is True
    assert rig.image_ref(sanitize_gate.IMAGE) == rig.PINNED_IMAGE_DIGEST
    # ...and the worker containers use the same resolved reference, not the tag.
    cmd = rig.build_cmd("/ws", "k", "1,2,3")
    assert rig.PINNED_IMAGE_DIGEST in cmd
    assert rig.IMAGE not in cmd


def test_an_unresolvable_image_falls_back_to_the_name_and_fails_loudly(monkeypatch):
    """If the image cannot be resolved at all there is nothing to run by id. Falling back to the
    name makes podman produce the error rather than cytune inventing a verdict."""
    monkeypatch.setattr(rig, "_DIGEST_CACHE", {})
    monkeypatch.setattr(rig, "image_digest", lambda image=None: None)
    assert rig.image_ref() == rig.IMAGE


# ============================================================ Attack B (focused adversarial re-run)
#
# THE BIND-BREAK, and it was in I4.1 itself. `cmd_endpoint` hashed `b["so_path"]` in the PARENT
# before spawning the measurement child. `_vendor/measure_child.py` then loads the DRIVER first and
# the `.so` only afterwards — so the driver's import-time code runs between the hash and the load,
# inside a container where the whole workspace was mounted read-write. A driver that overwrote the
# winner's `.so` with a faster binary producing identical output got all three checks to agree:
#
#   * I4.1  — both hashes were taken of the honest file, so they matched;
#   * C1    — the fast binary really did take that long, so the wall clock corroborated;
#   * oracle — identical output, so feasibility held.
#
# A forged speedup, fully bound, fully corroborated. Hashing again afterwards is not enough on its
# own: the swap can be undone before the process exits. The capability is what had to go.

def test_attack_b_the_artifact_tree_is_read_only_during_measurement():
    """FAILURE PATH, at the layer that makes the swap impossible rather than detectable.

    Nothing in a measure phase writes to `_so/` — the build phase is a separate container, which is
    what CF-1 is for — so the directory is mounted read-only and a driver's attempt to replace a
    binary fails at the filesystem. Verified end to end against the adversary's own fixture: the
    run died with `OSError: [Errno 30] Read-only file system` and fell back to the reference.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as ws:
        os.makedirs(os.path.join(ws, "k", "_so"))
        for mode in (rig.QUIESCED, rig.PORTABLE):
            cmd = rig.measure_cmd(ws, "k", mode, "endpoint", ["288"])
            ro = [a for a in cmd if a.endswith("/work/k/_so:ro")]
            assert ro, f"the measure phase mounts _so writable in {mode} mode: {cmd}"
        # the BUILD phase must keep it writable, or nothing could be compiled
        assert not [a for a in rig.build_cmd(ws, "k", "1") if a.endswith(":ro")
                    and "_so" in a]


def test_attack_b_the_measure_mount_is_absent_before_anything_is_built():
    """A read-only mount of a directory that does not exist would make podman create it, or fail.
    Before the first build there is nothing to protect."""
    import tempfile
    with tempfile.TemporaryDirectory() as ws:
        cmd = rig.measure_cmd(ws, "k", rig.PORTABLE, "golden", [5])
        assert not [a for a in cmd if a.endswith("_so:ro")]


def test_attack_b_a_swap_that_did_happen_is_still_caught_after_the_fact(tmp_path, monkeypatch,
                                                                        capsys):
    """Defence in depth, and the thing that would fire if the read-only mount were ever dropped.

    `cmd_endpoint` re-hashes the artifact after the measurement loop and marks the config
    infeasible when it moved. This drives the REAL function — the first version of this test
    asserted `before != after` on its own fixture and never called `cmd_endpoint` at all, which is
    the vacuous shape this project has been caught by twice (R2, T1).
    """
    pytest.importorskip("numpy")
    from cytune import worker

    out = tmp_path / "out"
    out.mkdir()
    (out / "build_manifest.jsonl").write_text(
        json.dumps({"config_id": REF, "ok": True, "reason": "ok", "compile_s": 1.0,
                    "so_size_b": 10, "so_path": str(out / "k.so")}) + "\n")
    (out / "k.so").write_bytes(b"honest")

    hashes = iter(["BEFORE", "AFTER"])        # the artifact moved while it was being measured
    monkeypatch.setattr(worker, "_artifact_digest", lambda *a, **k: next(hashes))
    monkeypatch.setattr(worker.campaign, "_module_of", lambda kdir: "kernel")
    monkeypatch.setattr(worker.campaign, "_rig", lambda: "no_turbo=1")
    monkeypatch.setattr(worker.campaign, "_measure_one",
                        lambda *a, **k: ({"median_ns": 1e6, "feasible": 1, "reason": "ok"},
                                         3e8, None))
    import build as buildmod
    monkeypatch.setattr(buildmod, "_meta", lambda kdir: None)

    worker.cmd_endpoint(str(tmp_path), str(out), [REF])
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    rec = payload["endpoints"][str(REF)]
    assert rec["feasible"] is False, rec
    assert "artifact_swapped_during_measurement" in rec["reason"]
    assert rec["artifact_sha256"] != rec["artifact_sha256_after"]


def test_attack_b_an_unswapped_measurement_still_passes(tmp_path, monkeypatch, capsys):
    """The control. Without it the check above would pass against an implementation that marked
    every endpoint measurement infeasible."""
    pytest.importorskip("numpy")
    from cytune import worker

    out = tmp_path / "out"
    out.mkdir()
    (out / "build_manifest.jsonl").write_text(
        json.dumps({"config_id": REF, "ok": True, "reason": "ok", "compile_s": 1.0,
                    "so_size_b": 10, "so_path": str(out / "k.so")}) + "\n")
    (out / "k.so").write_bytes(b"honest")

    monkeypatch.setattr(worker, "_artifact_digest", lambda *a, **k: "STABLE")
    monkeypatch.setattr(worker.campaign, "_module_of", lambda kdir: "kernel")
    monkeypatch.setattr(worker.campaign, "_rig", lambda: "no_turbo=1")
    monkeypatch.setattr(worker.campaign, "_measure_one",
                        lambda *a, **k: ({"median_ns": 1e6, "feasible": 1, "reason": "ok"},
                                         3e8, None))
    import build as buildmod
    monkeypatch.setattr(buildmod, "_meta", lambda kdir: None)

    worker.cmd_endpoint(str(tmp_path), str(out), [REF])
    rec = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["endpoints"][str(REF)]
    assert rec["feasible"] is True and rec["endpoint_ns"] == 1e6
    assert rec["artifact_sha256"] == rec["artifact_sha256_after"] == "STABLE"


# ------------------------------------------------- the production source digest (I4.2's input)
#
# THE DEFECT, and it is the vacuity shape this project has been caught by twice. `sha256_files`
# mixes each file's NAME into its digest so that a rename counts — correct for an artifact set, and
# fatal here: cythonize writes `<module>_<combo>.c`, so leaving the combo in the name gave every
# directive combination a distinct source digest BY CONSTRUCTION and I4.2 could never observe two
# combinations producing identical code.
#
# The end-to-end test against real Cython passed the whole time, because it hashed the .c files
# itself instead of going through `_source_digest`. A named test asserting the wrong thing — R2 and
# T1 again. It was caught by comparing the shipped code's answer against a measurement taken before
# the code existed: the ad-hoc one found an inert directive on four of the nine dogfood anchors,
# the shipped one reported none anywhere.

def _ccache(tmp_path, contents):
    """{combo: c-source} written the way cythonize writes it: `<module>_<combo>.c`."""
    out = tmp_path / "out"
    (out / "_ccache").mkdir(parents=True, exist_ok=True)
    for combo, text in contents.items():
        (out / "_ccache" / f"kernel_{combo}.c").write_text(text)
    return str(out)


def _cid_for(combo):
    for cid in range(theta.N_CONFIGS):
        if binding.combo_key(cid) == combo:
            return cid
    raise AssertionError(combo)


def test_the_source_digest_is_equal_for_combinations_that_generated_identical_c(tmp_path):
    """FAILURE PATH of the bug above: identical C under two different combos must hash the same."""
    from cytune import worker
    out = _ccache(tmp_path, {"11111": "/* same */\n", "11101": "/* same */\n"})
    a = worker._source_digest(out, _cid_for("11111"))
    b = worker._source_digest(out, _cid_for("11101"))
    assert a is not None and a == b, "the combo is leaking into the source digest"


def test_the_source_digest_differs_when_the_c_differs(tmp_path):
    """The control. Without it the fix could be 'hash a constant', which would make every kernel
    look totally degenerate and refuse every run."""
    from cytune import worker
    out = _ccache(tmp_path, {"11111": "/* A */\n", "11101": "/* B */\n"})
    assert (worker._source_digest(out, _cid_for("11111"))
            != worker._source_digest(out, _cid_for("11101")))


def test_i4_2_detects_an_inert_directive_through_the_production_path(tmp_path):
    """End to end over the SHIPPED function, not a re-implementation of it.

    Generated C that depends on every directive except `initializedcheck` — the real pattern, seen
    on four of the nine dogfood anchors — must come back with exactly that directive inert.
    """
    from cytune import worker
    combos = ["11111", "01111", "10111", "11011", "11101", "11110"]
    # the 4th character (initializedcheck) is erased from what decides the content
    out = _ccache(tmp_path, {c: f"/* {c[:3]}x{c[4:]} */\n" for c in combos})
    recs = {_cid_for(c): {"config_id": _cid_for(c), "artifact_sha256": f"{i:064d}",
                          "source_sha256": worker._source_digest(out, _cid_for(c))}
            for i, c in enumerate(combos)}
    report = binding.degeneracy(recs)
    assert report["directives_inert"] == ["initializedcheck"], report
    assert report["total_collapse"] is False


# ======================================= gaps found by the focused adversarial re-run, fixed here
#
# The hacker's report listed four things beyond the two bind-breaks. Three needed code.

def test_a_gate_that_omits_its_source_attestation_is_not_authoritative():
    """Attack A's SECONDARY defect. The stub image simply did not print `source_tree_sha256`, so
    I4.3 compared nothing and passed. Silence is not agreement — a verdict that does not say what
    it was about must not bind more tightly than one that does."""
    gate = {"ran": True, "clean": True, "config_id": 288,
            "image_digest": rig.PINNED_IMAGE_DIGEST}          # no source_tree_sha256
    out = binding.assert_gate_bound(config_id=288, gate=gate, source_tree_sha256="a" * 64,
                                    pinned_image_digest=rig.PINNED_IMAGE_DIGEST)
    assert out["authoritative"] is False
    assert "does not say what it was about" in out["warning"]


def test_a_gate_that_does_attest_its_source_still_passes():
    """Control: the check must bite only on the omission."""
    gate = {"ran": True, "clean": True, "config_id": 288, "source_tree_sha256": "a" * 64,
            "image_digest": rig.PINNED_IMAGE_DIGEST}
    out = binding.assert_gate_bound(config_id=288, gate=gate, source_tree_sha256="a" * 64,
                                    pinned_image_digest=rig.PINNED_IMAGE_DIGEST)
    assert out.get("authoritative") is not False


@pytest.mark.parametrize("line", [
    "@cython.boundscheck(False)",
    "@boundscheck(False)",
    "    @cython.wraparound(False)",
    "with cython.cdivision(True):",
    "    with nonecheck(False):",
    "@cython.initializedcheck(False)",
])
def test_a_scoped_directive_is_detected_and_reported(tmp_path, line):
    """The degeneracy-evasion route the header check missed.

    `@cython.boundscheck(False)` overrides -X for the function it decorates exactly as a file
    header does for the module, and it is not a comment, so nothing in the header scan saw it.
    """
    p = tmp_path / "k.pyx"
    p.write_text("cimport cython\n\n" + line + "\ndef run(double[::1] a):\n    return a[0]\n")
    found = session.check_scoped_directives(str(p))
    assert found, f"{line!r} was not detected"
    assert any("line" in v for v in found.values())


@pytest.mark.parametrize("line", [
    "@cython.boundscheck(False)",
    "with cython.cdivision(True):",
])
def test_a_scoped_directive_is_REPORTED_and_not_refused(tmp_path, line):
    """THE PROPORTIONALITY, and it is measured rather than argued.

    A file header neutralises a directive for the WHOLE module: every combination compiles
    identically and nothing the certificate says about directives is true, so it is refused. A
    decorator neutralises it for ONE function; the rest of the module still varies and the search
    still measures something real.

    Refusing on decorators would have blocked THREE OF THE NINE real scipy/scikit-learn anchors
    this product was validated against — `_ppoly`, `_shortest_path` and `_traversal` all use them,
    and all three still produce 21 distinct generated sources from 21 directive combinations. So
    the certificate names the file, the line and the directive instead of refusing the run.
    """
    p = tmp_path / "k.pyx"
    p.write_text("cimport cython\n\n" + line + "\ndef run(double[::1] a):\n    return a[0]\n")
    assert session.check_pinned_directives(str(p)) is None, "a scoped pin must not refuse the run"
    assert session.check_scoped_directives(str(p)), "...but it must be reported"


def test_a_module_wide_header_is_still_refused(tmp_path):
    """The control on the control: the proportionate treatment must not have weakened H12's fix."""
    p = tmp_path / "k.pyx"
    p.write_text("# cython: boundscheck=False\ndef run(double[::1] a):\n    return a[0]\n")
    assert session.check_pinned_directives(str(p)) == {"boundscheck": "boundscheck=False"}


@pytest.mark.parametrize("line", [
    "@cython.cfunc",
    "@staticmethod",
    "@cython.locals(i=cython.int)",
    "# @cython.boundscheck(False) — this is a comment, not a decorator",
    "with nogil:",
])
def test_ordinary_decorators_are_not_mistaken_for_pins(tmp_path, line):
    """The negative control. A check that flagged every decorated module would be noise, and
    `@cython.locals` / `@cython.cfunc` are ordinary in real Cython."""
    p = tmp_path / "k.pyx"
    p.write_text("cimport cython\n\n" + line + "\ndef run(double[::1] a):\n    return a[0]\n")
    assert session.check_scoped_directives(str(p)) is None
    assert session.check_pinned_directives(str(p)) is None


def test_c1_reports_no_power_rather_than_pass_when_the_noise_swamps_the_claim():
    """FAILURE PATH of a check reporting its own inability as a success.

    The largest residual any lie can produce is `(1 + warmup/K) x claimed_gain`. If the measured
    noise floor alone exceeds that, nothing could fail the check — so `corroborated: true` would
    mean only "the arithmetic was performed". Not-run is not a pass, one level up.
    """
    win, ref = _lie(1.02, 1.02)                      # a ~2% gain, honestly reported
    huge = [1.0e9 + (i % 5) * 3e8 for i in range(30)]   # seconds of spawn jitter
    out = certify.corroborate_ratio(win, ref, screen_overheads=huge)
    assert out["corroborated"] is None
    assert "no power here" in out["reason"]


def test_c1_still_decides_when_the_claim_is_large_enough_to_be_checkable():
    """Control: the cutoff must not swallow the cases the check exists for."""
    win, ref = _lie(1.0, 5.0)
    modest = [3.0e8 + (i % 5) * 1e6 for i in range(30)]
    out = certify.corroborate_ratio(win, ref, screen_overheads=modest)
    assert out["corroborated"] is False


# ===================================================================== D-3 (live dogfood, 1.1)
#
# THE DEFECT. `cli.tune` gates the search's BEST CANDIDATE before deciding what to emit — on
# purpose, because the gate is a bug finder and not only an emission filter. It stores that verdict
# in `san_emitted`, the variable meaning "the gate on the config being emitted". THREE paths can
# then demote the candidate to the reference:
#
#     sanitizer reports   -> san_emitted was never assigned (the else-branch is skipped)  OK
#     emit margin missed  -> `san_emitted = None`, and the reference is re-gated            OK
#     C1 not corroborated -> nothing clears it                                              BUG
#
# On the third path the reference is emitted while `san_emitted` still describes the candidate, so
# I4.3 refuses to certify: "the sanitizer gate reports config 966 but the emitted config is 288".
#
# Found by the live nine-anchor dogfood on `fleet_R_08_elkan` (exit 1). The unit tests could not
# find it: `corroborate_ratio` is tested thoroughly as a pure FUNCTION, and the outcome-space sweep
# in test_cytune_coherence.py mirrors the CLI's composition of the OTHER two demotion paths and
# omits this one. A gate tested in isolation and a composition that never composes it.
#
# I4.3 did exactly what the binding layer exists to do: refuse rather than emit a document about a
# run that did not happen.

_SAN_TREE = "b" * 64


def _gate_record(config_id, clean=True):
    """The shape `sanitize_gate.gate()` returns for a config that ran and came back clean."""
    return {"config_id": config_id, "ran": True, "clean": clean, "verdict": "clean",
            "tokens": [], "source_tree_sha256": _SAN_TREE}


def _demote(path, candidate, reference):
    """Mirror cli.tune's demotion composition for one path. Returns (emitted_id, san_emitted).

    Deliberately a mirror of the real ORDER rather than a call into `tune`, which needs containers.
    The three branches below are transcribed from cli.py's verify stage; if that order changes,
    this stops being a mirror and the test that depends on it should be updated with it.
    """
    san_emitted, winner = None, candidate
    gate = _gate_record(candidate, clean=(path != "sanitizer"))
    if path == "sanitizer":                       # cli.py: rejects(san_cand) -> never assigned
        winner = reference
    else:
        san_emitted = gate                        # cli.py line ~479: `san_emitted = san_cand`
        if path == "c1":                          # cli.py: corroborated is False
            winner = reference
            san_emitted = None                    # <- THE FIX
        elif path == "margin":                    # cli.py: not assess(...)["clears"]
            winner = reference
            san_emitted = None
    if san_emitted is None and winner is not None:
        san_emitted = _gate_record(winner)        # cli.py: `if san_emitted is None: _gate_emitted`
    return winner, san_emitted


@pytest.mark.parametrize("path", ["sanitizer", "c1", "margin"])
def test_i4_3_every_demotion_path_leaves_the_gate_describing_what_is_emitted(path):
    """D-3. All three demotion paths, not the two that happened to be mirrored before.

    Before the fix, `c1` left the CANDIDATE's verdict attached to a certificate emitting the
    REFERENCE, and I4.3 refused — correctly, and only at run time on a real anchor.
    """
    emitted, san = _demote(path, candidate=966, reference=theta.REFERENCE_ID)
    assert emitted == theta.REFERENCE_ID
    binding.assert_gate_bound(config_id=emitted, gate=san,
                              source_tree_sha256=_SAN_TREE,
                              pinned_image_digest=rig.PINNED_IMAGE_DIGEST)
    assert san["config_id"] == emitted, (
        f"{path}: the gate describes config {san['config_id']} but {emitted} is being emitted")


def test_i4_3_still_fires_when_a_demotion_path_forgets_to_reset_the_gate():
    """THE CONTROL. Without it the three tests above would pass for an `assert_gate_bound` that
    checked nothing, and the regression they exist to catch would be invisible.

    This is the exact state the live dogfood produced on fleet_R_08_elkan.
    """
    with pytest.raises(binding.BindingViolation) as e:
        binding.assert_gate_bound(config_id=theta.REFERENCE_ID,
                                  gate=_gate_record(966),
                                  source_tree_sha256=_SAN_TREE,
                                  pinned_image_digest=rig.PINNED_IMAGE_DIGEST)
    assert e.value.invariant == "I4.3"
    assert "966" in str(e.value) and str(theta.REFERENCE_ID) in str(e.value)


# ===================================================== D-4 (found while investigating D-3)
def test_d4_the_certificate_records_the_same_corroboration_the_gate_decided_on():
    """D-4. `build_certificate` took `screen_overheads` and did not forward them to
    `corroborate_ratio`, so the CLI gated on one budget and the document reported another.

    C1's budget is the LARGER of half the claimed gain and 3 sigma of the per-process overhead
    spread the run measured. Dropping the samples can only SHRINK it, so the certificate could say
    `corroborated: false` about a run whose gate had passed — a document contradicting the decision
    that produced it, which is D-3's defect one layer up.

    The fixture sits in the window where the two budgets disagree:
        0.5 * claimed_gain  <  residual  <=  3 sigma  <  (1 + warmup/K) * claimed_gain
    the last term being C1's own no-power cutoff, which must not fire or the check returns None
    and proves nothing.
    """
    K, warmup = 30, certify.ENDPOINT_WARMUP
    wm, rm = 90e6, 100e6                              # 10 ms per rep -> 300 ms claimed gain at K=30
    oh_ref, oh_win = 700e6, 850e6                     # observed delta +150 ms vs predicted -50 ms
    win = {"endpoint_ns": wm, "subs_ns": [wm] * 3, "n_sub": 3, "K": K,
           "wall_ns": [K * wm + oh_win] * 3}
    ref = {"endpoint_ns": rm, "subs_ns": [rm] * 3, "n_sub": 3, "K": K,
           "wall_ns": [K * rm + oh_ref] * 3}
    noisy = [700e6 + i * 9e6 for i in range(30)]      # a genuinely wide measured spread

    tight = certify.corroborate_ratio(win, ref)
    wide = certify.corroborate_ratio(win, ref, screen_overheads=noisy)
    # the window itself, asserted so a future change to the constants fails loudly here rather
    # than quietly turning this into a test of nothing
    assert tight["corroborated"] is False, tight
    assert wide["corroborated"] is True, wide
    assert wide["n_overhead_samples"] == 30 and tight["n_overhead_samples"] == 0

    c = certify.build_certificate(
        name="d4", winner_id=FAST_ID, reference_id=REF,
        endpoint={str(FAST_ID): win, str(REF): ref}, oracle=_D4_ORACLE, feasibility=_D4_FEAS,
        route=_D4_ROUTE, rig_mode="quiesced", rig_detail="quiesced — verified",
        budget={"probe": 17, "tuning": 16}, sources={"table": "/w/t.jsonl", "workspace": "/w"},
        allow_fast_math=False, screen_overheads=noisy)
    got = c["measurement"]["timing_corroboration"]
    assert got["corroborated"] is True, (
        "the certificate recomputed C1 without the run's own overhead samples; it reports "
        f"{got['corroborated']} where the gate decided True")
    assert got["n_overhead_samples"] == len(noisy), (
        f"the certificate says the noise floor came from {got['n_overhead_samples']} samples, "
        f"but the run measured {len(noisy)}")


FAST_ID = theta.id_of((False, False, True, False, False, "-O3", "native", "on", ("off", "off")))
_D4_ORACLE = {"output_class": "int", "tolerance": {"rtol": 0.0, "atol": 0.0},
              "deterministic": True, "n_det_reps": 5, "golden_sha256": "abc"}
_D4_FEAS = {"n_measured": 20, "n_infeasible": 0, "infeasible_fraction": 0.0, "reasons": {}}
_D4_ROUTE = {"rule": "R4", "route": "tune", "engine": "DOE", "budget": 16, "why": "lever"}
