"""CLI for tools.frequency_analysis.

Modes: stream (default), corpus (--corpus), coverage (--compute-coverage),
histogram (--histogram). Writes JSON to --output or stdout. Exit 0/1/2.
"""
from __future__ import annotations

import argparse
import json
import sys

from tools.historical_common import base_argparse, load_input, write_output, fail, normalize_config
from .core import (analyze_frequencies, analyze_corpus_frequencies,
                   compute_coverage, frequency_histogram)


def main(argv=None) -> int:
    p = base_argparse("frequency_analysis")
    p.add_argument("--corpus", action="store_true", help="treat input as a document corpus")
    p.add_argument("--compute-coverage", action="store_true")
    p.add_argument("--coverage-threshold", type=float, default=0.8)
    p.add_argument("--histogram", action="store_true")
    p.add_argument("--top-k", type=int, default=None)
    p.add_argument("--bottom-k", type=int, default=None)
    p.add_argument("--lowercase", action="store_true")
    p.add_argument("--remove-stopwords", action="store_true")
    args = p.parse_args(argv)

    try:
        data = load_input(args.input)
        cfg = dict(data.get("config") or {})
        if args.top_k is not None: cfg["top_k"] = args.top_k
        if args.bottom_k is not None: cfg["bottom_k"] = args.bottom_k
        if args.lowercase: cfg["lowercase"] = True
        if args.remove_stopwords: cfg["remove_stopwords"] = True
        cfg = normalize_config(cfg)
        if args.compute_coverage:
            freqs = dict(data.get("frequencies") or {})
            result = compute_coverage(freqs, args.coverage_threshold)
        elif args.histogram:
            freqs = dict(data.get("frequencies") or {})
            result = frequency_histogram(freqs)
        elif args.corpus:
            corpus = data.get("corpus")
            if not isinstance(corpus, list):
                raise ValueError("corpus mode requires 'corpus' list")
            result = analyze_corpus_frequencies(corpus, cfg)
        else:
            tokens = data.get("tokens")
            if not isinstance(tokens, list):
                raise ValueError("missing 'tokens' list (or use --corpus)")
            result = analyze_frequencies(tokens, cfg)
    except ValueError as e:
        return fail("ValueError", str(e), 1)
    except (OSError, json.JSONDecodeError) as e:
        return fail("RuntimeError", str(e), 2)

    write_output(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
