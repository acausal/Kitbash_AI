# SPEC: Templating Tool v1

**Version:** 1.0  
**Status:** Ready for implementation  
**Target:** Kitbash tool registry (standalone tool)  
**Depends:** stdlib `string.Template` (or lightweight jinja2 alternative)

---

## Purpose

Perform variable substitution and string interpolation in templates. Used by Pattern Explainer and other tools to generate human-readable output.

---

## Interface

### Tool Call

```
template_render(
    template: str,      # Template string with placeholders
    variables: dict,    # Dict of variable_name -> value
)
```

### Return Value

```json
{
  "status": "success",
  "result": "When query mentions thermodynamics, tool text_search is called 85% of the time.",
  "variables_used": ["topic", "tool_name", "confidence"],
  "variables_missing": [],
  "template_length": 45,
  "result_length": 78
}
```

### Error Cases

```json
{
  "status": "error",
  "reason": "Missing required variable: 'tool_name'",
  "missing_variables": ["tool_name"]
}
```

```json
{
  "status": "error",
  "reason": "Invalid template syntax: unclosed brace at position 42",
  "template": "..."
}
```

---

## Semantics

### Template Syntax (Simple: `$variable`)

Uses `string.Template` syntax (simple, safe, predictable):

```
$variable          → replaced with value
${variable}        → replaced with value (explicit braces)
$$                 → literal $
```

**Example:**
```
Template: "When query mentions $topic, tool $tool_name is called ${confidence}% of the time."
Variables: {"topic": "thermodynamics", "tool_name": "text_search", "confidence": 85}
Result: "When query mentions thermodynamics, tool text_search is called 85% of the time."
```

### Data Types

Variables can be any JSON-serializable type:
- Strings: `"hello"` → `hello`
- Numbers: `42` → `42`
- Booleans: `true` → `True` (Python repr)
- Lists: `["a", "b"]` → `["a", "b"]` (JSON string)
- Objects: `{"x": 1}` → `{"x": 1}` (JSON string)
- Null: `null` → `None` (or empty string, configurable)

**For non-string types, stringify using Python's `str()` or JSON:**
- `str(42)` → `"42"`
- `str(True)` → `"True"`
- `json.dumps([...])` → JSON array string

### Missing Variables

If a template references a variable not in `variables`:
- **Strict mode (default):** Error; list missing variables
- **Lenient mode:** Leave placeholder as-is (e.g., `$unknown_var` stays in output)

Tool uses **strict mode** by default (fail on missing).

### Escaping

To include a literal `$`, use `$$`:

```
Template: "Price: $$100"
Result: "Price: $100"
```

### Special Cases

**Empty string:** `template=""` → `result=""`

**No variables:** `template="static text"` → `result="static text"` (no substitutions)

**Whitespace:** Preserved as-is in template. Template and result preserve all whitespace.

---

## Implementation Notes

### Using stdlib `string.Template`

```python
from string import Template

def template_render(template: str, variables: dict) -> dict:
    try:
        tmpl = Template(template)
        result = tmpl.substitute(variables)  # Raises KeyError if missing variable
        
        return {
            "status": "success",
            "result": result,
            "variables_used": list(variables.keys()),
            "variables_missing": [],
            "template_length": len(template),
            "result_length": len(result)
        }
    except KeyError as e:
        missing = [str(e).strip("'")]  # Extract variable name from KeyError
        return {
            "status": "error",
            "reason": f"Missing required variable: '{missing[0]}'",
            "missing_variables": missing
        }
    except ValueError as e:
        return {
            "status": "error",
            "reason": f"Invalid template syntax: {str(e)}",
            "template": template
        }
```

### Lenient Mode (Optional)

To leave unmatched variables as-is instead of erroring:

```python
def template_render_lenient(template: str, variables: dict) -> dict:
    try:
        tmpl = Template(template)
        result = tmpl.safe_substitute(variables)  # Leaves unknown vars as $var
        return {
            "status": "success",
            "result": result,
            ...
        }
    except ValueError as e:
        return {
            "status": "error",
            "reason": f"Invalid template syntax: {str(e)}",
            ...
        }
```

Tool implements **strict mode only** (default `substitute`). Lenient mode can be added in v2 if needed.

### Detecting Variables

