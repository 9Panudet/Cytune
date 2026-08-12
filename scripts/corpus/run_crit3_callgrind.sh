#!/usr/bin/env bash
# Step-1.3 A1 — callgrind criterion-3 share at -O3 -march=native, in the :phase1-TOOLS image
# (valgrind present). callgrind counts INSTRUCTIONS (Ir), deterministic + contention-independent,
# so CF-1 quiescing is not required for its validity; still run one container at a time to avoid
# polluting any concurrent wall-clock timing. Raw -> results/characterization/crit3.
#
# Usage: run_crit3_callgrind.sh [N=5] [unit_key ...]   (default = the 9 survivors)
set -uo pipefail
cd "$(dirname "$0")/../.."
N="${1:-5}"; shift || true
IMG=localhost/motifbo-tools:phase1
OUT=results/characterization/crit3
mkdir -p "$OUT"

declare -A CLOSURE=(
  [csr_mean_variance_axis0]=data/corpus/sklearn/sparsefuncs_fast/closure
  [_dirichlet_expectation_2d]=data/corpus/sklearn/_online_lda_fast/closure
  [_inplace_contiguous_isotonic_regression]=data/corpus/sklearn/_isotonic/closure
  [_map_to_bins]=data/corpus/sklearn/_binning/closure
  [ppoly_evaluate]=data/corpus/scipy/_ppoly/closure
  [floyd_warshall]=data/corpus/scipy/_shortest_path/closure
  [connected_components]=data/corpus/scipy/_traversal/closure
  [elkan_iter_chunked_dense]=data/corpus/sklearn/_k_means_elkan/closure
  [_predict_from_raw_data]=data/corpus/sklearn/_predictor/closure
  [lloyd_iter_chunked_dense]=data/corpus/sklearn/_k_means_lloyd/closure
  [dbscan_inner]=data/corpus/sklearn/_dbscan_inner/closure
)
ORDER=("$@")
[ "${#ORDER[@]}" -eq 0 ] && ORDER=(csr_mean_variance_axis0 _dirichlet_expectation_2d \
  _inplace_contiguous_isotonic_regression _map_to_bins ppoly_evaluate floyd_warshall \
  connected_components elkan_iter_chunked_dense _predict_from_raw_data)

for u in "${ORDER[@]}"; do
  cl="${CLOSURE[$u]:-}"
  if [ -z "$cl" ] || [ ! -d "$cl" ]; then echo "SKIP $u (no closure: $cl)"; continue; fi
  echo "================ crit-3 callgrind: $u  (N=$N, -O3 -march=native) ================"
  podman run --rm \
    -v ./scripts:/probe:ro,Z \
    -v ./src:/src:ro,Z \
    -v "./$cl:/unit/closure:ro,Z" \
    -v "./$OUT:/out:Z" \
    -e UNIT_CLOSURE=/unit/closure \
    "$IMG" \
    python /probe/corpus/crit3_callgrind_run.py "$u" "$N"
  echo "---- $u crit3 done (rc=$?) ----"
done
echo "ALL crit-3 callgrind units processed -> $OUT"
