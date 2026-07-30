"""Driver for the running_max toy kernel (cytune v0 smoke).

Shows the contract a cytune driver must satisfy:
  make_inputs(seed) -> tuple passed to call()
  call(mod, inputs) -> the kernel's result
  canon(result)     -> a numpy array, canonicalised for hashing/comparison
  OUTPUT_CLASS      -> "float" | "int" | "bool"   (drives bit-exact vs toleranced oracle)

REPS is the calibration knob: cytune rewrites it in its VENDORED copy (never in your working tree)
so the reference config lands in the timing band.
"""
import numpy as np

N = 20000
REPS = 120
OUTPUT_CLASS = "float"


def make_inputs(seed):
    rng = np.random.default_rng(seed)
    a = rng.standard_normal(N).astype(np.float64)
    return (a, REPS)


def call(mod, inputs):
    return mod.run(*inputs)


def canon(result):
    return np.asarray(result, dtype=np.float64).reshape(-1)
