"""Certificate + emission (roadmap §8.1 step 5, §8.2 hard guarantees).

The certificate is the product. A speedup number with no statement of what was verified, how, and
under what rig is exactly the kind of claim this whole project exists to stop making — so the
emitted artifact always carries: what was measured, what the oracle checked, what was rejected as
incorrect, and whether the timing rig was quiesced or merely portable.

Host-side and numpy-free (theta is safe to import; classify/algorithms are not).
"""
from __future__ import annotations
import json

from ._vendor import theta
from . import routing
from . import __version__, SCHEMA_VERSION
from .plan import BASELINE_MARCH, fp_semantics, march_of

SCHEMA = f"cytune-certificate/{SCHEMA_VERSION}"

TAU = 0.02   # PREREG §1.1 tau — this rig's measured ~2% noise floor. Inherited, not invented here.

# C2 — THE SCOPE OF WHAT THIS DOCUMENT ATTESTS. Printed on every certificate.
#
# WHY IT IS HERE AND NOT ONLY IN SECURITY.md. A certificate is the artifact that leaves the
# machine: it gets pasted into a pull request, attached to a ticket, forwarded to someone deciding
# whether to trust a flag change. SECURITY.md stays in the repository. The one thing a reader who
# did not run the tool most needs to know — that the numbers come from code the runner supplied —
# has to travel with the document or it does not travel at all.
ATTESTATION = {
    "attests": ("that cytune built, oracle-checked, sanitizer-gated and timed the configuration "
                "named above, in the pinned toolchain, and that every claim here is bound to the "
                "hashes in PROVENANCE."),
    "does_not_attest": ("that the timings are what the kernel really takes. The measurement child "
                        "loads the user's own driver into the process that owns the clock, so the "
                        "reported medians are as trustworthy as that driver. cytune corroborates "
                        "them against the parent process's wall clock (see timing_corroboration): "
                        "that catches ANY claimed speedup on a kernel that is really flat, and "
                        "catches an inflated claim up to a true speedup of roughly 1.2x-2.3x "
                        "depending on the size of the claim. It does NOT catch a large real gain "
                        "being inflated further, and it cannot catch a driver that genuinely does "
                        "different work for different configurations."),
    # The ARTIFACT half of the same boundary. The clock limit above was stated from the first
    # version of this block; this one was recorded in the JSON provenance note and never printed,
    # so a reader of the rendered certificate — which is the copy that gets forwarded — did not see
    # it. Named by the focused adversarial re-run as the undemonstrated escape from the Attack B
    # fix, and the tag condition is explicit that every remaining limit belongs HERE.
    "does_not_attest_artifact": (
        "that the binary the measurement imported is the one hashed above. The hashes bind the "
        "FILE cytune built and pointed the endpoint tier at, checked before and after the "
        "measurement and against a read-only artifact tree. They do not bind against a driver "
        "that hijacks its own interpreter's module loader — it is loaded first, so it can import "
        "something else while the file on disk is untouched. No hash reaches that; it is the same "
        "trust boundary as the clock."),
    "audience": ("this is evidence to whoever controls the driver. It is NOT evidence to a third "
                 "party who does not trust that driver."),
}

IMPROVEMENT = "improvement"
HONEST_FLAT = "honest-flat"
NO_SAFE_IMPROVEMENT = "no-safe-improvement"

# Exit codes. Documented in docs/USER_GUIDE.md and pinned by test_cytune_certify.py so a script
# can branch on them. 0/2/3 are all SUCCESSFUL runs — the tool answered the question. 1 is an
# error: cytune could not answer.
EXIT_IMPROVEMENT = 0
EXIT_ERROR = 1
EXIT_HONEST_FLAT = 2
EXIT_NO_SAFE_IMPROVEMENT = 3
# A dry run answers a different question and must not borrow a verdict's code.
EXIT_DRY_RUN = 0

EXIT_BY_VERDICT = {IMPROVEMENT: EXIT_IMPROVEMENT,
                   HONEST_FLAT: EXIT_HONEST_FLAT,
                   NO_SAFE_IMPROVEMENT: EXIT_NO_SAFE_IMPROVEMENT}

# Every insider term the certificate uses, defined in the certificate itself. Cold-user finding
# F16: certificates said `rule R2`, `PREREG §9.2`, `IF_probe`, `tau`, `roadmap §1.4` and pointed
# at documents the user does not have.
GLOSSARY = {
    "delta_probe": "ratio of the slowest to the fastest FEASIBLE config in the 17-config probe "
                   "screen. A screening-tier number: it is routinely larger than the final "
                   "endpoint-tier speedup, because the screen is one fast measurement per config.",
    "IF_probe": "interaction fraction — how much of the probe's variation is NOT explained by "
                "independent single-factor effects. Low means the factors act separately. "
                "'NA (degenerate)' means too few feasible probe rows to fit it at all.",
    "tau": "0.02 — this rig's measured ~2% timing noise floor, and the hard lower bound on the "
           "emit margin. A gain smaller than tau is never claimed no matter how clean the run.",
    "emit margin": "max(2 x combined endpoint CV, tau). The bar a speedup must clear, computed "
                   "from THIS run's own measured noise, so a noisy rig demands a bigger gain.",
    "endpoint tier": "median-of-3 sub-measures at K=30 repetitions, escalating to at most 5 "
                     "while CV > 0.05. The measurement of record; the screen tier is not.",
    "separation": "every winner sub-measure was faster than every reference sub-measure. Not a "
                  "p-value — a direct statement over the repeated measurements.",
    "the reference": "config 288: Cython's safe defaults (boundscheck and wraparound ON) with "
                     "-O2 -march=x86-64 -ffp-contract=off. What cytune falls back to.",
    "§1.4 sanitizer gate": "the emitted config is rebuilt under AddressSanitizer + "
                           "UndefinedBehaviorSanitizer and run. A report makes it unemittable "
                           "regardless of whether its output was correct.",
    "wall-clock corroboration": "an independent check on the reported speedup, using a clock the "
                                "measured process cannot reach. The parent times each sub-measure "
                                "from outside; the winner and the reference run the same driver "
                                "with the same repetitions on the same inputs, so the time NOT "
                                "spent in the timed region must be the same for both apart from "
                                "the warmup calls. A driver that misreports its own elapsed time "
                                "breaks that equality. PASS means the discrepancy stayed inside a "
                                "budget derived from this run's own measured process-to-process "
                                "spread.",
    "rule R0..R5": "which routing rule fired. R0 abort, R1 honest-flat, R2 degenerate probe, "
                   "R3 interaction-dominated, R4 separable lever, R5 modest spread.",
}


def explain(cert):
    """`--explain` — why this answer, and what would have to change for it to be different.

    Everything here is already computed during a normal run; printing it costs nothing. It exists
    because the most common reasonable reaction to `HONEST-FLAT` is "did it actually try?", and the
    honest response is the counterfactual: here is the bar, here is what you measured against it,
    and here is what would move it.
    """
    L = []
    v = cert["verdict"]
    route = cert.get("routing") or {}
    m = cert.get("measurement") or {}
    mar = m.get("emit_margin") or {}
    sep = m.get("endpoint_separation") or {}
    sel = cert.get("selection") or {}
    eff = (cert.get("effective_config") or {}).get("values") or {}
    prov = (cert.get("effective_config") or {}).get("provenance") or {}

    L.append("=" * 78)
    L.append("WHY THIS ANSWER  (--explain)")
    L.append("=" * 78)

    L.append("")
    L.append("ROUTE")
    L.append(f"  rule {route.get('rule')} -> {route.get('route')}: {route.get('why')}")
    if route.get("budget_note"):
        L.append(f"  {route['budget_note']}")
    else:
        L.append(f"  budget {route.get('budget')} configs"
                 + (f" (base {route['budget_base']} + {route['feasibility_bonus']} feasibility "
                    f"bonus)" if route.get("feasibility_bonus") else ""))
    L.append("  The rule is a frozen policy, not a decision made about your kernel: it reads the")
    L.append("  probe's spread and decides how much to spend. It does not choose an algorithm —")
    L.append("  cytune ships one (DOE), because the study measured that routing between algorithms")
    L.append("  does not beat always-DOE.")

    L.append("")
    L.append("THE BAR")
    if mar.get("basis"):
        L.append(f"  a gain had to EXCEED {mar['margin']:.4f} to be called an improvement")
        L.append(f"  basis: {mar['basis']}")
        if mar.get("cv_winner") is not None:
            L.append(f"  measured noise this run: winner CV {mar['cv_winner']:.4f}, "
                     f"reference CV {mar['cv_reference']:.4f}")
    L.append(f"  rig: {m.get('rig_mode')} — {'decision-grade' if m.get('rig_mode') == 'quiesced' else 'INDICATIVE only'}")
    if sep.get("separated") is not None:
        L.append(f"  separation: {'yes' if sep['separated'] else 'NO'} — {sep.get('reason', '')}")

    L.append("")
    L.append("WHAT WAS SEARCHED")
    L.append(f"  measured {(cert.get('budget') or {}).get('total_measured')} of "
             f"{theta.N_CONFIGS} configurations "
             f"({(cert.get('budget') or {}).get('total_measured', 0) / theta.N_CONFIGS:.1%})")
    if sel.get("n_feasible_measured") is not None:
        L.append(f"  {sel.get('n_candidates')} of {sel['n_feasible_measured']} feasible configs "
                 f"were emittable under this run's policy")
    skipped = (sel.get("skipped_by_policy") or {})
    if skipped:
        L.append("  excluded by policy: "
                 + ", ".join(f"{n} {k}" for k, n in sorted(skipped.items())))

    L.append("")
    L.append("WHAT WOULD CHANGE THE ANSWER")
    for line in _counterfactuals(cert, v, mar, m, eff):
        L.append(f"  - {line}")

    L.append("")
    L.append("SETTINGS IN EFFECT")
    for k in sorted(eff):
        L.append(f"  {k:<18} {str(eff[k]):<12} ({prov.get(k, '?')})")
    L.append("=" * 78)
    return "\n".join(L)


