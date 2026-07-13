"""CLI for tools.stage2_normalization.

    python -m tools.stage2_normalization input.txt [-o cleaned.txt]
    python -m tools.stage2_normalization            # reads stdin, writes stdout

Exit 0 on success, 1 on failure (message to stderr). Summary prints to stdout.
"""
from __future__ import annotations

import argparse
import os
import sys

from .core import _normalize_with_count

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("stage2_normalization")
except Exception:  # structured_logger optional; never let logging break the tool
    _logger = None


def _read_input(path: str | None) -> str:
    """Read input text from a file path, or stdin when path is None."""
    if path is None:
        return sys.stdin.read()
    if not os.path.isfile(path):
        raise FileNotFoundError(f"input file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="stage2_normalization",
        description="Normalize whitespace and remove exact-duplicate lines (Stage 2).",
    )
    parser.add_argument("input", nargs="?", default=None,
                        help="path to input text (default: stdin)")
    parser.add_argument("-o", "--output", default=None,
                        help="output path (default: stdout)")
    args = parser.parse_args(argv)

    src = args.input if args.input is not None else "(stdin)"
    try:
        text = _read_input(args.input)
    except (FileNotFoundError, ValueError, UnicodeDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    before = len(text)
    cleaned, dup = _normalize_with_count(text)
    after = len(cleaned)

    dest = "(stdout)"
    if args.output:
        out_dir = os.path.dirname(os.path.abspath(args.output))
        try:
            os.makedirs(out_dir, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(cleaned)
        except OSError as e:
            print(f"error: cannot write output {args.output}: {e}", file=sys.stderr)
            return 1
        dest = args.output

    if _logger:
        _logger.log(event_type="normalization_started", data={"source": src, "char_count": before})
        _logger.log(event_type="normalization_complete", data={
            "source": src, "dest": dest,
            "char_count_before": before, "char_count_after": after,
            "duplicates_removed": dup,
        })

    # Content first, then summary line (spec: summary to stdout).
    if not args.output:
        sys.stdout.write(cleaned)
        if cleaned and not cleaned.endswith("\n"):
            sys.stdout.write("\n")
    print(f"Normalized {src} → {dest} ({before} chars → {after} chars, {dup} duplicates removed)",
          file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
