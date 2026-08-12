"""Per-unit driver registry for the Step-1.2 corpus campaign (roadmap §4.4 / §5.1).

Each entry carries the metadata to BUILD the unit (vendored closure / pyx / language) and
to DRIVE it: a `setup` recipe (a function returning the setup_code string that constructs
`args` UNTIMED in the child) + the public `kernel` callable name. Recipes are deterministic
in (scale, seed); the actual ~480-500 ms golden scale is chosen at G3 and fingerprinted by
input_manifest. Built incrementally — the 4 archetypes first, then the rest at replication.

Driving discipline (the harness enforces the timed region): construction is OUTSIDE the
timed region; the kernel is called AS CLOSE TO THE KERNEL AS POSSIBLE (wrapper units call
the chunked/inner function directly, not the high-level estimator) so criterion-3 reflects
the kernel, not estimator bookkeeping.
"""
SEED = 20260625


def csr_mean_variance_setup(scale, seed=SEED):
    """sparsefuncs_fast.csr_mean_variance_axis0 — two-pass CSR column variance over a random
    float64 CSR matrix (streaming/memory-bound archetype). args = (X_csr, weights).

    FAST deterministic O(nnz)-memory builder, BINOMIAL per-row counts (the scipy.sparse.random
    density model: each row ~ Binomial(n_features, density)). scipy.sparse.random is UNUSABLE at
    the golden: its replace=False coordinate choice peaks ~176 B/nnz (40M nnz -> 7.0 GB; 85M ->
    OOM at 12 GB, RECIPE_REVISION.md). This builder peaks ~12 B/nnz. TIMING-EQUIVALENT to
    scipy.sparse.random (measured ratio 0.994; per-row nnz std 3.08 vs 3.08; same total nnz):
    a FIXED nnz_per_row builder was 16% too fast (ratio 0.84) because constant inner-loop trip
    counts removed the branch-misprediction the variable (binomial) row counts cause — so the
    per-row count distribution MUST match, not just the total nnz (RECIPE_REVISION.md, builder
    equivalence). Column ids random (sorted vs unsorted is timing-irrelevant: the n_features-float
    accumulator is L1-resident)."""
    n_samples = int(scale["n_samples"]); n_features = int(scale["n_features"])
    density = scale["density"]
    return f"""
import numpy as np
from scipy.sparse import csr_matrix
rng = np.random.default_rng({seed})
n_samples, n_features, density = {n_samples}, {n_features}, {density}
counts = rng.binomial(n_features, density, size=n_samples).astype(np.int32)
indptr = np.zeros(n_samples + 1, dtype=np.int32); np.cumsum(counts, out=indptr[1:])
nnz = int(indptr[-1])
data = rng.standard_normal(nnz)
indices = rng.integers(0, n_features, size=nnz, dtype=np.int32)
X = csr_matrix((data, indices, indptr), shape=(n_samples, n_features))
weights = rng.uniform(0.5, 2.0, n_samples)
args = (X, weights)
kwargs = {{}}
"""


def pava_setup(scale, seed=SEED):
    """_isotonic._inplace_contiguous_isotonic_regression(y, w) — pool-adjacent-violators,
    IN-PLACE on y (and w). args = (y, w). Random y has ~50% adjacent violators -> real pooling
    on the FIRST call; a second call on the now-isotonic y is a degenerate no-op (NOT
    re-callable -> the timed endpoint needs a per-rep input refresh; see report)."""
    n = int(scale["n"])
    return f"""
import numpy as np
rng = np.random.default_rng({seed})
n = {n}
y = rng.standard_normal(n)                 # float64 C-contiguous; many adjacent violators
w = rng.uniform(0.5, 2.0, n)
args = (y, w)
kwargs = {{}}
"""


