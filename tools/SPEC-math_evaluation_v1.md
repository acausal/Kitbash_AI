# SPEC: Math Evaluation Tool v1

**Version:** 1.0  
**Status:** Ready for implementation  
**Target:** Kitbash tool registry (standalone tool)  
**Depends:** stdlib only

---

## Purpose

Evaluate arithmetic expressions and return numeric results. Lets agents perform calculations without involving the inference model.

---

## Interface

### Tool Call

```
math_evaluate(
    expression: str,         # e.g., "2 + 2 * 3", "sqrt(16)", "3.14 * 2^2"
    precision: int = 10,     # decimal places (default 10)
)
```

### Return Value

```json
{
  "result": 14.0,
  "expression": "2 + 2 * 3",
  "precision": 10,
  "status": "success"
}
```

### Error Cases

```json
{
  "status": "error",
  "reason": "Invalid syntax: unexpected token 'x' at position 5",
  "expression": "2 + 2 * x"
}
```

```json
{
  "status": "error",
  "reason": "Division by zero",
  "expression": "1 / 0"
}
```

---

## Semantics

### Input: `expression`

A string containing an arithmetic expression. Supports:

**Operators:**
- `+` addition
- `-` subtraction
- `*` multiplication
- `/` division (float division)
- `//` floor division
- `%` modulo
- `**` or `^` exponentiation

**Functions (stdlib `math` module):**
- `sqrt(x)` — square root
- `abs(x)` — absolute value
- `sin(x)`, `cos(x)`, `tan(x)` — trigonometric (radians)
- `log(x)`, `log10(x)`, `ln(x)` — logarithms
- `exp(x)` — e^x
- `ceil(x)`, `floor(x)` — rounding
- `min(x, y, ...)`, `max(x, y, ...)` — min/max of multiple values

**Constants (stdlib `math`):**
- `pi` — π
- `e` — Euler's number
- `inf` — infinity

**Literals:**
- Integers: `42`, `-17`
- Floats: `3.14`, `-0.5`, `1e-3` (scientific notation)

### Input: `precision`

Optional. Number of decimal places to round result to. Default 10 (no practical rounding for most calculations).

```
math_evaluate("1 / 3", precision=2)  # result: 0.33
math_evaluate("1 / 3", precision=10) # result: 0.3333333333
```

### Output: `result`

Numeric result. Type depends on input:
- All integer operations that don't overflow → int
- Any float operand or float-producing function → float
- Division `/` always returns float

### Error Handling

**Invalid syntax:**
```
math_evaluate("2 + + 3")
→ {"status": "error", "reason": "Invalid syntax: ..."}
```

**Undefined variables:**
```
math_evaluate("x + 2")
→ {"status": "error", "reason": "Undefined variable: x"}
```

**Math domain errors:**
```
math_evaluate("sqrt(-1)")
→ {"status": "error", "reason": "Math domain error: sqrt of negative number"}

math_evaluate("log(0)")
→ {"status": "error", "reason": "Math domain error: log(0) is undefined"}
```

**Division by zero:**
```
math_evaluate("1 / 0")
→ {"status": "error", "reason": "Division by zero"}

math_evaluate("1 // 0")
→ {"status": "error", "reason": "Division by zero"}
```

**Overflow (extremely rare in Python, but possible):**
```
math_evaluate("10 ** 1000000")
→ {"status": "error", "reason": "Result too large to compute"}
```

All errors return `{"status": "error", "reason": "..."}` with exit code 1. No exceptions raised; tool returns error dict.

---

## Implementation Notes

### Safe Evaluation

Use `ast.literal_eval()` + manual AST traversal (or `numexpr` if available), NOT `eval()` or `exec()`. This prevents arbitrary code execution.

**Recommended approach:**
1. Parse expression string into AST using `ast.parse()`
2. Walk AST and validate: only allow BinOp, UnaryOp, Call, Constant, Name nodes
3. Reject any Name not in the safe constants list (pi, e, inf)
4. Evaluate using `math` module only (no `__import__`, no builtins except math)

