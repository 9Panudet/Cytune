#!/usr/bin/env bash
# F1 (PREREG §12 A-4h): defer the graphify post-commit rebuild while a campaign cycle is live.
#
# Sourced from the TOP of .git/hooks/post-commit, immediately after the shebang:
#
#     # --- cytune F1 guard (PREREG §12 A-4h) ---
#     . "$(git rev-parse --show-toplevel)/scripts/hooks/graphify_gate.sh"
#     # --- end cytune F1 guard ---
#
# REINSTALL AFTER `graphify hook install` — that command regenerates .git/hooks/post-commit and
# drops this guard. Verify with:  bash scripts/hooks/verify_graphify_gate.sh
#
# Behaviour: on BUSY it records that a rebuild is owed and exits the hook 0 (commit succeeds, no
# rebuild spawned). On IDLE it does nothing and lets the normal graphify hook body run.
# Drain the debt when idle with:  bash scripts/hooks/graphify_drain.sh

_gg_repo="$(git rev-parse --show-toplevel 2>/dev/null || echo .)"
_gg_queue="$_gg_repo/graphify-out/.graphify_deferred"

if _gg_why="$(bash "$_gg_repo/scripts/hooks/campaign_busy.sh" 2>/dev/null)"; then
    mkdir -p "$(dirname "$_gg_queue")"
    # Append-only debt log: which commit was skipped and why. Drain reads only the fact that the
    # file is non-empty; the lines are for the operator and the P-2 report's honesty trail.
    printf '%s\t%s\t%s\n' \
        "$(git rev-parse --short HEAD 2>/dev/null || echo '?')" \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "$_gg_why" >> "$_gg_queue"
    echo "[graphify hook] DEFERRED — $_gg_why (CF-1 quiesce-all; rebuild owed, see graphify-out/.graphify_deferred)"
    exit 0
fi
unset _gg_repo _gg_queue _gg_why
