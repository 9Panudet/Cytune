"""P-2 fleet campaign runner (signed A-2, Option A + INT fielded; riders R1-R3 in force).

Order (the human's directive, binding):
  0. Host prep is the HUMAN's step (sudo host_prep.sh + measure_wrap --verify-only PASS). This
     runner REFUSES to start any measurement unless verify-only passes.
  1. --stage controls : re-run the §9.1 controls gate ONCE on the freshly-prepped rig into
     results/fleet/controls (fresh tables; the pilot's gate does NOT carry over). HARD STOP
     (exit 3) if planted or flat fails.
  2. --stage synth    : the 130-kernel synthetic fleet — 30 per confirmatory regime
     (FLAT_FM / MID / LEVER_SEP / INT, indices 6..35, 15/15 FEAS-balanced) + 10 honest-null
     (NULL, indices 6..15). Per slot: emit (generator v2) -> build_phase (plain container,
     CF-1) -> measure_phase (measure_wrap) -> v2 classification (a2_reclassify.reclassify) ->
     ANTI-CLONE acceptance vs accepted same-template kernels (rider R2): on clone, ledger
     REJECTED_CLONE with distances, demote the attempt, re-parameterize (<= 3 attempts, then
     the slot swaps to the next template with unused parameter room). Membership = measured
     v2 class (rider R3); boundary flags (±0.01) and the agreement-watch bit are ledgered.
  3. --stage holdout  : 5 per regime (indices 36..40, generator v2) — H kernels, measured in the
     same campaign, sealed into the H manifest (excluded from P3; P4 acceptance only).
  4. --stage anchors  : Dataset R — the 9 v1 survivors to full 1728 tables (adapters in
     r_anchor.py; csr/pava exist, the other 7 are task #43). R stays in H.
Resumable: a slot attempt with class_v2.json + ACCEPTED ledger entry is skipped; an interrupted
attempt (table without class_v2.json AND without endpoint.json) is deleted+redone for
calibrate-knob consistency (the pilot B_05/C_04 precedent). Every timed row carries the N1 rig
fingerprint (measure_wrap exports it). NO algorithm touches any measured table before the P-2
freeze.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_v2 as g2   # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
IMG = "localhost/motifbo-env:phase1"
REGIMES = ("FLAT_FM", "MID", "LEVER_SEP", "INT")
FLEET_COUNT = 30            # per confirmatory regime, indices 6..35 (PREREG §2 / A-2b)
NULL_COUNT = 10             # honest-null stratum, indices 6..15
HOLDOUT_COUNT = 5           # per regime, indices 36..40
MAX_ATTEMPTS = 3            # anti-clone re-parameterizations per slot before template swap

# --- Amendment A-3 (wave-2 top-up) ---
FLOOR_N = 26                # PREREG §2 per-cell power floor (δ=0.4)
TOPUP_CAP_S = 172800        # A-3d HARD cap: Σ(build_s+measure_s) over wave-2 cycles, 2 days
TOPUP_ORDER = ("FLAT_FM_W2", "MID_W2", "LEVER_SEP_W2")   # A-3d round-robin service order
TOPUP_CELL = {"FLAT_FM_W2": "FLAT+FM", "MID_W2": "MID", "LEVER_SEP_W2": "LEVER-SEP"}
TOPUP_START_INDEX = 50      # clear of fleet 6..35, H 36..40, spares 41+
TOPUP_MAX_SLOTS = 40        # roster length per W2 regime (cap/floors stop the walk first)

# --- Holdout H (human ruling at P-2: ">=15 fresh synthetic, >=3 per confirmatory class
# INCLUDING LEVER-SEP, anti-clone vs everything, sealed from P3") ---
# The original fixed 5-per-INTENDED-regime roster cannot deliver this: membership is MEASURED
# (A-2i) and wave-1 diagonals ran 41-68%, so 5 intended LEVER-SEP kernels yield ~2-3 measured.
# H therefore walks cell-aware, exactly like the top-up, over PRODUCER templates.
H_PER_CELL = 3              # ruling: >= 3 per confirmatory class
H_MIN_TOTAL = 15            # ruling: >= 15 total
# A-7d: FILL PRIORITY, not alphabetical — INT first (it was the structurally impossible cell and
# is the row the P4 product story most needs validated), then FLAT+FM (5 fresh keys pre-A-7), then
# the two cells that already had supply. A-7a: INT and FLAT+FM draw on the EXTENDED registries;
# MID and LEVER-SEP keep their pre-A-7 wave-2 registries untouched.
H_ORDER = ("INT_H", "FLAT_FM_H", "MID_W2", "LEVER_SEP_W2")
H_CELL = {"INT_H": "INT", "FLAT_FM_H": "FLAT+FM", "MID_W2": "MID", "LEVER_SEP_W2": "LEVER-SEP"}
H_START_INDEX = 200         # far clear of fleet (6-35), H-legacy (36-40), spares (41+), W2 (50+)
H_MAX_SLOTS = 30
H_CAP_S = 86400             # A-7d HARD cap: Σ(build_s+measure_s+orphan_s) over ALL holdout
#                             cycles, ANY status, 24 h. Mirrors A-3d exactly, including its
#                             "cap + at most one in-flight cycle" ceiling.


def _verify_rig():
    if subprocess.run(["bash", os.path.join(REPO, "scripts", "measure_wrap.sh"),
                       "--verify-only"]).returncode != 0:
        raise SystemExit("measure_wrap --verify-only FAILED — run host prep first (sudo "
                         "scripts/host_prep.sh); no fleet measurement without a verified rig")


def _run(cmd, log):
    with open(log, "a") as f:
        f.write("\n$ " + " ".join(cmd) + "\n")
        f.flush()
        return subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT).returncode


def _build_cmd(out, kid, configs="all"):
    # kernels live under out/_kernels inside the rw /work mount — calibrate REWRITES the driver's
    # REPS knob, so the kernel dir must NOT be a read-only mount (run_pilot's proven pattern).
    return ["podman", "run", "--rm", "--network=none", "--security-opt", "label=disable",
            "-v", f"{REPO}/scripts:/probe:ro", "-v", f"{REPO}/results:/results:ro",
            "-v", f"{out}:/work", IMG,
            "python3", "/probe/phasep/build_phase.py", f"/work/_kernels/{kid}", f"/work/{kid}",
            configs]


def _measure_cmd(out, kid, target_ms, configs="all"):
    return ["bash", f"{REPO}/scripts/measure_wrap.sh", "--security-opt", "label=disable",
            "-v", f"{REPO}/scripts:/probe:ro", "-v", f"{REPO}/results:/results:ro",
            "-v", f"{out}:/work", IMG,
            "python3", "/probe/phasep/measure_phase.py", f"/work/_kernels/{kid}", f"/work/{kid}",
            configs, "--target-ms", str(target_ms)]


def _classify_v2(out_kdir):
    """v2 classification in the pinned container (numpy parity with the auditors)."""
    rel = os.path.relpath(out_kdir, REPO)
    r = subprocess.run(["podman", "run", "--rm", "--network=none", "--security-opt",
                        "label=disable", "-v", f"{REPO}:/repo:ro", IMG, "python3", "-c",
                        f"import sys, json; sys.path.insert(0, '/repo/scripts/phasep');"
                        f"import a2_reclassify as a2;"
                        f"json.dump(a2.reclassify('/repo/{rel}'), sys.stdout)"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"classify_v2 failed for {out_kdir}: {r.stderr[-400:]}")
    return json.loads(r.stdout)


def _agreement_bit(out_kdir):
    ep = os.path.join(out_kdir, "endpoint.json")
    if not os.path.exists(ep):
        return None
    return json.load(open(ep)).get("agreement_binary_ok")


def _params_duplicate(ledger_path, template, params, trap):
    """D8 efficiency guard: a candidate whose (template, params, trap) EXACTLY equals an already-
    ACCEPTED kernel's (guaranteed clone) or an already-REJECTED_CLONE attempt's (measured evidence
    exists; deterministic re-rejection) is skipped without re-measuring. The measured anti-clone
    check remains the authority for all novel parameterizations."""
    if os.path.exists(ledger_path):
        for l in open(ledger_path):
            e = json.loads(l)
            if (e.get("status") in ("ACCEPTED", "REJECTED_CLONE") and e.get("template") == template
                    and e.get("params") == params and e.get("feas_variant") == trap):
                return True
    return False


def _accepted_props(ledger_path, template):
    """Measured property vectors of ACCEPTED kernels of this template (anti-clone reference set)."""
    out = []
    if os.path.exists(ledger_path):
        for l in open(ledger_path):
            e = json.loads(l)
            if e.get("status") == "ACCEPTED" and e.get("template") == template:
                out.append(tuple(e["p"]))
    return out


_SAN_CORRECTED = None


def _corrected_classes():
    """D23: classes revised after roadmap §1.4 was applied to configs the oracle passed but the
    sanitizer rejects. Loaded once, from the committed overlay."""
    global _SAN_CORRECTED
    if _SAN_CORRECTED is None:
        try:
            import san_overlay
            _SAN_CORRECTED = san_overlay.corrected_classes(os.path.join(REPO, "results", "fleet"))
        except Exception:
            _SAN_CORRECTED = {}
    return _SAN_CORRECTED


_SAN_VOIDED = None


def _voided():
    global _SAN_VOIDED
    if _SAN_VOIDED is None:
        try:
            import san_overlay
            _SAN_VOIDED = san_overlay.voided_kernels(os.path.join(REPO, "results", "fleet"))
        except Exception:
            _SAN_VOIDED = set()
    return _SAN_VOIDED


def _inference_conformant(e):
    """May this kernel's rows enter PER-CLASS INFERENCE? THE single definition.

    Two ways to be out, and they are different facts with the same consequence:
      - `agreement_ok is False` — PREREG §4 verbatim, unconditional, no threshold.
      - the kernel is ENDPOINT-VOIDED (D23 + measurement-auditor F2): every endpoint-measured
        config is one the §1.4 overlay rules infeasible, so the agreement check was performed on a
        landscape that is no longer in feasible space and is NOT EVALUABLE.

    The second is a ruling, and the conservative one. Reading a not-evaluable bit as PASS would let
    a DEFECT increase a cell's n — MID would read 27 and the checkpoint would claim 2 of 4 cells
    powered instead of 1 of 4. A correction that improves our own result is exactly the favourable
    surprise the campaign's discipline says to treat as an alarm. Recorded in DEVIATIONS_REGISTER
    for the human to confirm or overturn."""
    return e.get("agreement_ok") is not False and e.get("kernel_id") not in _voided()


def _cell_of(e):
    """A-2c verbatim, THE single definition of the confirmatory CELL. `measured_v2` never takes
    the literal value "FLAT+FM" (D11) — the FLAT+FM cell is measured-FLAT ∧ flag_FM, and bare
    measured-FLAT is returned as "FLAT" (descriptive-only, counts toward no floor).
    Every consumer imports this; a second copy is how D11 happened.

    D23: where the sanitizer overlay changed a kernel's class, the CORRECTED class wins. The
    ledger is append-only and still carries the uncorrected label — that is deliberate (history is
    evidence), which is exactly why the correction has to be applied here rather than by editing
    the ledger."""
    cls = _corrected_classes().get(e.get("kernel_id"), e.get("measured_v2"))
    return "FLAT+FM" if (cls == "FLAT" and e.get("flag_FM")) else cls


def _cell_counts(ledger_path, holdout=False, conformant=False):
    """A-3a / F2: measured n per confirmatory CELL over ACCEPTED synth non-R rows.
    holdout=False counts the TRAINING set (the A-3 floors); holdout=True counts H (its own
    ≥3-per-cell requirement).

    conformant=True applies PREREG §4 verbatim — "a kernel failing the binary check is flagged
    `agreement_fail`; … at P-2/fleet it is excluded from per-class inference (moved to
    descriptive-only)" — i.e. the INFERENCE set. The rule is unconditional; it has no threshold."""
    counts = {}
    if os.path.exists(ledger_path):
        for l in open(ledger_path):
            e = json.loads(l)
            if (e.get("status") != "ACCEPTED" or bool(e.get("holdout")) != holdout
                    or e.get("dataset", "synthetic") == "R"):
                continue
            if conformant and not _inference_conformant(e):
                continue
            cell = _cell_of(e)
            counts[cell] = counts.get(cell, 0) + 1
    return counts


