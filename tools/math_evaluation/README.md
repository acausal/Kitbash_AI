# math_evaluation

Safely evaluate arithmetic expressions so agents can calculate without the
inference model. `ast`-based evaluation (no `eval`/`exec`, no builtins except
`math`) — injection-safe by construction.

## Interface

```python
safe_evaluate("2 + 2 * 3")            # {"status":"success","result":8,...}
safe_evaluate("sqrt(16)")             # {"status":"success","result":4.0,...}
safe_evaluate("3.14 * 2^2")           # ^ is exponentiation
safe_evaluate("1 / 0")                # {"status":"error","reason":"Division by zero",...}
```

| Function | Purpose |
|----------|---------|
| `safe_evaluate(expression, precision=10)` | Evaluate; return result/error dict |

**Operators:** `+ - * / // % **` (and `^` as `**`). **Functions:** `sqrt abs
sin cos tan asin acos atan log ln log10 log2 exp ceil floor factorial gcd
degrees radians pow min max`. **Constants:** `pi e tau inf nan`.

Result type: `int` when integral, else `float`; `/` always float. Errors
(invalid syntax, undefined variable, math domain, division by zero, overflow)
return `{"status":"error","reason":...}` — never raised.

## CLI

```bash
python -m tools.math_evaluation evaluate "2 + 2 * 3"
python -m tools.math_evaluation evaluate "sqrt(16)" --precision 4
```

JSON to stdout, summary to stderr. Exit 0 = success, 1 = error. Pure stdlib;
same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.

**Spec:** `SPEC-math_evaluation_v1.md` · **Test:** `TEST-math_evaluation_examples.json`
