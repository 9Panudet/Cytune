# §4.2 admissibility checklist — `sklearn.manifold._barnes_hut_tsne` (CONTINGENT)

| # | §4.2 criterion | verdict | evidence / note |
|---|---|---|---|
| 1 | Non-templated `.pyx` | ☑ PASS | `.pyx`, sha256 == sdist |
| 2 | Stable upstream | ☑ PASS | `sklearn.manifold`, pinned sdist `b4237ed7…` |
| 3 | Isolatable hot loop, public-API inputs | ☑ PASS | deep-cluster build + **IMPORT-OK** (`build_from_closure.sh`; `…vendor_barnes_hut_tsne_build.log`) |
| 4 | Oracle-classifiable per §3.1 | ☑ **PASS** | **determinism PROVEN at 1.1.3** — kernel-level `gradient()` twice with fixed embedding + fixed CSR P-matrix, `num_threads=1`/`OMP_NUM_THREADS=1` → forces bit-identical (sha256 `782b36d5…`) + KL error bit-identical. Oracle class floats→tolerance (reproducible golden under fixed config). Raw: `logs/corpus/STEP_1.1.3_manifold_tsne_determinism.log` |
| 5 | Golden runtime 50–500 ms | ☐ PENDING-1.1.5 | rig; no number claimed |

**Status:** 1–4 PASS (determinism cleared at 1.1.3), 5 PENDING-1.1.5. **Manifold COUNTS toward §4.1b →
corpus = 11 folds** (tolerate-one-loss margin). Determinism is under the operative `OMP_NUM_THREADS=1`
config (the binding protocol); `num_threads>1` would reintroduce prange-reduction non-determinism, excluded
by the quiesce-all/OMP=1 protocol. Cross-refs: `MANIFEST.md`, `results/characterization/CORPUS_FOLD_LEDGER.md`.
