# SPEC: Time Series / Windowed Operations Tool v1

**Version:** 1.0  
**Status:** Ready for implementation  
**Target:** Kitbash tool registry (standalone tool)  
**Depends:** stdlib `statistics`, `collections`

---

## Purpose

Aggregate time-series data over sliding or fixed windows. Used for Dream Bucket statistics, grain activation patterns, topological drift monitoring, and trend detection in sleep pipeline.

---

## Interface

### Tool Call

```
timeseries_aggregate(
    data: list[tuple[str, float]],  # [(timestamp_iso, value), ...]
    window_size: int,               # Size of window (seconds)
    window_type: str = "fixed",     # "fixed" or "sliding"
    operation: str = "mean",        # mean, sum, median, min, max, count, entropy, variance
    start_time: str = None,         # ISO timestamp (optional, auto-detect if None)
    end_time: str = None,           # ISO timestamp (optional, auto-detect if None)
)
```

### Return Value

```json
{
  "status": "success",
  "operation": "mean",
  "window_size": 3600,
  "window_type": "fixed",
  "results": [
    {"window_start": "2026-07-14T00:00:00Z", "window_end": "2026-07-14T01:00:00Z", "value": 45.2, "count": 15},
    {"window_start": "2026-07-14T01:00:00Z", "window_end": "2026-07-14T02:00:00Z", "value": 47.8, "count": 18}
  ],
  "num_windows": 2,
  "data_points_processed": 33
}
```

### Error Cases

```json
{
  "status": "error",
  "reason": "Invalid operation: 'mode' (supported: mean, sum, median, min, max, count, entropy, variance)",
  "operation": "mode"
}
```

```json
{
  "status": "error",
  "reason": "Data not sorted by timestamp or contains invalid timestamps",
  "data_sample": [...]
}
```

---

## Semantics

### Input: `data`

List of `[timestamp, value]` tuples, where:
- `timestamp`: ISO 8601 format (e.g., `"2026-07-14T12:30:45Z"`)
- `value`: numeric (int or float)

Data should be sorted by timestamp (ascending). If not, tool returns error.

```python
data = [
    ("2026-07-14T00:00:00Z", 42.5),
    ("2026-07-14T00:15:00Z", 43.2),
    ("2026-07-14T00:30:00Z", 41.9),
    # ...
]
```

### Input: `window_size`

Size of window in **seconds**:
- `3600` = 1 hour
- `86400` = 1 day
- `60` = 1 minute
- `1` = 1 second (rarely useful)

### Input: `window_type`

**Fixed windows** (`"fixed"`): Divide time range into equal non-overlapping buckets.
- Start at `start_time` (or earliest timestamp), increment by `window_size`
- Each window contains data points within `[window_start, window_start + window_size)`
- Last window may be incomplete

**Sliding windows** (`"sliding"`): Windows overlap. For each data point, compute operation over preceding `window_size` seconds.
- More expensive computationally, smoother trends
- Result has one entry per data point (or fewer if sparse)

### Input: `operation`

Aggregation function applied to each window:
- **`mean`** — Average of values
- **`sum`** — Sum of values
- **`median`** — Median value
- **`min`** — Minimum value
- **`max`** — Maximum value
- **`count`** — Number of data points in window
- **`variance`** — Variance (measure of spread)
- **`entropy`** — Shannon entropy of value distribution (for categorical/binned data)

### Output: `results`

Array of aggregated windows, each with:
- `window_start`: ISO timestamp (start of window)
- `window_end`: ISO timestamp (end of window, exclusive)
- `value`: Result of operation (null if no data in window)
- `count`: Number of data points in window

**Example fixed windows:**
```json
[
  {
    "window_start": "2026-07-14T00:00:00Z",
    "window_end": "2026-07-14T01:00:00Z",
    "value": 45.2,
    "count": 15
  },
  {
    "window_start": "2026-07-14T01:00:00Z",
    "window_end": "2026-07-14T02:00:00Z",
    "value": 47.8,
    "count": 18
  }
]
```

### Special Cases

