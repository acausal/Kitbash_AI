# SPEC: JSON Query/Filter v1

**Module:** `tools/json_query_filter/`  
**Status:** Ready for build  
**Dependencies:** stdlib (json)  
**Priority:** High (foundational data plumbing; enables querying nested structures; pairs with external ingestion tools)

---

## Overview

Query and filter JSON data using lightweight path syntax. Extract fields from nested objects, filter arrays by conditions, select specific keys, flatten structures.

**Design principle:** Simple path-based queries (like jq but minimal syntax). No complex transformations; v1 focuses on extraction and filtering only.

**Use case:** "Parse an RSS feed JSON, extract all entry titles and publish dates, filter to entries from the last 7 days, return as JSON array."

---

## Scope

### In Scope ✓
- Path-based extraction: `.field`, `.field.nested`, `.array[0]`, `.array[*]`
- Array filtering: `.array[?condition]` (basic conditions: `== value`, `!= value`, `> value`, `< value`)
- Key selection: `.` returns all keys; `.{field1, field2}` returns subset
- Flattening: `.[]` iterates array; `.*.field` extracts field from all array elements
- Array slicing: `.array[start:end]`
- Default values: `.field // "default"` (if missing, use default)
- Output format: JSON or newline-delimited JSON (for arrays)
- Type checking: `.field | type` returns "string", "number", "array", "object", "null", "boolean"

### Out of Scope ✗
- Complex transformations (map, reduce, group_by)
- Computed fields or expressions (math, string manipulation)
- Recursive descent (`..`)
- Named functions or pipes beyond `| type`
- Sorting or ordering (handled by Line Filtering tool)
- Statistical aggregation (count, sum, avg)

---

## Module Structure

```
tools/json_query_filter/
  __init__.py                    # exports main functions
  core.py                        # implementation logic
  query_parser.py                # lightweight query DSL parser
  cli.py                         # argparse CLI
  query_schema.py                # dataclasses for JSON output
  README.md                       # usage docs
  __main__.py                    # CLI entry point
```

---

## Query Syntax

### Path Syntax

| Syntax | Meaning | Example |
|--------|---------|---------|
| `.` | Root object | `.` on `{"a": 1}` → `{"a": 1}` |
| `.field` | Get field | `.name` on `{"name": "Alice"}` → `"Alice"` |
| `.field.nested` | Nested field | `.user.name` on `{"user": {"name": "Bob"}}` → `"Bob"` |
| `.array[0]` | Array index | `.items[0]` on `{"items": [1,2,3]}` → `1` |
| `.array[*]` | All array elements | `.items[*]` on `{"items": [1,2,3]}` → `[1, 2, 3]` |
| `.array[]` | Iterate array (streaming) | `.items[]` → yields 1, 2, 3 (one per line in JSONL) |
| `.array[start:end]` | Array slice | `.items[1:3]` on `{"items": [0,1,2,3]}` → `[1, 2]` |
| `.*.field` | Extract field from all | `.items[*].name` on `{"items": [{"name": "A"}, {"name": "B"}]}` → `["A", "B"]` |
| `.field // default` | Default value | `.name // "Unknown"` if name missing → `"Unknown"` |
| `.{field1, field2}` | Select fields | `.{name, age}` on `{"name": "Alice", "age": 30, "email": "..."}` → `{"name": "Alice", "age": 30}` |

### Filter Syntax

| Syntax | Meaning |
|--------|---------|
| `.array[?type == "string"]` | Filter: keep if type field equals "string" |
| `.array[?count > 5]` | Filter: keep if count field > 5 |
| `.array[?active != false]` | Filter: keep if active != false |
| `.array[?created < "2026-07-01"]` | Filter: string comparison (lexicographic) |

### Pipe Syntax

| Syntax | Meaning |
|--------|---------|
| `.field \| type` | Get type of field result |
| `.array[*] \| type` | Get type of each array element |
| `.field \| length` | Get length of string/array/object |

---

## API

### Core Functions (in `core.py`)

#### 1. `query_json(json_obj: dict, query: str) -> dict`

**Purpose:** Query JSON object using path syntax.

**Input:**
- `json_obj` (dict): JSON object to query
- `query` (str): Query string (e.g., `.user.name`, `.items[*].id`)

