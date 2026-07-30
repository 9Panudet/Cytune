"""Certificate + emission (roadmap §8.1 step 5, §8.2 hard guarantees).

The certificate is the product. A speedup number with no statement of what was verified, how, and
under what rig is exactly the kind of claim this whole project exists to stop making — so the
emitted artifact always carries: what was measured, what the oracle checked, what was rejected as
incorrect, and whether the timing rig was quiesced or merely portable.

Host-side and numpy-free (theta is safe to import; classify/algorithms are not).
"""
from __future__ import annotations
import json

from ._phasep import theta
from . import routing

SCHEMA = "cytune-certificate/v0"

TAU = 0.02   # PREREG §1.1 tau — this rig's measured ~2% noise floor. Inherited, not invented here.


def emit_margin(win, ref):
    """The gain an emitted config must EXCEED before v0 will call it an improvement.

        margin = max(2 x combined relative endpoint uncertainty, TAU)

    Generalises D13/D15 to EVERY route. A bare fixed floor (the original 1.02) is wrong in both
    directions: too permissive when the endpoint measurements are noisy — which is exactly the
    portable-rig case where selection bias produces phantom gains of 1.06-1.11x — and arbitrary
    when they are clean. Tying the margin to the measured spread of the endpoint sub-measures makes
    the bar scale with how well this particular run could actually measure.

    The uncertainty term uses each config's CV over its endpoint sub-measures (not the standard
    error) combined in quadrature for the ratio. Using CV rather than CV/sqrt(n) is deliberately
    conservative: with 3-5 sub-measures an SEM would understate the spread, and the honest
    direction for a product that certifies speedups is the wider bar.

    v0 PRODUCT rule, not a pre-registered study threshold — the study never selects-then-claims
    this way. TAU is inherited; the 2x multiplier and the CV choice are v0's, and are stated as
    such in the certificate.
    """
    def _cv(rec):
        subs = [x for x in (rec or {}).get("subs_ns") or [] if x]
        if len(subs) < 2:
            return None
        mean = sum(subs) / len(subs)
        var = sum((x - mean) ** 2 for x in subs) / len(subs)
        return (var ** 0.5) / mean if mean else None

    cw, cr = _cv(win), _cv(ref)
    if cw is None or cr is None:
        # Cannot estimate the measurement spread, so the CI term is unavailable. Fall back to the
        # floor alone and SAY that the fallback happened rather than implying a measured bound.
        return {"margin": TAU, "tau": TAU, "ci_term": None, "cv_winner": cw, "cv_reference": cr,
                "basis": f"floor only (tau={TAU}) — too few endpoint sub-measures to estimate spread"}
    ci = 2.0 * ((cw ** 2 + cr ** 2) ** 0.5)
    margin = max(ci, TAU)
    return {"margin": margin, "tau": TAU, "ci_term": ci, "cv_winner": cw, "cv_reference": cr,
            "basis": (f"max(2 x combined endpoint CV = {ci:.4f}, tau = {TAU}) = {margin:.4f}")}


def endpoint_separation(win, ref):
    """Is the winner's endpoint timing cleanly separated from the reference's?

    WHY THIS EXISTS (bo-math-reviewer finding F6, 2026-07-25). Tuning selects the MINIMUM over B
    measured configs. On a flat landscape that minimum is biased low purely by selection: with
    per-config log-noise sd s, E[min of B] sits s*E[max_B Z] below the truth — a phantom 1.064x at
    B=32, s=0.03, and 1.109x at B=32, s=0.05 (portable-rig territory). Both exceed the 1.02 floor,
    so a fixed threshold alone would let cytune certify pure noise as a speedup. That is precisely
    the failure this product exists to refuse.

    The endpoint re-measure already removes most of it — the winner is re-timed fresh at K=30 and
    is NOT re-selected, so a phantom regresses toward the reference. This adds the remaining guard:
    every winner sub-measure must be faster than every reference sub-measure. It is a separation
    statement over the actual repeated measurements, with no distributional assumption, and it is
    cheap because the sub-measures are already collected.

    v0 PRODUCT RULE, not a pre-registered study threshold — the study never selects-then-claims
    this way. Recorded as such in the certificate and in CLI_V0_REPORT.md.
    """
    ws = [x for x in (win or {}).get("subs_ns") or [] if x]
    rs = [x for x in (ref or {}).get("subs_ns") or [] if x]
    if not ws or not rs:
        return {"separated": False, "reason": "missing endpoint sub-measures"}
    sep = max(ws) < min(rs)
    return {"separated": bool(sep),
            "winner_worst_ns": max(ws), "reference_best_ns": min(rs),
            "n_winner_subs": len(ws), "n_reference_subs": len(rs),
            "reason": ("every winner sub-measure beat every reference sub-measure" if sep else
                       "the winner's and the reference's endpoint sub-measures OVERLAP — the "
                       "apparent gain is not separable from measurement spread")}


