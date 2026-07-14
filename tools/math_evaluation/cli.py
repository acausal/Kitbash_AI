"""CLI for tools.math_evaluation.

Subcommand: evaluate <expression> [--precision N]
JSON to stdout, summary to stderr. Exit 0 success / 1 error.
"""
import argparse
import json
import sys

from .core import safe_evaluate


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="tools.math_evaluation")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("evaluate")
    e.add_argument("expression")
    e.add_argument("--precision", type=int, default=10)
    args = p.parse_args(argv)
    try:
        result = safe_evaluate(args.expression, precision=args.precision)
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"[error] {exc}\n")
        return 2
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
