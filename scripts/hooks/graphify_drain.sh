#!/usr/bin/env bash
# F1 drain (PREREG §12 A-4h): pay off graph rebuilds deferred during campaign cycles.
# Run when the runner is idle/paused — e.g. at a steward tick, or before reading the graph.
# Refuses to run while a cycle is live, so draining can never itself become the contaminating load.
set -uo pipefail

# Resolve from THIS script's own location, not from git or cwd. An empty/wrong repo path used to
# make the busy check silently fail to execute and the drain then reported "nothing owed" while a
# cycle was live — a fail-OPEN on a safety check. Caught by test_drain_refuses_while_a_cycle_is_live.
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
queue="$repo/graphify-out/.graphify_deferred"
busy="$repo/scripts/hooks/campaign_busy.sh"

# FAIL CLOSED: if the predicate cannot be run we do not know whether a cycle is live, and the
# expensive mistake is rebuilding during one. Refuse rather than assume idle.
if [ ! -r "$busy" ]; then
    echo "graphify_drain: REFUSING — cannot read the busy predicate at $busy (failing closed)."
    exit 2
fi
if why="$(bash "$busy" 2>/dev/null)"; then
    echo "graphify_drain: REFUSING — $why (CF-1 quiesce-all). Try again when the runner is idle."
    exit 2
fi

if [ ! -s "$queue" ]; then
    echo "graphify_drain: nothing owed."
    exit 0
fi

echo "graphify_drain: $(wc -l < "$queue") deferred commit(s) owed:"
cat "$queue"
# AST-only, no API cost (CLAUDE.md). One full update settles any number of deferred commits.
if graphify update "$repo"; then
    mv "$queue" "$queue.done.$(date -u +%Y%m%dT%H%M%SZ)"
    echo "graphify_drain: rebuilt; debt cleared."
else
    echo "graphify_drain: rebuild FAILED — debt log kept at $queue"
    exit 1
fi
