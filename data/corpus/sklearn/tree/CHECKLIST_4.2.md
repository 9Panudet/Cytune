# §4.2 admissibility checklist — `sklearn.tree` fold (`_tree`, `_criterion`, `_splitter`)

Admissible iff all 5 §4.2 criteria. Build-confirm = standalone IMPORT (§4), reference `cdivision=True`.

| # | §4.2 criterion | `_tree` | `_criterion` | `_splitter` | evidence |
|---|---|---|---|---|---|
| 1 | Non-templated `.pyx` | ☑ | ☑ | ☑ | all `.pyx` (not `.pyx.tp`); sha256 == sdist |
| 2 | Stable upstream | ☑ | ☑ | ☑ | `sklearn.tree`, pinned sdist `b4237ed7…` |
| 3 | Isolatable hot loop, public-API inputs | ☑ | ☑ | ☑ | fold-cluster build + **IMPORT-OK** (`build_from_closure.sh`); inputs via sklearn tree public API |
| 4 | Oracle-classifiable per §3.1 | ☑ | ☑ | ☑ | split indices/structure→bit-exact; impurity→tolerance (§4.3). Tolerance frozen at 1.1.3 |
| 5 | Golden runtime 50–500 ms | ☐ | ☐ | ☐ | PENDING-1.1.5 (rig; no number claimed) |

**Status:** criteria 1–4 PASS for all 3; criterion 5 PENDING-1.1.5. **Provisionally admissible.**
**CF-5 (C++): per-unit sanitizer-clean + `detect_leaks=1` leak-audit at 1.2/preflight before each counts.**
Cross-refs: `MANIFEST.md`, `build_from_closure.sh`, `results/characterization/{CORPUS_FOLD_LEDGER,CYTHON_3.2.5_COMPAT_BLOCKER,THETA_DIRECTIVE_POLICY}.md`.
