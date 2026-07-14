"""tools.math_evaluation package.

Library:
    from tools.math_evaluation import safe_evaluate
    safe_evaluate("2 + 2 * 3")  # -> {"status":"success","result":8,...}

CLI:
    python -m tools.math_evaluation evaluate "2 + 2 * 3"
    python -m tools.math_evaluation evaluate "sqrt(16)" --precision 4

Safe AST evaluation (no eval/exec, no builtins except math). Supports + - *
/ // % ** (and ^ as exponentiation), sqrt/abs/sin/cos/tan/log/ln/log10/exp/
ceil/floor/min/max/... and constants pi/e/tau/inf/nan. Errors returned as dicts
(status:"error"), never raised. Pure stdlib.
"""
from .core import safe_evaluate

__all__ = ["safe_evaluate"]
