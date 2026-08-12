"""Step 0.P / close-out G1 — known-good build runs a fixed-seed HYPOTHESIS property
corpus CLEAN under ASan+UBSan (§3.3).

`hypothesis` was pinned at re-pin 0.4.2b, after the 0.4.2 known-good run used a numpy
stand-in corpus. §3.3 names Hypothesis property cases in the validation input set, so
the byte-identical-toolchain carry-forward (which only covers re-running the SAME
inputs) does not by itself green Phase-0 exit item 3. This pass closes that gap:
a deterministic, committed Hypothesis corpus is run through the SAME known-good
sanitizer build + fresh-subprocess child as 0.4.2; ZERO sanitizer reports required.

Reuses the PROVEN build/tokens/directives from run_known_good_sanitize.py verbatim —
only the case source changes (Hypothesis corpus vs validation_inputs.CASES). Output
(gate evidence) -> /results/raw/hypothesis_sanitize/.

Runs INSIDE the pinned container:
  podman run --rm -v ./src:/src:ro,Z -v ./scripts:/scripts:ro,Z -v ./results:/results:Z \
    -e PYTHONPATH=/src -e MOTIFBO_IMAGE_ID=$ID -e MOTIFBO_GIT_REV=$REV \
    localhost/motifbo-env:phase0 python /scripts/run_hypothesis_sanitize.py
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
sys.path.insert(0, "/scripts")
import run_known_good_sanitize as kg  # noqa: E402  reuse PROVEN build/tokens/directives
from motifbo.build.profiles import sanitizer_runtime_env  # noqa: E402
from motifbo.sanitize import hypothesis_inputs as hi  # noqa: E402

N_PER_KERNEL = 40
OUT = Path("/results/raw/hypothesis_sanitize")


def run_case(kind, so, corpus_path, idx, env):
    p = subprocess.run([sys.executable, "/src/motifbo/sanitize/_hyp_san_child.py",
                        kind, str(so), str(corpus_path), str(idx)],
                       capture_output=True, text=True, timeout=300, env=env)
    report = (p.returncode != 0) or any(t in p.stderr for t in kg.SAN_TOKENS)
    return {"kind": kind, "idx": idx, "returncode": p.returncode,
            "clean": not report,
            "stderr_excerpt": "" if not report else p.stderr[-1200:]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    py_include = sysconfig.get_paths()["include"]
    asan_lib = subprocess.run(["gcc", "-print-file-name=libasan.so"],
                              capture_output=True, text=True, check=True).stdout.strip()
    base_env = dict(os.environ)
    base_env["PYTHONPATH"] = "/src"
    base_env["PYTHONDONTWRITEBYTECODE"] = "1"
    san_env = {**base_env, **sanitizer_runtime_env(asan_lib)}

    import hypothesis
    workdir = Path(tempfile.mkdtemp())
    results, counts = [], {}
    for kind in ("csr", "pava"):
        corpus = hi.generate_corpus(kind, N_PER_KERNEL)
        counts[kind] = len(corpus)
        corpus_path = OUT / f"corpus_{kind}.json"
        corpus_path.write_text(json.dumps(corpus, indent=1) + "\n")
        so = kg.build(kind, workdir, py_include)            # known-good + ASan/UBSan
        for idx in range(len(corpus)):
            results.append(run_case(kind, so, corpus_path, idx, san_env))

    reports = [r for r in results if not r["clean"]]
    summary = {
        "schema": "motifbo-hypothesis-sanitize-v1",
        "step": "0.P/G1",
        "image_id": os.environ.get("MOTIFBO_IMAGE_ID", "unknown"),
        "git_rev": os.environ.get("MOTIFBO_GIT_REV", "unknown"),
        "hypothesis_version": hypothesis.__version__,
        "directives": kg.KNOWN_GOOD_DIRECTIVES,
        "sanitizer_build": "-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -ffp-contract=off",
        "generation": "derandomize=True, database=None, phases=[generate]; committed corpus_{csr,pava}.json",
        "n_per_kernel": N_PER_KERNEL,
        "counts": counts,
        "total_cases": len(results),
        "reports": len(reports),
        "clean": len(reports) == 0,
        "cases": results,
    }
    (OUT / "hypothesis_sanitize.json").write_text(json.dumps(summary, indent=1) + "\n")

    lines = [
        "# Known-good ASan+UBSan over the HYPOTHESIS property corpus — Step 0.P / G1 (§3.3)",
        "",
        f"Closes the Phase-0 exit item-3 input-set gap: hypothesis=={hypothesis.__version__} "
        "was pinned at 0.4.2b after the 0.4.2 numpy-corpus run; §3.3 names Hypothesis "
        "property cases in the validation input set.",
        "",
        f"Directives (known-good class): {' '.join(kg.KNOWN_GOOD_DIRECTIVES)}",
        f"Sanitizer build: {summary['sanitizer_build']}",
        f"Generation: {summary['generation']}",
        f"Image: {summary['image_id']}  git: {summary['git_rev']}",
        "",
        f"Cases run: {summary['total_cases']} "
        f"(csr {counts.get('csr', 0)} + pava {counts.get('pava', 0)}; "
        "deterministic committed Hypothesis corpus, §3.3).",
        f"Sanitizer reports: **{summary['reports']}** -> "
        f"{'CLEAN (zero reports)' if summary['clean'] else 'NOT CLEAN'}.",
        "",
        "Committed corpus: results/raw/hypothesis_sanitize/corpus_{csr,pava}.json",
        "Raw per-case verdicts: results/raw/hypothesis_sanitize/hypothesis_sanitize.json",
    ]
    if reports:
        lines += ["", "## Reports"] + [
            f"- {r['kind']}[{r['idx']}]: rc={r['returncode']}\n```\n"
            f"{r['stderr_excerpt']}\n```" for r in reports]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    shutil.rmtree(workdir, ignore_errors=True)
    sys.exit(1 if reports else 0)


if __name__ == "__main__":
    main()
