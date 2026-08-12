"""Repo-level tests: the ones that are allowed to touch the study tree.

`src/cytune/**` may not import study/replay/benchmark code — that is the one-way dependency rule
(docs/ARCHITECTURE.md), enforced by `test_cytune_architecture.py`. But cytune's DOE planner *claims*
to reproduce `algorithms.doe`'s trajectory exactly, and a claim like that is only worth what its
test is worth. The test therefore has to import the study's `algorithms` and `replay` — so it lives
here, outside the package, where doing so is legitimate.

Everything under `src/cytune/` must pass with no `scripts/` and no `results/` present. Everything
here may assume the full repo checkout and skips cleanly when a study artifact is missing.

WHY THE STUDY MODULES ARE LOADED BY PATH AND NOT BY `import algorithms`.

`cytune/_vendor/` contains files with the SAME top-level names as the study's — `theta`,
`campaign`, `classify`, `algorithms` — and its `__init__` puts itself at `sys.path[0]` so that the
verbatim copies' bare imports resolve to each other. That insert happens whenever anything imports
cytune, which every test here does, so a plain `import algorithms` in this directory resolves to
the VENDORED copy.

That would make the equivalence test compare cytune against itself: it would load cytune's own fit
code, assert it agrees with cytune's own fit code, and pass forever while the two implementations
drifted arbitrarily far apart. A test that cannot fail is worse than no test, and this one exists
specifically to catch drift.

So the study modules are loaded from their files under distinct names (`study_algorithms`,
`study_replay`), which cannot be shadowed. `test_the_study_modules_are_not_the_vendored_ones`
asserts they really came from `scripts/phasep`.
"""
from __future__ import annotations

import importlib.util
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
STUDY = os.path.join(REPO, "scripts", "phasep")

for _p in (os.path.join(REPO, "src"), STUDY):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)          # append, never insert: _vendor owns the front of sys.path


def load_study_module(name, alias=None):
    """Import `scripts/phasep/<name>.py` under `alias`, bypassing sys.path entirely."""
    path = os.path.join(STUDY, f"{name}.py")
    if not os.path.exists(path):
        return None
    alias = alias or f"study_{name}"
    if alias in sys.modules:
        return sys.modules[alias]
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod
