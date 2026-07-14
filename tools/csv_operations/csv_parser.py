"""CSV parsing + dialect detection for tools.csv_operations.

Stdlib only (csv, io). parse_csv is exposed from core.py but delegates the
low-level work here. Handles: file or raw-text source, BOM strip, CRLF/LF,
Sniffer-based dialect detection (with explicit delimiter override and a comma
fallback), optional header row, headerless CSVs (synthesized col_N keys),
whitespace-trimmed values, and NULL-token normalization.

NULL tokens (empty / "NULL" / "null" / "N/A" / "n/a") are normalized to the
empty string so downstream ops treat them uniformly.
"""
from __future__ import annotations

import csv
import io
from typing import List, Tuple

_NULL_TOKENS = {"", "NULL", "null", "N/A", "n/a", "NA", "na"}

_OPERATORS = ("==", "!=", ">", "<", ">=", "<=", "regex")

# Sensible delimiter candidates for the Sniffer.
_SNIFF_DELIMS = ",;\t|"


def _read_source(data: str = None, file_path: str = None) -> str:
    """Return CSV text from `data` or `file_path`. Raises per taxonomy."""
    if data is not None and file_path is not None:
        raise ValueError("provide exactly one of `data` or `file_path`, not both")
    if data is None and file_path is None:
        raise ValueError("one of `data` or `file_path` is required")
    if file_path is not None:
        try:
            with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
                return f.read()
        except FileNotFoundError:
            raise
        except OSError as e:
            raise IOError(f"failed to read file {file_path!r}: {e}")
    # data given
    if data == "":
        raise ValueError("empty CSV data")
    return data


def _detect_dialect(text: str, delimiter: str = None):
    """Return a csv.Dialect. Explicit `delimiter` wins; else Sniffer; else comma."""
    if delimiter is not None:
        d = csv.excel()
        d.delimiter = delimiter
        return d
    sample = text[:1024]
    try:
        return csv.Sniffer().sniff(sample, delimiters=_SNIFF_DELIMS)
    except csv.Error:
        return csv.excel()


def _split_rows(text: str, dialect) -> List[List[str]]:
    # strict=True makes csv raise csv.Error on malformed input (e.g. an
    # unclosed quote at EOF), which parse_to_structure maps to ValueError.
    reader = csv.reader(io.StringIO(text), dialect, strict=True)
    return [row for row in reader]


def _normalize(cell: str) -> str:
    val = cell.strip()
    return "" if val in _NULL_TOKENS else val


def parse_to_structure(text: str, has_header: bool = True,
                       delimiter: str = None) -> dict:
    """Parse CSV text into headers + row dicts + delimiter metadata.

    Does NOT raise on empty input; callers validate before this. Returns a dict
    with keys: headers, rows, delimiter, column_count, row_count, has_header.
    """
    # Strip a leading BOM if present (utf-8-sig handles file reads; guard text too)
    if text.startswith("\ufeff"):
        text = text[1:]
    if text == "":
        raise ValueError("empty CSV data")

    dialect = _detect_dialect(text, delimiter)
    raw = _split_rows(text, dialect)
    if not raw:
        raise ValueError("malformed CSV: no rows")

    # Determine width from the first non-empty row to detect ragged input
    first = next((r for r in raw if r), None)
    if first is None:
        raise ValueError("malformed CSV: only blank lines")

    if has_header:
        headers = [_normalize(h) for h in raw[0]]
        body = raw[1:]
    else:
        ncols = len(first)
        headers = [f"col_{i + 1}" for i in range(ncols)]
        body = raw

    rows: List[dict] = []
    for r in body:
        if not r or all(c.strip() == "" for c in r):
            continue  # skip fully-blank rows
        # pad/truncate to header width for ragged rows
        cells = [_normalize(c) for c in r]
        if len(cells) < len(headers):
            cells = cells + [""] * (len(headers) - len(cells))
        elif len(cells) > len(headers):
            cells = cells[:len(headers)]
        rows.append(dict(zip(headers, cells)))

    return {
        "headers": headers,
        "rows": rows,
        "delimiter": dialect.delimiter,
        "column_count": len(headers),
        "row_count": len(rows),
        "has_header": has_header,
    }


def validate_operator(op: str) -> None:
    if op not in _OPERATORS:
        raise ValueError(f"invalid operator: {op!r} (expected one of {_OPERATORS})")
