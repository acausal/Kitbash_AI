"""Aggregate statistics helpers for tools.cosine_similarity (stdlib only)."""
import math
from typing import List


def _sorted(values: List[float]) -> List[float]:
    return sorted(values)


def mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def std(values: List[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / n)


def _percentile(sorted_vals: List[float], q: float) -> float:
    """Linear-interpolation percentile (q in [0,1])."""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_vals[0]
    idx = q * (n - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return sorted_vals[lo]
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def percentiles(values: List[float]) -> dict:
    s = _sorted(values)
    return {
        "p25": round(_percentile(s, 0.25), 6),
        "p50": round(_percentile(s, 0.50), 6),
        "p75": round(_percentile(s, 0.75), 6),
    }
