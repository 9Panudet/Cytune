"""cytune session — workspace, ingest, and the three measured phases (roadmap §8.1 steps 1/2/4).

A session owns one workspace directory laid out exactly like the study's, so the SAME container
entrypoints work unchanged:

    <workspace>/_kernels/<name>/{kernel.pyx, driver.py}   the vendored module under test
    <workspace>/<name>/{build_manifest.jsonl, oracle.json, golden.npy, table.jsonl, ...}   raw

Every measurement lands in table.jsonl before anything is claimed about it, so every number in the
certificate has a raw pointer and a recompute path — the same rule the study lives under.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import subprocess

from . import binding, lock, rig


# --------------------------------------------------------------------------------- cache keys
#
# B3 — CACHE-KEY COMPLETENESS. Reusing a measurement taken under different conditions is the D5/D6
# defect class, and finding R4 was a live instance of it: `table.jsonl` survived a `--target-ms`
# change, so a 38% smaller workload produced a byte-identical `delta_probe`. That was fixed by
# putting the calibration in the key. This makes the whole class structurally impossible instead of
# fixing one member of it.
#
# TWO KEYS, because the two artifacts have different dependencies:
#
#   build key        what the compiled .so depends on: the module source and the toolchain image.
#                    A change here invalidates builds AND every measurement taken from them.
#   measurement key  what a timing depends on: the build key, plus the driver, the calibrated
#                    workload, the rig mode, and the oracle. A change here keeps the .so files —
#                    which is what makes a re-run fast — and discards the timings.
#
# DELIBERATELY NOT IN EITHER KEY: the emission-policy flags (--allow-fast-math,
# --allow-fp-contract, --portable-flags). They change which configs are SELECTED and which may be
# emitted; they do not change what a measurement of config X yields. Invalidating on them would
# throw away valid timings every time a user added a flag, and would be a claim — "this number
# depended on your policy" — that is not true. They are recorded in the cache metadata so the
# provenance of a reused row is still complete. `test_cytune_cache.py` pins this exclusion together
# with its reason, so a future reader finds the argument rather than an omission.

_KNOB_LINE = re.compile(r"^(REPS|SCALE)\s*=.*$", re.MULTILINE)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


def file_digest(path, normalise_knob=False):
    """Content hash of a source file.

    `normalise_knob=True` blanks the driver's `REPS =` / `SCALE =` line before hashing. cytune
    REWRITES that line itself during calibration, so hashing the raw file would make the driver
    look changed on every single run and invalidate the cache unconditionally — a cache that always
    misses is not safer, it just moves the cost somewhere the user pays it.
    """
    try:
        src = open(path).read()
    except OSError:
        return None
    if normalise_knob:
        src = _KNOB_LINE.sub("<calibration knob>", src)
    return _sha(src)


def tree_digest(root):
    """Content hash of every source file under a module tree, path included.

    A closure compiles from many files, so hashing only the named .pyx would miss an edit to a
    `.pxd` it cimports — which is precisely the change most likely to alter the generated C while
    leaving the .pyx untouched. Paths are hashed alongside contents so a renamed file counts.
    """
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in ("_so", "_ccache", "__pycache__"))
        for fn in sorted(filenames):
            if fn.endswith((".pyc", ".so", ".c", ".o")):
                continue
            p = os.path.join(dirpath, fn)
            h.update(os.path.relpath(p, root).encode())
            try:
                with open(p, "rb") as f:
                    h.update(f.read())
            except OSError:
                h.update(b"<unreadable>")
    return h.hexdigest()[:16]


def build_key(module_path, image):
    """What the compiled .so depends on."""
    sha = tree_digest(module_path) if is_closure(module_path) else file_digest(module_path)
    return {"module_sha": sha, "image": image}


def measurement_key(module_path, driver_path, image, target_ms, knob, knob_value, rig_mode,
                    oracle=None):
    """What a timing depends on. Includes the build key: a rebuilt .so invalidates its timings."""
    orc = oracle or {}
    return {
        **build_key(module_path, image),
        "driver_sha": file_digest(driver_path, normalise_knob=True),
        "target_ms": target_ms,
        "knob": knob,
        "knob_value": knob_value,
        "rig_mode": rig_mode,
        "oracle_class": orc.get("output_class"),
        "oracle_tolerance": orc.get("tolerance"),
        "golden_sha256": orc.get("golden_sha256"),
    }


# Human-readable reason per key field, printed when invalidation fires so the user learns WHY the
# cache was dropped rather than watching a re-run happen for no stated reason.
KEY_REASONS = {
    "module_sha": "the module source changed",
    "image": "the pinned toolchain image changed",
    "driver_sha": "the driver changed",
    "target_ms": "--target-ms changed",
    "knob": "the driver's calibration knob changed",
    "knob_value": "the calibrated workload size changed",
    "rig_mode": "the measurement rig mode changed",
    "oracle_class": "the oracle's output class changed",
    "oracle_tolerance": "the oracle tolerance changed",
    "golden_sha256": "the golden output changed",
}

BUILD_FIELDS = ("module_sha", "image")


# Bumped whenever the SET of key fields changes. A cache written by an older cytune does not carry
# the newer fields, so "field absent" would otherwise read as "field unchanged" and the first run
# after an upgrade would reuse measurements the new key was introduced to invalidate.
KEY_SCHEMA = 1


def key_diff(prev, now):
    """[(field, reason, old, new)] for every field that CHANGED.

    A field missing from `prev` is not a change: on a first run the stored key holds only what has
    been computed so far (the build fields are written before the measurement fields exist), and
    treating absence as difference discarded the table on every first run. Upgrades are handled by
    KEY_SCHEMA instead, which is explicit about it.
    """
    if not prev:
        return []
    return [(k, KEY_REASONS.get(k, k), prev.get(k), now.get(k))
            for k in now if k in prev and prev.get(k) != now.get(k)]


def key_schema_changed(prev):
    """True when the stored key came from a cytune with a different set of key fields."""
    return bool(prev) and prev.get("_schema") != KEY_SCHEMA


class IngestError(RuntimeError):
    pass


class BuildFailure(IngestError):
    """Every candidate failed to compile. Carries the compiler's own words (F6)."""


