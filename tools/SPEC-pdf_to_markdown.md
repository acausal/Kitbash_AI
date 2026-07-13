# SPEC: PDF-to-Markdown Preprocessing Stage

## Purpose
Convert PDF documents to clean, readable text/Markdown using lightweight extraction (pypdf), emitting output to disk. This is the first concrete tool in the document ingestion pipeline, proving pragmatic text extraction without heavy ML dependencies. Structure inference (headings, tables) deferred to later stages if needed.

## Scope

### In Scope
- Accept a single PDF file path as input
- Use pypdf to extract raw text from all pages
- Normalize whitespace/encoding (collapse multiple spaces, handle line breaks)
- Write cleaned text to disk at a specified output path
- CLI entry point: `python -m tools.pdf_to_markdown <input.pdf> [--output <output.md>]`
- Library API: `convert_pdf_to_markdown(input_path: str, output_path: str) -> None`
- Clear error messages for common failures (file not found, parse failure, write permission)
- Structured logging via `structured_logger.py` (lightweight event logging)

### Non-Goals
- Structural inference (headings, emphasis, tables) — use pypdf's text extraction only, accept flat output
- Batch processing (multiple PDFs in one call; defer to v2)
- Post-processing or semantic chunking (Stage 3+ concern)
- Integration with Dream Bucket or Redis bus (Stage 3+ concern)
- Fallback extraction methods (fail loud on pypdf failure)
- OCR for scanned PDFs (assume searchable PDFs initially)
- Image/chart extraction (text only for now)

## API Contract

### CLI
```bash
python -m tools.pdf_to_markdown input.pdf
python -m tools.pdf_to_markdown input.pdf --output output.md
python -m tools.pdf_to_markdown input.pdf -o output.md
```

**Behavior:**
- If `--output` not specified, write to `<input_basename>.md` in the same directory
- Exit code 0 on success
- Exit code 1 on failure (with stderr message)
- Print a single-line summary to stdout on success: `Converted <input> → <output> (<N> chars)`

### Library API
```python
from tools.pdf_to_markdown import convert_pdf_to_markdown

convert_pdf_to_markdown("input.pdf", "output.md")
```

**Raises:**
- `FileNotFoundError` if input PDF does not exist
- `ValueError` if input path is not a .pdf file
- `RuntimeError` if pypdf fails to parse (with original error as cause)
- `IOError` if output cannot be written (permissions, disk full, etc.)

## Dependencies
- `pypdf` (PyPI package; lightweight, pure Python)
- Python 3.8+
- `structured_logger.py` (Kitbash core, allowed by tools isolation contract)

## Implementation Notes

### pypdf Integration
- Use `PdfReader` from pypdf to load input PDF
- Iterate over pages, extract text via `.extract_text()`
- Concatenate pages with page break markers (e.g., `\n\n--- PAGE 2 ---\n\n`)
- Normalize whitespace: collapse multiple spaces, handle line breaks
- On success: write cleaned text to output path
- On failure: capture exception, re-raise as `RuntimeError` with clear message

### Logging
Use `structured_logger.py` via:
```python
from structured_logger import get_event_logger
logger = get_event_logger("pdf_to_markdown")
logger.log(event_type="pdf_extraction_started", data={"source": input_path})
logger.log(event_type="pdf_extraction_complete", data={"source": input_path, "dest": output_path, "char_count": len(text)})
# On error:
logger.error(event_type="pdf_extraction_failed", data={"source": input_path, "error": str(e)})
```

For CLI feedback, use standard `print()` or `sys.stderr.write()`.

### Validation
- Verify output file was written and is non-empty
- Raise `RuntimeError("pypdf produced empty output")` if text extraction yields nothing

## Error Cases

| Case | Behavior |
|------|----------|
| Input file not found | Raise `FileNotFoundError` with path |
| Input is not a PDF (wrong extension) | Raise `ValueError` |
| pypdf parse failure (corrupt/unreadable PDF) | Raise `RuntimeError` with pypdf's error message |
| Output directory does not exist | Create it (or raise `IOError` if we can't) |
| Output file write fails | Raise `IOError` with OS error |
| No text extracted (empty PDF) | Raise `RuntimeError("pypdf produced empty output")` |

## Testing & Validation

### Manual Test Cases
1. **Happy path:** Feed a small, valid PDF → verify text output is written and readable
2. **Missing file:** Feed nonexistent path → verify `FileNotFoundError`
3. **Wrong extension:** Feed `.txt` file → verify `ValueError`
4. **Corrupt PDF:** Feed invalid PDF data → verify `RuntimeError` with pypdf error
5. **Permission denied:** Attempt to write to read-only directory → verify `IOError`

### Acceptance Criteria
- CLI can be invoked directly; produces correct output file
- Library function can be imported and called without side effects
- All error cases raise appropriate exceptions with useful messages
- Text output is non-empty and readable (no garbled characters)
- Tool produces pasted terminal output demonstrating each case

## Done When
- `tools/pdf_to_markdown/__init__.py` exports `convert_pdf_to_markdown()`
- `tools/pdf_to_markdown/cli.py` implements CLI via argparse
- `tools/pdf_to_markdown/README.md` documents usage
- All manual test cases pass with pasted output
- `tools/README.md` updated to list this tool
