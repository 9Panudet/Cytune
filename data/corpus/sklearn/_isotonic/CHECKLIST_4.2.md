# §4.2 admissibility checklist — `sklearn._isotonic`

Committed per Step 1.1.1 ("criteria checklist per unit committed", roadmap §7 row 1.1.1). A unit is
**admissible iff all 5** §4.2 criteria hold. Evidence pointers are to committed raw artifacts.
BUILD-CONFIRM is binding **STANDALONE IMPORT** (§4): cythonize-OK / compile-OK do not count.

| # | §4.2 criterion (verbatim intent) | verdict | evidence / note |
|---|---|---|---|
| 1 | **Non-templated `.pyx`** — Tempita `.pyx.tp` excluded (break source-hash determinism) | ☑ PASS | unit is `_isotonic.pyx`; vendored verbatim from sdist (sha256 `600f2b01…`). Not Tempita; no `include`. |
| 2 | **Stable upstream** — `scipy.special` excluded (Cython→C++/Pythran migration) | ☑ PASS | `sklearn.isotonic`, pinned at sdist sha256 `b4237ed7…` (1.5.2). Not `scipy.special`. |
| 3 | **Isolatable hot loop**, representative inputs from public APIs | ☑ PASS | vendored-closure build + **STANDALONE IMPORT `sklearn._isotonic`** in X′ (`build_from_closure.sh`; log `logs/corpus/STEP_1.1.1_vendor__isotonic_build.log`) incl. negative control. Closure is EMPTY (no repo cimport); inputs are plain contiguous numpy `float32`/`float64` 1-D arrays. |
| 4 | **Oracle-classifiable** per §3.1 (deterministic or tolerance-declarable) | ☑ PASS (classifiable) | result floats→tolerance; output shapes / unique-count / PAVA block indices→bit-exact. Exact tolerance **derived+frozen at 1.1.3** (per-unit oracle.json). |
| 5 | **Golden runtime 50–500 ms** at chosen input scale | ☐ PENDING-1.1.5 | input-scale design recorded (MANIFEST §5, CF-4 ~500 ms bias; fixed-seed length-`n` non-monotone `float64` to exercise pool+backtrack). Golden **measured under the timing rig at 1.1.5**; no runtime claimed here (empirical-honesty: a number needs a raw pointer). |

**Status:** 4/5 confirmed; criterion 5 (golden timing) **pending the rig at 1.1.5**. Provisionally
admissible; admissibility is **sealed at 1.1.5** when the golden lands in band with a raw pointer. If the
golden falls outside 50–500 ms at every tractable input scale, the unit is dropped (recorded), per §4.2.

Cross-refs: `MANIFEST.md` (provenance + EMPTY closure + driver design), `build_from_closure.sh` (the
STANDALONE-IMPORT gate), `logs/corpus/STEP_1.1.1_vendor__isotonic_build.log` (raw build-confirm output).