def directive_header(config):
    """The `# cython:` line to paste at the top of the .pyx (or pass via -X)."""
    bc, wa, cd, ic, nc = theta.directive_combo(config)
    return ("# cython: "
            f"boundscheck={bc}, wraparound={wa}, cdivision={cd}, "
            f"initializedcheck={ic}, nonecheck={nc}")


def gcc_flags(config):
    """Mirrors scripts/phasep/build.py's gcc invocation. -ffp-contract is ALWAYS explicit:
    GCC's default is `fast`, so leaving it implicit silently permits FMA contraction."""
    _dirs, opt_flags, ffp, _lang = theta.build_flags(config)
    return f"{opt_flags} -ffp-contract={ffp}"


def cython_x_flags(config):
    dirs, _o, _f, _l = theta.build_flags(config)
    return dirs


def build_certificate(*, name, winner_id, reference_id, endpoint, oracle, feasibility,
                      route, rig_mode, rig_detail, budget, sources, allow_fast_math,
                      flat_observation=None, winner_rejection=None):
    """Assemble the certificate. `endpoint` holds the verify-tier re-measurements keyed by str(id)."""
    win = endpoint.get(str(winner_id)) if winner_id is not None else None
    ref = endpoint.get(str(reference_id))
    speedup = None
    if win and ref and win.get("endpoint_ns") and ref.get("endpoint_ns"):
        speedup = ref["endpoint_ns"] / win["endpoint_ns"]

    is_reference = (winner_id == reference_id)
    cfg = theta.config_of(winner_id) if winner_id is not None else None
    uses_fm = bool(cfg and cfg[8][0] == "on")
    # The composite fmffp factor has THREE levels: (off,off), (off,fast), (on,NA). Only (on,NA) is
    # -ffast-math. (off,fast) permits FMA contraction, which is a DIFFERENT axis but still changes
    # floating-point results — so a user who declined fast-math can still be handed contraction.
    # Saying only "fast-math: not opted in" would leave them believing FP semantics were untouched.
    uses_contract = bool(cfg and cfg[8][0] == "off" and cfg[8][1] == "fast")

    cert = {
        "schema": SCHEMA,
        "module": name,
        "routing_label": routing.LABEL,
        "verdict": None,          # filled below
        "emitted_config": None,
        "speedup": None,
        "correctness": {
            "oracle_class": oracle.get("output_class"),
            "tolerance": oracle.get("tolerance"),
            "tolerance_basis": (
                "bit-exact (sha256 of the canonical output) — the output class is integral"
                if oracle.get("output_class") in ("int", "bool") else
                "numpy.allclose(rtol, atol) against the golden output; the reference config's "
                "output was bit-identical across repeated runs, so the tolerance sits at the "
                "pre-registered floor rather than being widened to fit observed drift"),
            "determinism_gate": {"deterministic": oracle.get("deterministic"),
                                 "n_reference_reps": oracle.get("n_det_reps")},
            "golden_sha256": oracle.get("golden_sha256"),
            "configs_measured": feasibility.get("n_measured"),
            "configs_rejected_infeasible": feasibility.get("n_infeasible"),
            "infeasible_fraction": feasibility.get("infeasible_fraction"),
            "rejected_reasons": feasibility.get("reasons"),
            "endpoint_recheck": (
                "the emitted config was re-measured at the endpoint tier and re-checked against "
                "the oracle; a config that passes the screen but fails here is never emitted"),
        },
        "measurement": {
            "rig_mode": rig_mode,
            "rig_statement": rig_detail,
            "endpoint_protocol": "median-of-3 sub-measures at K=30, escalating to at most 5 while CV > 0.05",
            "winner_endpoint_ns": (win or {}).get("endpoint_ns"),
            "reference_endpoint_ns": (ref or {}).get("endpoint_ns"),
            "winner_subs_ns": (win or {}).get("subs_ns"),
            "reference_subs_ns": (ref or {}).get("subs_ns"),
            "winner_cv": (win or {}).get("cv"),
            "reference_cv": (ref or {}).get("cv"),
        },
        "routing": route,
        "budget": budget,
        "fp_semantics": {
            "fma_contraction_permitted": uses_contract,
            "note": (
                "the emitted config sets -ffp-contract=fast, permitting the compiler to fuse "
                "multiply-add pairs. This is NOT -ffast-math (no reassociation, no finite-math "
                "assumptions), but it does change floating-point results. It was accepted only "
                "because it passed the oracle at the tolerance stated above."
                if uses_contract else
                "-ffp-contract is explicit in the emitted flags (GCC's default is `fast`, so "
                "leaving it implicit would silently permit FMA contraction)."),
        },
        "fast_math": {
            "opted_in": bool(allow_fast_math),
            "emitted_config_uses_fast_math": uses_fm,
            "policy": ("fast-math is opt-in; it changes what is TRIED, never what is ACCEPTED — a "
                       "fast-math config is emitted only if it passes the same oracle as "
                       "everything else"),
        },
        "sources": sources,
        # Present only on the honest-flat route: the fastest config seen in the probe, measured at
        # the endpoint tier and deliberately NOT recommended. Reported so the run is transparent
        # about what it saw, without converting a selection-biased sample minimum into a claim.
        "flat_observation": flat_observation,
        # A config that the screen accepted and the endpoint refused. Recorded in the ARTIFACT, not
        # only printed: it is a correctness-relevant event and an auditor must be able to see it.
        # A reason of `not_built` here means an ORCHESTRATION bug, not an oracle rejection (D18).
        "winner_rejection": winner_rejection,
    }

    if winner_id is None:
        cert["verdict"] = "no-safe-improvement"
        cert["summary"] = ("No config was both faster and correct. The reference configuration "
                           "remains the best safe choice.")
        return cert

    cert["emitted_config"] = {
        "config_id": winner_id,
        "factors": theta.as_dict(cfg),
        "directive_header": directive_header(cfg),
        "cython_x_flags": cython_x_flags(cfg),
        "gcc_flags": gcc_flags(cfg),
    }
    cert["speedup"] = speedup
    sep = endpoint_separation(win, ref)
    cert["measurement"]["endpoint_separation"] = sep
    mar = emit_margin(win, ref)
    cert["measurement"]["emit_margin"] = mar
    clears_margin = (speedup is not None) and ((speedup - 1.0) > mar["margin"])

    if is_reference or speedup is None or not clears_margin:
        cert["verdict"] = "honest-flat"
        cert["summary"] = _flat_summary(speedup, route, mar)
    elif not sep["separated"]:
        # Above the fixed floor, but the repeated measurements overlap. Selection over B configs
        # biases the apparent winner low; without separation this is not a defensible claim.
        cert["verdict"] = "honest-flat"
        cert["summary"] = (
            f"Measured {speedup:.3f}x, but {sep['reason']}. Tuning picks the fastest of many "
            f"measured configs, which biases that pick low on a flat landscape, so cytune will "
            f"not certify this as a speedup. Best safe config = the reference.")
    else:
        cert["verdict"] = "improvement"
        cert["summary"] = (f"{speedup:.3f}x faster than the reference configuration, verified at "
                           f"the endpoint tier and re-checked against the oracle.")
    return cert


