"""Step 0.4.2 — known-good build runs the full validation input set CLEAN (§3.3).

Builds the two reference kernels under the KNOWN-GOOD directive set + the 0.4.1
ASan+UBSan profile, runs every validation case (golden + edge + property, §3.3) in a
fresh subprocess under the gate runtime env, and asserts ZERO sanitizer reports.
The committed result under /results/sanitize/known_good/ is Phase-0 exit evidence.

Runs INSIDE the pinned container, e.g.:
  podman run --rm -v ./src:/src:ro,Z -v ./scripts:/scripts:ro,Z \
    -v ./results:/results:Z -e PYTHONPATH=/src -e MOTIFBO_IMAGE_ID=$ID \
    -e MOTIFBO_GIT_REV=$REV localhost/motifbo-env:phase0 \
    python /scripts/run_known_good_sanitize.py

Known-good = the most-checks-OFF SAFE class (§0.5.2): boundscheck/wraparound/
initializedcheck/nonecheck off, cdivision on, fast_math off. The sanitizer build
pins -O1/contract=off: neither -O nor contract is in the §3.3 safety-class key, so
the memory-safety verdict is independent of them.
"""
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

sys.path.insert(0, "/src")
from motifbo.build.profiles import sanitizer_argv, sanitizer_runtime_env  # noqa: E402
from motifbo.sanitize import validation_inputs as vi  # noqa: E402

KERNEL_SRC = {"csr": "csr_scale", "pava": "pava"}
KNOWN_GOOD_DIRECTIVES = ["boundscheck=False", "wraparound=False",
                         "initializedcheck=False", "nonecheck=False",
                         "cdivision=True"]
SAN_TOKENS = ("AddressSanitizer", "LeakSanitizer", "runtime error",
              "buffer-overflow", "use-after", "stack-overflow",
              "SUMMARY: AddressSanitizer", "SUMMARY: UndefinedBehavior")
OUT = Path("/results/sanitize/known_good")


def build(kind, workdir, py_include):
    stem = KERNEL_SRC[kind]
    pyx = workdir / f"{stem}.pyx"
    shutil.copy(f"/src/motifbo/refkernels/{stem}.pyx", pyx)
    xflags = []
    for d in KNOWN_GOOD_DIRECTIVES:
        xflags += ["-X", d]
    subprocess.run(["cython", "-3", *xflags, str(pyx)], check=True)
    so = workdir / f"{stem}.so"
    subprocess.run(sanitizer_argv(ffp_contract="off", c_path=str(workdir / f"{stem}.c"),
                                  so_path=str(so), py_include=py_include), check=True)
    return so


def run_case(kind, so, idx, env):
    p = subprocess.run([sys.executable, "/src/motifbo/sanitize/_san_child.py",
                        kind, str(so), str(idx)],
                       capture_output=True, text=True, timeout=300, env=env)
    report = (p.returncode != 0) or any(t in p.stderr for t in SAN_TOKENS)
    return {
        "kind": kind, "idx": idx, "name": vi.CASES[kind][idx]["name"],
        "returncode": p.returncode, "clean": not report,
        "stderr_excerpt": "" if not report else p.stderr[-1200:],
    }


def main():
    py_include = sysconfig.get_paths()["include"]
    asan_lib = subprocess.run(["gcc", "-print-file-name=libasan.so"],
                              capture_output=True, text=True, check=True).stdout.strip()
    base_env = dict(os.environ)
    base_env["PYTHONPATH"] = "/src"
    base_env["PYTHONDONTWRITEBYTECODE"] = "1"
    san_env = {**base_env, **sanitizer_runtime_env(asan_lib)}

    workdir = Path(tempfile.mkdtemp())
    results = []
    for kind in ("csr", "pava"):
        so = build(kind, workdir, py_include)
        for idx in range(len(vi.CASES[kind])):
            results.append(run_case(kind, so, idx, san_env))

    reports = [r for r in results if not r["clean"]]
    summary = {
        "schema": "motifbo-knowngood-sanitize-v1",
        "step": "0.4.2",
        "image_id": os.environ.get("MOTIFBO_IMAGE_ID", "unknown"),
        "git_rev": os.environ.get("MOTIFBO_GIT_REV", "unknown"),
        "directives": KNOWN_GOOD_DIRECTIVES,
        "sanitizer_build": "-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -ffp-contract=off",
        "runtime_env": {k: san_env[k] for k in
                        ("ASAN_OPTIONS", "UBSAN_OPTIONS", "LD_PRELOAD")},
        "asan_lib": asan_lib,
        "total_cases": len(results),
        "n_csr": len(vi.CSR_CASES), "n_pava": len(vi.PAVA_CASES),
        "reports": len(reports),
        "clean": len(reports) == 0,
        "cases": results,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "known_good_sanitize.json").write_text(json.dumps(summary, indent=1) + "\n")

    lines = [
        "# Known-good ASan+UBSan clean run — Step 0.4.2 (§3.3, Phase-0 exit evidence)",
        "",
        f"Directives (known-good class): {' '.join(KNOWN_GOOD_DIRECTIVES)}",
        f"Sanitizer build: {summary['sanitizer_build']}",
        f"Runtime: ASAN_OPTIONS={san_env['ASAN_OPTIONS']}  "
        f"UBSAN_OPTIONS={san_env['UBSAN_OPTIONS']}",
        f"Image: {summary['image_id']}  git: {summary['git_rev']}",
        "",
        f"Cases run: {summary['total_cases']} "
        f"(csr {summary['n_csr']} + pava {summary['n_pava']}; "
        f"golden + edge + fixed-seed property corpus, §3.3).",
        f"Sanitizer reports: **{summary['reports']}** -> "
        f"{'CLEAN (zero reports)' if summary['clean'] else 'NOT CLEAN'}.",
        "",
        "Raw per-case verdicts: results/sanitize/known_good/known_good_sanitize.json",
    ]
    if reports:
        lines += ["", "## Reports"] + [
            f"- {r['kind']}[{r['idx']}] {r['name']}: rc={r['returncode']}\n```\n"
            f"{r['stderr_excerpt']}\n```" for r in reports]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    shutil.rmtree(workdir, ignore_errors=True)
    sys.exit(1 if reports else 0)


if __name__ == "__main__":
    main()
