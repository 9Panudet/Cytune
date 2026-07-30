"""cytune CLI — ingest -> probe -> route -> tune -> verify -> certify (roadmap §8.1).

Host-side orchestration only: this process spawns containers and parses one JSON line back from
each. All numeric and measured work happens inside the pinned image, exactly as run_pilot.py does
it for the study.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time

from . import certify, rig, routing, sanitize_gate
from .doctor import doctor
from .plan import confirm_winner, select_winner
from .session import IngestError, Session
from . import __version__


def _say(msg=""):
    print(msg, flush=True)


def _feasibility_stats(rows):
    n = len(rows)
    infeas = [r for r in rows.values() if not r.get("feasible")]
    reasons = {}
    for r in infeas:
        reasons[r.get("reason") or "unknown"] = reasons.get(r.get("reason") or "unknown", 0) + 1
    return {"n_measured": n, "n_infeasible": len(infeas),
            "infeasible_fraction": (len(infeas) / n) if n else None,
            "reasons": reasons}


def tune(args):
    t_start = time.time()
    name = args.name or os.path.splitext(os.path.basename(args.module))[0]
    workspace = os.path.abspath(args.workspace)

    mode, detail = (rig.PORTABLE, "forced by --rig portable") if args.rig == "portable" \
        else rig.probe_rig()
    _say(f"cytune v0 — {name}")
    _say(f"  rig mode: {mode} ({detail})")
    _say(f"  {routing.LABEL}")
    _say()

    sess = Session(workspace, name, mode, detail, target_ms=args.target_ms)

    # ---------------------------------------------------------------- 1. ingest
    _say("[1/6] ingest — vendoring module + driver")
    src = sess.vendor(args.module, args.driver)
    _say(f"      {src['pyx']}")
    _say(f"      {src['driver']}")
    _say("      building the reference config + probe design ...")
    b = sess.build("probe")
    n_built = sum(1 for v in b["built"].values() if v)
    _say(f"      built {n_built}/{len(b['built'])} configs"
         + (f"; {len(b['failed'])} failed to compile" if b.get("failed") else ""))
    _say("      capturing golden output + deriving the oracle ...")
    g = sess.golden()
    orc = g["oracle"]
    _say(f"      oracle: class={orc['output_class']} deterministic={orc['deterministic']} "
         f"tolerance={json.dumps(orc['tolerance'])}")
    if g.get("calibrated"):
        c = g["calibrated"]
        _say(f"      calibrated {c['knob']}: {c['cur']} -> {c['new']} (reference ~{args.target_ms} ms)")
    else:
        _say("      no REPS/SCALE knob in the driver — measuring the workload as written")

    # ----------------------------------------------------------------- 2. probe
    _say()
    _say("[2/6] probe — pre-registered 16-config screen (PREREG §9.2)")
    sess.measure("probe")
    feat = sess.features()["features"]
    _say(f"      feasible {feat['n_probe_feasible']}/{feat['n_probe_attempted']} "
         f"({feat['feas_frac']:.1%})")
    _say(f"      delta_probe = {_fmt(feat['delta_probe'])}   "
         f"IF_probe = {'NA (degenerate)' if feat['if_probe_na'] else _fmt(feat['if_probe'])}")
    sig = feat["interim_signals"]
    if sig.get("fm_signal") and sig["fm_signal"] > 1.02:
        _say(f"      [interim signal] fast-math configs looked {sig['fm_signal']:.3f}x faster in "
             f"the probe. NOT claimed: they have not been accepted for correctness here.")
        if not args.allow_fast_math:
            _say("      re-run with --allow-fast-math to have them oracle-checked.")

    # ----------------------------------------------------------------- 3. route
    _say()
    _say("[3/6] route")
    route = routing.route(feat, bo_available=False)
    _say(f"      rule {route['rule']} -> {route['route']}"
         + (f" (engine {route['engine']}, budget {route['budget']})" if route["engine"] else ""))
    _say(f"      {route['why']}")
    if route.get("fallback_note"):
        _say(f"      NOTE: {route['fallback_note']}")
    if route.get("feasibility_note"):
        _say(f"      NOTE: {route['feasibility_note']}")

    if route["route"] == routing.ABORT:
        _say()
        _say(f"ABORT: {route['why']}")
        return 2

    # ------------------------------------------------------------------ 4. tune
    _say()
    _say("[4/6] tune")
    tuned = 0
    if route["route"] == routing.HONEST_FLAT:
        _say("      skipped — the probe says this landscape is flat. Spending a tuning budget "
             "here would buy noise.")
    else:
        sp = sess.screen_plan(route["budget"])
        _say(f"      {route['engine']} screen: design {sp['design_key']}, {len(sp['ids'])} configs")
        if sp["ids"]:
            sess.build(sp["ids"])
            sess.measure(sp["ids"])
            tuned += len(sp["ids"])
        remaining = route["budget"] - tuned
        if remaining > 0:
            wp = sess.walk_plan(remaining, allow_fast_math=args.allow_fast_math)
            if wp["ids"]:
                _say(f"      predicted-best walk: {len(wp['ids'])} configs"
                     + (f" ({wp['fit']['fast_math_skipped']} fast-math skipped)"
                        if wp.get("fit") and wp["fit"].get("fast_math_skipped") else ""))
                sess.build(wp["ids"])
                sess.measure(wp["ids"])
                tuned += len(wp["ids"])
        _say(f"      measured {tuned} additional configs")

    # ---------------------------------------------------------------- 5. verify
    _say()
    _say("[5/6] verify — endpoint tier on the winner + the reference")
    rows = sess.table_rows()
    feas = sess.feasible_medians()
    stats = _feasibility_stats(rows)
    ref_id = certify.theta.REFERENCE_ID
    observed, wdetail = select_winner(feas, allow_fast_math=args.allow_fast_math)
    flat_observation = None
    if route["route"] == routing.HONEST_FLAT and observed is not None and observed != ref_id:
        # The route declined to tune. Emitting a "winner" spotted incidentally in the probe would
        # contradict that decision inside the same document, and it is exactly the selection-biased
        # claim R1 exists to refuse: the best of 17 probe configs is biased low on a flat landscape.
        # We still MEASURE it at the endpoint so the user gets a real number — we just do not
        # recommend acting on it. (Defect found by smoke run 2, pilot_C_01.)
        flat_observation = {"config_id": observed}
        winner = ref_id
    else:
        winner = observed

    if winner is None:
        _say("      no feasible config at all — nothing can be certified")
        cert = certify.build_certificate(
            name=name, winner_id=None, reference_id=ref_id, endpoint={}, oracle=orc,
            feasibility=stats, route=route, rig_mode=mode, rig_detail=rig.certificate_line(mode, detail),
            budget={"probe": feat["n_probe_attempted"], "tuning": tuned, "total_measured": stats["n_measured"]},
            sources={"table": sess.table_path, "workspace": sess.workspace},
            allow_fast_math=args.allow_fast_math)
    else:
        verify_ids = sorted({winner, ref_id} | ({observed} if flat_observation else set()))
        # Guarantee the verify stage's own inputs exist before measuring them. table.jsonl persists
        # across runs, so the winner can be a config measured by an EARLIER run whose .so has since
        # been pruned; without this the endpoint reports not_built, the winner is (correctly)
        # refused, and a real speedup silently degrades to honest-flat. Build is idempotent. (D18)
        sess.build(verify_ids)
        ep = sess.endpoint(verify_ids)["endpoints"]
        _say(f"      re-measured {len(verify_ids)} configs at K=30, median-of-3")
        if flat_observation:
            obs_ep, ref_ep = ep.get(str(observed), {}), ep.get(str(ref_id), {})
            ratio = ((ref_ep.get("endpoint_ns") / obs_ep["endpoint_ns"])
                     if obs_ep.get("endpoint_ns") and ref_ep.get("endpoint_ns") else None)
            flat_observation.update({
                "endpoint_ratio_vs_reference": ratio,
                "endpoint_ns": obs_ep.get("endpoint_ns"),
                "feasible": obs_ep.get("feasible"),
                "note": ("measured but NOT recommended: the routing rule classified this landscape "
                         "as flat, so this config is the best of the probe sample rather than the "
                         "result of a tuning search. Picking the minimum of a sample biases it low "
                         "on a flat landscape, so cytune reports it and declines to act on it.")})
            _say(f"      [observation, not a recommendation] the fastest probe config "
                 f"({observed}) measured {ratio:.4f}x vs the reference"
                 if ratio else "      [observation] fastest probe config did not confirm")
        winner, rejection = confirm_winner(winner, ref_id, ep)
        # §1.4 SANITIZER GATE on the config actually about to be emitted (D23 / validation-auditor
        # F2). The oracle is an OUTPUT check and cannot see a read that produced a correct answer;
        # that is exactly how 1,296 out-of-bounds configs were recorded feasible in the study. A
        # report here makes the config infeasible and cytune falls back to the reference, same as
        # for an oracle failure. A gate that could not RUN is recorded as not-run, never as a pass.
        san = None
        if winner is not None and winner != ref_id and not rejection:
            _say("      §1.4 sanitizer gate on the emitted config (ASan+UBSan)")
            san = sanitize_gate.gate(sess.kdir, winner)
            if sanitize_gate.rejects(san):
                _say(f"      WINNER REJECTED by the sanitizer: config {winner} — "
                     f"{', '.join(san.get('tokens') or [])}")
                _say("      the oracle passed it; ASan did not. Correctness absolute — "
                     "a config that reports is never emitted.")
                rejection = {"rejected_config_id": winner,
                             "reason": f"sanitizer_report: {', '.join(san.get('tokens') or [])}",
                             "action": "fell back to the reference config",
                             "gate": "roadmap §1.4 / PREREG §301"}
                winner = ref_id
            elif san.get("clean"):
                _say("      sanitizer gate CLEAN")
            else:
                _say(f"      sanitizer gate DID NOT RUN ({san.get('verdict')}) — "
                     f"recorded in the certificate as not-run, which is not a pass")
        if rejection:
            # The screen said feasible, the endpoint says otherwise. Emitting it is not an option.
            _say(f"      WINNER REJECTED at endpoint: config {rejection['rejected_config_id']} — "
                 f"{rejection['reason']}")
            _say(f"      {rejection['action']}. A config that fails the oracle is never emitted.")
        cert = certify.build_certificate(
            name=name, winner_id=winner, reference_id=ref_id, endpoint=ep, oracle=orc,
            feasibility=stats, route=route, rig_mode=mode, rig_detail=rig.certificate_line(mode, detail),
            budget={"probe": feat["n_probe_attempted"], "tuning": tuned,
                    "total_measured": stats["n_measured"], **wdetail},
            sources={"table": sess.table_path, "workspace": sess.workspace},
            allow_fast_math=args.allow_fast_math, flat_observation=flat_observation,
            winner_rejection=rejection)

    # Set on EVERY path, including "no feasible config at all". A certificate that omits the field
    # is indistinguishable at a glance from one whose gate passed, and "the record does not say
    # which checks ran" is the root cause D23 exists to document. Absence is stated, not implied.
    cert["sanitizer_gate"] = san or {
        "ran": False, "clean": None, "verdict": "NOT_APPLICABLE",
        "note": ("no non-reference winner to gate — nothing is being emitted, so there is no "
                 "config whose memory safety could be at issue"),
        "rule": "roadmap §1.4 / PREREG §301"}

    cert["probe_features"] = feat
    cert["wall_clock_s"] = round(time.time() - t_start, 1)

    # --------------------------------------------------------------- 6. certify
    _say()
    _say("[6/6] certify")
    out_path = os.path.join(sess.odir, "certificate.json")
    with open(out_path, "w") as f:
        json.dump(cert, f, indent=2)
    txt_path = os.path.join(sess.odir, "certificate.txt")
    rendered = certify.render(cert)
    with open(txt_path, "w") as f:
        f.write(rendered + "\n")
    _say()
    _say(rendered)
    _say()
    _say(f"certificate: {out_path}")
    _say(f"raw table  : {sess.table_path}")
    return 0


def _fmt(x):
    return "n/a" if x is None else f"{x:.4f}"


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="cytune",
        description=f"Tune Cython directives + GCC flags for a module, and certify the result. "
                    f"v{__version__} — RESEARCH PREVIEW: the routing policy is interim and the "
                    f"P-3 algorithm study is not complete (see results/PHASEP_REPORT.md).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("tune", help="ingest -> probe -> route -> tune -> verify -> certify")
    t.add_argument("module", help="path to the .pyx module")
    t.add_argument("--driver", required=True,
                   help="driver.py defining make_inputs(seed), call(mod, inputs), canon(result), "
                        "OUTPUT_CLASS")
    t.add_argument("--workspace", default=".cytune", help="working directory (default: .cytune)")
    t.add_argument("--name", default=None, help="session name (default: module basename)")
    t.add_argument("--rig", default="auto", choices=["auto", "portable"],
                   help="auto detects the quiesced rig; portable forces best-effort measurement")
    t.add_argument("--target-ms", type=float, default=65.0,
                   help="calibrate the driver knob so the reference lands near this (0 disables)")
    t.add_argument("--allow-fast-math", action="store_true",
                   help="permit fast-math configs to be SELECTED (they are still oracle-checked)")
    t.set_defaults(func=tune)

    d = sub.add_parser("doctor", help="check the environment and print what to fix")
    d.set_defaults(func=doctor)

    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except IngestError as e:
        print(f"\ncytune: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
