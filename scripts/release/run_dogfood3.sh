#!/usr/bin/env bash
# F1 — run cytune end-to-end on the nine Dataset-R anchors.
#
# Read-only with respect to the study: it reads the STAGED copies under results/release/dogfood/
# and writes only under results/release/dogfood/. Nothing touches results/fleet or any frozen table.
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
CY="$REPO/.venv/bin/cytune"
STAGE="$REPO/results/release/dogfood3/staging"
OUT="$REPO/results/release/dogfood3"
mkdir -p "$OUT/runs"

ANCHORS="${*:-fleet_R_01_csr fleet_R_02_pava fleet_R_03_lda fleet_R_04_binning fleet_R_05_ppoly fleet_R_06_floyd fleet_R_07_cc fleet_R_08_elkan fleet_R_09_predictor}"

for kid in $ANCHORS; do
  echo "=== $kid ===" >> "$OUT/RUNLOG.txt"
  t0=$(date +%s)
  "$CY" tune "$STAGE/$kid" \
        --driver "$STAGE/$kid/driver.py" \
        --workspace "$OUT/runs/$kid" \
        --name "$kid" \
        --json > "$OUT/runs/$kid.json" 2> "$OUT/runs/$kid.log"
  rc=$?
  t1=$(date +%s)
  echo "$kid exit=$rc wall_s=$((t1 - t0))" >> "$OUT/RUNLOG.txt"
done
echo "DONE" >> "$OUT/RUNLOG.txt"
