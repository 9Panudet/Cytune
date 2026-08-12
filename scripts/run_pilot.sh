#!/usr/bin/env bash
# Step 0.2.4 pilot runner (host side). Verifies the rig, starts a 1 s thermal watch,
# runs both reference kernels at K_pilot=30 (+5 warmup, cycles on) through
# measure_wrap on the isolated core, writes RAW results to results/pilot/raw/.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

./scripts/measure_wrap.sh --verify-only

OUTDIR="${1:-results/pilot/raw}"          # pilot2 (PREREG_PILOT2.md): results/pilot/raw2
mkdir -p "$OUTDIR"
THERM="logs/governor/thermal/pilot_$(date -u +%Y%m%dT%H%M%SZ).csv"
./scripts/thermal_log.sh watch 1 "$THERM" & WPID=$!
trap 'kill $WPID 2>/dev/null || true' EXIT
echo "thermal watch -> $THERM (pid $WPID)"

GIT_REV=$(git rev-parse --short HEAD)
IMAGE_ID=$(podman image inspect localhost/motifbo-env:phase0 --format '{{.Id}}' | cut -c1-12)

for k in csr_scale pava; do
  MOTIFBO_CYCLES=1 ./scripts/measure_wrap.sh \
    -v ./src:/src:ro,Z -v ./scripts:/probe:ro,Z -v ./sandbox/refkernels:/build:ro,Z \
    -v "./$OUTDIR:/out:Z" \
    -e PYTHONPATH=/src -e PYTHONDONTWRITEBYTECODE=1 \
    -e MOTIFBO_IMAGE_ID="$IMAGE_ID" -e MOTIFBO_GIT_REV="$GIT_REV" \
    localhost/motifbo-env:phase0 \
    python /probe/pilot_measure.py "$k" "/out/${k}_K30.json"
done

podman run --rm -v ./src:/src:ro,Z -v ./scripts:/probe:ro,Z -e PYTHONPATH=/src \
  localhost/motifbo-env:phase0 python /probe/pilot_measure.py manifest \
  > results/pilot/INPUT_MANIFEST.json

kill $WPID 2>/dev/null || true; trap - EXIT
echo "pilot raw complete:"; ls -la "$OUTDIR"/; echo "thermal: $THERM"