def dbscan_setup(scale, seed=SEED):
    """_dbscan_inner.dbscan_inner(is_core, neighborhoods, labels) — DFS cluster expansion,
    labels filled IN-PLACE from -1. args = (is_core uint8[n], neighborhoods object[n] of intp
    arrays, labels intp[n]=-1). Re-call skips all (labels!=-1) -> degenerate no-op (NOT
    re-callable). neighborhoods is a numpy object array (each entry an intp neighbor list)."""
    n = int(scale["n"]); deg = int(scale["avg_deg"])
    return f"""
import numpy as np
rng = np.random.default_rng({seed})
n = {n}; deg = {deg}
is_core = (rng.random(n) < 0.8).astype(np.uint8)            # 80% core points
flat = rng.integers(0, n, size=n * deg, dtype=np.intp).reshape(n, deg)
neighborhoods = np.empty(n, dtype=object)
for i in range(n):
    neighborhoods[i] = flat[i]
labels = np.full(n, -1, dtype=np.intp)
args = (is_core, neighborhoods, labels)
kwargs = {{}}
"""


def lloyd_setup(scale, seed=SEED):
    """_k_means_lloyd.lloyd_iter_chunked_dense — ONE Lloyd iteration, dense. centers_old is
    READ-ONLY input; centers_new/weight_in_clusters/labels/center_shift are OUT buffers the
    kernel re-zeros internally each call -> RE-CALLABLE (identical work every rep, since
    centers_old is never updated here). n_threads=1 (single isolated core). args carry the
    full call tuple. Driven at the kernel (not KMeans.fit) so criterion-3 reflects the loop."""
    ns = int(scale["n_samples"]); nf = int(scale["n_features"]); nc = int(scale["n_clusters"])
    return f"""
import numpy as np
rng = np.random.default_rng({seed})
n_samples, n_features, n_clusters = {ns}, {nf}, {nc}
X = np.ascontiguousarray(rng.standard_normal((n_samples, n_features)))
sample_weight = rng.uniform(0.5, 2.0, n_samples)
centers_old = np.ascontiguousarray(rng.standard_normal((n_clusters, n_features)))
centers_new = np.zeros((n_clusters, n_features))
weight_in_clusters = np.zeros(n_clusters)
labels = np.zeros(n_samples, dtype=np.int32)
center_shift = np.zeros(n_clusters)
args = (X, sample_weight, centers_old, centers_new, weight_in_clusters, labels,
        center_shift, 1, True)
kwargs = {{}}
"""


def dirichlet2d_setup(scale, seed=SEED):
    """_online_lda_fast._dirichlet_expectation_2d(arr) — E[log θ] for θ~Dir(arr), i.e.
    psi(arr) - psi(rowsum(arr)) over a 2-D positive float64 array. Transcendental
    (Bernoulli-series psi) per element -> COMPUTE-bound (not memory-bound). Pure function;
    arr is const, returns a fresh array -> re-callable, no per-rep regen. args = (arr,)."""
    nr = int(scale["n_rows"]); nc = int(scale["n_cols"])
    return f"""
import numpy as np
rng = np.random.default_rng({seed})
arr = rng.gamma(2.0, 1.0, size=({nr}, {nc}))      # strictly-positive Dirichlet params, float64 C-contig
args = (arr,)
kwargs = {{}}
"""


def map_to_bins_setup(scale, seed=SEED):
    """_binning._map_to_bins(data, thresholds_list, is_categorical, missing_idx, n_threads, binned)
    — per-element binary search of each column into ~255 increasing thresholds (branch/search,
    boundscheck-sensitive). data const, binned written deterministically -> re-callable. n_threads=1
    (single isolated core). binned is uint8 FORTRAN-aligned ([::1,:]). args carry the full tuple."""
    ns = int(scale["n_samples"]); nf = int(scale["n_features"]); nb = int(scale.get("n_bins", 255))
    return f"""
import numpy as np
rng = np.random.default_rng({seed})
n_samples, n_features, n_bins = {ns}, {nf}, {nb}
data = np.ascontiguousarray(rng.standard_normal((n_samples, n_features)))   # float64 (X_DTYPE_C)
# per-feature increasing thresholds = sorted quantile-spaced cut points (n_bins-1 of them)
binning_thresholds = [np.sort(rng.standard_normal(n_bins - 1)).astype(np.float64)
                      for _ in range(n_features)]
is_categorical = np.zeros(n_features, dtype=np.uint8)
binned = np.zeros((n_samples, n_features), dtype=np.uint8, order='F')        # X_BINNED_DTYPE_C, F-aligned
args = (data, binning_thresholds, is_categorical, np.uint8(n_bins), 1, binned)
kwargs = {{}}
"""


