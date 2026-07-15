"""CLI for tools.inverted_index_builder.

Modes: build (default, from corpus), idf (from a {token: df} map),
add (merge one doc into an existing index), merge (combine multiple indexes).
Writes JSON to --output or stdout. Exit 0/1/2.
"""
from __future__ import annotations

import argparse
import json
import sys

from tools.historical_common import base_argparse, load_input, write_output, fail, normalize_config
from .core import build_index, compute_idf, add_document, merge_indexes


def main(argv=None) -> int:
    p = base_argparse("inverted_index_builder")
    p.add_argument("--idf", action="store_true", help="input is a {token: df} map")
    p.add_argument("--add", action="store_true", help="merge one doc into an existing index")
    p.add_argument("--merge", action="store_true", help="merge multiple index files")
    p.add_argument("--idf-scheme", choices=["standard", "log", "probabilistic"], default=None)
    p.add_argument("--lowercase", action="store_true")
    p.add_argument("--remove-stopwords", action="store_true")
    args = p.parse_args(argv)

    try:
        data = load_input(args.input)
        cfg = dict(data.get("config") or {})
        if args.idf_scheme: cfg["idf_scheme"] = args.idf_scheme
        if args.lowercase: cfg["lowercase"] = True
        if args.remove_stopwords: cfg["remove_stopwords"] = True
        cfg = normalize_config(cfg)
        if args.idf:
            df_map = dict(data.get("document_frequencies") or {})
            total = int(data.get("total_documents", 1))
            result = {"idf_values": compute_idf(df_map, total, cfg.get("idf_scheme", "standard"))}
        elif args.add:
            existing = dict(data.get("index_state") or {})
            doc = data.get("document")
            if not isinstance(doc, dict):
                raise ValueError("add mode requires 'document'")
            result = add_document(existing, doc, cfg)
        elif args.merge:
            indexes = data.get("indexes")
            if not isinstance(indexes, list):
                raise ValueError("merge mode requires 'indexes' list")
            result = merge_indexes(indexes, cfg)
        else:
            corpus = data.get("corpus")
            if not isinstance(corpus, list):
                raise ValueError("missing 'corpus' list (or use --idf/--merge)")
            result = build_index(corpus, cfg)
    except ValueError as e:
        return fail("ValueError", str(e), 1)
    except (OSError, json.JSONDecodeError) as e:
        return fail("RuntimeError", str(e), 2)

    write_output(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
