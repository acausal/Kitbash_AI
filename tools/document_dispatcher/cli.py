"""CLI for tools.document_dispatcher.

    python -m tools.document_dispatcher input.pdf [-o out.md] [--normalize]
    python -m tools.document_dispatcher input.pdf --output out.md

Exit 0 on success, 1 on failure (message to stderr). Summary prints to stdout.
"""
from __future__ import annotations

import argparse
import os
import sys

from .core import extract_document


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="document_dispatcher",
        description="Detect document format and route to the right extractor (Stage 1).",
    )
    parser.add_argument("input", help="path to input document")
    parser.add_argument("-o", "--output", default=None,
                        help="output path (default: <input_basename>.md)")
    parser.add_argument("--normalize", action="store_true",
                        help="run Stage 2 normalization after extraction (default: off)")
    args = parser.parse_args(argv)

    try:
        out = extract_document(args.input, args.output, normalize=args.normalize)
    except (FileNotFoundError, ValueError, RuntimeError, IOError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # never crash with a traceback; fail loud but clean
        print(f"error: unexpected failure: {e}", file=sys.stderr)
        return 1

    try:
        char_count = len(open(out, encoding="utf-8").read())
    except OSError:
        char_count = 0
    fmt = _format_of(args.input)
    print(f"Detected {fmt}. Converted {args.input} \u2192 {out} ({char_count} chars)",
          file=sys.stdout)
    return 0


def _format_of(input_path: str) -> str:
    from .core import detect_format
    try:
        return detect_format(input_path)
    except ValueError:
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
