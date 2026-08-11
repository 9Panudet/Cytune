"""A2/A3 — the one-way dependency rule, and leanness measured rather than asserted.

THE RULE. `src/cytune/**` may not import study, replay or benchmark code. cytune is a product; it
ships as a package and must work with no `scripts/` and no `results/` directory anywhere on the
machine. Before the v1.0.0 architecture pass it did the opposite: `_phasep.py` inserted
`scripts/phasep` onto `sys.path` and the package imported `theta`, `campaign`, `classify`,
`algorithms` and `sanitizer_spot_audit` from the study tree, while `rig.py` mounted both
`scripts/` and `results/` into every measurement container.

WHY THE STRONGEST FORM OF THIS TEST IS AN EXECUTION, NOT AN ASSERTION. A static import scan can be
defeated by a lazy `import` inside a function, a `sys.path` insert, or a data file read at runtime.
So the load-bearing test here (`test_the_package_imports_with_no_study_tree_on_sys_path`) launches
a subprocess whose `sys.path` cannot reach the study tree and imports every product module. If any
module still needs `scripts/phasep`, it raises there.

The static scans are kept as well, because they fail with a better message and they catch a
violation that a broad `except ImportError` would hide.
"""
from __future__ import annotations

import ast
import glob
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG_PARENT = os.path.dirname(HERE)

# Modules that exist only to run, analyse or report the Phase-P study. None may be imported by the
# product. `campaign`/`theta`/`classify`/`algorithms`/`build`/`seeds` are NOT on this list: they are
# vendored into `cytune/_vendor/` and are product code now, byte-pinned by test_cytune_vendor.py.
STUDY_ONLY = {
    "replay", "run_study", "run_fleet", "run_pilot", "generate", "generate_v2", "analyze_study",
    "report_p1", "report_p2", "r_anchor", "rqp2_acceptance", "a2_reclassify", "san_overlay",
    "sanitizer_spot_audit", "smoke_r_anchors", "a2_anchor_smoke", "run_probe_int", "bc_effect",
    "build_phase", "measure_phase", "cytune_phase", "motifbo",
}

# Filesystem paths that only exist inside a full study checkout. A product module naming one of
# these is reaching outside the package even if it never imports anything.
STUDY_PATHS = ("scripts/phasep", "/probe/phasep", "/probe", "/results/prereg", "results/fleet")

# The two ways cytune is entered: the console script (`cytune`, host side) and the container-side
# worker. Everything shipped in the package must be reachable from one of them, or from the
# explicitly-listed subprocess entry points below.
ENTRY_POINTS = ("cytune.cli", "cytune.worker", "cytune.audit")


def _product_sources():
    return sorted(p for p in glob.glob(os.path.join(HERE, "**", "*.py"), recursive=True)
                  if not os.path.basename(p).startswith("test_"))


def _rel(path):
    return os.path.relpath(path, HERE)


def _imported_names(src):
    """Top-level module names imported by this source, including inside functions."""
    tree = ast.parse(src)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


# --------------------------------------------------------------------------- A2: static scans
@pytest.mark.parametrize("path", _product_sources(), ids=_rel)
def test_no_product_module_imports_study_code(path):
    bad = _imported_names(open(path).read()) & STUDY_ONLY
    assert not bad, (
        f"{_rel(path)} imports study code {sorted(bad)}. cytune must ship standalone — vendor what "
        f"the product genuinely needs into cytune/_vendor/ (byte-pinned by test_cytune_vendor.py), "
        f"or move the test to tests/ if it is a study-equivalence check.")


@pytest.mark.parametrize("path", _product_sources(), ids=_rel)
def test_no_product_module_names_a_study_path(path):
    """String literals, docstrings excluded — prose may discuss the old arrangement."""
    tree = ast.parse(src := open(path).read())
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docs.add(id(body[0].value))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            for frag in STUDY_PATHS:
                if frag in node.value:
                    hits.append((frag, node.value[:120]))
    assert not hits, f"{_rel(path)} names a study path: {hits}"


def test_the_import_scan_actually_catches_a_violation():
    """Positive control. A scanner that matched nothing would pass every file silently."""
    planted = "import os\nimport replay\nfrom run_fleet import roster\n"
    assert _imported_names(planted) & STUDY_ONLY == {"replay", "run_fleet"}


def test_the_import_scan_sees_imports_hidden_inside_functions():
    """The old bridge was imported lazily inside functions in three modules, so a top-level-only
    scan would have called the violating arrangement clean."""
    planted = "def f():\n    import replay\n    return replay\n"
    assert "replay" in _imported_names(planted)


