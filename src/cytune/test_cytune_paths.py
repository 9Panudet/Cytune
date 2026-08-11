"""B4 — the path registry is walked, and the composition sweep must cover it.

`paths.PATH_REGISTRY` enumerates production's verify/emit decision paths as data. These tests are
the mechanism that makes the enumeration worth having:

  * every entry names a production site that still exists at that line;
  * every verdict is one the certificate can actually carry;
  * every path marked REQUIRED is reached by the composition mirror in test_cytune_coherence.py.

The third is the class defence. D-3 was the fourth defect of the shape "the unit is tested, the
composition models fewer cases than production has"; before this file the only thing standing
between that shape and a live-run discovery was somebody remembering to extend a mirror.
"""
from __future__ import annotations

import os
import re

import pytest

from cytune import certify, paths

HERE = os.path.dirname(os.path.abspath(__file__))


def test_the_registry_is_well_formed():
    assert paths.PATH_REGISTRY, "an empty registry protects nothing"
    for r in paths.PATH_REGISTRY:
        assert len(r) == len(paths.FIELDS), f"{r[0]}: wrong arity"
        d = dict(zip(paths.FIELDS, r))
        assert d["id"] and d["trigger"] and d["site"] and d["note"], d
        assert d["composition"] in (paths.REQUIRED, paths.CERTIFY_ONLY, paths.NA), d


def test_path_ids_are_unique():
    assert len(paths.IDS) == len(set(paths.IDS))


@pytest.mark.parametrize("pid", paths.IDS)
def test_every_registered_path_names_a_real_production_site(pid):
    """A registry whose sites have rotted is a map of a building that was demolished.

    Same check `test_cytune_invariants.py` applies to the invariant registry, and for the same
    reason: the entry has to keep pointing at code, or the enumeration decays into folklore.
    """
    d = paths.describe(pid)
    m = re.fullmatch(r"([A-Za-z_0-9]+\.py):(\d+)", d["site"])
    assert m, f"{pid}: site {d['site']!r} is not <file>.py:<line>"
    path = os.path.join(HERE, m.group(1))
    assert os.path.exists(path), f"{pid}: {m.group(1)} does not exist"
    n = len(open(path).read().splitlines())
    assert int(m.group(2)) <= n, f"{pid}: {d['site']} is past the end of the file ({n} lines)"


@pytest.mark.parametrize("pid", paths.IDS)
def test_every_registered_verdict_is_one_the_certificate_can_carry(pid):
    d = paths.describe(pid)
    if d["verdict"] is None:
        return
    assert d["verdict"] in certify.EXIT_BY_VERDICT, d
    if d["exit_code"] is not None:
        assert certify.EXIT_BY_VERDICT[d["verdict"]] == d["exit_code"], (
            f"{pid} claims exit {d['exit_code']} for verdict {d['verdict']!r}, but certify maps it "
            f"to {certify.EXIT_BY_VERDICT[d['verdict']]}")


def test_the_composition_sweep_covers_every_required_path():
    """THE GATE. A sweep that models fewer paths than production has now FAILS.

    Imports the mirror from the coherence suite rather than re-implementing it, so there is exactly
    one model of the CLI's decision order and this test measures THAT model's coverage.
    """
    from cytune import test_cytune_coherence as C

    seen = set()
    for gate, policy, winner, win_ns, ref_ns in C._outcomes():
        if policy.excluded_reason(winner):
            continue
        ep = C._endpoint(win_ns, ref_ns, winner)
        C._as_the_cli_would(winner, ep, gate, policy, seen=seen)
        # the honest-flat route (V-1) and the endpoint refusal (V-2) are properties of the RUN,
        # not of the outcome tuple, so they are swept as additional shapes over the same space.
        C._as_the_cli_would(winner, ep, gate, policy, route=C.FLAT_ROUTE, seen=seen)
        C._as_the_cli_would(winner, ep, gate, policy, confirm=False, seen=seen)
        C._as_the_cli_would(winner, C._endpoint_without_wall_clock(win_ns, ref_ns, winner),
                            gate, policy, seen=seen)
        C._as_the_cli_would(winner, C._endpoint(win_ns, ref_ns, winner, corroborates=False),
                            gate, policy, seen=seen)
        C._as_the_cli_would(winner, ep, {**gate, "image_overridden": True}, policy, seen=seen)
    C._as_the_cli_would(None, C._endpoint(100e6, 100e6, C.REF), C.CLEAN_GATE,
                        C._outcomes().__next__()[1], seen=seen)

    missing = sorted(paths.REQUIRED_IDS - seen)
    assert not missing, (
        f"the composition sweep never reached these registered production paths: {missing}.\n"
        f"Either the sweep's fixture space cannot produce them — which is how defect D-3 hid, its "
        f"endpoint records carrying no wall_ns so the C1 branch was unreachable IN PRINCIPLE — or "
        f"a path was added to cli.py and to paths.py but not to _as_the_cli_would.")


def test_the_coverage_check_is_not_vacuous():
    """If REQUIRED_IDS were empty, or the mirror recorded nothing, the gate above would pass while
    testing nothing. Both are asserted here rather than assumed."""
    assert len(paths.REQUIRED_IDS) >= 10, paths.REQUIRED_IDS
    from cytune import test_cytune_coherence as C
    seen = set()
    C._as_the_cli_would(C.REF, C._endpoint(100e6, 100e6, C.REF), C.CLEAN_GATE, None, seen=seen)
    assert seen, "the mirror recorded no path at all — the coverage set is always empty"


def test_paths_the_registry_declines_to_cover_say_why():
    """Every NA / certify-only entry must carry a reason in its note.

    The registry's value is that a gap is VISIBLE and argued, not that there are no gaps.
    """
    for d in paths.as_dicts():
        if d["composition"] != paths.REQUIRED:
            assert len(d["note"]) > 20, (
                f"{d['id']} is excluded from composition coverage with no stated reason")
