"""I1 — certificate coherence. The systemic fix for this project's most persistent defect class.

THE DEFECT CLASS. Four separate findings, none of which was a broken function:

  P2  The certificate said `EMIT: the reference configuration (unchanged)` and printed
      `boundscheck=False, wraparound=False` on the next line. Selection was right, rendering was
      right, and the composition said two contradictory things.
  R2  `--allow-fast-math` emitted `-ffp-contract=fast` — correctly, since -ffast-math subsumes
      contraction — while the certificate's `fma_contraction_permitted` field said False. A user
      scripting on the JSON field would compile with contraction the tool told them was off.
  P1  A sanitizer-reporting configuration was emitted under the words "the best safe choice",
      because the fallback path had its own wording that nobody had reconciled with the gate.
  P4  A not-run gate left the verdict line unqualified, so a script reading `verdict` saw a clean
      "improvement" for a recommendation nobody had memory-checked.

Every one of these is two correct components disagreeing with each other, with nothing whose job
was to notice. Fixing them one at a time produces four patches and a fifth instance next month.

WHAT THIS MODULE IS. The thing whose job it is to notice. `assert_certificate_coherent` runs on
EVERY real run, after the certificate is rendered and BEFORE anything is printed to the user or
written to disk, and raises rather than emit a document that contradicts itself.

WHY IT RAISES INSTEAD OF WARNING. A warning on an incoherent certificate is an incoherent
certificate plus a warning. The whole product is a claim that its output can be trusted; if the
output disagrees with itself, there is nothing to salvage and the honest move is to refuse. The
CLI turns the refusal into an error exit with the violated invariant named.

THE GROUND TRUTH IS ALWAYS THE CONFIG ID. Every check recomputes what the truth should be from
`emitted_config.config_id` through `theta`, and compares the certificate's fields against that. It
never compares two certificate fields to each other, because two fields can be consistently wrong.

AND THAT IS ALSO THE LIMIT OF THIS MODULE. A ground truth recomputed from the config id can only
ever confirm the config id. Whether the id describes the artifact that was built, gated and timed
is a different question, and the answer is `binding.py` (I4) — see its docstring for the three
findings that came of not asking it.

WHY THERE IS NO LONGER ANY PROSE SCANNING HERE. The first version of this module searched the
RENDERED TEXT for phrases — "best safe choice", "reference configuration (unchanged)", "MEASURED
SPEEDUP" — because P2 was a correct field under a contradictory sentence. That was the wrong layer
to check at, and it proved it: the scan flagged the sentence "it is NOT certified safe", which is
the line written to prevent the very defect it was flagging. A negation window patched that
instance and left the technique.

The technique is unnecessary. `render` is a pure function of the certificate, and I1.10 now
enforces that at run time by re-rendering from a JSON round-trip and requiring byte identity. So a
document that is structurally coherent renders to text that is coherent, and the question "may
these words appear when this field has that value?" belongs in renderer unit tests
(`test_cytune_render.py`), where a negation is a test case rather than a regex.

What runs here is structured: fields against `theta`, fields against each other's ground truth,
and the document against its own published schema.
"""
from __future__ import annotations

import json

from ._vendor import theta
from .certify import (EXIT_BY_VERDICT, HONEST_FLAT, IMPROVEMENT, NO_SAFE_IMPROVEMENT,
                      _json_safe, cython_x_flags, directive_header, gcc_flags, render)


class IncoherentCertificate(AssertionError):
    """A certificate that contradicts itself. Never emitted, never written."""

    def __init__(self, invariant, detail):
        self.invariant = invariant
        super().__init__(f"{invariant}: {detail}")


def _violation(inv, detail):
    raise IncoherentCertificate(inv, detail)


