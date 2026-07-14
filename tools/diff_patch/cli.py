"""CLI for tools.diff_patch.

Subcommands:
  generate <file_a> <file_b> [--context N]   -> unified diff JSON
  apply <file> <patch_file>                 -> patched text JSON
JSON to stdout, summary to stderr. Exit 0 success / 1 error.
"""
import argparse
import json
import sys

from .core import diff_generate, diff_apply


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="tools.diff_patch")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("file_a")
    g.add_argument("file_b")
    g.add_argument("--context", type=int, default=3)
    a = sub.add_parser("apply")
    a.add_argument("file")
    a.add_argument("patch_file")
    args = p.parse_args(argv)
    try:
        if args.cmd == "generate":
            ta = open(args.file_a, encoding="utf-8").read()
            tb = open(args.file_b, encoding="utf-8").read()
            result = diff_generate(ta, tb, context_lines=args.context)
        else:
            text = open(args.file, encoding="utf-8").read()
            patch = open(args.patch_file, encoding="utf-8").read()
            result = diff_apply(text, patch)
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"[error] {exc}\n")
        return 2
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
