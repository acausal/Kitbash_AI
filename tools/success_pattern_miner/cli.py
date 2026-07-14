"""CLI for tools.success_pattern_miner.

Reads traces from a file (--input) or stdin; dispatches on --pattern-type
(sequences|grains|mixed). Writes the run-result JSON to --output or stdout.

    python -m tools.success_pattern_miner --input traces.jsonl \
        --pattern-type sequences --min-frequency 3 --output patterns.json

Exit codes: 0 success | 1 ValueError (bad input/format) | 2 RuntimeError (I/O).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .core import (
    mine_success_tool_sequences,
    mine_success_grain_patterns,
    mine_mixed_success_patterns,
)
from .filtering import filter_success_traces

_DISPATCH = {
    "sequences": lambda t, mf, st, tw: mine_success_tool_sequences(
        t, min_frequency=mf, success_threshold=st, time_window_hours=tw),
    "grains": lambda t, mf, st, tw: mine_success_grain_patterns(
        t, min_frequency=mf, success_threshold=st),
    "mixed": lambda t, mf, st, tw: mine_mixed_success_patterns(
        t, min_frequency=mf, success_threshold=st),
}


def _load_traces(input_path: Optional[str], raw_stdin: str) -> list:
    text = raw_stdin
    if input_path:
        if not os.path.exists(input_path):
            raise RuntimeError(f"input file not found: {input_path}")
        with open(input_path, encoding="utf-8") as f:
            text = f.read()
    if not text.strip():
        return []
    text = text.strip()
    # JSONL (one trace per line) or a JSON array of traces.
    if text.lstrip().startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"invalid JSON array: {e}")
        if not isinstance(data, list):
            raise ValueError("input JSON must be an array of traces or JSONL")
        return data
    traces = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            traces.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise ValueError(f"invalid JSONL line: {e}")
    return traces


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="success_pattern_miner")
    p.add_argument("--input", default=None)
    p.add_argument("--pattern-type", required=True, choices=sorted(_DISPATCH))
    p.add_argument("--min-frequency", type=int, default=3)
    p.add_argument("--success-threshold", type=float, default=0.2)
    p.add_argument("--time-window-hours", type=int, default=None)
    p.add_argument("--output", default=None)
    args = p.parse_args(argv)

    try:
        traces = _load_traces(args.input, sys.stdin.read())
        result = _DISPATCH[args.pattern_type](
            traces, args.min_frequency, args.success_threshold,
            args.time_window_hours)
    except ValueError as e:
        sys.stderr.write(f"[error] {e}\n")
        return 1
    except RuntimeError as e:
        sys.stderr.write(f"[error] {e}\n")
        return 2

    if args.output:
        parent = os.path.dirname(args.output)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    else:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
