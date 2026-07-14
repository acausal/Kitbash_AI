"""CLI for tools.causal_credit_attribution.

Single trace: --trace [--patterns --historical --tool-metadata --weights-*]
Batch:       --traces --batch [--patterns --historical --weights-*]
Writes JSON to --output or stdout. Exit 0/1/2 (success/ValueError/RuntimeError).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .core import attribute_credit_to_tools, attribute_credit_to_grains, batch_attribute_credit
from .heuristic_aggregation import SIGNAL_KEYS

_WEIGHT_FLAGS = {s: f"weights_{s}" for s in SIGNAL_KEYS}


def _load(path: Optional[str], raw: str):
    text = raw
    if path:
        if not os.path.exists(path):
            raise RuntimeError(f"file not found: {path}")
        with open(path, encoding="utf-8") as f:
            text = f.read()
    text = (text or "").strip()
    if not text:
        return []
    if text.lstrip().startswith("["):
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("input JSON must be a list")
        return data
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="causal_credit_attribution")
    p.add_argument("--trace", default=None)
    p.add_argument("--traces", default=None)
    p.add_argument("--patterns", default=None)
    p.add_argument("--historical", default=None)
    p.add_argument("--tool-metadata", default=None)
    p.add_argument("--batch", action="store_true")
    p.add_argument("--output", default=None)
    for s in SIGNAL_KEYS:
        p.add_argument(f"--{s.replace('_', '-')}", dest=_WEIGHT_FLAGS[s], type=float, default=None)
    p.add_argument("--grain", action="store_true",
                   help="attribute credit to grain_activations instead of sequence")
    args = p.parse_args(argv)

    weights = {s: getattr(args, _WEIGHT_FLAGS[s]) for s in SIGNAL_KEYS}
    weights = {s: v for s, v in weights.items() if v is not None} or None

    def _stdin(name):
        return sys.stdin.read() if not getattr(args, name) else ""

    try:
        patterns = _load(args.patterns, "" ) if args.patterns else []
        hist = _load(args.historical, "") if args.historical else None
        tmeta = json.load(open(args.tool_metadata, encoding="utf-8")) if args.tool_metadata else None
        if args.batch or args.traces:
            traces = _load(args.traces, _stdin("traces"))
            result = batch_attribute_credit(traces, patterns, hist, weights)
        else:
            trace = _load(args.trace, _stdin("trace"))
            if not isinstance(trace, list):
                trace = [trace]
            if len(trace) != 1:
                raise ValueError("--trace expects exactly one trace object")
            trace = trace[0]
            if args.grain:
                result = attribute_credit_to_grains(trace, None, hist, weights)
            else:
                result = attribute_credit_to_tools(trace, patterns, hist, weights, tmeta)
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
