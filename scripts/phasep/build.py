"""Per-config build pipeline (PREREG §4.4): cythonize (cached per 32-combo) -> gcc -> .so.

Two modes, auto-detected from the kernel dir:
  synthetic : kernel_dir/kernel.pyx (module "kernel"), generator kernels.
  closure   : kernel_dir/kernel_meta.json + kernel_dir/closure/ (a vendored package), R anchors.
              Cythonize meta['pyx_relpath'] with -I closure_root so package-relative cimports
              (e.g. csr's `..utils._typedefs`) resolve; module name = meta['module'].
Runs in-container. Cythonize depends only on the 5 Cython directives; cache the .c per directive
combo (32/kernel). gcc per full config. Cythonize failure is cached once for the whole directive
combo (β policy) -> feasibility-0.
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import time
import theta

PYINC = subprocess.run(["python3", "-c", "import sysconfig;print(sysconfig.get_path('include'))"],
                       capture_output=True, text=True).stdout.strip()
NPINC = subprocess.run(["python3", "-c", "import numpy;print(numpy.get_include())"],
                       capture_output=True, text=True).stdout.strip()


def _combo_key(config):
    return "".join("1" if v else "0" for v in theta.directive_combo(config))


def _meta(kernel_dir):
    p = os.path.join(kernel_dir, "kernel_meta.json")
    return json.load(open(p)) if os.path.exists(p) else None


def _cythonize_synth(kernel_dir, config, cache_dir):
    combo = _combo_key(config)
    os.makedirs(cache_dir, exist_ok=True)
    c_path = os.path.join(cache_dir, f"kernel_{combo}.c")
    fail = c_path + ".FAIL"
    if os.path.exists(fail):
        return c_path, False, "cythonize_fail (cached)"
    if os.path.exists(c_path):
        return c_path, True, "cached"
    dirs, _o, _f, _l = theta.build_flags(config)
    pyx = os.path.join(kernel_dir, "kernel.pyx")
    r = subprocess.run(["cython", "-3"] + dirs.split() + ["-I", kernel_dir, pyx, "-o", c_path],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(c_path):
        open(fail, "w").write((r.stdout + r.stderr)[-800:])
        return c_path, False, "cythonize_fail"
    return c_path, True, "ok"


def _cythonize_closure(kernel_dir, config, cache_dir, meta):
    combo = _combo_key(config)
    os.makedirs(cache_dir, exist_ok=True)
    c_path = os.path.join(cache_dir, f"{meta['module']}_{combo}.c")
    fail = c_path + ".FAIL"
    if os.path.exists(fail):
        return c_path, False, "cythonize_fail (cached)"
    if os.path.exists(c_path):
        return c_path, True, "cached"
    work = os.path.join(cache_dir, f"work_{combo}")
    if os.path.exists(work):
        shutil.rmtree(work)
    shutil.copytree(os.path.join(kernel_dir, "closure"), work)
    dirs, _o, _f, _l = theta.build_flags(config)
    pyx = os.path.join(work, meta["pyx_relpath"])
    r = subprocess.run(["cython", "-3"] + dirs.split() + ["-I", work, pyx, "-o", c_path],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(c_path):
        open(fail, "w").write((r.stdout + r.stderr)[-800:])
        return c_path, False, "cythonize_fail"
    return c_path, True, "ok"


def _build_cobuild_config(kernel_dir, config, cache_dir, so_dir, meta, t0):
    """PACKAGE-IMPORT co-build (v1 delta_probe_pkg recipe): cythonize every cobuild module (dep
    order, per directive combo, cached) then gcc them INTO a per-config copy of the closure tree —
    the closure ships the package skeleton (__init__ shims) proven in v1; the child imports
    meta['pkg_module'] with that tree on sys.path[0]. Any stage failing ⇒ whole-config
    feasibility-0 (cythonize failures cached once per combo)."""
    combo = _combo_key(config)
    os.makedirs(cache_dir, exist_ok=True)
    fail = os.path.join(cache_dir, f"cobuild_{combo}.FAIL")
    if os.path.exists(fail):
        return {"ok": False, "reason": "cythonize_fail", "so_path": None,
                "compile_s": time.perf_counter() - t0, "so_size_b": 0,
                "log": "cythonize_fail (cached)"}
    dirs, opt_flags, ffp, _l = theta.build_flags(config)
    c_paths = []
    need = [(pyx, mod, os.path.join(cache_dir, f"{mod}_{combo}.c"))
            for pyx, mod in meta["cobuild"]]
    if not all(os.path.exists(c) for _p, _m, c in need):
        work = os.path.join(cache_dir, f"work_{combo}")
        if os.path.exists(work):
            shutil.rmtree(work)
        shutil.copytree(os.path.join(kernel_dir, "closure"), work)
        for pyx_rel, mod, c_path in need:
            if os.path.exists(c_path):
                continue
            r = subprocess.run(["cython", "-3"] + dirs.split() + ["-I", ".", pyx_rel,
                                                                  "-o", c_path],
                               cwd=work, capture_output=True, text=True)
            if r.returncode != 0 or not os.path.exists(c_path):
                open(fail, "w").write(f"{mod}: " + (r.stdout + r.stderr)[-800:])
                shutil.rmtree(work, ignore_errors=True)
                return {"ok": False, "reason": "cythonize_fail", "so_path": None,
                        "compile_s": time.perf_counter() - t0, "so_size_b": 0,
                        "log": f"cythonize {mod} failed"}
        shutil.rmtree(work, ignore_errors=True)
    c_paths = need
    cid = theta.id_of(config)
    pkg_root = os.path.join(so_dir, f"pkg_{cid}")
    if os.path.exists(pkg_root):
        shutil.rmtree(pkg_root)
    shutil.copytree(os.path.join(kernel_dir, "closure"), pkg_root,
                    ignore=shutil.ignore_patterns("*.c"))
    omp = ["-fopenmp"] if meta.get("openmp") else []
    main_so, total_b = None, 0
    for pyx_rel, mod, c_path in c_paths:
        so = os.path.join(pkg_root, pyx_rel[:-4] + ".so")
        cmd = (["gcc-13", "-shared", "-fPIC"] + opt_flags.split() +
               [f"-ffp-contract={ffp}"] + omp +
               ["-g0", "-pipe", f"-I{PYINC}", f"-I{NPINC}", c_path, "-o", so])
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(so):
            return {"ok": False, "reason": "build_fail", "so_path": None,
                    "compile_s": time.perf_counter() - t0, "so_size_b": 0,
                    "log": f"{mod}: " + (r.stdout + r.stderr)[-800:]}
        total_b += os.path.getsize(so)
        main_so = so
    return {"ok": True, "reason": "ok", "so_path": main_so,
            "compile_s": time.perf_counter() - t0, "so_size_b": total_b,
            "module": meta["module"]}


def build_config(kernel_dir, config, cache_dir, so_dir):
    """Full per-config build. Returns dict(ok, reason, so_path, compile_s, so_size_b[, log])."""
    t0 = time.perf_counter()
    meta = _meta(kernel_dir)
    module = meta["module"] if meta else "kernel"
    if meta and meta.get("cobuild"):
        return _build_cobuild_config(kernel_dir, config, cache_dir, so_dir, meta, t0)
    if meta:
        c_path, ok, clog = _cythonize_closure(kernel_dir, config, cache_dir, meta)
    else:
        c_path, ok, clog = _cythonize_synth(kernel_dir, config, cache_dir)
    if not ok:
        return {"ok": False, "reason": "cythonize_fail", "so_path": None,
                "compile_s": time.perf_counter() - t0, "so_size_b": 0, "log": clog}
    cid = theta.id_of(config)
    os.makedirs(so_dir, exist_ok=True)
    so = os.path.join(so_dir, f"{module}_{cid}.so")
    if os.path.exists(so):
        os.remove(so)
    _d, opt_flags, ffp, _l = theta.build_flags(config)
    cmd = (["gcc-13", "-shared", "-fPIC"] + opt_flags.split() +
           [f"-ffp-contract={ffp}", "-g0", "-pipe", f"-I{PYINC}", f"-I{NPINC}", c_path, "-o", so])
    r = subprocess.run(cmd, capture_output=True, text=True)
    compile_s = time.perf_counter() - t0
    if r.returncode != 0 or not os.path.exists(so):
        return {"ok": False, "reason": "build_fail", "so_path": None,
                "compile_s": compile_s, "so_size_b": 0, "log": (r.stdout + r.stderr)[-800:]}
    return {"ok": True, "reason": "ok", "so_path": so, "compile_s": compile_s,
            "so_size_b": os.path.getsize(so), "module": module}
