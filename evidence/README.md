# evidence/ — what every claim on the front page rests on

The `main` branch's README makes claims. This directory holds what they rest on, **on this branch**,
so no claim points at a file that lives somewhere else. If you find a claim in `README.md` that is
not in the table below, it is a defect and should be reported as one.

| claim in `README.md` | file here | what it is |
|---|---|---|
| "median regret 1.409 %, range 1.409–1.719 %, over five runs on nine real-code kernels" | `repeated_dogfood.json` | every per-anchor median/min/max/spread, the emitted-config counts, and the conditions the numbers hold under |
| "worst kernel 5.412 %, range 5.412–9.791 %" | `repeated_dogfood.json` → `headline_default_arm.worst_anchor_per_replicate` | |
| "it measures ~35 of 1,728 configurations" | `repeated_dogfood.json` → `per_anchor_default_arm.*.configs_measured` | 33 on eight kernels, 49 on one |
| "the certificate names what it did not prove" | `example_certificate_improvement.txt` | a real certificate from the campaign above, unedited |
| "it finds latent out-of-bounds bugs your tests cannot see" | `example_sanitizer_report.log` | a real AddressSanitizer report from the gate, on a kernel whose own correctness oracle passed |
| "four document schemas, machine-readable" | `schemas.json` | the certificate, audit, doctor and dry-run schemas |
| "it is tested by people trying to break it" | `adversarial_campaign.md` | what four testers found, including the five defects they found and the six issues still open |
| the guarantees | `../docs/GUARANTEES.md` | on this branch; the **non**-guarantees N1–N9 are in the same file and are not optional reading |

## Three things about these numbers that a careful reader should check first

**They are from one machine.** i3-10100F, 16 GB, quiesced. `../docs/GUARANTEES.md` N3 says nothing
transfers to other hardware, and means it.

**"Regret" is measured against a known optimum, not an estimated one.** For each of the nine
kernels all 1,728 configurations were exhaustively measured beforehand, so the best possible answer
is known exactly. That is what makes the accuracy claim checkable rather than rhetorical.

**Every number carries a range because a single run is one draw.** Two runs of the same unchanged
engine were measured to disagree by up to 6.711 percentage points on one kernel. Any cytune number
quoted without a range — including in older documents in this project's history — is one sample
presented as a property.

## What is not here

The frozen 1,728-configuration tables (215 MB), the full study, the pre-registrations and the
reports live on the **`research`** branch. The development harnesses that produced these files live
on **`dev`**. Nothing on this page depends on either being present.
