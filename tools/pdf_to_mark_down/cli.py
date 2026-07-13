"""CLI for tools.pdf_to_mark_down. Usage:

    python -m tools.pdf_to_mark_down input.pdf [--output output.md]
    python -m tools.pdf_to_mark_down input.pdf -o output.md

Exit 0 on success, 1 on failure (message to stderr).
"""
from __future__ import annotations

import argparse
import os
import sys

from .core import convert_pdf_to_markdown


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="pdf_to_mark_down",
        description="Extract text from a PDF to clean Markdown-ish text via pypdf.",
    )
    parser.add_argument("input", help="path to input .pdf file")
    parser.add_argument("-o", "--output", default=None,
                        help="output path (default: <input_basename>.md next to input)")
    args = parser.parse_args(argv)

    out = args.output
    if out is None:
        base = os.path.splitext(os.path.basename(args.input))[0]
        out = os.path.join(os.path.dirname(os.path.abspath(args.input)), f"{base}.md")

    try:
        convert_pdf_to_markdown(args.input, out)
    except (FileNotFoundError, ValueError, RuntimeError, IOError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # never crash with a traceback; fail loud but clean
        print(f"error: unexpected failure: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
