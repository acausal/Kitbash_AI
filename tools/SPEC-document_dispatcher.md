# SPEC: Document Dispatcher

## Purpose
Single entry point for document ingestion: accept any file, detect format, route to the appropriate extractor (`txt_extractor`, `markdown_extractor`, etc.), emit clean text. The dispatcher is a thin routing layer; all extraction logic lives in format-specific modules.

## Scope

### In Scope
- Accept a single input file path (any extension)
- Detect format by file extension (primary) + optional content sniffing (secondary)
- Route to the correct extractor based on detected format
- Pass through CLI arguments (`--output`, `-o`) to the extractor
- Delegate all text extraction to format-specific modules
- Fail loud if format is unrecognized
- Optionally chain Stage 2 normalization (`tools.stage2_normalization`) via an opt-in flag (see below)

### Non-Goals
- Extracting text itself (that's the extractors' job)
- Advanced content analysis or MIME type detection
- Batch processing (single file at a time)
- Fallback extractors (one format → one extractor)

## Format Detection Strategy

### Primary: File Extension
Map extensions to extractors:
| Extension | Extractor | Format |
|-----------|-----------|--------|
| `.pdf` | `pdf_to_markdown` | PDF |
| `.txt` | `txt_extractor` | Plain text |
| `.md`, `.markdown` | `markdown_extractor` | Markdown |
| `.html`, `.htm` | `html_extractor` | HTML |
| `.json` | `json_extractor` | JSON |
| `.docx`, `.doc` | `docx_extractor` | DOCX |
| `.rtf` | `rtf_extractor` | RTF |
| `.odt` | `odt_extractor` | ODT |
| `.epub` | `epub_extractor` | EPUB |

**Extension matching:** Case-insensitive (`input.PDF` → `pdf_to_markdown`).

### Secondary: Content Sniffing (Optional, For Robustness)
If needed later: read first N bytes and check for magic bytes:
- PDF: `%PDF`
- DOCX: `PK\x03\x04` (ZIP signature)
- EPUB: `PK\x03\x04` (ZIP) + `mimetype` file (EPUB-specific)
- RTF: `{\rtf`
- etc.

For now, **rely on extension only**. Content sniffing is a v2 enhancement.

## API Contract

### CLI
```bash
python -m tools.document_dispatcher input.pdf
python -m tools.document_dispatcher input.pdf --output output.md
python -m tools.document_dispatcher input.anything -o output.txt
python -m tools.document_dispatcher input.md --normalize      # also run Stage 2
```

**Behavior:**
- Detect format from `input` extension
- If extension unknown: raise `ValueError` and exit 1
- Route to appropriate extractor (e.g., `txt_extractor.convert_txt_to_markdown()`)
- Pass through `--output` / `-o` to the extractor
- If `--output` not specified, extractor writes to `<input_basename>.md` (default behavior)
- `--normalize` (optional, **default OFF**): after extraction, run Stage 2
  (`tools.stage2_normalization.normalize_text`) on the extracted text and
  overwrite the output with the normalized version. When omitted, raw extractor
  output is preserved unchanged.
- Exit code 0 on success
- Exit code 1 on failure (with stderr message)
- Print summary to stdout: `Detected <format>. Converted <input> → <output> (<N> chars)`

### Library API
```python
from tools.document_dispatcher import extract_document

extract_document("input.docx", "output.md")
extract_document("input.html")  # writes to input.md
```

**Signature:**
```python
def extract_document(input_path: str, output_path: str | None = None,
                     normalize: bool = False) -> str
    """
    Detect format and extract text via appropriate extractor.

    Args:
        input_path: Path to input document
        output_path: Path to write output (if None, defaults to input_basename.md)
        normalize: If True, run Stage 2 normalization (whitespace + exact-dup
            dedup) on the extracted text before writing. Default False.

    Returns:
        Path to the output file that was written

    Raises:
        FileNotFoundError: Input file does not exist
        ValueError: Extension not recognized or extension/format mismatch
        RuntimeError: Extractor fails (via delegated exception)
        IOError: Output cannot be written
    """
```

