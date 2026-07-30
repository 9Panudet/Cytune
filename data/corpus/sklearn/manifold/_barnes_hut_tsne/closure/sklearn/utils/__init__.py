# Minimal faithful package context for standalone import of the vendored tree cluster.
# _random.pyx does `from . import check_random_state`; provide the verbatim sklearn impl.
import numbers
import numpy as np
def check_random_state(seed):
    if seed is None or seed is np.random:
        return np.random.mtrand._rand
    if isinstance(seed, numbers.Integral):
        return np.random.RandomState(seed)
    if isinstance(seed, np.random.RandomState):
        return seed
    raise ValueError(f"{seed!r} cannot be used to seed a numpy.random.RandomState instance")
