"""tools.timeseries_windowed_operations core (stdlib only).

Aggregate time-series data over fixed or sliding windows. Used for Dream Bucket
statistics, grain activation patterns, drift monitoring, trend detection. See
SPEC-timeseries_windowed_operations_v1.md.
"""
import math
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

_SUPPORTED = ("mean", "sum", "median", "min", "max", "count", "variance", "entropy")
_DATETIME_FMT = "%Y-%m-%dT%H:%M:%S"


def _parse_ts(ts: str) -> datetime:
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _fmt_ts(dt: datetime) -> str:
    # normalize to 'Z' suffix, drop microseconds
    out = dt.astimezone(timezone.utc) if dt.tzinfo else dt
    return out.replace(microsecond=0).strftime(_DATETIME_FMT) + "Z"


def _shannon_entropy(values: List[float]) -> float:
    counts = Counter(values)
    total = len(values)
    return -sum((c / total) * math.log2(c / total) for c in counts.values() if c > 0)


def _compute_op(values: List[float], op: str) -> Any:
    if op == "mean":
        return statistics.mean(values)
    if op == "sum":
        return sum(values)
    if op == "median":
        return statistics.median(values)
    if op == "min":
        return min(values)
    if op == "max":
        return max(values)
    if op == "count":
        return len(values)
    if op == "variance":
        return statistics.variance(values) if len(values) > 1 else 0.0
    if op == "entropy":
        return _shannon_entropy(values)
    raise ValueError(f"Unknown operation: {op}")


def _sorted_and_valid(data: List[Tuple[str, float]]) -> Tuple[bool, List, List]:
    """Return (is_sorted, parsed_ts_list, values_list). Invalid ts -> is_sorted False."""
    parsed = []
    for ts, val in data:
        try:
            parsed.append(_parse_ts(ts))
        except (ValueError, TypeError):
            return False, [], []
    for i in range(1, len(parsed)):
        if parsed[i] < parsed[i - 1]:
            return False, parsed, []
    return True, parsed, [v for _, v in data]


def timeseries_aggregate(data: List[Tuple[str, float]], window_size: int,
                          window_type: str = "fixed", operation: str = "mean",
                          start_time: str = None, end_time: str = None) -> Dict:
    """Aggregate `data` over windows. Returns result/error dict (never raises)."""
    if operation not in _SUPPORTED:
        return {"status": "error",
                "reason": f"Invalid operation: '{operation}' (supported: {', '.join(_SUPPORTED)})",
                "operation": operation}
    if window_type not in ("fixed", "sliding"):
        return {"status": "error", "reason": f"Invalid window_type: '{window_type}'",
                "window_type": window_type}
    if not isinstance(window_size, int) or window_size <= 0:
        return {"status": "error", "reason": f"Invalid window_size: {window_size}"}
    if not data:
        return {"status": "success", "operation": operation, "window_size": window_size,
                "window_type": window_type, "results": [], "num_windows": 0,
                "data_points_processed": 0}
    ok, parsed, values = _sorted_and_valid(data)
    if not ok:
        sample = data[:3]
        return {"status": "error",
                "reason": "Data not sorted by timestamp or contains invalid timestamps",
                "data_sample": sample}
    start = _parse_ts(start_time) if start_time else parsed[0]
    end = _parse_ts(end_time) if end_time else parsed[-1]
    results = []
    if window_type == "fixed":
        cur = start
        while cur <= end:
            w_end = cur + timedelta(seconds=window_size)
            pts = [v for ts, v in zip(parsed, values) if cur <= ts < w_end]
            value = _compute_op(pts, operation) if pts else None
            results.append({"window_start": _fmt_ts(cur), "window_end": _fmt_ts(w_end),
                            "value": value, "count": len(pts)})
            cur = w_end
    else:  # sliding: one window per data point, [ts - window_size, ts]
        for ts, v in zip(parsed, values):
            w_start = ts - timedelta(seconds=window_size)
            pts = [vv for tts, vv in zip(parsed, values) if w_start <= tts <= ts]
            value = _compute_op(pts, operation) if pts else None
            results.append({"window_start": _fmt_ts(w_start), "window_end": _fmt_ts(ts),
                            "value": value, "count": len(pts)})
    return {"status": "success", "operation": operation, "window_size": window_size,
            "window_type": window_type, "results": results,
            "num_windows": len(results), "data_points_processed": len(data)}