## Error Handling

| Case | Behavior |
|------|----------|
| Input file not found | Raise `FileNotFoundError` (from underlying extractor) |
| Extension unknown (e.g., `.xyz`) | Raise `ValueError("Unknown format: xyz. Currently Supported: pdf, txt, md, html, json, docx, rtf, odt, epub")` |
| Format/extension mismatch detected (e.g., `.txt` file is actually DOCX) | Log warning, attempt extraction anyway; let extractor fail if it fails |
| Extractor raises exception | Re-raise with context (e.g., `RuntimeError("docx_extractor failed: <original message>")`) |
| Output write fails | Raise `IOError` (from extractor) |

## Implementation Notes

### Module Structure
```
tools/document_dispatcher/
  __init__.py          # exports extract_document()
  cli.py               # argparse CLI
  format_registry.py   # REQUIRED: centralized format → (module, func) mapping; overrides the default naming convention (e.g. pdf → tools.pdf_to_markdown)
  README.md            # usage docs
```

### Format Registry
To keep the dispatcher's routing code uniform across formats with **different**
naming conventions, all `format → (module, callable)` resolution lives in
`format_registry.py`. Most formats follow the default convention
(`tools.<format>_extractor` / `convert_<format>_to_markdown`); PDF is the
documented exception — its real package is `tools.pdf_to_markdown` — so it is
overridden explicitly rather than forcing a rename.

```python
# tools/document_dispatcher/format_registry.py
"""Centralized format -> (module, func) mapping."""

# format -> (importable module path, callable name)
# Override formats whose package/module name diverges from the default
# tools.<format>_extractor / convert_<format>_to_markdown convention.
EXTRACTOR_OVERRIDES: dict[str, tuple[str, str]] = {
    "pdf": ("tools.pdf_to_markdown", "convert_pdf_to_markdown"),
}


def resolve_extractor(format_name: str) -> tuple[str, str]:
    """Return (module_path, func_name) for a format name.

    Falls back to the default naming convention unless an override exists.
    """
    if format_name in EXTRACTOR_OVERRIDES:
        return EXTRACTOR_OVERRIDES[format_name]
    return (
        f"tools.{format_name}_extractor",
        f"convert_{format_name}_to_markdown",
    )
```

### Format Detection Logic
```python
def detect_format(input_path: str) -> str:
    """
    Return format name (e.g., 'docx', 'html') from file extension.
    Case-insensitive.
    Raises ValueError if unknown.
    """
    ext = Path(input_path).suffix.lower().lstrip('.')
    format_map = {
        'pdf': 'pdf',
        'txt': 'txt',
        'md': 'markdown',
        'markdown': 'markdown',
        'html': 'html',
        'htm': 'html',
        'json': 'json',
        'docx': 'docx',
        'doc': 'docx',  # simplified; .doc is legacy, route to docx_extractor
        'rtf': 'rtf',
        'odt': 'odt',
        'epub': 'epub',
    }
    if ext not in format_map:
        logger.error(event_type="format_detection_failed", data={"extension": ext, "supported": list(sorted(set(format_map.values())))})
        raise ValueError(f"Unknown format: {ext}. Currently Supported: {', '.join(sorted(set(format_map.values())))}")
    return format_map[ext]
```