META = "kernel_meta.json"

# The five directives cytune varies. A `# cython:` file header that names any of them silently
# defeats the entire search — see check_pinned_directives.
TUNED_DIRECTIVES = ("boundscheck", "wraparound", "cdivision", "initializedcheck", "nonecheck")
_CYTHON_HEADER = re.compile(r"^\s*#\s*cython\s*:\s*(.+)$", re.IGNORECASE)

# The OTHER two ways a source file pins a directive, both of which override -X for the code they
# cover and neither of which is a `# cython:` header:
#
#     @cython.boundscheck(False)          decorator on one function
#     with cython.boundscheck(False):     block inside one
#
# Found by the focused adversarial re-run as an untested degeneracy-evasion route.
#
# THESE ARE REPORTED, NOT REFUSED, AND THE REASON IS MEASURED. A file header neutralises a directive
# for the WHOLE module — every combination compiles identically, the search measures one program 33
# times, and nothing it says about directives is true. A decorator neutralises it for ONE function:
# the rest of the module still varies, the search still measures something real, and the emitted
# header still applies everywhere else.
#
# The proportionality matters because refusing on decorators would have blocked three of the nine
# real scipy/scikit-learn anchors this product was validated against — `_ppoly`, `_shortest_path`
# and `_traversal` all use them, and all three still produce 21 distinct generated sources from 21
# directive combinations, i.e. they are not degenerate. Refusing a third of real library code to
# guard against a lie that applies to a few functions would be the wrong trade, so the certificate
# names the file, the line and the directive instead.
_CYTHON_SCOPED = re.compile(
    r"^\s*(?:@|with\s+)(?:cython\s*\.\s*)?(" + "|".join(TUNED_DIRECTIVES) + r")\s*\(")


# Every file Cython reads that may carry a `# cython:` header. A header in an INCLUDED or CIMPORTED
# file neutralises the -X flags exactly as one in the named .pyx does, and the first version of
# this check looked only at the .pyx the user named.
_CYTHON_SOURCE_EXT = (".pyx", ".pxd", ".pxi", ".py")


def check_scoped_directives_tree(root, main_pyx=None):
    """{relpath: {directive: text}} over a whole module tree, for the scoped forms."""
    return _scan_tree(root, main_pyx, check_scoped_directives)


