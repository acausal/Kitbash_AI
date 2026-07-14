"""CLI for tools.line_filtering.

Reads raw text from stdin, dispatches on the first CLI arg (command name),
writes JSON to stdout. Flags via argparse.

    echo -e "cherry\napple\ndate" | python -m tools.line_filtering sort_lines --descending
    echo -e "apple\napple\nbanana" | python -m tools.line_filtering deduplicate_lines
    echo -e "apple\napple\nbanana" | python -m tools.line_filtering count_line_frequency --sort_by frequency

Exit codes: 0 success | 1 ValueError (bad input) | 2 RuntimeError (internal).
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import (
    count_line_frequency,
    deduplicate_lines,
    filter_by_frequency,
    head_tail_lines,
    reverse_lines,
    sort_lines,
    unique_lines,
)

_COMMANDS = ("sort_lines", "deduplicate_lines", "count_line_frequency",
             "filter_by_frequency", "unique_lines", "head_tail_lines", "reverse_lines")


def _dispatch(cmd: str, text: str, args) -> dict:
    if cmd == "sort_lines":
        return sort_lines(text, descending=args.descending,
                          case_insensitive=args.case_insensitive)
    if cmd == "deduplicate_lines":
        return deduplicate_lines(text, preserve_order=not args.no_preserve,
                                 case_insensitive=args.case_insensitive)
    if cmd == "count_line_frequency":
        return count_line_frequency(text, sort_by=args.sort_by)
    if cmd == "filter_by_frequency":
        return filter_by_frequency(text, min_count=args.min_count, max_count=args.max_count)
    if cmd == "unique_lines":
        return unique_lines(text, case_insensitive=args.case_insensitive)
    if cmd == "head_tail_lines":
        return head_tail_lines(text, n=args.n, tail=args.tail)
    if cmd == "reverse_lines":
        return reverse_lines(text)
    raise ValueError(f"unknown command: {cmd}")  # unreachable


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="line_filtering",
        description="Set operations + ordering over newline-delimited text (v1).",
    )
    parser.add_argument("command", choices=_COMMANDS)
    parser.add_argument("--descending", action="store_true")
    parser.add_argument("--case_insensitive", action="store_true")
    parser.add_argument("--no_preserve", action="store_true",
                        help="deduplicate_lines: sort instead of preserving order")
    parser.add_argument("--sort_by", choices=("frequency", "lexicographic"), default="frequency")
    parser.add_argument("--min_count", type=int, default=1)
    parser.add_argument("--max_count", type=int, default=None)
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--tail", action="store_true")
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