**Empty window:** If a window contains no data points:
- `value`: `null`
- `count`: `0`
- Window is still included in results

**Single data point in window:** Operations still work:
- `mean` of [42] = 42
- `variance` of [42] = 0
- `entropy` of [42] = 0

**Entropy operation:** Used to measure distribution uniformity:
- Uniform distribution (all values equal) → low entropy
- Mixed distribution (varied values) → high entropy
- Useful for detecting when query patterns become diverse vs. repetitive

---

## Implementation Notes

### Algorithm: Fixed Windows

```python
from datetime import datetime, timedelta

def aggregate_fixed_windows(data, window_size, operation):
    if not data:
        return []
    
    # Sort data by timestamp
    data_sorted = sorted(data, key=lambda x: x[0])
    
    # Determine time range
    start_ts = datetime.fromisoformat(data_sorted[0][0].replace('Z', '+00:00'))
    end_ts = datetime.fromisoformat(data_sorted[-1][0].replace('Z', '+00:00'))
    
    # Generate windows
    windows = []
    current = start_ts
    
    while current < end_ts:
        window_end = current + timedelta(seconds=window_size)
        
        # Collect data points in this window
        points = [v for ts, v in data_sorted
                  if current <= datetime.fromisoformat(ts.replace('Z', '+00:00')) < window_end]
        
        # Compute operation
        value = _compute_operation(points, operation)
        
        windows.append({
            "window_start": current.isoformat() + "Z",
            "window_end": window_end.isoformat() + "Z",
            "value": value,
            "count": len(points)
        })
        
        current = window_end
    
    return windows
```

### Algorithm: Sliding Windows

```python
def aggregate_sliding_windows(data, window_size, operation):
    if not data:
        return []
    
    data_sorted = sorted(data, key=lambda x: x[0])
    windows = []
    
    for i, (ts, val) in enumerate(data_sorted):
        # Window is [ts - window_size, ts]
        window_start_dt = datetime.fromisoformat(ts.replace('Z', '+00:00')) - timedelta(seconds=window_size)
        window_ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        
        # Collect points in window
        points = [v for t, v in data_sorted
                  if window_start_dt <= datetime.fromisoformat(t.replace('Z', '+00:00')) <= window_ts]
        
        value = _compute_operation(points, operation)
        
        windows.append({
            "window_start": window_start_dt.isoformat() + "Z",
            "window_end": window_ts.isoformat() + "Z",
            "value": value,
            "count": len(points)
        })
    
    return windows
```

### Operations

```python
import statistics
from math import log2

def _compute_operation(values, operation):
    if not values:
        return None
    
    if operation == "mean":
        return statistics.mean(values)
    elif operation == "sum":
        return sum(values)
    elif operation == "median":
        return statistics.median(values)
    elif operation == "min":
        return min(values)
    elif operation == "max":
        return max(values)
    elif operation == "count":
        return len(values)
    elif operation == "variance":
        return statistics.variance(values) if len(values) > 1 else 0.0
    elif operation == "entropy":
        return _shannon_entropy(values)
    else:
        raise ValueError(f"Unknown operation: {operation}")

def _shannon_entropy(values):
    """Calculate Shannon entropy of value distribution."""
    from collections import Counter
    counts = Counter(values)
    total = len(values)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * log2(p) if p > 0 else 0
    return entropy
```

---

## Data Structure

### Input Schema

```json
{
  "data": [
    ["2026-07-14T00:00:00Z", 42.5],
    ["2026-07-14T00:15:00Z", 43.2],
    ["2026-07-14T00:30:00Z", 41.9]
  ],
  "window_size": 3600,
  "window_type": "fixed",
  "operation": "mean"
}
```

### Output Schema (Success)

```json
{
  "status": "success",
  "operation": "mean",
  "window_size": 3600,
  "window_type": "fixed",
  "results": [
    {"window_start": "2026-07-14T00:00:00Z", "window_end": "2026-07-14T01:00:00Z", "value": 42.5, "count": 1}
  ],
  "num_windows": 1,
  "data_points_processed": 1
}
```

### Output Schema (Error)