def check_pinned_directives_tree(root, main_pyx=None):
    """Every pinned directive anywhere in a module tree — {relpath: {name: text}}.

    WHY THE WHOLE TREE. Real Cython modules are not one file: the nine anchors this product was
    validated against all cimport siblings. A `# cython: boundscheck=False` header in a cimported
    .pxd defeats the search for every module that includes it, and produces the identical lie —
    a certificate offering `boundscheck=True` for a translation unit compiled with it off.

    The I4.2 degeneracy check does NOT cover this case, which is a measured fact rather than a
    guess: `test_cytune_binding.py::test_the_degeneracy_check_names_the_directives_a_header_
    neutralised` shows the original H12 header leaves several distinct source classes, so the
    total-collapse refusal never fires. It reports `boundscheck` and `wraparound` as inert — real
    and useful, but a report is not a refusal. This is the refusal, and it is exact.
    """
    return _scan_tree(root, main_pyx, check_pinned_directives)


def _scan_tree(root, main_pyx, scan):
    found = {}
    if os.path.isfile(root):
        hit = scan(root)
        return {os.path.basename(root): hit} if hit else {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in ("_so", "_ccache", "__pycache__"))
        for fn in sorted(filenames):
            if not fn.endswith(_CYTHON_SOURCE_EXT):
                continue
            p = os.path.join(dirpath, fn)
            hit = scan(p)
            if hit:
                found[os.path.relpath(p, root)] = hit
    if main_pyx and os.path.exists(main_pyx):
        hit = scan(main_pyx)
        if hit:
            found.setdefault(os.path.basename(main_pyx), hit)
    return found


def check_pinned_directives(pyx_path):
    """Refuse a module whose own header pins a directive cytune is varying.

    THE DEFECT THIS PREVENTS (H12, found by the adversarial campaign, and it needs no adversary).

    In Cython a `# cython:` file header takes precedence over the `-X` flags on the command line —
    and `-X` is how the builder applies every configuration in Θ. So on a module carrying

        # cython: boundscheck=False, wraparound=False

    all 32 directive combinations compile to BYTE-IDENTICAL C. Measured in the pinned image: 0
    bounds-check sites with the header, 3 without, and `-X boundscheck=True` versus
    `-X boundscheck=False` produced identical output. The search still ran, still timed 33
    configurations, still picked a winner and still certified it — describing directives that were
    never applied, including calling config 288 "Cython's safe defaults" when it had been compiled
    with the checks off. The §1.4 gate then cleared a build that was not the build described.

    Every claim in that certificate is false, and nothing in the coherence gate could see it: I1
    verifies the DOCUMENT against the config id, and the config id was never what got built.

    Headers like this are ordinary in production Cython, so this is refused rather than warned
    about. A warning was already in the README and did not stop it — that is precisely the
    difference between a claim and a guarantee.

    Directives cytune does NOT vary (`language_level`, `cpow`, `embedsignature`, ...) are fine and
    are left alone: verified in the pinned image that a header naming only `cpow` leaves `-X
    boundscheck` working.
    """
    try:
        src = open(pyx_path).read()
    except OSError:
        return None
    pinned = {}
    for line in src.splitlines():
        m = _CYTHON_HEADER.match(line)
        if not m:
            # Cython only honours the header in the leading comment block; stop at the first line
            # that is neither a comment nor blank.
            if line.strip() and not line.lstrip().startswith("#"):
                break
            continue
        for part in m.group(1).split(","):
            if "=" not in part:
                continue
            name = part.split("=", 1)[0].strip()
            if name in TUNED_DIRECTIVES:
                pinned[name] = part.strip()
    return pinned or None


def check_scoped_directives(path):
    """{directive: "line N: <text>"} for decorators and `with` blocks that pin a tuned directive.

    Reported, never refused — see the comment on `_CYTHON_SCOPED` for why, and for the measurement
    that decided it.
    """
    try:
        src = open(path).read()
    except OSError:
        return None
    found = {}
    for line_no, line in enumerate(src.splitlines(), 1):
        m = _CYTHON_SCOPED.match(line)
        if m:
            found.setdefault(m.group(1), f"line {line_no}: {line.strip()}")
    return found or None


