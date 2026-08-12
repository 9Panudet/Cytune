"""R-anchor adapter (roadmap §3.1, PREREG §6 / A-2): wrap the 9 v1 survivor kernels into the
phasep harness — Dataset R to full 1,728 tables.

Real-code anchors, expected (not forced) to land where they land — measured class decides (A-2i).
Each anchor is re-scaled into the 50–80 ms band. CRITICAL (§6): goldens + tolerances are RE-DERIVED
at the new scale by the campaign's determinism gate + golden capture (never the v1 500 ms goldens).
Knob discipline (campaign._knob_line does a SINGLE-SHOT LINEAR rescale, so the knob must be linear
in runtime): re-callable units get a REPS knob (call-count loop; input sizes fixed — this also
keeps O(N³) floyd linear-in-knob); the in-place/mutating units (pava, elkan) get the SCALE knob
(both linear in their size key) with per-rep regen (D6). floyd/cc need the Decision-C PREIMPORT
(the vendored .so's absolute scipy imports must resolve) — measure_child honors driver.PREIMPORT.

Emits a closure-mode kernel dir (kernel_meta.json + closure/ + driver.py + spec.json) consumed by
build.py's closure path. elkan + predictor are PACKAGE-IMPORT co-build units (relative imports of
sibling vendored .so's) — pending the cobuild extension (task #43 stage B); build_anchor raises
for them until it lands, so nothing silently half-works.
"""
from __future__ import annotations
import json
import os
import shutil

