# markdown_extractor

Markdown (`.md`, `.markdown`) → normalized pass-through text. Stdlib only.
Markdown syntax is preserved as-is (not parsed); only line endings and
blank-line runs are normalized.

## Non-goals
No structure inference, batch, or bus integration.

## CLI
```
python -m tools.markdown_extractor input.md
python -m tools.markdown_extractor input.md -o out.md
```
Exit 0 / prints `Converted <in> → <out> (<N> chars)`; exit 1 on failure.

## Library
```python
from tools.markdown_extractor import convert_markdown_to_markdown
convert_markdown_to_markdown("input.md", "out.md")
```
Raises: `FileNotFoundError`, `ValueError` (not `.md`/`.markdown`),
`RuntimeError` (decode fails), `IOError` (write fail). Empty allowed.