def assert_certificate_coherent(cert, emitted_flags=None, gate_result=None, exit_code=None):
    """Raise IncoherentCertificate unless every claim in `cert` agrees with every other."""
    emitted = cert.get("emitted_config")
    verdict = cert.get("verdict")
    gate = gate_result if gate_result is not None else (cert.get("sanitizer_gate") or {})
    code = exit_code if exit_code is not None else cert.get("exit_code")

    # ---------------------------------------------------------------- I1.1  verdict <-> exit code
    if verdict not in (IMPROVEMENT, HONEST_FLAT, NO_SAFE_IMPROVEMENT):
        _violation("I1.1", f"unknown verdict {verdict!r}")
    want = EXIT_BY_VERDICT[verdict]
    if code != want:
        _violation("I1.1", f"verdict {verdict!r} must exit {want}, certificate says {code!r}. "
                           f"A script branching on $? would take the wrong branch.")
    if emitted is None:
        # Nothing was emitted at all (no feasible config). The only coherent verdict is
        # no-safe-improvement.
        if verdict != NO_SAFE_IMPROVEMENT:
            _violation("I1.1", f"no emitted config, but verdict is {verdict!r}")
        _assert_safety_earned(cert, gate)
        return True

    cid = emitted.get("config_id")
    if cid is None or not (0 <= cid < theta.N_CONFIGS):
        _violation("I1.2", f"emitted config_id {cid!r} is not a config in Θ")
    cfg = theta.config_of(cid)

    # ------------------------------------------------- I1.2  printed flags == the emitted config
    # Recomputed from the config id, never copied from another field.
    truth = {"directive_header": directive_header(cfg),
             "cython_x_flags": cython_x_flags(cfg),
             "gcc_flags": gcc_flags(cfg),
             # json_safe, because the certificate is compared as it will be SERIALISED — a tuple
             # here and a list on disk would make the check pass in memory and fail after a
             # round-trip, which is the opposite of what an artifact-integrity check is for.
             "factors": _json_safe(theta.as_dict(cfg))}

    for field in ("directive_header", "cython_x_flags", "gcc_flags"):
        if emitted.get(field) != truth[field]:
            _violation("I1.2", f"emitted_config.{field} is {emitted.get(field)!r} but config {cid} "
                               f"is {truth[field]!r}")
    if emitted.get("factors") != truth["factors"]:
        _violation("I1.2", f"emitted_config.factors disagree with config {cid}")

    if emitted_flags is not None and emitted_flags != truth["gcc_flags"]:
        _violation("I1.2", f"the flags handed to the caller ({emitted_flags!r}) are not the flags "
                           f"of config {cid} ({truth['gcc_flags']!r})")

    # ------------------------------------------- I1.3  FP-semantics fields == the emitted flags
    _assert_fp_coherent(cert, cfg, truth["gcc_flags"])

    # ------------------------------------ I1.4  the gate describes the config actually emitted
    gate_cid = gate.get("config_id")
    if gate.get("ran") and gate_cid is not None and gate_cid != cid:
        _violation("I1.4", f"sanitizer_gate describes config {gate_cid} but the emitted config is "
                           f"{cid}. This is finding F5: after a fallback the gate result described "
                           f"the REJECTED config, so the emitted one's status was never stated.")

    # ------------------------------------------------------- I1.5  not-run must qualify the line
    if gate.get("clean") is None:
        # The qualification is a RECORDED STRING, so this is an exact containment test rather than
        # a pattern hunting for three ways of saying "not run". `build_certificate` writes the
        # field and appends the same text to the summary; if a future path writes one without the
        # other, that is the defect P4 was.
        note = cert.get("sanitizer_gate_qualification")
        if not note:
            _violation("I1.5", "the sanitizer gate did not run, but the certificate records no "
                               "qualification for it (P4).")
        if note not in (cert.get("summary") or ""):
            _violation("I1.5", "the sanitizer gate did not run and the qualification is recorded, "
                               "but the verdict summary does not carry it. A reader who stops at "
                               "the summary would see an unqualified verdict for a recommendation "
                               "nobody memory-checked (P4).")
        if cert.get("sanitizer_gate_ran") is not False:
            _violation("I1.5", "gate clean is None but sanitizer_gate_ran is not False")

    # ---------------------------------------------- I1.6  safety wording vs the gate's verdict
    _assert_safety_earned(cert, gate)

    # --------------------------------- I1.7  a non-improvement verdict emits the reference only
    if verdict != IMPROVEMENT and cid != theta.REFERENCE_ID:
        _violation("I1.7", f"verdict is {verdict!r} but the emitted config is {cid}, not the "
                           f"reference ({theta.REFERENCE_ID}). Anything cytune is not recommending "
                           f"as an improvement must be the user's own baseline.")

    # -------------------------------- I1.9  the document honours its own published schema
    _assert_schema(cert)

    # ------------------------------------------- I1.8  a speedup is claimed only when verified
    if verdict == IMPROVEMENT:
        if not cert.get("speedup"):
            _violation("I1.8", "verdict is improvement but no speedup was recorded")
        if (cert.get("sanitizer_gate") or {}).get("clean") is False:
            _violation("I1.8", "verdict is improvement but the emitted config's sanitizer gate "
                               "REPORTED. G2 forbids emitting it at all.")
    return True


