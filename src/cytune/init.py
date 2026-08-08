"""`cytune init` — scaffold the driver, because writing one from scratch was the last hard step.

WHY THIS EXISTS. Everything else a first-time user needs is a command they can copy. The driver is
not: it is four names with exact contracts (`make_inputs(seed)`, `call(mod, inputs)`,
`canon(result)`, `OUTPUT_CLASS`), and getting `make_inputs` right means knowing what shapes and
dtypes the kernel wants — which is in the .pyx, which cytune is already reading. The novice-user
agent spent most of its time here, and the tester's T2/T3 findings were both about drivers that
looked finished and were not.

WHAT IT WILL AND WILL NOT GUESS. Typed Cython arguments (`double[::1] a`, `long[:, ::1] idx`,
`Py_ssize_t n`) map onto numpy arrays and scalars unambiguously, so those are filled in. Anything
untyped, or a `object`/`cdef class` parameter, gets a `TODO` marked loudly enough that the driver
does not silently run on made-up data. A scaffold that quietly guessed wrong would be worse than
none: the oracle would be derived from nonsense inputs and every downstream number would be about
a workload the user never intended.

The generated driver is then run through the same contract check `tune` uses, so the user sees it
pass before they spend a minute measuring.
"""
from __future__ import annotations

import json
import os
import re

from . import config as configmod
from .session import META, is_closure

# Cython scalar types -> (python literal for a default, numpy dtype when it appears as a buffer)
_SCALARS = {
    "int": ("128", "np.int32"),
    "long": ("128", "np.int64"),
    "long long": ("128", "np.int64"),
    "short": ("128", "np.int16"),
    "unsigned int": ("128", "np.uint32"),
    "size_t": ("128", "np.uint64"),
    "Py_ssize_t": ("128", "np.intp"),
    "float": ("1.0", "np.float32"),
    "double": ("1.0", "np.float64"),
    "long double": ("1.0", "np.longdouble"),
    "bint": ("True", "np.uint8"),
    "char": ("0", "np.int8"),
}

# `def run(double[::1] a, Py_ssize_t n)` — the leading `def`/`cpdef`/`cdef` and the argument list.
_FUNC = re.compile(r"^\s*(?:cp?def|def)\s+"
                   r"(?:(?P<rtype>[\w \[\]:,*]+?)\s+)??"
                   r"(?P<name>\w+)\s*\((?P<args>[^)]*)\)\s*:", re.MULTILINE)
# `double[::1] a`  /  `long[:, ::1] idx`  /  `Py_ssize_t n`
#
# The whitespace before <name> is REQUIRED, which is what makes an untyped argument (`obj`) fail to
# match and fall through to the unknown branch. Without it the type group happily matched the first
# character and `obj` was scaffolded as an argument named `bj` of type `o` — a wrong guess dressed
# as a confident one, which is the failure mode this whole module is written to avoid.
_ARG = re.compile(r"^\s*(?P<type>[A-Za-z_][\w ]*?)"
                  r"(?P<buf>\[[\s:,\d]*\])?"
                  r"\s+(?P<name>\w+)\s*(?:=\s*(?P<default>.+))?$")


def _entry_point(src):
    """The first PUBLIC function — the one a driver would call.

    `cdef` functions are not callable from Python, so they are skipped rather than offered as an
    entry point the driver could never reach.
    """
    for m in _FUNC.finditer(src):
        line = src[m.start():m.end()]
        if line.lstrip().startswith("cdef "):
            continue
        if m.group("name").startswith("_"):
            continue
        return m.group("name"), m.group("args")
    return None, None


def parse_arguments(args_text):
    """[{name, type, ndim, dtype, known}] for a Cython argument list."""
    out = []
    for raw in _split_args(args_text or ""):
        raw = raw.strip()
        if not raw or raw in ("self", "*", "/"):
            continue
        m = _ARG.match(raw)
        if not m:
            out.append({"name": raw.split()[-1], "type": None, "ndim": 0, "dtype": None,
                        "known": False})
            continue
        ctype = (m.group("type") or "").strip()
        buf = m.group("buf")
        # Dimensions are commas plus one — `[::1]` is ONE dimension, not the two colons it
        # contains, and `[:, ::1]` is two, not three. Counting colons scaffolded a 4096x4096x4096
        # array for `double[:, ::1]`.
        ndim = (buf.count(",") + 1) if (buf and ":" in buf) else 0
        dtype = _SCALARS.get(ctype, (None, None))[1]
        out.append({"name": m.group("name"), "type": ctype or None, "ndim": ndim,
                    "dtype": dtype, "has_default": bool(m.group("default")),
                    "known": bool(ctype and (dtype or ndim == 0) and ctype in _SCALARS)})
    return out


