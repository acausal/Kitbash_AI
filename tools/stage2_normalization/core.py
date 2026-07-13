"""stage2_normalization core: whitespace normalization + exact-dup line removal.

Isolation-first tool (see tools/README.md). Allowed imports: stdlib + Kitbash
core's structured_logger (read-only helper). No orchestrator/engine/redis imports.

Stage 2 of the Document Preprocessing Pipeline: takes Stage 1 (dispatcher /
extractor) text and emits whitespace-normalized, exact-duplicate-deduped text.
"""
from __future__ import annotations

import os

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("stage2_normalization")
except Exception:  # structured_logger optional; never let logging break the tool
    _logger = None


def _normalize_whitespace(text: str) -> str:
    """Normalize line endings, collapse blank runs (max 2), trim ends."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    out: list[str] = []
    blank = 0
    for ln in lines:
        if ln.strip() == "":
            blank += 1
            if blank <= 2:  # keep at most 2 consecutive blank lines
                out.append(ln)
        else:
            blank = 0
            out.append(ln)
    return "\n".join(out).strip()


def _normalize_with_count(text: str) -> tuple[str, int]:
    """Whitespace-normalize, then drop exact-duplicate non-empty lines.

    Blank lines are governed by the blank-collapse step, NOT dedup, so paragraph
    spacing survives. Returns (cleaned_text, duplicate_count).
    """
    normalized = _normalize_whitespace(text)
    lines = normalized.split("\n")
    seen: set[str] = set()
    out: list[str] = []
    dup = 0
    for ln in lines:
        if ln.strip() == "":
            out.append(ln)  # blanks pass through (already collapsed)
            continue
        if ln in seen:
            dup += 1
            continue
        seen.add(ln)
        out.append(ln)
    return "\n".join(out), dup


def normalize_text(text: str) -> str:
    """Normalize whitespace and remove exact-match duplicate lines.

    Args:
        text: Raw extracted text from Stage 1.

    Returns:
        Cleaned text (normalized whitespace, deduped lines). Empty string
        input returns empty string.

    Raises:
        ValueError: text is None or not a string.
    """
    if text is None or not isinstance(text, str):
        raise ValueError(
            "normalize_text requires a str (got "
            f"{'None' if text is None else type(text).__name__})"
        )
    cleaned, _ = _normalize_with_count(text)
    return cleaned
