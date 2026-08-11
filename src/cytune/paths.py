"""B4 — production's verify/emit decision paths, enumerated as DATA at their source.

WHY THIS FILE EXISTS. Defect D-3 was the FOURTH instance of one shape:

    the unit is tested, and the composition models fewer cases than production has.

  D13  the honest-flat route certified an IMPROVEMENT from a selection-biased probe minimum —
       every part correct, the composition dishonest.
  D14  "fast-math: not opted in" printed beside an emitted `-ffp-contract=fast`.
  D18  the verify stage never built its own inputs, so a real 2x degraded to honest-flat.
  D-3  the C1 demotion left the CANDIDATE's sanitizer verdict on a certificate emitting the
       REFERENCE. `corroborate_ratio` had four unit tests including a power-curve sweep; the
       composition sweep whose stated purpose was "reproduce the CLI's decision order" modelled
       two of the three demotion paths, and its fixtures carried no `wall_ns`, so the third was
       unreachable IN PRINCIPLE rather than merely unwritten. A live run found it instead.

Each time the fix was an instance fix: add the missing branch to the mirror. That closes the
instance and leaves the class open, because nothing tells you when the next branch is added to
production and not to the mirror.

This registry is the class defence. Production's paths live here as data; the composition sweep
reports which paths it reached; and `test_cytune_paths.py` fails when a path marked
`composition=REQUIRED` was never exercised. A sweep that models fewer paths than production has is
now a test failure rather than a live-run discovery.

WHAT IT DOES NOT DO, stated so nobody reads more into it than is there: nothing here notices a path
added to `cli.py` and not added to this file. That would need either coverage instrumentation of
the real `tune()` or a static analysis of its branch structure, and neither exists. What the
registry converts is the SECOND half of the failure — production path enumerated, composition
silently not covering it. The first half is still a human duty, and `test_every_registered_path_
names_a_real_production_site` is what keeps the enumeration from rotting once written.
"""
from __future__ import annotations

REQUIRED = "required"          # the composition sweep must reach this path
CERTIFY_ONLY = "certify-only"  # unreachable from cli.tune; reachable in build_certificate
NA = "n/a"                     # not a composition path (argument parsing, refusals, post-verdict)