def _topup_spend(ledger_path):
    """A-3d cap accounting: Σ(build_s + measure_s) over ALL wave-2 ledger rows, ANY status —
    BUILD_FAIL and MEASURE_FAIL cycles burn real rig time and are charged in full. `orphan_s`
    carries the reconciled cost of a cycle whose process was killed before it could ledger
    anything (see _reconcile_inflight)."""
    s = 0.0
    if os.path.exists(ledger_path):
        for l in open(ledger_path):
            e = json.loads(l)
            if e.get("wave") == 2:
                s += (e.get("build_s") or 0) + (e.get("measure_s") or 0) + (e.get("orphan_s") or 0)
    return s


def _h_spend(ledger_path):
    """A-7d cap accounting, the A-3d definition applied to H: Σ(build_s + measure_s + orphan_s)
    over ALL holdout ledger rows, ANY status. Keys on run_kind rather than a wave label because H
    is wave-EXEMPT (A-3b) — its rows carry wave null by construction."""
    s = 0.0
    if os.path.exists(ledger_path):
        for l in open(ledger_path):
            e = json.loads(l)
            if e.get("run_kind") == "holdout":
                s += (e.get("build_s") or 0) + (e.get("measure_s") or 0) + (e.get("orphan_s") or 0)
    return s


def _cap_stop_recorded(ledger_path, status="TOPUP_CAP_STOP"):
    if os.path.exists(ledger_path):
        for l in open(ledger_path):
            if json.loads(l).get("status") == status:
                return True
    return False


