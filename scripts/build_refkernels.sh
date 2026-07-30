#!/usr/bin/env bash
# Build the two 0.5.1 reference kernels under the PILOT REFERENCE CONFIG (recorded
# constant, Step 0.2.4): Cython defaults (all checks on) + gcc -O2 -march=x86-64
# -ffp-contract=off -g0 -pipe. Runs INSIDE the pinned container:
#   podman run --rm -v ./src:/src:ro,Z -v ./sandbox/refkernels:/build:Z \
#     localhost/motifbo-env:phase0 bash /src/../scripts/... (see run_pilot.sh)
# Output: /build/{csr_scale,pava}.so + build log on stdout.
set -euo pipefail
SRC="${1:-/src/motifbo/refkernels}"
OUT="${2:-/build}"
PYINC="$(python3.12 -c 'import sysconfig; print(sysconfig.get_paths()["include"])')"

echo "cython: $(cython --version 2>&1); gcc: $(gcc -dumpfullversion)"
for k in csr_scale pava; do
  cython -3 "$SRC/$k.pyx" -o "$OUT/$k.c"
  gcc -O2 -march=x86-64 -ffp-contract=off -g0 -pipe -shared -fPIC \
      -I"$PYINC" "$OUT/$k.c" -o "$OUT/$k.so"
  echo "built $OUT/$k.so ($(stat -c%s "$OUT/$k.so") bytes)"
done
