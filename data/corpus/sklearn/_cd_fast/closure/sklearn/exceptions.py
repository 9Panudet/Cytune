# Minimal vendored package-context shim for the _cd_fast closure.
# _cd_fast.pyx does a module-scope `from ..exceptions import ConvergenceWarning`.
# Upstream sklearn/exceptions.py is a heavyweight module exporting ~10 warning/error
# classes; the closure rule (§ closure-walk 6) forbids vendoring the heavyweight upstream
# __init__/module. ConvergenceWarning is a leaf `class ConvergenceWarning(UserWarning)`
# with no body logic, so this is a FAITHFUL minimal impl (verbatim class definition).
__all__ = ["ConvergenceWarning"]


class ConvergenceWarning(UserWarning):
    """Custom warning to capture convergence problems

    .. versionchanged:: 0.18
       Moved from sklearn.utils.
    """
