"""CLI for tools.contractions.

    echo "I don't think I'll go. That's fine." | python -m tools.contractions expand_contractions
    echo "I DON'T THINK I'LL GO." | python -m tools.contractions expand_contractions --preserve_case false
    echo "don't" | python -m tools.contractions expand_word
    python -m tools.contractions list_contractions

Exit codes: 0 success | 1 ValueError (invalid input) | 2 RuntimeError (library error).
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import expand_contractions, expand_word, list_contractions

_COMMANDS = ("expand_contractions", "expand_word", "list_contractions")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="contractions",
        description="Deterministic English contraction expansion (v1).",
    )
    parser.add_argument("command", choices=_COMMANDS)
    parser.add_argument("--preserve_case", default="true",
                        choices=("true", "false"))
    parser.add_argument("--text", default=None, help="text/word (alt to stdin)")
    args = parser.parse_args(argv)

    preserve = args.preserve_case != "false"
    try:
        if args.command == "expand_contractions":
            text = args.text if args.text is not None else sys.stdin.read()
            result = expand_contractions(text, preserve_case=preserve)
        elif args.command == "expand_word":
            word = args.text if args.text is not None else sys.stdin.read().strip()
            result = expand_word(word, preserve_case=preserve)
        elif args.command == "list_contractions":
            result = list_contractions()
        else:
            raise ValueError(f"unknown command: {args.command}")
    except ValueError as e:
        print(json.dumps({"error": str(e), "error_type": "ValueError"}), file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(json.dumps({"error": str(e), "error_type": "RuntimeError"}), file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
