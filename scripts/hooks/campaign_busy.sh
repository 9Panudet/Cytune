#!/usr/bin/env bash
# CF-1 quiesce-all predicate: "is a campaign build/measure cycle live right now?"
#
# Exit 0 = BUSY (a cycle is live; nothing else may run), exit 1 = IDLE.
# Prints the reason on BUSY so callers can log WHY they deferred.
#
# WHY THIS EXISTS (PREREG §12 A-4h / F1). The stewardship claim that a background rebuild was
# harmless "because measurement is pinned to isolated cpu3/7" is WRONG and is overruled here:
# cpuset isolates CORES, not DRAM bandwidth or the shared LLC (CF-4), and D5's root cause was
# precisely host load during measurement. On 2026-07-24 an overlapping workload contaminated 626
# measured rows and they had to be discarded. Quiesce-all means nothing else runs.
#
# DELIBERATELY CONSERVATIVE: this reports BUSY for the WHOLE cycle (build + measure), not just the
# timed phase. A rebuild kicked off during a build phase can still be running when the unattended
# runner crosses into its measure phase — which is exactly how the 2026-07-24 contamination
# happened. The cheap false-positive (a deferred graph rebuild) is worth avoiding the expensive
# false-negative (discarded measurements).
set -uo pipefail

# Resolved from this script's own location — not from git (absent in the pinned images) and not
# from cwd (a caller's cwd must never change whether the box reads busy).
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# `pgrep -f` matches whole command lines, so it also matches THIS script's own caller whenever the
# caller's command line happens to contain the pattern — e.g. a shell running
# `bash scripts/measure_wrap.sh --verify-only && bash scripts/hooks/campaign_busy.sh`. That made
# the predicate report BUSY on an idle box (D19). The `[m]` bracket trick only excludes pgrep
# itself, not the ancestry, so the ancestry is excluded explicitly.
_ancestry() {
    local p="$$"
    while [ -n "$p" ] && [ "$p" -gt 1 ] 2>/dev/null; do
        printf '%s\n' "$p"
        p="$(ps -o ppid= -p "$p" 2>/dev/null | tr -d '[:space:]')"
    done
}
_SELF=" $(_ancestry | tr '\n' ' ') "

# Print PIDs matching $1 that are not this process or one of its ancestors.
others_matching() {
    local pid
    for pid in $(pgrep -f "$1" 2>/dev/null); do
        case "$_SELF" in *" $pid "*) continue ;; esac
        printf '%s\n' "$pid"
    done
}

# 1. The campaign runner itself.
if [ -n "$(others_matching "[r]un_fleet\.py")" ]; then
    echo "campaign runner (run_fleet.py) is alive"; exit 0
fi

# 2. A timed measurement in flight (rig wrapper or its measure child), even without the runner —
#    covers controls gates, R-anchors and any hand-launched measurement.
if [ -n "$(others_matching "[m]easure_wrap\.sh")" ] || [ -n "$(others_matching "[m]easure_child\.py")" ]; then
    echo "a timed measurement (measure_wrap/measure_child) is in flight"; exit 0
fi

# 3. An in-flight cycle marker outlives a momentary process gap (fork between phases, or a runner
#    that died mid-cycle without reconciling). Treat it as busy until it is reconciled.
if [ -f "$repo/results/fleet/_topup_inflight.json" ]; then
    echo "in-flight cycle marker present (results/fleet/_topup_inflight.json)"; exit 0
fi

exit 1
