"""CLI for tools.json_query_filter.

Reads JSON from stdin, dispatches on the first CLI arg (command name),
writes JSON to stdout. The query/filter/schema are passed as flags.

    echo '{"user":{"name":"Alice"}}' | python -m tools.json_query_filter query_json --query .user.name
    echo '[...]' | python -m tools.json_query_filter filter_json_array --filter '?status == "active"'
    echo '{"id":1,...}' | python -m tools.json_query_filter validate_schema --schema '{...}'

Exit codes: 0 success | 1 ValueError (bad input) | 2 RuntimeError (internal).
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import (
    extract_fields,
    filter_json_array,
    flatten_json,
    query_json,
    validate_schema,
)

_COMMANDS = ("query_json", "filter_json_array", "extract_fields",
             "flatten_json", "validate_schema")


def _dispatch(cmd: str, payload: dict, args) -> dict:
    if cmd == "query_json":
        return query_json(payload, args.query)
    if cmd == "filter_json_array":
        if not isinstance(payload, list):
            raise ValueError("stdin payload must be a JSON array for filter_json_array")
        return filter_json_array(payload, args.filter)
    if cmd == "extract_fields":
        return extract_fields(payload, args.fields)
    if cmd == "flatten_json":
        if not isinstance(payload, dict):
            raise ValueError("stdin payload must be a JSON object for flatten_json")
        return flatten_json(payload, max_depth=args.max_depth, separator=args.separator)
    if cmd == "validate_schema":
        if args.schema is None:
            raise ValueError("validate_schema requires --schema")
        schema = json.loads(args.schema)
        return validate_schema(payload, schema)
    raise ValueError(f"unknown command: {cmd}")  # unreachable


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="json_query_filter",
        description="Path-based JSON query/filter/flatten/validate (v1).",
    )
    parser.add_argument("command", choices=_COMMANDS)
    parser.add_argument("--query")
    parser.add_argument("--filter")
    parser.add_argument("--fields", nargs="+", default=[])
    parser.add_argument("--max_depth", type=int, default=None)
    parser.add_argument("--separator", default=".")
    parser.add_argument("--schema")
    args = parser.parse_args(argv)

    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"invalid JSON input: {e}"}), file=sys.stderr)
        return 1
    # filter_json_array/extract_fields need a payload type; query_json needs dict.
    if args.command == "query_json" and not isinstance(payload, dict):
        print(json.dumps({"error": "query_json requires a JSON object on stdin"}), file=sys.stderr)
        return 1

    try:
        result = _dispatch(args.command, payload, args)
    except ValueError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
