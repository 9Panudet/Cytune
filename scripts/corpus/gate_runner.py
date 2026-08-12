"""Per-unit GATE runner (Step 1.2 campaign), run INSIDE the pinned container via
measure_wrap (so timed paths inherit --cpuset-cpus=3 + CF-1). One harness, reused
for every archetype. It NEVER fabricates: every number it prints comes from a real
kernel call or the validated runtime_ns endpoint rig; raw is written to /out.

Modes
  output-hash  <unit> <so> <scale_json>            -> {output_sha256, output_meta, input_fingerprint, recipe_sha256}
  scale-probe  <unit> <so> <scale_json> [nreps]    -> quick IN-PROCESS median_ns (scale SELECTION only, not an RQ1 number)
  endpoint     <unit> <so> <scale_json> <reps> <out>-> measure_endpoint(policy=None) raw + output hash + input fingerprint -> /out
  determinism  <unit> <so> <scale_json> <nrep>     -> nrep output hashes on a FRESH input each call (bit-identity / G5)
  recallable   <unit> <so> <scale_json>            -> output hash of call#1 vs call#2 on the SAME args tuple (is the kernel re-callable?)

The .so is loaded by file path (stem must equal PyInit_<stem>). corpus_drivers supplies
the deterministic (scale, seed) setup recipe; input_manifest supplies the pairing fingerprint.
"""
import hashlib
import importlib.util
import json
import os
import statistics
import sys
import time

import numpy as np


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _provenance(so):
    return {"image_id": os.environ.get("MOTIFBO_IMAGE_ID"),
            "git_rev": os.environ.get("MOTIFBO_GIT_REV"),
            "rig_state": os.environ.get("MOTIFBO_RIG_STATE"),
            "so_sha256": _sha256_file(so)}

sys.path.insert(0, "/probe/corpus")
import corpus_drivers as cd  # noqa: E402

from motifbo.timing.endpoint import measure_endpoint  # noqa: E402
from motifbo.timing import input_manifest as im        # noqa: E402


