"""H12 — a `# cython:` file header silently defeats the entire directive search.

Found by the adversarial campaign, and it needs no adversary: headers like
`# cython: boundscheck=False, wraparound=False` are ordinary in production Cython, including in
scipy and scikit-learn.

THE MECHANISM, measured in the pinned image: Cython's file header takes precedence over the `-X`
flags the builder uses, so with such a header every one of the 32 directive combinations compiles
to byte-identical C. `-X boundscheck=True` and `-X boundscheck=False` produced identical output.
The search still ran, still timed 33 configurations, still picked a winner, and still certified it
— describing directives that were never applied, and calling config 288 "Cython's safe defaults"
when it had been built with the checks off.

The coherence gate could not see it. I1 verifies the DOCUMENT against the config id; the config id
was never what got built. This is therefore checked at INGEST, where the source still exists.

The README already warned users not to do this. A warning did not stop it — which is the whole
difference between a claim and a guarantee.
"""
from __future__ import annotations

import pytest

from cytune import session


def _write(tmp_path, header):
    p = tmp_path / "k.pyx"
    p.write_text((header + "\n" if header else "") + "def run(a):\n    return a[0]\n")
    return str(p)


@pytest.mark.parametrize("header", [
    "# cython: boundscheck=False",
    "# cython: boundscheck=False, wraparound=False",
    "# cython: wraparound=True",
    "#cython:cdivision=True",
    "# CYTHON: initializedcheck=False",
    "# cython: language_level=3, boundscheck=False",
    "# cython: nonecheck=True",
])
def test_a_pinned_directive_is_detected(tmp_path, header):
    assert session.check_pinned_directives(_write(tmp_path, header))


@pytest.mark.parametrize("header", [
    None,
    "# cython: language_level=3",
    "# cython: cpow=True",
    "# cython: embedsignature=True, language_level=3",
    "# just a normal comment",
    "# cython: boundscheck is not set here because there is no equals sign",
])
def test_an_unrelated_header_is_left_alone(tmp_path, header):
    """`language_level=3` is on nearly every .pyx and `cpow=True` is on one of this project's own
    Dataset-R anchors. Verified in the pinned image that a header naming only `cpow` leaves
    `-X boundscheck` working, so refusing these would break real modules for no reason."""
    assert session.check_pinned_directives(_write(tmp_path, header)) is None


def test_a_directive_set_after_real_code_is_not_a_header(tmp_path):
    """Cython honours the directive header only in the leading comment block. A `# cython:` line
    further down is an ordinary comment and must not trigger a refusal."""
    p = tmp_path / "k.pyx"
    p.write_text("def run(a):\n    return a[0]\n\n# cython: boundscheck=False\n")
    assert session.check_pinned_directives(str(p)) is None


def test_vendor_refuses_and_names_the_offending_line(tmp_path):
    """FAILURE PATH end-to-end: the run must stop at ingest, before anything is copied or built."""
    mod = _write(tmp_path, "# cython: boundscheck=False, wraparound=False")
    drv = tmp_path / "d.py"
    drv.write_text("OUTPUT_CLASS='int'\ndef make_inputs(s): return ()\n"
                   "def call(m,i): return 1\ndef canon(r): return r\n")
    s = session.Session(str(tmp_path / "ws"), "k", "portable", "d")
    with pytest.raises(session.IngestError) as e:
        s.vendor(mod, str(drv))
    msg = str(e.value)
    assert "pins directives that cytune varies" in msg
    assert "boundscheck" in msg and "wraparound" in msg
    assert "OVERRIDES the -X flags" in msg
    import os
    assert not os.path.exists(s.kdir), "a refused module must not be vendored"


def test_a_clean_module_still_vendors(tmp_path):
    """Control — without this the refusal could be unconditional and every test above would pass."""
    mod = _write(tmp_path, "# cython: language_level=3")
    drv = tmp_path / "d.py"
    drv.write_text("OUTPUT_CLASS='int'\ndef make_inputs(s): return ()\n"
                   "def call(m,i): return 1\ndef canon(r): return r\n")
    s = session.Session(str(tmp_path / "ws"), "k", "portable", "d")
    res = s.vendor(mod, str(drv))
    assert res["closure"] is False