def ppoly_evaluate_setup(scale, seed=SEED):
    """_ppoly.evaluate(c, x, xp, dx, extrapolate, out) — piecewise-polynomial evaluation:
    per query point, BISECT the interval in x then HORNER-evaluate the degree-(k-1) poly. This is
    the Horner-FP archetype (the I-1 numeric reference hit 9.4x on a Horner loop). Inputs const, out
    overwritten deterministically -> re-callable. args = (c, x, xp, 0, True, out)."""
    k = int(scale.get("k", 4)); m = int(scale["m"]); p = int(scale["p"])
    return f"""
import numpy as np
rng = np.random.default_rng({seed})
k, m, p = {k}, {m}, {p}
c = np.ascontiguousarray(rng.standard_normal((k, m, 1)))           # (order, intervals, 1) float64
x = np.sort(rng.uniform(0.0, 1.0, size=m + 1)).astype(np.float64)  # increasing breakpoints (m+1,)
x[0] = 0.0; x[-1] = 1.0
xp = rng.uniform(0.0, 1.0, size=p).astype(np.float64)              # query points within [0,1]
out = np.empty((p, 1), dtype=np.float64)
args = (c, x, xp, 0, True, out)
kwargs = {{}}
"""


def floyd_setup(scale, seed=SEED):
    """_shortest_path.floyd_warshall(csgraph) — dense O(N^3) all-pairs shortest path. The hot loop
    dist[i,j]=min(dist[i,j],dist[i,k]+dist[k,j]) is index/array-bound -> the strongest remaining
    HIGH-Δ candidate (boundscheck-sensitive like csr). csgraph = dense NxN positive weights (complete
    graph; only the diagonal is 0 = no self-edge). overwrite=False -> input not mutated -> re-callable.
    validate_graph resolves to the installed scipy (config-invariant plumbing, dilutes Δ conservatively)."""
    N = int(scale["N"])
    return f"""
import numpy as np
rng = np.random.default_rng({seed})
N = {N}
csgraph = rng.uniform(0.1, 1.0, size=(N, N)).astype(np.float64)   # complete weighted graph
np.fill_diagonal(csgraph, 0.0)
args = (csgraph,)
kwargs = {{"directed": True, "overwrite": False}}
"""


def connected_components_setup(scale, seed=SEED):
    """_traversal.connected_components(csgraph) — (n_components, labels) over a sparse CSR graph via
    BFS over typed memoryviews -> pointer-ish, projected LOW-Δ. csgraph = random CSR. Input not
    mutated -> re-callable. validate_graph resolves to the installed scipy."""
    N = int(scale["N"]); deg = int(scale["avg_deg"])
    return f"""
import numpy as np
from scipy.sparse import csr_matrix
rng = np.random.default_rng({seed})
N, deg = {N}, {deg}
nnz = N * deg
rows = rng.integers(0, N, size=nnz)
cols = rng.integers(0, N, size=nnz)
data = np.ones(nnz, dtype=np.float64)
csgraph = csr_matrix((data, (rows, cols)), shape=(N, N))
args = (csgraph,)
kwargs = {{"directed": False}}
"""


