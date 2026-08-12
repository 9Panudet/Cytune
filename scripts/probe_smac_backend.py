"""Step 0.1.3 probe: pinned interpreter/package versions + which RF backend SMAC uses.

Roadmap §1.3 requires recording the active SMAC3 RF backend (pyrfr vs scikit-learn)
explicitly — the default changed across SMAC3 2.x releases. This probe inspects the
default model returned by the HPO facade, not documentation.
Output is captured verbatim into /data/env/SMAC_RF_BACKEND.md.
"""
import importlib
import importlib.metadata
import inspect
import platform

print("python", platform.python_version())
for mod, dist in (("Cython", "Cython"), ("numpy", "numpy"), ("scipy", "scipy"),
                  ("sklearn", "scikit-learn"), ("smac", "smac"),
                  ("ConfigSpace", "ConfigSpace"), ("pytest", "pytest")):
    importlib.import_module(mod)  # import must succeed, not just metadata lookup
    print(dist, importlib.metadata.version(dist))

try:
    import pyrfr  # noqa: F401
    print("pyrfr: PRESENT", pyrfr.__file__)
except ImportError:
    print("pyrfr: ABSENT from environment")

from ConfigSpace import ConfigurationSpace, Float
from smac import HyperparameterOptimizationFacade, Scenario

cs = ConfigurationSpace()
cs.add(Float("x", (0.0, 1.0)))
scenario = Scenario(cs, n_trials=1, output_directory="/tmp/smac_probe")
model = HyperparameterOptimizationFacade.get_model(scenario)

print("default model class:", type(model).__module__ + "." + type(model).__name__)
print("MRO:", " -> ".join(c.__module__ + "." + c.__name__ for c in type(model).__mro__))

src = inspect.getsource(inspect.getmodule(type(model)))
print("module source imports pyrfr:", "pyrfr" in src)
print("module source imports sklearn:", "sklearn" in src)

inner = [
    (name, type(val).__module__ + "." + type(val).__name__)
    for name, val in vars(model).items()
    if "forest" in type(val).__module__ + type(val).__name__.lower()
    or "sklearn" in type(val).__module__
    or "pyrfr" in type(val).__module__
]
print("wrapped estimator attributes (pre-fit):", inner if inner else "none (forest built lazily at _train)")

# Train/predict smoke: the forest is constructed lazily; prove the backend at fit time.
import numpy as np

X = np.linspace(0.0, 1.0, 8).reshape(-1, 1)
y = (X[:, 0] - 0.3) ** 2
model.train(X, y)
mu, var = model.predict(np.array([[0.5]]))
rf = model._rf
print("fitted forest class:", type(rf).__module__ + "." + type(rf).__name__)
print("fitted forest MRO:", " -> ".join(c.__module__ + "." + c.__name__ for c in type(rf).__mro__))
print("predict smoke: mu=%.6f var=%.6f" % (float(mu[0, 0]), float(var[0, 0])))
print("BACKEND VERDICT: sklearn" if "sklearn" in str(type(rf).__mro__) else "BACKEND VERDICT: NOT sklearn — investigate")