def _split_args(text):
    """Split on commas that are not inside brackets — `double[:, ::1] a` is ONE argument."""
    depth, cur, out = 0, "", []
    for ch in text:
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def _make_input_expr(arg, size_name="N"):
    """The numpy expression for one argument, or None when it must be a TODO."""
    if not arg["known"]:
        return None
    if arg["ndim"] == 0:
        lit = _SCALARS[arg["type"]][0]
        return lit
    shape = "N" if arg["ndim"] == 1 else ", ".join(["N"] * arg["ndim"])
    dtype = arg["dtype"]
    if dtype.startswith("np.float") or dtype == "np.longdouble":
        return f"np.ascontiguousarray(rng.standard_normal(({shape},)).astype({dtype}))"
    if dtype == "np.uint8":
        return f"np.ascontiguousarray((rng.random(({shape},)) > 0.5).astype({dtype}))"
    return f"np.ascontiguousarray(rng.integers(0, 100, size=({shape},)).astype({dtype}))"


DRIVER_TEMPLATE = '''"""cytune driver for {module}, scaffolded by `cytune init`.

FOUR NAMES, and cytune checks all four before it builds anything:

  SCALE          the calibration knob. cytune REWRITES this line so the reference configuration
                 lands near --target-ms. Keep it on its own line, as `SCALE = <int>`.
  make_inputs    fresh inputs for one repetition, from a seed. Called UNTIMED before every timed
                 call, so an in-place kernel cannot contaminate the next repetition.
  call           the timed region. Nothing else is timed.
  canon          the result as a numpy array. This is what the oracle compares, so it must be
                 deterministic and must actually depend on the computation.
  OUTPUT_CLASS   "float" | "int" | "bool". `int` and `bool` get a bit-exact sha256 oracle;
                 `float` gets numpy.allclose at the pre-registered tolerance floor. Declaring an
                 integer kernel as `float` silently downgrades your correctness check.
"""
import numpy as np

SCALE = {scale}

OUTPUT_CLASS = "{output_class}"   # TODO: confirm. "int"/"bool" buy a bit-exact oracle.


def make_inputs(seed):
    """Fresh inputs for ONE repetition. Must be deterministic in `seed`."""
    rng = np.random.default_rng(seed)
    N = SCALE
{inputs}
    return ({names},)


def call(mod, inputs):
    """The TIMED region — keep setup out of it."""
    return mod.{entry}(*inputs)


def canon(result):
    """The result as a numpy array, for the oracle."""
    return np.ascontiguousarray(np.asarray(result))
'''

TODO_BANNER = '''
# ==============================================================================
# cytune could not infer {n} of this kernel's arguments from its signature.
# Fill in the lines marked TODO below. Running as-is will fail the contract check.
# ==============================================================================
'''


# A starting workload that is big enough to time and small enough not to exhaust a 12 GB container
# before calibration has had a chance to shrink it. `SCALE` is one number used for every axis, so
# the safe value falls fast with dimensionality: 4096^2 float64 is 134 MB and 4096^3 is 549 GB.
_SCALE_BY_NDIM = {0: 4096, 1: 4096, 2: 512, 3: 64}


