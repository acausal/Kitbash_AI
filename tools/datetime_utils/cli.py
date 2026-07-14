"""CLI for tools.datetime_utils.

Multi-command: read a JSON object from stdin, dispatch on the first CLI arg
(command name), write the result JSON to stdout. Exit 0 on success, 1 on
ValueError (bad input), 2 on unexpected RuntimeError.

    echo '{"timestamp": "2026-07-14T12:30:45Z"}' | python -m tools.datetime_utils parse_iso8601
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import (
    duration_between,
    format_timestamp,
    get_current_time,
    parse_epoch,
    parse_iso8601,
    parse_string,
    timezone_offset,
)

_COMMANDS = {
    "parse_iso8601": parse_iso8601,
    "parse_epoch": parse_epoch,
    "parse_string": parse_string,
    "format_timestamp": format_timestamp,
    "get_current_time": get_current_time,
    "duration_between": duration_between,
    "timezone_offset": timezone_offset,
}


def _run_command(cmd: str, payload: dict) -> dict:
    fn = _COMMANDS[cmd]
    return fn(**payload)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="datetime_utils",
        description="DateTime parsing/formatting/timezone utilities (v1).",
    )
    parser.add_argument("command", choices=sorted(_COMMANDS),
                        help="subcommand to run")
    args = parser.parse_args(argv)  # validates command name; payload from stdin
    cmd = args.command

    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}), file=sys.stderr)
        return 1

    try:
        result = _run_command(cmd, payload)
    except (ValueError, KeyError, TypeError) as e:
        # ValueError = invalid input per taxonomy; KeyError/TypeError = bad/missing args.
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    except Exception as e:  # pragma: no cover - unexpected internal failure
        print(json.dumps({"error": f"internal error: {e}"}), file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
