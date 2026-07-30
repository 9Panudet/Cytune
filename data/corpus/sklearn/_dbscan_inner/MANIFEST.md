# Corpus unit manifest — `sklearn.cluster._dbscan_inner`

Step 1.1.1 vendoring. Per-unit provenance + admissibility record. This is a **C++ unit**
(`from libcpp.vector cimport vector`) — the DBSCAN fast inner DFS loop (connected-components labeling).

## 1. Identity & upstream pin
| field | value |
|---|---|
| codebase (LOMO fold) | `sklearn.cluster` |
| unit | `_dbscan_inner.pyx` |
| target import module | `sklearn.cluster._dbscan_inner` |
| upstream version | scikit-learn **1.5.2** |
| sdist | `scikit_learn-1.5.2.tar.gz` |
| **sdist sha256 (upstream pin)** | `b4237ed7b3fdd0a4882792e68ef2545d5baa50aca3bb45aa7df468138ad8f94d` |
| build image | X′ = `localhost/motifbo-env:phase1`; Python 3.12.3 / numpy 2.4.6 / Cython 3.2.5 / g++-13 (13.3.0) |
| language | **C++** (`libcpp.vector`); g++-13 `--cplus -std=c++14` |
| §4.3 kernel | DFS connected-components labeling over precomputed neighborhoods (core/non-core) |
| §4.3 oracle classes | integer cluster labels → **bit-exact** (no floats in the kernel) |

## 2. Vendored cimport closure (FULL)
The unit's compile-time closure is **two source files** + package markers. The cimported `_typedefs`
symbols (`uint8_t`, `intp_t`) are pure compile-time C `ctypedef`s — `_typedefs.pxd` cimports nothing,
includes no numpy header, has **no runtime `.so` to co-build** (CLOSURE-WALK rule 4: `ctypedef` is
compile-time only → `.pxd` suffices). `libcpp.vector` is a Cython/libcpp builtin → no vendoring.
Genuinely low-coupling.

| vendored path (under `closure/`) | role | sha256 | == sdist? |
|---|---|---|---|
| `sklearn/cluster/_dbscan_inner.pyx` | the unit (the C++ DFS kernel) | `0a1578e38a7e6cba9f578a356745e4c36e6692fb4a4f27b5653a29d3f923824f` | yes |
| `sklearn/utils/_typedefs.pxd` | cimported types (`uint8_t`, `intp_t`) | `81ec3b62e0995b0a68f8959718322bc09dbe2bfea607e0b81a177f66ef4677ea` | yes |
| `sklearn/__init__.py` | empty pkg marker (NOT upstream `__init__`) | — | n/a (stub) |
| `sklearn/cluster/__init__.py` | empty pkg marker (NOT upstream `__init__`) | — | n/a (stub) |
| `sklearn/utils/__init__.py` | empty pkg marker (NOT upstream `__init__`) | — | n/a (stub) |

Closure-walk: `_dbscan_inner.pyx` cimports `libcpp.vector` (Cython/libcpp builtin — no vendoring) and
`from ..utils._typedefs cimport uint8_t, intp_t` (relative → `sklearn/utils/_typedefs.pxd`).
`_typedefs.pxd` cimports nothing and declares only `ctypedef`s → no recursion, no co-built `.so`. There
is **no sibling `_dbscan_inner.pxd`**, and there are **no module-scope Python `import` / `from . import`**
statements in the `.pyx` (so no package-context stub is required). Closure is **complete and minimal**.
The empty package-marker stubs establish `sklearn.cluster.*` / `sklearn.utils.*` package depth for the
relative cimport without dragging in the heavyweight upstream `__init__` (and its `__check_build` guard).

## 3. Build-confirm — STANDALONE IMPORT from the VENDORED CLOSURE (binding, §4)
`build_from_closure.sh`, run in X′. Cythonizes `--cplus` with the **sklearn reference directive set**,
compiles with **g++-13 `-std=c++14`** (C++ unit; `-O1` for faster compile, all other flags per spec),
then STANDALONE-IMPORTs `_dbscan_inner` via a bare loader from the `.so` alone — NOT the extracted sdist
tree, NOT installed sklearn. Evidence (raw): `logs/corpus/STEP_1.1.1_vendor__dbscan_inner_build.log`.

Reference directives (sklearn, as-shipped):
`-X language_level=3 -X boundscheck=False -X wraparound=False -X initializedcheck=False -X nonecheck=False -X cdivision=True`

