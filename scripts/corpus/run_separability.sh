#!/usr/bin/env bash
# Step-1.3 A3 — separability factorial (2 boundscheck × 3 opt_level × 2 march) on the endpoint rig,
# CF-1 serial, for the 2 high-Δ units. csr is bare; elkan is package-import multi-module (cobuild) —
# separability_factorial.py auto-detects via UNITS[...].cobuild and rebuilds _k_means_common under each
# directive config. Usage: run_separability.sh [reps=15] [nsub=3] [unit ...]   (default csr + elkan)
set -uo pipefail
cd "$(dirname "$0")/../.."
REPS="${1:-15}"; NSUB="${2:-3}"; shift 2 || true
IMG=localhost/motifbo-env:phase1
OUT=results/characterization/separability
mkdir -p "$OUT"

declare -A CLOSURE=(
  [csr_mean_variance_axis0]=data/corpus/sklearn/sparsefuncs_fast/closure
  [elkan_iter_chunked_dense]=data/corpus/sklearn/_k_means_elkan/closure
)
ORDER=("$@")
[ "${#ORDER[@]}" -eq 0 ] && ORDER=(csr_mean_variance_axis0 elkan_iter_chunked_dense)

for u in "${ORDER[@]}"; do
  cl="${CLOSURE[$u]:-}"
  if [ -z "$cl" ] || [ ! -d "$cl" ]; then echo "SKIP $u (no closure: $cl)"; continue; fi
  echo "================ SEPARABILITY factorial: $u  (2x3x2, rig=median-of-${NSUB}) ================"
  ./scripts/measure_wrap.sh \
    -v ./scripts:/probe:ro,Z \
    -v ./src:/src:ro,Z \
    -v "./$cl:/unit/closure:ro,Z" \
    -v "./$OUT:/out:Z" \
    -e PYTHONPATH=/src \
    "$IMG" \
    python /probe/corpus/separability_factorial.py "$u" "$REPS" "$NSUB"
  echo "---- $u separability done (rc=$?) ----"
done
echo "ALL separability units processed -> $OUT"
