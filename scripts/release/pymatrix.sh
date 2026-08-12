#!/usr/bin/env bash
# The host-interpreter cell of the D3 stability matrix -- NOT RUN before 2026-08-13.
#
# `pyproject.toml` claims `requires-python = ">=3.9"` and `doctor` blocks below 3.9, while every
# run in the launch pass used ONE interpreter (3.14.5). Five of the six supported versions had
# never executed a line of this code, so the claim covered five untested versions. This runs the
# SHIPPED tree -- what a user pip-installs -- on each of them.
#
# The product suite only (`pytest -q src/cytune`): the half that must pass with no scripts/ and no
# results/. Nothing here measures time, so it is not a rig run, does not go through
# `measure_wrap.sh`, and does not need image X'. Throwaway `python:<v>-slim` containers are the
# right tool precisely because the thing under test is the interpreter.
#
# It found D33 on its first pass: `test_failure_path_sanitizer_check_passes_when_the_image_is_present`
# stubbed `doctor._run` but not `sanitize_gate.is_pinned_image()`, so it was reading the host's
# image store and failed on all six interpreters -- and on any machine without the pinned image.
#
#   usage: scripts/release/pymatrix.sh [outdir]        (default: results/release/pymatrix)
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-$REPO/results/release/pymatrix}"
VERSIONS="3.9 3.10 3.11 3.12 3.13 3.14"

mkdir -p "$OUT"
TAR="$(mktemp -d)/shipped.tar"

# The WORKING TREE, not `git archive main`: this has to be able to validate a fix before it is
# committed, and main is one branch behind dev by construction. `docs/` and `evidence/` are in
# because three suite tests assert that shipped strings cite documents that exist.
tar -C "$REPO" -cf "$TAR" pyproject.toml README.md src docs evidence || exit 1

rc_all=0
for V in $VERSIONS; do
  echo "=== python $V ==="
  podman run --rm -v "$TAR:/shipped.tar:ro,Z" "docker.io/library/python:${V}-slim" \
    bash -lc '
      set -e
      mkdir -p /work && cd /work && tar xf /shipped.tar
      python -V
      pip -q install --disable-pip-version-check ".[test]" 2>&1 | tail -3
      cytune --version
      python -c "import cytune, sys; print(\"import ok\", cytune.__version__, sys.version.split()[0])"
      python -m pytest -q src/cytune 2>&1 | tail -15
    ' >"$OUT/py${V}.log" 2>&1
  rc=$?
  [ $rc -eq 0 ] || rc_all=1
  echo "exit=$rc $(tail -2 "$OUT/py${V}.log" | tr '\n' ' ')"
done
echo "logs: $OUT"
exit $rc_all
