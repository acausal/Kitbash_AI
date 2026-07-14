"""tools.math_evaluation core (stdlib only; safe AST evaluation).

Evaluates arithmetic expressions without the inference model. Uses ast.parse
+ node whitelisting (no eval/exec, no builtins except math). See
SPEC-math_evaluation_v1.md.
"""
import ast
import math
from typing import Any, Dict

# Safe functions exposed to expressions (SPEC semantics).
_SAFE_FUNCS = {
    "sqrt": math.sqrt, "abs": abs, "fabs": math.fabs,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "log": math.log, "ln": math.log, "log10": math.log10, "log2": math.log2,
    "exp": math.exp, "ceil": math.ceil, "floor": math.floor,
    "factorial": math.factorial, "gcd": math.gcd,
    "degrees": math.degrees, "radians": math.radians,
    "pow": pow, "min": min, "max": max,
}
# Safe constants.
_SAFE_NAMES = {
    "pi": math.pi, "e": math.e, "tau": math.tau,
    "inf": math.inf, "nan": math.nan,
}

_ALLOWED_NODES = (
    ast.Expression, ast.Constant, ast.BinOp, ast.UnaryOp,
    ast.Call, ast.Name, ast.Load, ast.Add, ast.Sub, ast.Mult,
    ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd,
)


def _validate(node: ast.AST) -> None:
    parents: Dict[ast.AST, ast.AST] = {}
    for n in ast.walk(node):
        for child in ast.iter_child_nodes(n):
            parents[child] = n
    for n in ast.walk(node):
        if not isinstance(n, _ALLOWED_NODES):
            raise ValueError(f"disallowed syntax: {type(n).__name__}")
        if isinstance(n, ast.Name):
            parent = parents.get(n)
            if isinstance(parent, ast.Call) and parent.func is n:
                continue  # function name; validated by the Call branch
            if n.id not in _SAFE_NAMES:
                raise ValueError(f"undefined variable: {n.id}")
        if isinstance(n, ast.Call):
            if not isinstance(n.func, ast.Name) or n.func.id not in _SAFE_FUNCS:
                raise ValueError("unknown function call")


def safe_evaluate(expression: str, precision: int = 10) -> Dict[str, Any]:
    """Evaluate `expression` safely. Returns a result/error dict (never raises)."""
    if not isinstance(expression, str) or expression.strip() == "":
        return {"status": "error", "reason": "empty expression", "expression": expression}
    src = expression.replace("^", "**")
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError as e:
        return {"status": "error", "reason": f"invalid syntax: {e.msg}", "expression": expression}
    try:
        _validate(tree)
        result = eval(  # noqa: S307 -- safe: validated AST, no builtins
            compile(tree, "<math_evaluation>", "eval"),
            {"__builtins__": {}},
            {**_SAFE_FUNCS, **_SAFE_NAMES},
        )
    except ZeroDivisionError:
        return {"status": "error", "reason": "Division by zero", "expression": expression}
    except ValueError as e:
        return {"status": "error", "reason": f"Math domain error: {e}", "expression": expression}
    except OverflowError:
        return {"status": "error", "reason": "Result too large to compute", "expression": expression}
    except Exception as e:  # pragma: no cover - defensive
        return {"status": "error", "reason": f"invalid syntax: {e}", "expression": expression}
    try:
        rounded = round(float(result), precision)
    except (TypeError, ValueError):
        return {"status": "error", "reason": "non-numeric result", "expression": expression}
    # Preserve int when the value is integral and input was integer-like.
    if isinstance(result, int) or (isinstance(result, float) and result.is_integer()
                                   and not any(c in expression for c in ".eE")):
        rounded = int(rounded) if rounded.is_integer() else rounded
    return {
        "status": "success",
        "result": rounded,
        "expression": expression,
        "precision": precision,
    }
