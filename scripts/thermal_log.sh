#!/usr/bin/env bash
# Thermal monitor (Step 0.2.1, §5.1). Reads coretemp via sysfs hwmon directly
# (lm_sensors not installed — same data source; recorded deviation: HOST_NOTES.md).
# Also records throttle counters: §5.1 discards any run with throttle events > 0.
#
# Usage:
#   thermal_log.sh snapshot [outfile]        one CSV line (default file, see below)
#   thermal_log.sh watch <seconds> [outfile] sample every <seconds> until killed
#
# CSV: ts_epoch,ts_iso,pkg_mC,core0_mC,core1_mC,core2_mC,core3_mC,
#      core3_throttle,pkg_throttle,cpu3_freq_khz,no_turbo,gov_cpu3
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTDIR="$REPO_ROOT/logs/governor/thermal"
mkdir -p "$OUTDIR"

HW=/sys/class/hwmon/hwmon1               # coretemp on this host (CPU_MAP.md)
[ "$(cat $HW/name)" = "coretemp" ] || { # device numbering can shift across boots
  HW=$(grep -l coretemp /sys/class/hwmon/hwmon*/name | head -1 | xargs dirname)
}
[ -n "$HW" ] || { echo "coretemp hwmon not found"; exit 1; }

# Channels are discovered BY LABEL, never by fixed temp<N> index: enumeration shifts
# across boots with CPU online/isolation state (defect D4 — a reboot removed the
# "Core 3" channel and the rig aborted). Missing channel -> NA, never a crash.
chan() { # label -> tempN_input path or empty (empty is NOT an error: set -e safe)
  local f
  for f in "$HW"/temp[0-9]*_label; do
    if [ "$(cat "$f")" = "$1" ]; then echo "${f%_label}_input"; return 0; fi
  done
  return 0
}
C_PKG=$(chan "Package id 0"); C_C0=$(chan "Core 0"); C_C1=$(chan "Core 1")
C_C2=$(chan "Core 2"); C_C3=$(chan "Core 3")

HEADER="ts_epoch,ts_iso,pkg_mC,core0_mC,core1_mC,core2_mC,core3_mC,core3_throttle,pkg_throttle,cpu3_freq_khz,no_turbo,gov_cpu3"

rd() { [ -n "$1" ] && cat "$1" 2>/dev/null || echo NA; }

line() {
  local t1 t2 t3 t4 t5 ct pt fq nt gv
  t1=$(rd "$C_PKG")
  t2=$(rd "$C_C0")
  t3=$(rd "$C_C1")
  t4=$(rd "$C_C2")
  t5=$(rd "$C_C3")
  ct=$(cat /sys/devices/system/cpu/cpu3/thermal_throttle/core_throttle_count 2>/dev/null || echo NA)
  pt=$(cat /sys/devices/system/cpu/cpu3/thermal_throttle/package_throttle_count 2>/dev/null || echo NA)
  fq=$(cat /sys/devices/system/cpu/cpu3/cpufreq/scaling_cur_freq 2>/dev/null || echo NA)
  nt=$(cat /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || echo NA)
  gv=$(cat /sys/devices/system/cpu/cpu3/cpufreq/scaling_governor 2>/dev/null || echo NA)
  echo "$(date +%s),$(date -u +%Y-%m-%dT%H:%M:%SZ),$t1,$t2,$t3,$t4,$t5,$ct,$pt,$fq,$nt,$gv"
}

MODE="${1:-snapshot}"
case "$MODE" in
  snapshot)
    OUT="${2:-$OUTDIR/thermal_$(date -u +%Y%m%d).csv}"
    [ -s "$OUT" ] || echo "$HEADER" > "$OUT"
    line | tee -a "$OUT"
    ;;
  watch)
    IV="${2:?usage: thermal_log.sh watch <seconds> [outfile]}"
    OUT="${3:-$OUTDIR/thermal_$(date -u +%Y%m%d).csv}"
    [ -s "$OUT" ] || echo "$HEADER" > "$OUT"
    while true; do line >> "$OUT"; sleep "$IV"; done
    ;;
  *) echo "usage: thermal_log.sh snapshot [outfile] | watch <seconds> [outfile]"; exit 2 ;;
esac
