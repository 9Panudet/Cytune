"""Step-1.3 A1 — callgrind criterion-3 kernel-share at -O3 -march=native (construction-subtracted).

Two FULL-collection callgrind runs at the fastest config (worst case for share):
  A: build args, call kernel 0x   (construction-only baseline)
  B: build args, call kernel Nx   (construction + N kernel calls)
Per-object Ir delta (B-A) isolates the kernel's own instruction cost on each object (.so / libopenblas /
libpython / libm); the crit-3 share = unit-.so Ir / total per-call Ir (see crit3_callgrind_delta.py). This
is robust to fused-cython dispatch (which defeats --toggle-collect) and to memory-bound kernels. Dispatches
bare (crit3_callgrind.py) vs package-import multi-module (crit3_callgrind_pkg.py). Raw committed:
/out/<unit>__crit3.json + the two annotate texts + the two callgrind dumps.

Usage (in :phase1-tools): crit3_callgrind_run.py <unit_key> [N=2]
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, "/probe/corpus")
sys.path.insert(0, "/src")
import corpus_drivers as cd  # noqa: E402
from delta_probe_pkg import build_pkg  # noqa: E402

FAST = {"label": "cg_fast", "opt_flags": "-O3 -march=native", "ffp": "off",
        "cydirs": ("-X cdivision=True -X wraparound=False -X initializedcheck=False "
                   "-X nonecheck=False -X boundscheck=False")}


THREAD_ENV = {"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
# pin all thread pools: the openblas blas_thread_server SPINS background threads whose Ir varies
# run-to-run, leaving a nondeterministic BLAS residual in the (B-A) delta that is not kernel work.


def callgrind(driver, env, out):
    subprocess.run(["valgrind", "--tool=callgrind", f"--callgrind-out-file={out}"] + driver,
                   env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ann = out + ".annotate.txt"
    with open(ann, "w") as fh:
        fh.write(subprocess.run(["callgrind_annotate", "--threshold=100", "--inclusive=no", out],
                                capture_output=True, text=True).stdout)
    return ann


def main():
    unit_key = sys.argv[1]
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    u = cd.UNITS[unit_key]
    is_pkg = bool(u.get("cobuild"))
    os.makedirs("/out", exist_ok=True)

    if is_pkg:
        work, ok, err = build_pkg(u, FAST)
        if not ok:
            print("BUILD FAIL", err); sys.exit(3)
        drv = lambda n: ["python", "/probe/corpus/crit3_callgrind_pkg.py", unit_key, work, str(n)]  # noqa: E731
        so_names = [m + "." for _, m in u["cobuild"]]   # match _k_means_common.so etc.
        env = dict(os.environ, PYTHONPATH=f"/src:{work}", **THREAD_ENV)
    else:
        so = f"/tmp/cg/{u['mod']}.so"; os.makedirs("/tmp/cg", exist_ok=True)
        r = subprocess.run(["bash", "/probe/corpus/build_unit.sh", u["pyx"], u["mod"], so,
                            FAST["opt_flags"], FAST["ffp"], u.get("lang", "c"), FAST["cydirs"]],
                           capture_output=True, text=True)
        if not os.path.exists(so):
            print("BUILD FAIL", (r.stdout + r.stderr)[-400:]); sys.exit(3)
        drv = lambda n: ["python", "/probe/corpus/crit3_callgrind.py", unit_key, so, str(n)]  # noqa: E731
        so_names = [u["mod"] + "."]
        env = dict(os.environ, PYTHONPATH="/src", **THREAD_ENV)

    annA = callgrind(drv(0), env, f"/out/cgA_{unit_key}.out")
    annB = callgrind(drv(N), env, f"/out/cgB_{unit_key}.out")
    res = subprocess.run(["python", "/probe/corpus/crit3_callgrind_delta.py", unit_key,
                          ",".join(so_names), str(N), annA, annB], capture_output=True, text=True)
    sys.stdout.write(res.stdout); sys.stderr.write(res.stderr)
    for line in res.stdout.splitlines():
        if line.startswith("JSON "):
            d = json.loads(line[5:])
            d.update({"scale": dict(u.get("crit3_scale") or u.get("delta_scale") or u["trial"]),
                      "kernel": u["kernel"], "module": u["module"],
                      "build_path": "pkg cobuild" if is_pkg else "bare"})
            with open(f"/out/{unit_key}__crit3.json", "w") as fh:
                json.dump(d, fh, indent=2)


if __name__ == "__main__":
    main()
