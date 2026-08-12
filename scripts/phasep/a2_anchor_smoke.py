"""R-anchor adapter smoke (task #43 stage A) — builds only + untimed determinism; NO timing rows.

For each SINGLE-MODULE anchor (csr, pava, lda, binning, ppoly, floyd, cc): emit via build_anchor,
closure-build config 288, then run measure_child TWICE in fresh subprocesses (K_min=K_max=1,
warmup=1) and require bit-identical output_sha256 across the two runs (the determinism precondition
the campaign's 5-rep golden gate will enforce for-record at fleet time). csr/pava re-validate the
NEW uniform driver template (kwargs-aware, single knob line).

Run inside the plain container with the repo mounted AT ITS HOST PATH (so the driver's host_corpus
sys.path fallback resolves):
  podman run --rm --network=none --security-opt label=disable \
    -v <repo>:<repo> -v <scratch>:/work localhost/motifbo-env:phase1 \
    python3 <repo>/scripts/phasep/a2_anchor_smoke.py /work
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build          # noqa: E402
import r_anchor       # noqa: E402
import theta          # noqa: E402


def child_once(kdir, so_path, module):
    cmd = [sys.executable, os.path.join(HERE, "measure_child.py"), kdir, so_path,
           "1", "1", "1", "0.5", "12345", "12345", "--module", module]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       env={**os.environ, "OMP_NUM_THREADS": "1"})
    if r.returncode != 0:
        return None, (r.stdout + r.stderr)[-300:]
    return json.loads(r.stdout.strip().splitlines()[-1]), None


def main():
    work = sys.argv[1]
    kroot = os.path.join(work, "_anchor_smoke")
    n_fail = 0
    for ak in r_anchor.ALL_NINE:
        kid = f"smoke_R_{ak}"
        kdir = r_anchor.build_anchor(kroot, ak, kid, repo_root=os.path.dirname(os.path.dirname(HERE)))
        cache = os.path.join(work, "_anchor_ccache", kid)
        sodir = os.path.join(work, "_anchor_so", kid)
        res = build.build_config(kdir, theta.config_of(theta.REFERENCE_ID), cache, sodir)
        if not res.get("ok"):
            n_fail += 1
            print(f"FAIL {ak}: build cfg288: {str(res.get('log') or res.get('reason'))[:200]}")
            continue
        h = []
        for run in (1, 2):
            m, err = child_once(kdir, res["so_path"], res["module"])
            if m is None:
                n_fail += 1
                print(f"FAIL {ak}: child run {run}: {err}")
                break
            h.append(m["output_sha256"])
        else:
            if h[0] == h[1]:
                print(f"OK   {ak}: build+2×child, deterministic sha={h[0][:12]}…")
            else:
                n_fail += 1
                print(f"FAIL {ak}: NON-DETERMINISTIC across fresh children ({h[0][:10]} != {h[1][:10]})")
    print(f"\nANCHOR SMOKE: {'PASS' if n_fail == 0 else f'{n_fail} FAILURES'}")
    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
