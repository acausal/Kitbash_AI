"""CLI for tools.conditional_pattern_detector.

Each command reads its payload JSON from stdin (with 'traces' or 'patterns' /
'seed_conditions' / 'patterns' keys) and writes JSON to stdout.

    echo '{"traces":[...]}' | python -m tools.conditional_pattern_detector detect_conditional_patterns --min_support 2 --min_confidence 0.5
    echo '{"traces":[...],"seed_conditions":[{"type":"chain_length","operator":">=","value":3}]}' | python -m tools.conditional_pattern_detector detect_seeded_patterns
    echo '{"traces":[...]}' | python -m tools.conditional_pattern_detector extract_decision_trees --depth 2
    echo '{"patterns":[...]}' | python -m tools.conditional_pattern_detector filter_patterns --min_confidence 0.7 --min_lift 1.2
    echo '{"patterns":[...]}' | python -m tools.conditional_pattern_detector rank_patterns_by_metric --metric lift

Exit codes: 0 success | 1 ValueError (bad input) | 2 RuntimeError (internal).
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import (
    detect_conditional_patterns,
    detect_seeded_patterns,
    extract_decision_trees,
    filter_patterns,
    rank_patterns_by_metric,
)

_COMMANDS = (
    "detect_conditional_patterns",
    "detect_seeded_patterns",
    "extract_decision_trees",
    "filter_patterns",
    "rank_patterns_by_metric",
)


def _payload(args) -> dict:
    raw = sys.stdin.read()
    try:
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON input: {e}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="conditional_pattern_detector",
        description="Association-rule + shallow decision-tree discovery (v1).",
    )
    parser.add_argument("command", choices=_COMMANDS)
    parser.add_argument("--min_support", type=int, default=2)
    parser.add_argument("--min_confidence", type=float, default=0.5)
    parser.add_argument("--min_lift", type=float, default=1.0)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--metric", default="confidence")
    args = parser.parse_args(argv)

    try:
        p = _payload(args)
        cmd = args.command
        if cmd == "detect_conditional_patterns":
            result = detect_conditional_patterns(
                p.get("traces", []), min_support=args.min_support,
                min_confidence=args.min_confidence)
        elif cmd == "detect_seeded_patterns":
            result = detect_seeded_patterns(
                p.get("traces", []), p.get("seed_conditions", []),
                min_support=args.min_support)
        elif cmd == "extract_decision_trees":
            result = extract_decision_trees(p.get("traces", []), depth=args.depth)
        elif cmd == "filter_patterns":
            result = filter_patterns(
                p.get("patterns", []), args.min_confidence, args.min_lift)
        elif cmd == "rank_patterns_by_metric":
            result = rank_patterns_by_metric(p.get("patterns", []), metric=args.metric)
        else:
            raise ValueError(f"unknown command: {cmd}")
    except ValueError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
