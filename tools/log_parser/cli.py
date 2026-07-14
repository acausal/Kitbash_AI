"""CLI for tools.log_parser.

Multi-command: read JSON/JSONL from stdin (or --input file), dispatch on the
first CLI arg (command name), write JSON to stdout (or --output file).

    cat traces.jsonl | python -m tools.log_parser parse_jsonl_traces
    echo '{"query_id":"q1","chain":[...],"chain_type":"intra_query"}' \
      | python -m tools.log_parser parse_json_trace
    python -m tools.log_parser parse_jsonl_traces --input t.jsonl \
      --filter '{"min_chain_length":2}' --aggregate

Exit codes: 0 success | 1 ValueError (bad input) | 2 FileNotFoundError |
3 RuntimeError (internal).
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import (
    aggregate_chains,
    extract_chain_steps,
    filter_traces,
    parse_json_trace,
    parse_jsonl_traces,
    normalize_trace,
)

# stdin-payload commands: fn(**payload)
_PAYLOAD_COMMANDS = {
    "parse_json_trace": lambda p: parse_json_trace(p["json_str"]) if "json_str" in p
        else normalize_trace(p),
    "filter_traces": lambda p: filter_traces(p.get("traces", []), p.get("filters", {})),
    "aggregate_chains": lambda p: aggregate_chains(p.get("traces", [])),
    "extract_chain_steps": lambda p: extract_chain_steps(p.get("traces", [])),
    "normalize_trace": lambda p: normalize_trace(p.get("trace", p)),
}
# raw-text command (JSONL, not a JSON object)
_TEXT_COMMANDS = {"parse_jsonl_traces"}
_ALL = sorted(_TEXT_COMMANDS | set(_PAYLOAD_COMMANDS))


def _read_input(args) -> str:
    if args.input:
        try:
            with open(args.input, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"input file not found: {args.input}")
    return sys.stdin.read()


def _write_output(args, result) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text, file=sys.stdout)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="log_parser",
        description="Parse/normalize execution traces for pattern mining (v1).",
    )
    parser.add_argument("command", choices=_ALL, help="subcommand to run")
    parser.add_argument("--input", help="read from file instead of stdin")
    parser.add_argument("--output", help="write to file instead of stdout")
    parser.add_argument("--filter", help="JSON filter criteria (parse_jsonl_traces chaining)")
    parser.add_argument("--aggregate", action="store_true",
                        help="aggregate chains after parse/filter (parse_jsonl_traces chaining)")
    args = parser.parse_args(argv)
    cmd = args.command

    try:
        raw = _read_input(args)
    except FileNotFoundError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2

    try:
        if cmd in _TEXT_COMMANDS:
            result = parse_jsonl_traces(raw)
            traces = result["traces"]
            if args.filter:
                try:
                    filters = json.loads(args.filter)
                except json.JSONDecodeError as e:
                    raise ValueError(f"invalid --filter JSON: {e}")
                fr = filter_traces(traces, filters)
                traces = fr["traces"]
                result["filter_report"] = {k: v for k, v in fr.items() if k != "traces"}
                result["traces"] = traces
            if args.aggregate:
                result["aggregation"] = aggregate_chains(traces)
        else:
            try:
                payload = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError as e:
                # parse_json_trace treats raw as the JSON trace itself
                if cmd == "parse_json_trace":
                    raise ValueError(f"JSON parse failed: {e}")
                raise ValueError(f"Invalid JSON input: {e}")
            if not isinstance(payload, dict):
                raise ValueError("input JSON must be an object")
            result = _PAYLOAD_COMMANDS[cmd](payload)
    except ValueError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    except KeyError as e:
        print(json.dumps({"error": f"missing field: {e}"}), file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 3

    try:
        _write_output(args, result)
    except OSError as e:
        print(json.dumps({"error": f"output write failed: {e}"}), file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