- **POSITIVE:** cythonize `--cplus` → `g++-13 -std=c++14 -shared -fPIC -O1 -march=native -ffp-contract=fast
  -fopenmp` → `.so` (**197 104 bytes**) → bare-loader **IMPORT-OK**; exported callable `dbscan_inner`
  present (asserted). Printed line: `IMPORT-OK sklearn.cluster._dbscan_inner; exported callables: ['dbscan_inner']`.
- **NEGATIVE CONTROL (non-vacuity):** hide the vendored `_typedefs.pxd` → cythonize **fails** at
  `_dbscan_inner.pyx:29` (`Invalid index for memoryview specified, type <error>` — the `intp_t` index type
  is unresolved). Proves the build resolves the cimport from the **vendored closure**, not installed
  sklearn. Overall EXIT=0 (positive passes, negative fails as required).

## 4. §4.2 admissibility (all 5 criteria — see `CHECKLIST_4.2.md`)
| # | §4.2 criterion | determination | evidence |
|---|---|---|---|
| 1 | Non-templated `.pyx` | **PASS** | vendored file is `.pyx` (not `.pyx.tp`); no Tempita sibling |
| 2 | Stable upstream (not `scipy.special`) | **PASS** | `sklearn.cluster`; pinned sdist sha256 `b4237ed7…` |
| 3 | Isolatable hot loop, public-API inputs | **PASS** | vendored-closure build + STANDALONE IMPORT in X′ (§3) incl. negative control; inputs via `NearestNeighbors.radius_neighbors` public API |
| 4 | Oracle-classifiable per §3.1 | **PASS (classifiable)** | integer labels → **bit-exact** (no floats in kernel). Per-unit oracle.json frozen at **1.1.3** |
| 5 | Golden runtime 50–500 ms | **PENDING-1.1.5** | input-scale design recorded (§5); golden **measured under the timing rig at 1.1.5** (raw pointer there). No runtime number claimed here — empirical-honesty. |

**Admissibility status: 4/5 confirmed; criterion 5 (golden timing) pending the rig at 1.1.5.** A unit is
admissible iff ALL 5 (§4.2) — so this unit is **provisionally admissible**; final seal at 1.1.5.

## 5. Hot-loop driver call + input-scale design (criterion 3 inputs; CF-4 ~500 ms bias)
The single public kernel is `dbscan_inner(is_core, neighborhoods, labels)` (upstream call site:
`sklearn/cluster/_dbscan.py:436` → `dbscan_inner(core_samples, neighborhoods, labels)`). Representative
inputs are constructible from the public `sklearn.neighbors.NearestNeighbors` API:
1. Build a fixed-seed point cloud `X` (`shape (n_samples, n_features)`, deterministic generator).
2. `neighborhoods = NearestNeighbors(radius=eps).fit(X).radius_neighbors(X, return_distance=False)`
   (a `np.ndarray` of `object` — one `intp` index array per sample).
3. `is_core = (n_neighbors >= min_samples).astype(np.uint8)`; `labels = np.full(n_samples, -1, intp)`.
4. Call `dbscan_inner(is_core, neighborhoods, labels)`; labels is mutated in place (the DFS output).

**Input-scale design (CF-4):** bias `n_samples` / `eps` (hence neighborhood density and total edges
traversed by the DFS) toward the ~500 ms band-upper to dilute the unresolved CF-4 offset (≈1.6 % at 500 ms
vs ≈16 % at 50 ms) and keep CF-3 CI@30 ≤ 1 % reachable, with `OMP_NUM_THREADS=1`. The runtime is governed
by total edges (Σ neighborhood sizes) visited in the connected-components walk; `eps` controls density.
The **exact `n_samples`/`eps` that lands ~500 ms is calibrated at 1.1.5** under the timing rig (watch the
12 GB container ceiling — the `object`-array of neighborhoods is the memory driver). Recorded here as a
**design target, not a measurement** — no runtime number is claimed at 1.1.1.

## 6. Carried obligations
- Criterion 5 golden + SHA-256 sealed at **1.1.5**; per-unit oracle.json + §3.1 classification at **1.1.3**
  (integer labels → bit-exact; note DBSCAN cluster-id numbering depends on traversal order, so the oracle
  compares label **partitions** / canonicalized ids, decided at 1.1.3).
- Per-unit timing precision (CF-3 band, CI@30 ≤ 1 %) re-established at **1.2** under quiesce-all (CF-1).
- **C++ unit → CF-5 per-unit sanitizer-clean (ASan/UBSan) obligation APPLIES at 1.2** (the DFS uses
  `libcpp.vector` push_back/pop_back/back and memoryview indexing — sanitizer-clean must be demonstrated).
