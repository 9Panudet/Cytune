import importlib.util, sys
sys.path.insert(0, "/probe/corpus")
import corpus_drivers as cd
so = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 1000000
u = cd.UNITS["_inplace_contiguous_isotonic_regression"]
ns = {}; exec(u["setup"]({"n": n}), ns); args = tuple(ns["args"])
spec = importlib.util.spec_from_file_location("_isotonic", so)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m._inplace_contiguous_isotonic_regression(*args)   # single real call (fresh y)
print("pava_cg done n=%d" % n)
