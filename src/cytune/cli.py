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

from . import apply as applymod
from . import audit as auditmod
from . import init as initmod
from . import binding, certify, coherence, config, invariants, lock, rig, routing, sanitize_gate
from . import __version__, version_banner
from .doctor import doctor
from .plan import EmissionPolicy, confirm_winner, select_winner
from .session import BuildFailure, IngestError, Session, validate_inputs


class Out:
    """Where narration goes.

    With --json, stdout is a machine-readable channel and must carry NOTHING but the certificate,
    so every human-facing line moves to stderr. Without it, everything goes to stdout as before.
    """

    def __init__(self, json_mode=False):
        self.stream = sys.stderr if json_mode else sys.stdout
        self.json_mode = json_mode

    def __call__(self, msg=""):
        print(msg, file=self.stream, flush=True)


class Clock:
    """Stage timing and a per-config cost estimate, so a silent three minutes does not read as a
    hang. The estimate comes from THIS run's own probe stage rather than a hard-coded constant:
    per-config cost varies by an order of magnitude between a 2 ms and a 65 ms kernel."""

    def __init__(self, say):
        self.say = say
        self.t0 = time.time()
        self.per_config_s = None

    def elapsed(self):
        return time.time() - self.t0

    def learn(self, seconds, n_configs):
        if n_configs:
            self.per_config_s = seconds / n_configs

    def estimate(self, n_configs):
        if not self.per_config_s or not n_configs:
            return None
        return self.per_config_s * n_configs

    def eta(self, n_configs):
        est = self.estimate(n_configs)
        return f" (~{est:.0f}s estimated)" if est else ""

    def stage(self, label):
        self.say(f"      {label}   [t+{self.elapsed():.0f}s]")


def _feasibility_stats(rows):
    n = len(rows)
    infeas = [r for r in rows.values() if not r.get("feasible")]
    reasons = {}
    for r in infeas:
        reasons[r.get("reason") or "unknown"] = reasons.get(r.get("reason") or "unknown", 0) + 1
    out = {"n_measured": n, "n_infeasible": len(infeas),
           "infeasible_fraction": (len(infeas) / n) if n else None,
           "reasons": reasons}
    if infeas:
        out["pattern"] = _rejection_pattern([c for c, r in rows.items() if not r.get("feasible")])
    return out


def _rejection_pattern(infeasible_ids):
    """Which factor settings do ALL the rejected configs share?

    `12  crash` told a user nothing on the one run where the diagnosis mattered most: those 12
    were precisely the boundscheck=True configs, i.e. Cython catching the same off-by-one the
    memory-safety block twenty lines above was about, and the certificate never connected them.
    A factor level common to every rejection is a strong, cheap pointer at the cause.
    """
    if not infeasible_ids:
        return None
    from ._vendor import theta
    dicts = [theta.as_dict(theta.config_of(c)) for c in infeasible_ids]
    shared = {k: v for k, v in dicts[0].items() if all(d[k] == v for d in dicts[1:])}
    if not shared:
        return None
    return {"shared_factor_levels": {k: str(v) for k, v in shared.items()},
            "n": len(infeasible_ids),
            "note": ("every rejected config shares these settings. If one of them is "
                     "boundscheck=True or wraparound=True, the rejections are your own indexing "
                     "being caught by the check — look there first.")}


def _fmt(x):
    return "n/a" if x is None else f"{x:.4f}"


def _write_san_report(odir, san):
    """Persist the sanitizer's own words next to the certificate, and return the path.

    The certificate quotes a one-line summary; a user fixing the bug needs the stack and the
    shadow-byte map. Truncating that into a JSON field and calling it a day would be the same
    mistake as not recording which checks ran."""
    if not san or san.get("clean") is not False:
        return None
    path = os.path.join(odir, f"sanitizer_report_{san.get('config_id')}.log")
    with open(path, "w") as f:
        f.write(f"# cytune §1.4 sanitizer gate — config {san.get('config_id')}\n")
        f.write(f"# verdict: {san.get('verdict')}  tokens: {san.get('tokens')}\n")
        f.write("# The ERROR line, the faulting access and the stack trace are at the TOP.\n\n")
        f.write(san.get("full_output") or san.get("stderr_excerpt") or "(no captured output)\n")
    return path


def _gate_emitted(say, sess, config_id, reference_id, role="emitted config"):
    """Run the §1.4 gate on the config ACTUALLY being emitted — including the reference.

    Cold-user finding F5: after a sanitizer fallback the certificate's `sanitizer_gate` described
    the config that had been REJECTED, so the emitted config's own status was never stated and G2
    held only with an asterisk. It now runs on whatever is being handed to the user. Gating the
    reference is not ceremony: if the user's own baseline reads out of bounds, that is a defect in
    their code and they should hear it from the tool that just rebuilt it under ASan.
    """
    what = "reference" if config_id == reference_id else f"config {config_id}"
    say(f"      §1.4 sanitizer gate on the {role} ({what}, ASan+UBSan)")
    san = sanitize_gate.gate(sess.kdir, config_id)
    if san.get("clean") is True:
        say("      sanitizer gate CLEAN")
    elif san.get("clean") is False:
        say(f"      SANITIZER REPORTED on the {role.upper()}: "
            f"{', '.join(san.get('tokens') or [])}")
    else:
        say(f"      sanitizer gate DID NOT RUN ({san.get('verdict')}) — "
            f"recorded in the certificate as not-run, which is NOT a pass")
    return san


def _policy_of(eff):
    return EmissionPolicy(allow_fast_math=eff["allow_fast_math"],
                          allow_fp_contract=eff["allow_fp_contract"],
                          portable_flags=eff["portable_flags"])