### Routing Logic
```python
from tools.document_dispatcher.format_registry import resolve_extractor
from tools.stage2_normalization import normalize_text

def extract_document(input_path: str, output_path: str | None = None,
                     normalize: bool = False) -> str:
    """
    1. Detect format from extension
    2. Resolve the extractor module/function via format_registry
       (handles formats like pdf whose package name diverges from the
       default tools.<format>_extractor convention)
    3. Call the extractor (input_path, output_path)
    4. Optionally run Stage 2 (normalize_text) on the written file and rewrite it
    5. Return the output path
    """
    if not Path(input_path).exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    format_name = detect_format(input_path)
    output_path = output_path or f"{Path(input_path).stem}.md"

    module_path, func_name = resolve_extractor(format_name)
    try:
        extractor_module = __import__(module_path, fromlist=[func_name])
        convert_func = getattr(extractor_module, func_name)
    except (ImportError, AttributeError) as e:
        raise RuntimeError(f"Extractor module not found for format '{format_name}': {e}")

    # Delegate to extractor. Some extractors return the extracted text;
    # others (e.g. pdf_to_markdown) return None and write directly to disk.
    convert_func(input_path, output_path)

    if normalize:
        cleaned = normalize_text(Path(output_path).read_text(encoding="utf-8"))
        Path(output_path).write_text(cleaned, encoding="utf-8")

    # Return output path for convenience
    return output_path
```

### Logging
```python
from structured_logger import get_event_logger
from pathlib import Path
logger = get_event_logger("document_dispatcher")

logger.log(event_type="dispatch_started", data={"source": input_path, "format": format_name})

# Extractors vary: some return the extracted text, others (e.g. pdf_to_markdown)
# return None and write directly to output_path. To report a reliable char_count
# for every format, read the written output file back rather than relying on a
# return value (which may be None).
try:
    char_count = len(Path(output_path).read_text(encoding="utf-8"))
except (OSError, UnicodeDecodeError):
    char_count = 0

logger.log(event_type="dispatch_complete", data={"source": input_path, "dest": output_path, "format": format_name, "char_count": char_count})
logger.error(event_type="dispatch_failed", data={"source": input_path, "error": str(e)})
```

## Testing & Validation

### Manual Test Cases
1. **Happy path—each format:** Feed valid file (`.pdf`, `.txt`, `.md`, `.html`, `.json`, `.docx`, `.rtf`, `.odt`, `.epub`) → verify correct output
2. **Missing file:** Feed nonexistent path → verify `FileNotFoundError`
3. **Unknown extension:** Feed `.xyz` file → verify `ValueError("Unknown format: xyz...")`
4. **Extension/format mismatch:** Feed `.txt` file that's actually JSON → log warning, attempt extraction (let extractor decide if it fails)
5. **Output directory doesn't exist:** Create parent dirs or fail gracefully with `IOError`
6. **Permission denied:** Attempt to write to read-only dir → verify `IOError`
7. **Mixed line endings:** Input with `\r\n` and `\n` → verify all normalized to `\n`
8. **Unknown extension (verify against 9 formats):** Feed `.xyz` → verify `ValueError("Unknown format: xyz...")`
9. **`--normalize` off (default):** Run on a doc with duplicate/blank-heavy text → raw extractor output written unchanged (no Stage 2 applied)
10. **`--normalize` on:** Run same doc with `--normalize` → output equals `normalize_text(raw_output)` (whitespace collapsed, exact dups removed)

### Acceptance Criteria
- CLI works for all 9 formats (PDF + 8 others)
- Library function imports and calls cleanly
- Format detection is case-insensitive (`input.PDF` → `pdf_to_markdown`)
- Error messages are clear (e.g., "Unknown format: xyz. Currently Supported: pdf, txt, md, html, json, docx, rtf, odt, epub")
- Dispatches correctly to each extractor
- `--normalize` flag OFF by default; when ON, output is Stage-2-normalized
- Pasted terminal output demonstrating all test cases

## Done When
- `tools/document_dispatcher/__init__.py` exports `extract_document()`
- `tools/document_dispatcher/cli.py` implements CLI via argparse
- `tools/document_dispatcher/README.md` documents usage
- All manual test cases pass with pasted output
- `tools/README.md` updated to list the dispatcher
- Dispatcher works as the *primary* entry point (users call dispatcher, not individual extractors directly)
