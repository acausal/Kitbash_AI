"""pdf_to_mark_down core: lightweight PDF text extraction via pypdf.

Isolation-first tool (see tools/README.md). Allowed imports only:
pypdf, stdlib, and Kitbash core's structured_logger (read-only helper).
No orchestrator / sleep_* / redis_* / *_engine / mtr_* imports.
"""
from __future__ import annotations

import os
import re
import sys

from pypdf import PdfReader

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("pdf_to_mark_down")
except Exception:  # structured_logger optional; never let logging break extraction
    _logger = None


def _normalize(text: str) -> str:
    """Collapse runs of spaces; normalize line breaks; trim trailing space."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", ln).rstrip() for ln in text.split("\n")]
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)  # collapse 3+ blank lines
    return out.strip() + "\n" if out.strip() else ""


def convert_pdf_to_markdown(input_path: str, output_path: str) -> None:
    """Extract raw text from a PDF and write cleaned Markdown-ish text to disk.

    Raises:
        FileNotFoundError: input PDF does not exist
        ValueError: input path is not a .pdf file
        RuntimeError: pypdf fails to parse (cause chained) or yields empty text
        IOError: output cannot be written (permissions, disk full, etc.)
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"input PDF not found: {input_path}")
    if not input_path.lower().endswith(".pdf"):
        raise ValueError(f"input is not a .pdf file: {input_path}")

    if _logger:
        _logger.log(event_type="pdf_extraction_started", data={"source": input_path})

    try:
        reader = PdfReader(input_path)
        pages = []
        for i, page in enumerate(reader.pages, start=1):
            raw = page.extract_text() or ""
            body = _normalize(raw)
            if body:
                pages.append(f"--- PAGE {i} ---\n\n{body}")
        text = "\n\n".join(pages)
    except Exception as e:  # pypdf raises PdfReadError et al.
        msg = f"pypdf failed to parse {input_path}: {e}"
        if _logger:
            _logger.error(event_type="pdf_extraction_failed", data={"source": input_path, "error": str(e)})
        raise RuntimeError(msg) from e

    if not text.strip():
        msg = "pypdf produced empty output"
        if _logger:
            _logger.error(event_type="pdf_extraction_failed", data={"source": input_path, "error": msg})
        raise RuntimeError(msg)

    out_dir = os.path.dirname(os.path.abspath(output_path))
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as e:
        raise IOError(f"cannot create output directory {out_dir}: {e}") from e

    try:
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError as e:
        raise IOError(f"cannot write output {output_path}: {e}") from e

    if _logger:
        _logger.log(event_type="pdf_extraction_complete",
                    data={"source": input_path, "dest": output_path, "char_count": len(text)})

    print(f"Converted {input_path} → {output_path} ({len(text)} chars)", file=sys.stdout)
