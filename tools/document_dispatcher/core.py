"""document_dispatcher core: format detection + extractor routing (Stage 1).

Isolation-first tool (see tools/README.md). Allowed imports: stdlib,
other tools/, and Kitbash core's structured_logger (read-only helper).
No orchestrator/engine/redis imports.

Stage 2 (whitespace + exact-dup normalization) is wired in behind the
`normalize` flag (default OFF) so raw extractor output is preserved unless
explicitly requested.
"""
from __future__ import annotations

from pathlib import Path

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("document_dispatcher")
except Exception:  # structured_logger optional; never let logging break the tool
    _logger = None


_FORMAT_MAP: dict[str, str] = {
    "pdf": "pdf",
    "txt": "txt",
    "md": "markdown",
    "markdown": "markdown",
    "html": "html",
    "htm": "html",
    "json": "json",
    "docx": "docx",
    "doc": "docx",  # .doc is legacy; route to docx_extractor
    "rtf": "rtf",
    "odt": "odt",
    "epub": "epub",
}


def detect_format(input_path: str) -> str:
    """Return format name (e.g. 'docx', 'html') from file extension.

    Case-insensitive. Raises ValueError if the extension is unknown.
    """
    ext = Path(input_path).suffix.lower().lstrip(".")
    if ext not in _FORMAT_MAP:
        supported = sorted(set(_FORMAT_MAP.values()))
        if _logger:
            _logger.error(event_type="format_detection_failed",
                          data={"extension": ext, "supported": supported})
        raise ValueError(
            f"Unknown format: {ext}. Currently Supported: {', '.join(supported)}"
        )
    return _FORMAT_MAP[ext]


def _call_extractor(format_name: str, input_path: str, output_path: str) -> None:
    """Resolve and invoke the extractor for a format; raise on failure."""
    from tools.document_dispatcher.format_registry import resolve_extractor

    module_path, func_name = resolve_extractor(format_name)
    try:
        extractor_module = __import__(module_path, fromlist=[func_name])
        convert_func = getattr(extractor_module, func_name)
    except (ImportError, AttributeError) as e:
        raise RuntimeError(
            f"Extractor module not found for format '{format_name}': {e}"
        ) from e

    # Some extractors return text; others (e.g. pdf_to_markdown) return None and
    # write directly to output_path. We only depend on the side-effect file.
    convert_func(input_path, output_path)


def _read_output(output_path: str) -> str:
    try:
        return Path(output_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def extract_document(input_path: str, output_path: str | None = None,
                     normalize: bool = False) -> str:
    """Detect format and extract text via the appropriate extractor.

    Args:
        input_path: Path to input document.
        output_path: Path to write output (if None, defaults to
            <input_basename>.md next to the input).
        normalize: If True, run Stage 2 normalization (whitespace + exact-dup
            dedup) on the extracted text before writing. Default False — raw
            extractor output is preserved.

    Returns:
        Path to the output file that was written.

    Raises:
        FileNotFoundError: Input file does not exist.
        ValueError: Extension not recognized.
        RuntimeError: Extractor fails (delegated).
        IOError: Output cannot be written.
    """
    if not Path(input_path).exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    format_name = detect_format(input_path)
    output_path = output_path or f"{Path(input_path).stem}.md"

    if _logger:
        _logger.log(event_type="dispatch_started",
                    data={"source": input_path, "format": format_name,
                          "normalize": normalize})

    _call_extractor(format_name, input_path, output_path)

    if normalize:
        from tools.stage2_normalization import normalize_text
        text = normalize_text(_read_output(output_path))
        try:
            Path(output_path).write_text(text, encoding="utf-8")
        except OSError as e:
            raise IOError(f"cannot write normalized output {output_path}: {e}") from e

    char_count = len(_read_output(output_path))
    if _logger:
        _logger.log(event_type="dispatch_complete",
                    data={"source": input_path, "dest": output_path,
                          "format": format_name, "char_count": char_count,
                          "normalize": normalize})
    return output_path
