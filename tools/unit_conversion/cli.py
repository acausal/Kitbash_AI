"""CLI for tools.unit_conversion.

Subcommand: convert <value> <from_unit> <to_unit> [--precision N]
JSON to stdout, summary to stderr. Exit 0 success / 1 error.
"""
import argparse
import json
import sys

from .core import convert_units


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="tools.unit_conversion")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert")
    c.add_argument("value", type=float)
    c.add_argument("from_unit")
    c.add_argument("to_unit")
    c.add_argument("--precision", type=int, default=2)
    args = p.parse_args(argv)
    try:
        result = convert_units(args.value, args.from_unit, args.to_unit, precision=args.precision)
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"[error] {exc}\n")
        return 2
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
