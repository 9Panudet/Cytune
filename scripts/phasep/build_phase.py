"""BUILD-phase entrypoint (roadmap §4.4 phase 1) — runs in a PLAIN build container (compile cores).

Compiles every config's .so and writes build_manifest.jsonl. NO measurement here (CF-1). Resumable.
CLI: build_phase.py <kernel_dir> <out_dir> [configs=all]
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign  # noqa: E402


def main():
    kernel_dir, out_dir = sys.argv[1], sys.argv[2]
    configs = sys.argv[3] if len(sys.argv) > 3 else "all"
    os.makedirs(out_dir, exist_ok=True)
    ids = campaign.config_set(configs)
    mpath, n_ok = campaign.build_all(kernel_dir, out_dir, ids)
    print(f"build_phase: {n_ok}/{len(ids)} configs built (cythonize-fail cached as feasibility-0) -> {mpath}")


if __name__ == "__main__":
    main()
