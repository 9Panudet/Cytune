#!/usr/bin/env bash
# Step-1.3 GAP-2: re-measure BORDERLINE/median-deciding survivors on the v1.4 ENDPOINT rig
# (median-of-nsub-subprocess), CF-1 serial. Dispatches bare units (build_unit.sh + gate_runner
# endpoint -> delta_probe_endpoint.py) vs PACKAGE-import multi-module units (delta_probe_pkg.py
# with nsub>1). Closure mounted at /unit/closure as usual.
#
# Usage: run_delta_probe_endpoint.sh [reps=15] [nsub=3] [unit_key ...]
set -uo pipefail
cd "$(dirname "$0")/../.."
REPS="${1:-15}"; NSUB="${2:-3}"; shift 2 || true
IMG=localhost/motifbo-env:phase1
OUT=results/characterization/delta_probe
mkdir -p "$OUT"

declare -A CLOSURE=(
  [csr_mean_variance_axis0]=data/corpus/sklearn/sparsefuncs_fast/closure
  [_map_to_bins]=data/corpus/sklearn/_binning/closure
  [floyd_warshall]=data/corpus/scipy/_shortest_path/closure
  [_predict_from_raw_data]=data/corpus/sklearn/_predictor/closure
  [elkan_iter_chunked_dense]=data/corpus/sklearn/_k_means_elkan/closure
  [_dirichlet_expectation_2d]=data/corpus/sklearn/_online_lda_fast/closure
  [connected_components]=data/corpus/scipy/_traversal/closure
  [_inplace_contiguous_isotonic_regression]=data/corpus/sklearn/_isotonic/closure
  [ppoly_evaluate]=data/corpus/scipy/_ppoly/closure
)
# pkg (multi-module package-import) units use delta_probe_pkg.py; others the bare endpoint path
declare -A PKG=( [_predict_from_raw_data]=1 [elkan_iter_chunked_dense]=1 )

ORDER=("$@")
[ "${#ORDER[@]}" -eq 0 ] && ORDER=(_map_to_bins floyd_warshall _predict_from_raw_data)

for u in "${ORDER[@]}"; do
  cl="${CLOSURE[$u]:-}"
  if [ -z "$cl" ] || [ ! -d "$cl" ]; then echo "SKIP $u (no closure: $cl)"; continue; fi
  if [ "${PKG[$u]:-0}" = "1" ]; then
    SCRIPT="delta_probe_pkg.py"; ARGS=("$u" "$REPS" "$NSUB")
  else
    SCRIPT="delta_probe_endpoint.py"; ARGS=("$u" "$REPS" "$NSUB")
  fi
  echo "================ Δ-probe ENDPOINT: $u  (rig=median-of-${NSUB}, reps=${REPS}, $SCRIPT) ================"
  ./scripts/measure_wrap.sh \
    -v ./scripts:/probe:ro,Z \
    -v ./src:/src:ro,Z \
    -v "./$cl:/unit/closure:ro,Z" \
    -v "./$OUT:/out:Z" \
    -e PYTHONPATH=/src \
    "$IMG" \
    python "/probe/corpus/$SCRIPT" "${ARGS[@]}"
  echo "---- $u endpoint done (rc=$?) ----"
done
echo "ALL endpoint re-measures processed -> $OUT"
