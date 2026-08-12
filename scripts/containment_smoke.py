"""Step 0.4.3 — containment smoke fixtures (roadmap §3.4/§3.5; runs ON THE HOST).

Drives motifbo.containment.wrapper.run_contained against the pinned image with
deliberately misbehaving candidates (OOM / timeout / segfault / abort), plus a clean
and a plain-nonzero control. Asserts each is CAUGHT and LABELED per §3.5 and that
this orchestrator process never crashes. Writes evidence under results/containment/.

  PYTHONPATH=src python3 scripts/containment_smoke.py [image]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")
from motifbo.containment.wrapper import run_contained  # noqa: E402

IMAGE = sys.argv[1] if len(sys.argv) > 1 else "localhost/motifbo-env:phase0"
PY = "python3.12"

# (name, argv, timeout_s, memory_mb, expected_label)
FIXTURES = [
    ("clean", [PY, "-c", "print('ok')"], 30, 4096, "ok"),
    ("nonzero_exit", [PY, "-c", "import sys; sys.exit(3)"], 30, 4096, "nonzero_exit"),
    ("timeout", [PY, "-c", "import time; time.sleep(60)"], 3, 4096, "timeout"),
    ("oom", [PY, "-c", "b=bytearray(6*1024**3); print(len(b))"], 120, 4096,
     "memory_cap_kill"),
    ("segfault", [PY, "-c", "import ctypes; ctypes.string_at(0)"], 30, 4096, "crash"),
    # NOTE: the full crash-signal range (SEGV/ABRT/BUS/FPE/ILL -> "crash") is covered
    # exhaustively by the pure classifier in tests/test_containment_labels.py. Only a
    # real SIGSEGV is exercised end-to-end here: in this CPython, abort() manifests as
    # rc 139 too (indistinguishable from SEGV) and os.kill(SIGABRT) is deferred to
    # rc 0, so a separate "abort" host-fixture would add confusion, not coverage.
]


def main():
    out = Path("results/containment")
    out.mkdir(parents=True, exist_ok=True)
    records, ok = [], True
    for name, argv, timeout, mem, expected in FIXTURES:
        r = run_contained(argv, image=IMAGE, timeout_s=timeout, memory_mb=mem)
        passed = r.label == expected
        ok = ok and passed
        records.append({"fixture": name, "expected": expected, "got": r.label,
                        "pass": passed, "returncode": r.returncode,
                        "timed_out": r.timed_out, "oom_killed": r.oom_killed,
                        "duration_s": round(r.duration_s, 3)})
        print(f"[{'PASS' if passed else 'FAIL'}] {name:14s} "
              f"expected={expected:16s} got={r.label:16s} "
              f"rc={r.returncode} oom={r.oom_killed} t/o={r.timed_out}")

    summary = {
        "schema": "motifbo-containment-smoke-v1", "step": "0.4.3", "image": IMAGE,
        "limits": {"network": "none", "memory_mb": 4096, "sandbox_tmpfs_mb": 2048,
                   "compile_timeout_s": 120, "run_timeout_rule": "max(10x golden, 5s)"},
        "all_pass": ok, "fixtures": records,
    }
    (out / "containment_smoke.json").write_text(json.dumps(summary, indent=1) + "\n")
    lines = [
        "# Containment smoke fixtures — Step 0.4.3 (§3.4/§3.5)",
        "",
        f"Image: {IMAGE}",
        "Limits: --network=none, --memory=4g (no swap), --tmpfs /sandbox:size=2g, "
        "wall-clock timeout (per fixture).",
        "",
        "| fixture | expected | got | pass | rc | oom | timed_out |",
        "|---|---|---|---|---|---|---|",
    ] + [f"| {r['fixture']} | {r['expected']} | {r['got']} | "
         f"{'YES' if r['pass'] else 'NO'} | {r['returncode']} | "
         f"{r['oom_killed']} | {r['timed_out']} |" for r in records] + [
        "",
        f"All fixtures caught and correctly labeled, orchestrator survived: "
        f"**{'YES' if ok else 'NO'}**.",
        "Raw: results/containment/containment_smoke.json",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(f"\nall_pass={ok}  (orchestrator survived all {len(FIXTURES)} fixtures)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
