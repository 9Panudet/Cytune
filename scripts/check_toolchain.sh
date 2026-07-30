#!/usr/bin/env bash
# CI/preflight assertion for Step 0.1.2 (roadmap §1.3, §6.6 item 1):
# every pkg=version line in TOOLCHAIN.lock must match dpkg inside the built image,
# and gcc -dumpfullversion must match gcc_dumpfullversion. Required diff: exactly zero.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="${TOOLCHAIN_LOCK:-$REPO_ROOT/data/env/TOOLCHAIN.lock}"   # override = negative-test hook
IMAGE="$(grep -E '^image_tag=' "$LOCK" | cut -d= -f2)"

# pkg=version lines from the apt-backed sections ONLY ([apt-pinned*], [recorded-asserted]);
# other sections (e.g. [agent-tooling], host-side pins) are not dpkg-assertable in-image.
mapfile -t WANT < <(awk '/^\[/{inapt=($0 ~ /apt-pinned|recorded-asserted/)} inapt' "$LOCK" \
                    | grep -E '^[a-z0-9][a-z0-9.+-]*=' \
                    | sed 's/[[:space:]]*#.*$//')

PKGS=()
for line in "${WANT[@]}"; do PKGS+=("${line%%=*}"); done

GOT="$(podman run --rm "$IMAGE" bash -c \
  "dpkg-query -W -f '\${Package}=\${Version}\n' ${PKGS[*]} && echo gcc_dumpfullversion=\$(gcc -dumpfullversion)")"

FAIL=0
for line in "${WANT[@]}"; do
  if ! grep -qxF "$line" <<<"$GOT"; then
    echo "MISMATCH: lock has '$line'; image has '$(grep -E "^${line%%=*}=" <<<"$GOT" || echo '<absent>')'"
    FAIL=1
  fi
done

LOCK_GCCV="$(grep -E '^gcc_dumpfullversion=' "$LOCK")"
if ! grep -qxF "$LOCK_GCCV" <<<"$GOT"; then
  echo "MISMATCH: $LOCK_GCCV vs image $(grep -E '^gcc_dumpfullversion=' <<<"$GOT")"
  FAIL=1
fi

if [ "$FAIL" -ne 0 ]; then echo "TOOLCHAIN CHECK: FAIL"; exit 1; fi
echo "TOOLCHAIN CHECK: PASS ($(wc -l <<<"$GOT") assertions, zero diff)"
