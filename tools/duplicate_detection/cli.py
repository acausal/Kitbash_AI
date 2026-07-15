"""CLI for tools.duplicate_detection.

Mode: detect (default). Reads a corpus (list of {id, tokens|text}) from --input,
writes JSON to --output or stdout. Exit 0/1/2.
"""
from __future__ import annotations

import argparse
import json
import sys

from tools.historical_common import base_argparse, load_input, write_output, fail, normalize_config
from .core import detect_duplicates


def main(argv=None) -> int:
    p = base_argparse("duplicate_detection")
    p.add_argument("--strategy", choices=["exact", "jaccard", "shingle", "minhash"], default="exact")
    p.add_argument("--threshold", type=float, default=None)
    p.add_argument("--keep-strategy", choices=["first", "shortest", "longest"], default="first")
    p.add_argument("--lowercase", action="store_true")
    p.add_argument("--remove-stopwords", action="store_true")
    args = p.parse_args(argv)

    try:
        data = load_input(args.input)
        cfg = dict(data.get("config") or {})
        if args.lowercase:
            cfg["lowercase"] = True
        if args.remove_stopwords:
            cfg["remove_stopwords"] = True
        cfg = normalize_config(cfg)
        corpus = data.get("corpus") or data.get("documents") or data.get("documents_list")
        if not isinstance(corpus, list):
            raise ValueError("missing 'corpus'/'documents' list")
        threshold = args.threshold if args.threshold is not None else cfg.get("threshold", 1.0)
        result = detect_duplicates(
            corpus, strategy=args.strategy, threshold=threshold,
            keep_strategy=args.keep_strategy, config=cfg,
        )
    except ValueError as e:
        return fail("ValueError", str(e), 1)
    except (OSError, json.JSONDecodeError) as e:
        return fail("RuntimeError", str(e), 2)

    write_output(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