def _topup_accepted(ledger_path):
    """Wave-2 acceptances, rebuilt from the append-only ledger (the summary artifact must not be
    a function of which slots THIS launch happened to walk)."""
    out = []
    if os.path.exists(ledger_path):
        for l in open(ledger_path):
            e = json.loads(l)
            if e.get("wave") == 2 and e.get("status") == "ACCEPTED":
                out.append({k: e.get(k) for k in ("slot", "kernel_id", "template",
                                                  "intended_regime", "measured_v2", "flag_FM",
                                                  "flag_FEAS", "holdout", "wave")})
    return out


def _accepted_holdout(ledger_path):
    """H acceptances rebuilt from the append-only ledger (same discipline as _topup_accepted:
    the artifact must not depend on which slots THIS launch happened to walk)."""
    out = []
    if os.path.exists(ledger_path):
        for l in open(ledger_path):
            e = json.loads(l)
            if (e.get("status") == "ACCEPTED" and e.get("holdout")
                    and e.get("dataset", "synthetic") != "R"):
                out.append({k: e.get(k) for k in ("slot", "kernel_id", "template",
                                                  "intended_regime", "measured_v2", "flag_FM",
                                                  "flag_FEAS", "wave", "params", "feas_variant",
                                                  # A-7e: provenance travels with every H artifact
                                                  "provenance")})
    return out


def _inflight_path(out):
    return os.path.join(out, "_topup_inflight.json")


def _inflight_open(out, kid, log):
    with open(_inflight_path(out), "w") as f:
        json.dump({"kernel_id": kid, "t_start": time.time(), "log": log}, f)


def _inflight_close(out):
    p = _inflight_path(out)
    if os.path.exists(p):
        os.remove(p)


