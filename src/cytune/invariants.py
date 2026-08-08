"""A4 — the invariant registry.

One place that lists every runtime invariant cytune enforces. Each entry names a STABLE id, the
function that enforces it, where in production that function runs, and the test that makes it fire.

The registry is not documentation. `test_cytune_invariants.py` walks it and fails if an entry's
function is missing, if its named test does not exist, or if an invariant is enforced in the code
without an entry here. That is what stops it from becoming a list of things that used to be true.

WHY IDS. An invariant with a name can be cited — in a certificate, in an error message, in a
post-mortem — and a user who sees `violated invariant I1.3` can look it up. The four defects that
motivated I1 (P1, P2, R2, P4) were each discovered separately and fixed separately precisely
because nobody had named the thing they were all instances of.

THE TIERS.

  I1.*  CERTIFICATE COHERENCE — checked on every real run, before anything is printed or written.
        Violation raises and cytune emits nothing. These are about the DOCUMENT agreeing with the
        measurements behind it.
  I2.*  EMISSION — what cytune is allowed to hand a user. These are G1/G2/G4 at the point of
        emission, enforced inside `build_certificate` so that no caller can route around them.
  I3.*  ARTIFACT — the cache and the emitted files. What is reused must have been measured under
        the conditions it is reported under.
  I4.*  BINDING — the document is about THIS run. Every other tier reasons from the config id, so
        every other tier can only ever confirm the id. These check the id against the bytes that
        were built, gated and timed. H12, H6 and H1 were three instances of the gap they close.
"""
from __future__ import annotations

from . import binding, certify, coherence, session

