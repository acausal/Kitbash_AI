"""CLI for tools.pattern_explainer.

Subcommands: explain-cluster, explain-anomaly, explain-pattern,
explain-patterns, generate-sleep-report. Inputs are JSON files. Output
JSON to stdout; summary to stderr. Exit 0/1/2.
"""
import argparse
import json
import sys

from .core import (
    explain_collision_cluster,
    explain_anomaly,
    explain_pattern_reliability,
    explain_multiple_patterns,
    generate_sleep_report,
)


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as e:
        raise RuntimeError(f"input file not found: {path}") from e
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(f"failed to read {path}: {e}") from e


def _emit(obj):
    json.dump(obj, sys.stdout, indent=2)
    sys.stdout.write("\n")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="tools.pattern_explainer", description="Explain patterns/anomalies in plain language")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("explain-cluster")
    pc.add_argument("--cluster", required=True)
    pc.add_argument("--collision-index", default=None)

    pa = sub.add_parser("explain-anomaly")
    pa.add_argument("--anomaly", required=True)
    pa.add_argument("--baseline", default=None)

    pp = sub.add_parser("explain-pattern")
    pp.add_argument("--pattern", required=True)
    pp.add_argument("--confidence-scores", required=True)

    pps = sub.add_parser("explain-patterns")
    pps.add_argument("--patterns", required=True)
    pps.add_argument("--confidence-scores", required=True)
    pps.add_argument("--summary-style", default="brief", choices=["brief", "summary", "detailed"])

    pr = sub.add_parser("generate-sleep-report")
    pr.add_argument("--collision-clusters", default=None)
    pr.add_argument("--anomalies", default=None)
    pr.add_argument("--patterns", default=None)
    pr.add_argument("--confidence-scores", default=None)

    args = p.parse_args(argv)
    try:
        if args.cmd == "explain-cluster":
            idx = _load_json(args.collision_index) if args.collision_index else None
            result = explain_collision_cluster(_load_json(args.cluster), idx)
        elif args.cmd == "explain-anomaly":
            base = _load_json(args.baseline) if args.baseline else None
            result = explain_anomaly(_load_json(args.anomaly), base)
        elif args.cmd == "explain-pattern":
            result = explain_pattern_reliability(
                _load_json(args.pattern), _load_json(args.confidence_scores))
        elif args.cmd == "explain-patterns":
            plist = _load_json(args.patterns)
            slist = _load_json(args.confidence_scores)
            result = explain_multiple_patterns(plist, slist, args.summary_style)
        elif args.cmd == "generate-sleep-report":
            c = _load_json(args.collision_clusters) if args.collision_clusters else None
            a = _load_json(args.anomalies) if args.anomalies else None
            pt = _load_json(args.patterns) if args.patterns else None
            s = _load_json(args.confidence_scores) if args.confidence_scores else None
            result = generate_sleep_report(
                clusters=c or [], anomalies=a or [], patterns=pt or [], scores=s or [])
        else:  # pragma: no cover
            p.error(f"unknown command: {args.cmd}")
            return 2
    except ValueError as e:
        sys.stderr.write(f"[ValueError] {e}\n")
        return 1
    except RuntimeError as e:
        sys.stderr.write(f"[RuntimeError] {e}\n")
        return 2
    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
