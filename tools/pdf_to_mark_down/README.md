# pdf_to_mark_down

Extracts raw text from a single PDF and writes cleaned, flat Markdown-style text to disk. Part of the document ingestion pipeline (Stage 1). Lightweight: uses `pypdf` (pure Python, no ML).

## What it does
- Accepts one PDF path.
- Extracts text page-by-page via `pypdf`, tagging each with a `--- PAGE N ---` marker.
- Normalizes whitespace (collapses runs of spaces, normalizes line breaks).
- Writes the result to disk.

## Non-goals
Flat text only. No heading/table/structure inference, no OCR, no batch, no semantic chunking, no bus integration. Those are later stages.

## CLI
```
python -m tools.pdf_to_mark_down input.pdf
python -m tools.pdf_to_mark_down input.pdf --output out.md
python -m tools.pdf_to_mark_down input.pdf -o out.md
```
- Default output: `<input_basename>.md` next to the input.
- Exit 0 on success (prints `Converted <in> → <out> (<N> chars)`); exit 1 on failure (message to stderr).

## Library
```python
from tools.pdf_to_mark_down import convert_pdf_to_markdown
convert_pdf_to_markdown("input.pdf", "out.md")
```
Raises: `FileNotFoundError`, `ValueError` (not a .pdf), `RuntimeError` (pypdf parse fail / empty), `IOError` (write fail).

## Deps
`pypdf` (pip), `structured_logger.py` (optional, Kitbash core — allowed by the tools isolation contract).