def elkan_setup(scale, seed=SEED):
    """_k_means_elkan.elkan_iter_chunked_dense — ONE chunked dense Elkan EM iteration. The hot
    work is the per-point Euclidean distance computation (_euclidean_dense_dense, in the co-built
    _k_means_common) gated by triangle-inequality bound pruning. Elkan bounds are initialised in
    numpy EXACTLY as init_bounds_dense would (labels = nearest centre, upper_bounds = that distance,
    lower_bounds = all centre distances) so the kernel runs a VALID first iteration. The kernel
    MUTATES upper/lower bounds, labels, centers_new, weight_in_clusters, center_shift (update_centers
    =True) -> NOT re-callable -> per-rep regen (v1.4). All arrays float64 C-contig; labels int32;
    n_threads=1 (single isolated core). This is the candidate VECTORIZATION-sensitive unit (like
    floyd): the distance inner loop is the lever -O3/-march=native can move."""
    ns = int(scale["n_samples"]); nf = int(scale["n_features"]); nc = int(scale["n_clusters"])
    return f"""
import numpy as np
rng = np.random.default_rng({seed})
n_samples, n_features, n_clusters = {ns}, {nf}, {nc}
X = np.ascontiguousarray(rng.standard_normal((n_samples, n_features)))
sample_weight = np.ones(n_samples)
centers_old = np.ascontiguousarray(rng.standard_normal((n_clusters, n_features)))
centers_new = np.zeros((n_clusters, n_features))
weight_in_clusters = np.zeros(n_clusters)
# pairwise centre distances (k,k) -> center_half_distances + distance_next_center
cc2 = ((centers_old*centers_old).sum(1)[:, None] + (centers_old*centers_old).sum(1)[None, :]
       - 2.0*(centers_old @ centers_old.T))
np.maximum(cc2, 0.0, out=cc2)
cdist_cc = np.sqrt(cc2)
center_half_distances = np.ascontiguousarray(0.5*cdist_cc)
_dnc = cdist_cc + np.eye(n_clusters)*1e18                 # mask self-distance
distance_next_center = np.ascontiguousarray(_dnc.min(axis=1))
# init bounds EXACTLY as init_bounds_dense: nearest centre + all centre distances (via BLAS gram)
d2 = ((X*X).sum(1)[:, None] + (centers_old*centers_old).sum(1)[None, :] - 2.0*(X @ centers_old.T))
np.maximum(d2, 0.0, out=d2)
d = np.sqrt(d2)
labels = np.ascontiguousarray(np.argmin(d, axis=1).astype(np.int32))
upper_bounds = np.ascontiguousarray(d[np.arange(n_samples), labels])
lower_bounds = np.ascontiguousarray(d)
center_shift = np.zeros(n_clusters)
args = (X, sample_weight, centers_old, centers_new, weight_in_clusters, center_half_distances,
        distance_next_center, upper_bounds, lower_bounds, labels, center_shift, 1)
kwargs = {{"update_centers": True}}
"""


