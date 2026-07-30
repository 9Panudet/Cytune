#!/usr/bin/env bash
# Asserts the F1 guard is installed in .git/hooks/post-commit (PREREG §12 A-4h).
# `graphify hook install` regenerates that hook and silently drops the guard, so this check is
# part of the pre-resume checklist — a missing guard means the next unattended campaign runs
# without CF-1 protection.
set -uo pipefail
repo="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
hook="$repo/.git/hooks/post-commit"

if [ ! -f "$hook" ]; then
    echo "verify_graphify_gate: no post-commit hook installed — nothing can spawn a rebuild. OK."
    exit 0
fi
if grep -q 'cytune F1 guard' "$hook" && grep -q 'graphify_gate.sh' "$hook"; then
    echo "verify_graphify_gate: PASS — F1 guard present in .git/hooks/post-commit"
    exit 0
fi
cat >&2 <<'EOF'
verify_graphify_gate: FAIL — .git/hooks/post-commit exists but carries NO F1 guard.
A commit during a live campaign cycle would spawn a graph rebuild and contaminate measurement
(CF-4: cpuset does not isolate DRAM bandwidth). Reinstall the guard by inserting, right after the
shebang of .git/hooks/post-commit:

    # --- cytune F1 guard (PREREG §12 A-4h) ---
    . "$(git rev-parse --show-toplevel)/scripts/hooks/graphify_gate.sh"
    # --- end cytune F1 guard ---
EOF
exit 1
