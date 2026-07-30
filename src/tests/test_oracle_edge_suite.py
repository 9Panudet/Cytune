"""Step 0.3.4 — cdivision edge-suite tests (TDD, red first).

Grounding (roadmap §3.2(4)): cdivision=True changes semantics on negative
operands (floor vs truncation; modulo sign) and zero divisors (Python raises
ZeroDivisionError; C is UB — SIGFPE on x86). These tests compile a real
Cython kernel twice in the pinned container (cdivision=False / True) and
assert the ORACLE CATCHES every actual divergence — a missed divergence is a
failing test. Probes execute in fresh subprocesses (§3.2(2)); a crashed
child is the §3.5 segfault/abort path, also "caught".
"""
import builtins
import json
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest

from motifbo.oracle.bitwise import Outcome, compare_outcomes
from motifbo.oracle.edge_suite import (
    division_edge_cases,
    manifest_exception_entries,
    python_div_outcome,
)
from motifbo.oracle.manifest import validate_manifest

MANDATED_CASES = {  # §3.2(4): negative operands + zero divisors
    "neg_dividend", "neg_divisor", "neg_both",
    "zero_divisor", "zero_divisor_neg_dividend",
}


def case(name):
    table = {n: (a, b) for n, a, b in division_edge_cases()}
    return table[name]  # KeyError = generator failed to supply a mandated probe


# --- generator ----------------------------------------------------------------

def test_edge_cases_cover_mandated_probes_and_are_deterministic():
    cases = division_edge_cases()
    names = [n for n, _, _ in cases]
    assert len(names) == len(set(names)), "duplicate case names"
    assert MANDATED_CASES <= set(names)
    assert cases == division_edge_cases()  # frozen order, deterministic
    for name in ("zero_divisor", "zero_divisor_neg_dividend"):
        assert case(name)[1] == 0
    assert case("neg_dividend")[0] < 0 < case("neg_dividend")[1]
    assert case("neg_divisor")[1] < 0 < case("neg_divisor")[0]
    assert case("neg_both")[0] < 0 and case("neg_both")[1] < 0


def test_python_div_outcome_encodes_python_semantics():
    # Python: floor division; modulo carries the DIVISOR's sign.
    assert compare_outcomes(python_div_outcome(-7, 2),
                            Outcome.value([-4, 1])) is None
    assert compare_outcomes(python_div_outcome(7, -2),
                            Outcome.value([-4, -1])) is None
    assert compare_outcomes(python_div_outcome(-7, -2),
                            Outcome.value([3, -1])) is None
    zd = python_div_outcome(7, 0)
    assert compare_outcomes(zd, Outcome.exception(ZeroDivisionError)) is None


def test_manifest_entries_declare_zero_divisor_exceptions():
    entries = manifest_exception_entries()
    assert {e["case"] for e in entries} == {
        n for n, _, d in division_edge_cases() if d == 0}
    assert entries, "no zero-divisor probes declared"
    for e in entries:
        # the declared type must be exactly what Python semantics raises
        a, b = case(e["case"])
        declared = Outcome.exception(getattr(builtins, e["type"]))
        assert compare_outcomes(python_div_outcome(a, b), declared) is None
    manifest = {
        "schema": "motifbo-oracle-v1", "unit": "edge_suite_selftest",
        "outputs": [{"name": "quotient_remainder",
                     "class": "correctness-critical"}],
        "expected_exceptions": list(entries),
    }
    assert validate_manifest(manifest) == []  # 0.3.1 schema accepts them


# --- real compiled divergence (cdivision=False vs True) ------------------------

KERNEL_PYX = """\
def kernel(long a, long b):
    cdef long q = a // b
    cdef long r = a % b
    return (q, r)
"""

CHILD = """\
import importlib.util, json, sys
from pathlib import Path
so, a, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
stem = Path(so).stem                      # must match PyInit_<stem>
spec = importlib.util.spec_from_file_location(stem, so)
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
    v = mod.kernel(a, b)
    print(json.dumps({"kind": "value", "value": list(v)}))
except BaseException as e:
    print(json.dumps({"kind": "exception",
                      "type": f"{type(e).__module__}.{type(e).__qualname__}"}))
"""