def predictor_setup(scale, seed=SEED):
    """_predictor._predict_from_raw_data — HGBT tree inference: per row, walk root->leaf following
    num_threshold comparisons (data-dependent pointer-chase over node_struct records). Pure
    tree-DFS, latency-bound, NOT vectorizable -> projected LOW-Δ (the _predictor/cc class). A
    complete balanced binary tree of depth D (all numeric splits, no categorical) is built as a
    PREDICTOR_RECORD_DTYPE structured array; numeric_data ~ N(0,1) so splits at threshold 0 route
    ~50/50. out is fully overwritten from const inputs -> RE-CALLABLE (no regen). n_threads=1."""
    ns = int(scale["n_samples"]); nf = int(scale["n_features"]); depth = int(scale["depth"])
    return f"""
import numpy as np
rng = np.random.default_rng({seed})
n_samples, n_features, depth = {ns}, {nf}, {depth}
# PREDICTOR_RECORD_DTYPE (sklearn _hist_gradient_boosting/common.pyx)
NODE_DTYPE = np.dtype([
    ('value', np.float64), ('count', np.uint32), ('feature_idx', np.intp),
    ('num_threshold', np.float64), ('missing_go_to_left', np.uint8),
    ('left', np.uint32), ('right', np.uint32), ('gain', np.float64),
    ('depth', np.uint32), ('is_leaf', np.uint8), ('bin_threshold', np.uint8),
    ('is_categorical', np.uint8), ('bitset_idx', np.uint32)])
n_nodes = (1 << (depth + 1)) - 1
n_internal = (1 << depth) - 1
nodes = np.zeros(n_nodes, dtype=NODE_DTYPE)
for i in range(n_nodes):
    if i < n_internal:                       # internal: numeric split, children 2i+1 / 2i+2
        nodes['is_leaf'][i] = 0
        nodes['feature_idx'][i] = i % n_features
        nodes['num_threshold'][i] = 0.0
        nodes['left'][i] = 2*i + 1
        nodes['right'][i] = 2*i + 2
        nodes['missing_go_to_left'][i] = 1
    else:                                    # leaf
        nodes['is_leaf'][i] = 1
        nodes['value'][i] = rng.standard_normal()
numeric_data = np.ascontiguousarray(rng.standard_normal((n_samples, n_features)))
raw_left_cat_bitsets = np.zeros((1, 8), dtype=np.uint32)      # no categorical nodes -> unused
known_cat_bitsets = np.zeros((max(n_features, 1), 8), dtype=np.uint32)
f_idx_map = np.zeros(n_features, dtype=np.uint32)
out = np.empty(n_samples, dtype=np.float64)
args = (nodes, numeric_data, raw_left_cat_bitsets, known_cat_bitsets, f_idx_map, 1, out)
kwargs = {{}}
"""


