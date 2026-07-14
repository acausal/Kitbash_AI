"""CLI for tools.text_search.

Reads raw text from stdin, dispatches on the first CLI arg (command name),
writes JSON to stdout. Flags via argparse.

    echo "..." | python -m tools.text_search search_text --pattern "photo" --context_lines 2
    echo "..." | python -m tools.text_search search_and_extract --pattern 'fact_(\d+)'
    echo "..." | python -m tools.text_search replace_matches --pattern p --replacement r

Exit codes: 0 success | 1 ValueError (bad input) | 2 RuntimeError (internal).
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import (
    count_matches,
    replace_matches,
    search_and_extract,
    search_lines,
    search_text,
)

_COMMANDS = ("search_text", "search_lines", "search_and_extract",
             "count_matches", "replace_matches")


def _dispatch(cmd: str, text: str, args) -> dict:
    if cmd == "search_text":
        return search_text(text, args.pattern, context_lines=args.context_lines,
                           case_insensitive=args.case_insensitive,
                           multiline=args.multiline, verbose=args.verbose,
                           inverse=args.inverse)
    if cmd == "search_lines":
        lines = text.split("\n") if text else []
        return search_lines(lines, args.pattern, context_lines=args.context_lines,
                            case_insensitive=args.case_insensitive,
                            multiline=args.multiline, verbose=args.verbose,
                            inverse=args.inverse)
    if cmd == "search_and_extract":
        return search_and_extract(text, args.pattern, group_number=args.group_number,
                                  case_insensitive=args.case_insensitive)
    if cmd == "count_matches":
        return count_matches(text, args.pattern, case_insensitive=args.case_insensitive)
    if cmd == "replace_matches":
        if args.replacement is None:
            raise ValueError("replace_matches requires --replacement")
        return replace_matches(text, args.pattern, args.replacement,
                               case_insensitive=args.case_insensitive,
                               count_limit=args.count_limit)
    raise ValueError(f"unknown command: {cmd}")  # unreachable


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="text_search",
        description="Regex search/extract/count/replace over text (v1).",
    )
    parser.add_argument("command", choices=_COMMANDS)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--replacement")
    parser.add_argument("--context_lines", type=int, default=2)
    parser.add_argument("--group_number", type=int, default=0)
    parser.add_argument("--count_limit", type=int, default=None)
    parser.add_argument("--case_insensitive", action="store_true")
    parser.add_argument("--multiline", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--inverse", action="store_true")
    args = parser.parse_args(argv)

    text = sys.stdin.read()

    try:
        result = _dispatch(args.command, text, args)
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