Extract variable names from template (for logging/debugging):

```python
import re

def _extract_variables(template: str):
    """Extract all $variable references from template."""
    # Match $variable or ${variable}, but not $$
    pattern = r'\$(?!\$)\{?(\w+)\}?'
    matches = re.findall(pattern, template)
    return list(set(matches))  # Unique variables
```

---

## Data Structure

### Input Schema

```json
{
  "template": "When query mentions $topic, tool $tool_name is called ${confidence}% of the time.",
  "variables": {
    "topic": "thermodynamics",
    "tool_name": "text_search",
    "confidence": 85
  }
}
```

### Output Schema (Success)

```json
{
  "status": "success",
  "result": "When query mentions thermodynamics, tool text_search is called 85% of the time.",
  "variables_used": ["topic", "tool_name", "confidence"],
  "variables_missing": [],
  "template_length": 97,
  "result_length": 102
}
```

### Output Schema (Error - Missing Variable)

```json
{
  "status": "error",
  "reason": "Missing required variable: 'tool_name'",
  "missing_variables": ["tool_name"]
}
```

### Output Schema (Error - Invalid Syntax)

```json
{
  "status": "error",
  "reason": "Invalid template syntax: unclosed ${...}",
  "template": "..."
}
```

---

## Testing

### Unit Test Examples

```python
def test_simple_substitution():
    result = template_render("Hello $name", {"name": "Alice"})
    assert result["status"] == "success"
    assert result["result"] == "Hello Alice"

def test_multiple_variables():
    result = template_render(
        "$greeting, $name! Welcome to $place.",
        {"greeting": "Hi", "name": "Bob", "place": "Kitbash"}
    )
    assert result["result"] == "Hi, Bob! Welcome to Kitbash."

def test_braces():
    result = template_render(
        "The ${item} costs $price",
        {"item": "book", "price": 19.99}
    )
    assert result["result"] == "The book costs 19.99"

def test_escaping():
    result = template_render("Price: $$100", {})
    assert result["result"] == "Price: $100"

def test_repeat_variable():
    result = template_render(
        "$x + $x = ${x}$x",  # Using $x multiple times
        {"x": 5}
    )
    assert result["result"] == "5 + 5 = 55"

def test_no_variables():
    result = template_render("Static text", {})
    assert result["status"] == "success"
    assert result["result"] == "Static text"

def test_empty_template():
    result = template_render("", {})
    assert result["result"] == ""

def test_missing_variable():
    result = template_render("Hello $name", {})
    assert result["status"] == "error"
    assert "missing_variables" in result
    assert "name" in result["missing_variables"]

def test_number_variable():
    result = template_render(
        "Confidence: ${confidence}%",
        {"confidence": 92}
    )
    assert result["result"] == "Confidence: 92%"

def test_invalid_syntax():
    # Unclosed ${...}
    result = template_render("Price: ${incomplete", {"incomplete": 10})
    assert result["status"] == "error"
    assert "Invalid" in result["reason"]

def test_json_variable():
    result = template_render(
        "Data: $data",
        {"data": '{"x": 1, "y": 2}'}  # Pass as string
    )
    assert result["result"] == 'Data: {"x": 1, "y": 2}'
```

---

## CLI

```bash
# Render template with inline JSON variables
python -m tools.templating render \
  "Hello $name, your score is $score" \
  '{"name": "Alice", "score": 95}'
# Output: JSON with result field

# Render from file
python -m tools.templating render-file template.txt variables.json
# Output: JSON with result field

# Example output
{
  "status": "success",
  "result": "Hello Alice, your score is 95"
}
```

---

## Non-Goals

- **Logic in templates:** No `if`, `for`, or conditional rendering. Use separate tool for branching.
- **Filters/transformations:** No uppercase, lowercase, or format filters. Use with other tools.
- **Template inheritance:** No template composition or includes. Single flat template only.
- **Nested variables:** No nested object access like `$person.name`. Flatten first.
- **Performance:** No caching or optimization for repeated renders. Each call is fresh.

---

## Related Components

- **Pattern Explainer** — primary consumer (generates human-readable pattern descriptions)
- **Log Parser** — can generate formatted logs using templates
- **Text Search** — can search template output
- **Diff/Patch** — can diff before/after template renders