def is_closure(path):
    """Is this a multi-file MODULE TREE rather than a single .pyx?

    Real library code is not one file. Every kernel in this project's own Dataset R — nine modules
    from scipy and scikit-learn — `cimport`s siblings and needs the surrounding package on the
    include path to compile at all. cytune's ingest accepted a lone .pyx, which meant the product
    could not be pointed at the very code the study measured. Found by the ground-truth dogfood in
    the v1.0.0 release pass, which is exactly the sort of thing dogfooding is for.

    A closure directory holds `kernel_meta.json` (naming the .pyx to build, relative to `closure/`)
    and a `closure/` tree. The BUILD side already understood this — `_vendor/build.py::
    _cythonize_closure` has always handled it, because the study builds these kernels — so this is
    an ingest gap, not a missing capability.
    """
    return os.path.isdir(path) and os.path.exists(os.path.join(path, META))


def validate_inputs(module_path, driver_path):
    """Check both user-supplied paths BEFORE any directory is created.

    Two cold-user findings at once. F9: the old message was `not found: <path>` for either
    argument, so a user who mistyped one of two paths could not tell which. F11: the check
    happened inside Session, which had already created `.cytune/<name>/` and
    `.cytune/_kernels/<name>/` in the user's working directory — a run that found nothing still
    left litter behind, and for a bad --driver it had already vendored kernel.pyx.
    """
    problems = []
    if not os.path.exists(module_path):
        parent = os.path.dirname(os.path.abspath(module_path)) or "."
        hint = f" (the directory {parent} does not exist either)" if not os.path.isdir(parent) else ""
        problems.append(f"module: {module_path} does not exist{hint}")
    elif os.path.isdir(module_path):
        if not is_closure(module_path):
            problems.append(
                f"module: {module_path} is a directory but has no {META} — cytune expects either "
                f"`cytune tune <module.pyx>` or a module tree containing {META} and closure/")
        else:
            meta = os.path.join(module_path, META)
            try:
                rel = json.load(open(meta)).get("pyx_relpath")
            except (OSError, json.JSONDecodeError) as e:
                rel, problems = None, problems + [f"module: {meta} is not readable JSON ({e})"]
            if rel and not os.path.exists(os.path.join(module_path, "closure", rel)):
                problems.append(f"module: {META} names {rel}, which is not under "
                                f"{os.path.join(module_path, 'closure')}")
    elif not module_path.endswith(".pyx"):
        problems.append(f"module: {module_path} does not end in .pyx — "
                        f"cytune expects `cytune tune <module.pyx> --driver <driver.py>`")

    if not os.path.exists(driver_path):
        parent = os.path.dirname(os.path.abspath(driver_path)) or "."
        hint = f" (the directory {parent} does not exist either)" if not os.path.isdir(parent) else ""
        if os.path.isdir(driver_path):
            hint = " (that is a directory, not a file)"
        problems.append(f"--driver: {driver_path} does not exist{hint}")
    elif os.path.isdir(driver_path):
        problems.append(f"--driver: {driver_path} is a directory, not a file")
    elif not driver_path.endswith(".py"):
        problems.append(f"--driver: {driver_path} does not end in .py — "
                        f"cytune expects `cytune tune <module.pyx> --driver <driver.py>`")

    if problems:
        raise IngestError("\n  ".join(["bad arguments:"] + problems))


def _last_json(text):
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


