# docx_extractor

DOCX (`.docx`) → clean text. Uses `python-docx` (pure Python, no ML).
Paragraphs become lines; tables are emitted as `| col | col |` rows.

## Non-goals
No structure inference, formatting extraction (bold/italic/hyperlinks
are dropped to plain text), OCR, batch, or bus integration. Embedded
images/objects are skipped.

## CLI
```
python -m tools.docx_extractor input.docx
python -m tools.docx_extractor input.docx -o out.md
```
Exit 0 / prints `Converted <in> → <out> (<N> chars)`; exit 1 on failure.

## Library
```python
from tools.docx_extractor import convert_docx_to_markdown
convert_docx_to_markdown("input.docx", "out.md")
```
Raises: `FileNotFoundError`, `ValueError` (not `.docx`), `RuntimeError`
(DOCX/parse failure, e.g. corrupted ZIP), `IOError` (write fail).
Empty document allowed.
