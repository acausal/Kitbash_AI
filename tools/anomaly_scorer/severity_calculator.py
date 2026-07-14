"""Severity scoring for tools.anomaly_scorer.

Deterministic, threshold-based (v1: no statistical tests). Two public helpers:

  severity_from_magnitude(magnitude_ratio, std_ratio=0.0, trending_worse=False,
                          n_observations=None, persistence=False, recency_hours=None)
      -> float in [0.0, 1.0]

  recency_factor(age_hours, recency_weight=1.0) -> float
      recent anomalies (< 1h) boosted; decays toward 1.0 as they age.
"""

import math


# Magnitude-ratio -> base severity (piecewise, monotonic, hits TEST ranges):
#   2x..3x  -> 0.4 .. 0.55
#   3x..5x  -> 0.55 .. 0.70
#   5x..10x -> 0.70 .. 0.85
#   >10x    -> 0.85 .. 0.95
def _base_from_magnitude(mag: float) -> float:
    if mag <= 1.0:
        return 0.0
    if mag < 2.0:
        # 1x..2x: ramp 0.0 -> 0.4 (mild deviation)
        return 0.4 * (mag - 1.0)
    if mag < 3.0:
        return 0.4 + 0.15 * (mag - 2.0)            # 0.4 .. 0.55
    if mag < 5.0:
        return 0.55 + 0.075 * (mag - 3.0)           # 0.55 .. 0.70
    if mag < 10.0:
        return 0.70 + 0.15 * (mag - 5.0) * (1.0 / 5.0) * (5.0 / 5.0)  # 0.70 .. 0.85
    # >10x saturates
    return min(0.95, 0.85 + 0.10 * min(1.0, (mag - 10.0) / 20.0))


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def severity_from_magnitude(magnitude_ratio: float, std_ratio: float = 0.0,
                            trending_worse: bool = False, n_observations: int = None,
                            persistence: bool = False,
                            recency_hours: float = None) -> float:
    """Compute a deterministic severity in [0.0, 1.0].

    magnitude_ratio: observed/baseline (or observed-baseline)/baseline ratio.
    std_ratio: z = (observed-baseline)/std (used only to nudge if extreme).
    trending_worse: +0.1 if the anomaly is getting worse over time.
    n_observations: if < 5, -0.2 (low sample confidence).
    persistence: if the same anomaly recurred, +0.15.
    recency_hours: if < 1.0, +0.1.
    """
    sev = _base_from_magnitude(magnitude_ratio)
    if trending_worse:
        sev += 0.1
    if n_observations is not None and n_observations < 5:
        sev -= 0.2
    if persistence:
        sev += 0.15
    if recency_hours is not None and recency_hours < 1.0:
        sev += 0.1
    return round(_clamp(sev), 4)


def recency_factor(age_hours: float, recency_weight: float = 1.0) -> float:
    """Recency boost for score_anomaly_severity.

    recency_weight 1.0 => factor 1.0 (no extra boost). Higher weight boosts
    recent anomalies. TEST recency_weight_boost: original 0.78, age 0.5h,
    weight 1.5 -> adjusted ~0.80..0.84 => factor ~1.030..1.077.
    factor = 1 + (recency_weight-1) * exp(-age_hours) * 0.10.  At weight 1.5,
    age 0.5h: 1 + 0.5*exp(-0.5)*0.10 = 1.030.
    """
    factor = 1.0 + (recency_weight - 1.0) * math.exp(-max(age_hours, 0.0)) * 0.10
    return round(_clamp(factor, 1.0, 2.0), 4)