class Session:
    def __init__(self, workspace, name, mode, mode_detail, log_path=None, target_ms=65.0):
        self.workspace = os.path.abspath(workspace)
        self.name = name
        self.mode = mode
        self.mode_detail = mode_detail
        self.target_ms = target_ms
        self.kdir = os.path.join(self.workspace, "_kernels", name)
        self.odir = os.path.join(self.workspace, name)
        self.log_path = log_path or os.path.join(self.workspace, f"{name}.log")
        self.transcript = []
        self._made = False

    def _ensure(self):
        """Create the workspace only when there is actually something to put in it (F11)."""
        if not self._made:
            os.makedirs(self.kdir, exist_ok=True)
            os.makedirs(self.odir, exist_ok=True)
            self._made = True

    # ---------------------------------------------------------------- plumbing
    # Phases whose numbers are only meaningful on an uncontended machine. B3 asserts the
    # machine-level lock is held before any of them runs, so that no future code path can time
    # something outside `cli.tune`'s lock scope. Shaped like the CF-4 asserts: cheap, at the
    # boundary, pointing at the rule it protects.
    TIMED_PHASES = ("golden", "measure", "endpoint")

    def _run(self, cmd, phase):
        if phase in self.TIMED_PHASES:
            lock.assert_held(phase)
            lk = lock.current()
            if lk is not None:
                lk.heartbeat(phase)
        self._ensure()
        with open(self.log_path, "a") as f:
            f.write(f"\n$ {' '.join(cmd)}\n")
            f.flush()
            r = subprocess.run(cmd, capture_output=True, text=True)
            f.write(r.stdout)
            f.write(r.stderr)
        self.transcript.append({"phase": phase, "cmd": cmd, "rc": r.returncode})
        payload = _last_json(r.stdout)
        if r.returncode != 0 or payload is None:
            tail = (r.stdout + r.stderr)[-800:]
            raise IngestError(f"{phase} failed (rc={r.returncode}): {tail}")
        return payload

    def _ids_arg(self, ids):
        return "probe" if ids == "probe" else ",".join(str(i) for i in ids)

    # ------------------------------------------------------------------ ingest
    def vendor(self, pyx_path, driver_path):
        """Copy the user's module + driver into the workspace. We never build in-place: the build
        writes .c/.so next to sources and calibration may rewrite the driver knob, and doing either
        to a user's working tree would be rude and irreversible."""
        validate_inputs(pyx_path, driver_path)
        # Contract check BEFORE copying anything: a driver that cannot work should not leave a
        # vendored kernel behind (F11).
        missing = self._driver_contract_gaps(driver_path)
        if missing:
            raise IngestError(
                "driver does not satisfy the measurement contract, missing: " + ", ".join(missing) +
                "\n  a cytune driver must define: make_inputs(seed) -> inputs, call(mod, inputs) -> "
                "result, canon(result) -> numpy array, and OUTPUT_CLASS in {float,int,bool}"
                "\n  see docs/USER_GUIDE.md for a driver template you can copy")
        # H12 — before anything is copied or built. A header that pins a varied directive makes
        # every configuration compile identically, so the run would measure one build 33 times and
        # certify it under 33 different descriptions.
        main_pyx = pyx_path
        if is_closure(pyx_path):
            _m = json.load(open(os.path.join(pyx_path, META)))
            main_pyx = os.path.join(pyx_path, "closure", _m["pyx_relpath"])
        pinned_tree = check_pinned_directives_tree(pyx_path, main_pyx)
        if pinned_tree:
            names = sorted({n for p in pinned_tree.values() for n in p})
            where = "\n  ".join(f"{rel}: # cython: {v}"
                                for rel, p in sorted(pinned_tree.items())
                                for v in sorted(p.values()))
            raise IngestError(
                "your module pins directives that cytune varies, so tuning it is impossible:\n  "
                + where
                + "\n\n  A `# cython:` file header OVERRIDES the -X flags cytune builds with, so"
                  "\n  those configurations would compile to identical code and the certificate"
                  "\n  would describe directives that were never applied. This is checked across"
                  "\n  the WHOLE module tree, because a header in a cimported .pxd defeats the"
                  "\n  search for every file that includes it.\n"
                  "\n  Remove " + ", ".join(names) + " from the header(s) above and re-run. cytune"
                  "\n  will tell you what to put back — that is what it is for. Directives it does"
                  "\n  not vary (language_level, cpow, embedsignature, ...) can stay.")

        self._ensure()
        if is_closure(pyx_path):
            # A module TREE: copy kernel_meta.json and the whole closure/, which is the layout the
            # builder already expects. The driver still comes from --driver and is copied last, so
            # a closure that happens to ship its own driver.py cannot silently override the one the
            # user named.
            for entry in os.listdir(pyx_path):
                s, d = os.path.join(pyx_path, entry), os.path.join(self.kdir, entry)
                if entry == "driver.py":
                    continue
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
            meta = json.load(open(os.path.join(pyx_path, META)))
            main_pyx = os.path.join(pyx_path, "closure", meta["pyx_relpath"])
            shutil.copy2(driver_path, os.path.join(self.kdir, "driver.py"))
            return {"pyx": os.path.abspath(main_pyx), "driver": os.path.abspath(driver_path),
                    "vendored_to": self.kdir, "closure": True, "module": meta.get("module"),
                    "scoped_directives": check_scoped_directives_tree(pyx_path, main_pyx) or None,
                    "has_fp_work": self._has_fp_work(main_pyx)}
        for src, dst in ((pyx_path, "kernel.pyx"), (driver_path, "driver.py")):
            shutil.copy2(src, os.path.join(self.kdir, dst))
        return {"pyx": os.path.abspath(pyx_path), "driver": os.path.abspath(driver_path),
                "vendored_to": self.kdir, "closure": False,
                "scoped_directives": check_scoped_directives_tree(pyx_path, main_pyx) or None,
                "has_fp_work": self._has_fp_work(pyx_path)}

    @staticmethod
    def _has_fp_work(pyx_path):
        """Heuristic (F21): does this module plausibly do floating-point arithmetic?

        Used only to decide whether to print the FLOATING-POINT SEMANTICS block. Deliberately
        biased toward saying YES — over-warning is the safe failure direction for a warning — and
        the certificate labels it a heuristic. A kernel that computes in double and returns an
        int with no float declaration would read as False here; that is the known blind spot.
        """
        try:
            src = open(pyx_path).read()
        except OSError:
            return None
        return any(tok in src for tok in ("double", "float", "complex"))

    OUTPUT_CLASSES = ("float", "int", "bool")

    @staticmethod
    def _driver_contract_gaps(driver_path):
        """Checked by PARSING the source, not by importing it and not by substring search.

        Not importing is deliberate: importing a stranger's driver on the host runs arbitrary code
        outside the container, and the container is where their code is allowed to run.

        Not substring-searching is the fix for T2 (systematic-tester agent). The old check was
        `if "OUTPUT_CLASS" not in src`, so a driver that merely MENTIONED the name — in a comment,
        in a docstring, in `# TODO: set OUTPUT_CLASS` — satisfied the contract. The run then
        proceeded with no output class at all and the oracle fell back to `float`, the
        TOLERANCE-based mode. An integer kernel silently lost the bit-exact sha256 oracle that
        G1 promises it, and nothing anywhere said so. `def make_inputs` in a comment was rejected
        (the `def ` prefix made it accidentally stricter), so the two halves of one contract were
        checked to two different standards.

        Parsing also lets the VALUE be validated: `OUTPUT_CLASS = "banana"` used to reach the
        certificate (T3).
        """
        import ast
        src = open(driver_path).read()
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            return [f"the driver is not valid Python ({e.msg} at line {e.lineno})"]

        funcs = {n.name for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        gaps = [n for n in ("make_inputs", "call", "canon") if n not in funcs]

        assigned = {}
        for node in tree.body:                       # module level only
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target] if isinstance(node, ast.AnnAssign) else [])
            for t in targets:
                if isinstance(t, ast.Name):
                    assigned[t.id] = getattr(node, "value", None)
        if "OUTPUT_CLASS" not in assigned:
            gaps.append("OUTPUT_CLASS")
        else:
            v = assigned["OUTPUT_CLASS"]
            if isinstance(v, ast.Constant) and v.value not in Session.OUTPUT_CLASSES:
                gaps.append(
                    f"OUTPUT_CLASS = {v.value!r} is not one of "
                    f"{', '.join(Session.OUTPUT_CLASSES)} — cytune cannot derive an oracle from it")
        return gaps

    def build(self, ids, require_any=False):
        """Compile `ids`. With require_any=True, a TOTAL build failure aborts immediately and
        carries the compiler's own output (F6) instead of letting the run limp into golden
        capture and die there with an internal string."""
        res = self._run(rig.build_cmd(self.workspace, self.name, self._ids_arg(ids)), "build")
        if require_any and res.get("n_built") == 0 and res.get("n_requested"):
            diag = res.get("first_failure") or {}
            log = (diag.get("log") or "").strip() or "(the compiler produced no output)"
            host_log = os.path.join(self.odir, "build_failure.log")
            raise BuildFailure(
                f"your module did not compile — {res['n_requested']} of {res['n_requested']} "
                f"configurations failed ({diag.get('reason', 'unknown')}).\n\n"
                f"  first failure, config {diag.get('config_id')}:\n"
                + "\n".join("    " + l for l in log.splitlines()[-25:])
                + f"\n\n  full build log: {host_log}"
                + "\n  Fix the module and re-run. cytune cannot derive an oracle from a module "
                  "that does not build.")
        return res

    def reusable_knob(self, module_path, driver_path, image=None):
        """The calibrated workload from a previous run, when nothing it depends on has changed.

        Calibration is a property of (module, driver, target_ms, image, rig mode) and of nothing
        else, so re-deriving it on an unchanged re-run costs a measurement and — because the
        calibrated value is in the measurement cache key — lands on a different integer and
        discards the entire table. See `worker.cmd_golden` for how long that went unnoticed.

        Deliberately compares only the fields that are KNOWN before golden capture. The oracle
        fields are settled by golden itself, and a stale oracle is caught by
        `invalidate_stale_measurements` immediately afterwards.
        """
        prev = self._stored_key()
        if not prev or prev.get("knob_value") is None or key_schema_changed(prev):
            return None
        now = {**build_key(module_path, image if image is not None else rig.IMAGE),
               "driver_sha": file_digest(driver_path, normalise_knob=True),
               "target_ms": self.target_ms, "rig_mode": self.mode}
        if any(prev.get(k) != v for k, v in now.items()):
            return None
        return prev["knob_value"]

    def golden(self, reuse_knob=None):
        args = [self.target_ms] + ([reuse_knob] if reuse_knob is not None else [])
        cmd = rig.measure_cmd(self.workspace, self.name, self.mode, "golden", args)
        res = self._run(cmd, "golden")
        if not res.get("ok"):
            raise IngestError(f"{res.get('error')} — {res.get('hint', '')}")
        return res

    KEYFILE = "cache_key.json"

    def _stored_key(self):
        p = os.path.join(self.odir, self.KEYFILE)
        if not os.path.exists(p):
            return None
        try:
            return json.load(open(p))
        except (OSError, json.JSONDecodeError):
            return None

    def _merge_key(self, fields):
        self._ensure()
        key = self._stored_key() or {}
        key.update(fields)
        key["_schema"] = KEY_SCHEMA
        with open(os.path.join(self.odir, self.KEYFILE), "w") as f:
            json.dump(key, f, indent=2)
        return key

    def _next_archive(self, stem):
        n = 1
        while os.path.exists(os.path.join(self.odir, f"{stem}_{n}.jsonl")):
            n += 1
        return os.path.join(self.odir, f"{stem}_{n}.jsonl")

    def _drop_table(self, stale):
        table = os.path.join(self.odir, "table.jsonl")
        stale["n_rows"] = 0
        if os.path.exists(table):
            dest = self._next_archive("table_stale")
            stale["n_rows"] = sum(1 for _ in open(table))
            shutil.move(table, dest)
            stale["archived_to"] = dest

    def invalidate_stale_builds(self, module_path, image=None):
        """Runs BEFORE the first build.

        The `.so` files depend on the module source and the toolchain image, and on nothing else.
        `campaign.build_all` resumes by trusting `build_manifest.jsonl` alone — a config with a
        manifest row is "done" — which is correct inside the study, where a kernel's source never
        changes once its table exists. In a product workspace the user edits the kernel and runs
        again, and without this the measure phase is handed a binary compiled from the PREVIOUS
        source while the certificate reports it under the new one.

        This must run before `build`, not after: by the time the golden output is captured, the
        stale .so has already produced it.
        """
        key = build_key(module_path, image if image is not None else rig.IMAGE)
        prev = self._stored_key()
        changed = key_diff(prev, key)
        if key_schema_changed(prev):
            changed = changed or [("_schema", "cytune's cache key changed in a new version",
                                   prev.get("_schema"), KEY_SCHEMA)]
        stale = None
        if changed:
            stale = {"changed": [{"field": f, "reason": r, "was": o, "now": n}
                                 for f, r, o, n in changed],
                     "reasons": [r for _f, r, _o, _n in changed],
                     "invalidated_builds": True, "n_builds": 0}
            man = os.path.join(self.odir, "build_manifest.jsonl")
            if os.path.exists(man):
                dest = self._next_archive("build_manifest_stale")
                stale["n_builds"] = sum(1 for _ in open(man))
                shutil.move(man, dest)
            # I4: an artifact record whose .so is about to be deleted is worse than no record —
            # it would satisfy a binding check for a file that no longer exists.
            binding.drop(self.odir)
            for d in ("_so", "_ccache"):
                p = os.path.join(self.odir, d)
                if os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
            # A timing taken from a binary that no longer exists cannot be reused either.
            self._drop_table(stale)
        self._merge_key(key)
        return stale

    def invalidate_stale_measurements(self, golden, module_path=None, driver_path=None,
                                      image=None):
        """Runs AFTER golden capture, when the calibrated workload and the oracle are known.

        Drops timings only; the builds stay, which is what makes a re-run fast. Finding R4 was one
        member of this class — `table.jsonl` survived a `--target-ms` change, so a 38% smaller
        workload reported a byte-identical `delta_probe`. The key now carries every input that can
        change what a timing means.
        """
        cal = (golden or {}).get("calibrated") or {}
        key = measurement_key(
            module_path, driver_path, image if image is not None else rig.IMAGE,
            self.target_ms, (golden or {}).get("knob") or cal.get("knob"), cal.get("new"),
            self.mode, (golden or {}).get("oracle"))
        # Build fields were already settled by invalidate_stale_builds; compare only the rest, so a
        # single edit is not reported twice.
        prev = self._stored_key()
        measure_only = {k: v for k, v in key.items() if k not in BUILD_FIELDS}
        changed = key_diff(prev, measure_only) if prev else []
        stale = None
        if changed:
            stale = {"changed": [{"field": f, "reason": r, "was": o, "now": n}
                                 for f, r, o, n in changed],
                     "reasons": [r for _f, r, _o, _n in changed],
                     "invalidated_builds": False}
            self._drop_table(stale)
        self._merge_key(key)
        return stale

    def measure(self, ids):
        cmd = rig.measure_cmd(self.workspace, self.name, self.mode, "measure", [self._ids_arg(ids)])
        return self._run(cmd, "measure")

    def endpoint(self, ids):
        cmd = rig.measure_cmd(self.workspace, self.name, self.mode, "endpoint", [self._ids_arg(ids)])
        return self._run(cmd, "endpoint")

    # ------------------------------------------------------- pure compute (no timing)
    def features(self):
        return self._run(rig.compute_cmd(self.workspace, self.name, "features", []), "features")

    def screen_plan(self, budget, second_screen=False):
        args = [budget] + (["--second-screen"] if second_screen else [])
        return self._run(rig.compute_cmd(self.workspace, self.name, "screen", args), "screen")

    def walk_plan(self, budget, policy=None):
        args = [budget]
        if policy is not None:
            if policy.allow_fast_math:
                args.append("--allow-fast-math")
            if policy.allow_fp_contract:
                args.append("--allow-fp-contract")
            if policy.portable_flags:
                args.append("--portable-flags")
        return self._run(rig.compute_cmd(self.workspace, self.name, "walk", args), "walk")

    # ------------------------------------------------------------------- state
    def table_rows(self):
        p = os.path.join(self.odir, "table.jsonl")
        if not os.path.exists(p):
            return {}
        out = {}
        for line in open(p):
            r = json.loads(line)
            out[r["config_id"]] = r
        return out

    def feasible_medians(self):
        return {cid: r["screen"]["median_ns"] for cid, r in self.table_rows().items()
                if r.get("feasible") and r.get("screen")}

    @property
    def table_path(self):
        return os.path.join(self.odir, "table.jsonl")

    # ------------------------------------------------------------- I4 artifact binding
    def artifacts(self):
        """{config_id: build record}. The host's view of what was actually compiled."""
        return binding.read(self.odir)

    def source_tree_sha256(self):
        """Digest of the vendored kernel tree, computed the same way the sanitizer container
        computes it over /kdir — that is what makes the two comparable (I4.3)."""
        return binding.tree_sha256(self.kdir)
