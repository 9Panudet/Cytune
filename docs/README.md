# cytune documentation

**The front page is [`../README.md`](../README.md)** — what cytune is, how to install it, and a
verified quickstart. This directory holds the detail. There is exactly one copy of each fact; when
this page and the front page would overlap, this page points there instead.

| document | what it answers |
|---|---|
| [`../README.md`](../README.md) | What is cytune? How do I install and run it? What do the verdicts mean? |
| [USER_GUIDE.md](USER_GUIDE.md) | Every stage, every flag and its default, `.cytune.toml`, exit codes, and the certificate field by field. |
| [GUARANTEES.md](GUARANTEES.md) | What is promised, what is explicitly not, and the evidence for each — including the paths that are still untested. |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Errors people actually hit, with the fix, and what `cytune doctor` checks. |
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | Open findings, and the ones fixed in the productisation pass with the test that proves each. |
| [COMPATIBILITY.md](COMPATIBILITY.md) | The frozen 1.x public API: four JSON schemas, the exit-code table, and what may and may not change under you. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | The module map, the one-way dependency rule, why the measurement rig is vendored, and the invariant tiers. For someone changing the code. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to add a flag, an oracle class, a search engine, an invariant or a guarantee — and the obligation each carries. |
| [`../SECURITY.md`](../SECURITY.md) | The threat model. What certificate integrity means, what is defended, and the one class that cannot be. |
| [`../CHANGELOG.md`](../CHANGELOG.md) | What changed between releases, starting with the behavioural changes a user must know about. |

## How this documentation was written

Not from the source. It was written from two cold-user acceptance tests in which a tester was
allowed to read only the shipped docs, the CLI `--help`, and CLI output — and every point where the
docs turned out to be insufficient was recorded as a finding before the missing line was written.

- [`../results/usertest/USER_TEST_REPORT.md`](../results/usertest/USER_TEST_REPORT.md) — the first
  pass. Verdict: **a stranger would not succeed**, stopped at the first command. 21 findings.
- [`../results/usertest/PRODUCTIZATION_REPORT.md`](../results/usertest/PRODUCTIZATION_REPORT.md) —
  what was fixed, the test that proves each fix, and the re-test.
- [`../results/release/V1_RELEASE_REPORT.md`](../results/release/V1_RELEASE_REPORT.md) — the 1.0.0
  gate: the ground-truth dogfood against nine exhaustively-measured real modules, and a
  three-agent adversarial campaign (a novice user, a systematic tester, and an attacker whose
  objective was to force a false certificate).

Where something is documented but was never exercised, it says so in that place. That is the
project's own rule, applied to its own documentation: a guarantee whose failure path has never
fired is a claim, not a guarantee.
