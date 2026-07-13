# txt_extractor

Plain text (`.txt`) → normalized, flat Markdown-style text. Stdlib only.

## What it does
- Reads `.txt` (UTF-8, fall back to Latin-1).
- Normalizes line endings, strips per-line trailing space, collapses 3+ blank
  lines to 2.
- Writes the result.

## Non-goals
No structure inference, OCR, batch, or bus integration.

## CLI
```
python -m tools.txt_extractor input.txt
python -m tools.txt_extractor input.txt -o out.md
```
Exit 0 / prints `Converted <in> → <out> (<N> chars)`; exit 1 on failure.

## Library
```python
from tools.txt_extractor import convert_txt_to_markdown
convert_txt_to_markdown("input.txt", "out.md")
```
Raises: `FileNotFoundError`, `ValueError` (not `.txt`), `RuntimeError`
(decode fails), `IOError` (write fail). Empty input is allowed.
