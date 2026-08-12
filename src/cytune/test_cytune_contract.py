"""T1 and T2 — the two BLOCKERs from the systematic-tester agent.

Both are cases where a NAMED PROOF TEST existed and was vacuous. That is the failure mode this
project cares about most, so these tests drive the real path rather than a stub.

T1: a total build failure shipped no compiler diagnostic. Two documents promise "the compiler's own
    words"; the tool printed `cythonize_fail (cached)` and wrote a 79-byte "full build log"
    containing that same string. `test_f6_total_build_failure_aborts_with_the_compilers_own_words`
    stubbed the build result, so it never saw a real cythonize failure.

T2: the driver contract was a SUBSTRING search, so `# TODO: set OUTPUT_CLASS` satisfied it. The run
    then proceeded with no output class and the oracle fell back to `float` — the tolerance-based
    mode — silently costing an integer kernel the bit-exact sha256 oracle G1 promises it.
    `def make_inputs` in a comment WAS rejected, so one contract was checked to two standards.
"""
from __future__ import annotations

import pytest

from cytune.session import Session

GOOD = ('import numpy as np\nOUTPUT_CLASS = "int"\n'
        'def make_inputs(s):\n    return ()\n'
        'def call(m, i):\n    return 1\n'
        'def canon(r):\n    return r\n')


def _gaps(tmp_path, src):
    p = tmp_path / "d.py"
    p.write_text(src)
    return Session._driver_contract_gaps(str(p))


def test_a_valid_driver_has_no_gaps(tmp_path):
    assert _gaps(tmp_path, GOOD) == []


@pytest.mark.parametrize("name", ["make_inputs", "call", "canon"])
def test_a_missing_function_is_detected(tmp_path, name):
    src = GOOD.replace(f"def {name}(", "def something_else(")
    assert name in _gaps(tmp_path, src)


def test_t2_output_class_in_a_comment_does_not_satisfy_the_contract(tmp_path):
    """THE T2 BLOCKER. Mentioning the name is not defining it."""
    src = GOOD.replace('OUTPUT_CLASS = "int"', '# TODO: set OUTPUT_CLASS = "int" here')
    assert "OUTPUT_CLASS" in _gaps(tmp_path, src)


def test_t2_output_class_in_a_docstring_does_not_satisfy_the_contract(tmp_path):
    src = '"""This driver sets OUTPUT_CLASS eventually."""\n' + \
          GOOD.replace('OUTPUT_CLASS = "int"\n', '')
    assert "OUTPUT_CLASS" in _gaps(tmp_path, src)


def test_t2_a_function_named_in_a_comment_is_still_rejected(tmp_path):
    """The other half of the same contract, so the two are held to ONE standard."""
    src = GOOD.replace("def canon(r):\n    return r\n", "# def canon(r): return r\n")
    assert "canon" in _gaps(tmp_path, src)


def test_t2_a_function_defined_inside_another_function_still_counts(tmp_path):
    """`ast.walk` finds nested defs. Being generous here is fine — the container will fail loudly
    if the symbol is not actually importable — and being strict would reject legitimate drivers."""
    src = GOOD.replace("def canon(r):\n    return r\n",
                       "def _wrap():\n    def canon(r):\n        return r\n    return canon\n"
                       "canon = _wrap()\n")
    assert "canon" not in _gaps(tmp_path, src)


@pytest.mark.parametrize("value", ['"banana"', '"Float"', '"INT"', "None", "3"])
def test_t3_an_invalid_output_class_value_is_rejected(tmp_path, value):
    """T3. `OUTPUT_CLASS = "banana"` reached the certificate."""
    src = GOOD.replace('OUTPUT_CLASS = "int"', f"OUTPUT_CLASS = {value}")
    gaps = _gaps(tmp_path, src)
    assert gaps and "OUTPUT_CLASS" in gaps[0]


@pytest.mark.parametrize("value", ['"float"', '"int"', '"bool"'])
def test_every_documented_output_class_is_accepted(tmp_path, value):
    """Control: without this the check could reject everything and every test above would pass."""
    src = GOOD.replace('OUTPUT_CLASS = "int"', f"OUTPUT_CLASS = {value}")
    assert _gaps(tmp_path, src) == []


def test_a_driver_that_is_not_valid_python_is_diagnosed(tmp_path):
    gaps = _gaps(tmp_path, "def make_inputs(s)\n    return ()\n")
    assert gaps and "not valid Python" in gaps[0]


def test_an_annotated_assignment_counts(tmp_path):
    src = GOOD.replace('OUTPUT_CLASS = "int"', 'OUTPUT_CLASS: str = "int"')
    assert _gaps(tmp_path, src) == []


# ------------------------------------------------------------------------- T1
def test_t1_a_cached_cythonize_failure_recovers_the_compilers_words(tmp_path):
    """THE T1 BLOCKER, driven through the real recovery path.

    `_cythonize_synth` stashes the compiler's stdout+stderr in `<c_path>.FAIL`, then on any later
    call returns the reason string `cythonize_fail (cached)` as its "log". Nothing read the file
    back, so the user got the status word instead of the diagnostic.
    """
    import os
    from cytune import worker
    from cytune._vendor import theta
    import build as buildmod

    cache = tmp_path / "_ccache"
    cache.mkdir()
    cid = 10
    combo = buildmod._combo_key(theta.config_of(cid))
    real = ("Error compiling Cython file:\n"
            "------------------------------------------------------------\n"
            "def run(long long[::1] a, int reps)\n"
            "                                   ^\n"
            "kernel.pyx:1:35: Expected ':', found 'NEWLINE'\n")
    (cache / f"kernel_{combo}.c.FAIL").write_text(real)

    assert worker._read_cached_failure(str(cache), cid) == real
    assert "Expected ':'" in worker._read_cached_failure(str(cache), cid)


