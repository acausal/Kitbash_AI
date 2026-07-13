# odt_extractor

ODT (`.odt`) → clean text. Uses `odfpy` (pure Python). Paragraphs
(`<text:p>`) are extracted via `odf.teletype.extractText`; output is one
line per paragraph.

## Non-goals
No structure inference, formatting extraction, OCR, batch, or bus
integration. Embedded images are skipped.

## CLI
```
python -m tools.odt_extractor input.odt
python -m tools.odt_extractor input.odt -o out.md
```
Exit 0 / prints `Converted <in> → <out> (<N> chars)`; exit 1 on failure.

## Library
```python
from tools.odt_extractor import convert_odt_to_markdown
convert_odt_to_markdown("input.odt", "out.md")
```
Raises: `FileNotFoundError`, `ValueError` (not `.odt`), `RuntimeError`
(ODT parse failure, e.g. corrupted ZIP), `IOError` (write fail).
Empty allowed.
