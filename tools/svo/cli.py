"""CLI for tools.svo.

    python -m tools.svo input.txt [-o out.json]

Reads text from a file, extracts SVO triples, writes a JSON object
{svos, svo_count, with_subject, with_object} to the output file or stdout, and
a summary line to stderr. Exit 0 on success, 1 on failure.
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import extract_svo


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="svo",
        description="Extract subject-verb-object triples with spaCy (v1).",
    )
    parser.add_argument("input", help="path to input text file")
    parser.add_argument("-o", "--output", default=None,
                        help="write JSON to this file (default: stdout)")
    args = parser.parse_args(argv)

    try:
        with open(args.input, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        print(f"error: cannot read input {args.input}: {e}", file=sys.stderr)
        return 1

    try:
        triples = extract_svo(text)
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    n_subj = sum(1 for s in triples if s.subject)
    n_obj = sum(1 for s in triples if s.obj)
    payload = {
        "svos": [s.to_dict() for s in triples],
        "svo_count": len(triples),
        "with_subject": n_subj,
        "with_object": n_obj,
    }
    out_json = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(out_json)
        except OSError as e:
            print(f"error: cannot write output {args.output}: {e}", file=sys.stderr)
            return 1
    else:
        print(out_json, file=sys.stdout)

    print(f"Extracted {len(triples)} SVO triples from {args.input} "
          f"({n_subj} with subjects, {n_obj} with objects)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
