"""CLI for tools.unicode_normalizer.

Subcommands: normalize (text from arg or stdin), normalize-file (in -> out),
detect-mojibake (text), batch (JSON array or JSONL from stdin -> one object
per line). All print JSON to stdout.

    echo "Москва café 😀" | python -m tools.unicode_normalizer normalize
    python -m tools.unicode_normalizer normalize "北京 запуск"
    python -m tools.unicode_normalizer normalize-file inbox/raw.txt workspace/clean.txt
    python -m tools.unicode_normalizer detect-mojibake "Ð¼Ð¾Ð¶Ð±Ð°Ðº"
    echo '["café","Москва"]' | python -m tools.unicode_normalizer batch

Exit codes: 0 success | 1 ValueError | 2 FileNotFoundError / OSError / RuntimeError.
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import normalize_text, normalize_file, detect_mojibake


def _read_stdin_text() -> str:
    return sys.stdin.read()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="unicode_normalizer",
        description="Deterministic Unicode -> ASCII transliteration (anyascii).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_norm = sub.add_parser("normalize", help="normalize text (arg or stdin)")
    p_norm.add_argument("text", nargs="?", default=None, help="text (else stdin)")
    p_norm.add_argument("--strip", action="store_true",
                        help="strip unmappable chars instead of preserving")

    p_file = sub.add_parser("normalize-file", help="normalize file in -> out")
    p_file.add_argument("input_path")
    p_file.add_argument("output_path")
    p_file.add_argument("--strip", action="store_true")

    p_moji = sub.add_parser("detect-mojibake", help="detect mojibake")
    p_moji.add_argument("text", nargs="?", default=None)

    p_batch = sub.add_parser("batch", help="normalize a JSON array / JSONL")
    p_batch.add_argument("--strip", action="store_true")

    args = parser.parse_args(argv)

    try:
        if args.command == "normalize":
            text = args.text if args.text is not None else _read_stdin_text()
            result = normalize_text(text, preserve_unknown=not args.strip)
            print(json.dumps(result, ensure_ascii=False))
        elif args.command == "normalize-file":
            result = normalize_file(args.input_path, args.output_path,
                                    preserve_unknown=not args.strip)
            print(json.dumps(result, ensure_ascii=False))
        elif args.command == "detect-mojibake":
            text = args.text if args.text is not None else _read_stdin_text()
            result = detect_mojibake(text)
            print(json.dumps(result, ensure_ascii=False))
        elif args.command == "batch":
            raw = _read_stdin_text().strip()
            items = json.loads(raw) if raw.startswith("[") else [
                json.loads(ln) for ln in raw.splitlines() if ln.strip()
            ]
            out = [normalize_text(str(it), preserve_unknown=not args.strip)
                   for it in items]
            for r in out:
                print(json.dumps(r, ensure_ascii=False))
        else:
            parser.error(f"unknown command: {args.command}")
            return 2
    except ValueError as e:
        print(json.dumps({"error": str(e), "error_type": "ValueError"}), file=sys.stderr)
        return 1
    except (FileNotFoundError, OSError, RuntimeError) as e:
        print(json.dumps({"error": str(e), "error_type": type(e).__name__}), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
