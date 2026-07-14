# timeseries_windowed_operations

Aggregate time-series data over fixed or sliding windows. Used for Dream Bucket
statistics, grain activation patterns, drift monitoring, trend detection.
`tools.timeseries_windowed_operations`.

## Interface

```python
timeseries_aggregate(
    [("2026-07-14T00:00:00Z", 10), ("2026-07-14T00:30:00Z", 20), ...],
    window_size=3600, window_type="fixed", operation="mean")
# {"status":"success","results":[{"window_start":...,"window_end":...,"value":15.0,"count":2},...],...}
```

| Function | Purpose |
|----------|---------|
| `timeseries_aggregate(data, window_size, window_type="fixed", operation="mean", start_time=None, end_time=None)` | Windowed aggregation; return result/error dict |

**Operations:** mean, sum, median, min, max, count, variance, entropy (Shannon).
**Windows:** `fixed` (non-overlapping buckets from start), `sliding` (one window
per point over `[ts - window_size, ts]`). Empty windows have `value: null` but
are still emitted. ISO UTC only; data must be sorted ascending (else error).
Errors returned as dicts, never raised.

## CLI

```bash
python -m tools.timeseries_windowed_operations aggregate data.json \
  --window-size 3600 --window-type fixed --operation mean
```

`data.json` = JSON array of `[timestamp, value]`. JSON to stdout, summary to
stderr. Exit 0 = success, 1 = error. Pure stdlib; same `PYTHONPATH= ` prefix
rule in the Kitbash `.venv`.

**Spec:** `SPEC-timeseries_windowed_operations_v1.md` · **Test:** `TEST-timeseries_windowed_operations_examples.json`
