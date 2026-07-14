"""CLI for tools.anomaly_scorer.

Subcommands: detect-fp-spikes, detect-confidence-degradation,
detect-emerging-collisions, detect-trend-shifts, score-severity.

Input files are JSON. Output JSON to stdout. summary to stderr.
Exit: 0 success, 1 ValueError (bad input/format), 2 RuntimeError (I/O/processing).
"""

import argparse
import json
import sys

from .core import (
    detect_false_positive_rate_anomalies,
    detect_confidence_degradation,
    detect_emerging_collisions,
    detect_violation_trend_shifts,
    score_anomaly_severity,
)


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _emit(obj):
    json.dump(obj, sys.stdout, indent=2)
    sys.stdout.write("\n")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="anomaly_scorer", description="Detect anomalies in trace/Dream Bucket data")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("detect-fp-spikes")
    sp.add_argument("--grain-stats", required=True)
    sp.add_argument("--historical-baseline", required=True)
    sp.add_argument("--window-hours", type=int, default=4)

    sp = sub.add_parser("detect-confidence-degradation")
    sp.add_argument("--violation-timeline", required=True)
    sp.add_argument("--historical-baseline", required=True)

    sp = sub.add_parser("detect-emerging-collisions")
    sp.add_argument("--collision-index", required=True)
    sp.add_argument("--historical-collisions", required=True)
    sp.add_argument("--threshold", type=int, default=5)

    sp = sub.add_parser("detect-trend-shifts")
    sp.add_argument("--violation-timeline", required=True)
    sp.add_argument("--historical-trend", required=True)
    sp.add_argument("--window-days", type=int, default=1)

    sp = sub.add_parser("score-severity")
    sp.add_argument("--anomalies", required=True)
    sp.add_argument("--recency-weight", type=float, default=1.0)
    sp.add_argument("--reference-time", default=None)

    args = p.parse_args(argv)

    try:
        if args.command == "detect-fp-spikes":
            gs = _load_json(args.grain_stats)
            bl = _load_json(args.historical_baseline)
            result = detect_false_positive_rate_anomalies(gs, bl, args.window_hours)
        elif args.command == "detect-confidence-degradation":
            vt = _load_json(args.violation_timeline)
            bl = _load_json(args.historical_baseline)
            result = detect_confidence_degradation(vt, bl)
        elif args.command == "detect-emerging-collisions":
            ci = _load_json(args.collision_index)
            hc = _load_json(args.historical_collisions)
            result = detect_emerging_collisions(ci, hc, args.threshold)
        elif args.command == "detect-trend-shifts":
            vt = _load_json(args.violation_timeline)
            ht = _load_json(args.historical_trend)
            result = detect_violation_trend_shifts(vt, ht, args.window_days)
        elif args.command == "score-severity":
            anom = _load_json(args.anomalies)
            result = score_anomaly_severity(anom, args.recency_weight, args.reference_time)
    except ValueError as e:
        sys.stderr.write(f"ValueError: {e}\n")
        return 1
    except (OSError, RuntimeError) as e:
        sys.stderr.write(f"RuntimeError: {e}\n")
        return 2

    _emit(result)
    return 0
