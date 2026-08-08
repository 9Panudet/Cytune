#!/usr/bin/env bash
# THE PRE-TAG RITUAL. A live end-to-end run of every subcommand, against real containers.
#
# WHY THIS EXISTS AND WHY A TEST SUITE IS NOT IT. During the v1.0.0 architecture pass, 526 tests
# were green while `measure_wrap.sh` returned rc=127 mid-run: the script had been moved into the
# package and could no longer find the sibling it shells out to. Nothing in the suite touched it,
# because everything in the suite either mocks the rig or skips when podman is absent — which is
# correct for a unit suite and useless as a release gate. A green suite says the code is
# self-consistent. This says the product works on this machine.
#
#   bash scripts/release/smoke.sh          # ~4 minutes
#
# Exits non-zero on the first failure, loudly, naming the step.
set -uo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
CY="${CYTUNE:-$REPO/.venv/bin/cytune}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

pass() { printf '  \033[32mok\033[0m   %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; printf '\nSMOKE GATE FAILED — do not tag.\n'; exit 1; }
step() { printf '\n[%s] %s\n' "$1" "$2"; }

printf 'cytune live smoke gate — %s\n' "$($CY --version 2>&1)"

# ---------------------------------------------------------------------------- 1. doctor
step 1 "doctor — the environment is real"
if ! $CY doctor > "$WORK/doctor.txt" 2>&1; then
  cat "$WORK/doctor.txt"; fail "doctor reports a BLOCKING problem"
fi
grep -q "pinned image" "$WORK/doctor.txt" || fail "doctor did not check the pinned image"
pass "doctor exits 0"

$CY doctor --json > "$WORK/doctor.json" 2>/dev/null || fail "doctor --json failed"
python3 -c "
import json,sys
d=json.load(open('$WORK/doctor.json'))
assert d['schema'].startswith('cytune-doctor/'), d.get('schema')
assert d['ok'] is True, d
" || fail "doctor --json is not a valid cytune-doctor document"
pass "doctor --json honours its schema"

# ---------------------------------------------------------------------------- 2. init
step 2 "init — a driver written from a signature, with no hand editing"
mkdir -p "$WORK/proj" && cd "$WORK/proj"
cat > smoke.pyx <<'PYX'
def run(double[::1] a, long reps):
    cdef Py_ssize_t i, r, n = a.shape[0]
    cdef double acc = 0.0
    for r in range(reps):
        for i in range(n):
            acc += a[i] * 0.5
    return acc
PYX
$CY init smoke.pyx > "$WORK/init.txt" 2>&1 || fail "init exited non-zero"
grep -q "DRIVER CONTRACT: passes" "$WORK/init.txt" || { cat "$WORK/init.txt"; fail "init produced a driver that fails the contract check"; }
[ -f driver.py ] && [ -f .cytune.toml ] || fail "init did not write driver.py and .cytune.toml"
pass "init scaffolds a contract-passing driver"

# ---------------------------------------------------------------------------- 3. tune
step 3 "tune — a real build, a real measurement, a real gate (this is the rc=127 catcher)"
$CY tune smoke.pyx --driver driver.py --target-ms 5 --preset quick --apply \
   > "$WORK/tune.txt" 2>&1
RC=$?
case "$RC" in
  0|2|3) pass "tune completed with verdict exit $RC" ;;
  *) tail -40 "$WORK/tune.txt"; fail "tune exited $RC — 1 is an error, anything else is a crash" ;;
esac

CERT="$WORK/proj/.cytune/smoke/certificate.json"
[ -f "$CERT" ] || fail "no certificate was written"
python3 - "$CERT" <<'PY' || fail "the certificate is not bound to its artifacts"
import json, sys
c = json.load(open(sys.argv[1]))
p = c.get("provenance") or {}
assert p.get("emitted_artifact_sha256"), "no emitted artifact hash"
assert p["emitted_artifact_sha256"] == p.get("endpoint_artifact_sha256"), \
    "the emitted artifact is not the one that was timed"
