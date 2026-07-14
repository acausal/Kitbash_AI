# json_query_filter

Lightweight `jq`-like path queries over JSON — extraction, filtering, flattening,
and schema validation. Foundational data plumbing (pairs with `line_filtering`
and `text_search`). Isolation-first (stdlib `json` only + optional `structured_logger`).

## Library

```python
from tools.json_query_filter import (
    query_json, filter_json_array, extract_fields, flatten_json, validate_schema,
)

q   = query_json({"user": {"name": "Alice"}}, ".user.name")        # -> "Alice", found=True
arr = filter_json_array([...], "?status == \"active\"")             # keep matching
ex  = extract_fields(obj_or_list, ["id", "name"])                  # subset
fl  = flatten_json({"user": {"name": "A"}}, separator=".")        # single-level keys
v   = validate_schema(obj, {"required": ["id"], "types": {"id": "number"}})
```

Every function returns a **plain JSON-serializable dict**.

### Query syntax (paths)
- `.field`, `.a.b.c` — nested navigation
- `.arr[0]`, `.arr[1:3]` (slice), `.arr[*]` (all items)
- `.arr[*].field` / `.*.field` — extract a field from each array element
- `.field // "default"` — default if missing/null
- `.{a, b}` — field selection (subset object)
- `.field | type` / `.field | length` — pipe to type name or length

Missing fields, null navigation, and type mismatches return **null + found=False**
(graceful) — only *malformed syntax* raises `ValueError`.

### Filters
`?field op value` where `op` ∈ `== != > <` (no `>=`/`<=` in v1). Values: quoted
strings, numbers, `true`/`false`/`null`. Comparison: numeric when both numeric,
lexicographic for strings.

### validate_schema
Checks `required` presence and `types` per field; `extra fields allowed`. Returns
`valid`, `schema_checks`, and a list of `errors`.

## CLI

Reads JSON from **stdin**, writes JSON to **stdout**:

```bash
echo '{"user":{"name":"Alice","age":30}}' | python -m tools.json_query_filter query_json --query .user.name
echo '{"items":[{"id":1,"name":"A"},{"id":2,"name":"B"}]}' | python -m tools.json_query_filter query_json --query ".items[*].name"
echo '[{"id":1,"status":"active"},{"id":2,"status":"inactive"}]' | python -m tools.json_query_filter filter_json_array --filter '?status == "active"'
echo '{"id":1,"name":"Alice","email":"a@x.com","age":30}' | python -m tools.json_query_filter extract_fields --fields name email
echo '{"user":{"name":"A","contact":{"email":"a@x.com"}}}' | python -m tools.json_query_filter flatten_json --separator .
echo '{"id":1,"name":"Alice"}' | python -m tools.json_query_filter validate_schema --schema '{"required":["id","name"],"types":{"id":"number","name":"string"}}'
```

**Exit codes:** `0` success · `1` invalid input (`ValueError`) ·
`2` internal error (`RuntimeError`).

## Requirements

- Pure stdlib (`json`). No new deps.
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.json_query_filter ...`
