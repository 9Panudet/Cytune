#!/usr/bin/env bash
# Measurement wrapper (Step 0.2.1; roadmap §5.1, §1.2). The ONLY sanctioned way to run
# a measurement: verifies the frequency-control state set by scripts/host_prep.sh,
# logs it, then runs ONE command inside the pinned container on the isolated core 3.
#
#   measure_wrap.sh --verify-only
#   measure_wrap.sh [podman-args...] <image> <cmd...>
#     -> podman run --rm --cpuset-cpus=3 --memory=12g --memory-swap=12g --network=none \
#          [podman-args...] <image> <cmd...>
#
# REFUSES (exit 78, logged) unless ALL hold:        (roadmap Step 0.2.1 check)
#   no_turbo == 1; governor(cpu3) == performance; cpu7 (SMT sibling) idle-guaranteed:
#   either OFFLINE, or ONLINE while listed in isolcpus (post-D4 policy — keeps the
#   coretemp "Core 3" channel registered).
# It VERIFIES only — it never mutates host state (that is host_prep.sh, human+sudo).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GOVDIR="$REPO_ROOT/logs/governor"
LOG="$GOVDIR/invocations.log"
mkdir -p "$GOVDIR"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
ARGV="$*"   # captured before refuse() can shadow $* with its own arguments

NT=$(cat /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || echo MISSING)
GV=$(cat /sys/devices/system/cpu/cpu3/cpufreq/scaling_governor 2>/dev/null || echo MISSING)
C7=$(cat /sys/devices/system/cpu/cpu7/online 2>/dev/null || echo MISSING)
ISO=$(cat /sys/devices/system/cpu/isolated 2>/dev/null || echo "")
FQ=$(cat /sys/devices/system/cpu/cpu3/cpufreq/scaling_cur_freq 2>/dev/null || echo NA)
# CF-4 (§6.6): the active THP policy is the bracketed token in .../enabled.
THP=$(sed -n 's/.*\[\(.*\)\].*/\1/p' /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || echo MISSING)
STATE="no_turbo=$NT gov_cpu3=$GV cpu7_online=$C7 isolated=$ISO freq_cpu3_khz=$FQ thp=$THP"

refuse() {
  echo "$(ts) REFUSED $STATE reason=$1 argv=[$ARGV]" >> "$LOG"
  echo "measure_wrap: REFUSED — $1" >&2
  echo "  state: $STATE" >&2
  echo "  remedy: have the human run: sudo bash scripts/host_prep.sh" >&2
  exit 78
}

[ "$NT" = "1" ]           || refuse "no_turbo!=1 (turbo enabled or intel_pstate missing)"
[ "$GV" = "performance" ] || refuse "governor(cpu3)!=performance"
# sibling idle guarantee: offline, OR online-but-isolated (post-D4; isolcpus contains 3 and 7)
if [ "$C7" != "0" ]; then
  { grep -qw 3 <<<"$ISO" && grep -qw 7 <<<"$ISO"; } \
    || refuse "cpu7 online and not isolated (need offline, or isolcpus covering 3 and 7)"
fi
# CF-4 page-backing determinism (results/characterization/CF4_BASELINE.md): host THP
# 'always' re-enables khugepaged background promotion -> nondeterministic run-to-run
# page backing. The measurement requires 'madvise' or 'never' (non-madvising kernels
# get deterministic 4 KB either way). Captures the unversioned host invariant the
# CF-4 baseline depends on; fail-loud on drift.
case "$THP" in
  madvise|never) ;;
  *) refuse "thp=$THP (need madvise|never; 'always' breaks CF-4 page-backing determinism)";;
esac

if [ "${1:-}" = "--verify-only" ]; then
  echo "$(ts) VERIFY-ONLY PASS $STATE" >> "$LOG"
  echo "measure_wrap: state OK — $STATE"
  exit 0
fi
[ "$#" -ge 1 ] || { echo "usage: measure_wrap.sh [--verify-only | [podman-args] <image> <cmd...>]"; exit 2; }

"$REPO_ROOT/scripts/thermal_log.sh" snapshot >/dev/null   # pre-run thermal record
echo "$(ts) RUN-START PASS $STATE argv=[$*]" >> "$LOG"

# MOTIFBO_CYCLES=1: cycle-subsample run (§5.1 10% cross-check) — uses the committed
# perf seccomp profile. Default candidate runs keep perf_event_open DENIED (0.2.3).
EXTRA_OPTS=()
if [ "${MOTIFBO_CYCLES:-0}" = "1" ]; then
  EXTRA_OPTS+=(--security-opt "seccomp=$REPO_ROOT/data/env/seccomp-perf-events.json")
  echo "$(ts) CYCLES-SUBSAMPLE run (perf seccomp profile active)" >> "$LOG"
fi

set +e
podman run --rm --cpuset-cpus=3 --memory=12g --memory-swap=12g --network=none \
  -e RIG_FINGERPRINT="$STATE" \
  "${EXTRA_OPTS[@]}" "$@"
RC=$?
set -e

"$REPO_ROOT/scripts/thermal_log.sh" snapshot >/dev/null   # post-run thermal record
echo "$(ts) RUN-END rc=$RC $STATE" >> "$LOG"
exit "$RC"
