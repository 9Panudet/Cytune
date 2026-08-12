# §4.2 admissibility checklist — `sklearn.cluster._k_means_elkan`

Committed per Step 1.1.1 ("criteria checklist per unit committed", roadmap §7 row 1.1.1). A unit is
**admissible iff all 5** §4.2 criteria hold. Evidence pointers are to committed raw artifacts.

| # | §4.2 criterion (verbatim intent) | verdict | evidence / note |
|---|---|---|---|
| 1 | **Non-templated `.pyx`** — Tempita `.pyx.tp` excluded (breaks source-hash determinism) | ☑ PASS | unit is `_k_means_elkan.pyx` (not `.pyx.tp`); vendored verbatim from sdist (sha256 `b4c86968…`). Not Tempita. |
| 2 | **Stable upstream** — `scipy.special` excluded (Cython→C++/Pythran migration) | ☑ PASS | `sklearn.cluster`, pinned at sdist sha256 `b4237ed7…` (1.5.2). Not `scipy.special`. |
| 3 | **Isolatable hot loop**, representative inputs from public APIs | ☑ PASS | vendored-closure build + **STANDALONE IMPORT** of `sklearn.cluster._k_means_elkan` in X′ (`build_from_closure.sh`; log `logs/corpus/STEP_1.1.1_vendor__k_means_elkan_build.log`) incl. negative control. Co-built dep `_k_means_common.so` + runtime `extmath.row_norms` stub. Inputs: dense `float64` ndarrays + CSR `scipy.sparse` (public API). |
| 4 | **Oracle-classifiable** per §3.1 (deterministic or tolerance-declarable) | ☑ PASS (classifiable) | centers/bounds (floats) → tolerance; int `labels` (cluster assignment) → bit-exact. Exact tolerance **derived+frozen at 1.1.3** (per-unit oracle.json). |
| 5 | **Golden runtime 50–500 ms** at chosen input scale | ☐ PENDING-1.1.5 | input-scale design recorded (MANIFEST §5, CF-4 ~500 ms bias). Golden **measured under the timing rig at 1.1.5**; no runtime claimed here (empirical-honesty: a number needs a raw pointer). |

**Status:** 4/5 confirmed (import-OK); criterion 5 (golden timing) **pending the rig at 1.1.5**.
Provisionally admissible; admissibility **sealed at 1.1.5** when the golden lands in band with a raw
pointer. If the golden falls outside 50–500 ms at every tractable input scale, the unit is dropped
(recorded), per §4.2.

C-unit note: `_k_means_elkan` is **C** (gcc-13), so CF-5 (per-unit C++ sanitizer-clean obligation at
1.2) does not apply.

Cross-refs: `MANIFEST.md` (provenance + closure + driver design), `build_from_closure.sh` (the gate),
`logs/corpus/STEP_1.1.1_vendor__k_means_elkan_build.log` (raw build-confirm output).
