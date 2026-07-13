"""CLI for tools.negation_detector.

    python -m tools.negation_detector input.txt [--window/-w N]

Reads text from a file, marks negated tokens, prints a JSON object
{tokens, token_count, negated_count, negation_markers} to stdout and a summary
line to stderr. Exit 0 on success, 1 on failure.
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import detect_negations
from .negation_markers import is_negation_marker


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="negation_detector",
        description="Detect negation and mark tokens within a window (v1).",
    )
    parser.add_argument("input", help="path to input text file")
    parser.add_argument("-w", "--window", type=int, default=5,
                        help="token window around each negation marker (default: 5)")
    args = parser.parse_args(argv)

    try:
        with open(args.input, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        print(f"error: cannot read input {args.input}: {e}", file=sys.stderr)
        return 1

    try:
        tokens = detect_negations(text, window=args.window)
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    negated = sum(1 for t in tokens if t.is_negated)
    markers = [t.text for t in tokens if is_negation_marker(t.text, t.lemma)]
    payload = {
        "tokens": [t.to_dict() for t in tokens],
        "token_count": len(tokens),
        "negated_count": negated,
        "negation_markers": markers,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stdout)
    print(f"Detected negations in {args.input} \u2192 {len(tokens)} tokens, "
          f"{negated} marked as negated", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
