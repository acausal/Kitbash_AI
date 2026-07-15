"""CLI for tools.hypergraph_traversal.

Modes: --neighbors / --paths / --reachability / --coverage (mutually exclusive, required).
Reads a hypergraph JSON from --input; writes JSON to --output or stdout. Exit 0/1/2.
"""
from __future__ import annotations

import argparse
import json
import sys

from tools.historical_common import base_argparse, load_input, write_output, fail, normalize_config
from .core import find_neighbors, find_paths, reachability_analysis, hyperedge_coverage


def main(argv=None) -> int:
    p = base_argparse("hypergraph_traversal")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--neighbors", action="store_true")
    g.add_argument("--paths", action="store_true")
    g.add_argument("--reachability", action="store_true")
    g.add_argument("--coverage", action="store_true")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--max-depth", type=int, default=1)
    p.add_argument("--max-length", type=int, default=4)
    p.add_argument("--nodes", default=None, help="comma-separated target nodes for --coverage")
    p.add_argument("--directed", action="store_true")
    p.add_argument("--unweighted", action="store_true")
    args = p.parse_args(argv)

    try:
        data = load_input(args.input)
        cfg = dict(data.get("config") or {})
        if args.directed:
            cfg["directed"] = True
        if args.unweighted:
            cfg["unweighted"] = True
        cfg = normalize_config(cfg)
        if args.neighbors:
            if not args.start:
                raise ValueError("--start required for --neighbors")
            result = find_neighbors(data, args.start, max_depth=args.max_depth, config=cfg)
        elif args.paths:
            if not args.start or not args.end:
                raise ValueError("--start and --end required for --paths")
            result = find_paths(data, args.start, args.end, max_length=args.max_length, config=cfg)
        elif args.reachability:
            if not args.start:
                raise ValueError("--start required for --reachability")
            result = reachability_analysis(data, args.start, config=cfg)
        else:
            if not args.nodes:
                raise ValueError("--nodes required for --coverage")
            targets = [n.strip() for n in args.nodes.split(",") if n.strip()]
            result = hyperedge_coverage(data, targets, config=cfg)
    except ValueError as e:
        return fail("ValueError", str(e), 1)
    except (OSError, json.JSONDecodeError) as e:
        return fail("RuntimeError", str(e), 2)

    write_output(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
