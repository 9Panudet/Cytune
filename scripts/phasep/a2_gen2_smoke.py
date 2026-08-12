"""Generator v2 compile+RUN smoke (pre-fleet gate; builds + ONE untimed child call each — the
D8/D9 lesson: a compile-only smoke misses every call-time contract (dtype ABI, buffer bounds).

Emits one instance of EVERY template (all regimes), cythonize+gcc each at the reference config
(288) and at a strict bc-off/-O3/native config (1506), then RUNS one measure_child call at cfg 288
(K=1, warmup=1, no oracle — functional only, zero timing rows recorded). A template that fails
either build OR the call is a generator defect to fix BEFORE the fleet.

Run inside the plain container:
  podman run --rm --network=none --security-opt label=disable \
    -v <repo>:/repo:ro -v <scratch>:/work localhost/motifbo-env:phase1 \
    python3 /repo/scripts/phasep/a2_gen2_smoke.py /work
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build          # noqa: E402
import generate_v2 as g2   # noqa: E402
import theta          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIGS = [theta.REFERENCE_ID, 1506]   # reference + strict bc-off/-O3/native


def child_once(kdir, so_path):
    """One functional call via measure_child (K=1, warmup=1, no oracle). Returns (ok, err)."""
    r = subprocess.run([sys.executable, os.path.join(HERE, "measure_child.py"), kdir, so_path,
                        "1", "1", "1", "0.5", "12345", "12345"],
                       capture_output=True, text=True,
                       env={**os.environ, "OMP_NUM_THREADS": "1"})
    if r.returncode != 0:
        return False, (r.stdout + r.stderr)[-200:]
    return True, None


def main():
    work = sys.argv[1]
    # optional argv[2]: comma-list of registry keys (A-3: smoke the W2 regimes alone — the
    # wave-1 templates already passed this gate pre-fleet and are untouched)
    only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
    kroot = os.path.join(work, "_gen2_smoke")
    n_fail = 0
    for regime, templates in g2.REGISTRY.items():
        if only is not None and regime not in only:
            continue
        for (name, _pyx, _drv, pspace, feas_ok) in templates:
            variants = [None] + ([feas_ok[0]] if feas_ok else [])
            for trap in variants:
                kid = f"smoke_{regime}_{name}" + (f"_{trap}" if trap else "")
                kdir = g2.emit_kernel(kroot, regime, kid, name, pspace[0], trap, 0)
                cache = os.path.join(work, "_gen2_ccache", kid)
                sodir = os.path.join(work, "_gen2_so", kid)
                ref_so = None
                for cid in CONFIGS:
                    r = build.build_config(kdir, theta.config_of(cid), cache, sodir)
                    ok = r.get("ok")
                    if cid == theta.REFERENCE_ID and ok:
                        ref_so = r["so_path"]
                    tag = "OK " if ok else "FAIL"
                    if not ok:
                        n_fail += 1
                        print(f"{tag} {kid} cfg={cid}: {str(r.get('reason'))[:160]}")
                    else:
                        print(f"{tag} {kid} cfg={cid}")
                if ref_so:                       # D8/D9: exercise the CALL contract, not just gcc
                    ok, err = child_once(kdir, ref_so)
                    if not ok:
                        n_fail += 1
                        print(f"FAIL {kid} RUN: {err}")
                    else:
                        print(f"OK  {kid} RUN")
    print(f"\nGEN2 SMOKE: {'PASS' if n_fail == 0 else f'{n_fail} FAILURES'}")
    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