assert p.get("toolchain_image_digest"), "no toolchain image digest"
assert c.get("attestation", {}).get("does_not_attest"), "no attestation scope"
d = c.get("factor_degeneracy") or {}
assert d.get("total_collapse") is False, d
print(f"  verdict={c['verdict']} artifact={p['emitted_artifact_sha256'][:12]} "
      f"image={p['toolchain_image_digest'].split(':')[-1][:12]} "
      f"binaries={d.get('n_distinct_artifacts')}/{c['budget']['total_measured']}")
PY
pass "the certificate is bound to the artifacts that produced it"

"$REPO/.venv/bin/python" - "$WORK/proj/.cytune/smoke" <<'PY' || fail "certificate.txt is not what certificate.json renders to"
import json, os, sys
from cytune import certify
d = sys.argv[1]
cert = json.load(open(os.path.join(d, "certificate.json")))
txt = open(os.path.join(d, "certificate.txt")).read()
assert certify.render(cert) + "\n" == txt, "the two files on disk disagree"
PY
pass "certificate.txt round-trips from certificate.json"

grep -q "PROVENANCE" "$WORK/proj/.cytune/smoke/certificate.txt" || fail "no PROVENANCE block"
grep -q "IT DOES NOT ATTEST" "$WORK/proj/.cytune/smoke/certificate.txt" || fail "no attestation block"
pass "the rendered certificate carries provenance and attestation"

# --apply writes beside the module and never touches it without --in-place
if [ "$RC" = "0" ]; then
  [ -f smoke.tuned.pyx ] || fail "--apply on an improvement wrote nothing"
  grep -q "^# cython:" smoke.tuned.pyx || fail "--apply wrote no directive header"
  pass "--apply wrote smoke.tuned.pyx and left the original alone"
else
  grep -q "NOT APPLIED" "$WORK/tune.txt" || fail "--apply neither applied nor explained why not"
  pass "--apply refused and said why (verdict was $RC)"
fi

# ---------------------------------------------------------------------------- 4. audit
step 4 "audit — the deterministic risk set, no timing"
$CY audit smoke.pyx --driver driver.py --json > "$WORK/audit.json" 2> "$WORK/audit.txt"
ARC=$?
case "$ARC" in
  0|3) pass "audit completed with exit $ARC" ;;
  *) tail -30 "$WORK/audit.txt"; fail "audit exited $ARC" ;;
esac
python3 -c "
import json
d=json.load(open('$WORK/audit.json'))
assert d['schema'].startswith('cytune-audit/'), d.get('schema')
assert d['risk_set_size'] >= 8, d['risk_set_size']
assert d['n_not_run'] == 0, f\"{d['n_not_run']} risk-set entries could not be gated\"
print(f\"  verdict={d['verdict']} clean={d['n_clean']} reported={d['n_reported']}\")
" || fail "the audit report is not a valid cytune-audit document"
pass "audit gated the whole risk set"

# ---------------------------------------------------------------------------- 5. resume
step 5 "resume — a second run reuses the cache instead of rebuilding"
$CY tune smoke.pyx --driver driver.py --target-ms 5 --preset quick --dry-run \
   > "$WORK/resume.txt" 2>&1
[ $? -eq 0 ] || { tail -20 "$WORK/resume.txt"; fail "the resumed dry run failed"; }
grep -q "cache invalidated" "$WORK/resume.txt" && fail "an unchanged re-run discarded its cache"
pass "an unchanged re-run keeps its cache"

# ---------------------------------------------------------------------------- 6. binding
step 6 "the container-backed binding tests (skipped by a plain pytest run without podman)"
cd "$REPO"
"$REPO/.venv/bin/python" -m pytest -q src/cytune/test_cytune_binding.py \
    > "$WORK/binding.txt" 2>&1 || { tail -30 "$WORK/binding.txt"; fail "the binding tests failed"; }
grep -qE "[0-9]+ passed" "$WORK/binding.txt" || fail "no binding tests ran"
tail -1 "$WORK/binding.txt" | sed 's/^/  /'
pass "artifact binding holds against real Cython and real gcc"

printf '\n\033[32mSMOKE GATE PASSED\033[0m — every subcommand ran end to end on this machine.\n'
