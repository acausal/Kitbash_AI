# SPEC: Document Format Extractors (Master)

## Purpose
Provide lightweight, format-agnostic text extraction for common document types (TXT, Markdown, HTML, JSON, DOCX, RTF, ODT, EPUB), each emitting clean text to disk. These are the building blocks for document ingestion; they accept a single file and output normalized text, with zero structural inference. Each extractor follows a shared contract and error taxonomy.

## Shared Contract

### Scope (All Extractors)
- Accept a single input file (correct extension, readable)
- Extract and normalize text content to plain text or Markdown
- Write output to disk at a specified path
- CLI entry point: `python -m tools.<format>_extractor <input> [--output <output.md>]`
- Library API: `convert_<format>_to_markdown(input_path: str, output_path: str) -> None`
- Structured logging via `structured_logger.py`
- Clear, fail-loud error messages

### Non-Goals (All Extractors)
- Structural inference (headings, emphasis, tables)
- Batch processing
- Semantic chunking or post-processing
- OCR or scanned-document recovery
- Fallback extraction methods
- Integration with Dream Bucket or Redis bus

### Shared Error Taxonomy
All extractors raise:
- `FileNotFoundError` — input file does not exist
- `ValueError` — input file wrong extension or format
- `RuntimeError` — extraction library fails (corrupt data, parse error, unsupported encoding)
- `IOError` — output cannot be written (permissions, disk full, etc.)

### Shared CLI
```bash
python -m tools.<format>_extractor input.<ext>
python -m tools tools.<format>_extractor input.<ext> --output output.md
python -m tools.<format>_extractor input.<ext> -o output.md
```

**Behavior (all):**
- If `--output` not specified, write to `<input_basename>.md` in same directory
- Exit code 0 on success
- Exit code 1 on failure (with stderr message)
- Print summary to stdout: `Converted <input> → <output> (<N> chars)`

### Shared Library API
```python
from tools.<format>_extractor import convert_<format>_to_markdown
convert_<format>_to_markdown("input.<ext>", "output.md")
```

### Shared Logging (via structured_logger.py)
```python
from structured_logger import get_event_logger
logger = get_event_logger("<format>_extractor")
logger.log(event_type="extraction_started", data={"source": input_path})
logger.log(event_type="extraction_complete", data={"source": input_path, "dest": output_path, "char_count": len(text)})
logger.error(event_type="extraction_failed", data={"source": input_path, "error": str(e)})
```

---

## Format-Specific Implementations