**Example:**
```python
import ast
import math

def safe_evaluate(expression: str, precision: int = 10) -> dict:
    try:
        tree = ast.parse(expression, mode='eval')
        # Validate tree contains only safe operations
        _validate_ast(tree.body)
        # Evaluate with restricted namespace
        result = eval(compile(tree, '<string>', 'eval'), 
                     {"__builtins__": {}},  # No builtins
                     {**math.__dict__, "pi": math.pi, "e": math.e})
        return {"result": round(result, precision), "expression": expression, "status": "success"}
    except ZeroDivisionError:
        return {"status": "error", "reason": "Division by zero", "expression": expression}
    except ValueError as e:
        return {"status": "error", "reason": f"Math domain error: {e}", "expression": expression}
    except Exception as e:
        return {"status": "error", "reason": f"Invalid syntax: {str(e)}", "expression": expression}
```

### AST Validation

Only allow:
- `ast.BinOp` (binary operators: +, -, *, /, //, %, **)
- `ast.UnaryOp` (unary: -, +)
- `ast.Call` (function calls like sqrt, sin, etc.)
- `ast.Constant` (numbers, pi, e, inf)
- `ast.Name` (variable references, whitelist only math constants)

Reject:
- `ast.Subscript` (indexing)
- `ast.Attribute` (attribute access)
- `ast.Lambda` (lambdas)
- `ast.Import` (imports)
- Any function call not in safe list (sqrt, sin, log, etc.)

---

## Data Structure

### Input Schema

```json
{
  "expression": "2 + 2 * 3",
  "precision": 10
}
```

### Output Schema

**Success:**
```json
{
  "status": "success",
  "result": 14.0,
  "expression": "2 + 2 * 3",
  "precision": 10
}
```

**Error:**
```json
{
  "status": "error",
  "reason": "Division by zero",
  "expression": "1 / 0"
}
```

---

## Testing

### Unit Test Examples

```python
def test_basic_arithmetic():
    assert math_evaluate("2 + 3")["result"] == 5
    assert math_evaluate("2 * 3")["result"] == 6
    assert math_evaluate("2 ** 3")["result"] == 8

def test_order_of_operations():
    assert math_evaluate("2 + 2 * 3")["result"] == 8  # not 12
    assert math_evaluate("(2 + 2) * 3")["result"] == 12

def test_floats():
    assert abs(math_evaluate("1 / 3")["result"] - 0.333333) < 0.0001

def test_functions():
    result = math_evaluate("sqrt(16)")["result"]
    assert result == 4.0
    
    result = math_evaluate("sin(0)")["result"]
    assert result == 0.0

def test_constants():
    result = math_evaluate("pi * 2")["result"]
    assert abs(result - 6.28318) < 0.001

def test_precision():
    result = math_evaluate("1 / 3", precision=2)["result"]
    assert result == 0.33

def test_errors():
    error = math_evaluate("1 / 0")
    assert error["status"] == "error"
    assert "Division by zero" in error["reason"]
    
    error = math_evaluate("sqrt(-1)")
    assert error["status"] == "error"
    assert "domain error" in error["reason"]
    
    error = math_evaluate("x + 2")
    assert error["status"] == "error"
    assert "Undefined" in error["reason"] or "Name" in error["reason"]
```

---

## CLI

```bash
python -m tools.math_evaluation evaluate "2 + 2 * 3"
# Output:
# {
#   "status": "success",
#   "result": 8,
#   "expression": "2 + 2 * 3",
#   "precision": 10
# }

python -m tools.math_evaluation evaluate "1 / 0"
# Output:
# {
#   "status": "error",
#   "reason": "Division by zero",
#   "expression": "1 / 0"
# }
```

---

## Non-Goals

- **Symbolic math:** No algebra simplification, no symbolic derivatives, no symbolic integration. Use `sympy` separately if needed.
- **Complex numbers:** Only real numbers. `sqrt(-1)` is an error.
- **Arbitrary precision:** Uses Python floats (IEEE 754). Very large numbers may lose precision.
- **Custom functions:** Can't define new functions or store variables across calls. Each call is stateless.
- **Matrix operations:** No linear algebra. Single scalar expressions only.

---

## Related Components

- **Unit Conversion** — complements this tool for unit-aware calculations
- **Templating** — can embed math expressions in generated text
- **Diff/Patch** — can track calculation histories if needed
