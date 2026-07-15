"""Error categorization for microspecialist selection (redesign on REAL schema).

Roadmap Phase A data analysis / PIPELINE-ERROR_CATEGORIZATION_FOR_SPECIALISTS.md.

WHY A REDESIGN (grounded audit, 2026-07-15):
The spec assumes violations carry a natural-language `user_complaint` and a
`context_at_failure` / `grain_confidence`, and that we can call
`tools.log_parser` / `tools.conditional_pattern_detector` / `tools.pattern_explainer`
/ `text_search.match_any`. NONE of that exists:
  - Real violation record (dream_bucket.log_consistency_violation) is
    {type, source_layer, returned_fact_id, returned_confidence,
     mtr_error_signal, mtr_state_time, dissonance_type, context, session_id}.
  - Synthetic generator (generate_synthetic_dream_bucket.py) writes a *similar
    but not identical* record: {timestamp, returned_fact_id, returned_confidence,
    mtr_error_signal, dissonance_type, session_id} (no type/source_layer/context).
  - The three tools + text_search.match_any do not exist.

So we categorize on the fields the data ACTUALLY carries — never on a
user_complaint that isn't there. The spec's 8 natural-language categories
(coreference, sense ambiguity, ...) require complaint text we do not have and
are DROPPED. We use coherence/confidence-based categories derived from real
signals, which is honest given the schema.

This module reads violations via the REAL DreamBucketReader (live or any dir),
classifies, counts, and emits a recommendation report. Pure stdlib + dream_bucket.

Usage:
    python error_categorizer.py --dream-bucket data/subconscious/dream_bucket
    python error_categorizer.py --input violations.jsonl   # raw jsonl instead
"""
from __future__ import annotations

import sys
import json
import argparse
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


# Real-schema category rules. Each function takes the violation record dict and
# returns True if it matches. Order matters: first match wins.
def _is_high_conf_low_coh(v: Dict[str, Any]) -> bool:
    return v.get("dissonance_type") == "high_confidence_low_coherence"

def _is_context_switch_failure(v: Dict[str, Any]) -> bool:
    return v.get("dissonance_type") == "context_switch_failure"

def _is_incoherent_response(v: Dict[str, Any]) -> bool:
    return v.get("dissonance_type") == "incoherent_response"

def _is_confidence_mismatch(v: Dict[str, Any]) -> bool:
    # Confident, but MTR's error signal says it was wrong -> confidence not
    # backed by coherence.
    conf = v.get("returned_confidence", 0.0) or 0.0
    err = v.get("mtr_error_signal", 0.0) or 0.0
    return conf >= 0.8 and err >= 0.4

def _is_low_confidence(v: Dict[str, Any]) -> bool:
    return (v.get("returned_confidence", 1.0) or 1.0) < 0.5

# Order: most-specific dissonance_type first, then derived signals, then fallbacks.
_CATEGORY_RULES: List[tuple] = [
    ("high_confidence_low_coherence", _is_high_conf_low_coh),
    ("context_switch_failure", _is_context_switch_failure),
    ("incoherent_response", _is_incoherent_response),
    ("confidence_mismatch", _is_confidence_mismatch),
    ("low_confidence_violation", _is_low_confidence),
]

# Map a category -> the microspecialist it argues for building. Honest: only
# the categories we can actually detect get a recommendation; unmapped ones
# point at "richer violation data needed".
SPECIALIST_MAP = {
    "high_confidence_low_coherence": "Confidence Calibrator",
    "context_switch_failure": "Context-Switch Detector",
    "incoherent_response": "Coherence Validator",
    "confidence_mismatch": "Confidence Calibrator",
    "low_confidence_violation": "Retrieval Re-Ranker",
}


def classify_violation(v: Dict[str, Any]) -> str:
    """Classify one violation record on REAL fields. Returns a category string."""
    for name, rule in _CATEGORY_RULES:
        try:
            if rule(v):
                return name
        except Exception:
            # A malformed record field should not crash categorization.
            continue
    dt = v.get("dissonance_type")
    if dt:
        return "unknown_dissonance"  # present but unmapped dissonance_type
    return "unclassified"            # no usable signal