# ---------------------------------------------------------------------------------- tune
def tune(args):
    say = Out(args.json)
    clock = Clock(say)
    eff = args.effective["values"]
    policy = _policy_of(eff)

    # T4 (systematic-tester agent): `--target-ms -5` was accepted, calibrated REPS to 1, and
    # produced a full certificate for a workload of one repetition under the banner
    # `reference ~-5.0 ms`. A negative target is not a preference, it is a typo.
    _t = eff["target_ms"]
    if _t is not None and _t < 0:
        print(f"cytune: --target-ms must be >= 0, got {_t}.\n"
              f"  0 disables calibration and measures the workload as your driver writes it.",
              file=sys.stderr)
        return certify.EXIT_ERROR
    if _t and _t < 1.0:
        print(f"cytune: --target-ms {_t} is below 1 ms, which is under this rig's timing "
              f"resolution.\n  Use 0 to disable calibration, or a target of at least a few ms.",
              file=sys.stderr)
        return certify.EXIT_ERROR
    if eff.get("budget_scale", 1.0) <= 0 or eff.get("budget_scale", 1.0) > 16:
        print(f"cytune: budget_scale must be in (0, 16], got {eff.get('budget_scale')}.",
              file=sys.stderr)
        return certify.EXIT_ERROR

    name = args.name or os.path.splitext(os.path.basename(args.module))[0]
    workspace = os.path.abspath(eff["workspace"])

    # Paths first, before a single directory is created (F9/F11).
    validate_inputs(args.module, args.driver)

    if eff["rig"] == "portable":
        mode, detail = rig.PORTABLE, "forced by --rig portable"
    else:
        mode, detail = rig.probe_rig()
        if eff["rig"] == "quiesced" and mode != rig.QUIESCED:
            print(f"cytune: --rig quiesced was requested but the host is not quiesced.\n"
                  f"  {detail}\n"
                  f"  Run `sudo scripts/host_prep.sh` for the quiesced rig, or pass\n"
                  f"  `--rig portable` to accept indicative timings.", file=sys.stderr)
            return certify.EXIT_ERROR

    # B3 — the machine-level measurement lock, taken HERE: after the rig mode is known (so the
    # refusal can name it), before `Session(...)` creates anything on disk (so a refusal leaves no
    # workspace behind), and above every one of the container spawns below. Whole-run scope, not
    # per phase: a per-phase lock would still let a competing run's BUILD land inside this run's
    # MEASURE, which is the contamination mode.
    _lk = lock.MeasurementLock(workspace=workspace, rig_mode=mode,
                               argv=" ".join(sys.argv[:6]))
    try:
        _lk.acquire(wait=bool(eff.get("wait")),
                    on_wait=lambda h: print(
                        "cytune: queued — " + lock.describe(h, _lk.path).splitlines()[0]
                        + "\n  waiting for it to finish (--wait). Ctrl-C to give up.",
                        file=sys.stderr))
    except lock.Busy as e:
        print("cytune: REFUSING TO MEASURE — " + lock.describe(e.holder, e.path), file=sys.stderr)
        return certify.EXIT_ERROR
    lock.set_current(_lk)

    say(f"{version_banner()} — {name}")
    say(f"  rig mode: {mode} ({detail})")
    say(f"  {routing.LABEL}")
    if args.effective.get("config_file"):
        say(f"  defaults from {args.effective['config_file']}")
    if not (policy.allow_fast_math or policy.allow_fp_contract):
        say("  floating-point: STRICT (default) — no config that changes FP semantics may be "
            "emitted")
    if args.dry_run:
        say("  DRY RUN — ingest and probe only; no tuning budget will be spent")
    say()

    sess = Session(workspace, name, mode, detail, target_ms=eff["target_ms"])

    # ---------------------------------------------------------------- 1. ingest
    say("[1/6] ingest — vendoring module + driver")
    src = sess.vendor(args.module, args.driver)
    say(f"      {src['pyx']}")
    say(f"      {src['driver']}")

    # B3, first half. Must happen BEFORE the build: a stale .so would otherwise produce the golden
    # output, and everything downstream would describe the previous version of the kernel.
    _scoped = src.get("scoped_directives") or {}
    if _scoped:
        _names = sorted({n for d in _scoped.values() for n in d})
        say(f"      NOTE: your source pins {', '.join(_names)} with decorators or `with` blocks in "
            f"{len(_scoped)} file(s).")
        say("      Cython honours those over the -X flags, so the emitted header will not reach "
            "those functions. Listed on the certificate.")

    stale_b = sess.invalidate_stale_builds(args.module)
    if stale_b:
        say(f"      cache invalidated because {', '.join(stale_b['reasons'])} — discarding "
            f"{stale_b['n_builds']} cached build(s)"
            + (f" and {stale_b['n_rows']} measurement row(s)" if stale_b.get("n_rows") else ""))
        say("      (everything is recompiled from the module as it is now)")

    say("      building the reference config + probe design (17 configs; this is the slowest "
        "stage on a first run — one cythonize per distinct directive combo) ...")
    t = time.time()
    b = sess.build("probe", require_any=True)
    n_built = sum(1 for v in b["built"].values() if v)
    say(f"      built {n_built}/{len(b['built'])} configs"
        + (f"; {len(b['failed'])} failed to compile" if b.get("failed") else "")
        + f"   [{time.time() - t:.0f}s]")
    if b.get("failed") and b.get("first_failure"):
        say(f"      NOTE: {len(b['failed'])} configuration(s) did not compile — first reason "
            f"'{b['first_failure'].get('reason')}'; full log at "
            f"{os.path.join(sess.odir, 'build_failure.log')}")

    # I4.2 — AS EARLY AS IT IS OBSERVABLE. The probe spans many directive combinations, so if the
    # directives are being neutralised by something outside cytune the evidence exists now, before
    # a search budget is spent measuring 33 copies of one program. Refusing here rather than at
    # certification is the difference between a 40-second failure and a ten-minute one.
    deg = b.get("degeneracy") or {}
    binding.assert_no_total_degeneracy(
        deg, module_hint=f"\n  module: {src['pyx']}")
    if deg.get("directives_inert"):
        say(f"      note: {', '.join(deg['directives_inert'])} did not change the generated C for "
            f"this kernel ({deg['n_distinct_generated_sources']} distinct sources from "
            f"{deg['n_directive_combos_built']} directive combinations)")
    say("      capturing golden output + deriving the oracle ...")
    g = sess.golden(reuse_knob=sess.reusable_knob(args.module, args.driver))
    orc = g["oracle"]
    say(f"      oracle: class={orc['output_class']} deterministic={orc['deterministic']} "
        f"tolerance={json.dumps(orc['tolerance'])}")
    if g.get("calibrated"):
        c = g["calibrated"]
        if c.get("reused"):
            say(f"      reusing the calibrated {c['knob']} = {c['new']} from the previous run "
                f"(module, driver, --target-ms, image and rig are unchanged)")
        else:
            say(f"      calibrated {c['knob']}: {c['cur']} -> {c['new']} "
                f"(reference ~{eff['target_ms']} ms)")
        # Calibration extrapolates linearly from ONE measurement, so a kernel whose cost is not
        # linear in the knob — or a machine that was busy during that one measurement — lands
        # somewhere else entirely. A 30 ms target that produced a 49 ms reference said nothing at
        # all; the user then read every later number as if the workload were the one they asked
        # for. Reported, not corrected: re-calibrating in a loop would spend measurement budget on
        # a number that only has to be approximately right. (U5, novice-user agent.)
        _cur_ms, _tgt = (None if c.get("reused") else c.get("cur_ms")), eff["target_ms"]
        if _cur_ms and _tgt:
            _pred = _cur_ms * (c["new"] / c["cur"]) if c.get("cur") else None
            if _pred and abs(_pred - _tgt) / _tgt > 0.25:
                say(f"      NOTE: calibration is a linear extrapolation from one measurement and "
                    f"is only approximate here")
        sess.calibration_note = {"target_ms": _tgt, "measured_before_ms": _cur_ms}
    else:
        say("      no REPS/SCALE knob in the driver — measuring the workload as written")
    # B3, second half: everything a TIMING depends on, now that the workload and oracle are known.
    stale = sess.invalidate_stale_measurements(g, module_path=args.module,
                                               driver_path=args.driver)
    if stale and stale.get("n_rows"):
        say(f"      cache invalidated because {', '.join(stale['reasons'])} — discarding "
            f"{stale['n_rows']} cached measurement row(s)")
        for c in stale["changed"]:
            say(f"        {c['reason']}: {c['was']!r} -> {c['now']!r}")
        say(f"      (archived to {stale['archived_to']}; builds are reused, timings are not)")

    # ----------------------------------------------------------------- 2. probe
    say()
    # The label said "16-config screen" and the next line reported "feasible 17/17": the design
    # is 16 configs and the reference is measured alongside it. Two adjacent lines, two
    # denominators, no explanation. (Novice-user agent.)
    say("[2/6] probe — pre-registered 16-config screen + the reference (PREREG §9.2)")
    t = time.time()
    sess.measure("probe")
    feat = sess.features()["features"]
    clock.learn(time.time() - t, feat["n_probe_attempted"])
    rate = f", ~{clock.per_config_s:.1f}s/config" if clock.per_config_s else ""
    say(f"      feasible {feat['n_probe_feasible']}/{feat['n_probe_attempted']} "
        f"({feat['feas_frac']:.1%})   [{time.time() - t:.0f}s{rate}]")
    say(f"      delta_probe = {_fmt(feat['delta_probe'])}   "
        f"IF_probe = {'NA (degenerate)' if feat['if_probe_na'] else _fmt(feat['if_probe'])}")
    say("      (delta_probe is a SCREENING ratio and is normally larger than the final measured "
        "speedup)")
    sig = feat["interim_signals"]
    if sig.get("fm_signal") and sig["fm_signal"] > 1.02 and not policy.allow_fast_math:
        say(f"      [interim signal] fast-math configs looked {sig['fm_signal']:.3f}x faster in "
            f"the probe. NOT claimed: they have not been accepted for correctness here.")
        say("      re-run with --allow-fast-math to have them oracle-checked.")

    # ----------------------------------------------------------------- 3. route
    say()
    say("[3/6] route")
    route = routing.route(feat, bo_available=False)
    # The PRESET scales the budget the frozen routing rule chose; it never replaces the rule. Both
    # numbers are recorded so the certificate shows what the policy asked for and what was spent.
    scale = eff.get("budget_scale", 1.0)
    if route["budget"] and scale != 1.0:
        route["budget_routed"] = route["budget"]
        route["budget_scale"] = scale
        route["budget"] = max(2, int(round(route["budget"] * scale)))
        route["budget_note"] = (f"--preset {eff.get('preset')} scaled the routed budget "
                                f"{route['budget_routed']} by {scale} to {route['budget']}")
    say(f"      rule {route['rule']} -> {route['route']}"
        + (f" (engine {route['engine']}, budget {route['budget']})" if route["engine"] else ""))
    say(f"      {route['why']}")
    if route.get("budget_note"):
        say(f"      {route['budget_note']}")
    if route.get("fallback_note"):
        say(f"      NOTE: {route['fallback_note']}")
    if route.get("feasibility_note"):
        say(f"      NOTE: {route['feasibility_note']}")

    if route["route"] == routing.ABORT:
        say()
        say(f"ABORT: {route['why']}")
        return certify.EXIT_ERROR

    if args.dry_run:
        return _dry_run_report(say, args, feat, route, clock, policy, mode, detail, sess)

    # ------------------------------------------------------------------ 4. tune
    say()
    n_planned = 0 if route["route"] == routing.HONEST_FLAT else route["budget"]
    say(f"[4/6] tune{clock.eta(n_planned)}")
    tuned, wdetail = 0, {}
    search_provenance = {
        "engine": ("probe screen + predicted-best walk" if eff.get("probe_as_screen")
                   else "probe + D-optimal screen + predicted-best walk"),
        "design_key": None,
        "second_screen": not bool(eff.get("probe_as_screen")),
        "prior": "none (classical D-optimal probe design, PREREG_PHASEP §9.2)",
        "note": ("--probe-as-screen skips the second D-optimal screen and spends the whole "
                 "tuning budget on the walk. It is EXPERIMENTAL and off by default: it failed "
                 "its pre-registered ship rule on one anchor. See DOE_V2_REPORT.md."),
    }
    if route["route"] == routing.HONEST_FLAT:
        say("      skipped — the probe says this landscape is flat. Spending a tuning budget "
            "here would buy noise.")
    else:
        sp = sess.screen_plan(route["budget"],
                              second_screen=not eff.get("probe_as_screen"))
        search_provenance["design_key"] = sp["design_key"]
        if sp["ids"]:
            say(f"      {route['engine']} screen: design {sp['design_key']}, "
                f"{len(sp['ids'])} configs{clock.eta(len(sp['ids']))}")
        else:
            say(f"      {route['engine']} screen: none — the 17-config probe already served as "
                f"the D-optimal screen")
            say(f"      so all {route['budget']} tuning configs go to the predicted-best walk")
        if sp["ids"]:
            sess.build(sp["ids"])
            sess.measure(sp["ids"])
            tuned += len(sp["ids"])
            clock.stage(f"screen done ({tuned} configs measured)")
        remaining = route["budget"] - tuned
        if remaining > 0:
            wp = sess.walk_plan(remaining, policy=policy)
            skipped = ((wp.get("fit") or {}).get("skipped_by_policy")) or {}
            if wp["ids"]:
                say(f"      predicted-best walk: {len(wp['ids'])} configs"
                    + (f" ({', '.join(f'{n} {k}' for k, n in sorted(skipped.items()))} skipped "
                       f"by policy)" if skipped else ""))
                sess.build(wp["ids"])
                sess.measure(wp["ids"])
                tuned += len(wp["ids"])
        say(f"      measured {tuned} additional configs   [t+{clock.elapsed():.0f}s]")

    # ---------------------------------------------------------------- 5. verify
    say()
    say("[5/6] verify — endpoint tier on the winner + the reference")
    rows = sess.table_rows()
    feas = sess.feasible_medians()
    stats = _feasibility_stats(rows)
    ref_id = certify.theta.REFERENCE_ID
    observed, wdetail = select_winner(feas, policy=policy)
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

    san_emitted, rejection, ep, screen_overheads = None, None, {}, []
    if winner is None:
        say("      no feasible config at all — nothing can be certified")
    else:
        verify_ids = sorted({winner, ref_id} | ({observed} if flat_observation else set()))
        # Guarantee the verify stage's own inputs exist before measuring them. table.jsonl persists
        # across runs, so the winner can be a config measured by an EARLIER run whose .so has since
        # been pruned; without this the endpoint reports not_built, the winner is (correctly)
        # refused, and a real speedup silently degrades to honest-flat. Build is idempotent. (D18)
        sess.build(verify_ids)
        _ep_res = sess.endpoint(verify_ids)
        ep = _ep_res["endpoints"]
        screen_overheads = _ep_res.get("screen_overhead_ns") or []
        say(f"      re-measured {len(verify_ids)} configs at K=30, median-of-3")
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
            say(f"      [observation, not a recommendation] the fastest probe config "
                f"({observed}) measured {ratio:.4f}x vs the reference"
                if ratio else "      [observation] fastest probe config did not confirm")
        winner, rejection = confirm_winner(winner, ref_id, ep)

        # §1.4 SANITIZER GATE, ON THE SEARCH'S BEST CANDIDATE — FIRST, and regardless of whether
        # it was going to be recommended.
        #
        # The gate is a BUG FINDER, not only an emission filter. The fastest config a search finds
        # is the checks-off corner, which is exactly where a latent out-of-bounds read becomes a
        # live one — and the oracle cannot see it, because a reduction absorbs the garbage element
        # (D23). An earlier version of this pass settled the emit decision first and gated only
        # the emitted config; on the very fixture this product exists to catch, the offending
        # config measured 1.0142x, fell below the emit margin, was dropped for being slow, and the
        # memory defect was never reported at all. Finding the bug is worth more than saving one
        # gate run.
        if winner is not None and winner != ref_id and not rejection:
            san_cand = _gate_emitted(say, sess, winner, ref_id,
                                     role="search's best candidate")
            if sanitize_gate.rejects(san_cand):
                say("      the oracle passed it; ASan did not. Correctness absolute — "
                    "a config that reports is never emitted.")
                rejection = {
                    "rejected_config_id": winner,
                    "reason": f"sanitizer_report: {', '.join(san_cand.get('tokens') or [])}",
                    "action": "fell back to the reference config",
                    "gate": "roadmap §1.4 / PREREG §301",
                    # The ENDPOINT ratio when we have one — the screen median is a fast single
                    # measurement and quoting it would overstate how fast the refused config
                    # actually was.
                    "observed_ratio": certify.assess(ep.get(str(winner)),
                                                     ep.get(str(ref_id)))["speedup"],
                    "report_path": _write_san_report(sess.odir, san_cand),
                    "sanitizer": san_cand,
                }
                winner = ref_id
            else:
                san_emitted = san_cand

        # C1 — DOES THE PARENT'S CLOCK AGREE? Runs after the gate deliberately: the gate is a bug
        # finder and finding a memory defect in the user's kernel is worth more than saving one
        # container run, so it is never skipped by an earlier refusal.
        #
        # A speedup the wall clock cannot account for is not certified. This is the one direction
        # `implausible_timings` could not see — a driver reporting LESS time than elapsed looks
        # exactly like spawn overhead to a one-sided check.
        if winner is not None and winner != ref_id and not rejection:
            cor = certify.corroborate_ratio(ep.get(str(winner)), ep.get(str(ref_id)),
                                            screen_overheads=screen_overheads)
            if cor.get("corroborated") is False:
                say(f"      TIMING NOT CORROBORATED: {cor['reason']}")
                say("      the speedup is withheld — cytune does not certify a ratio its own "
                    "clock cannot account for.")
                rejection = {
                    "rejected_config_id": winner,
                    "reason": "timing_not_corroborated: " + cor["reason"],
                    "action": "fell back to the reference config; no speedup is claimed",
                    "gate": "C1 parent wall-clock corroboration",
                    "corroboration": cor,
                    "observed_ratio": None,
                    # Keep the candidate's verdict where a reader can still see it: the config was
                    # gated and came back clean, and only its TIMING is unaccounted for. Dropping
                    # it on the floor would lose a real result about the user's code.
                    "sanitizer": san_emitted,
                }
                winner = ref_id
                # That gate described the CANDIDATE, not the emission — the same reset the
                # emit-margin demotion below performs, and the one this path was missing. Without
                # it the reference is emitted carrying the candidate's verdict, `_gate_emitted`
                # below is skipped because `san_emitted` is not None, and I4.3 refuses the whole
                # certificate. Found by the live dogfood on fleet_R_08_elkan; see D-3 in
                # test_cytune_binding.py, which mirrors all three demotion paths rather than two.
                san_emitted = None

        # NOW settle what is emitted. A candidate that survived the gate but does not clear the
        # emit margin and the separation test is not going to be recommended, so the REFERENCE is
        # what gets emitted — and the certificate's EMIT block must therefore print the reference.
        # Deciding this after building the certificate is what produced a document saying "EMIT:
        # the reference configuration (unchanged)" above a `boundscheck=False, wraparound=False`
        # header (proof run p21).
        if winner is not None and winner != ref_id and not rejection:
            a = certify.assess(ep.get(str(winner)), ep.get(str(ref_id)))
            if not a["clears"]:
                say(f"      the search's best config ({winner}) measured "
                    f"{a['speedup']:.4f}x but is NOT recommended: {a['why']}")
                say("      emitting the reference instead; the reference is gated below.")
                flat_observation = {
                    "config_id": winner,
                    "endpoint_ratio_vs_reference": a["speedup"],
                    "endpoint_ns": (ep.get(str(winner)) or {}).get("endpoint_ns"),
                    "feasible": (ep.get(str(winner)) or {}).get("feasible"),
                    "sanitizer_gate": san_emitted,
                    "note": ("measured but NOT recommended: " + a["why"] + ". Tuning picks the "
                             "fastest of many measured configs, which biases that pick low, so "
                             "cytune reports the number and declines to act on it.")}
                winner = ref_id
                san_emitted = None          # that gate described the candidate, not the emission

        if rejection:
            if not rejection.get("gate"):
                # The screen said feasible, the endpoint says otherwise. Emitting it is not an
                # option.
                say(f"      WINNER REJECTED at endpoint: config "
                    f"{rejection['rejected_config_id']} — {rejection['reason']}")
                say(f"      {rejection['action']}. A config that fails the oracle is never "
                    f"emitted.")
                rejection.setdefault("observed_ratio",
                                     (feas.get(ref_id) / feas[rejection["rejected_config_id"]])
                                     if feas.get(ref_id)
                                     and feas.get(rejection["rejected_config_id"]) else None)
            winner = ref_id

        # The emitted config's OWN gate. Runs on the reference too — including on the honest-flat
        # path, where the reference is what the user is being handed (F5).
        if san_emitted is None:
            san_emitted = _gate_emitted(say, sess, winner, ref_id)
            if san_emitted.get("clean") is False:
                _write_san_report(sess.odir, san_emitted)

    # ---------------------------------------------------------- I4, before anything is assembled
    #
    # Everything above this line reasons about a config_id. These four checks are the only ones
    # whose ground truth is a hash of a file rather than a function of that id, which is why they
    # can see what I1 structurally cannot: whether the run this document describes is the run that
    # happened.
    artifacts = sess.artifacts()
    tree_sha = sess.source_tree_sha256()
    degeneracy = binding.degeneracy(artifacts)
    if winner is not None:
        # BOTH sides of the ratio. A forged reference measurement manufactures a speedup exactly as
        # well as a forged winner one, and binding only the emitted config would leave that open.
        for cid in sorted({winner, ref_id}):
            binding.assert_emission_bound(config_id=cid, artifacts=artifacts,
                                          endpoint=ep.get(str(cid)))
        binding.assert_gate_bound(config_id=winner, gate=san_emitted,
                                  source_tree_sha256=tree_sha,
                                  pinned_image_digest=rig.PINNED_IMAGE_DIGEST)
    rig_fps = binding.assert_rig_bound(rig_mode=mode, endpoint_records=ep)
    provenance = binding.provenance(
        config_id=winner, artifacts=artifacts, endpoint=ep.get(str(winner)), gate=san_emitted,
        degeneracy_report=degeneracy, rig_fingerprints=rig_fps,
        image_digest=rig.image_digest(), source_tree_sha256=tree_sha,
        n_measured=stats["n_measured"])

    cert = certify.build_certificate(
        name=name, winner_id=winner, reference_id=ref_id, endpoint=ep, oracle=orc,
        feasibility=stats, route=route, rig_mode=mode,
        rig_detail=rig.certificate_line(mode, detail),
        budget={"probe": feat["n_probe_attempted"], "tuning": tuned,
                "total_measured": stats["n_measured"]},
        sources={"table": sess.table_path, "workspace": sess.workspace},
        allow_fast_math=policy.allow_fast_math, flat_observation=flat_observation,
        winner_rejection=rejection, emitted_gate=san_emitted, selection=wdetail,
        probe_features=feat, policy=policy, has_fp_work=src.get("has_fp_work"),
        effective_config=args.effective, provenance=provenance, degeneracy=degeneracy,
        screen_overheads=screen_overheads, scoped_directives=src.get("scoped_directives"),
        search=search_provenance)

    if san_emitted and san_emitted.get("clean") is False:
        cert.setdefault("memory_safety_finding", {})
        cert["memory_safety_finding"]["report_path"] = os.path.join(
            sess.odir, f"sanitizer_report_{san_emitted.get('config_id')}.log")

    cert["probe_features"] = feat
    cert["wall_clock_s"] = round(clock.elapsed(), 1)

    # --------------------------------------------------------------- 6. certify
    say()
    say("[6/6] certify")
    rendered = certify.render(cert)

    # I1 — COHERENCE GATE. Runs before a single byte is printed or written. A certificate whose
    # parts contradict each other is not a certificate, and the four defects this catches (P1, P2,
    # R2, P4) were all shipped documents in which every individual component was correct. Raising
    # here is deliberate: there is nothing to salvage in a document that disagrees with itself.
    coherence.assert_certificate_coherent(
        cert,
        emitted_flags=(cert.get("emitted_config") or {}).get("gcc_flags"),
        gate_result=san_emitted, exit_code=cert.get("exit_code"))
    # I1.10 — and the text is what this document renders to, so the two files on disk cannot
    # disagree. Replaces five substring searches with one exact statement.
    coherence.assert_render_is_a_function_of_the_document(cert, rendered)

    out_path = os.path.join(sess.odir, "certificate.json")
    with open(out_path, "w") as f:
        json.dump(cert, f, indent=2)
    with open(os.path.join(sess.odir, "certificate.txt"), "w") as f:
        f.write(rendered + "\n")
    say()
    say(rendered)
    say()
    say(f"certificate: {out_path}")
    say(f"raw table  : {sess.table_path}")

    if getattr(args, "explain", False):
        say()
        say(certify.explain(cert))

    if args.apply:
        say()
        try:
            res = applymod.apply_to(args.module, cert, in_place=args.in_place)
            say(f"APPLIED: {res['action']} the directive header in {res['target']}")
            if res.get("backup"):
                say(f"         original backed up to {res['backup']}")
            if res.get("diff"):
                say("")
                for line in res["diff"].splitlines():
                    say(f"  {line}")
            say("")
            say("Build snippet:")
            say(applymod.build_snippet(cert))
        except applymod.ApplyRefused as e:
            say(f"NOT APPLIED — {e}")

    if args.json:
        json.dump(cert, sys.stdout, indent=1)
        sys.stdout.write("\n")

    return cert.get("exit_code", certify.EXIT_ERROR)


