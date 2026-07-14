"""Row filtering / selection / sorting for tools.csv_operations.

Stdlib only. Pure functions operating on lists of row dicts. Kept separate
from core.py per the module layout; core.py wraps these with the JSON-result
metadata + error taxonomy.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _to_number(v: str) -> Optional[float]:
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def match_row(row: Dict[str, str], column: str, operator: str,
              value: str) -> bool:
    """Return True if `row` satisfies column operator value.

    Raises ValueError on missing column / invalid operator; RuntimeError on a
    bad regex (so callers can map to exit 3).
    """
    if column not in row:
        raise ValueError(f"column not found: {column!r}")
    cell = row.get(column, "")

    if operator in (">", "<", ">=", "<="):
        a = _to_number(cell)
        b = _to_number(value)
        if a is not None and b is not None:
            if operator == ">":  return a > b
            if operator == "<":  return a < b
            if operator == ">=": return a >= b
            if operator == "<=": return a <= b
        # string fallback
        if operator == ">":  return cell > value
        if operator == "<":  return cell < value
        if operator == ">=": return cell >= value
        if operator == "<=": return cell <= value

    if operator == "==":
        return cell == value
    if operator == "!=":
        return cell != value
    if operator == "regex":
        try:
            return re.search(value, cell) is not None
        except re.error as e:
            raise RuntimeError(f"invalid regex {value!r}: {e}")

    raise ValueError(f"invalid operator: {operator!r}")


def filter_rows(rows: List[Dict[str, str]], column: str, operator: str,
                value: str) -> List[Dict[str, str]]:
    return [r for r in rows if match_row(r, column, operator, value)]


def select_columns(rows: List[Dict[str, str]], columns: List[str],
                   exclude: bool = False) -> List[Dict[str, str]]:
    if not rows:
        return []
    avail = list(rows[0].keys())
    missing = [c for c in columns if c not in avail]
    if missing:
        raise ValueError(f"column(s) not found: {missing}")
    if exclude:
        keep = [c for c in avail if c not in columns]
    else:
        keep = list(columns)
    return [{c: r[c] for c in keep} for r in rows]


def _sort_key(row: Dict[str, str], column: str, numeric: bool):
    v = row.get(column, "")
    if numeric:
        n = _to_number(v)
        # push non-numeric/empty to the end consistently (ascending)
        return (n is None, n if n is not None else 0.0)
    return v


def sort_rows(rows: List[Dict[str, str]], column: str, descending: bool = False,
              numeric: bool = False) -> List[Dict[str, str]]:
    if not rows:
        return []
    if column not in rows[0]:
        raise ValueError(f"column not found: {column!r}")
    if numeric:
        # Validate: every row must be numeric (or empty, which sorts last)
        for i, r in enumerate(rows):
            v = r.get(column, "")
            if v != "" and _to_number(v) is None:
                raise ValueError(
                    f"non-numeric value in column {column!r} at row {i}: {v!r}")
    return sorted(rows, key=lambda r: _sort_key(r, column, numeric),
                  reverse=descending)
