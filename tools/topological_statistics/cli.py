"""CLI for tools.topological_statistics.

Modes: --degree / --clustering / --paths / --centrality / --components (mutually
exclusive, required). Reads a graph JSON from --input; writes JSON to --output or
stdout. Exit 0/1/2.
"""
from __future__ import annotations

import argparse
import json
import sys

from tools.historical_common import base_argparse, load_input, write_output, fail, normalize_config
from .core import (
    compute_degree_stats, compute_clustering_coefficients, compute_path_lengths,
    compute_centrality, analyze_components,
)


def main(argv=None) -> int:
    p = base_argparse("topological_statistics")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--degree", action="store_true")
    g.add_argument("--clustering", action="store_true")
    g.add_argument("--paths", action="store_true")
    g.add_argument("--centrality", action="store_true")
    g.add_argument("--components", action="store_true")
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
        if args.degree:
            result = compute_degree_stats(data, config=cfg)
        elif args.clustering:
            result = compute_clustering_coefficients(data, config=cfg)
        elif args.paths:
            result = compute_path_lengths(data, config=cfg)
        elif args.centrality:
            result = compute_centrality(data, config=cfg)
        else:
            result = analyze_components(data, config=cfg)
    except ValueError as e:
        return fail("ValueError", str(e), 1)
    except (OSError, json.JSONDecodeError) as e:
        return fail("RuntimeError", str(e), 2)

    write_output(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