def _reconcile_inflight(out, ledger, run_meta):
    """A-3d, death-visible accounting. A cycle killed mid-phase (session limit, host restart, OOM —
    all routine in this campaign) never writes a ledger row, so its compute would be invisible to
    the hard cap and would accumulate without bound across relaunches. Each phase writes its own
    progress artifact CONTINUOUSLY — build_manifest.jsonl one row per compiled config, table.jsonl
    one row per measured config — so the newest mtime among them is a tight LOWER bound on how long
    the dead cycle actually ran (granularity = the phase's own write cadence, sub-minute). That
    bound is ledgered as CYCLE_ORPHAN.orphan_s so the append-only ledger remains the single source
    of truth for spend. Lower bound, not upper: charging wall-clock-to-relaunch would bill idle time
    after an undetected death (wave-1 had one death go ~2 h unnoticed).

    D20: the run log is NOT such an artifact. `_run` writes the "$ podman run …" header, flushes,
    then hands the fd to the child — whose stdout is block-buffered, so nothing more lands until
    the child EXITS. A cycle killed during the BUILD phase therefore left log mtime == t_start and
    charged 0.0 s, and three of the seven wave-2 CYCLE_ORPHAN rows are exactly that. The build's
    real progress signal is build_manifest.jsonl (+ the _so directory as a backstop, since its
    mtime advances as each .so lands)."""
    p = _inflight_path(out)
    if not os.path.exists(p):
        return None
    rec = json.load(open(p))
    t0 = float(rec["t_start"])
    last = t0
    kdir = os.path.join(out, rec["kernel_id"])
    for f in (rec.get("log"),
              os.path.join(kdir, "table.jsonl"),            # measure phase, one row per config
              os.path.join(kdir, "build_manifest.jsonl"),   # D20: build phase, one row per config
              os.path.join(kdir, "_so")):                   # D20 backstop: dir mtime per .so
        if f and os.path.exists(f):
            last = max(last, os.path.getmtime(f))
    orphan_s = round(max(0.0, last - t0), 1)
    ledger.write(json.dumps({"slot": rec["kernel_id"], "kernel_id": rec["kernel_id"],
                             "status": "CYCLE_ORPHAN", "orphan_s": orphan_s,
                             "note": "killed mid-cycle; charged at the last-activity lower bound",
                             **run_meta}) + "\n")
    ledger.flush()
    os.remove(p)
    print(f"[reconcile] {rec['kernel_id']}: CYCLE_ORPHAN charged {orphan_s}s to the A-3d cap")
    return orphan_s


def _topup_open(counts, ptr, roster_lens):
    """Regimes still to serve: cell below floor AND roster not exhausted (A-3d)."""
    return [r for r in TOPUP_ORDER
            if counts.get(TOPUP_CELL[r], 0) < FLOOR_N and ptr[r] < roster_lens[r]]


def _slot_done(ledger_path, slot_kid_prefix):
    if os.path.exists(ledger_path):
        for l in open(ledger_path):
            e = json.loads(l)
            if e.get("slot") == slot_kid_prefix and e.get("status") == "ACCEPTED":
                return e
    return None


def _measure_complete(out_kdir):
    """A measure phase is complete ⇔ finalize wrote class_record.json (the LAST artifact).
    endpoint.json alone is NOT completion — a finalize crash leaves table+endpoint without it."""
    return os.path.exists(os.path.join(out_kdir, "class_record.json"))


def _clean_interrupted(out_kdir):
    """Pilot B_05/C_04 precedent, extended: any measure that did not reach class_record.json
    (mid-screen interrupt OR finalize crash) is deleted and redone under a single fresh calibrate
    context; the cached build is kept."""
    t = os.path.join(out_kdir, "table.jsonl")
    if os.path.exists(t) and not _measure_complete(out_kdir):
        for f in ("table.jsonl", "oracle.json", "golden.npy", "suspicious.json",
                  "endpoint.json", "class_record.json"):
            p = os.path.join(out_kdir, f)
            if os.path.exists(p):
                os.remove(p)
        return True
    return False


