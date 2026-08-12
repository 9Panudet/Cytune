# MANIFEST — scipy.sparse.csgraph._shortest_path (Step 1.1.1 corpus unit)

## Identity
- **codebase**: scipy
- **fold**: scipy.csgraph
- **unit**: `_shortest_path`
- **target import module**: `scipy.sparse.csgraph._shortest_path`
- **kernel .pyx (sdist-relative)**: `scipy/sparse/csgraph/_shortest_path.pyx`
- **language**: C (Cython → gcc-13)
- **sdist pin**: scipy 1.13.1
  - tarball sha256: `095a87a0312b08dfd6a6155cbbd310a8c51800fc931b8c0b84003014b874ed3c`  (== task spec)

## Full vendored closure (per-file sha256 == sdist)
| closure path | role | sha256 (== sdist file) |
|---|---|---|
| `closure/scipy/sparse/csgraph/_shortest_path.pyx` | kernel `.pyx` (plain, NOT Tempita) | `712f09ddb3b94e6e8219b1f39bdba7887a09f90170bae8caad08b8d2de68ddd9` |
| `closure/scipy/sparse/csgraph/parameters.pxi` | textual `include 'parameters.pxi'` — DTYPE/ITYPE typedefs, `int32_or_int64` fused types, `NULL_IDX` DEF | `8cd4bdb208af7c822218cc1f32d16bc809c048c1778bace74b29e51ebb2de3c9` |
| `closure/scipy/__init__.py` | empty package marker | (empty) |
| `closure/scipy/sparse/__init__.py` | empty package marker | (empty) |
| `closure/scipy/sparse/csgraph/__init__.py` | empty package marker | (empty) |

The two source files are copied verbatim from the sdist (no edits); their hashes equal the sdist's.

## Closure-walk result (why the closure is exactly this)
From `_shortest_path.pyx` (and there is **no** sibling `.pxd` in `csgraph/`):
- **cimports** — all Cython/stdlib/numpy builtins, so **NONE are vendored**:
  - `cimport numpy as np` (numpy headers come from the image's numpy)
  - `cimport cython`
  - `from libc.stdlib cimport malloc, free`
  - `from libc.math cimport INFINITY`
- **`include 'parameters.pxi'`** — a *textual* include (not a cimport). It is a sibling file in
  `csgraph/`, vendored into the closure. Hiding it breaks cythonize (negative control below).
- **module-scope Python `import`** — resolved at runtime against the **image's** scipy (closure-walk
  rule 5; scipy.sparse is available in X'), so NOT vendored:
  - `import warnings`, `import numpy as np`
  - `from scipy.sparse import csr_matrix, issparse`
  - `from scipy.sparse.csgraph._validation import validate_graph`
  - `from scipy.sparse._sputils import convert_pydata_sparse_to_scipy`
- **No `cdef class` / non-inline `cdef`/`cpdef` is cimported from any other repo module** ⇒ no sibling
  `.so` cluster to co-build. (This is a C unit; the C++ sibling-`.so` obligation does not apply.)
- **No package-context stubs needed** — there is no `from . import <helper>`; the empty `__init__.py`
  markers suffice.

## Reference directive set (as-shipped config used for cythonize)
- scipy unit ⇒ **bare `-3`**. scipy's per-function `@cython.boundscheck(False)` decorators (8 of them,
  at lines 344/637/666/705/740/785/829/881 of the .pyx) are the as-shipped pins and are preserved
  verbatim by copying the file unedited.
- **cythonize**: `cython -3 -I scipy/sparse/csgraph _shortest_path.pyx`  (`-I` so `include 'parameters.pxi'` resolves against the vendored dir only).
- **compile (C)**: `gcc-13 -shared -fPIC -O3 -march=native -ffp-contract=fast -fopenmp -I<pyinclude> -I<numpy-include>`.
  `-ffp-contract=fast` is passed explicitly per §3.2 (never left to GCC's default).

## Build-confirm (STANDALONE IMPORT — binding, §4)
- In-container only: `localhost/motifbo-env:phase1` (X'), via
  `podman run --rm -v <unit_dir>:/unit:ro,Z localhost/motifbo-env:phase1 bash /unit/build_from_closure.sh`.
- Built FROM THE VENDORED CLOSURE ALONE → `.so` = **423640 bytes**.
- STANDALONE-IMPORTED under its true FQ name `scipy.sparse.csgraph._shortest_path` with
  `OMP_NUM_THREADS=1`; module-init Python imports resolve against image scipy.
  Exported: `shortest_path, dijkstra, bellman_ford, floyd_warshall, johnson, NegativeCycleError, DTYPE, ITYPE`.
  → **`IMPORT-OK scipy.sparse.csgraph._shortest_path`**.
- **Negative control**: hide vendored `parameters.pxi` ⇒ cythonize fails
  (`'parameters.pxi' not found`) ⇒ proves the build resolves the `include` against the VENDORED
  closure, not anything installed.
- Raw log: `logs/corpus/STEP_1.1.1_vendor__shortest_path_build.log`.
- Build environment in X': Python 3.12.3, gcc-13 13.3.0, Cython 3.2.5, numpy 2.4.6, image scipy 1.17.1
  (image scipy is IRRELEVANT to the compile; it only services the runtime py-imports above).

## Hot-loop driver calls (for the 1.1.5 golden / timing rig)
Public entry points (all in the built module):
- `shortest_path(csgraph, method='auto'|'FW'|'D'|'BF'|'J', directed=, return_predecessors=, unweighted=, overwrite=, indices=)`
- `floyd_warshall(csgraph, ...)`  — dense O(N^3) inner triple loop (`_floyd_warshall`, .pyx:345)
- `dijkstra(csgraph, ..., indices=)`  — Fibonacci-heap kernels (`_dijkstra_*`, .pyx:741–882)
- `bellman_ford(csgraph, ..., indices=)`  — `_bellman_ford_*` (.pyx:1075/1116)
- `johnson(csgraph, ..., indices=)`  — `_johnson_*` (.pyx:1357/1390)

**Input-scale design (DESIGN target only; NO runtime number is claimed here — golden measured at 1.1.5
per CF-4):** drive the dense O(N^3) `floyd_warshall` path with a random-but-fixed-seed sparse CSR
adjacency on the order of N≈400–600 nodes (a `floyd_warshall` of N≈500 is the natural ~500ms-class
target), and the Dijkstra/Bellman-Ford/Johnson paths with a larger-N sparse CSR over a fixed index set,
biased toward ~500ms per CF-4. Exact N is fixed and the golden is measured in-container at 1.1.5.

## Oracle classification (§3.1)
Pure-numeric, deterministic kernels — **no RNG, no file/network/OS IO** in the .pyx. Outputs are the
distance matrix (DTYPE float64) and, optionally, the predecessor matrix (ITYPE int32). ⇒
**deterministic / exact-reproducible** oracle class: a frozen golden output array compared
elementwise (bitwise-equal for the integer predecessor matrix; tight numeric tolerance for the float64
distances under the pinned `-ffp-contract=fast`). `NegativeCycleError` on negative-cycle inputs is a
classifiable deterministic exception. No tiered/statistical oracle needed.

## Carried obligations / notes
- **C++ sanitizer obligation (CF-5 @ 1.2)**: N/A — this is a **C** unit, not C++. No per-unit
  sanitizer obligation is carried for it.
- §4.2 criterion 5 (golden 50–500 ms): **PENDING-1.1.5** (measured in-container; no number claimed now).
- DO NOT commit from this subagent; only this unit's files + its log were written.