**Output (JSON):**
```json
{
  "query": ".user.name",
  "result": "Alice",
  "result_type": "string",
  "found": true
}
```

Or for arrays:
```json
{
  "query": ".items[*]",
  "result": [
    {"id": 1, "name": "Item 1"},
    {"id": 2, "name": "Item 2"}
  ],
  "result_type": "array",
  "result_count": 2,
  "found": true
}
```

Or if not found:
```json
{
  "query": ".nonexistent.field",
  "result": null,
  "result_type": "null",
  "found": false
}
```

**Behavior:**
- Parse query string
- Navigate JSON object following path
- Return result + metadata (type, found flag)
- If path doesn't exist, return null with `found: false`

**Error handling:**
- `ValueError` if query syntax is invalid (malformed path, bad filter)
- `ValueError` if json_obj is not a dict

---

#### 2. `filter_json_array(json_array: list, filter_query: str) -> dict`

**Purpose:** Filter array by condition.

**Input:**
- `json_array` (list): Array of objects to filter
- `filter_query` (str): Filter condition (e.g., `?type == "string"`, `?count > 5`)

**Output (JSON):**
```json
{
  "filter": "?status == \"active\"",
  "total_items": 10,
  "filtered_items": 7,
  "results": [
    {"id": 1, "status": "active", "name": "Alice"},
    {"id": 2, "status": "active", "name": "Bob"}
  ]
}
```

**Behavior:**
- Apply filter to each element
- Keep elements matching condition
- Return filtered array + metadata

**Error handling:**
- `ValueError` if filter syntax invalid
- `ValueError` if json_array is not a list

---

#### 3. `extract_fields(json_obj: dict, fields: list) -> dict`

**Purpose:** Extract specific fields from object(s).

**Input:**
- `json_obj` (dict or list): Object or array to extract from
- `fields` (list of str): Field names to extract (e.g., `["name", "email"]`)

**Output (JSON):**
```json
{
  "fields_requested": ["name", "email"],
  "extraction": {
    "name": "Alice",
    "email": "alice@example.com"
  }
}
```

Or from array:
```json
{
  "fields_requested": ["id", "name"],
  "total_items": 3,
  "results": [
    {"id": 1, "name": "Item 1"},
    {"id": 2, "name": "Item 2"},
    {"id": 3, "name": "Item 3"}
  ]
}
```

**Behavior:**
- For dict: extract specified fields into new dict
- For list of dicts: extract specified fields from each, return list of dicts
- Missing fields are omitted from output (not filled with null)

---

#### 4. `flatten_json(json_obj: dict, max_depth: int = None, separator: str = ".") -> dict`

**Purpose:** Flatten nested JSON into single-level keys.

**Input:**
- `json_obj` (dict): Object to flatten
- `max_depth` (int, optional): Flatten only to this depth (default: unlimited)
- `separator` (str): Key separator in output (default: ".")

**Output (JSON):**
```json
{
  "original": {
    "user": {
      "name": "Alice",
      "contact": {
        "email": "alice@example.com"
      }
    }
  },
  "flattened": {
    "user.name": "Alice",
    "user.contact.email": "alice@example.com"
  },
  "max_depth": null,
  "separator": "."
}
```

