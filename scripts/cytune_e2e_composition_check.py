#!/usr/bin/env python3
"""Composition-level E2E regression checks for D13 and D14 (cytune v0).

WHY THIS IS NOT A pytest. Both defects are properties of the WHOLE PIPELINE's output, and both
were invisible to unit tests of the parts: every component was individually correct and the
composition was dishonest. Reproducing them needs a real run, which spawns podman — so this runs on
the HOST (the pinned images have no podman and no git), unlike src/cytune/test_cytune_*.py which
run inside the container.

Each check runs in BOTH directions:
  green — the current pipeline's real certificate satisfies the property;
  red   — a reconstructed PRE-FIX certificate violates it, proving the check discriminates.
A check that only ever ran green would pass just as happily against the defective code.

Usage:
  python3 scripts/cytune_e2e_composition_check.py            # live E2E (re-runs the CLI)
  python3 scripts/cytune_e2e_composition_check.py --artifacts-only
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(REPO, "src"))

from cytune import certify, routing                      # noqa: E402
from cytune._phasep import theta                         # noqa: E402

WS = os.path.join(REPO, "results", "cli_v0", "ws")
CASES = [
    # (name, module, driver) — a flat kernel (exercises D13) and one that tunes (exercises D14)
    ("pilot_C_01",
     "results/pilot/_kernels/pilot_C_01/kernel.pyx",
     "results/pilot/_kernels/pilot_C_01/driver.py"),
    ("toy_running_max",
     "src/cytune/examples/running_max.pyx",
     "src/cytune/examples/running_max_driver.py"),
]

FP_AFFECTING = ("-ffp-contract=fast", "-ffast-math")
_fails = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        _fails.append(label)
    return ok


# --------------------------------------------------------------------- the properties
def prop_flat_emits_reference(cert):
    """D13: a flat/honest-flat verdict must emit the REFERENCE — no probe-minimum leakage."""
    if cert["routing"]["route"] != routing.HONEST_FLAT:
        return None, "not a flat route"
    emitted = (cert.get("emitted_config") or {}).get("config_id")
    if cert["verdict"] != "honest-flat":
        return False, f"flat route produced verdict={cert['verdict']}"
    if emitted != theta.REFERENCE_ID:
        return False, f"flat route emitted config {emitted}, not the reference {theta.REFERENCE_ID}"
    return True, f"verdict=honest-flat, emitted=reference({theta.REFERENCE_ID})"


def prop_fp_flags_disclosed(cert, rendered):
    """D14: every FP-semantics-affecting flag actually emitted must be disclosed in the text."""
    e = cert.get("emitted_config")
    if not e:
        return None, "nothing emitted"
    flags = e.get("gcc_flags", "")
    affecting = [f for f in FP_AFFECTING if f in flags]
    if not affecting:
        return None, f"no value-affecting FP flag emitted ({flags})"
    if "FLOATING-POINT SEMANTICS" not in rendered and "fast-math" not in rendered.lower():
        return False, f"emitted {affecting} with NO disclosure in the certificate"
    if "-ffp-contract=fast" in affecting and not (cert.get("fp_semantics") or {}).get(
            "fma_contraction_permitted"):
        return False, "-ffp-contract=fast emitted but fp_semantics does not flag contraction"
    return True, f"disclosed: {affecting}"


def prop_no_orchestration_rejection(cert):
    """D18: a winner may be refused by the ORACLE, never because we forgot to build it.

    `confirm_winner` refusing is a correctness feature. But a refusal whose reason is `not_built`
    means the verify stage was handed a config the pipeline never compiled — an orchestration bug
    that silently degrades a real speedup to honest-flat while looking like a safety event.
    """
    wr = cert.get("winner_rejection")
    if not wr:
        return None, "no winner was rejected in this run"
    reason = str(wr.get("reason", ""))
    if "not_built" in reason:
        return False, f"winner {wr.get('rejected_config_id')} refused for {reason} — orchestration"
    return True, f"refusal was a genuine oracle/measurement event: {reason}"


# --------------------------------------------------------------------- red controls
def red_control_d13(cert):
    """Reconstruct the PRE-FIX D13 behaviour: on the flat route, emit the probe minimum anyway."""
    obs = cert.get("flat_observation")
    if not obs or not obs.get("config_id"):
        return None, "no probe-minimum recorded for this run; cannot reconstruct"
    ep = {str(theta.REFERENCE_ID): {"feasible": True,
                                    "endpoint_ns": cert["measurement"]["reference_endpoint_ns"],
                                    "subs_ns": cert["measurement"]["reference_subs_ns"]},
          str(obs["config_id"]): {"feasible": True, "endpoint_ns": obs["endpoint_ns"],
                                  "subs_ns": [obs["endpoint_ns"]] * 3}}
    prefix = certify.build_certificate(
        name=cert["module"], winner_id=obs["config_id"], reference_id=theta.REFERENCE_ID,
        endpoint=ep, oracle={"output_class": "float", "tolerance": {}, "deterministic": True,
                             "n_det_reps": 5, "golden_sha256": "x"},
        feasibility={"n_measured": 0, "n_infeasible": 0, "infeasible_fraction": None, "reasons": {}},
        route=cert["routing"], rig_mode="quiesced", rig_detail="q", budget={},
        sources=cert["sources"], allow_fast_math=False)
    ok, detail = prop_flat_emits_reference(prefix)
    return ok, detail


def red_control_d14(cert, rendered):
    """Reconstruct the PRE-FIX D14 behaviour: strip the FP-semantics disclosure from the text."""
    e = cert.get("emitted_config")
    if not e or not any(f in e.get("gcc_flags", "") for f in FP_AFFECTING):
        return None, "this run emitted no value-affecting FP flag"
    stripped = "\n".join(l for l in rendered.splitlines()
                         if "FLOATING-POINT SEMANTICS" not in l
                         and "-ffp-contract" not in l
                         and "fast-math" not in l.lower()
                         and "contract" not in l.lower())
    blind = json.loads(json.dumps(cert))
    blind["fp_semantics"] = {"fma_contraction_permitted": False}
    ok, detail = prop_fp_flags_disclosed(blind, stripped)
    return ok, detail


# --------------------------------------------------------------------- driver
def run_live(name, module, driver):
    cmd = [sys.executable, "-m", "cytune", "tune", os.path.join(REPO, module),
           "--driver", os.path.join(REPO, driver), "--workspace", WS, "--name", name]
    env = {**os.environ, "PYTHONPATH": os.path.join(REPO, "src")}
    r = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:]); print(r.stderr[-2000:])
        raise SystemExit(f"live run failed for {name} (rc={r.returncode})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts-only", action="store_true",
                    help="validate committed certificates without re-running the pipeline")
    a = ap.parse_args()

    print("cytune composition-level E2E checks (D13, D14)")
    print("=" * 70)
    for name, module, driver in CASES:
        if not a.artifacts_only:
            print(f"\n[live] {name} — running the full pipeline ...")
            run_live(name, module, driver)
        cdir = os.path.join(WS, name)
        cert = json.load(open(os.path.join(cdir, "certificate.json")))
        rendered = open(os.path.join(cdir, "certificate.txt")).read()
        print(f"\n{name}  (route={cert['routing']['route']}, verdict={cert['verdict']})")

        ok, detail = prop_flat_emits_reference(cert)
        if ok is None:
            print(f"  [skip] D13 flat-emits-reference — {detail}")
        else:
            check(f"D13 GREEN  {name}: flat verdict emits the reference", ok, detail)
            red, rdetail = red_control_d13(cert)
            if red is None:
                print(f"  [skip] D13 red control — {rdetail}")
            else:
                check(f"D13 RED    {name}: pre-fix behaviour is CAUGHT", red is False, rdetail)

        ok, detail = prop_no_orchestration_rejection(cert)
        if ok is None:
            print(f"  [skip] D18 no-orchestration-rejection — {detail}")
        else:
            check(f"D18 GREEN  {name}: winner refusals are oracle events, not build gaps", ok, detail)
        # red control is unconditional: the property must catch a planted not_built refusal
        planted = dict(cert)
        planted["winner_rejection"] = {"rejected_config_id": 1294, "reason": "not_built: None",
                                       "action": "fell back to the reference configuration"}
        red, rdetail = prop_no_orchestration_rejection(planted)
        check(f"D18 RED    {name}: a not_built refusal is CAUGHT", red is False, rdetail)

        ok, detail = prop_fp_flags_disclosed(cert, rendered)
        if ok is None:
            print(f"  [skip] D14 fp-disclosure — {detail}")
        else:
            check(f"D14 GREEN  {name}: emitted FP flags are disclosed", ok, detail)
            red, rdetail = red_control_d14(cert, rendered)
            if red is None:
                print(f"  [skip] D14 red control — {rdetail}")
            else:
                check(f"D14 RED    {name}: undisclosed FP flag is CAUGHT", red is False, rdetail)

    print("\n" + "=" * 70)
    if _fails:
        print(f"COMPOSITION CHECKS FAILED ({len(_fails)}): {_fails}")
        return 1
    print("ALL COMPOSITION CHECKS PASSED (green on current code, red on reconstructed pre-fix)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
