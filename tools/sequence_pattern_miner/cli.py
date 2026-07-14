"""CLI for tools.sequence_pattern_miner.

Multi-command: read a JSON object from stdin, dispatch on the first CLI arg,
merge typed flags over the payload, write JSON to stdout.

    echo '{"traces":[...]}' | python -m tools.sequence_pattern_miner extract_ngrams --n 2
    echo '{"sequences":[...]}' | python -m tools.sequence_pattern_miner filter_sequences --min_frequency 3

Exit codes: 0 success | 1 ValueError (bad input) | 2 RuntimeError (internal).
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import (
    extract_ngrams,
    extract_ngrams_by_length,
    filter_sequences,
    rank_sequences_by_element_type,
    sequences_to_markov_transitions,
)

_COMMANDS = {
    "extract_ngrams": lambda p: extract_ngrams(
        p.get("traces", []), n=p.get("n", 2),
        min_frequency=p.get("min_frequency", 1), chain_filter=p.get("chain_filter")),
    "extract_ngrams_by_length": lambda p: extract_ngrams_by_length(
        p.get("traces", []), min_n=p.get("min_n", 1),
        max_n=p.get("max_n", 4), min_frequency=p.get("min_frequency", 1)),
    "filter_sequences": lambda p: filter_sequences(
        p.get("sequences", []), min_frequency=p.get("min_frequency", 1),
        max_frequency=p.get("max_frequency")),
    "rank_sequences_by_element_type": lambda p: rank_sequences_by_element_type(
        p.get("sequences", [])),
    "sequences_to_markov_transitions": lambda p: sequences_to_markov_transitions(
        p.get("sequences", [])),
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="sequence_pattern_miner",
        description="Mine frequent n-gram sequences from execution traces (v1).",
    )
    parser.add_argument("command", choices=sorted(_COMMANDS))
    parser.add_argument("--n", type=int)
    parser.add_argument("--min_n", type=int)
    parser.add_argument("--max_n", type=int)
    parser.add_argument("--min_frequency", type=int)
    parser.add_argument("--max_frequency", type=int)
    parser.add_argument("--chain_filter")
    args = parser.parse_args(argv)
    cmd = args.command

    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}), file=sys.stderr)
        return 1
    if not isinstance(payload, dict):
        print(json.dumps({"error": "input JSON must be an object"}), file=sys.stderr)
        return 1

    # typed flags override payload values when provided
    for key in ("n", "min_n", "max_n", "min_frequency", "max_frequency", "chain_filter"):
        val = getattr(args, key)
        if val is not None:
            payload[key] = val

    try:
        result = _COMMANDS[cmd](payload)
    except ValueError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2
    except (KeyError, TypeError) as e:
        print(json.dumps({"error": f"invalid arguments: {e}"}), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
