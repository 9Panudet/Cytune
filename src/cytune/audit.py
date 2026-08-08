"""`cytune audit` — deterministic memory-safety audit of the risky directive corners.

WHY THIS EXISTS: K6, measured and then fixed rather than left as a caveat.

`cytune tune` gates the search's best candidate and the config it emits — two configurations out of
1,728. That is enough to guarantee it never EMITS something the sanitizer reported on, which is
guarantee G2. It is not enough to FIND a latent bug: across five runs of the same out-of-bounds
fixture the defect was reported in three, because the DOE walk's winner varied between runs. So the
product's most valuable capability — finding the memory bug your tests cannot see — depended on
where a search happened to land.

`audit` removes the search from the loop. It does not tune, does not time anything, and needs no
quiesced rig. It builds a PRE-REGISTERED set of configurations under AddressSanitizer +
UndefinedBehaviorSanitizer and runs your driver on each. Same kernel, same set, same verdict, every
run.

WHY THE RISK SET IS NOT JUST "THE FIVE DIRECTIVES, ONE AT A TIME".

That was the obvious design and it would have missed D23 — the defect this whole tool exists to
catch. D23's mechanism needs TWO directives off together:

    boundscheck=False, wraparound=True   ->  a[-1] is rewritten to a[n-1]. In bounds. Legal.
    boundscheck=True,  wraparound=False  ->  a[-1] raises IndexError before it can read.
    boundscheck=False, wraparound=False  ->  a[-1] reads one element BEFORE the buffer. The bug.

Neither single flip exposes it; only the pair does. The risk set therefore includes the pair
explicitly, and `test_cytune_audit.py` pins that it does — because a risk set that cannot catch the
defect that motivated the feature is decoration.

HONEST SCOPE, which the report states in these words: `audit` checks the configurations in this
set, on the inputs your driver generates. A clean audit is not a proof of memory safety (N1 in
docs/GUARANTEES.md still applies). What it gives you is a DETERMINISTIC answer to a narrower and
much more useful question: for this kernel, which of these directives is it actually safe to turn
off?
"""
from __future__ import annotations

import os

from . import __version__, SCHEMA_VERSION
from ._vendor import theta

SCHEMA = f"cytune-audit/{SCHEMA_VERSION}"

# Exit codes. Deliberately aligned with `tune`'s scheme: 0 means "the answer is yes, go ahead",
# 3 means "cytune is refusing something / found something you must look at", 1 means it could not
# answer. An audit that could not run is an ERROR, never a pass — the same rule as the not-run
# sanitizer gate in `tune`.
EXIT_CLEAN = 0
EXIT_ERROR = 1
EXIT_DEFECTS_FOUND = 3

CLEAN = "clean"
DEFECTS_FOUND = "defects-found"
INCOMPLETE = "incomplete"

_REF = theta.REFERENCE
_BC, _WA, _CD, _IC, _NC, _OPT, _MARCH, _FUN, _FMFFP = range(9)


def _flip(**kw):
    """A config that is the reference with the named factors changed."""
    cfg = list(_REF)
    idx = {"boundscheck": _BC, "wraparound": _WA, "cdivision": _CD,
           "initializedcheck": _IC, "nonecheck": _NC}
    for k, v in kw.items():
        cfg[idx[k]] = v
    return tuple(cfg)


# The pre-registered risk set. Fixed at release; not a function of anything measured, so the audit
# is a pure function of (kernel, driver).
#
# `directive` names the directive whose safety this row decides, or None for rows that exist to
# establish context (the reference) or to cover the realistic worst case (the study's corners).
RISK_SET = [
    ("reference", _REF, None,
     "Cython's safe defaults. If THIS reports, the defect is in your kernel as written and has "
     "nothing to do with tuning."),

    ("boundscheck_off", _flip(boundscheck=False), "boundscheck",
     "bounds checking removed. An index past the end becomes a real out-of-bounds access."),

    ("wraparound_off", _flip(wraparound=False), "wraparound",
     "negative-index rewriting removed. a[-1] stops meaning a[n-1]."),

    ("cdivision_on", _flip(cdivision=True), "cdivision",
     "C division semantics: no zero-division check, and C's truncation for negative operands."),

    ("initializedcheck_off", _flip(initializedcheck=False), "initializedcheck",
     "memoryview initialisation checking removed."),

    # THE D23 PAIR. Not derivable from the singles — see the module docstring.
    ("boundscheck_and_wraparound_off", _flip(boundscheck=False, wraparound=False),
     "boundscheck+wraparound",
     "both off together. This is the D23 combination: the only one under which a[-1] reads before "
     "the start of the buffer. Neither single flip can expose it."),

    # The realistic worst case a tuner would actually pick, and the study's own pre-registered
    # corners. Imported from the vendored sanitizer rig so the two cannot diverge.
    ("all_checks_off_O3_native", (False, False, True, False, False, "-O3", "native", "on",
                                  ("off", "off")), None,
     "every check off at -O3 -march=native -funroll-loops: the corner a tuner is most likely to "
     "select, and the one the Phase-P study audits."),

    ("all_checks_off_fastmath", (False, False, True, False, False, "-O3", "native", "on",
                                 ("on", "NA")), None,
     "the same corner with -ffast-math, in case the defect is reached only under FP reassociation."),
]

