"""CLI for tools.timeseries_windowed_operations.

Subcommand: aggregate <data.json> [--window-size N] [--window-type fixed|sliding]
           [--operation mean|sum|...] [--start T] [--end T]
data.json: JSON array of [timestamp, value] pairs.
JSON to stdout, summary to stderr. Exit 0 success / 1 error.
"""
import argparse
import json
import sys

from .core import timeseries_aggregate


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="tools.timeseries_windowed_operations")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("aggregate")
    a.add_argument("data_file")
    a.add_argument("--window-size", type=int, default=3600)
    a.add_argument("--window-type", default="fixed", choices=["fixed", "sliding"])
    a.add_argument("--operation", default="mean")
    a.add_argument("--start", default=None)
    a.add_argument("--end", default=None)
    args = p.parse_args(argv)
    try:
        data = json.load(open(args.data_file, encoding="utf-8"))
        result = timeseries_aggregate(
            data, window_size=args.window_size, window_type=args.window_type,
            operation=args.operation, start_time=args.start, end_time=args.end)
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"[error] {exc}\n")
        return 2
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
