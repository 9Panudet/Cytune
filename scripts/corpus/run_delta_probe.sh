#!/usr/bin/env bash
# Host-side runner for the Step-1.3 16-config Δ-probe (PREREG_DELTA_PROBE.md).
# Loops the crit-3 SURVIVOR units (one per surviving module) SERIALLY through measure_wrap
# (CF-1: ONE container at a time, isolated core 3, verified rig). Each unit's vendored closure
# is mounted at /unit/closure; delta_probe.py builds the 16 configs + times each in fresh
# subprocesses and writes results/characterization/delta_probe/<unit>.json.
#
# Usage: run_delta_probe.sh [nreps=25] [unit_key ...]   (no unit_key => all 5 driven survivors)
set -uo pipefail
cd "$(dirname "$0")/../.."
NREPS="${1:-25}"; shift || true
IMG=localhost/motifbo-env:phase1
OUT=results/characterization/delta_probe
mkdir -p "$OUT"

# unit_key -> vendored closure dir (one driven survivor per surviving module)
declare -A CLOSURE=(
  [csr_mean_variance_axis0]=data/corpus/sklearn/sparsefuncs_fast/closure
  [_inplace_contiguous_isotonic_regression]=data/corpus/sklearn/_isotonic/closure
  [_dirichlet_expectation_2d]=data/corpus/sklearn/_online_lda_fast/closure
  [_map_to_bins]=data/corpus/sklearn/_binning/closure
  [ppoly_evaluate]=data/corpus/scipy/_ppoly/closure
  [floyd_warshall]=data/corpus/scipy/_shortest_path/closure
  [connected_components]=data/corpus/scipy/_traversal/closure
)
ORDER=(csr_mean_variance_axis0 _inplace_contiguous_isotonic_regression _dirichlet_expectation_2d _map_to_bins ppoly_evaluate)
[ "$#" -gt 0 ] && ORDER=("$@")

for u in "${ORDER[@]}"; do
  cl="${CLOSURE[$u]:-}"
  if [ -z "$cl" ] || [ ! -d "$cl" ]; then echo "SKIP $u (no closure: $cl)"; continue; fi
  echo "================ Δ-probe: $u  (closure=$cl) ================"
  ./scripts/measure_wrap.sh \
    -v ./scripts:/probe:ro,Z \
    -v ./src:/src:ro,Z \
    -v "./$cl:/unit/closure:ro,Z" \
    -v "./$OUT:/out:Z" \
    -e PYTHONPATH=/src \
    "$IMG" \
    python /probe/corpus/delta_probe.py "$u" "$NREPS"
  echo "---- $u done (rc=$?) ----"
done
echo "ALL Δ-probe units processed -> $OUT"