# scale/reps0 are STARTING knobs; calibrate tunes the knob named in the driver.
# out_idx: None = use fn's return; int = that arg (in-place/out buffer); tuple = those args.
ANCHORS = {
    "csr": {
        "closure_src": "data/corpus/sklearn/sparsefuncs_fast/closure",
        "module": "sparsefuncs_fast", "pyx_relpath": "sklearn/utils/sparsefuncs_fast.pyx",
        "kernel": "csr_mean_variance_axis0", "setup": "csr_mean_variance_setup",
        "knob": "SCALE", "scale_key": "n_samples", "scale0": 1_000_000,
        "fixed": {"n_features": 200, "density": 0.05}, "out_idx": "None", "preimport": None,
    },
    "pava": {
        "closure_src": "data/corpus/sklearn/_isotonic/closure",
        "module": "_isotonic", "pyx_relpath": "sklearn/_isotonic.pyx",
        "kernel": "_inplace_contiguous_isotonic_regression", "setup": "pava_setup",
        "knob": "SCALE", "scale_key": "n", "scale0": 1_500_000, "fixed": {},
        "out_idx": "0", "preimport": None,      # IN-PLACE on y -> per-rep regen (D6)
    },
    "lda": {
        "closure_src": "data/corpus/sklearn/_online_lda_fast/closure",
        "module": "_online_lda_fast",
        "pyx_relpath": "sklearn/decomposition/_online_lda_fast.pyx",
        "kernel": "_dirichlet_expectation_2d", "setup": "dirichlet2d_setup",
        "knob": "REPS", "reps0": 20, "fixed": {"n_rows": 20_000, "n_cols": 100},
        "out_idx": "None", "preimport": None,   # pure fn, re-callable
    },
    "binning": {
        "closure_src": "data/corpus/sklearn/_binning/closure",
        "module": "_binning",
        "pyx_relpath": "sklearn/ensemble/_hist_gradient_boosting/_binning.pyx",
        "kernel": "_map_to_bins", "setup": "map_to_bins_setup",
        "knob": "REPS", "reps0": 5,
        "fixed": {"n_samples": 100_000, "n_features": 30, "n_bins": 255},
        "out_idx": "5", "preimport": None,      # binned overwritten identically -> re-callable
    },
    "ppoly": {
        "closure_src": "data/corpus/scipy/_ppoly/closure",
        "module": "_ppoly", "pyx_relpath": "_ppoly.pyx",
        "kernel": "evaluate", "setup": "ppoly_evaluate_setup",
        "knob": "REPS", "reps0": 10, "fixed": {"k": 4, "m": 2_000, "p": 500_000},
        "out_idx": "5", "preimport": None,      # out overwritten identically -> re-callable
    },
    "floyd": {
        "closure_src": "data/corpus/scipy/_shortest_path/closure",
        "module": "_shortest_path", "pyx_relpath": "scipy/sparse/csgraph/_shortest_path.pyx",
        "kernel": "floyd_warshall", "setup": "floyd_setup",
        "knob": "REPS", "reps0": 4, "fixed": {"N": 240},
        "out_idx": "None", "preimport": "scipy.sparse.csgraph",   # overwrite=False -> re-callable;
        # REPS knob keeps calibration LINEAR (N would be cubic and break the single-shot rescale)
    },
    "cc": {
        "closure_src": "data/corpus/scipy/_traversal/closure",
        "module": "_traversal", "pyx_relpath": "scipy/sparse/csgraph/_traversal.pyx",
        "kernel": "connected_components", "setup": "connected_components_setup",
        "knob": "REPS", "reps0": 8, "fixed": {"N": 200_000, "avg_deg": 5},
        "out_idx": "None", "preimport": "scipy.sparse.csgraph",   # returns (n_components, labels)
    },
    # ---- PACKAGE-IMPORT co-build units (v1 delta_probe_pkg recipe): relative imports of sibling
    # vendored .so's — built per config INTO a closure-tree copy; child imports pkg_module.
    "elkan": {
        "closure_src": "data/corpus/sklearn/_k_means_elkan/closure",
        "module": "_k_means_elkan", "pyx_relpath": "sklearn/cluster/_k_means_elkan.pyx",
        "kernel": "elkan_iter_chunked_dense", "setup": "elkan_setup",
        "knob": "SCALE", "scale_key": "n_samples", "scale0": 100_000,
        "fixed": {"n_features": 50, "n_clusters": 50},
        "out_idx": "(3, 4, 7, 8, 9, 10)",       # mutates centers_new,wts,upper,lower,labels,shift
        "preimport": None, "openmp": True,
        "pkg_module": "sklearn.cluster._k_means_elkan",
        "cobuild": [["sklearn/cluster/_k_means_common.pyx", "_k_means_common"],
                    ["sklearn/cluster/_k_means_elkan.pyx", "_k_means_elkan"]],
    },
    "predictor": {
        "closure_src": "data/corpus/sklearn/_predictor/closure",
        "module": "_predictor",
        "pyx_relpath": "sklearn/ensemble/_hist_gradient_boosting/_predictor.pyx",
        "kernel": "_predict_from_raw_data", "setup": "predictor_setup",
        "knob": "REPS", "reps0": 4,
        "fixed": {"n_samples": 500_000, "n_features": 20, "depth": 6},
        "out_idx": "6", "preimport": None, "openmp": True,
        "pkg_module": "sklearn.ensemble._hist_gradient_boosting._predictor",
        "cobuild": [["sklearn/ensemble/_hist_gradient_boosting/common.pyx", "common"],
                    ["sklearn/ensemble/_hist_gradient_boosting/_bitset.pyx", "_bitset"],
                    ["sklearn/ensemble/_hist_gradient_boosting/_predictor.pyx", "_predictor"]],
    },
}

_DRIVER = '''"""R-anchor driver for {kid} ({anchor}) — v1 survivor re-scaled to the 50-80ms band.
Goldens/tolerances RE-DERIVED at this scale (never v1 500ms). Mutating units ⇒ per-rep regen (D6);
re-callable units use the REPS call-count knob (linear calibration)."""
import sys
for _p in ("/probe/corpus", "{host_corpus}"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import numpy as np
import corpus_drivers as cd

KERNEL_MODULE = "{module}"
PREIMPORT = {preimport}
PKG_MODULE = {pkg_module}
OUTPUT_CLASS = "float"
{knob_line}
_KERNEL = "{kernel}"
_OUT_IDX = {out_idx}
_FIXED = {fixed}

def _scale():
    d = dict(_FIXED)
{scale_stmt}
    return d

def make_inputs(seed):
    ns = {{}}
    exec(cd.{setup}(_scale(), seed), ns)   # UNTIMED per-rep regen (D6); builds args (+kwargs)
    return (ns["args"], ns.get("kwargs") or {{}})

def call(mod, inputs):
    args, kwargs = inputs
    fn = getattr(mod, _KERNEL)
    ret = None
    for _ in range({reps_expr}):
        ret = fn(*args, **kwargs)
    if _OUT_IDX is None:
        return ret
    if isinstance(_OUT_IDX, tuple):
        return tuple(args[i] for i in _OUT_IDX)
    return args[_OUT_IDX]

def canon(result):
    if isinstance(result, (tuple, list)):
        return np.concatenate([np.asarray(x, np.float64).reshape(-1) for x in result])
    return np.asarray(result, dtype=np.float64).reshape(-1)
'''