DIRECTIVES = ["boundscheck", "wraparound", "cdivision", "initializedcheck"]

# `nonecheck` is the fifth Cython directive cytune varies and is deliberately NOT in the risk set.
# The reference config already has it OFF (theta.REFERENCE = (..., nonecheck=False)), so there is
# no "disable it" direction to audit — flipping it from the reference turns a check ON, which can
# only make the build stricter. Stated here and in the report because its absence from the
# "IS IT SAFE TO DISABLE" table was noticed and had no explanation. (U14, novice-user agent.)
NOT_AUDITED = {
    "nonecheck": ("already off at the reference config, so there is no 'disable' direction to "
                  "test. Turning it ON only adds checks."),
}

SAFE = "safe to disable"
UNSAFE = "UNSAFE to disable"
UNKNOWN = "unknown (the gate did not run)"

# Outcome states. `clean` from the gate is three-valued (True/False/None), which is right for an
# emission decision but too coarse for an audit REPORT: it folds "your kernel raised an exception in
# this configuration" together with "the pinned image was missing", and those are opposite kinds of
# news. The first is a finding about the user's code; the second is a hole in the audit.
#
# RUN_FAIL_NO_TOKEN is the study's own name for "the process failed with no sanitizer token", and
# the Phase-P sanitizer controls PRE-REGISTER it as the expected result for the planted
# out-of-bounds kernel at the reference config: with boundscheck ON, Cython raises IndexError
# before the illegal read can happen. Reporting that as "NOT RUN" hides the single most useful
# thing the audit learned about that directive.
OK = "clean"
REPORTED = "reported"
RAISED = "raised"
NOT_RUN = "not-run"
BUILD_FAIL = "build-fail"

_RAISED_VERDICTS = {"RUN_FAIL_NO_TOKEN"}
_BUILD_VERDICTS = {"BUILD_FAIL"}


def outcome_of(gate):
    """Map a gate result onto the audit's five outcome states."""
    clean = (gate or {}).get("clean")
    verdict = (gate or {}).get("verdict")
    if clean is True:
        return OK
    if clean is False:
        return REPORTED
    if verdict in _RAISED_VERDICTS:
        return RAISED
    if verdict in _BUILD_VERDICTS:
        return BUILD_FAIL
    return NOT_RUN


# Which outcomes are evidence about a directive, and in which direction. RAISED counts as UNSAFE:
# a kernel that throws in a configuration is a kernel that cannot use that configuration, whatever
# the reason. BUILD_FAIL and NOT_RUN are absence of evidence and must never read as safety.
_EVIDENCE = {OK: "safe", REPORTED: "unsafe", RAISED: "unsafe",
             BUILD_FAIL: None, NOT_RUN: None}

# What the audit is and is not, in the report itself, so the number cannot be over-read.
SCOPE_NOTE = (
    "This audit rebuilt your kernel in the configurations listed above under AddressSanitizer + "
    "UndefinedBehaviorSanitizer and ran YOUR driver on each. It is deterministic: the set is "
    "pre-registered, so the same kernel gives the same verdict every run.\n"
    "  It checks these configurations only, on the inputs your driver generates. A clean audit is "
    "evidence, not proof: ASan cannot see an error on a code path your inputs never take. What a "
    "REPORT means is definite — that configuration commits a memory-safety error and cytune will "
    "never emit it.")


def risk_configs():
    """[(name, config_id, directive, why)] — the audit's fixed work list."""
    return [(name, theta.id_of(cfg), directive, why) for name, cfg, directive, why in RISK_SET]


