"""Baseline comparison helpers for tools.anomaly_scorer (stdlib only)."""

import statistics
from datetime import datetime


def parse_ts(ts: str) -> datetime:
    """Parse ISO-8601 timestamps like '2026-07-14T10:00:00Z' (or with offset)."""
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        # fall back: truncate to 19 chars (YYYY-MM-DDTHH:MM:SS)
        return datetime.fromisoformat(s[:19])


def deviation_magnitude(observed: float, baseline: float) -> float:
    """Ratio observed/baseline (the TEST/SPEC-example definition: 0.31/0.06
    = 5.17). Handles baseline 0 (returns observed, or 0.0 if both 0)."""
    if baseline == 0:
        if observed == 0:
            return 0.0
        return float(observed)
    return observed / baseline


def z_score(observed: float, baseline: float, std: float) -> float:
    if std == 0:
        return 0.0
    return (observed - baseline) / std


def linear_trend(timeline: list) -> dict:
    """Linear regression over a timeline of {'timestamp':..., 'dissonance':...}.

    Returns {'slope': float, 'direction': 'increasing'|'decreasing'|'stable',
             'n_points': int, 'first': float, 'last': float}.
    Raises ValueError if < 3 points or values missing.
    """
    if not timeline or len(timeline) < 3:
        raise ValueError("timeline needs >= 3 points to compute a trend")
    pts = []
    for p in timeline:
        ts = p.get("timestamp")
        val = p.get("dissonance", p.get("violation_rate", p.get("value")))
        if ts is None or val is None:
            raise ValueError("timeline point missing timestamp or value")
        pts.append((parse_ts(ts).timestamp(), float(val)))
    pts.sort(key=lambda x: x[0])
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    n = len(xs)
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        slope = 0.0
    else:
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    # direction from sign + magnitude relative to value scale
    if abs(slope) < 1e-9:
        direction = "stable"
    elif slope > 0:
        direction = "increasing"
    else:
        direction = "decreasing"
    return {
        "slope": round(slope, 4),
        "direction": direction,
        "n_points": n,
        "first": ys[0],
        "last": ys[-1],
        "delta": round(ys[-1] - ys[0], 4),
    }


def slope_per_hour(timeline: list) -> float:
    """Convenience: slope expressed per hour (regression slope is per second)."""
    tr = linear_trend(timeline)
    return round(tr["slope"] * 3600.0, 4)