def assert_document_valid(doc):
    """I1.9 for the artifacts that are not certificates — the dry-run report and the audit report.

    All four documents are public contracts (docs/COMPATIBILITY.md), so all four are checked against
    their published schema before they leave the process. Without this, only `certificate.json` was
    guarded and the other three could drift from the promise while every test validated a
    hand-written fixture.
    """
    _assert_schema(doc)
    return True


def _assert_schema(doc):
    """I1.9. cytune publishes a schema and promises consumers can build against it; the cheapest
    way for that promise to rot is for the emitter and the schema to drift while every test
    validates hand-written fixtures. So the real document is checked against the real contract, on
    every real run, before it is written."""
    from . import schema
    errs = schema.validate(doc)
    if errs:
        _violation("I1.9", "the certificate does not honour its own published schema "
                           f"({doc.get('schema')}): " + "; ".join(errs[:5]))


def _assert_fp_coherent(cert, cfg, flags):
    """R2. The emitted FLAG STRING is the ground truth; every FP field must match it.

    `-ffast-math` subsumes `-ffp-contract=fast`: theta.build_flags forces the contract build-arg to
    `fast` whenever fast-math is on. So a certificate that reports `fma_contraction_permitted:
    False` next to a flag string containing `-ffp-contract=fast` is contradicting itself, and the
    field is the half a script would read.
    """
    fp = cert.get("fp_semantics") or {}
    flag_fast_math = "-ffast-math" in flags
    flag_contract = "-ffp-contract=fast" in flags

    if bool(fp.get("fast_math_permitted")) != flag_fast_math:
        _violation("I1.3", f"fp_semantics.fast_math_permitted="
                           f"{fp.get('fast_math_permitted')!r} but the emitted flags "
                           f"{'contain' if flag_fast_math else 'do not contain'} -ffast-math")
    if bool(fp.get("fma_contraction_permitted")) != flag_contract:
        _violation("I1.3", f"fp_semantics.fma_contraction_permitted="
                           f"{fp.get('fma_contraction_permitted')!r} but the emitted flags "
                           f"{'contain' if flag_contract else 'do not contain'} "
                           f"-ffp-contract=fast. This is finding R2.")
    if flag_fast_math and not flag_contract:
        _violation("I1.3", "-ffast-math without -ffp-contract=fast: fast-math implies contraction, "
                           "so the emitted flag string is internally inconsistent")
    if flag_fast_math and not fp.get("fma_contraction_implied_by_fast_math"):
        _violation("I1.3", "fast-math is on but the certificate does not record that contraction "
                           "came with it — the user would read an opt-in they never made")

    # The policy is consent. An emitted config may not exceed it — on ANY axis.
    #
    # This used to re-derive the two FP axes here, which meant `--portable-flags` was not checked
    # at all: a run that promised `-march=x86-64` could emit `-march=native` and the invariant
    # would pass it. Asking the EmissionPolicy itself closes that and cannot drift from it — a new
    # policy axis is covered the day it is added, without anyone remembering to extend this
    # function. (Found by scrutinising the invariant against its own claim.)
    from .plan import EmissionPolicy
    pol = cert.get("emission_policy") or {}
    policy = EmissionPolicy(allow_fast_math=bool(pol.get("allow_fast_math")),
                            allow_fp_contract=bool(pol.get("allow_fp_contract")),
                            portable_flags=bool(pol.get("portable_flags")))
    why = policy.excluded_reason(theta.id_of(cfg))
    if why:
        _violation("I1.3", f"the emitted config is excluded by this run's own emission policy "
                           f"({why}); policy={pol}. G4/G5: a config outside the consent the user "
                           f"gave must never be emitted.")

    # Kept as well as the policy check, because these produce a much more specific message for the
    # two cases a user is most likely to hit.
    if flag_fast_math and not pol.get("allow_fast_math"):
        _violation("I1.3", "the emitted config uses -ffast-math but the run's policy did not allow "
                           "it. G4 says every FP-semantics change is opt-in.")
    if flag_contract and not (pol.get("allow_fp_contract") or pol.get("allow_fast_math")):
        _violation("I1.3", "the emitted config permits FMA contraction but the run's policy allowed "
                           "neither --allow-fp-contract nor --allow-fast-math (G4).")


