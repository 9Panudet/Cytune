#!/usr/bin/env bash
# Host-side runner for the Step-1.3 Δ-probe on PACKAGE-IMPORT multi-module units (elkan,
# predictor). Same CF-1 discipline as run_delta_probe.sh (ONE container, isolated core 3,
# verified rig) but the closure is built+imported as a PACKAGE (delta_probe_pkg.py), since
# these kernels relative-import a sibling vendored .so and cannot be bare-loaded.
#
# Usage: run_delta_probe_pkg.sh [nreps=25] [unit_key ...]   (default => elkan + predictor)
set -uo pipefail
cd "$(dirname "$0")/../.."
NREPS="${1:-25}"; shift || true
IMG=localhost/motifbo-env:phase1
OUT=results/characterization/delta_probe
mkdir -p "$OUT"

declare -A CLOSURE=(
  [elkan_iter_chunked_dense]=data/corpus/sklearn/_k_means_elkan/closure
  [_predict_from_raw_data]=data/corpus/sklearn/_predictor/closure
)
ORDER=(elkan_iter_chunked_dense _predict_from_raw_data)
[ "$#" -gt 0 ] && ORDER=("$@")

for u in "${ORDER[@]}"; do
  cl="${CLOSURE[$u]:-}"
  if [ -z "$cl" ] || [ ! -d "$cl" ]; then echo "SKIP $u (no closure: $cl)"; continue; fi
  echo "================ Δ-probe (pkg): $u  (closure=$cl) ================"
  ./scripts/measure_wrap.sh \
    -v ./scripts:/probe:ro,Z \
    -v ./src:/src:ro,Z \
    -v "./$cl:/unit/closure:ro,Z" \
    -v "./$OUT:/out:Z" \
    "$IMG" \
    python /probe/corpus/delta_probe_pkg.py "$u" "$NREPS"
  echo "---- $u done (rc=$?) ----"
done
echo "ALL pkg Δ-probe units processed -> $OUT"