def _dry_run_report(say, args, feat, route, clock, policy, mode, detail, sess):
    """ingest + probe only: what the landscape looks like, what tuning would cost, what cytune
    would do. The cheapest way to decide whether a full run is worth it."""
    n = 0 if route["route"] == routing.HONEST_FLAT else route["budget"]
    est = clock.estimate(n + 2)          # +2 for the endpoint re-measure of winner and reference
    say()
    say("=" * 78)
    say("DRY RUN — nothing was tuned, no budget was spent")
    say("=" * 78)
    say(f"  landscape       : delta_probe {_fmt(feat['delta_probe'])}, "
        f"IF_probe {'NA' if feat['if_probe_na'] else _fmt(feat['if_probe'])}, "
        f"feasible {feat['feas_frac']:.1%}")
    say(f"  routing         : rule {route['rule']} -> {route['route']}"
        + (f" (engine {route['engine']})" if route["engine"] else ""))
    say(f"  would measure   : {n} configs beyond the {feat['n_probe_attempted']} already probed")
    say(f"  estimated cost  : "
        + (f"~{est:.0f}s more ({clock.per_config_s:.1f}s/config on this kernel)"
           if est else "unknown — the probe did not yield a per-config cost"))
    say(f"  rig             : {mode} ({detail})")
    say(f"  FP policy       : "
        + ("strict — no FP-semantics change may be emitted"
           if not (policy.allow_fast_math or policy.allow_fp_contract)
           else f"fast_math={policy.allow_fast_math} fp_contract={policy.allow_fp_contract}"))
    if route["route"] == routing.HONEST_FLAT:
        say()
        say("  cytune would DECLINE to tune this kernel: the probe spread is at or below this")
        say("  rig's noise floor, so a search would buy noise. Running the full command would")
        say("  emit your reference configuration unchanged.")
    else:
        say()
        say(f"  cytune would run a {route['engine']} search at budget {route['budget']}, verify the")
        say("  winner at the endpoint tier, gate it under ASan+UBSan, and certify.")
    say()
    say("  Re-run without --dry-run to do it.")
    say("=" * 78)
    say(f"probe measurements are already saved in {sess.table_path} and will be reused "
        f"(unless --target-ms changes, which invalidates them).")
    if args.json:
        doc = {"schema": f"cytune-dry-run/{certify.SCHEMA_VERSION}",
               "cytune_version": __version__, "dry_run": True, "verdict": None,
               "module": args.name or os.path.basename(args.module),
               "note": "a dry run produces NO verdict and NO recommendation; it reports the "
                       "landscape and what a full run would do",
               "probe_features": feat, "routing": route,
               "would_measure_configs": n,
               "estimated_seconds": est,
               "per_config_seconds": clock.per_config_s,
               "rig_mode": mode, "emission_policy": policy.as_dict(),
               "exit_code": certify.EXIT_DRY_RUN}
        coherence.assert_document_valid(doc)     # I1.9, for this artifact too
        json.dump(doc, sys.stdout, indent=1)
        sys.stdout.write("\n")
    # A dry run has NO verdict, so it must not borrow a verdict's exit code. Returning 0 for a
    # flat kernel and 2 for a tunable one sent a scripter down the "verified speedup, safe to
    # use" branch of the documented recipe on a kernel whose real answer was
    # no-safe-improvement. Found by the fresh-tester re-test.
    return certify.EXIT_DRY_RUN


