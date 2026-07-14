"""text_search core: regex search over text/lines (thin stdlib `re` wrapper).

Isolation-first tool (see tools/README.md). Allowed imports: stdlib and Kitbash
core's structured_logger (read-only helper). No orchestrator/engine/redis imports.

All functions return JSON-serializable dicts. Lines are 1-indexed. `multiline`
maps to re.DOTALL (per SPEC naming). None text/pattern -> ValueError; empty text
/ empty pattern are acceptable (per test cases 29/31).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("text_search")
except Exception:  # optional; never let logging break the tool
    _logger = None


def _build_flags(case_insensitive: bool, multiline: bool, verbose: bool) -> int:
    flags = 0
    if case_insensitive:
        flags |= re.IGNORECASE
    if multiline:
        flags |= re.DOTALL  # SPEC: "multiline" => '.' matches newlines
    if verbose:
        flags |= re.VERBOSE
    return flags


def _compile(pattern: str, flags: int) -> "re.Pattern":
    if pattern is None:
        raise ValueError("pattern must not be None")
    if not isinstance(pattern, str):
        raise ValueError("pattern must be a string")
    try:
        return re.compile(pattern, flags)
    except re.error as e:
        raise ValueError(f"invalid regex pattern: {e}")


def _ctx(lines: List[str], idx: int, context_lines: int, before: bool) -> List[dict]:
    out = []
    if before:
        lo = max(0, idx - context_lines)
        for j in range(lo, idx):
            out.append({"line_number": j + 1, "text": lines[j]})
    else:
        hi = min(len(lines), idx + 1 + context_lines)
        for j in range(idx + 1, hi):
            out.append({"line_number": j + 1, "text": lines[j]})
    return out


# --------------------------------------------------------------------------- #
# search_lines (core matcher; search_text delegates here)
# --------------------------------------------------------------------------- #
def search_lines(lines: list, pattern: str, context_lines: int = 2,
                 case_insensitive: bool = False, multiline: bool = False,
                 verbose: bool = False, inverse: bool = False) -> dict:
    if lines is None:
        raise ValueError("lines must not be None")
    if not isinstance(lines, list):
        raise ValueError("lines must be a list")
    if not isinstance(context_lines, int) or isinstance(context_lines, bool) or context_lines < 0:
        raise ValueError("context_lines must be a non-negative integer")
    rx = _compile(pattern, _build_flags(case_insensitive, multiline, verbose))

    matches: List[dict] = []
    lines_with = 0
    match_no = 0
    for i, line in enumerate(lines):
        found = list(rx.finditer(line))
        if inverse:
            if not found:
                match_no += 1
                matches.append({
                    "match_number": match_no,
                    "line_number": i + 1,
                    "matched_text": line,
                    "match_position": {"start": 0, "end": len(line)},
                    "context_before": _ctx(lines, i, context_lines, True),
                    "context_after": _ctx(lines, i, context_lines, False),
                })
            continue
        if found:
            lines_with += 1
            for m in found:
                match_no += 1
                matches.append({
                    "match_number": match_no,
                    "line_number": i + 1,
                    "matched_text": line,
                    "match_position": {"start": m.start(), "end": m.end()},
                    "context_before": _ctx(lines, i, context_lines, True),
                    "context_after": _ctx(lines, i, context_lines, False),
                })
    if inverse:
        lines_with = len(matches)
    if _logger:
        _logger.log(event_type="search_complete",
                    data={"pattern": pattern, "total_lines": len(lines),
                          "matches_found": len(matches)})
    return {
        "search_params": {
            "pattern": pattern, "context_lines": context_lines,
            "case_insensitive": case_insensitive, "multiline": multiline,
            "inverse": inverse, "total_lines_searched": len(lines),
        },
        "results": {
            "total_matches": len(matches),
            "total_lines_with_matches": lines_with,
            "matches": matches,
        },
    }


def search_text(text: str, pattern: str, context_lines: int = 2,
                case_insensitive: bool = False, multiline: bool = False,
                verbose: bool = False, inverse: bool = False) -> dict:
    if text is None:
        raise ValueError("text must not be None")
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    # multiline (re.DOTALL) lets '.' match newlines, which is only observable
    # when the whole text is searched as one unit (per-line split would strip
    # the newline). SPEC test 24: search_text("a\nb", "a.b", multiline=True).
    if multiline:
        lines = [text]
    else:
        lines = text.split("\n") if text else []
    res = search_lines(lines, pattern, context_lines, case_insensitive,
                       multiline, verbose, inverse)
    return res


# --------------------------------------------------------------------------- #
# search_and_extract
# --------------------------------------------------------------------------- #
def search_and_extract(text: str, pattern: str, group_number: int = 0,
                       case_insensitive: bool = False) -> dict:
    if text is None:
        raise ValueError("text must not be None")
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if not isinstance(group_number, int) or isinstance(group_number, bool) or group_number < 0:
        raise ValueError("group_number must be a non-negative integer")
    rx = _compile(pattern, _build_flags(case_insensitive, False, False))
    lines = text.split("\n") if text else []

    extracted: List[dict] = []
    match_no = 0
    for i, line in enumerate(lines):
        for m in rx.finditer(line):
            match_no += 1
            groups = {"group_0": m.group(0)}
            for gi, gv in enumerate(m.groups(), start=1):
                groups[f"group_{gi}"] = gv
            if group_number > (len(m.groups())):
                raise ValueError(f"group_number {group_number} out of range")
            extracted.append({
                "match_number": match_no,
                "line_number": i + 1,
                "full_match": m.group(0),
                "requested_group": m.group(group_number),
                "extracted_groups": groups,
            })
    return {
        "search_params": {"pattern": pattern, "group_number": group_number,
                          "case_insensitive": case_insensitive},
        "results": {"total_matches": len(extracted), "extracted_values": extracted},
    }


# --------------------------------------------------------------------------- #
# count_matches
# --------------------------------------------------------------------------- #
def count_matches(text: str, pattern: str, case_insensitive: bool = False) -> dict:
    if text is None:
        raise ValueError("text must not be None")
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    rx = _compile(pattern, _build_flags(case_insensitive, False, False))
    lines = text.split("\n") if text else []
    total = 0
    lines_with = 0
    for line in lines:
        n = len(rx.findall(line))
        if n:
            lines_with += 1
            total += n
    density = round(total / len(lines), 4) if lines else 0.0
    return {
        "pattern": pattern,
        "case_insensitive": case_insensitive,
        "total_matches": total,
        "total_lines_searched": len(lines),
        "lines_with_matches": lines_with,
        "match_density": density,
    }


# --------------------------------------------------------------------------- #
# replace_matches
# --------------------------------------------------------------------------- #
def replace_matches(text: str, pattern: str, replacement: str,
                    case_insensitive: bool = False,
                    count_limit: int = None) -> dict:
    if text is None:
        raise ValueError("text must not be None")
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if replacement is None or not isinstance(replacement, str):
        raise ValueError("replacement must be a string")
    if count_limit is not None:
        if not isinstance(count_limit, int) or isinstance(count_limit, bool) or count_limit < 0:
            raise ValueError("count_limit must be a non-negative integer")
    rx = _compile(pattern, _build_flags(case_insensitive, False, False))
    lines = text.split("\n") if text else []

    remaining = count_limit if count_limit is not None else -1  # -1 = unlimited
    changes: List[dict] = []
    new_lines: List[str] = []
    change_no = 0
    total_repl = 0
    for i, line in enumerate(lines):
        if remaining == 0:
            new_lines.append(line)
            continue
        per_line = 0 if remaining < 0 else remaining
        try:
            if remaining < 0:
                new_line, n = rx.subn(replacement, line)
            else:
                new_line, n = rx.subn(replacement, line, count=per_line)
        except re.error as e:
            raise ValueError(f"invalid replacement / backreference: {e}")
        if n:
            change_no += 1
            total_repl += n
            changes.append({"change_number": change_no, "line_number": i + 1,
                            "original": line, "replaced": new_line})
            if remaining > 0:
                remaining -= n
        new_lines.append(new_line)

    modified = "\n".join(new_lines) if text else ""
    if _logger:
        _logger.log(event_type="replace_complete",
                    data={"pattern": pattern, "replacements_made": total_repl})
    return {
        "search_params": {"pattern": pattern, "replacement": replacement,
                          "case_insensitive": case_insensitive,
                          "count_limit": count_limit,
                          "replacements_made": total_repl},
        "original_text": text,
        "modified_text": modified,
        "changes": changes,
    }
