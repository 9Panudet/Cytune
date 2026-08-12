#!/usr/bin/env bash
# CI/preflight assertion for Step 0.1.3 (roadmap §1.3, §6.6 item 1):
#  (1) committed lockfile hashes match the working tree (sha256sum -c);
#  (2) the image's installed package set matches requirements.lock exactly (zero diff);
#  (3) interpreter is the pinned Python 3.12.3; `import smac` works (guards D3 regression);
#  (4) SMAC RF backend is the recorded one: sklearn-backed, pyrfr absent.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HASHFILE="${LOCK_HASHFILE:-$REPO_ROOT/data/env/LOCK_HASHES.sha256}"   # override = negative-test hook
IMAGE="${MOTIFBO_IMAGE:-localhost/motifbo-env:phase0}"
LOCK="$REPO_ROOT/data/env/requirements.lock"

FAIL=0

# (1) lockfile hashes
if ! (cd "$REPO_ROOT" && grep -v '^#' "$HASHFILE" | sha256sum -c --quiet -); then
  echo "MISMATCH: lockfile sha256 differs from committed LOCK_HASHES.sha256"
  FAIL=1
fi

# (2) installed set == lock (name==version, case/sep-normalized per PEP 503)
norm() { tr 'A-Z' 'a-z' | sed 's/[-_.]\+/-/'; }
LOCK_SET="$(grep -E '^[a-zA-Z0-9_.-]+==' "$LOCK" | sed 's/ .*//;s/\\$//' | norm | sort)"
IMG_SET="$(podman run --rm "$IMAGE" pip freeze --all --exclude pip | norm | sort)"
if ! DIFF="$(diff <(echo "$LOCK_SET") <(echo "$IMG_SET"))"; then
  echo "MISMATCH: image package set vs requirements.lock:"; echo "$DIFF"
  FAIL=1
fi

# (3)+(4) interpreter pin, smac importability, recorded backend
if ! podman run --rm -i "$IMAGE" python - <<'EOF'
import platform, sys
assert platform.python_version() == "3.12.3", platform.python_version()
import smac  # D3 guard: fails loudly on sklearn/smac skew
try:
    import pyrfr
    sys.exit("pyrfr present — contradicts recorded backend (SMAC_RF_BACKEND.md)")
except ImportError:
    pass
import inspect
import smac.model.random_forest.random_forest as rf
assert "from sklearn.ensemble._forest import ForestRegressor" in inspect.getsource(rf)
print("python/smac/backend assertions OK")
EOF
then
  echo "MISMATCH: in-image interpreter/smac/backend assertion failed"
  FAIL=1
fi

if [ "$FAIL" -ne 0 ]; then echo "PYTHON ENV CHECK: FAIL"; exit 1; fi
echo "PYTHON ENV CHECK: PASS (hashes, package set, interpreter, backend)"
