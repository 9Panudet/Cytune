#!/usr/bin/env bash
# Motif+BO Step 0.2.1 — host measurement preparation. RUN BY THE HUMAN WITH SUDO:
#   sudo bash scripts/host_prep.sh
# The orchestrator NEVER runs this and never assumes it ran: scripts/measure_wrap.sh
# re-verifies the resulting state at every invocation and refuses to run otherwise.
# Effects do NOT survive reboot. Restore with: sudo bash scripts/host_unprep.sh
set -euo pipefail
[ "$(id -u)" = "0" ] || { echo "ERROR: run with sudo"; exit 1; }

# 1. Disable turbo (roadmap §5.1)
echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo

# 2. SMT sibling (cpu7) idle policy — isolcpus-aware (defect D4). Done BEFORE the
#    governor loop so cpu7's freshly created cpufreq policy is covered by it.
#    - isolcpus=3,7 active (post-0.2.4 hardening): keep cpu7 ONLINE — the scheduler
#      already never places tasks there, and offlining it de-registers coretemp's
#      "Core 3" channel (the measurement core's own sensor).
#    - no isolcpus (pre-hardening boot): offline cpu7 (the only idle guarantee).
if grep -qw 7 /sys/devices/system/cpu/isolated 2>/dev/null; then
  echo 1 > /sys/devices/system/cpu/cpu7/online
  sleep 0.2   # cpufreq policy (re)appears on online
  SIB_POLICY="online+isolated"
else
  echo 0 > /sys/devices/system/cpu/cpu7/online
  SIB_POLICY="offline"
fi

# 3. Performance governor on every ONLINE CPU. Writing an OFFLINE cpu's lingering
#    policy returns EBUSY and killed earlier runs at this point (D4, bug 2) — so
#    iterate online CPUs only, but still hard-fail on any of those.
#    Direct sysfs write — cpupower (kernel-tools) is not installed; same kernel
#    interface. Recorded deviation: HOST_NOTES.md.
for c in 0 1 2 3 4 5 6 7; do
  on=$(cat /sys/devices/system/cpu/cpu$c/online 2>/dev/null || echo 1)  # cpu0: no file
  [ "$on" = "1" ] || continue
  echo performance > /sys/devices/system/cpu/cpu$c/cpufreq/scaling_governor
done

# 4. Show the resulting state (the wrapper re-verifies this independently)
echo "--- host_prep result ---"
echo "no_turbo     = $(cat /sys/devices/system/cpu/intel_pstate/no_turbo)   (need 1)"
echo "cpu7 policy  = $SIB_POLICY (online=$(cat /sys/devices/system/cpu/cpu7/online), isolated=$(cat /sys/devices/system/cpu/isolated))"
for c in 0 1 2 3; do
  echo "cpu$c governor= $(cat /sys/devices/system/cpu/cpu$c/cpufreq/scaling_governor)   (need performance)"
done
echo "Done. Verify from the orchestrator with: scripts/measure_wrap.sh --verify-only"
