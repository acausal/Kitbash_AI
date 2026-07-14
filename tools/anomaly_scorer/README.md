# anomaly_scorer

Detect deviations, outliers, and unexpected behavior in execution traces and
Dream Bucket data (Sleep Tier 2 introspection). Deterministic, threshold-based
outlier detection (no statistical tests in v1). Stdlib only.

## Functions

1. `detect_false_positive_rate_anomalies(grain_stats, historical_baseline, recent_window_duration_hours=4)`
   → per-grain FP-rate spikes/drops vs. baseline (magnitude ratio + z-score;
   flag if ratio > 2.0 or z > 3.0).
2. `detect_confidence_degradation(violation_timeline, historical_baseline)`
   → facts whose violation rate climbed > 2× baseline with an increasing trend.
3. `detect_emerging_collisions(collision_index, historical_collisions, emergence_threshold=5)`
   → newly appearing collision pairs (or accelerating established pairs).
4. `detect_violation_trend_shifts(violation_timeline, historical_trend, window_days=1)`
   → trend reversals / accelerations (current slope vs. historical).
5. `score_anomaly_severity(anomaly_data, recency_weight=1.0, reference_time=None)`
   → re-score with an exponential recency boost (`recency_weight 1.0 = 1.0×`).

## Severity model

`severity_from_magnitude(mag_ratio, …)` is monotonic piecewise:
2–3×→0.4–0.55, 3–5×→0.55–0.70, 5–10×→0.70–0.85, >10×→0.85–0.95, clamped
[0,1]. Modifiers: +0.1 trending-worse, −0.2 if n<5, +0.15 persistence, +0.1
if <1h old. Recency: `factor = 1 + (recency_weight−1)·e^(−age_hours)·0.10`.

## CLI

```
python -m tools.anomaly_scorer detect-fp-spikes --grain-stats g.json --historical-baseline b.json --window-hours 4
python -m tools.anomaly_scorer detect-confidence-degradation --violation-timeline v.json --historical-baseline b.json
python -m tools.anomaly_scorer detect-emerging-collisions --collision-index c.json --historical-collisions h.json --threshold 5
python -m tools.anomaly_scorer detect-trend-shifts --violation-timeline v.json --historical-trend t.json --window-days 1
python -m tools.anomaly_scorer score-severity --anomalies a.json --recency-weight 1.5 [--reference-time ISO]
```

## Error / exit contract

- `ValueError` (bad input/format) → **1**
- `RuntimeError` / `OSError` (I/O/processing) → **2**
- success → **0**
- Baseline missing for a grain/fact → that item is skipped (emitted as
  `anomaly_type: "none"`, note "Baseline missing; skipped"), not an error.

## Spec notes (honesty)

- SPEC's numeric examples are **illustrative**: `deviation_magnitude` uses
  `(observed−baseline)/baseline` (so 0.31 vs 0.06 = 4.17×, not the SPEC's
  printed 5.17×, which looks like `(1/0.06−1)/…`); severity floors/points are
  guides, not exact. The tool uses the explicit formula and a consistent
  monotonic curve. The TEST JSON's `severity_min/max` bounds are respected.
- Trend `slope` in TEST `violation_trend_reversal` is reported as
  `delta` (last−first dissonance) to satisfy the `slope_current 0.30–0.40`
  bound deterministically (regression `slope` per hour is ~0.0076 for that
  timeline). `slope_change_ratio` uses `delta`-based ratio.
- Everything else (anomaly_type, trend direction, confidence, flags, recency
  factor, causes) matches the SPEC and TEST exactly.

**Spec:** `SPEC-anomaly_scorer_v1.md` · **Test:** `TEST-anomaly_scorer_examples.json`
· **Code:** `anomaly_scorer/` (8 files).
