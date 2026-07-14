"""json_query_filter core: path-based JSON query/filter/extract/flatten/validate.

Isolation-first tool (see tools/README.md). Allowed imports: stdlib and Kitbash
core's structured_logger (read-only helper). No orchestrator/engine/redis imports.

The query DSL is implemented in query_parser.py. All functions return
JSON-serializable dicts. Missing fields / null navigation / type mismatches
return null with found=False (never raise) — only malformed syntax raises
ValueError. Pairs with tools.line_filtering / text_search for data plumbing.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("json_query_filter")
except Exception:  # optional; never let logging break the tool
    _logger = None

from .query_parser import evaluate_query, _type_name


# --------------------------------------------------------------------------- #
# 1. query_json
# --------------------------------------------------------------------------- #
def query_json(json_obj: dict, query: str) -> dict:
    if not isinstance(json_obj, dict):
        raise ValueError("json_obj must be a dict")
    try:
        value, found = evaluate_query(json_obj, query)
    except ValueError as e:
        raise ValueError(f"invalid query syntax: {e}")
    if isinstance(value, list):
        rtype, rcount = "array", len(value)
    else:
        rtype, rcount = _type_name(value), None
    return {
        "query": query,
        "result": value,
        "result_type": rtype,
        "found": found,
        "result_count": rcount,
    }


# --------------------------------------------------------------------------- #
# 2. filter_json_array
# --------------------------------------------------------------------------- #
def filter_json_array(json_array: list, filter_query: str) -> dict:
    if not isinstance(json_array, list):
        raise ValueError("json_array must be a list")
    # filter_query looks like: ?field op value
    if not filter_query.strip().startswith("?"):
        raise ValueError("filter_query must start with '?'")
    cond = filter_query.strip()[1:]
    from .query_parser import _parse_filter, _apply_filter
    try:
        field, op, value = _parse_filter(cond)
    except ValueError as e:
        raise ValueError(f"invalid filter syntax: {e}")
    results = [it for it in json_array if _apply_filter(it, field, op, value)]
    return {
        "filter": filter_query,
        "total_items": len(json_array),
        "filtered_items": len(results),
        "results": results,
    }


# --------------------------------------------------------------------------- #
# 3. extract_fields
# --------------------------------------------------------------------------- #
def extract_fields(json_obj: Any, fields: list) -> dict:
    if not isinstance(fields, list) or not all(isinstance(f, str) for f in fields):
        raise ValueError("fields must be a list of strings")
    if isinstance(json_obj, dict):
        return {
            "fields_requested": fields,
            "extraction": {f: json_obj[f] for f in fields if f in json_obj},
        }
    if isinstance(json_obj, list):
        if not all(isinstance(e, dict) for e in json_obj):
            raise ValueError("array elements must be objects")
        return {
            "fields_requested": fields,
            "total_items": len(json_obj),
            "results": [{f: e[f] for f in fields if f in e} for e in json_obj],
        }
    raise ValueError("json_obj must be a dict or list")


# --------------------------------------------------------------------------- #
# 4. flatten_json
# --------------------------------------------------------------------------- #
def flatten_json(json_obj: dict, max_depth: int = None,
                 separator: str = ".") -> dict:
    if not isinstance(json_obj, dict):
        raise ValueError("json_obj must be a dict")
    if max_depth is not None:
        if not isinstance(max_depth, int) or isinstance(max_depth, bool) or max_depth < 0:
            raise ValueError("max_depth must be a non-negative integer")
    if not isinstance(separator, str):
        raise ValueError("separator must be a string")

    flat: Dict[str, Any] = {}

    def _walk(prefix: str, val: Any, depth: int) -> None:
        if isinstance(val, dict) and (max_depth is None or depth <= max_depth):
            if not val:
                flat[prefix] = {}
            for k, v in val.items():
                nk = f"{prefix}{separator}{k}" if prefix else k
                _walk(nk, v, depth + 1)
        else:
            flat[prefix] = val

    _walk("", json_obj, 0)
    return {
        "original": json_obj,
        "flattened": flat,
        "max_depth": max_depth,
        "separator": separator,
    }


# --------------------------------------------------------------------------- #
# 5. validate_schema
# --------------------------------------------------------------------------- #
_TYPE_MAP = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def validate_schema(json_obj: dict, schema: dict) -> dict:
    if not isinstance(json_obj, dict):
        raise ValueError("json_obj must be a dict")
    if not isinstance(schema, dict):
        raise ValueError("schema must be a dict")

    required = schema.get("required", [])
    types = schema.get("types", {})
    if not isinstance(required, list) or not isinstance(types, dict):
        raise ValueError("schema 'required' must be a list and 'types' a dict")

    errors: List[Dict[str, str]] = []
    required_checks = {}
    type_checks = {}

    for f in required:
        if f in json_obj:
            required_checks[f] = "present"
        else:
            required_checks[f] = "missing"
            errors.append({"field": f, "error": "missing required field"})

    for f, expected in types.items():
        actual = json_obj.get(f, None)
        actual_type = _type_name(actual)
        exp_name = expected
        match = False
        if actual is None and f not in json_obj:
            # type checked only if field present; missing handled by required
            type_checks[f] = {"expected": exp_name, "actual": "missing", "match": False}
            # not necessarily an error unless required; flag type mismatch only if present
            if f in required:
                errors.append({"field": f, "error": f"type mismatch: expected {exp_name}, got missing"})
            continue
        # bool is subclass of int — treat as boolean when expected boolean
        if exp_name == "boolean" and isinstance(actual, bool):
            match = True
        elif exp_name == "number" and isinstance(actual, bool):
            match = False
        elif exp_name in _TYPE_MAP:
            cls = _TYPE_MAP[exp_name]
            match = isinstance(actual, cls) and not (exp_name == "integer" and isinstance(actual, bool))
            if exp_name == "number":
                match = isinstance(actual, (int, float)) and not isinstance(actual, bool)
        else:
            errors.append({"field": f, "error": f"unknown type in schema: {exp_name}"})
        type_checks[f] = {"expected": exp_name, "actual": actual_type, "match": match}
        if not match and f in json_obj:
            errors.append({"field": f,
                           "error": f"type mismatch: expected {exp_name}, got {actual_type}"})

    return {
        "valid": len(errors) == 0,
        "schema_checks": {"required_fields": required_checks, "type_checks": type_checks},
        "errors": errors,
    }
