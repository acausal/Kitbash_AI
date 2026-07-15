"""CLI for tools.multispectral_analyzer.

Modes: takes --data (or --input for a data file), --data-type (text/json/log),
--spectrum-config (JSON), --detect-divergence (bool), --output (canonical) with
--output-json alias (spec said --output-json; project convention keeps --output).

Reads from --input file or stdin; writes JSON to --output or stdout. Envelope via
historical_common. Exit 0 ok, 1 on error, 2 on usage error.
"""
from __future__ import annotations

import argparse
import json
import sys

from tools.historical_common import base_argparse, load_input, write_output, fail


def main(argv=None) -> int:
    ap = base_argparse("multispectral_analyzer")
    ap.add_argument("--data", help="data string to analyze (alternative to --input)")
    ap.add_argument("--data-type", default="text", choices=["text", "json", "log"])
    ap.add_argument("--spectrum-config", help="JSON: {\"enabled\":[...],\"disabled\":[...]}")
    ap.add_argument("--detect-divergence", default="true", choices=["true", "false"])
    ap.add_argument("--output", help="write result JSON here (canonical)")
    ap.add_argument("--output-json", help="alias for --output")
    args = ap.parse_args(argv)

    out_path = args.output or args.output_json

    # Resolve data: explicit --data > --input file > stdin
    if args.data is not None:
        data = args.data
    else:
        if args.input:
            try:
                with open(args.input, "r", encoding="utf-8") as fh:
                    data = fh.read()
            except OSError as e:
                return fail("IOError", f"cannot read --input {args.input}: {e}", 1)
        else:
            data = sys.stdin.read()

    try:
        cfg = json.loads(args.spectrum_config) if args.spectrum_config else None
    except json.JSONDecodeError as e:
        return fail("ValueError", f"invalid --spectrum-config JSON: {e}", 2)

    try:
        from .core import analyze_multispectral
        result = analyze_multispectral(
            data=data,
            data_type=args.data_type,
            spectrum_config=cfg,
            detect_divergence=(args.detect_divergence == "true"),
        )
    except ValueError as e:
        return fail("ValueError", str(e), 2)
    except Exception as e:  # noqa: BLE001
        return fail(type(e).__name__, str(e), 1)

    write_output(result, out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