# --------------------------------------------------------------------------------- audit
def audit(args):
    """`cytune audit` — gate the pre-registered risk set. No tuning, no timing, no rig needed."""
    say = Out(args.json)
    name = args.name or os.path.splitext(os.path.basename(args.module))[0]
    workspace = os.path.abspath(args.workspace)

    validate_inputs(args.module, args.driver)

    say(f"{version_banner()} — audit {name}")
    say("  memory-safety audit of a PRE-REGISTERED risk set. No search, no timing — the same")
    say("  kernel gives the same verdict every run.")
    say()

    # B3. `audit` times nothing, so it cannot be CORRUPTED by a concurrent run — but it compiles
    # and runs the whole risk set under ASan, so it is a heavy load PRODUCER and would corrupt a
    # concurrent `tune`. It takes the same machine-level lock for that reason, in the direction
    # that matters: this process is the contaminant.
    _lk = lock.MeasurementLock(workspace=workspace, rig_mode="audit (load producer)",
                               argv=" ".join(sys.argv[:5]))
    try:
        _lk.acquire(wait=bool(getattr(args, "wait", False)),
                    on_wait=lambda h: print("cytune: queued behind a running measurement (--wait)",
                                            file=sys.stderr))
    except lock.Busy as e:
        print("cytune: REFUSING TO RUN — " + lock.describe(e.holder, e.path)
              + "\n  `audit` measures no time, but it compiles and runs the whole risk set under\n"
                "  ASan, which would contaminate the measurement already in flight.",
              file=sys.stderr)
        return certify.EXIT_ERROR
    lock.set_current(_lk)

    # portable is honest here: `audit` never times anything, so the rig mode cannot affect a
    # single one of its conclusions. Requiring the quiesced rig would be ceremony.
    sess = Session(workspace, name, rig.PORTABLE, "audit does not measure time", target_ms=0)
    say("[1/2] ingest — vendoring module + driver")
    src = sess.vendor(args.module, args.driver)
    say(f"      {src['pyx']}")
    say(f"      {src['driver']}")
    say()
    say(f"[2/2] sanitizer gate on {len(auditmod.RISK_SET)} pre-registered configurations")

    rows = auditmod.run(sess.kdir, sanitize_gate.gate, say=say, odir=sess.odir,
                        write_report=_write_san_report)
    rep = auditmod.build_report(name, rows, module_path=os.path.abspath(args.module),
                                driver_path=os.path.abspath(args.driver),
                                image=sanitize_gate.IMAGE)
    rep["workspace"] = sess.workspace
    coherence.assert_document_valid(rep)          # I1.9, for this artifact too

    out_path = os.path.join(sess.odir, "audit.json")
    with open(out_path, "w") as f:
        json.dump(rep, f, indent=2)
    rendered = auditmod.render(rep)
    with open(os.path.join(sess.odir, "audit.txt"), "w") as f:
        f.write(rendered + "\n")
    say()
    say(rendered)
    say()
    say(f"audit report: {out_path}")

    if args.json:
        json.dump(rep, sys.stdout, indent=1)
        sys.stdout.write("\n")
    return rep["exit_code"]


