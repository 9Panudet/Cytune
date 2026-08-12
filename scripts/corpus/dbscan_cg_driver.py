"""Single fresh dbscan_inner call for callgrind crit-3 (Step 1.2.4, v1.4). The build of the
object-array neighborhoods is done BEFORE collection starts (--collect-atstart=no), and
--toggle-collect='*dbscan_inner*' captures ONLY the one kernel call (dbscan_inner is a plain
typed def, not fused -> no fused-dispatch toggle problem). crit-3 = (cython kernel-self +
C++ vector/stack Ir) / total collected; the neighborhoods[i] Python-object access shows up as
PyObject/__Pyx_GetItem* symbols = NON-kernel (the Theta directives can't tune Python C-API)."""
import importlib.util
import sys

sys.path.insert(0, "/probe/corpus")
import corpus_drivers as cd


def main():
    so = sys.argv[1]
    scale = {"n": int(sys.argv[2]), "avg_deg": int(sys.argv[3])} if len(sys.argv) > 3 \
        else dict(cd.UNITS["dbscan_inner"]["trial"])
    u = cd.UNITS["dbscan_inner"]
    ns = {}
    exec(u["setup"](scale), ns)             # build neighborhoods (collection OFF here)
    args = tuple(ns["args"])
    spec = importlib.util.spec_from_file_location("_dbscan_inner", so)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m.dbscan_inner(*args)                    # toggle-collect captures THIS call only
    print("dbscan_cg done n=%d" % scale["n"])


if __name__ == "__main__":
    main()
