"""CLI for tools.filesystem_access.

Each subcommand maps to a core function. write_file reads its content from
stdin (JSON string or raw text); the rest take --path. All write JSON to stdout.

    python -m tools.filesystem_access read_file --path "workspace/data.json"
    echo '{"key":"value"}' | python -m tools.filesystem_access write_file --path "workspace/output.json"
    python -m tools.filesystem_access list_directory --path "workspace/" --recursive
    python -m tools.filesystem_access file_exists --path "workspace/data.json"
    python -m tools.filesystem_access get_file_metadata --path "workspace/data.json"
    python -m tools.filesystem_access delete_file --path "scratch/temp.json"

Exit codes: 0 success | 1 ValueError (boundary) | 2 FileNotFoundError |
3 IOError/RuntimeError (internal).
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import (
    delete_file, file_exists, get_file_metadata,
    list_directory, read_file, write_file,
)

_COMMANDS = (
    "read_file", "write_file", "delete_file",
    "list_directory", "file_exists", "get_file_metadata",
)


def _load_config_arg(args) -> dict:
    # config is passed by path; core falls back to bundled default if None
    return args.config


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="filesystem_access",
        description="Airlock-bounded safe filesystem I/O (v1).",
    )
    parser.add_argument("command", choices=_COMMANDS)
    parser.add_argument("--path", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--mode", default="w", choices=("w", "a", "x"))
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--include_metadata", action="store_true", default=True)
    parser.add_argument("--no_metadata", action="store_true")
    args = parser.parse_args(argv)

    cmd = args.command
    cfg = _load_config_arg(args)
    try:
        if cmd == "read_file":
            result = read_file(args.path, config=cfg)
        elif cmd == "write_file":
            raw = sys.stdin.read()
            try:
                content = json.loads(raw)
                content = json.dumps(content, ensure_ascii=False)
            except json.JSONDecodeError:
                content = raw  # raw text (e.g. "new line")
            result = write_file(args.path, content, mode=args.mode, config=cfg)
        elif cmd == "delete_file":
            result = delete_file(args.path, config=cfg)
        elif cmd == "list_directory":
            inc = (not args.no_metadata) and args.include_metadata
            result = list_directory(args.path, recursive=args.recursive,
                                    include_metadata=inc, config=cfg)
        elif cmd == "file_exists":
            result = file_exists(args.path, config=cfg)
        elif cmd == "get_file_metadata":
            result = get_file_metadata(args.path, config=cfg)
        else:
            raise ValueError(f"unknown command: {cmd}")
    except ValueError as e:
        print(json.dumps({"error": str(e), "error_type": "ValueError"}), file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(json.dumps({"error": str(e), "error_type": "FileNotFoundError"}), file=sys.stderr)
        return 2
    except (OSError, RuntimeError) as e:
        print(json.dumps({"error": str(e), "error_type": type(e).__name__}), file=sys.stderr)
        return 3

    print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
