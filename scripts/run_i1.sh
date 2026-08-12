#!/usr/bin/env bash
# Step 0.5.2 I-1 runner (host side). Verifies the rig, builds the known-good/known-bad
# configs OFF the measurement core, starts a 1 s thermal watch, then measures all four
# (kernel, config) at K_final=30 (+5 warmup, cycles on) through measure_wrap on the
# isolated core. RAW -> results/calibration/i1/raw/. Per PREREG_I1.md.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

./scripts/measure_wrap.sh --verify-only

OUTDIR="results/calibration/i1/raw"
mkdir -p "$OUTDIR" sandbox/i1

GIT_REV=$(git rev-parse --short HEAD)
IMAGE_ID=$(podman image inspect localhost/motifbo-env:phase0 --format '{{.Id}}' | cut -c1-12)
KERNELS="${MOTIFBO_I1_KERNELS:-csr_scale pava horner}"

# 1. Build the requested configs off the measurement core (plain podman).
podman run --rm -v ./src:/src:ro,Z -v ./scripts:/probe:ro,Z -v ./sandbox/i1:/build:Z \
  -e MOTIFBO_I1_KERNELS="$KERNELS" \
  localhost/motifbo-env:phase0 python /probe/build_i1.py

# 2. Thermal watch.
THERM="logs/governor/thermal/i1_$(date -u +%Y%m%dT%H%M%SZ).csv"
./scripts/thermal_log.sh watch 1 "$THERM" & WPID=$!
trap 'kill $WPID 2>/dev/null || true' EXIT
echo "thermal watch -> $THERM (pid $WPID)"

# 3. Measure each (kernel, config) serially on the isolated core.
for k in $KERNELS; do
  for c in good bad; do
    MOTIFBO_CYCLES=1 ./scripts/measure_wrap.sh \
      -v ./src:/src:ro,Z -v ./scripts:/probe:ro,Z -v ./sandbox/i1:/build:ro,Z \
      -v "./$OUTDIR:/out:Z" \
      -e PYTHONPATH=/src -e PYTHONDONTWRITEBYTECODE=1 \
      -e MOTIFBO_IMAGE_ID="$IMAGE_ID" -e MOTIFBO_GIT_REV="$GIT_REV" \
      localhost/motifbo-env:phase0 \
      python /probe/i1_measure.py "$k" "$c" "/out/${k}_${c}_K30.json"
  done
done

kill $WPID 2>/dev/null || true; trap - EXIT
echo "I-1 raw complete:"; ls -la "$OUTDIR"/; echo "thermal: $THERM"
