"""tools.positive_signal_scorer core (stdlib only).

score_patterns() computes all 5 dimensions, combines into a composite
signal_strength, ranks descending, and flags sample-size confidence. compute_signal_dimension()
delegates to a single dimension for debugging. See SPEC-positive_signal_scorer_v1.md.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .signal_dimensions import (
    frequency_score, support_score, outcome_correlation_score,
    consistency_score, temporal_stability_score, is_success,
)
from .composite_scoring import composite, normalize_weights, DIMENSIONS

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("positive_signal_scorer")
except Exception:
    _logger = None

_ADEQUATE = 10
_VERY_HIGH = 50


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_id() -> str:
    return "pos_score_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _confidence(n: int) -> str:
    if n >= _VERY_HIGH:
        return "very_high"
    if n >= _ADEQUATE:
        return "adequate"
    return "low"


def _validate_patterns(patterns) -> None:
    if not isinstance(patterns, list):
        raise ValueError("patterns must be a list")
    for p in patterns:
        if not isinstance(p, dict) or "pattern_id" not in p:
            raise ValueError("each pattern must be a dict with 'pattern_id'")


def _validate_traces(traces) -> None:
    if not isinstance(traces, list):
        raise ValueError("traces must be a list")


def score_patterns(patterns: list, execution_traces: list,
                   weights: dict = None) -> dict:
    """Score success patterns on 5 signal dimensions; emit ranked composite.

    See SPEC §API 1. `weights` optionally overrides default dimension weights.
    """
    _validate_patterns(patterns)
    _validate_traces(execution_traces)
    w = normalize_weights(weights)

    freq = frequency_score(patterns, execution_traces)
    supp = support_score(patterns, execution_traces)
    oc_corr, oc_detail = outcome_correlation_score(patterns, execution_traces)
    cons = consistency_score(patterns, execution_traces)
    temp = temporal_stability_score(patterns, execution_traces)

    scores_by_dim = {
        "frequency": freq, "support": supp, "outcome_correlation": oc_corr,
        "consistency": cons, "temporal_stability": temp,
    }
    strength = composite(scores_by_dim, weights)

    scored = []
    for p in patterns:
        pid = p.get("pattern_id")
        seq = p.get("sequence") or p.get("grain_sequence") or []
        num, denom = oc_detail.get(pid, (0, 0))
        sample = denom if p.get("frequency") is None else p.get("frequency", denom)
        n = int(p.get("frequency", denom) or denom)
        scored.append({
            "pattern_id": pid,
            "pattern": seq,
            "signal_strength": strength.get(pid, 0.0),
            "signal_dimensions": {
                "frequency_score": freq.get(pid, 0.0),
                "support_score": supp.get(pid, 0.0),
                "outcome_correlation_score": oc_corr.get(pid, 0.0),
                "consistency_score": cons.get(pid, 0.0),
                "temporal_stability_score": temp.get(pid, 0.0),
            },
            "sample_size": n,
            "sample_size_confidence": _confidence(n),
            "success_rate_given_pattern": round(num / denom, 4) if denom else 0.0,
            "coverage": float(p.get("coverage", 0.0) or 0.0),
            "notes": _notes(n, temp.get(pid, 0.0), cons.get(pid, 0.0)),
        })
    scored.sort(key=lambda s: (-s["signal_strength"], s["pattern_id"]))
    for rank, s in enumerate(scored, start=1):
        s["rank"] = rank
    if _logger:
        _logger.log(event_type="scoring_complete",
                    data={"patterns_scored": len(scored)})
    return {
        "scoring_run_id": _run_id(),
        "timestamp": _now(),
        "patterns_scored": len(scored),
        "patterns": scored,
        "metadata": {
            "weights": w,
            "min_sample_size_for_adequate_confidence": _ADEQUATE,
        },
    }


def _notes(n: int, temp: float, cons: float) -> str:
    if n < _ADEQUATE:
        return "Low sample size; monitor for confirmation"
    if temp < 0.5:
        return "Possible temporal drift; success rate varies across time"
    if cons < 0.7:
        return "Outcome variance is high; pattern may be inconsistent"
    return "Strong pattern; appears consistently across time period"


def compute_signal_dimension(patterns: list, traces: list, dimension: str) -> dict:
    """Compute a single signal dimension across patterns. See SPEC §API 2."""
    _validate_patterns(patterns)
    _validate_traces(traces)
    if dimension not in DIMENSIONS:
        raise ValueError(f"dimension must be one of {DIMENSIONS}")
    if dimension == "frequency":
        sc = frequency_score(patterns, traces)
        detail = {pid: (0, 0) for pid in sc}
    elif dimension == "support":
        sc = support_score(patterns, traces)
        detail = {pid: (0, 0) for pid in sc}
    elif dimension == "outcome_correlation":
        sc, detail = outcome_correlation_score(patterns, traces)
    elif dimension == "consistency":
        sc = consistency_score(patterns, traces)
        detail = {pid: (0, 0) for pid in sc}
    else:  # temporal_stability
        sc = temporal_stability_score(patterns, traces)
        detail = {pid: (0, 0) for pid in sc}
    defs = {
        "frequency": "How often does this pattern appear? min(freq / median_freq, 1.0)",
        "support": "What % of successful traces contain this pattern? (provided support)",
        "outcome_correlation": "(traces where pattern AND success) / (traces where pattern fires)",
        "consistency": "max(1.0 - cv(error_signals), 0.0); low variance = high consistency",
        "temporal_stability": "1.0 - (max_bucket_corr - min_bucket_corr); stable = high",
    }
    out = []
    for p in patterns:
        pid = p.get("pattern_id")
        num, denom = detail.get(pid, (0, 0))
        out.append({
            "pattern_id": pid,
            "pattern": p.get("sequence") or p.get("grain_sequence") or [],
            "score": sc.get(pid, 0.0),
            "numerator": num,
            "denominator": denom,
        })
    return {"dimension": dimension, "definition": defs[dimension], "pattern_scores": out}