# id, trigger, production site, what is emitted, verdict, exit, san_emitted disposition,
# composition duty, note
PATH_REGISTRY = (
    ("V-0", "select_winner returns None: nothing feasible, or everything policy-excluded",
     "cli.py:405", "nothing", "no-safe-improvement", 3,
     "never assigned; the gate is recorded NOT_RUN by _gate_absent", REQUIRED,
     "the whole verify block is skipped; certify.py:751 early-returns"),

    ("V-1", "honest-flat route with an incidental probe winner",
     "cli.py:407", "reference", "honest-flat", 2,
     "None -> the reference is gated at cli.py:559", REQUIRED,
     "D13's path. The probe minimum is reported as an observation and refused as a recommendation"),

    ("V-1b", "the search's own best IS the reference -- there is nothing to demote",
     "cli.py:416", "reference", "honest-flat", 2,
     "None -> the reference is gated at cli.py:559", REQUIRED,
     "the quiet majority path on a flat landscape, and the one a sweep is likeliest to leave "
     "unnamed because nothing visibly happens on it"),

    ("V-2", "confirm_winner refuses the endpoint (infeasible / no endpoint_ns / not_built)",
     "cli.py:447", "reference", "no-safe-improvement", 3,
     "None -> the reference is gated", REQUIRED,
     "D18 rode in on this path. Its rejection dict has NO 'gate' key and cli.py:543 branches on "
     "that absence, so it is the one demotion shaped differently from the rest"),

    ("V-3", "the sanitizer reports on the search's best candidate",
     "cli.py:460", "reference", "no-safe-improvement", 3,
     "never assigned; the candidate's verdict is kept in rejection['sanitizer']", REQUIRED,
     "gated BEFORE the emit decision on purpose: the gate is a bug finder, not only a filter"),

    ("V-4", "C1 parent wall clock cannot account for the claimed speedup",
     "cli.py:490", "reference", "no-safe-improvement", 3,
     "assigned at cli.py:481, then reset to None at cli.py:516 -- the D-3 fix", REQUIRED,
     "the path D-3 was on. The reset is what makes the following gate describe the emission"),

    ("V-4-N", "C1 returns corroborated=None (no wall clock, no medians, or the no-power cutoff)",
     "certify.py:480", "candidate", "improvement", 0,
     "the candidate's own gate stands", REQUIRED,
     "NOT a demotion. Registered because a sweep can 'cover C1' while only ever reaching one of "
     "its three return shapes -- which is exactly how D-3 hid"),

    ("V-5", "the emit margin or the endpoint separation is missed",
     "cli.py:524", "reference", "honest-flat", 2,
     "assigned, then reset to None at cli.py:540", REQUIRED,
     "the candidate's gate is preserved in flat_observation['sanitizer_gate']"),

    ("V-6", "the EMITTED config's own sanitizer gate reports",
     "cli.py:558", "reference (unsafe)", "no-safe-improvement", 3,
     "the emitted config's verdict, reporting", REQUIRED,
     "certify.py:876 OVERWRITES whatever verdict was set above it"),

    ("V-7", "the gate did not run on the emitted config (clean is None)",
     "certify.py:907", "unchanged", None, None,
     "not-run", REQUIRED,
     "a qualifier, not a demotion: the verdict is untouched and the safety wording is downgraded"),

    ("V-8", "the gate is CLEAN but came from an unpinned image",
     "certify.py:902", "unchanged", None, None,
     "kept, marked non-authoritative", REQUIRED,
     "H6. Verdict unchanged; --apply refuses"),

    ("V-9", "the candidate survives every check",
     "cli.py:481", "candidate", "improvement", 0,
     "the candidate's own gate (cli.py:559 is skipped)", REQUIRED,
     "the only path that emits something other than the reference"),

    ("V-10", "margin cleared, separation failed, winner not the reference",
     "certify.py:836", "candidate", "honest-flat", 2,
     "n/a", CERTIFY_ONLY,
     "cli.tune cannot reach it (it demotes on margin AND separation) but build_certificate's own "
     "I2.1 guard at certify.py:816 tests margin ONLY. Registered because production and its "
     "source-of-truth guard disagree about what 'clears' means"),

    ("V-11", "I4.1 / I4.3 / I4.4 binding violation after the emit decision",
     "cli.py:575", "nothing (refuses to write)", None, 1,
     "the gate is I4.3's input", NA,
     "fires AFTER the composition, on its output, so it cannot be a path the composition takes -- "
     "it is the layer that caught D-3 in production when the composition got it wrong"),

    ("V-12", "I1.* certificate incoherence",
     "cli.py:619", "nothing (refuses to write)", None, 1,
     "the gate is an input", NA,
     "not a path the composition takes: the entire coherence sweep is this check running over "
     "every path the composition DOES take"),

    ("V-13", "--apply refused (verdict, rejection, unpinned image, or gate not CLEAN)",
     "cli.py:642", "no source edit", None, None,
     "read-only", NA,
     "post-verdict: it acts on a finished certificate and changes no field of it, so it composes "
     "nothing; apply.py has its own I2.5 test"),

    ("E-ABORT", "routing rule R0: infeasible reference, or fewer than 4 feasible probe rows",
     "cli.py:343", "nothing", None, 1, "n/a", NA,
     "pre-verify: no winner has been selected yet, so there is no emit decision to compose"),
    ("E-DRY", "--dry-run", "cli.py:348", "nothing", None, 0, "n/a", NA,
     "prints a cytune-dry-run document whose verdict is null; it is a different document schema, "
     "not a verdict path, and test_cytune_api.py covers it"),
    ("E-ARG", "bad --target-ms / --budget-scale", "cli.py:166", "nothing", None, 1, "n/a", NA,
     "argument validation, before any measurement exists; covered by test_cytune_ux.py"),
    ("E-RIG", "--rig quiesced on a host that is not quiesced", "cli.py:191", "nothing", None, 1,
     "n/a", NA,
     "argument validation against the probed rig, before the session is constructed"),
    ("E-INGEST", "validate_inputs raises IngestError", "cli.py:185", "nothing", None, 1, "n/a",
     NA, "pre-build: the module or driver could not be read, so no composition has begun"),
    ("E-BUILD", "not one config compiles", "cli.py:238", "nothing", None, 1, "n/a", NA,
     "BuildFailure: there is no measurement to compose a decision from"),
    ("E-DEGEN", "I4.2 total directive degeneracy", "cli.py:253", "nothing", None, 1, "n/a", NA,
     "refuses to tune a module where the directives cannot matter"),
    ("E-LOCK", "another measurement holds the machine-level lock",
     "cli.py:198", "nothing", None, 1, "n/a", NA,
     "B3. Refuses rather than measuring against a contended machine"),
)

FIELDS = ("id", "trigger", "site", "emits", "verdict", "exit_code", "san", "composition", "note")

IDS = tuple(r[0] for r in PATH_REGISTRY)
REQUIRED_IDS = frozenset(r[0] for r in PATH_REGISTRY if r[7] == REQUIRED)


def describe(path_id):
    for r in PATH_REGISTRY:
        if r[0] == path_id:
            return dict(zip(FIELDS, r))
    raise KeyError(path_id)


def as_dicts():
    return [dict(zip(FIELDS, r)) for r in PATH_REGISTRY]
