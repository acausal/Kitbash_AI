"""CLI for tools.ner.

    python -m tools.ner input.txt [--labels PERSON,ORG] [--output out.json]

Reads text from a file, extracts named entities, writes a JSON object
{entities, entity_count, label_counts} to the output file or stdout, and a
summary line to stderr. Exit 0 on success, 1 on failure.
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import extract_entities


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="ner",
        description="Extract named entities with spaCy (v1).",
    )
    parser.add_argument("input", help="path to input text file")
    parser.add_argument("-l", "--labels", default=None,
                        help="comma-separated entity labels to keep (e.g. PERSON,ORG)")
    parser.add_argument("-o", "--output", default=None,
                        help="write JSON to this file (default: stdout)")
    args = parser.parse_args(argv)

    try:
        with open(args.input, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        print(f"error: cannot read input {args.input}: {e}", file=sys.stderr)
        return 1

    labels = [x.strip() for x in args.labels.split(",") if x.strip()] if args.labels else None
    try:
        entities = extract_entities(text, labels=labels)
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    label_counts: dict = {}
    for e in entities:
        label_counts[e.label] = label_counts.get(e.label, 0) + 1
    payload = {
        "entities": [e.to_dict() for e in entities],
        "entity_count": len(entities),
        "label_counts": label_counts,
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

    breakdown = ", ".join(f"{n} {lbl}" for lbl, n in sorted(label_counts.items()))
    summary = f"Extracted {len(entities)} entities from {args.input}"
    if breakdown:
        summary += f" ({breakdown})"
    print(summary, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