def _directive_verdicts(rows):
    """Per-directive: is turning it off safe FOR THIS KERNEL?

    A directive is 'safe to disable' only if every row that tests it came back CLEAN. The pair row
    counts against BOTH of its directives: if `a[-1]` reads out of bounds only when boundscheck and
    wraparound are both off, then neither of them is individually safe to disable, because turning
    off the second one later is what arms the bug.
    """
    out = {}
    for d in DIRECTIVES:
        relevant = [r for r in rows if r.get("directive") and d in r["directive"].split("+")]
        evidence = [_EVIDENCE[r["outcome"]] for r in relevant]
        if not relevant:
            out[d] = UNKNOWN
        elif "unsafe" in evidence:
            out[d] = UNSAFE
        elif all(e == "safe" for e in evidence):
            out[d] = SAFE
        else:
            # Some row could not be checked. Absence of evidence is not safety.
            out[d] = UNKNOWN
    return out


def build_report(name, rows, module_path=None, driver_path=None, image=None):
    """Assemble the audit report from the per-config gate results."""
    reported = [r for r in rows if r["outcome"] == REPORTED]
    raised = [r for r in rows if r["outcome"] == RAISED]
    unchecked = [r for r in rows if r["outcome"] in (NOT_RUN, BUILD_FAIL)]
    ref_row = next((r for r in rows if r["name"] == "reference"), None)

    # A sanitizer report is the strongest finding and dominates. An unchecked row only makes the
    # audit INCOMPLETE when nothing worse was found — otherwise the headline would be "we could not
    # check one thing" on a run that just found a buffer overflow.
    if reported:
        verdict = DEFECTS_FOUND
    elif unchecked:
        verdict = INCOMPLETE
    else:
        verdict = CLEAN

    rep = {
        "schema": SCHEMA,
        "cytune_version": __version__,
        "command": "audit",
        "module": name,
        "module_path": module_path,
        "driver_path": driver_path,
        "sanitizer_image": image,
        "risk_set_size": len(rows),
        "results": rows,
        "directive_verdicts": _directive_verdicts(rows),
        "directives_not_audited": NOT_AUDITED,
        "n_reported": len(reported),
        "n_clean": sum(1 for r in rows if r["outcome"] == OK),
        "n_raised": len(raised),
        "n_not_run": len(unchecked),
        "verdict": verdict,
        "scope": SCOPE_NOTE,
        "exit_code": {CLEAN: EXIT_CLEAN, DEFECTS_FOUND: EXIT_DEFECTS_FOUND,
                      INCOMPLETE: EXIT_ERROR}[verdict],
    }

    if ref_row is not None and ref_row.get("clean") is False:
        rep["reference_reports"] = True
        rep["summary"] = (
            "Your kernel reports under the sanitizer AT THE REFERENCE CONFIGURATION — with every "
            "Cython check still ON. This is a defect in the kernel as you wrote it, not something "
            "tuning introduced. Fix it before tuning: cytune has no configuration it can call safe "
            "for this module.")
    elif verdict == DEFECTS_FOUND:
        names = ", ".join(r["name"] for r in reported)
        rep["summary"] = (
            f"MEMORY-SAFETY DEFECT found in your kernel. {len(reported)} of {len(rows)} audited "
            f"configurations reported: {names}. These are latent bugs in YOUR code that only "
            f"manifest once the named directives are disabled — an output check cannot see them, "
            f"because a reduction absorbs the bad element. Fix the indexing before disabling those "
            f"directives.")
    elif verdict == INCOMPLETE:
        rep["summary"] = (
            f"AUDIT INCOMPLETE — {len(unchecked)} of {len(rows)} configurations could not be "
            f"checked, so this is not a clean result. Run `cytune doctor` to see why the sanitizer "
            f"gate could not run. Not-run is not a pass.")
    else:
        rep["summary"] = (
            f"No sanitizer report in any of the {len(rows)} audited configurations. "
            + (f"{len(raised)} configuration(s) made your kernel RAISE, which is a separate finding "
               f"— see the rows marked RAISED. " if raised else "")
            + f"On the inputs your driver generates, the directives marked 'safe to disable' above "
              f"committed no memory-safety error. That is evidence, not proof — see the scope note.")

    if raised:
        rep["raised_note"] = (
            "A RAISED row means your kernel threw an exception in that configuration rather than "
            "producing a sanitizer report. When the configuration still has boundscheck ON, that "
            "is usually Cython catching an out-of-range index BEFORE it becomes an illegal read — "
            "so it is evidence of the same indexing bug, caught by the check you were thinking of "
            "removing. It is recorded as UNSAFE to disable, because a kernel that throws in a "
            "configuration cannot use that configuration.")
    return rep


