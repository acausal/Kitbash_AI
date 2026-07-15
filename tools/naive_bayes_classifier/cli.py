"""CLI for tools.naive_bayes_classifier.

Modes: train (default, from corpus), classify, batch, evaluate.
Writes JSON to --output or stdout. Exit 0/1/2.
"""
from __future__ import annotations

import argparse
import json
import sys

from tools.historical_common import base_argparse, load_input, write_output, fail, normalize_config
from .core import train_classifier, classify, batch_classify, evaluate_classifier


def main(argv=None) -> int:
    p = base_argparse("naive_bayes_classifier")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--train", action="store_true")
    g.add_argument("--classify", action="store_true")
    g.add_argument("--batch", action="store_true")
    g.add_argument("--evaluate", action="store_true")
    p.add_argument("--feature-type", choices=["bernoulli", "multinomial"], default=None)
    p.add_argument("--smoothing", default=None)
    p.add_argument("--lowercase", action="store_true")
    p.add_argument("--remove-stopwords", action="store_true")
    args = p.parse_args(argv)

    try:
        data = load_input(args.input)
        cfg = dict(data.get("config") or {})
        if args.lowercase: cfg["lowercase"] = True
        if args.remove_stopwords: cfg["remove_stopwords"] = True
        cfg = normalize_config(cfg)
        ft = args.feature_type or cfg.get("feature_type", "bernoulli")
        smoothing = args.smoothing or cfg.get("smoothing", "laplace")
        if args.train:
            corpus = data.get("corpus") or data.get("training_corpus")
            if not isinstance(corpus, list):
                raise ValueError("missing 'corpus'/'training_corpus' list")
            result = train_classifier(corpus, feature_type=ft, smoothing=smoothing, config=cfg)
        elif args.classify:
            model = dict(data.get("model") or {})
            doc = data.get("document")
            if not isinstance(doc, dict):
                raise ValueError("missing 'document'")
            result = classify(model, doc)
        elif args.batch:
            model = dict(data.get("model") or {})
            docs = data.get("documents") or data.get("corpus")
            if not isinstance(docs, list):
                raise ValueError("missing 'documents' list")
            result = batch_classify(model, docs)
        else:
            model = dict(data.get("model") or {})
            test = data.get("test_corpus") or data.get("corpus")
            if not isinstance(test, list):
                raise ValueError("missing 'test_corpus' list")
            result = evaluate_classifier(model, test)
    except ValueError as e:
        return fail("ValueError", str(e), 1)
    except (OSError, json.JSONDecodeError) as e:
        return fail("RuntimeError", str(e), 2)

    write_output(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
