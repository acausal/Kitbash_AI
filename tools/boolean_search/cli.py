"""CLI for tools.boolean_search.

Modes: search (default, query + corpus), parse (query only).
Writes JSON to --output or stdout. Exit 0/1/2.
"""
from __future__ import annotations

import argparse
import json
import sys

from tools.historical_common import base_argparse, load_input, write_output, fail, normalize_config
from .core import search, parse_query


def main(argv=None) -> int:
    p = base_argparse("boolean_search")
    p.add_argument("--query", default=None, help="boolean query string (or in input JSON)")
    p.add_argument("--parse", action="store_true", help="parse only (no corpus needed)")
    p.add_argument("--lowercase", action="store_true")
    p.add_argument("--remove-stopwords", action="store_true")
    args = p.parse_args(argv)

    try:
        data = load_input(args.input)
        cfg = dict(data.get("config") or {})
        if args.lowercase: cfg["lowercase"] = True
        if args.remove_stopwords: cfg["remove_stopwords"] = True
        cfg = normalize_config(cfg)
        query = args.query or data.get("query")
        if not query:
            raise ValueError("missing --query or 'query' field")
        if args.parse:
            result = parse_query(query, cfg)
        else:
            corpus = data.get("corpus")
            if not isinstance(corpus, list):
                raise ValueError("missing 'corpus' list (or use --parse)")
            result = search(query, corpus, cfg)
    except ValueError as e:
        return fail("ValueError", str(e), 1)
    except (OSError, json.JSONDecodeError) as e:
        return fail("RuntimeError", str(e), 2)

    write_output(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
