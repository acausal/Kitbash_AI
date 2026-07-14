"""tools.positive_signal_scorer composite scoring (stdlib only).

Weighted average of the 5 signal dimensions into signal_strength in [0,1].
Default weights from SPEC-positive_signal_scorer_v1.md. See "Composite Scoring".
"""
from __future__ import annotations

from typing import Dict, List

DIMENSIONS = ["frequency", "support", "outcome_correlation", "consistency", "temporal_stability"]

DEFAULT_WEIGHTS: Dict[str, float] = {
    "frequency": 0.15,
    "support": 0.15,
    "outcome_correlation": 0.35,
    "consistency": 0.20,
    "temporal_stability": 0.15,
}


def normalize_weights(weights: Dict[str, float] = None) -> Dict[str, float]:
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        for k in DIMENSIONS:
            if k in weights and isinstance(weights[k], (int, float)):
                w[k] = float(weights[k])
    total = sum(w.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {k: v / total for k, v in w.items()}


def composite(scores_by_dim: Dict[str, Dict[str, float]],
              weights: Dict[str, float] = None) -> Dict[str, float]:
    """Return {pattern_id: signal_strength} as the weighted sum of dimensions."""
    w = normalize_weights(weights)
    pids = set()
    for dim in scores_by_dim.values():
        pids.update(dim.keys())
    out: Dict[str, float] = {}
    for pid in pids:
        s = 0.0
        for dim in DIMENSIONS:
            s += w[dim] * scores_by_dim.get(dim, {}).get(pid, 0.0)
        out[pid] = round(min(1.0, max(0.0, s)), 4)
    return out
