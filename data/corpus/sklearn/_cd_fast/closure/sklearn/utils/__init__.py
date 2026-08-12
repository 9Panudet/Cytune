# Minimal vendored package-context for the _cd_fast closure.
# _random.pyx (a runtime-import dependency of _cd_fast) does a module-scope
# `from . import check_random_state`. Upstream exposes check_random_state on the
# sklearn.utils package (re-exported from sklearn.utils.validation). The closure rule
# (closure-walk 5/6) forbids vendoring the heavyweight upstream __init__; instead we
# provide a FAITHFUL minimal impl, copied verbatim (semantics-identical) from
# sklearn/utils/validation.py:check_random_state of scikit-learn 1.5.2.
import numbers

import numpy as np

__all__ = ["check_random_state"]


def check_random_state(seed):
    """Turn seed into a np.random.RandomState instance.

    - None / np.random -> the process-wide np.random.mtrand._rand singleton
    - numbers.Integral  -> np.random.RandomState(seed)
    - RandomState       -> returned as-is
    - otherwise         -> ValueError
    """
    if seed is None or seed is np.random:
        return np.random.mtrand._rand
    if isinstance(seed, numbers.Integral):
        return np.random.RandomState(seed)
    if isinstance(seed, np.random.RandomState):
        return seed
    raise ValueError(
        "%r cannot be used to seed a numpy.random.RandomState instance" % seed
    )
