"""CLI for tools.tokenizer.

    python -m tools.tokenizer input.txt [--lemma/-l] [--remove-stop/-s]

Reads text from a file, tokenizes with spaCy, prints a JSON object
{tokens, token_count, stop_word_count} to stdout, and a summary line.
Exit 0 on success, 1 on failure (message to stderr).
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import tokenize


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="tokenizer",
        description="Tokenize text with spaCy (v1: English).",
    )
    parser.add_argument("input", help="path to input text file")
    parser.add_argument("-l", "--lemma", action="store_true",
                        help="include base-form lemma for each token")
    parser.add_argument("-s", "--remove-stop", action="store_true",
                        help="exclude stop words from the output")
    parser.add_argument("-m", "--model", default="en_core_web_sm",
                        help="spaCy model (default: en_core_web_sm)")
    args = parser.parse_args(argv)

    try:
        with open(args.input, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        print(f"error: cannot read input {args.input}: {e}", file=sys.stderr)
        return 1

    try:
        tokens = tokenize(text, lemmatize=args.lemma,
                          remove_stop=args.remove_stop, model=args.model)
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    stop_count = sum(1 for t in tokens if t.is_stop)
    payload = {
        "tokens": [t.to_dict() for t in tokens],
        "token_count": len(tokens),
        "stop_word_count": stop_count,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stdout)

    removed = " (stop words removed)" if args.remove_stop else ""
    print(f"Tokenized {args.input} \u2192 {len(tokens)} tokens{removed}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
