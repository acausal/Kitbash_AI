"""tools.timeseries_windowed_operations package.

Library:
    from tools.timeseries_windowed_operations import timeseries_aggregate
    timeseries_aggregate(data, window_size=3600, window_type="fixed", operation="mean")
    # data: [(iso_ts, value), ...]

CLI:
    python -m tools.timeseries_windowed_operations aggregate data.json --window-size 3600 --operation mean

Aggregates [(timestamp, value)] over fixed (non-overlapping) or sliding windows.
Operations: mean, sum, median, min, max, count, variance, entropy. ISO UTC only;
data must be sorted ascending (else error). Errors returned as dicts, never
raised. Pure stdlib.
"""
from .core import timeseries_aggregate

__all__ = ["timeseries_aggregate"]