def _flat_summary(speedup, route, margin=None):
    if route.get("route") == routing.HONEST_FLAT:
        return ("No worthwhile speedup found — the probe spread sat at or below this rig's noise "
                "floor. Best safe config = the reference. This is a real answer, not a failure: "
                "on real code a flat landscape is the common case.")
    got = f"only {speedup:.4f}x" if speedup else "no measurable gain"
    bar = (f", below the {1 + margin['margin']:.4f}x bar this run could actually resolve "
           f"({margin['basis']})") if margin else ", which is within measurement noise"
    return (f"Tuning ran but found {got} over the reference{bar}. "
            f"Best safe config = the reference.")


def render(cert):
    """Human-readable certificate — what the user actually reads in the terminal."""
    L = []
    add = L.append
    add("=" * 78)
    add(f"cytune certificate — {cert['module']}")
    add(f"  {cert['routing_label']}")
    add("=" * 78)
    add("")
    v = cert["verdict"]
    add(f"VERDICT: {v.upper()}")
    add(f"  {cert['summary']}")
    add("")

    if cert["emitted_config"] and v == "improvement":
        e = cert["emitted_config"]
        add("EMIT — paste this at the top of the .pyx:")
        add(f"  {e['directive_header']}")
        add("")
        add("  ...or pass to cythonize:")
        add(f"  {e['cython_x_flags']}")
        add("")
        add("GCC flags:")
        add(f"  {e['gcc_flags']}")
        add("")
        m = cert["measurement"]
        add(f"MEASURED SPEEDUP: {cert['speedup']:.4f}x")
        add(f"  reference {m['reference_endpoint_ns'] / 1e6:.3f} ms  ->  "
            f"emitted {m['winner_endpoint_ns'] / 1e6:.3f} ms")
        add(f"  {m['endpoint_protocol']}")
        sep = m.get("endpoint_separation") or {}
        if sep.get("reason"):
            add(f"  separation: {sep['reason']}")
        mar = m.get("emit_margin") or {}
        if mar.get("basis"):
            add(f"  emit margin: gain had to exceed {mar['margin']:.4f} — {mar['basis']}")
            add("               (v0 product rule, not a pre-registered study threshold)")
        add("")
    elif cert["emitted_config"]:
        add("EMIT: the reference configuration (unchanged) is the best safe choice.")
        add(f"  {cert['emitted_config']['directive_header']}")
        add(f"  {cert['emitted_config']['gcc_flags']}")
        add("")

    wr = cert.get("winner_rejection")
    if wr:
        add("WINNER REJECTED AT VERIFY")
        add(f"  config {wr.get('rejected_config_id')} — {wr.get('reason')}")
        add(f"  {wr.get('action')}")
        add("")

    fo = cert.get("flat_observation")
    if fo and fo.get("endpoint_ratio_vs_reference"):
        add("OBSERVED BUT NOT RECOMMENDED")
        add(f"  config {fo['config_id']} measured {fo['endpoint_ratio_vs_reference']:.4f}x vs the "
            f"reference at the endpoint tier.")
        add(f"  {fo['note']}")
        add("")

    c = cert["correctness"]
    add("CORRECTNESS CERTIFICATE")
    add(f"  oracle class          : {c['oracle_class']}")
    add(f"  tolerance             : {json.dumps(c['tolerance'])}")
    add(f"  basis                 : {c['tolerance_basis']}")
    add(f"  determinism gate      : bit-identical over "
        f"{c['determinism_gate']['n_reference_reps']} reference reps -> "
        f"{c['determinism_gate']['deterministic']}")
    add(f"  configs measured      : {c['configs_measured']}")
    add(f"  rejected as incorrect : {c['configs_rejected_infeasible']}"
        f" ({c['infeasible_fraction']:.1%} of measured)" if c["infeasible_fraction"] is not None
        else f"  rejected as incorrect : {c['configs_rejected_infeasible']}")
    if c["rejected_reasons"]:
        for reason, n in sorted(c["rejected_reasons"].items(), key=lambda kv: -kv[1]):
            add(f"      {n:>4}  {reason}")
    add(f"  endpoint re-check     : {c['endpoint_recheck']}")
    add("")

    m = cert["measurement"]
    add("RIG MODE")
    add(f"  {m['rig_mode']}: {m['rig_statement']}")
    add("")

    r = cert["routing"]
    add("ROUTING")
    add(f"  rule {r['rule']} -> {r['route']}" + (f" (engine: {r['engine']})" if r.get("engine") else ""))
    add(f"  {r['why']}")
    if r.get("fallback_note"):
        add(f"  NOTE: {r['fallback_note']}")
    if r.get("feasibility_note"):
        add(f"  NOTE: {r['feasibility_note']}")
    add(f"  {cert['routing_label']}")
    add("")

    fp = cert.get("fp_semantics") or {}
    if fp.get("fma_contraction_permitted"):
        add("FLOATING-POINT SEMANTICS")
        add(f"  {fp['note']}")
        add("")

    fm = cert["fast_math"]
    if not fm["opted_in"]:
        add("FAST-MATH: not opted in (--allow-fast-math). Fast-math configs were excluded from "
            "selection.")
    else:
        add(f"FAST-MATH: opted in; emitted config uses fast-math = {fm['emitted_config_uses_fast_math']}")
    add(f"  {fm['policy']}")
    add("")
    add("RAW: every number above recomputes from " + cert["sources"]["table"])
    add("=" * 78)
    return "\n".join(L)
