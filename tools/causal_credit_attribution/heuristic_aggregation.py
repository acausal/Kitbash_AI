"""tools.causal_credit_attribution aggregation (stdlib only).

Combine the 4 signals into per-component credit, then normalize so total = 1.0.
See SPEC §"Composite Attribution" + "Total credit normalization".
"""
from __future__ import annotations

from typing import Dict, List, Sequence

SIGNAL_KEYS = ["positional", "historical_correlation", "pattern_membership", "input_output_salience"]

DEFAULT_WEIGHTS: Dict[str, float] = {
    "positional": 0.30,
    "historical_correlation": 0.35,
    "pattern_membership": 0.25,
    "input_output_salience": 0.10,
}


def normalize_weights(weights: Dict[str, float] = None) -> Dict[str, float]:
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        for k in SIGNAL_KEYS:
            if k in weights and isinstance(weights[k], (int, float)):
                w[k] = float(weights[k])
    total = sum(w.values())
    return {k: v / total for k, v in w.items()} if total > 0 else dict(DEFAULT_WEIGHTS)


def aggregate(components: Sequence, signals: Dict[str, Dict[Any, float]],
              weights: Dict[str, float] = None) -> Dict[Any, float]:
    """Weighted sum of the 4 signals per component, then normalize to sum 1.0."""
    w = normalize_weights(weights)
    raw: Dict[Any, float] = {}
    for c in components:
        s = 0.0
        for key in SIGNAL_KEYS:
            s += w[key] * signals.get(key, {}).get(c, 0.0)
        raw[c] = s
    total = sum(raw.values())
    if total <= 0:
        n = len(raw) or 1
        return {c: round(1.0 / n, 4) for c in raw}
    return {c: round(v / total, 4) for c, v in raw.items()}
