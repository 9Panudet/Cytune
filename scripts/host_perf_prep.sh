#!/usr/bin/env bash
# Motif+BO Step 0.2.3 — install the scoped SELinux module enabling in-container
# self-process perf counting (cycle cross-check, roadmap §5.1).
# RUN BY THE HUMAN WITH SUDO:  sudo bash scripts/host_perf_prep.sh
# SELinux remains Enforcing. Persists across reboots. Remove: sudo semodule -r motifbo_perf
set -euo pipefail
[ "$(id -u)" = "0" ] || { echo "ERROR: run with sudo"; exit 1; }
cd "$(dirname "$0")/../data/env/selinux"

command -v checkmodule >/dev/null 2>&1 || dnf install -y checkpolicy
checkmodule -M -m -o motifbo_perf.mod motifbo_perf.te
semodule_package -o motifbo_perf.pp -m motifbo_perf.mod
semodule -i motifbo_perf.pp

echo "--- result ---"
semodule -l | grep motifbo_perf && echo "module installed; SELinux still $(getenforce)"
echo "Verify from the orchestrator: the Step 0.2.3 in-container probe must print OK."