def _counterfactuals(cert, verdict, mar, m, eff):
    """The concrete list of things that would have produced a different verdict."""
    out = []
    gate = cert.get("sanitizer_gate") or {}
    if verdict == HONEST_FLAT:
        flat = cert.get("flat_observation") or {}
        r = flat.get("endpoint_ratio_vs_reference")
        if r and mar.get("margin"):
            need = 1.0 + mar["margin"]
            out.append(f"the fastest config measured {r:.4f}x and needed to exceed {need:.4f}x. "
                       f"That is a real gap, not a rounding one.")
        if m.get("rig_mode") == "portable":
            out.append("a quiesced rig would lower the bar: portable measurement widened the emit "
                       "margin because the noise it measured was larger. `sudo scripts/host_prep.sh`")
        out.append("a larger search may find something the budget did not reach: `--preset thorough`")
        if not eff.get("allow_fp_contract") and not eff.get("allow_fast_math"):
            out.append("floating-point configs were excluded by default. If your kernel tolerates "
                       "reassociation, `--allow-fp-contract` (or `--allow-fast-math`) widens the "
                       "candidate set — the oracle still has to pass.")
    elif verdict == NO_SAFE_IMPROVEMENT:
        out.append("a faster configuration EXISTS. It was refused, so the answer changes only when "
                   "the defect does — fix the kernel, then re-run.")
        out.append("`cytune audit` names which directives are unsafe here, deterministically.")
    else:
        out.append(f"nothing, unless the measurement was wrong: re-run to confirm "
                   f"({cert.get('speedup', 0):.4f}x had to clear {1 + mar.get('margin', 0):.4f}x "
                   f"AND show separated endpoint measurements).")
        out.append("`--apply` writes the emitted header for you; it refuses unless the gate was "
                   "CLEAN.")
    if gate.get("clean") is None:
        out.append("the §1.4 sanitizer gate did NOT run, so this recommendation is oracle-checked "
                   "but not memory-checked. `cytune doctor` says why.")
    return out


def _json_safe(obj):
    """Canonicalise to types that survive a JSON round-trip unchanged.

    `theta.as_dict` reports the composite `fmffp` factor as a TUPLE, which `json.dump` writes as an
    array and `json.load` reads back as a list — so the in-memory certificate and `certificate.json`
    were not the same object. The whole G6 claim is that every number recomputes FROM THE ARTIFACT,
    which requires the artifact to be the canonical form rather than a lossy projection of it.
    """
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


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
    # THE MAGNITUDE, not just the fact. Separation was reported as a bare yes, so a gap of 74 µs —
    # 0.2%, a tenth of this rig's own tau — read exactly like a gap of 40%. A reader deciding
    # whether to trust a headline speedup needs to know the guard passed by a hair. Found by the
    # novice-user agent (U3), on a run whose reference sub-measures spanned 36.9-49.2 ms.
    gap_ns = min(rs) - max(ws)
    gap_rel = (gap_ns / min(rs)) if min(rs) else None
    thin = sep and gap_rel is not None and gap_rel < TAU
    reason = ("every winner sub-measure beat every reference sub-measure" if sep else
              "the winner's and the reference's endpoint sub-measures OVERLAP — the "
              "apparent gain is not separable from measurement spread")
    if thin:
        reason += (f", but only by {gap_rel:.4%} ({gap_ns / 1e6:.3f} ms) — less than tau={TAU}, "
                   f"so the separation is real but THIN")
    elif sep:
        reason += f", by {gap_rel:.2%}"
    return {"separated": bool(sep),
            "winner_worst_ns": max(ws), "reference_best_ns": min(rs),
            "gap_ns": gap_ns, "gap_relative": gap_rel, "thin": bool(thin),
            "n_winner_subs": len(ws), "n_reference_subs": len(rs),
            "reason": reason}


# The endpoint protocol escalates while CV > 0.05, to at most 5 sub-measures. It can therefore END
# above the target, and nothing said so: a run whose reference CV finished at 0.1097 — twice the
# threshold — printed the protocol sentence unchanged, and a reader had to infer the escalation had
# been capped by counting `len(reference_subs_ns)`. Found by the novice-user agent (U4).
CV_TARGET = 0.05
MAX_SUBS = 5


def cv_of(rec):
    subs = [x for x in (rec or {}).get("subs_ns") or [] if x]
    if len(subs) < 2:
        return None
    mean = sum(subs) / len(subs)
    var = sum((x - mean) ** 2 for x in subs) / len(subs)
    return (var ** 0.5) / mean if mean else None


def escalation_status(win, ref):
    """Did the endpoint tier reach its own noise target, or run out of sub-measures?"""
    out = {"cv_target": CV_TARGET, "max_sub_measures": MAX_SUBS, "target_met": True,
           "capped": [], "cv": {}}
    for name, rec in (("winner", win), ("reference", ref)):
        cv = cv_of(rec)
        n = len([x for x in (rec or {}).get("subs_ns") or [] if x])
        out["cv"][name] = cv
        if cv is not None and cv > CV_TARGET:
            out["target_met"] = False
            out["capped"].append(
                {"which": name, "cv": cv, "n_sub_measures": n,
                 "note": (f"the {name}'s endpoint sub-measures ended at CV {cv:.4f}, above the "
                          f"{CV_TARGET} target"
                          + (f", after escalating to the {MAX_SUBS}-sub-measure cap"
                             if n >= MAX_SUBS else ""))})
    if not out["target_met"]:
        out["warning"] = (
            "the endpoint tier did NOT reach its noise target. The emit margin widens to "
            "compensate — that is what it is for — but the timings behind this verdict are "
            "noisier than the protocol intends, and a re-run on a quieter machine may answer "
            "differently.")
    return out


