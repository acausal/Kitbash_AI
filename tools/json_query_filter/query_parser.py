"""Lightweight JSON query DSL parser + evaluator for tools.json_query_filter.

Grammar (per SPEC-json_query_filter_v1.md):
  query := path (pipe)*
  path  := '.' seg ('.' seg)* | '.' '{' fields '}' | (empty -> root)
  seg   := field | field '[' index | '*' | slice | '?' filter ']' | '//' default
  pipe  := '|' ('type' | 'length')

Evaluation is left-to-right, short-circuiting to MISSING on missing paths, null
navigation, or type mismatches. A present null value is distinguished from a
missing value via the _MISSING sentinel. Malformed syntax raises ValueError.
Pure stdlib. Imported by core.py.
"""
from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

_MISSING = object()  # sentinel: path did not resolve to a present value


def _type_name(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return "unknown"


_SEG_RE = re.compile(r"^([^.\[]+)(.*)$")


def _parse_filter(expr: str) -> Tuple[str, str, Any]:
    m = re.match(r"^\s*([A-Za-z_][\w.]*)\s*(==|!=|>|<)\s*(.+?)\s*$", expr)
    if not m:
        raise ValueError(f"invalid filter condition: {expr!r}")
    return m.group(1), m.group(2), _parse_literal(m.group(3))


def _parse_literal(raw: str) -> Any:
    raw = raw.strip()
    if len(raw) >= 2 and ((raw[0] == '"' and raw[-1] == '"') or (raw[0] == "'" and raw[-1] == "'")):
        return raw[1:-1]
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw == "null":
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _apply_filter(item: Any, field: str, op: str, value: Any) -> bool:
    if not isinstance(item, dict) or field not in item:
        return False
    lhs = item[field]
    rhs = value
    if isinstance(lhs, str) and isinstance(rhs, str):
        pass
    elif isinstance(lhs, bool) or isinstance(rhs, bool):
        pass
    elif isinstance(lhs, (int, float)) and not isinstance(lhs, bool):
        try:
            rhs = float(rhs) if ("." in str(rhs) or "e" in str(rhs).lower()) else int(rhs)
        except (ValueError, TypeError):
            pass
    if op == "==":
        return lhs == rhs
    if op == "!=":
        return lhs != rhs
    if op == ">":
        return lhs > rhs
    if op == "<":
        return lhs < rhs
    raise ValueError(f"unsupported operator: {op}")


def _navigate(obj: Any, field: str) -> Any:
    if isinstance(obj, dict) and field in obj:
        return obj[field]  # may be None (present null)
    return _MISSING


def _eval_array_step(arr: Any, spec: str) -> Any:
    if not isinstance(arr, list):
        return _MISSING
    spec = spec.strip()
    if spec == "*":
        return arr
    if spec.isdigit() or (spec.startswith("-") and spec[1:].isdigit()):
        idx = int(spec)
        if -len(arr) <= idx < len(arr):
            return arr[idx]
        return _MISSING
    if ":" in spec:
        parts = spec.split(":")
        try:
            s = int(parts[0]) if parts[0] else None
            e = int(parts[1]) if len(parts) > 1 and parts[1] else None
        except ValueError:
            raise ValueError(f"invalid slice: {spec!r}")
        return arr[s:e]
    cond = spec[1:] if spec.startswith("?") else spec
    return [it for it in arr if _apply_filter(it, *_parse_filter(cond))]


def _resolve_default(value: Any, default_expr: Optional[str]) -> Any:
    if value is not _MISSING:
        return value
    if default_expr is None:
        return _MISSING
    return _parse_literal(default_expr.strip())


def _split_default(seg: str) -> Tuple[str, Optional[str]]:
    if "//" in seg:
        idx = seg.index("//")
        return seg[:idx].rstrip(), seg[idx + 2:].strip()
    return seg, None


def _evaluate_single_path(obj: Any, path: str) -> Any:
    path = path.strip()
    if path == "" or path == ".":
        return obj
    if not path.startswith("."):
        raise ValueError(f"path must start with '.': {path!r}")
    if path.startswith(".{") and path.endswith("}"):
        inner = path[2:-1]
        fields = [f.strip() for f in inner.split(",") if f.strip()]
        if not isinstance(obj, dict):
            return _MISSING
        return {f: obj[f] for f in fields if f in obj}
    segs = [s for s in path[1:].split(".") if s != ""]
    cur: Any = obj
    for i, raw_seg in enumerate(segs):
        seg, default_expr = _split_default(raw_seg)
        m = _SEG_RE.match(seg)
        if not m:
            raise ValueError(f"malformed path segment: {seg!r}")
        field, brackets = m.group(1), m.group(2)
        if brackets and brackets.count("[") != brackets.count("]"):
            raise ValueError(f"unclosed bracket in segment: {seg!r}")
        cur = _navigate(cur, field)
        for b in re.findall(r"\[([^\]]*)\]", brackets):
            cur = _eval_array_step(cur, b)
            if cur is _MISSING:
                break
        if cur is _MISSING:
            if default_expr is not None:
                return _parse_literal(default_expr.strip())
            return _MISSING
        if default_expr is not None:
            cur = _resolve_default(cur, default_expr)
        if isinstance(cur, list) and i < len(segs) - 1:
            nxt = segs[i + 1].split("//", 1)[0]
            if re.match(r"^[^.\[]+$", nxt):
                cur = [_evaluate_single_path(it, "." + nxt) for it in cur]
                break
    return cur


def parse_query(query: str) -> Tuple[List[str], List[str]]:
    query = query.strip()
    if not query:
        raise ValueError("empty query")
    if "|" in query:
        head, tail = query.split("|", 1)
        paths, pipes = parse_query(head)
        t = tail.strip()
        if t.startswith("|"):
            t = t[1:].strip()
        return paths, pipes + [t]
    return [query], []


def evaluate_query(obj: Any, query: str) -> Tuple[Any, bool]:
    paths, pipes = parse_query(query)
    if not paths:
        raise ValueError("empty query path")
    value = _evaluate_single_path(obj, paths[0])
    if value is _MISSING:
        return None, False
    for pipe in pipes:
        if value is None:
            break
        if pipe == "type":
            value = _type_name(value)
        elif pipe == "length":
            value = len(value) if isinstance(value, (str, list, dict)) else None
        else:
            raise ValueError(f"unknown pipe: {pipe!r}")
    return value, True
