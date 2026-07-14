"""CLI for tools.edge_weight_mutation.

Subcommands:
  mutate <graph.json> <edge_id> <delta> [--reason R]
  mutate-batch <graph.json> <mutations.json> [--no-atomic]
JSON to stdout, summary to stderr. Exit 0 success / 1 error.
"""
import argparse
import json
import sys

from .core import edge_mutate, edge_mutate_batch


def _deep_copy(graph: dict) -> dict:
    return json.loads(json.dumps(graph))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="tools.edge_weight_mutation")
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mutate")
    m.add_argument("graph_file")
    m.add_argument("edge_id")
    m.add_argument("delta", type=float)
    m.add_argument("--reason")
    b = sub.add_parser("mutate-batch")
    b.add_argument("graph_file")
    b.add_argument("mutations_file")
    b.add_argument("--no-atomic", dest="atomic", action="store_false", default=True)
    args = p.parse_args(argv)
    try:
        graph = json.load(open(args.graph_file, encoding="utf-8"))
        if args.cmd == "mutate":
            result = edge_mutate(graph, args.edge_id, args.delta, reason=args.reason)
            if result.get("status") == "success":
                json.dump(graph, open(args.graph_file, "w", encoding="utf-8"), indent=2)
        else:
            mutations = json.load(open(args.mutations_file, encoding="utf-8"))
            result = edge_mutate_batch(graph, mutations, atomic=args.atomic)
            if result.get("status") == "success":
                json.dump(graph, open(args.graph_file, "w", encoding="utf-8"), indent=2)
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"[error] {exc}\n")
        return 2
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
