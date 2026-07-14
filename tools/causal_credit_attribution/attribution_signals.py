"""tools.causal_credit_attribution signals (stdlib only).

Pure functions computing each of the 4 attribution signal scores per component.
See SPEC §"Attribution Signals". All return dicts keyed by component
(tool name or grain_id).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def positional_signal(sequence: Sequence) -> Dict[Any, float]:
    """Later components get higher credit: (i+1)/N for 0-indexed position i;
    last=1.0, first=1/N.

    NOTE: SPEC §"Attribution Signals" writes `(N - i) / N` but its own prose
    ("last tool gets 1.0, first gets 1/N") and the worked API example (positional
    rises 0.15->0.20->0.25->0.35 down the chain) contradict that formula. The
    intent is unambiguously "later = higher", so we implement (i+1)/N. Documented
    in README.
    """
    n = len(sequence)
    if n == 0:
        return {}
    return {item: (i + 1) / n for i, item in enumerate(sequence)}


def _success_rate(tool: Any, traces: List[dict]) -> float:
    denom = 0
    num = 0
    for t in traces:
        seq = t.get("sequence")
        if seq is None:
            seq = t.get("grain_activations", [])
        if tool in seq:
            denom += 1
            if t.get("outcome") == "success" or (
                isinstance(t.get("error_signal"), (int, float)) and t["error_signal"] < 0.2
            ):
                num += 1
    return (num / denom) if denom else 0.0


def historical_correlation_signal(components: Sequence, traces: Optional[List[dict]]
                                  ) -> Dict[Any, float]:
    if not traces:
        return {c: 0.0 for c in components}
    return {c: _success_rate(c, traces) for c in components}


def pattern_membership_signal(components: Sequence, sequence: Sequence,
                              success_patterns: Optional[List[dict]]) -> Dict[Any, float]:
    """min(count_in_patterns / max_count, 1.0); bonus if pattern active in trace."""
    if not success_patterns:
        return {c: 0.0 for c in components}
    counts: Dict[Any, int] = {c: 0 for c in components}
    active: set = set()
    for p in success_patterns:
        pseq = p.get("sequence") or p.get("grain_sequence") or []
        contains_any = False
        for c in components:
            if c in pseq:
                counts[c] = counts.get(c, 0) + 1
                contains_any = True
        if contains_any and any(c in pseq for c in sequence):
            active.update(c for c in components if c in pseq)
    mx = max(counts.values(), default=0) or 1
    out: Dict[Any, float] = {}
    for c in components:
        base = min(counts[c] / mx, 1.0)
        out[c] = min(base + (0.1 if c in active else 0.0), 1.0)
    return out


def input_output_salience_signal(components: Sequence,
                                 tool_metadata: Optional[Dict[str, dict]] = None
                                 ) -> Dict[Any, float]:
    """v1 base heuristic 0.5; elevated by CWL brief custom fields when present:
    work_type 'action' -> 0.8 (produces durable effects), 'exploratory' -> 0.5,
    'neutral' -> 0.6; depends_on_results True -> +0.1 (transforms key inputs).
    Forward-compat hook for BRIEF-CWL_EPISODE_DEPENDENCY_INTEGRATION.md.
    """
    out: Dict[Any, float] = {}
    for c in components:
        score = 0.5
        meta = (tool_metadata or {}).get(c) if tool_metadata else None
        if isinstance(meta, dict):
            wt = meta.get("work_type")
            if wt == "action":
                score = 0.8
            elif wt == "exploratory":
                score = 0.5
            elif wt == "neutral":
                score = 0.6
            if meta.get("depends_on_results"):
                score = min(score + 0.1, 1.0)
        out[c] = round(score, 4)
    return out