# C1 — RATIO CORROBORATION against the parent's own clock.
#
# `_measure_one` brackets the whole child process with `perf_counter_ns` in the PARENT. The child
# cannot reach that timer, so it is the one number in the system a driver cannot write. What it
# buys is not a second measurement of the kernel — the wall includes spawn, imports, warmup and
# per-rep input regeneration — but it is enough to check the CLAIM, because of what cancels.
#
#     wall  =  spawn + import + WARMUP*t + K*t + K*gen + misc
#     overhead := wall - K*median            (the non-timed remainder, directly observable)
#             =  spawn + import + WARMUP*t + K*gen + misc
#
# The winner and the reference run the SAME driver, the SAME K, the SAME inputs from the SAME seed,
# in the SAME image. Everything in that expression is identical between them except `WARMUP*t`. So
# the two overheads must differ by exactly WARMUP*(t_win - t_ref), and t is the very quantity being
# claimed. A driver that under-reports the winner by a factor f moves the observed difference by
# K*(f-1)*t instead — six times the size, and in the opposite direction.
#
# WHAT THIS CATCHES THAT THE OLD CHECK DID NOT. `worker.implausible_timings` compares K*median
# against the wall and fires only when the claim EXCEEDS the elapsed time. That is the over-claim
# half. This is two-sided: an under-claim (a driver reporting less time than it took, which is how
# you manufacture a speedup) shifts the remainder the same amount in the other direction.
#
# ITS POWER IS A CURVE, NOT A YES. For a true speedup r_true reported as r_claim, the unexplained
# fraction of the claimed gain is (1 + WARMUP/K) * (1/r_true - 1/r_claim) / (1 - 1/r_claim). That is
# (1 + WARMUP/K) whenever there is no real speedup at all, so ANY claim about a flat kernel — the
# demonstrated H1 attack — is caught with a factor of two to spare. Inflating an ALREADY-LARGE real
# gain is not: at this tolerance a genuine 2.5x may be reported as 5x. The boundary is tabulated in
# GUARANTEES N8 and pinned by test_cytune_binding.py rather than described here and left to drift.
#
# The tolerance cannot simply be tightened: an honest 9.85x run left 38% of its claimed gain
# unexplained, so a stricter budget would withhold real speedups.
#
# WHAT IT CANNOT CATCH AT ALL is in SECURITY.md and GUARANTEES N8: a driver that makes the
# reference GENUINELY slower — it can see which module it was handed — burns real wall clock, so
# every relation above holds and the certificate is a true statement about a rigged comparison.
CORROBORATION_TOL = 0.5        # at most half the claimed absolute gain may be unexplained
CORROBORATION_SIGMA = 3.0      # ...or 3 sigma of the run's OWN measured process-overhead spread
ENDPOINT_WARMUP = 5            # == campaign.WARMUP; pinned by test_cytune_binding.py


