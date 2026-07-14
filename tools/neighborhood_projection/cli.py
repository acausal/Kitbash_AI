"""CLI for tools.neighborhood_projection.

Multi-command: read a JSON object from stdin, dispatch on the first CLI arg
(command name), write the result JSON to stdout. Exit 0 on success, 1 on
ValueError (bad input / bad JSON), 2 on RuntimeError (malformed graph).

    echo '{"edge_graph": {...}, "seed_nodes": ["fact_123"], "depth_limit": 2}' \
      | python -m tools.neighborhood_projection project_neighborhood
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import (
    explain_path,
    filter_neighborhood,
    project_neighborhood,
    project_neighborhood_bidirectional,
    rank_neighborhood_by_weight,
)

_COMMANDS = {
    "project_neighborhood": project_neighborhood,
    "project_neighborhood_bidirectional": project_neighborhood_bidirectional,
    "filter_neighborhood": filter_neighborhood,
    "rank_neighborhood_by_weight": rank_neighborhood_by_weight,
    "explain_path": explain_path,
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="neighborhood_projection",
        description="Project/query local neighborhoods over a procedural edge graph (v1).",
    )
    parser.add_argument("command", choices=sorted(_COMMANDS),
                        help="subcommand to run")
    args = parser.parse_args(argv)
    cmd = args.command

    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}), file=sys.stderr)
        return 1
    if not isinstance(payload, dict):
        print(json.dumps({"error": "input JSON must be an object"}), file=sys.stderr)
        return 1

    try:
        result = _COMMANDS[cmd](**payload)
    except ValueError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2
    except (KeyError, TypeError) as e:
        # missing/extra args -> treat as invalid input
        print(json.dumps({"error": f"invalid arguments: {e}"}), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