UNITS = {
    "csr_mean_variance_axis0": {
        "fold": "utils", "module": "sparsefuncs_fast", "lang": "c",
        "archetype": "streaming",
        "unit_dir": "data/corpus/sklearn/sparsefuncs_fast",
        "pyx": "sklearn/utils/sparsefuncs_fast.pyx", "mod": "sparsefuncs_fast",
        "kernel": "csr_mean_variance_axis0",
        "setup": csr_mean_variance_setup,
        # trial scale for G2 criterion-3 (substantial enough that the thin def-wrapper
        # dtype-check is negligible vs the cdef loop; representative of the golden regime).
        "trial": {"n_samples": 200_000, "n_features": 200, "density": 0.05},
        # delta-probe scale (~35 M nnz -> ~200 ms; kernel-dominant, lighter than the 86.5 M golden).
        "delta_scale": {"n_samples": 3_500_000, "n_features": 200, "density": 0.05},
    },
    "_inplace_contiguous_isotonic_regression": {
        "fold": "isotonic", "module": "_isotonic", "lang": "c",
        "archetype": "branch-PAVA",
        "unit_dir": "data/corpus/sklearn/_isotonic",
        "pyx": "sklearn/_isotonic.pyx", "mod": "_isotonic",
        "kernel": "_inplace_contiguous_isotonic_regression",
        "setup": pava_setup, "out_arg_indices": [0],      # y is the in-place result
        "mutated_arg_indices": [0, 1],                    # kernel writes BOTH y and w -> reset both
        "recallable": False,                              # in-place on y -> degenerate re-call
        "trial": {"n": 2_000_000},
        "delta_scale": {"n": 4_000_000},                  # per-rep regen (in-place); modest n bounds regen cost
    },
    "dbscan_inner": {
        "fold": "cluster", "module": "_dbscan_inner", "lang": "c++",
        "archetype": "cpp-DFS",
        "unit_dir": "data/corpus/sklearn/_dbscan_inner",
        "pyx": "sklearn/cluster/_dbscan_inner.pyx", "mod": "_dbscan_inner",
        "kernel": "dbscan_inner",
        "setup": dbscan_setup, "out_arg_indices": [2],    # labels filled in-place
        "mutated_arg_indices": [2],                       # labels written -> reset each rep
        "recallable": False,                              # labels!=-1 -> degenerate re-call
        "trial": {"n": 200_000, "avg_deg": 10},
    },
    "lloyd_iter_chunked_dense": {
        "fold": "cluster", "module": "_k_means_lloyd", "lang": "c",
        "archetype": "wrapper-BLAS", "openmp": True,
        "preimport": "sklearn.cluster",                   # Decision C: break the circular import
        "unit_dir": "data/corpus/sklearn/_k_means_lloyd",
        "pyx": "sklearn/cluster/_k_means_lloyd.pyx", "mod": "_k_means_lloyd",
        "kernel": "lloyd_iter_chunked_dense",
        # BLAS-DROP spot-check (A1): the hot distance step is `_gemm` (cimported from _cython_blas ->
        # libopenblas), so the crit-3 callgrind delta shows large BLAS Ir. Package-import multi-module
        # like elkan: _cython_blas + _k_means_common co-built under the matrix.
        "closure": "data/corpus/sklearn/_k_means_lloyd/closure",
        "pkg_module": "sklearn.cluster._k_means_lloyd",
        "cobuild": [("sklearn/cluster/_k_means_common.pyx", "_k_means_common"),
                    ("sklearn/utils/_cython_blas.pyx", "_cython_blas"),
                    ("sklearn/cluster/_k_means_lloyd.pyx", "_k_means_lloyd")],
        "setup": lloyd_setup, "out_arg_indices": [3, 4, 5, 6],   # centers_new,wts,labels,shift
        "mutated_arg_indices": [3, 4, 5, 6],              # OUT buffers (re-zeroed internally)
        "recallable": True,                               # centers_old read-only; OUTs re-zeroed
        "trial": {"n_samples": 200_000, "n_features": 50, "n_clusters": 50},
    },

    # ---- crit-3 SURVIVORS driven for the Step-1.3 Δ-probe (one per surviving module) ----
    "_dirichlet_expectation_2d": {
        "fold": "decomposition", "module": "_online_lda_fast", "lang": "c",
        "archetype": "transcendental-compute",
        "unit_dir": "data/corpus/sklearn/_online_lda_fast",
        "pyx": "sklearn/decomposition/_online_lda_fast.pyx", "mod": "_online_lda_fast",
        "kernel": "_dirichlet_expectation_2d",
        "setup": dirichlet2d_setup, "recallable": True,
        "trial": {"n_rows": 20_000, "n_cols": 100},
        "delta_scale": {"n_rows": 120_000, "n_cols": 100},      # 12 M psi evals (~150-300 ms)
    },
    "_map_to_bins": {
        "fold": "ensemble", "module": "_binning", "lang": "c",
        "archetype": "search-branch",
        "unit_dir": "data/corpus/sklearn/_binning",
        "pyx": "sklearn/ensemble/_hist_gradient_boosting/_binning.pyx", "mod": "_binning",
        "kernel": "_map_to_bins",
        "setup": map_to_bins_setup, "out_arg_indices": [5],     # binned written deterministically
        "mutated_arg_indices": [5], "recallable": True,         # data const -> overwrite identical
        "trial": {"n_samples": 500_000, "n_features": 30, "n_bins": 255},
        "delta_scale": {"n_samples": 300_000, "n_features": 30, "n_bins": 255},  # 9 M searches (~0.7s slow pole)
    },
    "ppoly_evaluate": {
        "fold": "interpolate", "module": "_ppoly", "lang": "c",
        "archetype": "horner-fp",
        "unit_dir": "data/corpus/scipy/_ppoly",
        "pyx": "_ppoly.pyx", "mod": "_ppoly",
        "kernel": "evaluate",
        "setup": ppoly_evaluate_setup, "out_arg_indices": [5],  # out written deterministically
        "mutated_arg_indices": [5], "recallable": True,         # inputs const -> overwrite identical
        "trial": {"k": 4, "m": 2_000, "p": 2_000_000},
        "delta_scale": {"k": 4, "m": 2_000, "p": 6_000_000},    # 6 M Horner+bisect
    },
    "floyd_warshall": {
        "fold": "csgraph", "module": "_shortest_path", "lang": "c",
        "archetype": "dense-allpairs",
        "unit_dir": "data/corpus/scipy/_shortest_path",
        "pyx": "scipy/sparse/csgraph/_shortest_path.pyx", "mod": "_shortest_path",
        "kernel": "floyd_warshall",
        "preimport": "scipy.sparse.csgraph",                    # Decision-C: break circular import
        "setup": floyd_setup, "recallable": True,
        "trial": {"N": 300},
        "delta_scale": {"N": 700},                              # O(N^3) ~3.4e8 (~0.3-0.6s)
    },
    "connected_components": {
        "fold": "csgraph", "module": "_traversal", "lang": "c",
        "archetype": "pointer-bfs",
        "unit_dir": "data/corpus/scipy/_traversal",
        "pyx": "scipy/sparse/csgraph/_traversal.pyx", "mod": "_traversal",
        "kernel": "connected_components",
        "preimport": "scipy.sparse.csgraph",                    # Decision-C: break circular import
        "setup": connected_components_setup, "recallable": True,
        "trial": {"N": 100_000, "avg_deg": 5},
        "delta_scale": {"N": 2_000_000, "avg_deg": 5},          # 10 M edges BFS
    },

    # ---- PACKAGE-IMPORT multi-module co-build survivors (Δ-probe via delta_probe_pkg.py) ----
    # These kernels' .so does a RELATIVE import of a sibling vendored .so (from ._k_means_common
    # import CHUNK_SIZE / from ._bitset cimport ...), so they CANNOT be bare-loaded by
    # gate_runner (spec_from_file_location sets __package__='' -> relative import fails). They are
    # built+timed as a PACKAGE import from the mounted closure (cobuild list = dep order).
    "elkan_iter_chunked_dense": {
        "fold": "cluster", "module": "_k_means_elkan", "lang": "c",
        "archetype": "distance-vectorizable", "openmp": True,
        "closure": "data/corpus/sklearn/_k_means_elkan/closure",
        "pkg_module": "sklearn.cluster._k_means_elkan",
        "cobuild": [("sklearn/cluster/_k_means_common.pyx", "_k_means_common"),
                    ("sklearn/cluster/_k_means_elkan.pyx", "_k_means_elkan")],
        "mod": "_k_means_elkan", "kernel": "elkan_iter_chunked_dense",
        "setup": elkan_setup,
        "mutated_arg_indices": [3, 4, 7, 8, 9, 10],          # centers_new,wts,upper,lower,labels,shift
        "recallable": False,                                 # bounds/labels mutated -> per-rep regen
        "trial": {"n_samples": 50_000, "n_features": 50, "n_clusters": 50},
        "delta_scale": {"n_samples": 200_000, "n_features": 50, "n_clusters": 50},
        # screen best ~20 ms (perfect-bound pruning) is sub-band; endpoint bumps n (~50 ms) to
        # VERIFY the high Δ reproduces on the clean rig (contamination check; magnitude caveat stays)
        "endpoint_scale": {"n_samples": 500_000, "n_features": 50, "n_clusters": 50},
    },
    "_predict_from_raw_data": {
        "fold": "ensemble", "module": "_predictor", "lang": "c",
        "archetype": "tree-dfs", "openmp": True,
        "closure": "data/corpus/sklearn/_predictor/closure",
        "pkg_module": "sklearn.ensemble._hist_gradient_boosting._predictor",
        "cobuild": [("sklearn/ensemble/_hist_gradient_boosting/common.pyx", "common"),
                    ("sklearn/ensemble/_hist_gradient_boosting/_bitset.pyx", "_bitset"),
                    ("sklearn/ensemble/_hist_gradient_boosting/_predictor.pyx", "_predictor")],
        "mod": "_predictor", "kernel": "_predict_from_raw_data",
        "setup": predictor_setup, "out_arg_indices": [6],
        "mutated_arg_indices": [6], "recallable": True,      # out overwritten from const inputs
        "trial": {"n_samples": 2_000_000, "n_features": 20, "depth": 12},
        "delta_scale": {"n_samples": 5_000_000, "n_features": 20, "depth": 15},
    },
}
