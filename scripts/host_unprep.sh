#!/usr/bin/env bash
# Motif+BO — restore host defaults after measurement sessions (run with sudo).
# Inverse of scripts/host_prep.sh. A reboot achieves the same.
set -euo pipefail
[ "$(id -u)" = "0" ] || { echo "ERROR: run with sudo"; exit 1; }

echo 1 > /sys/devices/system/cpu/cpu7/online
echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo
for g in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor; do
  echo schedutil > "$g"
done
echo "Restored: turbo on, schedutil governor, cpu7 online."