def categorize_violations(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach a 'category' key to each record. Returns a new list of dicts."""
    out = []
    for rec in records:
        rec = dict(rec)
        rec["category"] = classify_violation(rec)
        out.append(rec)
    return out


def count_by_category(categorized: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    return dict(Counter(c["category"] for c in categorized))


def generate_report(counts: Dict[str, int], total: int) -> str:
    """Human-readable report + top-3 specialist recommendation (real categories)."""
    if total == 0:
        return ("VIOLATION ANALYSIS REPORT\n"
                "===========================\n"
                "Total violations: 0\n\n"
                "No violations to categorize. (Collect real query violations, or\n"
                "run generate_synthetic_dream_bucket.py to exercise the pipeline.)\n")
    lines = [
        "VIOLATION ANALYSIS REPORT",
        "===========================",
        f"Total violations: {total}",
        "",
        "TOP VIOLATION TYPES:",
    ]
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    for cat, n in ranked:
        pct = (n / total) * 100
        lines.append(f"  {cat}: {n} ({pct:.1f}%)")

    # Recommendation: top-3 categories -> specialists (dedup, preserve order).
    recommended: List[str] = []
    for cat, _ in ranked[:3]:
        spec = SPECIALIST_MAP.get(cat)
        if spec and spec not in recommended:
            recommended.append(spec)
    lines.append("")
    lines.append("RECOMMENDATION:")
    lines.append("Build these microspecialists (in priority order, derived from real signals):")
    for i, spec in enumerate(recommended, 1):
        lines.append(f"  {i}. {spec}")
    # Honesty note about what we could NOT detect.
    lines.append("")
    lines.append("NOTE: categories are derived from the REAL violation schema")
    lines.append("(dissonance_type / returned_confidence / mtr_error_signal). The")
    lines.append("original spec's natural-language categories (coreference, sense")
    lines.append("ambiguity, ...) require a user_complaint field the violation")
    lines.append("record does not carry, and are intentionally NOT fabricated.")
    return "\n".join(lines)


def run(dream_bucket_dir: Optional[str], input_path: Optional[str]) -> Dict[str, Any]:
    """Load violations from a dream-bucket dir or a raw jsonl, categorize, report."""
    records: List[Dict[str, Any]] = []
    source = None
    if input_path:
        source = f"jsonl:{input_path}"
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    elif dream_bucket_dir:
        source = f"dream_bucket:{dream_bucket_dir}"
        try:
            from dream_bucket import DreamBucketReader
        except ImportError:
            return {"ok": False, "blocker": "dream_bucket module not importable"}
        reader = DreamBucketReader(dream_bucket_dir)
        try:
            records = list(reader.read_live_log("violations"))
        except FileNotFoundError:
            records = []
    else:
        return {"ok": False, "blocker": "pass --dream-bucket <dir> or --input <jsonl>"}

    categorized = categorize_violations(records)
    counts = count_by_category(categorized)
    report = generate_report(counts, len(categorized))
    return {
        "ok": True,
        "source": source,
        "total": len(categorized),
        "counts": counts,
        "report": report,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="error_categorizer")
    ap.description = "Categorize Dream Bucket violations on REAL schema; recommend microspecialists."
    ap.add_argument("--dream-bucket", default=None, help="Dream bucket root dir (reads live/violations.jsonl)")
    ap.add_argument("--input", default=None, help="Raw violations jsonl instead of a dream bucket")
    ap.add_argument("--output-json", dest="output", default=None, help="Write JSON result here (or stdout)")
    args = ap.parse_args(list(argv) if argv is not None else None)

    result = run(args.dream_bucket, args.input)
    if not result.get("ok"):
        sys.stderr.write(f"ERROR_CATEGORIZER BLOCKED: {result.get('blocker')}\n")
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return 2

    sys.stderr.write(result["report"] + "\n")
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