def _overhead_ns(rec, warmup=ENDPOINT_WARMUP):
    """Per-sub-measure non-timed remainder, and its robust spread."""
    subs = [x for x in (rec or {}).get("subs_ns") or [] if x]
    walls = [x for x in (rec or {}).get("wall_ns") or [] if x]
    k = (rec or {}).get("K")
    if not subs or not walls or not k or len(walls) < len(subs):
        return None
    oh = [w - k * m for w, m in zip(walls, subs)]
    oh_sorted = sorted(oh)
    med = oh_sorted[len(oh_sorted) // 2]
    mad = sorted(abs(x - med) for x in oh)[len(oh) // 2]
    return {"median_ns": med, "sigma_ns": 1.4826 * mad, "n": len(oh), "values_ns": oh,
            "warmup": warmup}


def _robust_sigma(values):
    """MAD-based sigma. Robust, because one slow spawn must not widen the budget for the whole run."""
    vals = [v for v in (values or []) if v is not None]
    if len(vals) < 4:
        return None
    s = sorted(vals)
    med = s[len(s) // 2]
    mad = sorted(abs(v - med) for v in vals)[len(vals) // 2]
    return 1.4826 * mad


def corroborate_ratio(win, ref, screen_overheads=None):
    """Does the parent's clock agree with the ratio the child reported? (C1)

    Returns a dict that always carries `corroborated`: True, False, or None when there is not
    enough parent-side data to decide (an older workspace, or a single sub-measure). None is not a
    pass and is reported as unavailable, in the same spirit as a sanitizer gate that did not run.
    """
    ow, orf = _overhead_ns(win), _overhead_ns(ref)
    if not ow or not orf:
        return {"corroborated": None, "reason": "the parent-side wall clock was not recorded for "
                                                "both configs, so the reported ratio could not be "
                                                "corroborated independently"}
    wm = (win or {}).get("endpoint_ns")
    rm = (ref or {}).get("endpoint_ns")
    k = (win or {}).get("K") or ENDPOINT_WARMUP
    if not wm or not rm:
        return {"corroborated": None, "reason": "no endpoint medians to corroborate"}

    predicted = ow["warmup"] * (wm - rm)          # expected oh_win - oh_ref
    observed = ow["median_ns"] - orf["median_ns"]
    residual = abs(observed - predicted)
    claimed_gain = k * abs(rm - wm)
    # THE NOISE FLOOR IS MEASURED, NOT CHOSEN. `wall - K x median` is a fixed per-process cost —
    # spawn, interpreter start, numpy import, the bootstrap CI — and it varies between processes by
    # an amount this run has already sampled dozens of times: `campaign.measure_all` records
    # `spawn_overhead_ns` for every config it screened, on this machine, this kernel and this
    # driver. Three sub-measures of within-config spread is a poor estimate of that; thirty screen
    # rows is a good one.
    #
    # This replaced a flat "5% of the overhead". The novice-user agent's honest 9.85x run passed
    # with 24% headroom under that constant, which is not the margin an honest run should have —
    # and the estimator it needed was already in the workspace, unused.
    sigma = max([s for s in (_robust_sigma(screen_overheads),
                             ow["sigma_ns"], orf["sigma_ns"]) if s] or [0.0])
    budget = max(CORROBORATION_TOL * claimed_gain, CORROBORATION_SIGMA * sigma)

    # A CHECK THAT CANNOT FAIL MUST NOT REPORT PASS.
    #
    # The largest residual any lie can produce is the r_true = 1 case, `(1 + warmup/K) x
    # claimed_gain`. When the noise floor alone is bigger than that — a small claimed gain on a
    # kernel with a large fixed per-process cost, e.g. a few hundred milliseconds of spawn overhead
    # at `--target-ms 5` — no fabrication could exceed the budget, so `corroborated: true` would
    # mean only "the arithmetic was performed". That is a check reporting its own inability as a
    # pass, which is the D23 lapse in miniature.
    #
    # Reported as unavailable instead, on the same rule as a sanitizer gate that could not run:
    # not-run is not a pass. Found by the focused adversarial re-run, which observed that C1 had no
    # lower cutoff.
    max_detectable = (1.0 + ow["warmup"] / k) * claimed_gain
    if budget >= max_detectable:
        return {"corroborated": None,
                "noise_sigma_ns": sigma, "n_overhead_samples": len(screen_overheads or []),
                "residual_ns": residual, "budget_ns": budget,
                "reason": (f"this run cannot corroborate a gain this small: the process-to-process "
                           f"overhead spread it measured ({CORROBORATION_SIGMA:.0f} sigma = "
                           f"{CORROBORATION_SIGMA * sigma / 1e6:.1f} ms) is larger than the "
                           f"largest discrepancy any misreport of a "
                           f"{claimed_gain / 1e6:.1f} ms gain could produce, so the check has no "
                           f"power here and passing it would mean nothing. The emit margin and the "
                           f"separation test still apply.")}
    ok = residual <= budget
    return {
        "corroborated": bool(ok),
        "noise_sigma_ns": sigma,
        "n_overhead_samples": len(screen_overheads or []),
        "reported_ratio": (rm / wm) if wm else None,
        "predicted_overhead_delta_ns": predicted,
        "observed_overhead_delta_ns": observed,
        "residual_ns": residual,
        "budget_ns": budget,
        "unexplained_fraction_of_claimed_gain": (residual / claimed_gain) if claimed_gain else None,
        "basis": (f"overhead := wall - K x median, measured by the PARENT process around each "
                  f"sub-measure. Winner and reference share spawn, imports, input generation and "
                  f"K, so their overheads must differ by exactly warmup x (t_win - t_ref) = "
                  f"{predicted / 1e6:.1f} ms; the run observed {observed / 1e6:.1f} ms. "
                  f"Residual {residual / 1e6:.1f} ms against a budget of {budget / 1e6:.1f} ms "
                  f"(the larger of {CORROBORATION_TOL:.0%} of the claimed gain and "
                  f"{CORROBORATION_SIGMA:.0f} sigma of the per-process overhead spread this run "
                  f"measured over {len(screen_overheads or [])} screened configs)."),
        "reason": ("the reported speedup is consistent with the time the parent process observed "
                   "elapsing" if ok else
                   f"the reported speedup is NOT consistent with the wall-clock time the parent "
                   f"observed: {residual / 1e6:.1f} ms of the claim is unexplained, against a "
                   f"budget of {budget / 1e6:.1f} ms. Either the driver is not reporting the time "
                   f"the kernel took, or the two configurations did not do the same work."),
    }


def assess(win, ref):
    """Would this winner actually be certified as an improvement? Decided BEFORE it is gated.

    WHY THIS IS A SEPARATE FUNCTION. The emit decision used to be made inside
    build_certificate, after the CLI had already gated the search's winner — so on a run where
    the winner failed to clear the margin, the certificate said "EMIT: the reference
    configuration (unchanged)" and then printed the WINNER's directives. On a live proof run that
    meant a certificate offering `boundscheck=False, wraparound=False` under the words "the
    reference configuration". A user pasting that would disable bounds checking on the strength
    of a sentence promising them Cython's safe defaults.

    Hoisting the decision here lets the CLI settle what it will emit first, then gate exactly
    that — which is also the only way the §1.4 gate can honestly describe the emitted config.
    """
    speedup = None
    if win and ref and win.get("endpoint_ns") and ref.get("endpoint_ns"):
        speedup = ref["endpoint_ns"] / win["endpoint_ns"]
    mar = emit_margin(win, ref)
    sep = endpoint_separation(win, ref)
    clears_margin = (speedup is not None) and ((speedup - 1.0) > mar["margin"])
    clears = bool(clears_margin and sep.get("separated"))
    if speedup is None:
        why = "the endpoint measurement did not produce a comparable time"
    elif not clears_margin:
        why = (f"the measured gain {speedup:.4f}x does not exceed the "
               f"{1 + mar['margin']:.4f}x bar this run could resolve ({mar['basis']})")
    elif not sep.get("separated"):
        why = sep.get("reason")
    else:
        why = "it cleared both the emit margin and the separation test"
    return {"speedup": speedup, "emit_margin": mar, "separation": sep,
            "clears_margin": bool(clears_margin), "clears": clears, "why": why}


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
                      flat_observation=None, winner_rejection=None, emitted_gate=None,
                      selection=None, probe_features=None, policy=None, has_fp_work=None,
                      effective_config=None, provenance=None, degeneracy=None,
                      screen_overheads=None, scoped_directives=None, search=None):
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
    # Since F19 both are opt-in, so reaching either state means the user asked for it.
    # THE EMITTED FLAG STRING IS THE GROUND TRUTH. theta.build_flags forces -ffp-contract=fast
    # whenever -ffast-math is on, so a fast-math config DOES permit contraction — reporting
    # `fma_contraction_permitted: False` next to a `gcc_flags` string containing
    # `-ffp-contract=fast` is the certificate contradicting itself, and a user scripting on the
    # JSON field would compile with contraction while the tool told them it was not permitted.
    # Found by the fresh-tester re-test.
    _contract_flag = bool(cfg) and theta.build_flags(cfg)[2] == "fast"
    uses_contract = bool(cfg and cfg[8][0] == "off" and cfg[8][1] == "fast")
    contract_implied_by_fast_math = bool(_contract_flag and uses_fm)

    cert = {
        "schema": SCHEMA,
        "cytune_version": __version__,
        "module": name,
        "routing_label": routing.LABEL,
        "glossary": GLOSSARY,
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
            "rejected_pattern": feasibility.get("pattern"),
            # PRECISE, because the previous wording implied more than the code does. Each
            # measurement subprocess canonicalises and hashes the FIRST repetition only
            # (_vendor/measure_child.py: `if out_hash is None`), then runs the remaining
            # repetitions untimed-for-correctness. So the endpoint tier's 3-5 sub-measures give
            # 3-5 independent oracle checks — one per fresh process, on freshly regenerated
            # inputs — not one per repetition. That is still strictly more than the screen tier's
            # single check, and it is what the guarantee is: stating "re-checked against the
            # oracle" without the scope was an overclaim of exactly the kind this project exists
            # to refuse. Found by the adversarial campaign (F3).
            "endpoint_recheck": (
                "the emitted config was re-measured at the endpoint tier; each of its 3-5 "
                "sub-measures is a fresh process whose FIRST repetition is canonicalised and "
                "checked against the golden output. A config that passes the screen but fails "
                "here is never emitted. Repetitions after the first in each process are timed but "
                "not output-checked."),
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
        # WHICH ENGINE PRODUCED THIS ANSWER. Two releases of cytune can emit different configs for
        # the same module because the search changed, and a certificate that does not say which
        # search ran leaves the reader unable to reproduce or compare it. `design_key` names the
        # screen design (or its absence), `prior` names what informed the design criterion.
        "search": search,
        "budget": budget,
        "selection": selection,
        "effective_config": effective_config,
        # I4 — the hashes every claim above is bound to. Always present, because a certificate that
        # omits its provenance is a certificate a reader has to take on trust, which is the state
        # this release exists to leave.
        "provenance": provenance,
        "factor_degeneracy": degeneracy,
        # Functions in the user's own source that pin a tuned directive with a decorator or a
        # `with` block. NOT a refusal — see session._CYTHON_SCOPED for the measurement that decided
        # that — but the emitted header does not reach them and the user has to be told which.
        "scoped_directives": scoped_directives,
        # C2 — WHAT THIS DOCUMENT ATTESTS, in the document. Certificates get forwarded; SECURITY.md
        # does not travel with them, so the one limit a third-party reader most needs is stated
        # here rather than only in a file they will never open.
        "attestation": ATTESTATION,
        # Always a dict, never None: a certificate that omits the consent state is a certificate
        # a reader has to guess about, and guessing is what this project is a record of. When no
        # policy object is supplied (older callers, unit tests) it is derived from the one flag
        # those callers had.
        "emission_policy": (policy.as_dict() if policy is not None else
                            {"allow_fast_math": bool(allow_fast_math),
                             "allow_fp_contract": False, "portable_flags": False,
                             "default_is_strict": True}),
        "fp_semantics": {
            "emitted_fp_semantics": (fp_semantics(winner_id) if winner_id is not None else None),
            # True whenever the EMITTED FLAGS permit it, however it got there.
            "fma_contraction_permitted": bool(_contract_flag),
            "fma_contraction_implied_by_fast_math": contract_implied_by_fast_math,
            "fma_contraction_selected_independently": uses_contract,
            "fast_math_permitted": uses_fm,
            # F21: the block used to fire on kernels with no floating-point code at all. This is a
            # HEURISTIC and is labelled as one: an int/bool output class with no float token in
            # the source is strong evidence there is no FP arithmetic to reorder, but a kernel
            # could compute in double and round to int on the way out. When unsure we show the
            # block — the failure direction of a warning is to over-warn, not to stay silent.
            "kernel_has_fp_work": has_fp_work,
            "fp_work_basis": ("oracle output class is float, or the module source declares a "
                              "float/double/complex type. Heuristic: a kernel that computes in "
                              "double and returns an int would read as no-FP-work here."),
            "note": (
                "the emitted config sets -ffast-math, which permits reassociation, assumes no "
                "NaNs or infinities, and ALSO implies -ffp-contract=fast (multiply-add fusion) — "
                "which is why that flag appears in the emitted string even though you did not "
                "pass --allow-fp-contract. You opted in with --allow-fast-math, and it was "
                "accepted only because it passed the oracle at the tolerance stated above."
                if contract_implied_by_fast_math else
                "the emitted config sets -ffp-contract=fast, permitting the compiler to fuse "
                "multiply-add pairs. This is NOT -ffast-math (no reassociation, no finite-math "
                "assumptions), but it does change floating-point results. You opted in with "
                "--allow-fp-contract, and it was accepted only because it passed the oracle at "
                "the tolerance stated above."
                if uses_contract else
                "-ffp-contract is explicit in the emitted flags (GCC's default is `fast`, so "
                "leaving it implicit would silently permit FMA contraction)."),
        },
        "fast_math": {
            "opted_in": bool(allow_fast_math),
            "emitted_config_uses_fast_math": uses_fm,
            "policy": ("every floating-point-semantics change is opt-in (--allow-fast-math for "
                       "-ffast-math, --allow-fp-contract for FMA contraction). Opting in changes "
                       "what is TRIED and what may be EMITTED; it never changes what is ACCEPTED "
                       "— such a config is emitted only if it passes the same oracle as "
                       "everything else"),
        },
        # F20: -march is a search factor and `native` is in it. A user pastes the emitted flags
        # into a build whose artifacts may run elsewhere; `native` hard-codes the compiling
        # machine's ISA and the binary can fault with SIGILL or be silently detuned.
        "portability": _portability(winner_id),
        "sources": sources,
        # Present only on the honest-flat route: the fastest config seen in the probe, measured at
        # the endpoint tier and deliberately NOT recommended. Reported so the run is transparent
        # about what it saw, without converting a selection-biased sample minimum into a claim.
        "flat_observation": flat_observation,
        # A config that the screen accepted and the endpoint refused. Recorded in the ARTIFACT, not
        # only printed: it is a correctness-relevant event and an auditor must be able to see it.
        # A reason of `not_built` here means an ORCHESTRATION bug, not an oracle rejection (D18).
        "winner_rejection": winner_rejection,
        # THE GATE ON THE CONFIG ACTUALLY EMITTED. Finding F5: after a sanitizer fallback the
        # certificate's `sanitizer_gate` described the config that was REJECTED, so the emitted
        # config's own status was never stated. G2 now holds with no asterisk: this field always
        # describes `emitted_config`, and if the gate was skipped it says so and why.
        "sanitizer_gate": emitted_gate or _gate_absent("the certificate was built without a gate "
                                                       "result for the emitted config"),
    }

    if probe_features:
        cert["probe_vs_endpoint"] = _probe_reconciliation(probe_features, speedup)

    if winner_id is None:
        # No feasible config at all. This path used to return here with no exit_code and an
        # un-downgraded "remains the best safe choice" — so it asserted safety for a configuration
        # nothing had gated, and would then have been refused by the coherence gate for having no
        # exit code. Found while replacing the prose scan with a field: the field made the branch
        # that never set it visible.
        cert["verdict"] = NO_SAFE_IMPROVEMENT
        cert["summary"] = ("No config was both faster and correct. The reference configuration "
                           "remains the best safe choice.")
        cert["safety_wording_earned"] = safety_wording_earned(emitted_gate)
        if not cert["safety_wording_earned"]:
            cert["summary"] = _downgrade_safety_claims(cert["summary"])
        cert["sanitizer_gate_ran"] = bool((emitted_gate or {}).get("ran"))
        cert["exit_code"] = EXIT_NO_SAFE_IMPROVEMENT
        return cert

    # INVARIANT: anything other than an improvement emits the REFERENCE, and the block that says
    # "the reference configuration (unchanged)" must therefore be printing the reference. The CLI
    # demotes a non-clearing winner before gating; this catches any future path that forgets to.
    if winner_id != reference_id and winner_rejection is not None:
        raise AssertionError("a rejected winner must have been replaced by the reference before "
                             "the certificate is built")

    cert["emitted_config"] = {
        "config_id": winner_id,
        "factors": _json_safe(theta.as_dict(cfg)),
        "directive_header": directive_header(cfg),
        "cython_x_flags": cython_x_flags(cfg),
        "gcc_flags": gcc_flags(cfg),
    }
    cert["speedup"] = speedup
    # F17: on the fallback path the "winner" IS the reference, so separation would compare the
    # reference against itself and report a vacuous "the sub-measures OVERLAP". That reads as a
    # measurement problem when there is none. Report the comparison only when there is one.
    self_compare = is_reference and winner_rejection is not None
    sep = ({"separated": None, "not_applicable": True,
            "reason": "the emitted config IS the reference (the faster candidate was refused), so "
                      "there is no winner-vs-reference comparison to make"}
           if self_compare else endpoint_separation(win, ref))
    cert["measurement"]["endpoint_separation"] = sep
    mar = emit_margin(win, ref)
    cert["measurement"]["emit_margin"] = mar
    cert["measurement"]["escalation"] = escalation_status(win, ref)
    # D-4. `screen_overheads` MUST be forwarded. The CLI gates on
    # `corroborate_ratio(win, ref, screen_overheads=...)` — the budget is the larger of half the
    # claimed gain and 3 sigma of the per-process overhead spread this run measured. Recomputing it
    # here without them silently used a DIFFERENT, smaller budget, so every certificate reported
    # "measured over 0 screened configs" while the gate had measured it over ~33, and a run whose
    # gate passed on the 3-sigma budget could write a document saying `corroborated: false`.
    # The document and the decision must come from the same inputs — the D-3 lesson, one layer up.
    cert["measurement"]["timing_corroboration"] = (
        {"corroborated": None, "not_applicable": True,
         "reason": "the emitted config IS the reference, so there is no ratio to corroborate"}
        if self_compare else corroborate_ratio(win, ref, screen_overheads=screen_overheads))
    clears_margin = (speedup is not None) and ((speedup - 1.0) > mar["margin"])

    # INVARIANT (I1.7 at its source). Anything that is not going to be certified as an improvement
    # is emitted as the REFERENCE, and `render` prints "the reference configuration (unchanged)"
    # for exactly those verdicts. So a non-clearing winner must have been demoted before we get
    # here, or the document says "reference" above a non-reference header — which is P2 verbatim.
    #
    # The CLI does demote (it has to, so the §1.4 gate can run on what is actually emitted). This
    # makes the contract structural instead of a property of one caller: the B2 property sweep
    # found that build_certificate would still assemble the lying document if any other path
    # forgot. Raising is right — there is no honest certificate to build from these arguments.
    if not is_reference and winner_rejection is None and not clears_margin:
        raise AssertionError(
            f"config {winner_id} does not clear the emit margin ({speedup!r} vs "
            f"{1 + mar['margin']:.4f}x) and must be demoted to the reference before the "
            f"certificate is built — otherwise the EMIT block claims the reference while printing "
            f"config {winner_id}'s directives (defect P2).")

    if winner_rejection is not None:
        # F4 — THE HIGHEST-VALUE FIX IN THE WHOLE ACCEPTANCE TEST. A faster config was found and
        # REFUSED. Calling that "honest-flat" tells the user their kernel has no headroom, which
        # is the opposite of what happened, and when the refusal came from the sanitizer it buries
        # a real memory-safety defect in their code under one reassuring word. "No headroom
        # exists" and "all the headroom was unsafe" are different answers and now have different
        # verdicts.
        cert["verdict"] = NO_SAFE_IMPROVEMENT
        cert["memory_safety_finding"] = _memory_finding(winner_rejection)
        cert["summary"] = _no_safe_summary(winner_rejection)
    elif is_reference or speedup is None or not clears_margin:
        cert["verdict"] = HONEST_FLAT
        cert["summary"] = _flat_summary(speedup, route, mar, flat_observation)
    elif not sep["separated"]:
        # Above the fixed floor, but the repeated measurements overlap. Selection over B configs
        # biases the apparent winner low; without separation this is not a defensible claim.
        cert["verdict"] = HONEST_FLAT
        cert["summary"] = (
            f"Measured {speedup:.3f}x, but {sep['reason']}. Tuning picks the fastest of many "
            f"measured configs, which biases that pick low on a flat landscape, so cytune will "
            f"not certify this as a speedup. Best safe config = the reference.")
    else:
        cert["verdict"] = IMPROVEMENT
        cert["summary"] = (f"{speedup:.3f}x faster than the reference configuration, verified at "
                           f"the endpoint tier and re-checked against the oracle.")

    # A sanitizer report on the EMITTED config. Found by a live run of the productised gate: with
    # the gate now applied to the fallback as well, a kernel whose *reference* reports leaves
    # cytune with nothing safe to hand back — and the old wording still called that emission "the
    # best safe choice", which is false. G2 says a reporting config is never emitted; when even
    # the baseline reports, the honest output is NO recommendation plus the defect, not a
    # reassuring sentence about a configuration that is also unsafe.
    emitted_reports = (emitted_gate or {}).get("clean") is False
    cert["emitted_config_unsafe"] = bool(emitted_reports)
    # The EMIT-NOTHING block below tells the user the shown configuration is "what you already
    # have". That is only true of the reference. The CLI gates the search's candidate FIRST and
    # falls back on a report, so a reporting non-reference config always arrives here as a
    # `winner_rejection`; this refuses the one shape that would make the block's wording false.
    if emitted_reports and not is_reference and winner_rejection is None:
        raise AssertionError(
            f"config {winner_id} was reported on by the sanitizer and is not the reference, but no "
            f"rejection was recorded. A reporting candidate must be refused and replaced by the "
            f"reference before the certificate is built (G2).")
    if emitted_reports:
        finding = _memory_finding(
            {"rejected_config_id": winner_id,
             "reason": f"sanitizer_report: {', '.join((emitted_gate or {}).get('tokens') or [])}",
             "on_emitted_config": True}, gate=emitted_gate)
        # A rejection finding, if there is one, describes a DIFFERENT config; keep both.
        if cert.get("memory_safety_finding") is None:
            cert["memory_safety_finding"] = finding
        else:
            cert["memory_safety_finding_emitted"] = finding
        cert["verdict"] = NO_SAFE_IMPROVEMENT
        cert["summary"] = (
            "cytune has NO SAFE RECOMMENDATION for this module. The sanitizer reported on the "
            "configuration that would have been emitted"
            + (" — and on the faster candidate that was already refused"
               if winner_rejection else "")
            + f" (config {winner_id}"
            + (", your reference/baseline settings" if is_reference else "")
            + "). Fix the defect below before tuning: a memory error at your baseline is not "
              "something a compiler flag can make safe.")
    # A gate that could not run degrades the guarantee, and the VERDICT LINE must carry that —
    # not only a section further down. A reader who stops after the summary, or a script reading
    # `verdict`, would otherwise see an unqualified "improvement" for a recommendation nobody
    # memory-checked. "The records said this passed without recording which checks produced that
    # verdict" is the sentence this whole project exists because of.
    # "Safe" requires a CLEAN gate FROM THE PINNED IMAGE. A clean result from an image supplied
    # via CYTUNE_SANITIZER_IMAGE is not a pass: cytune cannot know that image runs the same rig,
    # and the adversarial campaign turned a reporting kernel into `clean: true` with a stub (H6).
    _g = emitted_gate or {}
    # THE ONE FIELD that decides whether this document may call anything safe. Every renderer
    # branch and every summary reads it; the coherence gate checks it against the gate result; the
    # renderer tests check the wording against it. Previously the same condition was re-derived at
    # four sites and the rendered text was searched for phrases to catch the drift.
    cert["safety_wording_earned"] = safety_wording_earned(emitted_gate)
    if not cert["safety_wording_earned"]:
        cert["summary"] = _downgrade_safety_claims(cert["summary"])
    if _g.get("image_overridden"):
        cert["sanitizer_gate_authoritative"] = False
        cert["summary"] += (
            f"  [NOTE: the §1.4 gate ran against {_g.get('image')!r}, which is NOT the pinned "
            f"image. A result from an unpinned image is not treated as a pass; --apply refuses.]")
    if (emitted_gate or {}).get("clean") is None and winner_id is not None:
        cert["sanitizer_gate_ran"] = False
        # Recorded as a field AND appended to the summary. I1.5 checks the summary carries exactly
        # this string, which is an exact test instead of a pattern guessing at the wording.
        cert["sanitizer_gate_qualification"] = (
            "  [NOTE: the §1.4 sanitizer gate did NOT run "
            f"({(emitted_gate or {}).get('verdict', 'no gate result')}), so this configuration is "
            "oracle-checked but NOT memory-checked. Not-run is not a pass — see `cytune doctor`.]")
        cert["summary"] += cert["sanitizer_gate_qualification"]
    else:
        cert["sanitizer_gate_ran"] = bool((emitted_gate or {}).get("ran"))
    cert["exit_code"] = EXIT_BY_VERDICT.get(cert["verdict"], EXIT_ERROR)
    return cert


# The word "safe" is earned by a CLEAN §1.4 gate and by nothing else. Several summary strings end
# with "Best safe config = the reference", which is right when the gate cleared and an overclaim
# when it did not run — the same document asserting safety in one paragraph and withdrawing it in
# the next. Rewritten in ONE place rather than at each of the six sites, because a rule that lives
# in more than one place drifts (D11, D22). Caught by the I1.6 property sweep.
_SAFETY_DOWNGRADES = (
    ("Best safe config = the reference.",
     "Best config found = the reference (not memory-checked)."),
    ("remains the best safe choice.",
     "remains the best cytune found; it was not memory-checked."),
    ("is the best safe choice.",
     "is the best cytune found; it was not memory-checked."),
)


def safety_wording_earned(gate):
    """May a document describing this gate result call the configuration safe?

    CLEAN, from the PINNED image, and nothing else. Not-run is not a pass (D23) and a clean verdict
    from an image that is not the pinned one is not a pass either (H6).
    """
    g = gate or {}
    return bool(g.get("clean") is True and not g.get("image_overridden"))


def _downgrade_safety_claims(summary):
    for claim, honest in _SAFETY_DOWNGRADES:
        summary = (summary or "").replace(claim, honest)
    return summary


def _gate_absent(reason):
    return {"ran": False, "clean": None, "verdict": "NOT_RUN",
            "note": f"emitted config not gated: {reason}",
            "warning": "NOT RUN IS NOT A PASS — the emit decision rests on the oracle alone, and "
                       "an output oracle cannot see a read that produced a correct answer (D23).",
            "rule": "roadmap §1.4 / PREREG §301"}


def _portability(winner_id):
    if winner_id is None:
        return None
    m = march_of(winner_id)
    if m != "native":
        return {"march": m, "portable": True,
                "note": f"-march={m} targets a baseline ISA; the emitted flags are safe to use on "
                        f"machines other than this one."}
    return {"march": m, "portable": False,
            "note": ("-march=native hard-codes THIS machine's instruction set into the build. A "
                     "binary compiled with these flags may fault with an illegal instruction, or "
                     "be silently detuned, on any other CPU. If your build artifacts run anywhere "
                     "else, re-run with --portable-flags to get a recommendation restricted to "
                     f"-march={BASELINE_MARCH}, and re-measure."),
            "remedy_flag": "--portable-flags"}


def _memory_finding(rejection, gate=None):
    """The prominent block for a memory-safety defect found in the USER's kernel."""
    reason = (rejection or {}).get("reason") or ""
    if not reason.startswith("sanitizer_report"):
        return None
    summary = reason.split("sanitizer_report:", 1)[-1].strip()
    return {
        "found": True,
        "config_id": rejection.get("rejected_config_id"),
        "sanitizer_summary": summary,
        "observed_ratio": rejection.get("observed_ratio"),
        "on_emitted_config": bool(rejection.get("on_emitted_config")),
        "report_path": (rejection.get("report_path") or (gate or {}).get("report_path")),
        "explanation": (
            "This is a latent bug in YOUR kernel, not a cytune limitation. It only manifests when "
            "boundscheck/wraparound are disabled, and the output check could not see it: a "
            "reduction absorbs one garbage element without changing the answer, so the result was "
            "correct while the read was illegal. Fix the indexing before disabling those "
            "directives yourself — including by hand."),
        "provenance": ("this is the exact failure mode of defect D23, where 1,296 configs that "
                       "read out of bounds were recorded as feasible because their output "
                       "happened to be right. See logs/defects/D23.md."),
        # C2. `tune` gates two configs out of 1,728 — the search's best candidate and the emitted
        # one — so WHICH directive is unsafe depends on where the search landed. `audit` answers
        # that deterministically over a pre-registered risk set.
        "next_step": AUDIT_POINTER,
    }


# One sentence, defined once, used by the finding block, the no-safe summary and the rendered
# certificate — so the three cannot drift into three different recommendations.
AUDIT_POINTER = ("Run `cytune audit <module.pyx> --driver <driver.py>` to find out WHICH directives "
                 "are unsafe for this kernel. `tune` gates the configuration it was about to "
                 "recommend; `audit` checks a pre-registered risk set and gives the same answer "
                 "every run.")


def _no_safe_summary(rejection):
    reason = (rejection or {}).get("reason") or "the candidate did not confirm at the endpoint"
    ratio = (rejection or {}).get("observed_ratio")
    fast = f"{ratio:.3f}x faster " if ratio else ""
    if reason.startswith("sanitizer_report"):
        return (f"A faster configuration exists and cytune REFUSES to recommend it. Config "
                f"{rejection.get('rejected_config_id')} was {fast}and the sanitizer reported on "
                f"it. Your kernel is NOT flat — its headroom is unsafe. Best safe config = the "
                f"reference. {AUDIT_POINTER}")
    return (f"A faster configuration was found and rejected at the endpoint tier "
            f"({reason}). Your kernel is not flat; the candidate simply did not hold up. "
            f"Best safe config = the reference.")


def _probe_reconciliation(feat, speedup):
    """F8: the console prints `delta_probe = 2.65` and the certificate says `1.27x`, with nothing
    connecting them. Two numbers from two measurement tiers is not a contradiction, but a user has
    no way to know that."""
    d = feat.get("delta_probe")
    if d is None:
        return None
    return {
        "delta_probe": d,
        "endpoint_speedup": speedup,
        "why_they_differ": (
            "delta_probe is a SCREENING-tier ratio: one fast measurement of each of 17 configs, "
            "slowest over fastest, and the fastest is a sample minimum so it is biased low. The "
            "speedup is an ENDPOINT-tier median-of-3 at K=30 of the emitted config against the "
            "reference, and it had to clear the separation test and the emit margin. They are "
            "measured differently and only the endpoint number is claimed. delta_probe being "
            "much larger is normal and is not evidence of a lost speedup — it is what a noisy "
            "sample minimum looks like."),
    }


def _flat_summary(speedup, route, margin=None, observation=None):
    if route.get("route") == routing.HONEST_FLAT:
        return ("No worthwhile speedup found — the probe spread sat at or below this rig's noise "
                "floor. Best safe config = the reference. This is a real answer, not a failure: "
                "on real code a flat landscape is the common case.")
    # When the search's winner was demoted, `speedup` is 1.0 (reference vs reference) and quoting
    # it would understate what was actually seen. The observation carries the real ratio.
    observed = (observation or {}).get("endpoint_ratio_vs_reference") or speedup
    got = f"only {observed:.4f}x" if observed else "no measurable gain"
    bar = (f", below the {1 + margin['margin']:.4f}x bar this run could actually resolve "
           f"({margin['basis']})") if margin else ", which is within measurement noise"
    return (f"Tuning ran but found {got} over the reference{bar}. "
            f"Best safe config = the reference.")


def _wrap(text, indent="  ", width=96):
    words, line, out = text.split(), indent, []
    for w in words:
        if len(line) + len(w) + 1 > width and line.strip():
            out.append(line)
            line = indent + w
        else:
            line = (line + " " + w) if line.strip() else line + w
    if line.strip():
        out.append(line)
    return out


def next_step(cert):
    """One sentence for a human, printed ABOVE the certificate: what to do next.

    C3. The certificate is a document for someone who wants the evidence; it opens with a verdict
    token and a table. A first-time user's actual question is "so what do I do?", and answering it
    after two screens of provenance is answering it too late.

    A pure function of the document, so it cannot say something the certificate does not support,
    and so the wording is testable without a run. It is NOT part of the rendered certificate --
    the document is unchanged and `certificate.txt` still round-trips from `certificate.json`.
    """
    v = cert.get("verdict")
    emitted = (cert.get("emitted_config") or {}).get("config_id")
    is_ref = emitted == theta.REFERENCE_ID or emitted is None
    gate = cert.get("sanitizer_gate") or {}
    finding = cert.get("memory_safety_finding") or cert.get("memory_safety_finding_emitted")
    speed = cert.get("speedup")

    if finding:
        # Ordering is a judgement and it is deliberate: a memory-safety report outranks every
        # performance statement in the document, including a good one.
        return ("WHAT TO DO: fix the memory-safety bug below before anything else. cytune rebuilt "
                "your kernel under AddressSanitizer and it read memory it does not own. No speed "
                "recommendation is worth acting on until that is fixed.")
    if v == IMPROVEMENT:
        line = (f"WHAT TO DO: paste the directive header below into your .pyx and build with the "
                f"gcc flags shown — measured {speed:.3f}x faster than your current settings."
                if speed else
                "WHAT TO DO: paste the directive header below into your .pyx and build with the "
                "gcc flags shown.")
        if cert.get("safety_wording_earned") is False:
            line += (" NOTE: the memory-safety gate did not run authoritatively on this machine, "
                     "so the speed claim stands and the safety claim does not.")
        return line
    if v == HONEST_FLAT:
        return ("WHAT TO DO: nothing — keep your current settings. cytune measured the space and "
                "found no configuration reliably faster than what you already have. That is a "
                "real answer, not a failure.")
    if v == NO_SAFE_IMPROVEMENT:
        if is_ref:
            return ("WHAT TO DO: keep your current settings. cytune found a faster candidate but "
                    "could not stand behind it — the reason is in the REJECTED block below.")
        return ("WHAT TO DO: keep your current settings. cytune has no recommendation it can "
                "support for this kernel.")
    return "WHAT TO DO: read the verdict below; cytune has no short answer for this outcome."


def render(cert):
    """Human-readable certificate — what the user actually reads in the terminal."""
    L = []
    add = L.append

    def para(text, indent="  "):
        L.extend(_wrap(text, indent))

    add("=" * 78)
    add(f"cytune certificate — {cert['module']}   [{cert.get('cytune_version', '?')}]")
    para(cert["routing_label"])
    add("=" * 78)
    add("")
    v = cert["verdict"]
    add(f"VERDICT: {v.upper()}")
    para(cert["summary"])
    add("")

    # ---- the loudest thing in the document, deliberately placed above the recommendation ----
    findings = [f for f in (cert.get("memory_safety_finding"),
                            cert.get("memory_safety_finding_emitted"))
                if f and f.get("found")]
    if findings:
        add("!" * 78)
        add(f"!! cytune found {'a' if len(findings) == 1 else len(findings)} MEMORY-SAFETY "
            f"DEFECT{'' if len(findings) == 1 else 'S'} in your kernel.")
        add("!" * 78)
        for mf in findings:
            ratio = mf.get("observed_ratio")
            if mf.get("on_emitted_config"):
                add(f"  config {mf['config_id']} — the configuration that would have been "
                    f"EMITTED, i.e.")
                add("  your own baseline settings — was REPORTED ON by the sanitizer:")
            else:
                add(f"  config {mf['config_id']}"
                    + (f" was {ratio:.3f}x faster and" if ratio else "")
                    + " was REFUSED by the sanitizer:")
            add(f"    {mf['sanitizer_summary']}")
            if mf.get("report_path"):
                add(f"    full report: {mf['report_path']}")
            add("")
        para(findings[0]["explanation"])
        add("")
        para(findings[0]["provenance"])
        add("")

    if cert["emitted_config"] and v == IMPROVEMENT:
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
        _esc = m.get("escalation") or {}
        if _esc.get("warning"):
            for _c in _esc.get("capped", []):
                add(f"  !! {_c['note']}")
            for _l in _wrap(_esc["warning"], "     "):
                add(_l)
        sep = m.get("endpoint_separation") or {}
        if sep.get("reason"):
            add(f"  separation: {sep['reason']}")
        # Every other gate in this document states its own criterion inline ("gain had to exceed
        # X", "every winner sub-measure beat every reference sub-measure"). This one printed a
        # percentage and a budget and left the reader to compare them — the single place in an
        # otherwise self-explaining certificate that required arithmetic. Found by the novice-user
        # agent, who had to do it.
        cor = m.get("timing_corroboration") or {}
        if cor.get("corroborated") is True:
            add(f"  wall-clock corroboration: PASS — {cor['residual_ns'] / 1e6:.1f} ms of the "
                f"claimed gain is unaccounted for by the parent process's own clock, and it had to "
                f"stay under {cor['budget_ns'] / 1e6:.1f} ms")
        elif cor.get("corroborated") is None and not cor.get("not_applicable"):
            add(f"  wall-clock corroboration: NOT CHECKED — {cor.get('reason')}")
        mar = m.get("emit_margin") or {}
        if mar.get("basis"):
            add(f"  emit margin: gain had to exceed {mar['margin']:.4f} — {mar['basis']}")
            add("               (product rule, not a pre-registered study threshold)")
        add("")
    elif cert["emitted_config"] and cert.get("emitted_config_unsafe"):
        add("EMIT: NOTHING. cytune has no safe configuration to recommend for this module.")
        para("The configuration below is what you already have, and the sanitizer reported on it "
             "too. It is shown so you know exactly what was checked — it is NOT a recommendation, "
             "and it is NOT certified safe.")
        add(f"  {cert['emitted_config']['directive_header']}")
        add(f"  {cert['emitted_config']['gcc_flags']}")
        add("")
    elif cert["emitted_config"]:
        # "Safe" is the word a user scans for, so it is earned by a CLEAN gate and by nothing else.
        # With the gate not run this line used to assert "the best safe choice" while the summary
        # further down said the configuration was never memory-checked — the same document making
        # and withdrawing the claim. The condition now lives in ONE field rather than being
        # re-derived here, which is what lets the renderer tests check the wording exhaustively.
        if cert.get("safety_wording_earned"):
            add("EMIT: the reference configuration (unchanged) is the best safe choice.")
        else:
            add("EMIT: the reference configuration (unchanged). cytune found nothing better.")
            add("      This configuration was NOT memory-checked — the §1.4 sanitizer gate did "
                "not run,")
            add("      so it is not certified safe, only unimproved. Not-run is not a pass.")
        add(f"  {cert['emitted_config']['directive_header']}")
        add(f"  {cert['emitted_config']['gcc_flags']}")
        add("")

    port = cert.get("portability") or {}
    if port and not port.get("portable", True):
        add("PORTABILITY WARNING — the emitted flags are NOT machine-independent")
        para(port["note"])
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
    frac = (f" ({c['infeasible_fraction']:.1%} of measured)"
            if c["infeasible_fraction"] is not None else "")
    add(f"  rejected as incorrect : {c['configs_rejected_infeasible']}{frac}")
    if c["rejected_reasons"]:
        for reason, n in sorted(c["rejected_reasons"].items(), key=lambda kv: -kv[1]):
            add(f"      {n:>4}  {reason}")
    pat = c.get("rejected_pattern")
    if pat and pat.get("shared_factor_levels"):
        add("      all " + str(pat["n"]) + " share: "
            + ", ".join(f"{k}={v}" for k, v in sorted(pat["shared_factor_levels"].items())))
        para(pat["note"], indent="      ")
    add(f"  endpoint re-check     : {c['endpoint_recheck']}")
    sel = cert.get("selection") or {}
    if sel.get("n_feasible_measured") is not None:
        add(f"  emittable candidates  : {sel['n_candidates']} of "
            f"{sel['n_feasible_measured']} feasible "
            f"({sel['n_excluded_by_policy']} excluded by policy"
            + (": " + ", ".join(f"{k}={n}" for k, n in sorted(sel["excluded_by_reason"].items()))
               if sel.get("excluded_by_reason") else "") + ")")
    add("")

    # --- the emitted config's OWN memory-safety status, always stated (F5) ---
    sg = cert.get("sanitizer_gate") or {}
    add("SANITIZER GATE (on the config being emitted)")
    if sg.get("clean") is True:
        add(f"  CLEAN — config {sg.get('config_id')} was rebuilt under ASan+UBSan and ran with no "
            f"report.")
        para("A clean gate is not proof of memory safety: it means no error was detected on the "
             "inputs your driver generated, for this one configuration.", indent="  ")
    elif sg.get("clean") is False:
        add(f"  REPORTED — config {sg.get('config_id')}: {', '.join(sg.get('tokens') or [])}")
    else:
        add(f"  NOT RUN ({sg.get('verdict')}) — **NOT RUN IS NOT A PASS**")
        if sg.get("note"):
            para(sg["note"], indent="    ")
        para("The emit decision rests on the output oracle alone, and an output oracle cannot "
             "see a read that produced a correct answer. That is exactly defect D23.", indent="  ")
    add("")

    m = cert["measurement"]
    add("RIG MODE")
    add(f"  {m['rig_mode']}: {m['rig_statement']}")
    add("")

    # I4 — the hashes. Deliberately above ROUTING: what the claims are bound to matters more than
    # which rule chose the budget.
    from . import binding as _binding
    prov_lines = _binding.render_provenance(cert.get("provenance"))
    if prov_lines:
        L.extend(prov_lines)
        add("")

    scoped = cert.get("scoped_directives") or {}
    if scoped:
        names = sorted({n for d in scoped.values() for n in d})
        add("DIRECTIVES YOUR SOURCE PINS ITSELF — the emitted header does not reach these")
        para(f"{', '.join(names)} " + ("is" if len(names) == 1 else "are") +
             " fixed by a decorator or a `with` block inside your module. Cython honours those "
             "over the -X flags cytune builds with, so for the functions they cover the emitted "
             "header changes nothing — including where it says the reference is Cython's safe "
             "defaults. The rest of the module is unaffected and was tuned normally.")
        for rel in sorted(scoped)[:6]:
            for d, where in sorted(scoped[rel].items()):
                add(f"    {rel}: {d} — {where}")
        add("")

    deg = cert.get("factor_degeneracy") or {}
    if deg.get("directives_inert"):
        add("FACTOR DEGENERACY — directives that do nothing to THIS kernel")
        para(f"{', '.join(deg['directives_inert'])} never changed the generated C in any pair of "
             f"configurations this run built that differed only in it. Turning them off cannot "
             f"make your kernel faster, and cytune did not claim it would. "
             f"{deg.get('basis', '')}")
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
    # F21: only speak about floating-point semantics when the emitted config actually changes
    # them AND the kernel plausibly has floating-point work to change.
    changes_fp = fp.get("fma_contraction_permitted") or fp.get("fast_math_permitted")
    implied = fp.get("fma_contraction_implied_by_fast_math")
    if changes_fp and fp.get("kernel_has_fp_work") is not False:
        add("FLOATING-POINT SEMANTICS")
        para(fp["note"])
        add("")
    elif changes_fp:
        add("FLOATING-POINT SEMANTICS")
        para(f"{fp['note']} (Your oracle's output class is integral and no floating-point type "
             f"was found in the module source, so this most likely has no effect on your "
             f"results — but the flag is in the emitted build either way.)")
        add("")

    fm = cert["fast_math"]
    ep = cert.get("emission_policy") or {}
    opted = [n for n, k in (("--allow-fast-math", "allow_fast_math"),
                            ("--allow-fp-contract", "allow_fp_contract")) if ep.get(k)]
    if not opted:
        add("FLOATING-POINT CONSENT: strict (default). No config that changes floating-point")
        add("  semantics — neither -ffast-math nor FMA contraction — was eligible for emission.")
    else:
        # WHERE the consent came from, not just which setting it was. The line used to name
        # `--allow-fast-math` whenever the effective policy had it on — including when it came from
        # a `.cytune.toml` in an ancestor directory the user may not have known about, or from a
        # preset. Consent is the one thing that must never be misattributed: a reader deciding
        # whether to trust an FP-relaxed result needs to know it was a file, not their own
        # keystroke. `effective_config.provenance` had it right all along; this line now reads it.
        # (S1, adversarial campaign.)
        prov = (cert.get("effective_config") or {}).get("provenance") or {}
        srcs = {"--allow-fast-math": prov.get("allow_fast_math"),
                "--allow-fp-contract": prov.get("allow_fp_contract")}
        parts = []
        for flag in opted:
            where = srcs.get(flag)
            parts.append(f"{flag}" + (f" (from {where})" if where and where != "command line"
                                      else ""))
        add(f"FLOATING-POINT CONSENT: opted in via {', '.join(parts)}; emitted semantics = "
            f"{fp.get('emitted_fp_semantics')}")
        if any(w and w not in ("command line", "built-in default") for w in srcs.values()):
            para("NOTE: that opt-in did NOT come from the command line you typed. It came from the "
                 "source named above — check it if you did not intend to relax floating-point "
                 "semantics.")
        if implied:
            para("NOTE: -ffast-math subsumes FMA contraction, so the emitted flags contain "
                 "-ffp-contract=fast even though --allow-fp-contract was not passed. That is a "
                 "restatement of what -ffast-math already permits, not a second undisclosed "
                 "change — but if you need contraction OFF, do not use --allow-fast-math.")
    para(fm["policy"])
    add("")

    pv = cert.get("probe_vs_endpoint")
    if pv and pv.get("delta_probe") is not None:
        add("WHY THE PROBE NUMBER AND THE SPEEDUP DIFFER")
        add(f"  delta_probe {pv['delta_probe']:.4f}   ->   endpoint speedup "
            + (f"{pv['endpoint_speedup']:.4f}" if pv.get("endpoint_speedup") else "none claimed"))
        para(pv["why_they_differ"])
        add("")

    g = cert.get("glossary") or {}
    if g:
        add("GLOSSARY — every term above, defined here so you need no other document")
        for term in sorted(g):
            L.extend(_wrap(f"{term}: {g[term]}", indent="    "))
        add("")

    att = cert.get("attestation") or {}
    if att:
        add("WHAT THIS CERTIFICATE ATTESTS")
        para(f"IT ATTESTS {att['attests']}")
        add("")
        para(f"IT DOES NOT ATTEST {att['does_not_attest']}")
        add("")
        if att.get("does_not_attest_artifact"):
            para(f"IT DOES NOT ATTEST {att['does_not_attest_artifact']}")
            add("")
        para(att["audience"])
        add("")

    add("RAW: every number above recomputes from " + cert["sources"]["table"])
    add(f"EXIT CODE: {cert.get('exit_code')}  "
        f"(0 improvement, 2 honest-flat, 3 no-safe-improvement, 1 error)")
    add("=" * 78)
    return "\n".join(L)