# ------------------------------------------------------------------- A2: the executable proof
def test_the_package_imports_with_no_study_tree_on_sys_path():
    """Import every product module in a subprocess that cannot see scripts/ or results/.

    This is the guarantee itself rather than a proxy for it. `sys.path` is reduced to the package's
    parent plus the stdlib, and the repo root — the only thing from which `scripts/phasep` is
    reachable by relative path — is removed.
    """
    mods = sorted({_rel(p)[:-3].replace(os.sep, ".").removesuffix(".__init__")
                   for p in _product_sources()} - {"__main__"})
    prog = (
        "import sys, os\n"
        f"sys.path = [p for p in sys.path if p and 'scripts' not in p]\n"
        f"sys.path.insert(0, {PKG_PARENT!r})\n"
        "import importlib\n"
        f"for m in {mods!r}:\n"
        "    importlib.import_module('cytune.' + m if m != '' else 'cytune')\n"
        "print('OK')\n")
    r = subprocess.run([sys.executable, "-c", prog], capture_output=True, text=True,
                       cwd=os.path.dirname(PKG_PARENT), env={**os.environ, "PYTHONPATH": ""})
    assert "OK" in r.stdout, (
        f"the package does not import standalone.\nstdout: {r.stdout}\nstderr: {r.stderr[-2500:]}")


def test_container_mounts_expose_only_the_package_and_workspace():
    """A measurement container must not be able to see the study tree at all.

    The mount list is where "ships standalone" is either true or a slogan: while `scripts/` and
    `results/` were mounted, a container-side module could reach the study's frozen tables whatever
    the import graph said.
    """
    from cytune import rig
    mounts = [a for a in rig._mounts("/tmp/ws") if ":" in a and a.startswith("/")]
    assert len(mounts) == 2, f"expected exactly 2 mounts (package, workspace), got {mounts}"
    srcs = [m.split(":")[0] for m in mounts]
    assert os.path.abspath(srcs[0]) == HERE, f"first mount must be the package, got {srcs[0]}"
    assert srcs[1] == "/tmp/ws"
    joined = " ".join(rig._mounts("/tmp/ws"))
    for frag in ("/probe", "/results", "scripts"):
        assert frag not in joined, f"container still sees {frag}: {joined}"


def test_the_sanitizer_gate_mounts_only_the_package_and_the_kernel_dir():
    from cytune import sanitize_gate as sg
    assert "/repo" not in sg._SNIPPET, "the gate snippet still reaches into a repo mount"
    assert "scripts/phasep" not in sg._SNIPPET


# ------------------------------------------------------------------------ A3: leanness, measured
# Launched as subprocesses, never imported, so no import edge points at them.
SUBPROCESS_ENTRY_POINTS = {"_vendor/measure_child.py", "_vendor/san_child.py"}

# Sample kernel + driver shipped for the quickstart. DATA, not code: `running_max_driver.py` is
# passed to `--driver` and executed inside the container, never imported by the package. Pinned by
# test_the_shipped_example_exists_and_is_documented so it cannot rot into dead weight.
EXAMPLE_DATA = {"examples/running_max.pyx", "examples/running_max_driver.py"}

# Enumerations the SHIPPED TEST MODULES consume, not the runtime. `paths.py` is B4's registry of
# production's verify/emit decision paths; it is data about cli.py, walked by test_cytune_paths.py
# to fail when the composition sweep models fewer paths than production has (the shape defect D-3
# was the fourth instance of). The reachability walk deliberately excludes test modules, so a
# registry only they import reads as dead — the same reason `examples/` is exempt.
#
# Exempt, not unpinned: `test_test_support_is_actually_used` below asserts a shipped test really
# imports it, so this cannot become a hiding place for dead code.
TEST_SUPPORT = {"paths.py"}


def _module_key(path):
    """`src/cytune/_vendor/build.py` -> `_vendor/build.py`, the key used by the reachability walk."""
    return _rel(path).replace(os.sep, "/")


