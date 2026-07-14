"""tools.anomaly_scorer package.

Library:
    from tools.anomaly_scorer import (
        detect_false_positive_rate_anomalies,
        detect_confidence_degradation,
        detect_emerging_collisions,
        detect_violation_trend_shifts,
        score_anomaly_severity,
    )

CLI:
    python -m tools.anomaly_scorer detect-fp-spikes --grain-stats g.json \
        --historical-baseline b.json --window-hours 4
"""

from .core import (
    detect_false_positive_rate_anomalies,
    detect_confidence_degradation,
    detect_emerging_collisions,
    detect_violation_trend_shifts,
    score_anomaly_severity,
)
from .severity_calculator import severity_from_magnitude, recency_factor
from .baselines import deviation_magnitude, z_score, linear_trend

__all__ = [
    "detect_false_positive_rate_anomalies",
    "detect_confidence_degradation",
    "detect_emerging_collisions",
    "detect_violation_trend_shifts",
    "score_anomaly_severity",
    "severity_from_magnitude",
    "recency_factor",
    "deviation_magnitude",
    "z_score",
    "linear_trend",
]