# (id, what it guarantees, the callable, where it runs in production, the test that fires it)
REGISTRY = [
    # ---------------------------------------------------------------- I1: certificate coherence
    ("I1.1", "the verdict, the exit code and the rendered VERDICT line all agree",
     coherence.assert_certificate_coherent, "cli.tune, before writing or printing",
     "test_cytune_coherence.py::test_verdict_and_exit_code_must_agree"),

    ("I1.2", "the directives and flags PRINTED are those of the emitted config id (P2)",
     coherence.assert_certificate_coherent, "cli.tune, before writing or printing",
     "test_cytune_coherence.py::test_p2_emit_block_must_match_the_emitted_config"),

    ("I1.3", "every FP-semantics field agrees with the emitted flag string, including "
             "fast-math's implication of contraction (R2), and neither exceeds the policy (G4)",
     coherence._assert_fp_coherent, "cli.tune, via assert_certificate_coherent",
     "test_cytune_coherence.py::test_r2_fp_fields_must_agree_with_the_emitted_flag_string"),

    ("I1.4", "the sanitizer_gate field describes the config actually emitted, never another (F5)",
     coherence.assert_certificate_coherent, "cli.tune, before writing or printing",
     "test_cytune_coherence.py::test_f5_the_gate_must_describe_the_emitted_config"),

    ("I1.5", "a gate that did not run qualifies the verdict summary and sets the machine-readable "
             "flag (P4)",
     coherence.assert_certificate_coherent, "cli.tune, before writing or printing",
     "test_cytune_coherence.py::test_p4_a_not_run_gate_must_qualify_the_verdict_line"),

    ("I1.6", "the one field that licenses safety wording agrees with the gate, and only a CLEAN "
             "gate from the pinned image sets it (P1, H6)",
     coherence._assert_safety_earned, "cli.tune, via assert_certificate_coherent",
     "test_cytune_coherence.py::test_p1_safety_wording_cannot_survive_a_reporting_gate"),

    ("I1.7", "anything not certified as an improvement emits the user's own reference",
     coherence.assert_certificate_coherent, "cli.tune, before writing or printing",
     "test_cytune_coherence.py::test_a_non_improvement_must_emit_the_reference"),

    ("I1.8", "a speedup is printed only for an improvement, and an improvement never has a "
             "reporting gate (G2)",
     coherence.assert_certificate_coherent, "cli.tune, before writing or printing",
     "test_cytune_coherence.py::test_an_improvement_verdict_cannot_have_a_reporting_gate"),

    ("I1.9", "the emitted document honours its own published JSON schema, so the compatibility "
             "promise is checked against real output rather than against fixtures",
     coherence._assert_schema, "cli.tune, via assert_certificate_coherent",
     "test_cytune_coherence.py::test_i1_9_a_certificate_violating_its_own_schema_is_refused"),

    ("I1.10", "certificate.txt is exactly what certificate.json renders to, so anything proved "
              "about the document is true of the text the user reads",
     coherence.assert_render_is_a_function_of_the_document, "cli.tune, before writing or printing",
     "test_cytune_render.py::test_i1_10_a_rendering_of_another_document_is_refused"),

    # ------------------------------------------------------------------------- I2: emission
    ("I2.1", "a candidate that does not clear the emit margin is demoted to the reference BEFORE "
             "the certificate is built, or the build refuses (P2 at its source)",
     certify.build_certificate, "certify.build_certificate, on every run",
     "test_cytune_coherence.py::test_b2_a_non_clearing_winner_is_refused_at_its_source"),

    ("I2.2", "a sanitizer-reporting candidate is refused and replaced by the reference before it "
             "can be certified (G2)",
     certify.build_certificate, "certify.build_certificate, on every run",
     "test_cytune_product_fixes.py::"
     "test_a_reporting_candidate_cannot_be_certified_without_a_rejection"),

    ("I2.3", "a rejected winner has been replaced by the reference before certification",
     certify.build_certificate, "certify.build_certificate, on every run",
     "test_cytune_certify.py::test_a_rejected_winner_must_be_replaced_before_certification"),

    ("I2.4", "the word 'safe' in a summary is downgraded unless the gate cleared",
     certify._downgrade_safety_claims, "certify.build_certificate, on every run",
     "test_cytune_coherence.py::test_b2_the_invariant_holds_over_every_generated_run_outcome"),

    ("I2.5", "--apply refuses anything that is not an improvement gated CLEAN",
     None, "apply.check_applicable, on --apply",
     "test_cytune_product_fixes.py::test_apply_refuses_when_the_gate_did_not_run"),

    # ------------------------------------------------------------------------- I3: artifacts
    ("I3.1", "a changed module or toolchain image invalidates cached builds AND the timings taken "
             "from them",
     session.Session.invalidate_stale_builds, "cli.tune, before the first build",
     "test_cytune_cache.py::test_a_changed_module_discards_builds_and_measurements"),

    ("I3.2", "a changed driver, workload, rig mode or oracle invalidates cached timings (R4)",
     session.Session.invalidate_stale_measurements, "cli.tune, after golden capture",
     "test_cytune_cache.py::test_a_changed_rig_mode_discards_measurements_but_keeps_builds"),

    ("I3.3", "discarded measurements are archived, never destroyed",
     session.Session.invalidate_stale_measurements, "cli.tune, on invalidation",
     "test_cytune_cache.py::test_discarded_measurements_are_archived_not_destroyed"),

    ("I3.4", "certificate.json re-renders to certificate.txt byte-for-byte",
     certify.render, "cli.tune, step 6",
     "test_cytune_cache.py::test_b4_a_certificate_rerenders_byte_for_byte_from_its_json"),

    # --------------------------------------------------------------------- I4: artifact binding
    ("I4.1", "the emitted configuration names the artifact that was actually timed, on both "
             "sides of the ratio",
     binding.assert_emission_bound, "cli.tune, before the certificate is assembled",
     "test_cytune_binding.py::test_i4_1_a_swapped_artifact_is_refused"),

    ("I4.2", "the directives cytune varies actually change the generated code, so a factor "
             "neutralised from outside cytune is refused rather than certified (H12, generically)",
     binding.assert_no_total_degeneracy, "cli.tune, immediately after the probe build",
     "test_cytune_binding.py::test_i4_2_total_degeneracy_is_refused_with_the_blacklist_off"),

    ("I4.3", "the sanitizer verdict is about this configuration, this source tree, and the "
             "pinned toolchain identified by DIGEST rather than by tag (H6)",
     binding.assert_gate_bound, "cli.tune, before the certificate is assembled",
     "test_cytune_binding.py::test_i4_3_a_gate_on_another_source_tree_is_refused"),

    ("I4.4", "a timing reported as decision-grade carries the rig fingerprint measure_wrap "
             "verified for it",
     binding.assert_rig_bound, "cli.tune, before the certificate is assembled",
     "test_cytune_binding.py::test_i4_4_a_quiesced_claim_over_an_ungated_row_is_refused"),
]

IDS = [i for i, *_ in REGISTRY]


def describe(invariant_id):
    for i, what, _fn, where, test in REGISTRY:
        if i == invariant_id:
            return {"id": i, "guarantees": what, "enforced_in": where, "test": test}
    return None
