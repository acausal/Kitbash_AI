"""CLI for tools.csv_operations.

All row-transform commands (filter/select/sort/unique/stats) read the CSV
source (--file or stdin), parse it, then apply the operation. parse_csv just
parses. All print JSON to stdout.

    echo "name,age\nAlice,30\nBob,25" | python -m tools.csv_operations parse_csv
    python -m tools.csv_operations filter_rows --file data.csv --column age --operator ">" --value 25
    python -m tools.csv_operations select_columns --file data.csv --columns name email
    python -m tools.csv_operations sort_rows --file data.csv --column age --numeric
    python -m tools.csv_operations unique_values --file data.csv --column active
    python -m tools.csv_operations csv_stats --file data.csv

Exit codes: 0 success | 1 ValueError | 2 FileNotFoundError | 3 IOError/RuntimeError.
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import (
    parse_csv, filter_rows, select_columns, sort_rows, unique_values, csv_stats,
)

_COMMANDS = (
    "parse_csv", "filter_rows", "select_columns",
    "sort_rows", "unique_values", "csv_stats",
)


def _source(opts) -> dict:
    """Parse the CSV source once; returns the parse_csv dict."""
    data = None
    if not opts.file and not sys.stdin.isatty():
        data = sys.stdin.read()
    return parse_csv(data=data, file_path=opts.file,
                     has_header=opts.has_header, delimiter=opts.delimiter)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="csv_operations",
        description="Stdlib CSV parse/filter/select/sort/unique/stats (v1).",
    )
    parser.add_argument("command", choices=_COMMANDS)
    parser.add_argument("--file", default=None, help="CSV file path")
    parser.add_argument("--has_header", default="true", choices=("true", "false"))
    parser.add_argument("--delimiter", default=None)
    parser.add_argument("--column", default=None)
    parser.add_argument("--operator", default="==")
    parser.add_argument("--value", default=None)
    parser.add_argument("--columns", nargs="*", default=None)
    parser.add_argument("--exclude", action="store_true")
    parser.add_argument("--descending", action="store_true")
    parser.add_argument("--numeric", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.command == "parse_csv":
            result = _source(args)
        else:
            parsed = _source(args)
            rows = parsed["rows"]
            if args.command == "filter_rows":
                result = filter_rows(rows, args.column, args.operator, args.value)
            elif args.command == "select_columns":
                result = select_columns(rows, args.columns or [], exclude=args.exclude)
            elif args.command == "sort_rows":
                result = sort_rows(rows, args.column, descending=args.descending,
                                   numeric=args.numeric)
            elif args.command == "unique_values":
                result = unique_values(rows, args.column)
            elif args.command == "csv_stats":
                result = csv_stats(rows)
            else:
                raise ValueError(f"unknown command: {args.command}")
    except ValueError as e:
        print(json.dumps({"error": str(e), "error_type": "ValueError"}), file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(json.dumps({"error": str(e), "error_type": "FileNotFoundError"}), file=sys.stderr)
        return 2
    except (OSError, RuntimeError) as e:
        print(json.dumps({"error": str(e), "error_type": type(e).__name__}), file=sys.stderr)
        return 3

    print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
