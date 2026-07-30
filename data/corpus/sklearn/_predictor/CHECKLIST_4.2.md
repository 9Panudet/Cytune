# §4.2 admissibility checklist — `sklearn.ensemble._hist_gradient_boosting._predictor`

Committed per Step 1.1.1 ("criteria checklist per unit committed", roadmap §7 row 1.1.1). A unit is
**admissible iff all 5** §4.2 criteria hold. Evidence pointers are to committed raw artifacts.

| # | §4.2 criterion (verbatim intent) | verdict | evidence / note |
|---|---|---|---|
| 1 | **Non-templated `.pyx`** — Tempita `.pyx.tp` excluded (break source-hash determinism) | ☑ PASS | unit is `_predictor.pyx` (not `.pyx.tp`); vendored verbatim (sha256 `e8a1cc6b…`). Cluster `common.pyx`/`_bitset.pyx` also plain `.pyx`. Not Tempita. |
| 2 | **Stable upstream** — `scipy.special` excluded (Cython→C++/Pythran migration) | ☑ PASS | `sklearn.ensemble._hist_gradient_boosting`, pinned at sdist sha256 `b4237ed7…` (1.5.2). Not `scipy.special`. |
| 3 | **Isolatable hot loop**, representative inputs from public APIs | ☑ PASS | STANDALONE-IMPORT of `sklearn.ensemble._hist_gradient_boosting._predictor` in X′ from the vendored runtime `.so` cluster (`build_from_closure.sh`; log `logs/corpus/STEP_1.1.1_vendor__predictor_build.log`) incl. negative control. Inputs are plain numpy arrays (`PREDICTOR_RECORD_DTYPE` nodes + data matrices). |
| 4 | **Oracle-classifiable** per §3.1 (deterministic or tolerance-declarable) | ☑ PASS (classifiable) | float64 prediction / partial-dependence outputs → tolerance; tree topology deterministic for fixed input. Exact tolerance **derived+frozen at 1.1.3** (per-unit oracle.json). |
| 5 | **Golden runtime 50–500 ms** at chosen input scale | ☐ PENDING-1.1.5 | input-scale design recorded (MANIFEST §5, CF-4 ~500 ms bias). Golden **measured under the timing rig at 1.1.5**; no runtime claimed here (empirical-honesty: a number needs a raw pointer). |

**Status:** 4/5 confirmed; criterion 5 (golden timing) **pending the rig at 1.1.5**. Provisionally
admissible; admissibility is **sealed at 1.1.5** when the golden lands in band with a raw pointer. If the
golden falls outside 50–500 ms at every tractable input scale, the unit is dropped (recorded), per §4.2.

Cross-refs: `MANIFEST.md` (provenance + runtime `.so` cluster + driver design), `build_from_closure.sh`
(the standalone-IMPORT gate), `results/characterization/CORPUS_FOLD_LEDGER.md` (fold = `sklearn.ensemble`).