def _import_graph():
    """path -> set of package-internal files it imports, following LAZY imports too.

    Static rather than runtime, because half the package's imports are deliberately lazy: `plan.py`
    imports `algorithms` inside `walk_plan()` so the host never needs numpy, and `campaign.py`
    imports `build` inside `build_all()`. A runtime "what is in sys.modules after importing cli"
    check reports all of those as dead.
    """
    by_key = {_module_key(p): p for p in _product_sources()}
    # Bare-name imports (`import theta`) resolve against _vendor/, which puts itself on sys.path.
    vendor_by_base = {os.path.basename(k)[:-3]: k for k in by_key if k.startswith("_vendor/")}
    pkg_by_base = {os.path.basename(k)[:-3]: k for k in by_key if "/" not in k}

    graph = {}
    for key, path in by_key.items():
        tree = ast.parse(open(path).read())
        deps = set()

        def _add(name):
            base = name.split(".")[-1] if "." in name else name
            for table in (vendor_by_base, pkg_by_base):
                if base in table:
                    deps.add(table[base])

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    _add(a.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    _add(node.module)
                # `from . import certify, config` / `from ._vendor import theta`
                if node.level and node.module is None:
                    for a in node.names:
                        _add(a.name)
                if node.level and node.module:
                    for a in node.names:
                        _add(f"{node.module}.{a.name}")
        graph[key] = deps
    return by_key, graph


def _container_snippet_imports():
    """The §1.4 gate ships a Python program as a STRING and runs it inside the container. Its
    imports are real import edges that no AST walk of the package would otherwise see."""
    from cytune import sanitize_gate as sg
    names = set()
    for node in ast.walk(ast.parse(sg._SNIPPET)):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


def test_every_product_module_is_reachable_from_an_entry_point():
    """Dead code is deleted, not tolerated (A3).

    Every .py in the package must be reachable, through the static import graph, from one of:
    the console script (`cytune.cli`), the container worker (`cytune.worker`), the audit command,
    the §1.4 gate's container snippet, or an explicitly-listed subprocess entry point.
    """
    by_key, graph = _import_graph()

    seeds = {"cli.py", "worker.py", "audit.py", "__init__.py", "__main__.py"}
    seeds |= SUBPROCESS_ENTRY_POINTS
    # the gate's in-container program
    vendor_by_base = {os.path.basename(k)[:-3]: k for k in by_key if k.startswith("_vendor/")}
    for name in _container_snippet_imports():
        base = name.split(".")[-1]
        if base in vendor_by_base:
            seeds.add(vendor_by_base[base])
        if name.startswith("cytune."):
            tail = name.split(".", 1)[1].replace(".", "/") + ".py"
            if tail in by_key:
                seeds.add(tail)
            if (tail := name.split(".", 1)[1].replace(".", "/") + "/__init__.py") in by_key:
                seeds.add(tail)

    for k in SUBPROCESS_ENTRY_POINTS:
        assert k in by_key, f"{k} is listed as a subprocess entry point but does not exist"

    seen, stack = set(), [s for s in seeds if s in by_key]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(graph.get(cur, ()))

    unreachable = sorted(set(by_key) - seen - EXAMPLE_DATA - TEST_SUPPORT)
    assert not unreachable, (
        f"unreachable from any entry point: {unreachable}\n"
        f"Delete it, or move it out of the package. A3 measures leanness rather than assuming it. "
        f"If it is genuinely reachable by a route this graph cannot see (a subprocess, a container "
        f"snippet), add it to the seed list WITH the reason.")


def test_test_support_is_actually_used():
    """The exemption above is not a hiding place.

    Every TEST_SUPPORT module must exist AND be imported by a shipped test module. An exemption
    nobody checks is how dead code survives a leanness gate.
    """
    tests = [f for f in os.listdir(HERE) if f.startswith("test_") and f.endswith(".py")]
    assert tests, "no shipped test modules found"
    for rel in sorted(TEST_SUPPORT):
        assert os.path.exists(os.path.join(HERE, rel)), f"TEST_SUPPORT module missing: {rel}"
        mod = rel[:-3]
        importers = []
        for t in tests:
            tree = ast.parse(open(os.path.join(HERE, t)).read())
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[-1] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [a.name for a in node.names]
                    if node.module:
                        names.append(node.module.split(".")[-1])
                if mod in names:
                    importers.append(t)
                    break
        assert importers, (
            f"{rel} is exempted from the reachability walk as test support, but no shipped test "
            f"imports it. Delete it or use it.")


def test_the_reachability_walk_would_notice_a_dead_module():
    """Positive control: a file nothing imports must come out unreachable."""
    by_key, graph = _import_graph()
    graph["_dead_module.py"] = set()
    by_key["_dead_module.py"] = "/nonexistent"
    seen, stack = set(), ["cli.py"]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(graph.get(cur, ()))
    assert "_dead_module.py" not in seen


def test_the_reachability_walk_follows_lazy_imports():
    """`plan.py` imports `algorithms` inside a function body. If the walk missed that, the vendored
    fit code would read as dead and the obvious 'fix' would be to delete the thing the DOE search
    depends on."""
    _by_key, graph = _import_graph()
    assert "_vendor/algorithms.py" in graph["plan.py"], \
        "the import graph missed plan.py's function-local `import algorithms`"


def test_the_shipped_example_exists_and_is_documented():
    """`examples/` is data, so the reachability walk skips it — which means something else has to
    stop it rotting. It must exist, and the docs must actually point a user at it."""
    for rel in EXAMPLE_DATA:
        assert os.path.exists(os.path.join(HERE, rel)), f"shipped example missing: {rel}"
    repo = os.path.dirname(os.path.dirname(HERE))
    docs = []
    for cand in ("README.md", os.path.join("docs", "USER_GUIDE.md")):
        p = os.path.join(repo, cand)
        if os.path.exists(p):
            docs.append(open(p).read())
    assert docs, "no docs found to check"
    assert any("running_max" in d for d in docs), (
        "the package ships examples/running_max.pyx but no document mentions it. Either point the "
        "quickstart at it or delete it — an undocumented example is dead weight.")