def scaffold_driver(pyx_path, scale=None):
    """Return (driver_source, notes). `notes` lists what could not be inferred."""
    src = open(pyx_path).read()
    entry, args_text = _entry_point(src)
    notes = []
    if not entry:
        entry = "TODO_function_name"
        notes.append("no public `def`/`cpdef` function was found — set `mod.<name>` in call()")
        args = []
    else:
        args = parse_arguments(args_text)

    lines, names = [], []
    unknown = 0
    for a in args:
        if a.get("has_default") and not a["known"]:
            continue
        expr = _make_input_expr(a)
        names.append(a["name"])
        if expr is None:
            unknown += 1
            lines.append(f"    {a['name']} = None   # TODO: {a['type'] or 'untyped'} — cytune "
                         f"cannot infer this; build the value this argument needs")
            notes.append(f"argument {a['name']!r}"
                         + (f" has type {a['type']!r}" if a["type"] else " is untyped")
                         + " — filled in as TODO")
        else:
            lines.append(f"    {a['name']} = {expr}")
    if not args:
        lines.append("    # TODO: build this kernel's inputs")
        notes.append("the entry point takes no arguments cytune could parse")

    body = "\n".join(lines) if lines else "    pass"
    if scale is None:
        max_ndim = max([a["ndim"] for a in args] or [0])
        scale = _SCALE_BY_NDIM.get(max_ndim, 32)
    text = DRIVER_TEMPLATE.format(
        module=os.path.basename(pyx_path), scale=scale, entry=entry,
        output_class="float", inputs=body,
        names=", ".join(names) if names else "")
    if unknown:
        text = text.replace("import numpy as np",
                            "import numpy as np\n" + TODO_BANNER.format(n=unknown).strip())
    return text, notes


CONFIG_TEMPLATE = '''# cytune project defaults. CLI flags win over this file; the certificate records
# the effective value AND where it came from, so a reader never has to guess.
[cytune]
workspace         = "{workspace}"
rig               = "auto"        # auto | quiesced | portable
target_ms         = 65
preset            = "standard"    # quick | standard | thorough
allow_fast_math   = false         # both default OFF: they change floating-point results
allow_fp_contract = false
portable_flags    = false         # true restricts the answer to -march=x86-64
'''


def main_pyx_of(module_path):
    """The .pyx a driver would import, for either a lone file or a module tree."""
    if is_closure(module_path):
        meta = json.load(open(os.path.join(module_path, META)))
        return os.path.join(module_path, "closure", meta["pyx_relpath"])
    return module_path


def init(args):
    """`cytune init <module.pyx>` — write a driver, write a config, prove the contract passes."""
    from .session import Session
    say = print
    module = args.module
    if not os.path.exists(module):
        print(f"cytune: {module} does not exist", file=__import__("sys").stderr)
        return 1
    pyx = main_pyx_of(module)
    if not os.path.exists(pyx):
        print(f"cytune: {pyx} does not exist", file=__import__("sys").stderr)
        return 1

    # Beside the module: INSIDE a module tree, next to a lone .pyx. `os.path.dirname` of a
    # directory is its parent, which put a closure's driver one level above the tree it belongs to.
    home = (os.path.abspath(module) if os.path.isdir(module)
            else os.path.dirname(os.path.abspath(module)) or ".")
    driver_path = args.driver or os.path.join(home, "driver.py")
    if os.path.exists(driver_path) and not args.force:
        print(f"cytune: {driver_path} already exists. Pass --force to overwrite it, or "
              f"--driver PATH to write elsewhere.", file=__import__("sys").stderr)
        return 1

    text, notes = scaffold_driver(pyx)
    with open(driver_path, "w") as f:
        f.write(text)

    say(f"cytune init — {os.path.basename(pyx)}")
    say(f"  wrote {driver_path}")

    cfg = os.path.join(os.getcwd(), configmod.FILENAME)
    if os.path.exists(cfg):
        say(f"  kept  {cfg} (already present)")
    else:
        with open(cfg, "w") as f:
            f.write(CONFIG_TEMPLATE.format(workspace=".cytune"))
        say(f"  wrote {cfg}")

    say("")
    gaps = Session._driver_contract_gaps(driver_path)
    if gaps:
        say("  DRIVER CONTRACT: incomplete — " + ", ".join(gaps))
    else:
        say("  DRIVER CONTRACT: passes (make_inputs, call, canon, OUTPUT_CLASS all present)")

    if notes:
        say("")
        say(f"  {len(notes)} thing(s) cytune could not infer — each is marked TODO in the driver:")
        for n in notes:
            say(f"    - {n}")
        say("")
        say("  Fill those in, then run the command below. cytune deliberately does not guess: an")
        say("  input it invented would give you an oracle derived from data you never intended.")
    say("")
    say("  Next:")
    say(f"    cytune doctor")
    say(f"    cytune tune {module} --driver {driver_path} --dry-run")
    return 0 if not gaps else 1
