"""CLI for tools.templating.

Subcommands:
  render <template> <variables_json> [--mode strict|lenient]
  render-file <template_file> <variables_json_file> [--mode ...]
JSON to stdout, summary to stderr. Exit 0 success / 1 error.
"""
import argparse
import json
import sys

from .core import template_render


def _load_vars(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="tools.templating")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("template")
    r.add_argument("variables", help="JSON object string")
    r.add_argument("--mode", default="strict", choices=["strict", "lenient"])
    rf = sub.add_parser("render-file")
    rf.add_argument("template_file")
    rf.add_argument("variables_file")
    rf.add_argument("--mode", default="strict", choices=["strict", "lenient"])
    args = p.parse_args(argv)
    try:
        if args.cmd == "render":
            variables = json.loads(args.variables)
            template = args.template
        else:
            with open(args.template_file, encoding="utf-8") as f:
                template = f.read()
            variables = _load_vars(args.variables_file)
        result = template_render(template, variables, mode=args.mode)
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"[error] {exc}\n")
        return 2
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