@pytest.fixture(scope="session")
def div_builds(tmp_path_factory):
    """Compile the SAME kernel source under both cdivision directives,
    pinned flags per the refkernel profile (-ffp-contract always explicit)."""
    if shutil.which("cython") is None or shutil.which("gcc") is None:
        pytest.fail("pinned container must provide cython + gcc")
    d = tmp_path_factory.mktemp("divkernels")
    include = sysconfig.get_paths()["include"]
    builds = {}
    for stem, directive in (("divkernel_pysem", "cdivision=False"),
                            ("divkernel_csem", "cdivision=True")):
        pyx = d / f"{stem}.pyx"
        pyx.write_text(KERNEL_PYX)
        subprocess.run(["cython", "-3", "-X", directive, str(pyx)], check=True)
        so = d / f"{stem}.so"
        subprocess.run(
            ["gcc", "-O2", "-march=x86-64", "-ffp-contract=off", "-g0",
             "-pipe", "-shared", "-fPIC", f"-I{include}",
             str(d / f"{stem}.c"), "-o", str(so)], check=True)
        builds[directive] = so
    return builds


def run_probe(so, a, b):
    """Fresh subprocess per probe (§3.2(2)); negative returncode = crash."""
    p = subprocess.run([sys.executable, "-c", CHILD, str(so), str(a), str(b)],
                       capture_output=True, text=True, timeout=60)
    if p.returncode < 0:
        return {"kind": "crash", "signal": -p.returncode}
    assert p.returncode == 0, f"probe child failed: {p.stderr}"
    return json.loads(p.stdout)


def to_outcome(res):
    if res["kind"] == "value":
        return Outcome.value(res["value"])
    return Outcome.exception(res["type"])


@pytest.mark.parametrize("name", sorted(MANDATED_CASES | {"positive_control"}))
def test_golden_build_matches_python_semantics(div_builds, name):
    a, b = case(name)
    got = run_probe(div_builds["cdivision=False"], a, b)
    assert got["kind"] != "crash", "golden build must never crash"
    assert compare_outcomes(python_div_outcome(a, b), to_outcome(got)) is None


@pytest.mark.parametrize("name,c_semantics", [
    ("neg_dividend", [-3, -1]),   # C truncates toward zero; % takes dividend sign
    ("neg_divisor", [-3, 1]),
])
def test_negative_operand_divergence_is_caught(div_builds, name, c_semantics):
    a, b = case(name)
    golden = python_div_outcome(a, b)
    got = run_probe(div_builds["cdivision=True"], a, b)
    assert got["kind"] == "value", f"unexpected candidate outcome: {got}"
    # pin the actual C result, proving the directive took effect…
    assert compare_outcomes(Outcome.value(c_semantics), to_outcome(got)) is None
    # …and the oracle must catch the divergence (None here = missed = FAIL)
    assert compare_outcomes(golden, to_outcome(got)) is not None


@pytest.mark.parametrize("name", ["positive_control", "neg_both"])
def test_agreeing_cases_do_not_false_positive(div_builds, name):
    # -7 // -2 == 3 and -7 % -2 == -1 under BOTH semantics: the suite must
    # not flag configurations that genuinely agree.
    a, b = case(name)
    got = run_probe(div_builds["cdivision=True"], a, b)
    assert compare_outcomes(python_div_outcome(a, b), to_outcome(got)) is None


@pytest.mark.parametrize("name", ["zero_divisor", "zero_divisor_neg_dividend"])
def test_zero_divisor_divergence_is_caught(div_builds, name):
    a, b = case(name)
    golden = python_div_outcome(a, b)
    got = run_probe(div_builds["cdivision=True"], a, b)
    if got["kind"] == "crash":
        # §3.5 segfault/abort path: x86 integer divide-by-zero raises SIGFPE(8)
        assert got["signal"] == 8, f"unexpected crash signal: {got}"
    else:
        # if it survived, the outcome must STILL mismatch the golden
        # ZeroDivisionError — a clean match here means cdivision=True did not
        # change semantics, i.e. the divergence was missed: failing test.
        reason = compare_outcomes(golden, to_outcome(got))
        assert reason is not None, f"missed zero-divisor divergence: {got}"
