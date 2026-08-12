"""RUNTIME_NS harness — parent API (Step 0.2.2; roadmap §5.1, §3.2(2)).

measure() spawns ONE fresh subprocess per call (per candidate module: a candidate's
crtfastmath/MXCSR effects die with its process — §3.2(2); empirical boundaries in
data/env/GCC_SEMANTICS.md F7) running motifbo/timing/_child.py, which times K reps
with perf_counter_ns immediately around the kernel call only. Child failures raise —
never a silent empty result (D1 ethos).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

_CHILD = Path(__file__).with_name("_child.py")
_RESULT_KEYS = {"samples_ns", "reps", "warmup", "import_ns", "setup_ns", "cycles",
                "child_pid", "per_rep_regen", "mutated_arg_indices"}


def measure(module_path, kernel, setup_code, reps, warmup=5, timeout_s=300.0,
            cycles=False, mutated_arg_indices=None, per_rep_regen=None, preimport=None):
    """Time `kernel` from `module_path` in a fresh subprocess.

    setup_code: python source executed (untimed) in the child; must define `args`
    (tuple) and may define `kwargs` (dict). cycles=True additionally records per-rep
    user-space CPU cycles (10%-subsample cross-check, §5.1; requires the perf seccomp
    profile + SELinux module — see perf_cycles.py).

    mutated_arg_indices: indices of args the kernel mutates in place (PAVA y/w, dbscan
    labels, lloyd outputs). When non-empty (or per_rep_regen=True), the child REGENERATES
    the input from setup_code before each rep (v1.4, UNTIMED) so an in-place kernel does
    not time a degenerate already-converged path on reps 2..K. per_rep_regen overrides the
    default (= bool(mutated_arg_indices)). Returns the child's result dict.
    """
    with tempfile.TemporaryDirectory(prefix="runtime_ns_") as td:
        spec_path = Path(td) / "spec.json"
        out_path = Path(td) / "result.json"
        spec_path.write_text(json.dumps({
            "module_path": str(module_path), "kernel": kernel,
            "setup_code": setup_code, "reps": int(reps), "warmup": int(warmup),
            "cycles": bool(cycles), "out": str(out_path),
            "mutated_arg_indices": list(mutated_arg_indices or []),
            "per_rep_regen": per_rep_regen, "preimport": preimport,
        }))

        proc = subprocess.run(
            [sys.executable, str(_CHILD), str(spec_path)],
            capture_output=True, text=True, timeout=timeout_s,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"RUNTIME_NS child failed (rc={proc.returncode}) for "
                f"{module_path}:{kernel}\nstderr:\n{proc.stderr}")
        if not out_path.exists():
            raise RuntimeError(
                f"RUNTIME_NS child exited 0 but wrote no result for "
                f"{module_path}:{kernel} — refusing to fabricate")

        result = json.loads(out_path.read_text())

    missing = _RESULT_KEYS - result.keys()
    if missing or len(result["samples_ns"]) != int(reps):
        raise RuntimeError(f"RUNTIME_NS result malformed (missing={missing}, "
                           f"n_samples={len(result.get('samples_ns', []))}, reps={reps})")
    return result
