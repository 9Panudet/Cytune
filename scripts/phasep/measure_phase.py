"""MEASURE-phase entrypoint (roadmap §4.4 phase 2/3) — runs INSIDE the measure_wrap container.

Reads the pre-built .so (build_manifest.jsonl); does calibrate → golden+determinism gate →
screen all → suspicious §7 → endpoint §4 → classify. NO compilation here (CF-1). Each config is a
fresh subprocess (measure_child) inside this one gated container. Resumable (table.jsonl append-only).

CLI: measure_phase.py <kernel_dir> <out_dir> [configs=all] [--target-ms 65]
     [--no-calibrate] [--no-endpoint] [--no-suspicious]
"""
import argparse
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kernel_dir"); ap.add_argument("out_dir")
    ap.add_argument("configs", nargs="?", default="all")
    ap.add_argument("--target-ms", type=float, default=65.0)
    ap.add_argument("--no-calibrate", action="store_true")
    ap.add_argument("--no-endpoint", action="store_true")
    ap.add_argument("--no-suspicious", action="store_true")
    a = ap.parse_args()
    ids = campaign.config_set(a.configs)

    if not a.no_calibrate:
        print("calibrate:", campaign.calibrate(a.kernel_dir, a.out_dir, a.target_ms))
    orc = campaign.golden_and_oracle(a.kernel_dir, a.out_dir)
    print(f"oracle: class={orc['output_class']} deterministic={orc['deterministic']} "
          f"tol={orc['tolerance']} shape={orc['golden_shape']}")
    tp, nf = campaign.measure_all(a.kernel_dir, a.out_dir, ids)
    print(f"screen: {nf}/{len(ids)} feasible -> {tp}")
    if not a.no_suspicious:
        ev = campaign.suspicious_remeasure(a.kernel_dir, a.out_dir)
        print(f"suspicious: {len(ev)} events")
    if not a.no_endpoint:
        ep = campaign.endpoint_tier(a.kernel_dir, a.out_dir)
        print(f"endpoint: top-decile n={ep.get('top_decile_n')} tau_b={ep.get('kendall_tau_b')} "
              f"agreement_ok={ep.get('agreement_binary_ok')}")
    rec = campaign.finalize(a.kernel_dir, a.out_dir)
    print(f"class_record: measured={rec['classification'].get('measured_class')} n_feasible={rec['n_feasible']}")


if __name__ == "__main__":
    main()
