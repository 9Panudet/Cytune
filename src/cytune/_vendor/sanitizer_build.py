"""The ASan+UBSan build, extracted from the study's `sanitizer_spot_audit.py`.

This is the ONE vendored file that is not a whole-file copy. The study module is 373 lines, of
which the product needs three things: `SAN_TOKENS`, `CORNERS`, and `_sanitizer_build`. The rest is
the study's own roster/memoisation/reporting, and it drags in `san_overlay` (another 210 lines)
purely to enumerate fleet kernels that do not exist in a user's checkout. Vendoring all of that to
reach one function would put ~580 unreachable lines in the package, which A3 forbids.

So the three product-relevant definitions are copied here verbatim and the study's module-scope
plumbing is replaced with the vendored equivalents. `test_cytune_vendor.py::
test_sanitizer_build_matches_the_study_function_source` compares the SOURCE TEXT of
`_sanitizer_build` against the study's, and asserts SAN_TOKENS and CORNERS are equal, so this file
cannot drift from the audited original any more quietly than the byte-identical ones can.
"""
from __future__ import annotations

import os
import shutil
import subprocess

import build as bld
import theta
from profiles import sanitizer_argv

# A sanitizer report is decisive (halt_on_error=1) but the tokens are also matched textually,
# because a report that does not kill the process must not be silently accepted.
SAN_TOKENS = ("AddressSanitizer", "LeakSanitizer", "runtime error", "buffer-overflow",
              "use-after", "stack-overflow", "SUMMARY: AddressSanitizer",
              "SUMMARY: UndefinedBehavior", "UndefinedBehaviorSanitizer")

# (name, config) — the study's pre-registered sanitizer corners. `cytune audit` extends this with
# the per-directive singles; see cytune/audit.py::RISK_SET, which imports CORNERS from here so the
# two cannot diverge.
CORNERS = [
    ("reference", theta.REFERENCE),
    ("checks_off_O3_native_unroll",
     (False, False, True, False, False, "-O3", "native", "on", ("off", "off"))),
    ("checks_off_fastmath_native",
     (False, False, True, False, False, "-O3", "native", "on", ("on", "NA"))),
]


def _sanitizer_build(kdir, config, cache_dir, so_dir, module_hint):
    """Cythonize via THE campaign builder (so the C is byte-identical to what was measured), then
    link with profiles.sanitizer_argv instead of the performance profile. Returns dict."""
    meta = bld._meta(kdir)
    fm_on = config[8][0] == "on"
    _d, _o, ffp, _l = theta.build_flags(config)
    os.makedirs(so_dir, exist_ok=True)
    if meta and meta.get("cobuild"):
        # Co-build anchors: cythonize every module, then link them all with the sanitizer flags
        # into a per-config copy of the closure tree (same layout measure_child imports from).
        cid = theta.id_of(config)
        combo = bld._combo_key(config)
        work = os.path.join(cache_dir, f"sanwork_{combo}")
        if os.path.exists(work):
            shutil.rmtree(work)
        shutil.copytree(os.path.join(kdir, "closure"), work)
        dirs = _d
        c_map = []
        for pyx_rel, mod in meta["cobuild"]:
            c_path = os.path.join(cache_dir, f"san_{mod}_{combo}.c")
            if not os.path.exists(c_path):
                r = subprocess.run(["cython", "-3"] + dirs.split() + ["-I", ".", pyx_rel,
                                                                     "-o", c_path],
                                   cwd=work, capture_output=True, text=True)
                if r.returncode != 0 or not os.path.exists(c_path):
                    shutil.rmtree(work, ignore_errors=True)
                    return {"ok": False, "reason": "cythonize_fail",
                            "log": (r.stdout + r.stderr)[-600:]}
            c_map.append((pyx_rel, mod, c_path))
        shutil.rmtree(work, ignore_errors=True)
        pkg_root = os.path.join(so_dir, f"sanpkg_{cid}")
        if os.path.exists(pkg_root):
            shutil.rmtree(pkg_root)
        shutil.copytree(os.path.join(kdir, "closure"), pkg_root,
                        ignore=shutil.ignore_patterns("*.c"))
        main_so = None
        for pyx_rel, mod, c_path in c_map:
            so = os.path.join(pkg_root, pyx_rel[:-4] + ".so")
            argv = sanitizer_argv(ffp_contract=ffp, c_path=c_path, so_path=so,
                                  py_include=bld.PYINC, fast_math=fm_on)
            argv = argv[:1] + [f"-I{bld.NPINC}"] + argv[1:]
            if meta.get("openmp"):
                argv = argv[:1] + ["-fopenmp"] + argv[1:]
            r = subprocess.run(argv, capture_output=True, text=True)
            if r.returncode != 0 or not os.path.exists(so):
                return {"ok": False, "reason": "build_fail",
                        "log": f"{mod}: " + (r.stdout + r.stderr)[-600:]}
            main_so = so
        return {"ok": True, "so_path": main_so, "module": meta["module"]}

    if meta:
        c_path, ok, clog = bld._cythonize_closure(kdir, config, cache_dir, meta)
        module = meta["module"]
    else:
        c_path, ok, clog = bld._cythonize_synth(kdir, config, cache_dir)
        module = module_hint
    if not ok:
        return {"ok": False, "reason": "cythonize_fail", "log": clog}
    so = os.path.join(so_dir, f"san_{module}_{theta.id_of(config)}.so")
    argv = sanitizer_argv(ffp_contract=ffp, c_path=c_path, so_path=so,
                          py_include=bld.PYINC, fast_math=fm_on)
    argv = argv[:1] + [f"-I{bld.NPINC}"] + argv[1:]
    r = subprocess.run(argv, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(so):
        return {"ok": False, "reason": "build_fail", "log": (r.stdout + r.stderr)[-600:]}
    return {"ok": True, "so_path": so, "module": module}