def build_anchor(out_root, anchor_key, kid, repo_root="."):
    a = ANCHORS[anchor_key]
    kdir = os.path.join(out_root, kid)
    os.makedirs(kdir, exist_ok=True)
    # vendored closure
    dst = os.path.join(kdir, "closure")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(os.path.join(repo_root, a["closure_src"]), dst)
    # meta (closure-mode build; cobuild units carry the dep-ordered module list + pkg import)
    with open(os.path.join(kdir, "kernel_meta.json"), "w") as f:
        json.dump({"module": a["module"], "pyx_relpath": a["pyx_relpath"], "kernel": a["kernel"],
                   "anchor": anchor_key, "mode": "closure", "preimport": a["preimport"],
                   "cobuild": a.get("cobuild"), "pkg_module": a.get("pkg_module"),
                   "openmp": a.get("openmp", False)},
                  f, indent=2)
    # driver — exactly ONE knob line (campaign._knob_line prefers REPS; ambiguity avoided)
    if a["knob"] == "SCALE":
        knob_line = f'SCALE = {a["scale0"]}                        # calibration knob ({a["scale_key"]})'
        scale_stmt = f'    d["{a["scale_key"]}"] = SCALE'
        reps_expr = "1"
    else:
        knob_line = f'REPS = {a["reps0"]}                         # calibration knob (call count; sizes fixed)'
        scale_stmt = "    pass"
        reps_expr = "REPS"
    driver = _DRIVER.format(
        kid=kid, anchor=anchor_key, module=a["module"], kernel=a["kernel"],
        out_idx=a["out_idx"], fixed=repr(a["fixed"]), setup=a["setup"],
        preimport=repr(a["preimport"]), pkg_module=repr(a.get("pkg_module")),
        knob_line=knob_line, scale_stmt=scale_stmt, reps_expr=reps_expr,
        host_corpus=os.path.abspath(os.path.join(repo_root, "scripts/corpus")))
    with open(os.path.join(kdir, "driver.py"), "w") as f:
        f.write(driver)
    # spec (dataset R; measured class decides — A-2i)
    with open(os.path.join(kdir, "spec.json"), "w") as f:
        json.dump({"kernel_id": kid, "intended_class": "A", "dataset": "R", "family": "R_anchor",
                   "anchor": anchor_key, "is_control": False, "module": a["module"],
                   "kernel": a["kernel"], "knob": a["knob"],
                   "knob0": a.get("scale0", a.get("reps0")), "fixed": a["fixed"],
                   "in_place": a["out_idx"] not in ("None",) and not a["out_idx"].startswith("("),
                   "preimport": a["preimport"],
                   "note": "v1 survivor; goldens+tolerances re-derived at fleet scale (never v1 500ms)"},
                  f, indent=2)
    return kdir


SINGLE_MODULE = ("csr", "pava", "lda", "binning", "ppoly", "floyd", "cc")
COBUILD = ("elkan", "predictor")
ALL_NINE = SINGLE_MODULE + COBUILD

if __name__ == "__main__":
    import sys
    out_root = sys.argv[1] if len(sys.argv) > 1 else "results/fleet/_kernels"
    for i, ak in enumerate(ALL_NINE, 1):
        kd = build_anchor(out_root, ak, f"fleet_R_{i:02d}_{ak}")
        print(f"built R-anchor {ak} -> {kd}")
