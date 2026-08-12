# Corpus unit manifest — `sklearn.decomposition._online_lda_fast` (11th fold / margin)

Step 1.1.1 margin fold (human-ordered step 2b). `sklearn.decomposition` is a **new fold** added by
ordinary §4.2 curation (NOT the B-12 amendment). It secures the ≥10-fold floor independent of the
contingent `manifold` fold.

## 1. Identity & upstream pin
| field | value |
|---|---|
| codebase (LOMO fold) | `sklearn.decomposition` (**fold 11 — margin**) |
| unit | `_online_lda_fast.pyx` (Online LDA variational-inference inner math) |
| upstream version | scikit-learn **1.5.2** |
| **sdist sha256 (pin)** | `b4237ed7b3fdd0a4882792e68ef2545d5baa50aca3bb45aa7df468138ad8f94d` |
| build image | X′ = `localhost/motifbo-env:phase1` (`d45e33b0`); numpy 2.4.6 / Cython 3.2.5 / gcc-13 |
| kernel | `digamma`/`psi`, Dirichlet-expectation (1d/2d), `mean_change` (L1 convergence) |
| oracle classes (§3.1) | floats → tolerance (all outputs are float scalars/arrays; deterministic) |

## 2. Vendored cimport closure (FULL)
Same clean low-coupling profile as `sparsefuncs_fast`: one repo cimport, pure typedefs, **no co-built
`.so`**.

| vendored path (under `closure/`) | role | sha256 | == sdist? |
|---|---|---|---|
| `sklearn/decomposition/_online_lda_fast.pyx` | the unit | `00c1187ed26886613ce006b2a92027d025db01bd9a73f4002ff3926e33ac149c` | yes |
| `sklearn/utils/_typedefs.pxd` | cimported types (`float64_t,intp_t`) | `81ec3b62e0995b0a68f8959718322bc09dbe2bfea607e0b81a177f66ef4677ea` | yes |
| `sklearn/__init__.py`, `sklearn/decomposition/__init__.py`, `sklearn/utils/__init__.py` | empty pkg markers | — | n/a |

Closure-walk: cimports `cython.floating`, `libc.math` (builtins) + `from ..utils._typedefs cimport
float64_t, intp_t` (relative → vendored `_typedefs.pxd`, pure typedefs). Complete & minimal.

## 3. Build-confirm + determinism — VENDORED-CLOSURE gate
`build_from_closure.sh` in X′. Raw: `logs/corpus/STEP_1.1.1_vendor_online_lda_fast_build.log`.
- **POSITIVE:** cythonize → `gcc-13 -O3 -march=native -ffp-contract=fast -fopenmp` → `.so` (281 080 B)
  → bare-loader import OK; callables `mean_change`, `_dirichlet_expectation_1d`, `_dirichlet_expectation_2d`.
- **DETERMINISM SMOKE (criterion 4 support):** `mean_change` and `_dirichlet_expectation_2d` driven
  twice at kernel level with identical fixed-seed `float64` arrays (`OMP_NUM_THREADS=1`) → **bit-identical**.
  The unit has **no RNG and no `cython.parallel`** (fully serial) — so determinism is structural, not
  incidental. (This is the kernel-level deterministic driving the human asked to confirm.)
- **NEGATIVE CONTROL:** hide vendored `_typedefs.pxd` → cythonize fails → build uses the vendored closure.
  EXIT=0 overall.

## 4. §4.2 admissibility (see `CHECKLIST_4.2.md`)
| # | criterion | verdict | evidence |
|---|---|---|---|
| 1 | Non-templated `.pyx` | **PASS** | `.pyx`, not `.pyx.tp` |
| 2 | Stable upstream | **PASS** | `sklearn.decomposition`; not `scipy.special`; pinned sdist |
| 3 | Isolatable hot loop, public-API inputs | **PASS** | vendored-closure build+import (§3); inputs are plain `float64` arrays (numpy public API) |
| 4 | Oracle-classifiable per §3.1 | **PASS** | floats→tolerance; determinism smoke confirms reproducibility. Tolerance derived+frozen at 1.1.3 |
| 5 | Golden runtime 50–500 ms | **PENDING-1.1.5** | input-scale design below; golden measured under the rig at 1.1.5 (raw pointer there) |

**Admissibility: 4/5 confirmed; criterion 5 pending the rig at 1.1.5. Provisionally admissible →
counts as the confident fold securing the ≥10 floor.**

## 5. Driver calls + input-scale design (CF-4 ~500 ms bias)
Public hot-loop driver calls:
1. `mean_change(arr_1, arr_2)` — L1 mean abs change between two `float64` vectors (LDA convergence test)
2. `_dirichlet_expectation_2d(arr)` — `psi(arr) - psi(rowsum)` over a `(n_topics, n_features)` matrix
3. `_dirichlet_expectation_1d(doc_topic, alpha, out)` — 1-D variant

**Input-scale design (CF-4):** large fixed-seed `float64` matrix for `_dirichlet_expectation_2d`
(`(n_topics, n_features)`) and/or long vectors for `mean_change`, sized to land ~500 ms band-upper,
`OMP_NUM_THREADS=1`. **Exact shape calibrated at 1.1.5** under the timing rig (12 GB ceiling watched);
recorded here as a design target, not a measurement.

## 6. Carried obligations
- Criterion 5 golden + SHA-256 at **1.1.5**; oracle.json + §3.1 tolerance at **1.1.3**.
- Per-unit CI@30 ≤ 1 % at **1.2** (CF-1 quiesce-all, CF-3 band).
- **C** unit (no C++) → CF-5 does not apply.
