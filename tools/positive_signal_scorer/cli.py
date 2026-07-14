"""CLI for tools.positive_signal_scorer.

Reads patterns (--patterns) and traces (--traces) from files or stdin; optional
--dimension for single-dimension mode; --weights-* flags override defaults.
Writes JSON to --output or stdout.

    python -m tools.positive_signal_scorer \
        --patterns patterns.json --traces traces.jsonl --output scored.json
    python -m tools.positive_signal_scorer \
        --patterns patterns.json --traces traces.jsonl --dimension outcome_correlation
    python -m tools.positive_signal_scorer \
        --patterns patterns.json --traces traces.jsonl \
        --weights-outcome-correlation 0.5 --output scored.json

Exit codes: 0 success | 1 ValueError (bad input) | 2 RuntimeError (I/O).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .core import score_patterns, compute_signal_dimension
from .composite_scoring import DIMENSIONS

_WEIGHT_FLAGS = {d: f"weights_{d}" for d in DIMENSIONS}


def _load(path: Optional[str], raw: str):
    text = raw
    if path:
        if not os.path.exists(path):
            raise RuntimeError(f"file not found: {path}")
        with open(path, encoding="utf-8") as f:
            text = f.read()
    if not text.strip():
        return []
    text = text.strip()
    if text.lstrip().startswith("["):
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("input JSON must be a list")
        return data
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="positive_signal_scorer")
    p.add_argument("--patterns", default=None)
    p.add_argument("--traces", default=None)
    p.add_argument("--dimension", default=None, choices=DIMENSIONS)
    p.add_argument("--output", default=None)
    for d in DIMENSIONS:
        p.add_argument(f"--weights-{d.replace('_', '-')}", type=float, default=None)
    args = p.parse_args(argv)

    weights = {d: getattr(args, _WEIGHT_FLAGS[d]) for d in DIMENSIONS}
    weights = {d: v for d, v in weights.items() if v is not None} or None

    try:
        patterns = _load(args.patterns, _read_stdin("patterns", args.patterns))
        traces = _load(args.traces, _read_stdin("traces", args.traces))
        if args.dimension:
            result = compute_signal_dimension(patterns, traces, args.dimension)
        else:
            result = score_patterns(patterns, traces, weights)
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


def _read_stdin(name: str, path: Optional[str]) -> str:
    # When no --file is given, read that stream from stdin (only one stdin, so
    # patterns takes precedence, traces from stdin if patterns was a file).
    if path:
        return ""
    return sys.stdin.read()


if __name__ == "__main__":
    raise SystemExit(main())