def process_slot(kroot, out, ledger, log, run_meta, regime, slot, target_ms, is_holdout=False,
                 attempt_gate=None, cap_status="TOPUP_CAP_DEFERRED"):
    """One roster slot through the acceptance loop. Returns the ACCEPTED ledger entry or None.
    attempt_gate (A-3d/A-7d): called before any candidate that would BUILD/MEASURE (dup-skips and
    resumed-complete candidates are free and never gated); a False return ledgers `cap_status`
    and returns "CAP" so the caller stops the walk mid-slot, not 1-3 measured candidates late."""
    ledger_path = ledger.name
    if is_holdout:
        # A-7e: the provenance label rides on EVERY holdout row this slot writes — accepts,
        # clone rejects, dup-skips, failures and exhaustions alike. The attempt ledger is part of
        # the H supply story, so a row that cost nothing still has to say which registry it came
        # from. Local rebinding: every `**run_meta` below picks it up.
        run_meta = {**run_meta, "provenance": g2.provenance(regime)}
    kid0, name0, params0, trap0, gi = slot
    prior = _slot_done(ledger_path, kid0)
    if prior:
        print(f"[skip accepted] {kid0}")
        return prior
    tmpl_list = g2.REGISTRY[regime]
    order = [t for t in tmpl_list if t[0] == name0] + [t for t in tmpl_list if t[0] != name0]
    attempt = 0
    for name, _pyx, _drv, pspace, feas_ok in order:
        for k in range(min(MAX_ATTEMPTS, len(pspace))):
            params = pspace[(gi + k) % len(pspace)]
            trap = trap0 if (trap0 is None or trap0 in feas_ok) else (feas_ok[0] if feas_ok else None)
            if trap0 is not None and trap is None:
                continue                      # FEAS+ slot needs a FEAS-capable template
            kid = kid0 if attempt == 0 else f"{kid0}_r{attempt}"
            attempt += 1                      # a dup-skip CONSUMES the attempt number so kid↔params
            if _params_duplicate(ledger_path, name, params, trap):   # stays stable across relaunches
                ledger.write(json.dumps({"slot": kid0, "kernel_id": kid,
                                         "status": "PARAMS_DUPLICATE", "template": name,
                                         "params": params, "feas_variant": trap,
                                         **run_meta}) + "\n"); ledger.flush()
                print(f"  {kid}: PARAMS_DUPLICATE ({name} {params}) — skipping measure")
                continue
            g2.emit_kernel(kroot, regime, kid, name, params, trap, gi, holdout=is_holdout)
            # patch: emit under the slot's kid but the template may have swapped — spec records it
            out_kdir = os.path.join(out, kid)
            os.makedirs(out_kdir, exist_ok=True)
            if _clean_interrupted(out_kdir):
                print(f"[resume] {kid}: interrupted measure deleted (build kept)")
            t = {"build_s": None, "measure_s": None}
            if not _measure_complete(out_kdir):
                if attempt_gate is not None and not attempt_gate():
                    ledger.write(json.dumps({"slot": kid0, "kernel_id": kid,
                                             "status": cap_status, "template": name,
                                             **run_meta}) + "\n"); ledger.flush()
                    print(f"  {kid}: {cap_status} (cap reached mid-slot)")
                    return "CAP"
                if attempt_gate is not None:
                    _inflight_open(out, kid, log)     # A-3d: make a killed cycle's cost visible
                # A-3d charges "any status": build_s/measure_s are recorded BEFORE the returncode
                # is inspected, so a failed cycle costs the cap exactly what it burned.
                t0 = time.time()
                rc = _run(_build_cmd(out, kid), log)
                t["build_s"] = round(time.time() - t0, 1)
                if rc != 0:
                    ledger.write(json.dumps({"slot": kid0, "kernel_id": kid, "status": "BUILD_FAIL",
                                             "template": name, **t, **run_meta}) + "\n")
                    ledger.flush(); _inflight_close(out)
                    continue
                t0 = time.time()
                rc = _run(_measure_cmd(out, kid, target_ms), log)
                t["measure_s"] = round(time.time() - t0, 1)
                if rc != 0:
                    ledger.write(json.dumps({"slot": kid0, "kernel_id": kid, "status": "MEASURE_FAIL",
                                             "template": name, **t, **run_meta}) + "\n")
                    ledger.flush(); _inflight_close(out)
                    continue
            v2 = _classify_v2(out_kdir)
            p = g2.property_vector(v2["delta_all"], v2["delta_strict"], v2["if_strict"],
                                   v2["infeasible_frac"], v2["greedy_gap_v1_all_axis"])
            ok, dist = g2.anti_clone_check(p, _accepted_props(ledger_path, name))
            flags = g2.boundary_flags(v2["delta_strict"], v2["if_strict"], v2["fm_ratio"],
                                      round(v2["infeasible_frac"] * 1728), 1728)
            entry = {"slot": kid0, "kernel_id": kid, "template": name, "params": params,
                     "feas_variant": trap, "intended_regime": g2.REGIME_INTENDED[regime],
                     "measured_v2": v2["v2_class"], "flag_FM": v2["flag_FM"],
                     "flag_FEAS": v2["flag_FEAS"], "p": list(p),
                     "boundary_flags": flags, "agreement_ok": _agreement_bit(out_kdir),
                     "holdout": is_holdout, **t, **run_meta}
            with open(os.path.join(out_kdir, "class_v2.json"), "w") as f:
                json.dump({**v2, "boundary_flags": flags,
                           "membership_rule": "A-2i measured full-table"}, f, indent=2)
            if ok:
                entry["status"] = "ACCEPTED"
                ledger.write(json.dumps(entry) + "\n"); ledger.flush()
                _inflight_close(out)      # cost is now on the ledger; nothing left to reconcile
                print(f"  {kid}: v2={v2['v2_class']} FM={v2['flag_FM']} FEAS={v2['flag_FEAS']} "
                      f"flags={flags} ACCEPTED")
                return entry
            entry["status"] = "REJECTED_CLONE"
            entry["clone_distances"] = dist
            ledger.write(json.dumps(entry) + "\n"); ledger.flush()
            _inflight_close(out)
            print(f"  {kid}: REJECTED_CLONE (max|Δ|={max(dist):.4f} < {g2.EPS_CLONE}) — "
                  f"re-parameterizing")
    ledger.write(json.dumps({"slot": kid0, "status": "SLOT_EXHAUSTED", **run_meta}) + "\n")
    ledger.flush()
    print(f"  {kid0}: SLOT_EXHAUSTED (all templates/params tried) — P-2 honest finding")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=["controls", "synth", "holdout", "anchors", "topup"])
    ap.add_argument("--out", default=os.path.join(REPO, "results", "fleet"))
    ap.add_argument("--target-ms", type=float, default=65.0)
    ap.add_argument("--only", default=None, help="single slot kid for smoke/debug")
    ap.add_argument("--deprioritize", default="",
                    help="A-7i: comma-separated regime keys the holdout walk stops SERVING "
                         "(their cells are still counted and reported). Recorded into run_meta so "
                         "every subsequent ledger row carries the allocation regime in force.")
    ap.add_argument("--controls-dir", default="controls",
                    help="controls-gate subdir under --out (A-3e uses controls_a3 so the "
                         "wave-1 gate evidence is never overwritten)")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    kroot = os.path.join(out, "_kernels")
    os.makedirs(kroot, exist_ok=True)
    log = os.path.join(out, "run_fleet.log")
    _verify_rig()
    run_meta = {"run_id": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
                "run_kind": {"controls": "fleet-controls", "synth": "fleet", "holdout": "holdout",
                             "anchors": "anchors", "topup": "fleet-topup"}[a.stage]}
    if a.stage == "topup":
        run_meta["wave"] = 2                      # A-3b: wave label on every wave-2 ledger row
    deprioritized = tuple(x for x in a.deprioritize.split(",") if x)
    if deprioritized:
        # A-7i: the allocation regime rides on every row this launch writes, so an auditor can
        # recover WHICH cells were being served when any given row was produced — from the ledger
        # alone, without reconstructing launch commands from shell history.
        bad = [r for r in deprioritized if r not in g2.REGISTRY]
        if bad:
            raise SystemExit(f"--deprioritize: unknown regime key(s) {bad}")
        run_meta["deprioritized"] = list(deprioritized)

    if a.stage == "controls":
        # fresh §9.1 re-gate on the prepped rig — reuse run_pilot's gate against a FRESH out dir
        import run_pilot
        cdir = os.path.join(out, a.controls_dir)
        os.makedirs(cdir, exist_ok=True)
        ledger = open(os.path.join(out, "fleet_ledger.jsonl"), "a")
        ok = run_pilot.controls_gate(cdir, "measure_wrap", a.target_ms, ledger, log)
        ledger.close()
        sys.exit(0 if ok else 3)

    ledger = open(os.path.join(out, "fleet_ledger.jsonl"), "a")
    # topup (A-3e) gates on the FRESH controls_a3 re-verify; earlier stages on the wave-1 gate.
    # A-4 resume: an EXPLICIT --controls-dir also selects the dir a run gates ON, so each resume
    # can re-gate into its own directory instead of overwriting a previous gate's committed
    # evidence. Omitting the flag preserves the prior behaviour exactly.
    gate_dir = a.controls_dir if a.controls_dir != "controls" else \
        ("controls_a3" if a.stage == "topup" else "controls")
    if not os.path.exists(os.path.join(out, gate_dir, "controls_gate.json")):
        raise SystemExit(f"controls re-gate has not PASSED in results/fleet/{gate_dir} — run "
                         f"--stage controls --controls-dir {gate_dir} first (HARD gate)")
    gate = json.load(open(os.path.join(out, gate_dir, "controls_gate.json")))
    if not (gate.get("planted", {}).get("ok") and gate.get("flat", {}).get("ok")):
        raise SystemExit("controls re-gate recorded FAIL — HARD STOP")

    if a.stage == "anchors":
        # Dataset R: all 9 v1 survivors to full 1728 tables (A-2b; R stays in holdout H). Real
        # code — no anti-clone loop (that is a generator discipline); measured v2 class recorded.
        import r_anchor
        summary = []
        for i, ak in enumerate(r_anchor.ALL_NINE, 1):
            kid = f"fleet_R_{i:02d}_{ak}"
            if a.only and kid != a.only:
                continue
            if _slot_done(ledger.name, kid):
                print(f"[skip accepted] {kid}")
                continue
            r_anchor.build_anchor(kroot, ak, kid, repo_root=REPO)
            out_kdir = os.path.join(out, kid)
            os.makedirs(out_kdir, exist_ok=True)
            if _clean_interrupted(out_kdir):
                print(f"[resume] {kid}: interrupted measure deleted (build kept)")
            t = {"build_s": None, "measure_s": None}
            if not _measure_complete(out_kdir):
                t0 = time.time()
                if _run(_build_cmd(out, kid), log) != 0:
                    ledger.write(json.dumps({"slot": kid, "kernel_id": kid, "status": "BUILD_FAIL",
                                             "anchor": ak, **run_meta}) + "\n"); ledger.flush()
                    continue
                t["build_s"] = round(time.time() - t0, 1)
                t0 = time.time()
                if _run(_measure_cmd(out, kid, a.target_ms), log) != 0:
                    ledger.write(json.dumps({"slot": kid, "kernel_id": kid, "status": "MEASURE_FAIL",
                                             "anchor": ak, **run_meta}) + "\n"); ledger.flush()
                    continue
                t["measure_s"] = round(time.time() - t0, 1)
            v2 = _classify_v2(out_kdir)
            flags = g2.boundary_flags(v2["delta_strict"], v2["if_strict"], v2["fm_ratio"],
                                      round(v2["infeasible_frac"] * 1728), 1728)
            with open(os.path.join(out_kdir, "class_v2.json"), "w") as f:
                json.dump({**v2, "boundary_flags": flags,
                           "membership_rule": "A-2i measured full-table"}, f, indent=2)
            entry = {"slot": kid, "kernel_id": kid, "anchor": ak, "status": "ACCEPTED",
                     "dataset": "R", "holdout": True, "measured_v2": v2["v2_class"],
                     "flag_FM": v2["flag_FM"], "flag_FEAS": v2["flag_FEAS"],
                     "boundary_flags": flags, "agreement_ok": _agreement_bit(out_kdir),
                     **t, **run_meta}
            ledger.write(json.dumps(entry) + "\n"); ledger.flush()
            summary.append(entry)
            print(f"  {kid}: v2={v2['v2_class']} FM={v2['flag_FM']} FEAS={v2['flag_FEAS']}")
            with open(os.path.join(out, "anchors_summary.json"), "w") as f:
                json.dump(summary, f, indent=2)
        ledger.close()
        print(f"\nanchors stage complete: {len(summary)} measured")
        return

    if a.stage == "topup":
        # Amendment A-3d: one slot per turn cycling TOPUP_ORDER, skipping cells already at
        # >= FLOOR_N (measured CELLS, F2: FLAT+FM = FLAT ∧ flag_FM); HARD stop at the cap
        # regardless of floors. Resumable: counts/spend/skips all re-derive from the ledger.
        _reconcile_inflight(out, ledger, run_meta)   # charge any cycle killed by a prior launch
        rosters = {r: g2.roster(r, TOPUP_MAX_SLOTS, start_index=TOPUP_START_INDEX)
                   for r in TOPUP_ORDER}
        ptr = {r: 0 for r in TOPUP_ORDER}
        lens = {r: len(rosters[r]) for r in TOPUP_ORDER}
        turn = 0

        def _cap_gate():
            return _topup_spend(ledger.name) < TOPUP_CAP_S

        def _write_summary():
            with open(os.path.join(out, "topup_summary.json"), "w") as f:
                json.dump(_topup_accepted(ledger.name), f, indent=2)

        while True:
            counts = _cell_counts(ledger.name)
            cells_now = {c: counts.get(c, 0) for c in TOPUP_CELL.values()}
            # The CAP is evaluated BEFORE roster state: a stop caused by the cap must never be
            # recorded as "rosters exhausted" (the two have very different meanings at P-2).
            spend = _topup_spend(ledger.name)
            if spend >= TOPUP_CAP_S:
                if not _cap_stop_recorded(ledger.name):
                    ledger.write(json.dumps({"status": "TOPUP_CAP_STOP", "spend_s": round(spend, 1),
                                             "cap_s": TOPUP_CAP_S, "cells": cells_now,
                                             **run_meta}) + "\n"); ledger.flush()
                print(f"topup: TOPUP_CAP_STOP at {spend:.0f}s >= {TOPUP_CAP_S}s — "
                      f"honest final-n stands (A-3d), cells {cells_now}")
                break
            open_r = _topup_open(counts, ptr, lens)
            if not open_r:
                print(f"topup: floors met or rosters exhausted — cells {cells_now}")
                break
            while TOPUP_ORDER[turn % len(TOPUP_ORDER)] not in open_r:
                turn += 1
            regime = TOPUP_ORDER[turn % len(TOPUP_ORDER)]
            turn += 1
            slot = rosters[regime][ptr[regime]]
            ptr[regime] += 1
            if a.only and slot[0] != a.only:
                continue
            print(f"[topup] {slot[0]} — cell {TOPUP_CELL[regime]} at "
                  f"{cells_now[TOPUP_CELL[regime]]}/{FLOOR_N}, wave-2 spend {spend / 3600:.2f}h")
            process_slot(kroot, out, ledger, log, run_meta, regime, slot, a.target_ms,
                         attempt_gate=_cap_gate)
            _write_summary()
        _write_summary()
        summary = _topup_accepted(ledger.name)
        ledger.close()
        final = _cell_counts(os.path.join(out, "fleet_ledger.jsonl"))
        print(f"\ntopup stage complete: {len(summary)} accepted; cells "
              f"{ {c: final.get(c, 0) for c in TOPUP_CELL.values()} }")
        return

    if a.stage == "holdout":
        # Cell-aware H walk. Stop when EVERY confirmatory cell has >= H_PER_CELL and the total is
        # >= H_MIN_TOTAL, or at the A-7d cap, or when supply is exhausted (reported honestly — a
        # cell that cannot fill is a P-2 finding, never tuned away). H is sealed: holdout=True on
        # every row.
        #
        # A-7d FILL PRIORITY — the reading, recorded (the directive's phrasing admits a stricter
        # one). "INT >=3 first, then FLAT+FM >=3, then MID and LEVER-SEP" is implemented as
        # SERVICE ORDER within the round-robin over cells still under floor (H_ORDER puts INT_H
        # first, FLAT_FM_H second), NOT as strict pre-emption. Strict pre-emption would let a
        # structurally unfillable cell — exactly the A-7f scenario the amendment anticipates for
        # INT — consume the whole 86,400 s and leave MID and LEVER-SEP at zero, which is strictly
        # worse than the pre-A-7 state. Round-robin-within-under-floor is A-3d's own allocation
        # rule and its stated rationale ("maximizes worst-case balance at a cap-stop"); A-6 left it
        # untouched and so does this. If the human intended strict pre-emption, it is a one-line
        # change here and this comment is the place it is recorded.
        _reconcile_inflight(out, ledger, run_meta)   # charge any H cycle killed by a prior launch
        if deprioritized:
            print(f"[A-7i] DEPRIORITIZED (served no further, still counted+reported): "
                  f"{list(deprioritized)}")
        rosters = {r: g2.roster(r, H_MAX_SLOTS, start_index=H_START_INDEX) for r in H_ORDER}
        ptr = {r: 0 for r in H_ORDER}
        lens = {r: len(rosters[r]) for r in H_ORDER}
        turn = 0

        def _h_cap_gate():
            return _h_spend(ledger.name) < H_CAP_S

        while True:
            hc = _cell_counts(ledger.name, holdout=True)
            cells_now = {c: hc.get(c, 0) for c in H_CELL.values()}
            total = sum(cells_now.values())
            # The CAP is evaluated BEFORE roster state (A-3d discipline): a stop caused by the cap
            # must never be recorded as "supply exhausted" — at P-2 those mean opposite things.
            spend = _h_spend(ledger.name)
            if spend >= H_CAP_S:
                if not _cap_stop_recorded(ledger.name, "H_CAP_STOP"):
                    ledger.write(json.dumps({"status": "H_CAP_STOP", "spend_s": round(spend, 1),
                                             "cap_s": H_CAP_S, "cells": cells_now,
                                             "total": total, **run_meta}) + "\n"); ledger.flush()
                print(f"holdout: H_CAP_STOP at {spend:.0f}s >= {H_CAP_S}s — honest final-n "
                      f"stands (A-7d), cells {cells_now} total {total}")
                break
            # A-7i: a deprioritized regime is dropped from SERVING only. Its cell stays in
            # `cells_now` and in every count and report — the shortfall is reported as measured.
            need = [r for r in H_ORDER
                    if r not in deprioritized
                    and (cells_now[H_CELL[r]] < H_PER_CELL
                         or total < H_MIN_TOTAL) and ptr[r] < lens[r]]
            if not need:
                short = {c: n for c, n in cells_now.items() if n < H_PER_CELL}
                # Three ways a cell can end short and they are NOT the same finding:
                # deprioritized (A-7i allocation ruling), supply-exhausted (roster spent), or
                # cap-stopped (handled above, before roster state). Reporting a deprioritized cell
                # as "supply exhausted" would attribute a human allocation decision to the data.
                dep_cells = {H_CELL[r] for r in deprioritized if r in H_CELL}
                by_dep = {c: n for c, n in short.items() if c in dep_cells}
                by_supply = {c: n for c, n in short.items() if c not in dep_cells}
                msg = f"holdout: stop — cells {cells_now} total {total}"
                if not short:
                    msg += f" (>= {H_PER_CELL}/cell, >= {H_MIN_TOTAL} total: MET)"
                if by_supply:
                    msg += f"; SHORT (supply exhausted): {by_supply} — honest P-2 finding"
                if by_dep:
                    msg += (f"; SHORT (A-7i DEPRIORITIZED, not supply): {by_dep} — the human "
                            f"allocation ruling, reported as measured")
                print(msg)
                break
            # prefer a cell that is still under its per-cell floor over merely topping up the total
            under = [r for r in need if cells_now[H_CELL[r]] < H_PER_CELL]
            pool = under or need
            while H_ORDER[turn % len(H_ORDER)] not in pool:
                turn += 1
            regime = H_ORDER[turn % len(H_ORDER)]
            turn += 1
            slot = rosters[regime][ptr[regime]]
            ptr[regime] += 1
            if a.only and slot[0] != a.only:
                continue
            print(f"[holdout] {slot[0]} — cell {H_CELL[regime]} at "
                  f"{cells_now[H_CELL[regime]]}/{H_PER_CELL}, total {total}/{H_MIN_TOTAL}, "
                  f"{g2.provenance(regime)}, H spend {spend / 3600:.2f}h/{H_CAP_S / 3600:.0f}h")
            process_slot(kroot, out, ledger, log, run_meta, regime, slot, a.target_ms,
                         is_holdout=True, attempt_gate=_h_cap_gate,
                         cap_status="H_CAP_DEFERRED")
            with open(os.path.join(out, "holdout_summary.json"), "w") as f:
                json.dump([e for e in _accepted_holdout(ledger.name)], f, indent=2)
        lpath = os.path.join(out, "fleet_ledger.jsonl")
        ledger.close()
        final = _cell_counts(lpath, holdout=True)
        cells = {c: final.get(c, 0) for c in H_CELL.values()}
        acc = _accepted_holdout(lpath)
        prov = {}
        for e in acc:
            prov[e.get("provenance")] = prov.get(e.get("provenance"), 0) + 1
        print(f"\nholdout stage complete: cells {cells} total {sum(cells.values())} "
              f"(>= {H_PER_CELL}/cell, >= {H_MIN_TOTAL} total required)")
        print(f"  provenance (A-7e): {prov}")
        print(f"  H spend: {_h_spend(lpath):.0f}s / {H_CAP_S}s cap (A-7d)")
        short = {c: n for c, n in cells.items() if n < H_PER_CELL}
        if short:
            # A-7f/A-7i: a cell that will not fill is REPORTED with its attempt ledger, never
            # iterated — but the CAUSE must be attributed correctly. A cell the walk stopped
            # serving by human ruling is not evidence about supply.
            dep_cells = {H_CELL[r] for r in deprioritized if r in H_CELL}
            by_dep = {c: n for c, n in short.items() if c in dep_cells}
            by_supply = {c: n for c, n in short.items() if c not in dep_cells}
            if by_supply:
                print(f"  SHORT (supply/cap): {by_supply} — honest P-2 finding. A-7c forbids a "
                      f"second extension; if INT is among these, report it as the STRUCTURAL "
                      f"FINDING of A-7f (the INT-producing parameter region is narrow) with the "
                      f"full attempt ledger.")
            if by_dep:
                print(f"  SHORT (A-7i DEPRIORITIZED — human allocation ruling, NOT supply): "
                      f"{by_dep}. Counted and reported as measured; must never be presented as "
                      f"supply exhaustion.")
        return

    summary = []
    if a.stage == "synth":
        plan = [(r, g2.roster(r, FLEET_COUNT, start_index=6)) for r in REGIMES]
        plan.append(("NULL", g2.roster("NULL", NULL_COUNT, feas_balance=False, start_index=6)))
    else:
        plan = []
    for regime, slots in plan:
        for slot in slots:
            if a.only and slot[0] != a.only:
                continue
            e = process_slot(kroot, out, ledger, log, run_meta, regime, slot, a.target_ms,
                             is_holdout=(a.stage == "holdout"))
            if e:
                summary.append({k: e[k] for k in ("slot", "kernel_id", "template",
                                                  "intended_regime", "measured_v2", "flag_FM",
                                                  "flag_FEAS", "holdout")})
            with open(os.path.join(out, f"{a.stage}_summary.json"), "w") as f:
                json.dump(summary, f, indent=2)
    ledger.close()
    print(f"\n{a.stage} stage complete: {len(summary)} accepted")


if __name__ == "__main__":
    main()
