"""Driver for the ctrl_oob POSITIVE control (planted heap-buffer-overflow)."""
import numpy as np

N = 4096
REPS = 4
OUTPUT_CLASS = "float"


def make_inputs(seed):
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(N).astype(np.float64), REPS)


def call(mod, inputs):
    return np.asarray(mod.run(*inputs), dtype=np.float64).reshape(-1)


def canon(result):
    return np.asarray(result, dtype=np.float64).reshape(-1)
