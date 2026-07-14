"""tools.success_pattern_miner success-criteria filtering (stdlib only).

Selects the traces that count as "success" and (optionally) applies a sliding
time window. Fail-loud on missing required fields so malformed input never
silently vanishes. See SPEC-success_pattern_miner_v1.md section "Implementation
Notes 1/7".
"""
from datetime import datetime, timezone
from typing import List, Optional


def _parse_ts(s: Optional[str]):
    if not s:
        return None
    if not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def is_success(trace: dict, success_threshold: float) -> bool:
    """A trace is a success iff outcome == 'success' OR error_signal < threshold."""
    if not isinstance(trace, dict):
        raise ValueError("each trace must be a dict")
    outcome = trace.get("outcome")
    err = trace.get("error_signal")
    if outcome is None and err is None:
        raise ValueError("trace missing required 'outcome' or 'error_signal'")
    if outcome == "success":
        return True
    if err is not None:
        try:
            return float(err) < float(success_threshold)
        except (TypeError, ValueError):
            raise ValueError("error_signal must be numeric")
    return False


def filter_success_traces(traces: list, success_threshold: float = 0.2,
                          time_window_hours: Optional[int] = None) -> List[dict]:
    """Return success traces, dropping non-success and (optionally) out-of-window.

    Required per-trace fields (ValueError if any missing):
      trace_id | query_id, timestamp, and at least one of
      sequence | grain_activations.
    Time window: keep only traces where (now - timestamp) <= time_window_hours.
    A success trace with an unparseable timestamp is excluded when a window is
    set (cannot prove it falls inside the window).
    """
    if not isinstance(traces, list):
        raise ValueError("traces must be a list")
    now = datetime.now(timezone.utc)
    out: List[dict] = []
    for t in traces:
        if not isinstance(t, dict):
            raise ValueError("each trace must be a dict")
        if "trace_id" not in t and "query_id" not in t:
            raise ValueError("trace missing required 'trace_id'/'query_id'")
        if "timestamp" not in t:
            raise ValueError("trace missing required 'timestamp'")
        if "sequence" not in t and "grain_activations" not in t:
            raise ValueError("trace must have 'sequence' or 'grain_activations'")
        if not is_success(t, success_threshold):
            continue
        if time_window_hours is not None:
            ts = _parse_ts(t.get("timestamp"))
            if ts is None:
                continue
            age_h = (now - ts).total_seconds() / 3600.0
            if age_h > float(time_window_hours):
                continue
        out.append(t)
    return out