**Behavior:**
- Recursively traverse object
- Build flattened keys using separator
- Stop at max_depth if specified
- Ignore arrays (keep as values, don't flatten into)

---

#### 5. `validate_schema(json_obj: dict, schema: dict) -> dict`

**Purpose:** Validate JSON against a simple schema (check required fields, types).

**Input:**
- `json_obj` (dict): Object to validate
- `schema` (dict): Schema specification
  ```python
  {
    "required": ["id", "name"],
    "types": {
      "id": "number",
      "name": "string",
      "email": "string",
      "active": "boolean"
    }
  }
  ```

**Output (JSON):**
```json
{
  "valid": true,
  "schema_checks": {
    "required_fields": {
      "id": "present",
      "name": "present"
    },
    "type_checks": {
      "id": {"expected": "number", "actual": "number", "match": true},
      "name": {"expected": "string", "actual": "string", "match": true},
      "email": {"expected": "string", "actual": "string", "match": true},
      "active": {"expected": "boolean", "actual": "boolean", "match": true}
    }
  },
  "errors": []
}
```

Or if invalid:
```json
{
  "valid": false,
  "schema_checks": { /* ... */ },
  "errors": [
    {"field": "name", "error": "missing required field"},
    {"field": "active", "error": "type mismatch: expected boolean, got string"}
  ]
}
```

**Behavior:**
- Check all required fields present
- Check types match schema
- Return validation result + detailed error list

---

### CLI Interface (in `cli.py`)

```bash
# Query JSON
echo '{"user": {"name": "Alice", "age": 30}}' \
  | python -m tools.json_query_filter query_json --query ".user.name"

# Query array
echo '{"items": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]}' \
  | python -m tools.json_query_filter query_json --query ".items[*].name"

# Filter array
echo '[
  {"id": 1, "status": "active"},
  {"id": 2, "status": "inactive"},
  {"id": 3, "status": "active"}
]' | python -m tools.json_query_filter filter_json_array --filter "?status == \"active\""

# Extract fields
echo '{"id": 1, "name": "Alice", "email": "alice@example.com", "age": 30}' \
  | python -m tools.json_query_filter extract_fields --fields name email

# Flatten
echo '{"user": {"name": "Alice", "contact": {"email": "alice@example.com"}}}' \
  | python -m tools.json_query_filter flatten_json --separator "."

# Validate
echo '{"id": 1, "name": "Alice", "email": "alice@example.com"}' \
  | python -m tools.json_query_filter validate_schema --schema '{
      "required": ["id", "name"],
      "types": {"id": "number", "name": "string", "email": "string"}
    }'
```

**Exit codes:**
- `0` → success
- `1` → invalid input (ValueError)
- `2` → internal error (RuntimeError)

---

### Schema (in `query_schema.py`)

```python
from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Union

@dataclass
class QueryResult:
    query: str
    result: Any
    result_type: str  # "string", "number", "object", "array", "null", "boolean"
    found: bool
    result_count: Optional[int] = None  # for arrays

@dataclass
class FilterResult:
    filter: str
    total_items: int
    filtered_items: int
    results: List[Any]

@dataclass
class ExtractionResult:
    fields_requested: List[str]
    total_items: Optional[int] = None
    results: Union[Dict[str, Any], List[Dict[str, Any]]] = None
    extraction: Optional[Dict[str, Any]] = None

@dataclass
class FlattenResult:
    original: Dict[str, Any]
    flattened: Dict[str, Any]
    max_depth: Optional[int] = None
    separator: str = "."

@dataclass
class TypeCheck:
    expected: str
    actual: str
    match: bool

@dataclass
class SchemaError:
    field: str
    error: str

@dataclass
class ValidationResult:
    valid: bool
    schema_checks: Dict[str, Any]
    errors: List[SchemaError]
```

---

## Query Parsing Rules

### Precedence & Associativity

1. **Path segments** (left-to-right): `.user.name.first` → navigate user → name → first
2. **Array indexing** (highest): `.array[0]` evaluates before `.array[*]`
3. **Filters** (middle): `.array[?condition]` applies after path navigation
4. **Pipes** (lowest): `.field | type` applies last

### Edge Cases

- **Missing fields**: `.nonexistent` → `null` (not error)
- **Array out of bounds**: `.items[99]` on 5-item array → `null`
- **Type mismatch**: `.string_field[0]` (indexing string) → `null` (not error)
- **Null navigation**: `.null_field.nested` → `null` (not error)
- **Empty arrays**: `.items[*]` on empty array → `[]`

---

## Error Handling

**Unified error taxonomy:**
- `FileNotFoundError` — not applicable
- `ValueError` — invalid query syntax, invalid filter condition, invalid schema, non-dict input to query_json
- `RuntimeError` — internal query execution error (should be rare)
- `IOError` — not applicable

**Logging:**
- Use `structured_logger.get_event_logger("json_query_filter")`
- Events: `query_started`, `query_complete`, `query_failed`, `validation_complete`
- Metadata: query string, result type, items processed, execution_time_ms

---

## Test Cases

### Happy Path (query_json)
1. Simple field: `.name` → correct value
2. Nested field: `.user.address.city` → correct value
3. Array index: `.items[0]` → first item
4. Array all: `.items[*]` → all items
5. Array slice: `.items[1:3]` → items 1-2
6. Extract from array: `.items[*].id` → all ids
7. Missing field: `.nonexistent` → null with found=false
8. Type detection: `.field | type` → "string", "number", etc.
9. Default value: `.missing // "default"` → "default"
10. Field selection: `.{name, email}` → only those fields

### Happy Path (filter_json_array)
11. Equality filter: `?status == "active"` → matches
12. Inequality filter: `?count != 0` → matches
13. Greater than: `?age > 18` → matches
14. Less than: `?price < 100` → matches
15. No matches: filter returns empty array

### Happy Path (extract_fields)
16. Extract from object → subset with requested fields
17. Extract from array → list of objects with requested fields
18. Missing fields → omitted from output
19. All fields requested → all extracted

### Happy Path (flatten_json)
20. Flatten nested object → single-level keys
21. Flatten with custom separator → uses specified separator
22. Flatten to max_depth → stops at depth

### Happy Path (validate_schema)
23. Valid object → passes all checks
24. Missing required field → validation fails
25. Type mismatch → validation fails
26. Extra fields (not in schema) → allowed, validation passes

### Edge Cases
27. Empty object: `.` on `{}` → `{}`
28. Empty array: `.items[*]` on `{"items": []}` → `[]`
29. Array out of bounds: `.items[99]` → `null`
30. Nested null: `.null_field.nested` → `null` (not error)
31. Type mismatch in access: `.string[0]` → `null` (not error)
32. Very deep nesting (10+ levels) → handled
33. Large arrays (1000+ elements) → handled
34. Unicode in keys/values → preserved
35. Null values in object → preserved
36. Boolean/number types → preserved and detected correctly

### Error Cases
37. Malformed query (unclosed bracket): `.items[` → `ValueError`
38. Invalid filter syntax: `?invalid condition` → `ValueError`
39. Invalid JSON object input → `ValueError`
40. Invalid array input to filter → `ValueError`
41. Invalid schema format → `ValueError`

### CLI Behavior
42. CLI exit code 0 on success
43. CLI exit code 1 on ValueError
44. CLI exit code 2 on RuntimeError
45. CLI reads JSON from stdin
46. CLI with multiple operations (--query, --filter) → first applies

---

## Non-Goals (Explicitly Out of Scope)

- Complex transformations (map, reduce, group_by)
- Computed fields or math expressions
- Recursive descent (`..`)
- Named functions or custom logic
- Sorting (handled by Line Filtering)
- Statistical aggregation
- Streaming/real-time processing
- SQL-like joins or complex filters

---

## Implementation Notes

### Query Parser Strategy

Build a simple recursive descent parser:
1. Parse top-level path (`.field`, `.field.nested`, `.array[index]`)
2. Parse array indexing/slicing (`[0]`, `[*]`, `[1:3]`, `[?filter]`)
3. Parse filter conditions (`?field == value`)
4. Parse pipes (`| type`, `| length`)
5. Execute step by step; short-circuit on null

### Filter Condition Parsing

Simple expression parser:
- Operands: field name (left side), literal value (right side)
- Operators: `==`, `!=`, `>`, `<` (no `>=`, `<=` in v1; defer to v2)
- String literals: quoted values; lexicographic comparison

### Type Detection

Use Python's built-in type names:
- `str` → `"string"`
- `int`, `float` → `"number"`
- `list` → `"array"`
- `dict` → `"object"`
- `bool` → `"boolean"`
- `None` → `"null"`

---

## Success Criteria

- ✅ All 46 test cases pass (manually verified with terminal output)
- ✅ CLI exit codes correct (0, 1, 2)
- ✅ Query paths navigate correctly (nested, array, slicing)
- ✅ Array filters work (equality, comparison)
- ✅ Field extraction correct (subset selection)
- ✅ Flattening preserves all data
- ✅ Schema validation detects missing/type-mismatched fields
- ✅ Edge cases handled gracefully (missing fields, null, out-of-bounds)
- ✅ Error messages clear and actionable
- ✅ Errors logged via structured_logger with context
- ✅ README documents query syntax, examples, and limitations

---

**Last updated:** 2026-07-14  
**Prepared by:** Claude  
**Status:** Ready for Hermes build
