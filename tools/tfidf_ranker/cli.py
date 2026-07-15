"""CLI for tools.tfidf_ranker.

Modes: rank (query + corpus, default), tfidf (emit vectors), similarity
(two vectors). Writes JSON to --output or stdout. Exit 0/1/2.
"""
from __future__ import annotations

import argparse
import json
import sys

from tools.historical_common import base_argparse, load_input, write_output, fail, normalize_config
from .core import rank_documents, compute_tfidf, cosine_similarity


def main(argv=None) -> int:
    p = base_argparse("tfidf_ranker")
    p.add_argument("--query", default=None, help="space-separated query (or 'query' field)")
    p.add_argument("--tfidf", action="store_true", help="emit per-doc TF-IDF vectors")
    p.add_argument("--similarity", action="store_true", help="cosine of two vector JSON inputs")
    p.add_argument("--tfidf-variant", choices=["standard", "sublinear", "bm25"], default=None)
    p.add_argument("--lowercase", action="store_true")
    p.add_argument("--remove-stopwords", action="store_true")
    args = p.parse_args(argv)

    try:
        data = load_input(args.input)
        cfg = dict(data.get("config") or {})
        if args.tfidf_variant: cfg["tfidf_variant"] = args.tfidf_variant
        if args.lowercase: cfg["lowercase"] = True
        if args.remove_stopwords: cfg["remove_stopwords"] = True
        cfg = normalize_config(cfg)
        if args.similarity:
            a = dict(data.get("vector_a") or {})
            b = dict(data.get("vector_b") or {})
            result = {"cosine_similarity": round(cosine_similarity(a, b), 6)}
        elif args.tfidf:
            corpus = data.get("corpus")
            if not isinstance(corpus, list):
                raise ValueError("missing 'corpus' list")
            result = compute_tfidf(corpus, cfg)
        else:
            query = args.query or data.get("query")
            if not query:
                raise ValueError("missing --query or 'query' field")
            corpus = data.get("corpus")
            if not isinstance(corpus, list):
                raise ValueError("missing 'corpus' list")
            result = rank_documents(query.split() if isinstance(query, str) else list(query),
                                    corpus, cfg)
    except ValueError as e:
        return fail("ValueError", str(e), 1)
    except (OSError, json.JSONDecodeError) as e:
        return fail("RuntimeError", str(e), 2)

    write_output(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