def test_t1_a_missing_cache_marker_returns_nothing_rather_than_guessing(tmp_path):
    from cytune import worker
    assert worker._read_cached_failure(str(tmp_path / "nope"), 10) == ""
    (tmp_path / "_ccache").mkdir()
    assert worker._read_cached_failure(str(tmp_path / "_ccache"), 10) == ""


def test_t1_status_words_are_never_accepted_as_a_build_log():
    """The condition that made the fix necessary: the 'log' was non-empty and worthless."""
    import inspect
    from cytune import worker
    src = inspect.getsource(worker._capture_first_failure_log)
    for word in ("cythonize_fail (cached)", "cythonize_fail", "build_fail"):
        assert repr(word) in src or f'"{word}"' in src, \
            f"{word!r} must be treated as 'no real log', or T1 comes back"


# ------------------------------------------------- T5/T7: config errors, not tracebacks
def _load(tmp_path, text, name=".cytune.toml"):
    from cytune import config
    p = tmp_path / name
    p.write_text(text)
    return config.load(str(p))


def test_t5_malformed_toml_is_a_config_error_not_a_traceback(tmp_path):
    """T5. `tomllib.TOMLDecodeError` is not a ConfigError, so `main`'s handler never saw it and the
    user got a raw Python traceback."""
    from cytune import config
    with pytest.raises(config.ConfigError, match="not valid TOML"):
        _load(tmp_path, "[cytune\ntarget_ms = = 3\n")


def test_t5_an_unreadable_config_is_a_config_error(tmp_path):
    from cytune import config
    d = tmp_path / "adir"
    d.mkdir()
    with pytest.raises(config.ConfigError, match="cannot be read"):
        config.load(str(d))


@pytest.mark.parametrize("line,word", [
    ('rig = "turbo"', "rig"),
    ('objective = "energy"', "objective"),
    ('preset = "ludicrous"', "preset"),
])
def test_t7_an_invalid_enum_value_is_rejected(tmp_path, line, word):
    """T7. Unknown KEYS were an error, but a bad VALUE was accepted and then quietly ignored —
    the same defect the unknown-key check exists to prevent."""
    from cytune import config
    with pytest.raises(config.ConfigError, match=word):
        _load(tmp_path, f"[cytune]\n{line}\n")


@pytest.mark.parametrize("line", ["target_ms = -5", "budget_scale = -1.0"])
def test_t7_a_negative_number_is_rejected(tmp_path, line):
    from cytune import config
    with pytest.raises(config.ConfigError, match="must not be negative"):
        _load(tmp_path, f"[cytune]\n{line}\n")


def test_a_valid_config_still_loads(tmp_path):
    """Control: without this the loader could reject everything."""
    vals, _p = _load(tmp_path, '[cytune]\nrig = "portable"\ntarget_ms = 40\npreset = "thorough"\n')
    assert vals["rig"] == "portable" and vals["target_ms"] == 40.0
    assert vals["preset"] == "thorough"


def test_d32_a_workspace_inside_the_module_directory_is_refused(tmp_path):
    """D32 — the documented directory-mode invocation crashed with a bare traceback.

    `cytune tune .` from inside a closure module, with the default `.cytune` workspace, made
    `vendor` copytree the module directory into a workspace inside itself: ~150 levels of
    `.cytune/_kernels/.cytune/_kernels/...` and then `[Errno 36] File name too long`.

    Found by a senior-power-user agent following USER_GUIDE §2.1 literally. A refusal that names
    the fix is the minimum; the guide's own default must not be a trap.
    """
    import json as _json
    import os
    import pytest
    from cytune.session import IngestError, Session

    mod = tmp_path / "multi"
    (mod / "closure" / "pkg").mkdir(parents=True)
    (mod / "closure" / "pkg" / "k.pyx").write_text("def run(double[::1] a):\n    return a[0]\n")
    (mod / "kernel_meta.json").write_text(_json.dumps({"pyx_relpath": "pkg/k.pyx"}))
    drv = tmp_path / "driver.py"
    drv.write_text("import numpy as np\n"
                   "def make_inputs(seed): return (np.zeros(4),)\n"
                   "def call(mod, i): return mod.run(*i)\n"
                   "def canon(r): return np.asarray([r], dtype=np.float64)\n"
                   'OUTPUT_CLASS = "float"\n')

    inside = Session(str(mod / ".cytune"), "k", "portable", "t", target_ms=0)
    with pytest.raises(IngestError, match="inside the module directory"):
        inside.vendor(str(mod), str(drv))

    # NEGATIVE CONTROL: a workspace outside the tree must NOT be refused by this check. A guard
    # that refused every directory module would pass the assertion above and be useless.
    outside = Session(str(tmp_path / "ws"), "k", "portable", "t", target_ms=0)
    try:
        outside.vendor(str(mod), str(drv))
    except IngestError as e:
        assert "inside the module directory" not in str(e), e
