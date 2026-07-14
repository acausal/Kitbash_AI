"""csv_operations core: parse, filter, select, sort, unique, stats.

Stdlib only (csv, json, re). Isolation-first tool (see tools/README.md).
Consumes/returns JSON-serializable dicts. Allowed imports: stdlib + Kitbash
core's structured_logger (read-only helper; failed import is non-fatal).

Error taxonomy (matches the SPEC CLI exit codes):
  ValueError        -> invalid input / missing column / malformed CSV   (CLI 1)
  FileNotFoundError -> CSV file not found                                (CLI 2)
  OSError/RuntimeError -> file IO / bad regex / internal                 (CLI 3)
"""
from __future__ import annotations

import csv
import traceback
from collections import Counter, OrderedDict
from typing import Any, Dict, List

from . import csv_parser as P
from . import filters as F

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("csv_operations")
except Exception:
    _logger = None


def _log(event: str, **data) -> None:
    if _logger:
        try:
            _logger.log(event_type=event, data=data)
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# 1. parse_csv
# --------------------------------------------------------------------------- #
def parse_csv(data: str = None, file_path: str = None, has_header: bool = True,
              delimiter: str = None) -> dict:
    _log("parse_started", has_header=has_header, delimiter=delimiter)
    text = P._read_source(data, file_path)  # raises FileNotFoundError/IOError/ValueError
    try:
        struct = P.parse_to_structure(text, has_header=has_header, delimiter=delimiter)
    except csv.Error as e:
        _log("parse_failed", error=str(e))
        raise ValueError(f"malformed CSV: {e}")
    except ValueError:
        _log("parse_failed", error=traceback.format_exc(limit=2))
        raise
    result = {
        "operation": "parse_csv",
        "row_count": struct["row_count"],
        "column_count": struct["column_count"],
        "has_header": struct["has_header"],
        "delimiter": struct["delimiter"],
        "headers": struct["headers"],
        "rows": struct["rows"],
    }
    _log("parse_complete", row_count=struct["row_count"],
         column_count=struct["column_count"])
    return result


# --------------------------------------------------------------------------- #
# 2. filter_rows
# --------------------------------------------------------------------------- #
def filter_rows(rows: List[Dict[str, str]], column: str, operator: str,
                value: str) -> dict:
    P.validate_operator(operator)
    _log("filter_applied", column=column, operator=operator)
    try:
        out = F.filter_rows(rows, column, operator, value)
    except (ValueError, RuntimeError):
        raise
    return {
        "operation": "filter_rows",
        "column": column,
        "operator": operator,
        "value": value,
        "input_row_count": len(rows),
        "output_row_count": len(out),
        "rows": out,
    }


# --------------------------------------------------------------------------- #
# 3. select_columns
# --------------------------------------------------------------------------- #
def select_columns(rows: List[Dict[str, str]], columns: List[str] = None,
                   exclude: bool = False) -> dict:
    if columns is None:
        columns = []
    out = F.select_columns(rows, columns, exclude=exclude)
    return {
        "operation": "select_columns",
        "columns": list(columns),
        "exclude": exclude,
        "input_column_count": len(rows[0]) if rows else 0,
        "output_column_count": len(out[0]) if out else 0,
        "rows": out,
    }


# --------------------------------------------------------------------------- #
# 4. sort_rows
# --------------------------------------------------------------------------- #
def sort_rows(rows: List[Dict[str, str]], column: str, descending: bool = False,
              numeric: bool = False) -> dict:
    _log("sort_applied", column=column, numeric=numeric)
    try:
        out = F.sort_rows(rows, column, descending=descending, numeric=numeric)
    except ValueError:
        raise
    return {
        "operation": "sort_rows",
        "column": column,
        "descending": descending,
        "numeric": numeric,
        "rows": out,
    }


# --------------------------------------------------------------------------- #
# 5. unique_values
# --------------------------------------------------------------------------- #
def unique_values(rows: List[Dict[str, str]], column: str) -> dict:
    if not rows:
        return {"operation": "unique_values", "column": column,
                "total_rows": 0, "unique_count": 0, "values": [],
                "value_counts": {}}
    if column not in rows[0]:
        raise ValueError(f"column not found: {column!r}")
    counts = Counter(r.get(column, "") for r in rows)
    # sorted by count desc, then value asc (deterministic)
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return {
        "operation": "unique_values",
        "column": column,
        "total_rows": len(rows),
        "unique_count": len(ordered),
        "values": [k for k, _ in ordered],
        "value_counts": {k: v for k, v in ordered},
    }


# --------------------------------------------------------------------------- #
# 6. csv_stats
# --------------------------------------------------------------------------- #
def csv_stats(rows: List[Dict[str, str]]) -> dict:
    _log("stats_generated", row_count=len(rows))
    if not rows:
        return {"operation": "csv_stats", "row_count": 0,
                "column_count": 0, "columns": {}}
    cols: Dict[str, Any] = OrderedDict()
    headers = list(rows[0].keys())
    for col in headers:
        values = [r.get(col, "") for r in rows]
        non_empty = [v for v in values if v != ""]
        # type inference: first up to 5 non-empty values must all be numeric
        sample = non_empty[:5]
        is_numeric = bool(sample) and all(F._to_number(v) is not None for v in sample)
        unique = list(OrderedDict.fromkeys(values))
        col_stat: Dict[str, Any] = {
            "type": "numeric" if is_numeric else "text",
            "unique_count": len(unique),
            "sample_values": unique[:5],
        }
        if is_numeric and non_empty:
            nums = [F._to_number(v) for v in non_empty]
            col_stat["min"] = min(nums)
            col_stat["max"] = max(nums)
        cols[col] = col_stat
    return {
        "operation": "csv_stats",
        "row_count": len(rows),
        "column_count": len(headers),
        "columns": cols,
    }