def _assert_safety_earned(cert, gate):
    """I1.6, as a field rather than a phrase.

    `safety_wording_earned` is the ONE place the question "may this document call the emitted
    configuration safe?" is answered, and every renderer branch and every summary keys off it. So
    the runtime check is that the field agrees with the gate, and whether the right words follow
    from the field is settled in `test_cytune_render.py` over the whole outcome space — where
    "these words must NOT appear" is a test case and not a regex with a negation window.

    Earned means CLEAN from the PINNED image. An overridden image cannot buy the wording (H6).
    """
    earned = bool(gate.get("clean") is True and not gate.get("image_overridden"))
    stated = cert.get("safety_wording_earned")
    if stated is None:
        _violation("I1.6", "the certificate does not record whether the safety wording was earned; "
                           "every branch that can call a configuration safe reads that field, so "
                           "its absence means the question was never answered.")
    if bool(stated) != earned:
        _violation("I1.6",
                   f"safety_wording_earned={stated!r} but the emitted config's sanitizer gate is "
                   f"{gate.get('verdict', 'absent')!r} (clean={gate.get('clean')!r}, "
                   f"image_overridden={gate.get('image_overridden')!r}), which earns "
                   f"{earned!r}. Only a CLEAN gate from the pinned image earns that wording — "
                   f"this is finding P1, where a reporting config was emitted as 'the best safe "
                   f"choice'.")


def assert_render_is_a_function_of_the_document(cert, rendered):
    """I1.10 — the text the user reads is derived from the document that was written, and nothing
    else.

    This REPLACES five substring searches of the rendered certificate. Each of those asked whether
    one expected phrase was present or one forbidden phrase was absent; between them they covered a
    handful of sentences out of eighty lines, and one of them fired on the sentence written to
    prevent the defect it was checking for.

    Re-rendering the document from its own JSON round-trip and requiring byte identity is a
    stronger statement than all of them together: certificate.txt is exactly what certificate.json
    renders to, so anything provable about the JSON is true of the text. It also catches the case
    none of the substring checks could — the .txt on disk describing a different document from the
    .json beside it — which is what a consumer diffing the two would find.
    """
    fresh = render(json.loads(json.dumps(_json_safe(cert))))
    if fresh != rendered:
        first = next((i for i, (a, b) in enumerate(zip(fresh.splitlines(),
                                                       (rendered or "").splitlines()))
                      if a != b), None)
        _violation("I1.10",
                   "the rendered certificate is not what this document renders to — the text and "
                   "the JSON would disagree on disk"
                   + (f" (first difference at line {first + 1})" if first is not None else
                      " (they differ in length)"))
    return True
