# §4.2 admissibility checklist — `sklearn.cluster._dbscan_inner`

Committed per Step 1.1.1 ("criteria checklist per unit committed", roadmap §7 row 1.1.1). A unit is
**admissible iff all 5** §4.2 criteria hold. Evidence pointers are to committed raw artifacts.
This is a **C++ unit** (`libcpp.vector`).

| # | §4.2 criterion (verbatim intent) | verdict | evidence / note |
|---|---|---|---|
| 1 | **Non-templated `.pyx`** — Tempita `.pyx.tp` excluded (breaks source-hash determinism) | ☑ PASS | unit is `_dbscan_inner.pyx`; vendored verbatim from sdist (sha256 `0a1578e3…`). No `.pyx.tp` sibling — not Tempita. |
| 2 | **Stable upstream** — `scipy.special` excluded (Cython→C++/Pythran migration) | ☑ PASS | `sklearn.cluster`, pinned at sdist sha256 `b4237ed7…` (1.5.2). Not `scipy.special`. |
| 3 | **Isolatable hot loop**, representative inputs from public APIs | ☑ PASS | vendored-closure build + **STANDALONE IMPORT** in X′ (`build_from_closure.sh`; log `logs/corpus/STEP_1.1.1_vendor__dbscan_inner_build.log`) incl. negative control. Inputs via `sklearn.neighbors.NearestNeighbors.radius_neighbors` public API. |
| 4 | **Oracle-classifiable** per §3.1 (deterministic or tolerance-declarable) | ☑ PASS (classifiable) | integer cluster labels → **bit-exact** (no floats in kernel). Partition/canonical-id comparison + per-unit oracle.json **frozen at 1.1.3**. |
| 5 | **Golden runtime 50–500 ms** at chosen input scale | ☐ PENDING-1.1.5 | input-scale design recorded (MANIFEST §5, CF-4 ~500 ms bias via `n_samples`/`eps`). Golden **measured under the timing rig at 1.1.5**; no runtime claimed here (empirical-honesty: a number needs a raw pointer). |

**Status:** 4/5 confirmed; criterion 5 (golden timing) **pending the rig at 1.1.5**. Provisionally
admissible; admissibility is **sealed at 1.1.5** when the golden lands in band with a raw pointer. If the
golden falls outside 50–500 ms at every tractable input scale, the unit is dropped (recorded), per §4.2.

C++ note: this unit carries the **CF-5 per-unit sanitizer-clean obligation at 1.2** (ASan/UBSan over the
`libcpp.vector` DFS + memoryview indexing).

Cross-refs: `MANIFEST.md` (provenance + closure + driver design), `build_from_closure.sh` (the gate),
`logs/corpus/STEP_1.1.1_vendor__dbscan_inner_build.log` (raw build-confirm output).