```json
{
  "status": "error",
  "reason": "Data not sorted by timestamp",
  "data_sample": [...]
}
```

---

## Testing

### Unit Test Examples

```python
def test_fixed_windows_mean():
    data = [
        ("2026-07-14T00:00:00Z", 10),
        ("2026-07-14T00:30:00Z", 20),
        ("2026-07-14T01:00:00Z", 30),
    ]
    result = timeseries_aggregate(data, window_size=3600, window_type="fixed", operation="mean")
    assert result["status"] == "success"
    assert len(result["results"]) == 2
    assert result["results"][0]["value"] == 15  # (10 + 20) / 2
    assert result["results"][1]["value"] == 30

def test_fixed_windows_sum():
    data = [("2026-07-14T00:00:00Z", 5), ("2026-07-14T00:15:00Z", 15)]
    result = timeseries_aggregate(data, window_size=3600, operation="sum")
    assert result["results"][0]["value"] == 20

def test_sliding_windows():
    data = [
        ("2026-07-14T00:00:00Z", 10),
        ("2026-07-14T00:30:00Z", 20),
        ("2026-07-14T01:00:00Z", 30),
    ]
    result = timeseries_aggregate(data, window_size=3600, window_type="sliding", operation="mean")
    assert result["num_windows"] == 3  # One per data point

def test_empty_window():
    data = [
        ("2026-07-14T00:00:00Z", 10),
        ("2026-07-14T02:00:00Z", 20),  # Gap of 2 hours
    ]
    result = timeseries_aggregate(data, window_size=3600, operation="mean")
    # Middle window should have null value
    assert any(w["value"] is None for w in result["results"])

def test_variance():
    data = [
        ("2026-07-14T00:00:00Z", 10),
        ("2026-07-14T00:15:00Z", 20),
        ("2026-07-14T00:30:00Z", 30),
    ]
    result = timeseries_aggregate(data, window_size=3600, operation="variance")
    assert result["results"][0]["value"] > 0  # Non-zero variance

def test_entropy():
    data = [
        ("2026-07-14T00:00:00Z", 1),
        ("2026-07-14T00:15:00Z", 1),  # All same value
    ]
    result = timeseries_aggregate(data, window_size=3600, operation="entropy")
    assert result["results"][0]["value"] == 0  # Zero entropy for uniform distribution

def test_unsorted_data():
    data = [
        ("2026-07-14T01:00:00Z", 20),
        ("2026-07-14T00:00:00Z", 10),  # Out of order
    ]
    result = timeseries_aggregate(data, window_size=3600, operation="mean")
    assert result["status"] == "error"
    assert "not sorted" in result["reason"]

def test_invalid_timestamps():
    data = [("not-a-timestamp", 10)]
    result = timeseries_aggregate(data, window_size=3600, operation="mean")
    assert result["status"] == "error"
```

---

## CLI

```bash
# Fixed windows
python -m tools.timeseries aggregate \
  data.json \
  --window-size 3600 \
  --window-type fixed \
  --operation mean
# Output: JSON results

# Sliding windows
python -m tools.timeseries aggregate \
  data.json \
  --window-size 86400 \
  --window-type sliding \
  --operation entropy

# Example data.json
[
  ["2026-07-14T00:00:00Z", 42.5],
  ["2026-07-14T00:15:00Z", 43.2],
  ["2026-07-14T00:30:00Z", 41.9]
]
```

---

## Non-Goals

- **Forecasting/prediction:** No time-series models, no future extrapolation
- **Smoothing/filtering:** No moving average beyond windowing, no low-pass filters
- **Seasonal decomposition:** No detrending, no seasonal extraction
- **Real-time streaming:** No incremental updates; each call is batch
- **Timezone handling:** ISO UTC only; no timezone conversions

---

## Related Components

- **Log Parser** — provides raw time-series data
- **Anomaly Scorer** — can use entropy/variance thresholds to flag anomalies
- **Frequency Analysis** — complementary for distribution analysis
- **Dream Bucket** — tracks grain activation times, violation timestamps
- **Sleep pipeline** — uses windowed stats for drift detection
