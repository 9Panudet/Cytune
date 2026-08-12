"""K lloyd_iter_chunked_dense calls for callgrind dilution analysis (Step 1.2.4, Decision C).
lloyd is re-callable, so K calls amortize the one-time setup. Classify per-symbol Ir by SOURCE
.so: the lloyd VARIANT .so = directive-tunable (outer kernel); installed _kmeans_common.so +
BLAS = the FIXED helper a Theta-variant does NOT change -> dilution = helper / (outer+helper)."""
import importlib.util, sys
sys.path.insert(0, "/probe/corpus")
import sklearn.cluster            # Decision C pre-import
import corpus_drivers as cd
so, K = sys.argv[1], int(sys.argv[2])
u = cd.UNITS["lloyd_iter_chunked_dense"]
ns = {}; exec(u["setup"]({"n_samples": 50000, "n_features": 50, "n_clusters": 50}), ns)
args = tuple(ns["args"])
spec = importlib.util.spec_from_file_location("_k_means_lloyd", so)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
for _ in range(K):
    m.lloyd_iter_chunked_dense(*args)
print("lloyd_cg done K=%d" % K)