# ---------------------------------------------------------------------------------- main
class _Parser(argparse.ArgumentParser):
    """Usage errors exit 1, not argparse's default 2.

    The documented exit scheme reserves 2 for HONEST-FLAT — a successful run with a real answer.
    Leaving argparse's 2 in place would make `if [ $? -eq 2 ]` mean either "no speedup worth
    having" or "you typed the flag wrong", which is worse than having no scheme at all.
    """

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        print(f"\nrun `{self.prog} --help` to see every flag and its default.", file=sys.stderr)
        raise SystemExit(certify.EXIT_ERROR)


def _explicit_options(argv, dest_by_flag):
    """Which settings did the user actually TYPE? Needed so a value left at its argparse default
    does not out-rank the .cytune.toml the user wrote on purpose."""
    seen = set()
    for tok in argv or []:
        flag = tok.split("=", 1)[0]
        if flag in dest_by_flag:
            seen.add(dest_by_flag[flag])
    return seen


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = _Parser(
        prog="cytune",
        description=f"Tune Cython directives + GCC flags for a module, and certify the result. "
                    f"{version_banner()}. The routing policy is an engineering default grounded "
                    f"in the Phase-P study, not a validated per-cell router "
                    f"(see results/PHASEP_REPORT.md §5).")
    ap.add_argument("--version", action="version", version=version_banner())
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=_Parser)

    t = sub.add_parser("tune", help="ingest -> probe -> route -> tune -> verify -> certify")
    t.add_argument("module", help="path to the .pyx module")
    t.add_argument("--driver", required=True,
                   help="driver.py defining make_inputs(seed), call(mod, inputs), canon(result), "
                        "OUTPUT_CLASS")
    t.add_argument("--workspace", default=".cytune", help="working directory (default: .cytune)")
    t.add_argument("--name", default=None, help="session name (default: module basename)")
    t.add_argument("--rig", default="auto", choices=["auto", "quiesced", "portable"],
                   help="auto: use the quiesced rig if available, else portable. "
                        "quiesced: REQUIRE the quiesced rig and refuse to run without it. "
                        "portable: force best-effort measurement (default: auto)")
    t.add_argument("--target-ms", dest="target_ms", type=float, default=65.0,
                   help="calibrate the driver knob so the reference lands near this, in ms "
                        "(0 disables; default: 65)")
    t.add_argument("--allow-fast-math", dest="allow_fast_math", action="store_true",
                   help="permit -ffast-math configs to be selected and EMITTED "
                        "(still oracle-checked; default: off)")
    t.add_argument("--allow-fp-contract", dest="allow_fp_contract", action="store_true",
                   help="permit FMA contraction (-ffp-contract=fast) to be selected and EMITTED. "
                        "Weaker than fast-math but still changes floating-point results "
                        "(default: off)")
    t.add_argument("--portable-flags", dest="portable_flags", action="store_true",
                   help="restrict the recommendation to -march=x86-64 so the emitted flags are "
                        "safe on machines other than this one (default: off)")
    t.add_argument("--probe-as-screen", dest="probe_as_screen", action="store_true",
                   help="EXPERIMENTAL, off by default. Skip the second D-optimal screen design "
                        "and spend the whole tuning budget on the predicted-best walk — the "
                        "17-config probe is already a D-optimal screen. It measured better but "
                        "did not clear its pre-registered acceptance rule, so it is opt-in")
    t.add_argument("--wait", dest="wait", action="store_true",
                   help="if another cytune measurement holds this machine, queue behind it "
                        "instead of refusing. Two runs measuring at once produce wrong numbers "
                        "with no warning (default: refuse)")
    t.add_argument("--dry-run", dest="dry_run", action="store_true",
                   help="ingest + probe only: print the landscape, what cytune would do, and an "
                        "estimated cost. Spends no tuning budget")
    t.add_argument("--json", action="store_true",
                   help="write the certificate as JSON to stdout; all narration goes to stderr")
    t.add_argument("--apply", action="store_true",
                   help="write the emitted directive header into <module>.tuned.pyx. Refuses "
                        "unless the verdict is an improvement whose sanitizer gate was CLEAN")
    t.add_argument("--in-place", dest="in_place", action="store_true",
                   help="with --apply, edit the module itself (a .cytune-backup is kept)")
    t.add_argument("--preset", default="standard", choices=sorted(config.PRESETS),
                   help="; ".join(f"{k}: {v}" for k, v in config.PRESET_HELP.items())
                        + ". A preset scales the routed search budget and the workload size; it "
                          "cannot change the oracle, the sanitizer gate or the emit margin. Any "
                          "individual flag you also pass wins over it")
    t.add_argument("--explain", action="store_true",
                   help="after the verdict, print why this route and budget were chosen, what the "
                        "margin was, and what would have to be true for the answer to change")
    t.add_argument("--config", default=None,
                   help=f"path to a {config.FILENAME} (default: nearest one at or above the CWD)")
    t.add_argument("--no-config", dest="no_config", action="store_true",
                   help=f"ignore any {config.FILENAME}")
    t.set_defaults(func=tune)

    au = sub.add_parser("audit",
                        help="memory-safety audit of the risky directive corners (no tuning)")
    au.add_argument("module", help="path to the .pyx module")
    au.add_argument("--driver", required=True,
                    help="driver.py defining make_inputs(seed), call(mod, inputs), canon(result), "
                         "OUTPUT_CLASS")
    au.add_argument("--workspace", default=".cytune", help="working directory (default: .cytune)")
    au.add_argument("--name", default=None, help="session name (default: module basename)")
    au.add_argument("--wait", dest="wait", action="store_true",
                    help="queue behind a running cytune measurement instead of refusing")
    au.add_argument("--json", action="store_true",
                    help="write the audit report as JSON to stdout; narration goes to stderr")
    au.set_defaults(func=audit)

    d = sub.add_parser("doctor", help="check the environment and print what to fix")
    d.add_argument("--json", action="store_true", help="machine-readable check results")
    d.add_argument("--build-image", dest="build_image", action="store_true",
                   help="build the pinned toolchain image and verify its digest against the one "
                        "every number in results/ was measured on. Refuses if they differ. Use "
                        "this when the `pinned image` check above is BLOCKING, or when the "
                        "`sanitizer gate` check reports that the image is not the pinned one")
    d.set_defaults(func=doctor)

    i = sub.add_parser("init", help="scaffold a driver.py and .cytune.toml for a module")
    i.add_argument("module", help="path to the .pyx module (or a module tree)")
    i.add_argument("--driver", default=None,
                   help="where to write the driver (default: driver.py beside the module)")
    i.add_argument("--force", action="store_true", help="overwrite an existing driver")
    i.set_defaults(func=initmod.init)

    # F12: argparse routes an unrecognised SUB-command flag back to the top-level parser, whose
    # error then prints `usage: cytune [-h] {tune,doctor} ...` — so a user who typed
    # `--fast-math` never sees that the real spelling is `--allow-fast-math`. Handle the leftovers
    # ourselves and show the usage of the sub-command they were actually running.
    a, extras = ap.parse_known_args(argv)
    if extras:
        target = {"tune": t, "audit": au, "doctor": d, "init": i}.get(getattr(a, "cmd", None), ap)
        target.print_usage(sys.stderr)
        print(f"cytune {a.cmd}: error: unrecognized arguments: {' '.join(extras)}",
              file=sys.stderr)
        print(f"\nrun `cytune {a.cmd} --help` to see every flag and its default.", file=sys.stderr)
        return certify.EXIT_ERROR

    if a.cmd == "tune":
        if a.in_place and not a.apply:
            print("cytune: --in-place requires --apply", file=sys.stderr)
            return certify.EXIT_ERROR
        dest_by_flag = {"--workspace": "workspace", "--rig": "rig", "--target-ms": "target_ms",
                        "--allow-fast-math": "allow_fast_math",
                        "--allow-fp-contract": "allow_fp_contract",
                        "--portable-flags": "portable_flags", "--preset": "preset",
                        "--probe-as-screen": "probe_as_screen"}
        try:
            file_values, file_path = ({}, None) if a.no_config else config.load(a.config)
        except config.ConfigError as e:
            print(f"cytune: {e}", file=sys.stderr)
            return certify.EXIT_ERROR
        a.effective = config.resolve(a, _explicit_options(argv, dest_by_flag),
                                     file_values, file_path)

    try:
        return a.func(a)
    except KeyboardInterrupt:
        # Ctrl-C during a queue wait, or mid-run. The `finally` below still releases the lock, so
        # an interrupted run never leaves the machine locked against the next one.
        print("\ncytune: interrupted.", file=sys.stderr)
        return certify.EXIT_ERROR
    except BuildFailure as e:
        print(f"\ncytune: {e}", file=sys.stderr)
        return certify.EXIT_ERROR
    except IngestError as e:
        print(f"\ncytune: {e}", file=sys.stderr)
        return certify.EXIT_ERROR
    except binding.BindingViolation as e:
        # I4 refused. Distinct from the I1 message on purpose: I1 fires on a cytune defect (the
        # document disagreed with itself), while I4 usually fires on something about the USER's
        # environment or kernel that makes an honest certificate impossible — a neutralised
        # directive, a swapped artifact, a gate that built something else.
        entry = invariants.describe(e.invariant)
        print(f"\ncytune: REFUSING TO CERTIFY — a claim could not be tied to the artifact behind "
              f"it.\n  violated invariant {e.invariant}: {e}", file=sys.stderr)
        if entry:
            print(f"\n  {e.invariant} guarantees: {entry['guarantees']}", file=sys.stderr)
        print(f"\n  Nothing was written. Every other check cytune runs verifies the certificate "
              f"against\n  the configuration id; this one verifies the configuration id against "
              f"the bytes that\n  were built, gated and timed. When it fails, the document would "
              f"be about a run that\n  did not happen. See docs/ARCHITECTURE.md#invariants.",
              file=sys.stderr)
        return certify.EXIT_ERROR
    except coherence.IncoherentCertificate as e:
        # The I1 gate refused. Nothing was printed and nothing was written — deliberately, because
        # a self-contradicting certificate is worse than no certificate. This is a cytune bug, not
        # a user error, so it says so and asks for the report.
        entry = invariants.describe(e.invariant)
        print(f"\ncytune: INTERNAL — refusing to emit a certificate that contradicts itself.\n"
              f"  violated invariant {e.invariant}: {e}", file=sys.stderr)
        if entry:
            print(f"  {e.invariant} guarantees: {entry['guarantees']}\n"
                  f"  enforced in: {entry['enforced_in']}", file=sys.stderr)
        print(f"\n  Nothing was written. This is a defect in cytune, not in your kernel: the run\n"
              f"  itself may have been fine, but the document describing it disagreed with the\n"
              f"  measurements behind it, and emitting it anyway is exactly the failure this\n"
              f"  tool exists to refuse. Please report it with the command you ran.\n"
              f"  See docs/ARCHITECTURE.md#invariants.", file=sys.stderr)
        return certify.EXIT_ERROR
    finally:
        # B3: release the machine-level measurement lock on EVERY exit path, including the
        # refusals above. The kernel would drop it at process exit anyway, but `main()` is called
        # in-process by the test suite and by anything embedding cytune, where "the process exits"
        # is not a release.
        _held = lock.current()
        if _held is not None:
            _held.release()
            lock.set_current(None)


if __name__ == "__main__":
    raise SystemExit(main())
