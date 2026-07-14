"""tools.causal_credit_attribution core (stdlib only).

attribute_credit_to_tools / attribute_credit_to_grains / batch_attribute_credit.
Combines 4 signals, normalizes credit to sum 1.0, ranks by position, flags
confidence. See SPEC-causal_credit_attribution_v1.md.

Forward-compat: `tool_metadata` lets the CWL brief's custom fields
(work_type / depends_on_results) drive input_output_salience when added
retroactively later.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .attribution_signals import (
    positional_signal, historical_correlation_signal,
    pattern_membership_signal, input_output_salience_signal,
)
from .heuristic_aggregation import aggregate, normalize_weights, SIGNAL_KEYS

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("causal_credit_attribution")
except Exception:
    _logger = None

_HIST_HIGH = 100
_HIST_LOW = 10


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_id() -> str:
    return "attr_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _confidence(hist_n: int, n_signals: int) -> str:
    if hist_n < _HIST_LOW:
        return "low"
    if hist_n > _HIST_HIGH and n_signals >= 2:
        return "high"
    return "medium"


def _validate_trace(trace: dict) -> None:
    if not isinstance(trace, dict):
        raise ValueError("trace must be a dict")
    if "trace_id" not in trace:
        raise ValueError("trace missing 'trace_id'")
    if "sequence" not in trace and "grain_activations" not in trace:
        raise ValueError("trace must have 'sequence' or 'grain_activations'")


def _component_attributions(components: List[Any], sequence: List[Any],
                            success_patterns, historical_traces, weights,
                            tool_metadata=None) -> List[dict]:
    signals = {
        "positional": positional_signal(sequence),
        "historical_correlation": historical_correlation_signal(components, historical_traces),
        "pattern_membership": pattern_membership_signal(components, sequence, success_patterns),
        "input_output_salience": input_output_salience_signal(components, tool_metadata),
    }
    credits = aggregate(components, signals, weights)
    hist = historical_correlation_signal(components, historical_traces)
    out = []
    for c in components:
        out.append({
            "position": sequence.index(c) if c in sequence else -1,
            "component": c,
            "credit_score": credits[c],
            "attribution_signals": {
                "positional_signal": round(signals["positional"].get(c, 0.0), 4),
                "historical_correlation_signal": round(signals["historical_correlation"].get(c, 0.0), 4),
                "pattern_membership_signal": round(signals["pattern_membership"].get(c, 0.0), 4),
                "input_output_salience_signal": round(signals["input_output_salience"].get(c, 0.0), 4),
            },
            "historical_success_rate": round(hist.get(c, 0.0), 4),
        })
    return out


def attribute_credit_to_tools(trace: dict, success_patterns: list = None,
                              historical_traces: list = None, weights: dict = None,
                              tool_metadata: dict = None) -> dict:
    _validate_trace(trace)
    seq = trace.get("sequence") or []
    components = list(seq)
    base = _component_attributions(components, seq, success_patterns,
                                   historical_traces, weights, tool_metadata)
    appearances = _pattern_appearances(components, success_patterns)
    hist_n = len(historical_traces) if historical_traces else 0
    conf = _confidence(hist_n, 4 if (success_patterns or historical_traces) else 1)
    tool_attrs = []
    for b in base:
        tool_attrs.append({
            "position": b["position"],
            "tool": b["component"],
            "credit_score": b["credit_score"],
            "attribution_signals": b["attribution_signals"],
            "appears_in_patterns": appearances.get(b["component"], []),
            "historical_success_rate": b["historical_success_rate"],
            "confidence": conf,
        })
    tool_attrs.sort(key=lambda x: x["position"])
    total = round(sum(t["credit_score"] for t in tool_attrs), 4)
    if _logger:
        _logger.log(event_type="attribution_complete", data={"trace_id": trace.get("trace_id")})
    return {
        "attribution_run_id": _run_id(),
        "timestamp": _now(),
        "trace_id": trace.get("trace_id"),
        "trace_sequence": list(seq),
        "outcome": trace.get("outcome"),
        "error_signal": trace.get("error_signal", 0.0),
        "total_credit_attributed": total,
        "tool_attributions": tool_attrs,
        "metadata": {
            "weights": normalize_weights(weights),
            "success_patterns_used": len(success_patterns or []),
            "historical_traces_used": hist_n,
        },
    }


def attribute_credit_to_grains(trace: dict, grain_signal_scores: list = None,
                               historical_traces: list = None, weights: dict = None,
                               success_patterns: list = None) -> dict:
    _validate_trace(trace)
    grains = list(trace.get("grain_activations") or [])
    # grain_signal_scores feed historical_correlation-equivalent if no historical_traces
    sig_map = {}
    if grain_signal_scores:
        for g in grain_signal_scores:
            sig_map[g.get("grain_id")] = g.get("success_signal_strength", 0.0)
    base = _component_attributions(grains, grains, success_patterns, historical_traces, weights)
    appearances = _grain_pattern_appearances(grains, success_patterns)
    conf = _confidence(len(historical_traces) if historical_traces else 0,
                       4 if (success_patterns or historical_traces) else 1)
    grain_attrs = []
    for b in base:
        grain_attrs.append({
            "position": b["position"],
            "grain_id": b["component"],
            "credit_score": b["credit_score"],
            "attribution_signals": b["attribution_signals"],
            "appears_in_patterns": appearances.get(b["component"], []),
            "historical_success_rate": b["historical_success_rate"] or sig_map.get(b["component"], 0.0),
            "confidence": conf,
        })
    grain_attrs.sort(key=lambda x: x["position"])
    total = round(sum(g["credit_score"] for g in grain_attrs), 4)
    return {
        "attribution_run_id": _run_id(),
        "timestamp": _now(),
        "trace_id": trace.get("trace_id"),
        "trace_sequence": list(grains),
        "outcome": trace.get("outcome"),
        "error_signal": trace.get("error_signal", 0.0),
        "total_credit_attributed": total,
        "grain_attributions": grain_attrs,
        "metadata": {
            "weights": normalize_weights(weights),
            "success_patterns_used": len(success_patterns or []),
            "historical_traces_used": len(historical_traces) if historical_traces else 0,
        },
    }


def batch_attribute_credit(traces: list, success_patterns: list = None,
                           historical_traces: list = None, weights: dict = None) -> dict:
    if not isinstance(traces, list):
        raise ValueError("traces must be a list")
    attributions = [attribute_credit_to_tools(t, success_patterns, historical_traces, weights)
                    for t in traces]
    agg: Dict[Any, float] = {}
    for a in attributions:
        for ta in a["tool_attributions"]:
            agg[ta["tool"]] = agg.get(ta["tool"], 0.0) + ta["credit_score"]
    return {
        "batch_attribution_run_id": "batch_" + _run_id(),
        "timestamp": _now(),
        "traces_processed": len(traces),
        "attributions": attributions,
        "aggregated_tool_credit": {k: round(v, 4) for k, v in agg.items()},
    }


def _pattern_appearances(components, success_patterns) -> Dict[Any, List[str]]:
    out: Dict[Any, List[str]] = {c: [] for c in components}
    if not success_patterns:
        return out
    for p in success_patterns:
        pid = p.get("pattern_id", "pattern")
        pseq = p.get("sequence") or p.get("grain_sequence") or []
        for c in components:
            if c in pseq:
                out[c].append(pid)
    return out


def _grain_pattern_appearances(grains, success_patterns) -> Dict[Any, List[str]]:
    return _pattern_appearances(grains, success_patterns)
