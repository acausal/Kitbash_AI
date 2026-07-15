"""CLI for tools.relevance_gate.

Usage:
  python -m tools.relevance_gate --query "..." --context "..." \
      --candidates candidates.json [--weights w.json] [--top-k 3] --output result.json
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(prog="relevance_gate", description="Deterministic query-time relevance filter.")
    ap.add_argument("--query", required=True)
    ap.add_argument("--context", default="")
    ap.add_argument("--candidates", required=True, help="JSON file: [{\"id\",\"text\"}]")
    ap.add_argument("--weights", default=None, help="JSON file: {lexical,similarity_bucket,entity_overlap,structural_overlap}")
    ap.add_argument("--top-k", type=int, default=None, dest="top_k")
    ap.add_argument("--output", default=None, help="Write result JSON here (or stdout)")
    args = ap.parse_args(list(argv) if argv is not None else None)

    with open(args.candidates, "r", encoding="utf-8") as f:
        candidates = json.load(f)
    weights = None
    if args.weights:
        with open(args.weights, "r", encoding="utf-8") as f:
            weights = json.load(f)

    result = apply_relevance_gate(args.query, args.context, candidates, weights, args.top_k)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