def _load(so_path, mod_name):
    spec = importlib.util.spec_from_file_location(mod_name, so_path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _exec_setup(setup_code):
    ns = {}
    exec(setup_code, ns)
    return tuple(ns["args"]), dict(ns.get("kwargs", {}))


def _canon(obj):
    """Canonical bytes for one return element (ndarray | scalar | tuple/list)."""
    h = hashlib.sha256()
    def feed(o):
        if isinstance(o, np.ndarray):
            a = np.ascontiguousarray(o)
            h.update(b"ND"); h.update(str(a.dtype).encode()); h.update(str(a.shape).encode())
            h.update(a.tobytes())
        elif isinstance(o, (tuple, list)):
            h.update(b"SEQ"); h.update(str(len(o)).encode())
            for x in o:
                h.update(_canon(x))
        elif isinstance(o, (int, np.integer)):
            h.update(b"I"); h.update(repr(int(o)).encode())
        elif isinstance(o, (float, np.floating)):
            h.update(b"F"); h.update(np.float64(o).tobytes())
        elif o is None:
            h.update(b"NONE")
        else:
            raise TypeError(f"un-hashable return element type {type(o)!r}")
    feed(obj)
    return h.digest()


def _output_hash(fn, args, kwargs, out_arg_indices=None):
    """Call fn; hash its return value AND any in-place-written arg buffers (out_arg_indices).

    For pure kernels (csr) the return is the output. For in-place kernels the 'output' is
    the mutated buffer(s) named in out_arg_indices — those are hashed AFTER the call.
    """
    ret = fn(*args, **kwargs)
    h = hashlib.sha256()
    h.update(_canon(ret))
    meta = {"return_type": type(ret).__name__}
    if out_arg_indices:
        for i in out_arg_indices:
            h.update(b"OUTARG"); h.update(str(i).encode()); h.update(_canon(args[i]))
        meta["out_arg_indices"] = list(out_arg_indices)
    if isinstance(ret, np.ndarray):
        meta["return_shape"] = list(ret.shape); meta["return_dtype"] = str(ret.dtype)
    elif isinstance(ret, (tuple, list)):
        meta["return_len"] = len(ret)
        meta["elem_shapes"] = [list(np.shape(x)) for x in ret]
        meta["elem_dtypes"] = [str(getattr(x, "dtype", type(x).__name__)) for x in ret]
    return h.hexdigest(), meta


def main():
    mode, unit_key, so = sys.argv[1], sys.argv[2], sys.argv[3]
    raw_scale = sys.argv[4]
    # scale may be JSON ({"n_samples":..}) or shell-friendly CSV "key=val,key=val".
    if raw_scale.lstrip().startswith("{"):
        scale = json.loads(raw_scale)
    else:
        scale = {}
        for kv in raw_scale.split(","):
            k, v = kv.split("=")
            scale[k] = float(v) if ("." in v or "e" in v.lower()) else int(v)
    u = cd.UNITS[unit_key]
    setup_code = u["setup"](scale)
    out_idx = u.get("out_arg_indices")  # in-place kernels declare which args are outputs
    mod_name = u["mod"]
    if u.get("preimport"):              # wrapper units: pre-import parent pkg (Decision C)
        __import__(u["preimport"])

    if mode == "output-hash":
        m = _load(so, mod_name); fn = getattr(m, u["kernel"])
        args, kwargs = _exec_setup(setup_code)
        oh, meta = _output_hash(fn, args, kwargs, out_idx)
        print(json.dumps({"unit": unit_key, "scale": scale, "output_sha256": oh,
                          "output_meta": meta,
                          "input_fingerprint": im.fingerprint_args(args, kwargs),
                          "recipe_sha256": im.recipe_sha256(setup_code)}))

    elif mode == "scale-probe":
        nreps = int(sys.argv[5]) if len(sys.argv) > 5 else 7
        mutated = u.get("mutated_arg_indices") or []
        regen = bool(mutated) and not u.get("recallable", False)   # v1.4: fresh input per call
        m = _load(so, mod_name); fn = getattr(m, u["kernel"])
        args, kwargs = _exec_setup(setup_code)
        for _ in range(3):
            if regen: args, kwargs = _exec_setup(setup_code)
            fn(*args, **kwargs)             # warmup (scale selection only)
        samples = []
        for _ in range(nreps):
            if regen: args, kwargs = _exec_setup(setup_code)   # UNTIMED fresh input
            t0 = time.perf_counter_ns(); fn(*args, **kwargs); samples.append(time.perf_counter_ns() - t0)
        print(json.dumps({"unit": unit_key, "scale": scale, "nreps": nreps,
                          "median_ns": statistics.median(samples),
                          "min_ns": min(samples), "max_ns": max(samples),
                          "note": "IN-PROCESS scale-selection timing, NOT an RQ1 endpoint"}))

    elif mode == "endpoint":
        reps = int(sys.argv[5]); out = sys.argv[6]
        nsub = int(sys.argv[7]) if len(sys.argv) > 7 else 3   # >3 = characterization sweep
        mutated = u.get("mutated_arg_indices") or []
        # v1.4: regen per-rep ONLY for in-place kernels that are NOT re-callable (PAVA, dbscan).
        # Re-callable mutators (lloyd: re-zeros outputs, centers_old read-only) keep args-once —
        # regen would rebuild the input each rep for no correctness gain (pure cost).
        per_rep_regen = bool(mutated) and not u.get("recallable", False)
        res = measure_endpoint(module_path=so, kernel=u["kernel"], setup_code=setup_code,
                               reps=reps, n_subproc=nsub, policy=None,
                               mutated_arg_indices=mutated, per_rep_regen=per_rep_regen,
                               preimport=u.get("preimport"))
        m = _load(so, mod_name); fn = getattr(m, u["kernel"])
        args, kwargs = _exec_setup(setup_code)
        oh, meta = _output_hash(fn, args, kwargs, out_idx)
        res["unit"] = unit_key; res["scale"] = scale; res["so_path"] = so
        res["golden_output_sha256"] = oh; res["output_meta"] = meta
        res["input_fingerprint"] = im.fingerprint_args(args, kwargs)
        res["recipe_sha256"] = im.recipe_sha256(setup_code)
        res["provenance"] = _provenance(so)
        with open(out, "w") as fh:
            json.dump(res, fh, indent=2)
        print(json.dumps({"endpoint_ns": res["endpoint_ns"],
                          "subproc_medians_ns": res["subproc_medians_ns"],
                          "golden_output_sha256": oh, "wrote": out}))

    elif mode == "determinism":
        nrep = int(sys.argv[5])
        hashes = []
        for _ in range(nrep):
            m = _load(so, mod_name); fn = getattr(m, u["kernel"])  # fresh module each rep
            args, kwargs = _exec_setup(setup_code)                  # FRESH input each rep
            oh, _ = _output_hash(fn, args, kwargs, out_idx)
            hashes.append(oh)
        print(json.dumps({"unit": unit_key, "scale": scale, "nrep": nrep,
                          "hashes": hashes, "all_identical": len(set(hashes)) == 1}))

    elif mode == "recallable":
        # Re-callability needs BOTH output-identity AND timing: an in-place kernel can return
        # identical output on call#2 because it does NOTHING (dbscan: labels already filled),
        # which output-identity alone reads as "re-callable". So time 3 successive calls on the
        # SAME args: degenerate iff call#2/#3 wall << call#1 (reps 2..K would time a no-op).
        m = _load(so, mod_name); fn = getattr(m, u["kernel"])
        args, kwargs = _exec_setup(setup_code)
        hashes, times = [], []
        for _ in range(3):
            t0 = time.perf_counter_ns()
            ret = fn(*args, **kwargs)
            times.append(time.perf_counter_ns() - t0)
            h = hashlib.sha256(); h.update(_canon(ret))
            if out_idx:
                for i in out_idx:
                    h.update(_canon(args[i]))
            hashes.append(h.hexdigest())
        ratio = times[1] / times[0] if times[0] else 0.0
        degenerate = (hashes[0] != hashes[1]) or (ratio < 0.5)   # output drift OR <half the work
        print(json.dumps({"unit": unit_key, "call_times_ns": times,
                          "call2_over_call1": ratio, "hashes": hashes,
                          "outputs_identical": len(set(hashes)) == 1,
                          "degenerate_on_recall": degenerate,
                          "recallable_for_timed_endpoint": not degenerate,
                          "note": "degenerate iff output drifts OR call2 wall < 0.5*call1 (no-op)"}))
    else:
        raise SystemExit(f"unknown mode {mode!r}")


if __name__ == "__main__":
    main()
