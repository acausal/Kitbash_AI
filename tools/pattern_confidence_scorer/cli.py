"""CLI for tools.pattern_confidence_scorer.

Subcommands: score-traces, score-dream-bucket, compare, decay. Patterns are
read from a JSON file (list of pattern dicts). Traces / dream-bucket are JSONL
or JSON. All print one JSON object to stdout.

    python -m tools.pattern_confidence_scorer score-traces \
        --patterns patterns.json --traces traces.jsonl --pattern-type sequence
    python -m tools.pattern_confidence_scorer score-dream-bucket \
        --patterns patterns.json --dream-bucket db.jsonl --pattern-type collision
    python -m tools.pattern_confidence_scorer compare \
        --patterns patterns.json --traces traces.jsonl --dream-bucket db.jsonl
    python -m tools.pattern_confidence_scorer decay \
        --scores scored.json --decay-factor 0.99 --reference-date 2026-07-14

Exit codes: 0 success | 1 ValueError | 2 FileNotFoundError / OSError / RuntimeError.
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import (
    score_patterns_against_traces, score_patterns_against_dream_bucket,
    compare_pattern_reliability, decay_confidence_by_age,
)


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _load_patterns(path: str):
    data = _load_json(path)
    if isinstance(data, dict) and "patterns" in data:
        return data["patterns"]
    return data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="pattern_confidence_scorer",
        description="Score discovered patterns vs. outcomes (precision/recall/F1).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_tr = sub.add_parser("score-traces")
    p_tr.add_argument("--patterns", required=True)
    p_tr.add_argument("--traces", required=True)
    p_tr.add_argument("--pattern-type", default="sequence")

    p_db = sub.add_parser("score-dream-bucket")
    p_db.add_argument("--patterns", required=True)
    p_db.add_argument("--dream-bucket", required=True)
    p_db.add_argument("--pattern-type", default="sequence")

    p_cmp = sub.add_parser("compare")
    p_cmp.add_argument("--patterns", required=True)
    p_cmp.add_argument("--traces", default=None)
    p_cmp.add_argument("--dream-bucket", default=None)
    p_cmp.add_argument("--pattern-type", default="sequence")

    p_decay = sub.add_parser("decay")
    p_decay.add_argument("--scores", required=True)
    p_decay.add_argument("--decay-factor", type=float, default=0.99)
    p_decay.add_argument("--reference-date", default=None)

    args = parser.parse_args(argv)

    try:
        if args.command == "score-traces":
            patterns = _load_patterns(args.patterns)
            traces = _load_jsonl(args.traces)
            result = score_patterns_against_traces(
                patterns, traces, args.pattern_type)
        elif args.command == "score-dream-bucket":
            patterns = _load_patterns(args.patterns)
            result = score_patterns_against_dream_bucket(
                patterns, args.dream_bucket, args.pattern_type)
        elif args.command == "compare":
            patterns = _load_patterns(args.patterns)
            traces = _load_jsonl(args.traces) if args.traces else None
            result = compare_pattern_reliability(
                patterns, args.traces, args.dream_bucket, args.pattern_type)
        elif args.command == "decay":
            scores = _load_json(args.scores)
            result = decay_confidence_by_age(
                scores, args.decay_factor, args.reference_date)
        else:
            parser.error(f"unknown command: {args.command}")
            return 2
    except ValueError as e:
        print(json.dumps({"error": str(e), "error_type": "ValueError"}), file=sys.stderr)
        return 1
    except (FileNotFoundError, OSError, RuntimeError) as e:
        print(json.dumps({"error": str(e), "error_type": type(e).__name__}), file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
