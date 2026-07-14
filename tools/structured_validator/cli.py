"""CLI for tools.structured_validator.

    python -m tools.structured_validator input.txt --grammar grammars/greeting.lark
    python -m tools.structured_validator input.txt --grammar-string 'start: "hi"'

Reads input text from a file, loads a Lark grammar (from a .lark file path or an
inline string via --grammar-string), validates, then writes a JSON ParseResult
to --output (or stdout) and a summary line to stderr.

Exit codes: 0 = parse succeeded, 1 = validation failed (parse error),
2 = grammar/file error (bad grammar, missing file, bad input).
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import validate_input


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="structured_validator",
        description="Validate text against a Lark grammar (v1).",
    )
    parser.add_argument("input", help="path to input text file")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("-g", "--grammar", default=None,
                   help="path to a .lark grammar file (or inline EBNF string)")
    g.add_argument("--grammar-string", dest="grammar_string", default=None,
                   help="inline Lark EBNF grammar string")
    parser.add_argument("-s", "--start", default="start",
                        help="start rule name (default: start)")
    parser.add_argument("-o", "--output", default=None,
                        help="write JSON to this file (default: stdout)")
    args = parser.parse_args(argv)

    try:
        with open(args.input, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        print(f"error: cannot read input {args.input}: {e}", file=sys.stderr)
        return 2

    grammar = args.grammar_string if args.grammar_string is not None else args.grammar
    try:
        result = validate_input(text, grammar, grammar_start=args.start)
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    payload = result.to_dict()
    out_json = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(out_json)
        except OSError as e:
            print(f"error: cannot write output {args.output}: {e}", file=sys.stderr)
            return 2
    else:
        print(out_json, file=sys.stdout)

    verdict = "PASS" if result.success else "FAIL"
    print(f"Validation: {args.input} against {result.grammar_name} \u2192 {verdict}",
          file=sys.stderr)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
