"""line_filtering core: set operations + ordering over newline-delimited text.

Isolation-first tool (see tools/README.md). Allowed imports: stdlib and Kitbash
core's structured_logger (read-only helper). No orchestrator/engine/redis imports.

All functions return JSON-serializable dicts. Lines are split on "\n"; trailing
newlines stripped. No whitespace trimming (preserve as-is, per SPEC case 29).
Empty text -> zero lines (graceful). None text -> ValueError.
"""
from __future__ import annotations

from collections import Counter
from typing import List, Tuple

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("line_filtering")
except Exception:  # optional; never let logging break the tool
    _logger = None


def _split(text: str) -> List[str]:
    if text is None:
        raise ValueError("text must not be None")
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if text == "":
        return []
    # splitlines drops a trailing empty (from trailing \n); keep behavior simple:
    return text.split("\n")


# --------------------------------------------------------------------------- #
# 1. sort_lines
# --------------------------------------------------------------------------- #
def sort_lines(text: str, descending: bool = False,
               case_insensitive: bool = False) -> dict:
    lines = _split(text)
    if case_insensitive:
        out = sorted(lines, key=lambda s: s.lower(), reverse=descending)
    else:
        out = sorted(lines, reverse=descending)
    return {
        "operation": "sort_lines",
        "params": {"descending": descending, "case_insensitive": case_insensitive,
                   "total_lines": len(lines)},
        "result": {"sorted_lines": out, "line_count": len(out)},
    }


# --------------------------------------------------------------------------- #
# 2. deduplicate_lines
# --------------------------------------------------------------------------- #
def deduplicate_lines(text: str, preserve_order: bool = True,
                      case_insensitive: bool = False) -> dict:
    lines = _split(text)
    seen = set()
    out = []
    for ln in lines:
        key = ln.lower() if case_insensitive else ln
        if key not in seen:
            seen.add(key)
            out.append(ln)
    if not preserve_order:
        out = sorted(out)
    return {
        "operation": "deduplicate_lines",
        "params": {"preserve_order": preserve_order, "case_insensitive": case_insensitive,
                   "total_lines_input": len(lines),
                   "duplicate_lines": len(lines) - len(out)},
        "result": {"deduplicated_lines": out, "unique_line_count": len(out),
                   "duplicates_removed": len(lines) - len(out)},
    }


# --------------------------------------------------------------------------- #
# 3. count_line_frequency
# --------------------------------------------------------------------------- #
def count_line_frequency(text: str, sort_by: str = "frequency") -> dict:
    lines = _split(text)
    if sort_by not in ("frequency", "lexicographic"):
        raise ValueError("sort_by must be 'frequency' or 'lexicographic'")
    counts = Counter(lines)
    total = sum(counts.values())
    freq_list = [{"line": ln, "count": c,
                  "frequency_percent": round(c / total * 100, 2) if total else 0.0}
                 for ln, c in counts.items()]
    if sort_by == "frequency":
        # descending count, tie-break lexicographic ascending
        freq_list.sort(key=lambda e: (-e["count"], e["line"]))
    else:
        freq_list.sort(key=lambda e: e["line"])
    if counts:
        by_count = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        most = by_count[0]
        least = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
        stats = {"most_common": most[0], "most_common_count": most[1],
                 "least_common": least[0], "least_common_count": least[1]}
    else:
        stats = {"most_common": "", "most_common_count": 0,
                 "least_common": "", "least_common_count": 0}
    return {
        "operation": "count_line_frequency",
        "params": {"sort_by": sort_by, "total_lines": total,
                   "unique_lines": len(counts)},
        "results": {"frequency_list": freq_list, "distribution_stats": stats},
    }


# --------------------------------------------------------------------------- #
# 4. filter_by_frequency
# --------------------------------------------------------------------------- #
def filter_by_frequency(text: str, min_count: int = 1,
                        max_count: int = None) -> dict:
    if not isinstance(min_count, int) or isinstance(min_count, bool) or min_count < 1:
        raise ValueError("min_count must be an integer >= 1")
    if max_count is not None:
        if not isinstance(max_count, int) or isinstance(max_count, bool):
            raise ValueError("max_count must be an integer")
        if min_count > max_count:
            raise ValueError("min_count must be <= max_count")
    lines = _split(text)
    counts = Counter(lines)
    kept_lines = [ln for ln in lines if min_count <= counts[ln] <= (max_count if max_count is not None else counts[ln])]
    kept_uniq = sorted({ln for ln in kept_lines})
    return {
        "operation": "filter_by_frequency",
        "params": {"min_count": min_count, "max_count": max_count,
                   "total_lines_input": len(lines),
                   "unique_lines_input": len(counts)},
        "results": {"filtered_lines": kept_lines, "lines_kept": len(kept_lines),
                    "lines_removed": len(lines) - len(kept_lines),
                    "unique_lines_kept": len(kept_uniq)},
    }


# --------------------------------------------------------------------------- #
# 5. unique_lines
# --------------------------------------------------------------------------- #
def unique_lines(text: str, case_insensitive: bool = False) -> dict:
    lines = _split(text)
    counts = Counter(ln.lower() if case_insensitive else ln for ln in lines)
    # preserve original casing/order of first appearance among truly-unique lines
    seen = set()
    out = []
    for ln in lines:
        key = ln.lower() if case_insensitive else ln
        if counts[key] == 1 and key not in seen:
            seen.add(key)
            out.append(ln)
    return {
        "operation": "unique_lines",
        "params": {"case_insensitive": case_insensitive, "total_lines": len(lines),
                   "unique_items": len(out)},
        "results": {"lines_appearing_once": out, "count": len(out)},
    }


# --------------------------------------------------------------------------- #
# 6. head_tail_lines
# --------------------------------------------------------------------------- #
def head_tail_lines(text: str, n: int = 10, tail: bool = False) -> dict:
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError("n must be a non-negative integer")
    lines = _split(text)
    if n == 0:
        extracted = []
    else:
        extracted = lines[-n:] if tail else lines[:n]
    return {
        "operation": "tail_lines" if tail else "head_lines",
        "params": {"n": n, "tail": tail, "total_lines": len(lines)},
        "results": {"extracted_lines": extracted, "count": len(extracted)},
    }


# --------------------------------------------------------------------------- #
# 7. reverse_lines
# --------------------------------------------------------------------------- #
def reverse_lines(text: str) -> dict:
    lines = _split(text)
    return {
        "operation": "reverse_lines",
        "params": {"total_lines": len(lines)},
        "results": {"reversed_lines": list(reversed(lines))},
    }