### TXT Extractor
**Module:** `tools/txt_extractor/`  
**Library:** None (read directly via Python's builtin `open()`)  
**Input:** `.txt` files  
**Output:** Clean text (UTF-8, normalized line endings)

**Extraction Strategy:**
- Open file with `open(input_path, 'r', encoding='utf-8')`
- If encoding fails, retry with `encoding='latin-1'` (fallback)
- Read entire file, strip leading/trailing whitespace
- Normalize line endings: `\r\n` → `\n`, collapse multiple blank lines (max 2)
- Write to output path

**Edge Cases:**
- Binary `.txt` (will fail on UTF-8 decode; raise `RuntimeError` with encoding error)
- Empty file: write empty output (not an error)
- Very large files (>1GB): read and write in chunks to avoid memory exhaustion

**Error Handling:**
- Encoding error → `RuntimeError("Cannot decode file as UTF-8 or Latin-1: <details>")`
- Empty output allowed (not an error)

---

### Markdown Extractor
**Module:** `tools/markdown_extractor/`  
**Library:** None (read via `open()`)  
**Input:** `.md`, `.markdown` files  
**Output:** Same text (pass-through with normalization)

**Extraction Strategy:**
- Read file as UTF-8 (fallback to Latin-1)
- Strip leading/trailing whitespace
- Collapse multiple blank lines (max 2)
- Preserve Markdown syntax (don't parse it; treat as plain text)
- Write to output

**Edge Cases:**
- YAML frontmatter (e.g., `---\ntitle: ...\n---`): preserve as-is
- Embedded code blocks: preserve as-is
- Empty file: allowed

**Error Handling:**
- Encoding error → `RuntimeError("Cannot decode file as UTF-8 or Latin-1: <details>")`

---

### HTML Extractor
**Module:** `tools/html_extractor/`  
**Library:** `html.parser.HTMLParser` (stdlib; no external dep)  
**Input:** `.html`, `.htm` files  
**Output:** Clean text (tags stripped, entities decoded)

**Extraction Strategy:**
- Parse HTML via `HTMLParser`
- Extract text content, skip `<script>`, `<style>`, `<meta>` tags
- Decode HTML entities (`&nbsp;` → space, `&amp;` → `&`, etc.)
- Collapse multiple whitespace/blank lines
- Write to output

**Edge Cases:**
- Malformed HTML: `HTMLParser` is forgiving; extract what's possible
- JavaScript/CSS in content: skip `<script>`/`<style>` tags
- Deeply nested divs: flatten to text
- Empty HTML: allowed

**Error Handling:**
- Parse error (rare with HTMLParser): `RuntimeError("HTML parse failed: <details>")`

---

### JSON Extractor
**Module:** `tools/json_extractor/`  
**Library:** `json` (stdlib)  
**Input:** `.json` files  
**Output:** Extracted text from specified fields (default: `content`, `text`, `body`, `message`; try in order)

**Extraction Strategy:**
- Load JSON with `json.load()`
- Look for text in these fields (in order): `content`, `text`, `body`, `message`, `data`
- If any field exists and is a string, use it
- If multiple text fields exist, concatenate with `\n---\n` separator
- If JSON is an array of objects, concatenate all matching fields with separator
- Normalize whitespace and write to output

**Edge Cases:**
- JSON is a string (not object/array): use the string directly
- No recognized text field: raise `ValueError("No extractable text field found (expected one of: content, text, body, message, data)")`
- Nested JSON (object with `content: { nested: "..." }`): try to extract from top level only; don't recurse
- Non-UTF-8 encoding: raise `RuntimeError("JSON encoding error: <details>")`

**Error Handling:**
- Invalid JSON: `RuntimeError("JSON parse error: <details>")`
- No text field: `ValueError("No extractable text field found in JSON")`

---

### DOCX Extractor
**Module:** `tools/docx_extractor/`  
**Library:** `python-docx` (PyPI; lightweight, no ML)  
**Input:** `.docx` files  
**Output:** Clean text (paragraphs separated by newlines)

**Extraction Strategy:**
- Use `Document(input_path)` from `python-docx`
- Iterate over paragraphs: `doc.paragraphs`
- Extract `.text` from each paragraph
- Concatenate with newlines
- Handle tables: iterate `doc.tables`, extract cell text, format as `| col1 | col2 |` rows
- Normalize whitespace, write to output

**Edge Cases:**
- Complex formatting (bold, italic, hyperlinks): extract text only, skip markup
- Embedded images/objects: skip (text extraction only)
- Empty document: allowed
- Corrupted DOCX (malformed ZIP): `RuntimeError` from python-docx

**Error Handling:**
- python-docx parse error: `RuntimeError("DOCX parse failed: <details>")`
- Corrupted ZIP structure: same

---

### RTF Extractor
**Module:** `tools/rtf_extractor/`  
**Library:** `striprtf` (PyPI; lightweight, pure Python)  
**Input:** `.rtf` files  
**Output:** Clean text

**Extraction Strategy:**
- Use `striprtf.rtf_to_text()` from the `striprtf` library
- Read file as bytes, pass to `rtf_to_text()`
- Normalize whitespace, write to output

**Edge Cases:**
- Encoding issues: `striprtf` handles internally
- Embedded images/objects: stripped
- Malformed RTF: `striprtf` does best-effort extraction

**Error Handling:**
- striprtf parse error: `RuntimeError("RTF parse failed: <details>")`
- File read error: standard `IOError`

---

### ODT Extractor
**Module:** `tools/odt_extractor/`  
**Library:** `odfpy` (PyPI; lightweight, handles ODF formats)  
**Input:** `.odt` files  
**Output:** Clean text (paragraphs separated by newlines)

**Extraction Strategy:**
- Use `odf.opendocument.load()` and `odf.text` from `odfpy`
- Iterate over text content in the ODT (which is a ZIP of XML files)
- Extract all text elements (`odf.text.P` for paragraphs, etc.)
- Concatenate with newlines
- Normalize whitespace, write to output

**Edge Cases:**
- Complex formatting: extract text only
- Embedded images: skip
- Corrupted ODT (malformed ZIP): `RuntimeError`

**Error Handling:**
- odfpy parse error: `RuntimeError("ODT parse failed: <details>")`
- Corrupted ZIP: same

---

### EPUB Extractor
**Module:** `tools/epub_extractor/`  
**Library:** `ebooklib` (PyPI; lightweight EPUB parser)  
**Input:** `.epub` files  
**Output:** Clean text (chapter content concatenated with separators)

**Extraction Strategy:**
- Use `ebooklib.epub.read_epub()` to load the EPUB file
- Iterate over book items (chapters)
- For each chapter (HTML content), use `html.parser.HTMLParser` to extract text (same as HTML extractor)
- Concatenate chapters with `\n--- CHAPTER ---\n` separator
- Normalize whitespace, write to output

**Edge Cases:**
- EPUB3 vs EPUB2: `ebooklib` handles both
- Embedded images: skip
- Complex layouts (poetry, comics): extract text only
- Corrupted EPUB (malformed ZIP): `RuntimeError`

**Error Handling:**
- ebooklib parse error: `RuntimeError("EPUB parse failed: <details>")`
- Corrupted ZIP: same

---

## Testing & Validation

### Per-Extractor Manual Tests
Each format follows this test pattern:
1. **Happy path:** Valid file of format → verify text output is written
2. **Missing file:** Nonexistent path → verify `FileNotFoundError`
3. **Wrong extension:** Feed `.txt` to DOCX extractor → verify `ValueError`
4. **Corrupt/malformed file:** Feed invalid data → verify `RuntimeError` with clear message
5. **Permission denied:** Attempt to write to read-only dir → verify `IOError`

### Acceptance Criteria (All Extractors)
- CLI invocation works; produces correct output file
- Library function imports and calls without side effects
- All error cases raise appropriate exceptions
- Text output is non-empty and readable (no garbled chars)
- Pasted terminal output demonstrates all cases

---

## Dependencies Summary

| Extractor | Primary Library | Source | ML-Free? | RAM-Light? |
|-----------|-----------------|--------|----------|-----------|
| TXT | `open()` (builtin) | stdlib | ✓ | ✓ |
| Markdown | `open()` (builtin) | stdlib | ✓ | ✓ |
| HTML | `html.parser` | stdlib | ✓ | ✓ |
| JSON | `json` | stdlib | ✓ | ✓ |
| DOCX | `python-docx` | PyPI | ✓ | ✓ |
| RTF | `striprtf` | PyPI | ✓ | ✓ |
| ODT | `odfpy` | PyPI | ✓ | ✓ |
| EPUB | `ebooklib` | PyPI | ✓ | ✓ |

All are pure Python, no ML stacks, minimal RAM footprint.

---

## Done When

For each format extractor:
- `tools/<format>_extractor/__init__.py` exports `convert_<format>_to_markdown()`
- `tools/<format>_extractor/cli.py` implements CLI via argparse
- `tools/<format>_extractor/README.md` documents format-specific quirks
- All manual test cases pass with pasted output
- `tools/README.md` updated to list all extractors

All extractors committed together (or incrementally per format, your choice).
