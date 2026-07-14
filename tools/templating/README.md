# templating

Safe variable substitution via `string.Template`. Used by Pattern Explainer
and others to generate human-readable output. `tools.templating`.

## Interface

```python
template_render("When query mentions $topic, tool $tool_name is called ${confidence}% of the time.",
                {"topic": "thermodynamics", "tool_name": "text_search", "confidence": 85})
# {"status":"success","result":"When query mentions thermodynamics, tool text_search is called 85% of the time.",...}

template_render("Hello $name", {})                       # error: missing variable
template_render("Price: $$100", {})                      # "Price: $100" (escape)
template_render("Hello $name", {}, mode="lenient")       # keeps "$name" intact
```

| Function | Purpose |
|----------|---------|
| `template_render(template, variables={}, mode="strict")` | Render; return result/error dict |
| `extract_variables(template)` | Unique `$var` names referenced |

**Modes:** strict (default) errors on missing variable; lenient leaves
placeholders in place. Values serialized via `str()`/JSON per SPEC. Errors
returned as dicts, never raised.

## CLI

```bash
python -m tools.templating render "Hello $name" '{"name":"Alice"}'
python -m tools.templating render-file template.txt vars.json --mode lenient
```

JSON to stdout, summary to stderr. Exit 0 = success, 1 = error. Pure stdlib;
same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.

**Spec:** `SPEC-templating_v1.md` · **Test:** `TEST-templating_examples.json`
