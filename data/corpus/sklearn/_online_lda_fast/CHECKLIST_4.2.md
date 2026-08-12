# §4.2 admissibility checklist — `sklearn.decomposition._online_lda_fast` (11th fold / margin)

New fold via ordinary §4.2 curation (NOT B-12). Admissible iff all 5 §4.2 criteria hold.

| # | §4.2 criterion | verdict | evidence / note |
|---|---|---|---|
| 1 | Non-templated `.pyx` | ☑ PASS | `_online_lda_fast.pyx`; vendored verbatim (sha256 `00c1187e…`). Not Tempita. |
| 2 | Stable upstream (not `scipy.special`) | ☑ PASS | `sklearn.decomposition`, pinned sdist `b4237ed7…` (1.5.2). |
| 3 | Isolatable hot loop, public-API inputs | ☑ PASS | vendored-closure build+import in X′ (`build_from_closure.sh`; log `logs/corpus/STEP_1.1.1_vendor_online_lda_fast_build.log`) + negative control. Inputs are plain `float64` arrays (numpy). |
| 4 | Oracle-classifiable per §3.1 | ☑ PASS | floats→tolerance; **determinism smoke bit-identical** (no RNG/prange). Tolerance derived+frozen at 1.1.3. |
| 5 | Golden runtime 50–500 ms | ☐ PENDING-1.1.5 | input-scale design recorded (MANIFEST §5, CF-4). Golden measured under the rig at 1.1.5; no number claimed here. |

**Status:** 4/5 confirmed; criterion 5 pending the rig at 1.1.5. Provisionally admissible — this is the
**confident 11th fold** that secures the ≥10-fold floor independent of the contingent `manifold` fold.

Cross-refs: `MANIFEST.md`, `build_from_closure.sh`, `results/characterization/CORPUS_FOLD_LEDGER.md`.
