"""cytune — Cython-directive x GCC-flag autotuner with a correctness certificate.

Status: RESEARCH PREVIEW. The label is deliberate and load-bearing. The routing policy is an
engineering default grounded in the Phase-P study, not a validated per-cell router (§5 of
results/PHASEP_REPORT.md measured that routing does not beat always-DOE on held-out kernels).
Everything the product REFUSES to do — emit an oracle-failing config, emit a config the
sanitizer reports on, invent a speedup on a flat landscape, emit a config whose floating-point
semantics differ from your source without your consent — is measured and tested. Everything it
CHOOSES is provisional.

Hard guarantees (roadmap §8.2), enforced and tested, not aspirational:
  G1  Never emits a config that failed the oracle — under any flag, objective or budget.
  G2  Never emits a config the §1.4 ASan+UBSan gate reported on; the gate runs on the config
      ACTUALLY emitted, and a gate that could not run is recorded as not-run, never as a pass.
  G3  "No worthwhile speedup; best safe config = reference" is a first-class, tested output.
  G4  Every floating-point-semantics change is opt-in (--allow-fast-math, --allow-fp-contract)
      and still oracle-gated.

ONE version string, used by the CLI banner, `doctor`, `--version` and every machine-readable
artifact. Three different version strings across those places was finding F7 of the cold-user
acceptance test: a user could not cite a version in a bug report.
`test_cytune_api.py::test_the_version_is_single_sourced` asserts all four report the same string,
so F7 is structurally impossible rather than fixed once.

WHY "research preview" SURVIVES 1.0.0. The version freezes the API — the certificate schema, the
exit codes, the flag names — and promises they will not move under a consumer within 1.x. It does
NOT claim the study behind the routing policy is complete: three of four kernel categories are
underpowered, the statistical auditor's independent re-check has never run against the corrected
data, and RQ-P2 measured that routing does not beat always-DOE. The label describes the EVIDENCE;
the version number describes the INTERFACE. Dropping the label at 1.0.0 would be exactly the kind
of quiet upgrade-by-implication this project exists to refuse. See docs/GUARANTEES.md N5.
"""

__version__ = "1.1.0"
SCHEMA_VERSION = "1.0"
RELEASE_LABEL = "research preview"


def version_banner():
    return f"cytune {__version__} ({RELEASE_LABEL})"
