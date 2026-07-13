# json_extractor

JSON (`.json`) → text pulled from known fields. Stdlib `json`. Looks for
text in `content`, `text`, `body`, `message`, `data` (in order); joins
multiple hits with `\n---\n`. Arrays of objects are concatenated.

## Non-goals
No recursion into nested objects, no structure inference, batch, or bus.

## CLI
```
python -m tools.json_extractor input.json
python -m tools.json_extractor input.json -o out.md
```
Exit 0 / prints `Converted <in> → <out> (<N> chars)`; exit 1 on failure.

## Library
```python
from tools.json_extractor import convert_json_to_markdown
convert_json_to_markdown("input.json", "out.md")
```
Raises: `FileNotFoundError`, `ValueError` (not `.json`, or no extractable
field), `RuntimeError` (JSON parse/encoding error), `IOError` (write fail).