def render(rep):
    """The human-readable audit report."""
    L = []
    W = 78
    L.append("=" * W)
    L.append(f"cytune audit — {rep['module']}   (schema {rep['schema']})")
    L.append("=" * W)
    L.append("")
    L.append("PRE-REGISTERED RISK SET — deterministic, no search, no timing")
    L.append("")
    marks = {OK: "CLEAN   ", REPORTED: "REPORTED", RAISED: "RAISED  ",
             NOT_RUN: "NOT RUN ", BUILD_FAIL: "NO BUILD"}
    for r in rep["results"]:
        L.append(f"  [{marks[r['outcome']]}] {r['name']}  (config {r['config_id']})")
        L.append(f"             {r['why']}")
        if r["outcome"] == REPORTED:
            L.append(f"             >>> {', '.join(r.get('tokens') or []) or r.get('verdict')}")
            if r.get("report_path"):
                L.append(f"             full report: {r['report_path']}")
        elif r["outcome"] == RAISED:
            L.append("             >>> your kernel raised in this configuration (no sanitizer "
                     "report).")
            # The bounds-check explanation only applies where boundscheck is actually ON. It was
            # printed on every RAISED row, including the checks-off corners, so a cdivision or
            # initializedcheck failure was annotated with a reason about an unrelated directive.
            # (T8, systematic-tester agent.)
            if r["directives"].get("boundscheck") == "True":
                L.append("                 boundscheck is ON here, so this is usually Cython "
                         "catching a bad index")
                L.append("                 before it becomes an illegal read — evidence of the "
                         "same defect.")
            else:
                L.append("                 boundscheck is OFF here, so this is your kernel failing "
                         "for some other")
                L.append("                 reason in this configuration. Either way it cannot be "
                         "used.")
        elif r["outcome"] == BUILD_FAIL:
            L.append(f"             >>> this configuration did not compile: {r.get('note') or ''}")
        elif r["outcome"] == NOT_RUN:
            L.append(f"             >>> NOT CHECKED ({r.get('verdict')}). Not-run is not a pass.")
        # OK needs no second line: the [CLEAN] marker already said it. An `else` here stamped
        # "NOT CHECKED (CLEAN). Not-run is not a pass." under every clean row, so a report whose
        # own verdict was "no sanitizer report in any of the 8 configurations" told the reader,
        # eight times, that nothing had been checked. Found by the novice-user agent (U1).
    L.append("")
    L.append("-" * W)
    L.append("IS IT SAFE TO DISABLE THIS DIRECTIVE, FOR THIS KERNEL?")
    L.append("")
    for d, v in rep["directive_verdicts"].items():
        L.append(f"  {d:<20} {v}")
    for d, why in sorted(NOT_AUDITED.items()):
        L.append(f"  {d:<20} not audited — {why}")
    L.append("")
    if rep["directive_verdicts"].get("boundscheck") == UNSAFE or \
            rep["directive_verdicts"].get("wraparound") == UNSAFE:
        L.append("  NOTE: boundscheck and wraparound are judged TOGETHER as well as singly. A pair")
        L.append("  that reports only when both are off still makes each of them unsafe to disable,")
        L.append("  because turning off the second one is what arms the bug.")
        L.append("")
    L.append("-" * W)
    L.append(f"VERDICT: {rep['verdict'].upper()}")
    L.append("")
    for line in _wrap(rep["summary"], W - 2):
        L.append("  " + line)
    L.append("")
    L.append("SCOPE")
    for line in _wrap(rep["scope"], W - 2):
        L.append("  " + line)
    L.append("=" * W)
    return "\n".join(L)


def _wrap(text, width):
    out = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split():
            if cur and len(cur) + 1 + len(word) > width:
                out.append(cur)
                cur = word
            else:
                cur = f"{cur} {word}".strip()
        out.append(cur)
    return out


def run(kdir, gate_fn, say=None, odir=None, write_report=None):
    """Gate every config in the risk set. Pure orchestration — injected `gate_fn` so the audit can
    be tested without a container."""
    rows = []
    total = len(RISK_SET)
    for i, (name, cid, directive, why) in enumerate(risk_configs(), 1):
        if say:
            say(f"  [{i}/{total}] {name} (config {cid}) — ASan+UBSan")
        g = gate_fn(kdir, cid) or {}
        row = {"name": name, "config_id": cid, "directive": directive, "why": why,
               "directives": {k: str(v) for k, v in
                              theta.as_dict(theta.config_of(cid)).items()},
               "outcome": outcome_of(g),
               "clean": g.get("clean"), "verdict": g.get("verdict"),
               "tokens": g.get("tokens") or [], "note": g.get("note") or g.get("reason")}
        if row["outcome"] == REPORTED and write_report:
            row["report_path"] = write_report(odir, g)
        if say:
            say(f"          {row['outcome'].upper()}"
                + (f" — {', '.join(row['tokens'])}" if row["tokens"] else ""))
        rows.append(row)
    return rows
