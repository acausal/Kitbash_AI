# SPEC: Anomaly Scorer v1

**Module:** `tools/anomaly_scorer/`  
**Status:** Ready for build  
**Dependencies:** stdlib (json, collections, math, statistics)  
**Priority:** High (completes Sleep Tier 2 introspection triad; feeds hypothesis generation)

---

## Overview

Detect deviations, outliers, and unexpected behavior patterns in execution traces and Dream Bucket data. Identify when reliable grains suddenly fail, when false positive rates spike, when new collisions emerge unexpectedly, or when violation patterns shift. Emit scored anomalies with severity levels and possible causes for Sleep Tier 2 investigation.

**Design principle:** Deterministic outlier detection against baselines. Compare current window vs. historical baseline; flag deviations > threshold as anomalies. No statistical tests (v1); just threshold-based comparison.

**Use case:** "Grain_42 had a 5% false positive rate for 10 days, then jumped to 31% in the last 4 hours. Anomaly Scorer should detect that spike, estimate severity (78%), and suggest possible causes."

---

## Scope

### In Scope ✓
- Detect false positive rate spikes (current vs. baseline)
- Detect confidence degradation (reliable facts now causing violations)
- Detect emerging collisions (new fact pairs colliding frequently in recent window)
- Detect violation timeline shifts (increasing/decreasing trends)
- Measure deviation magnitude (2x baseline? 10x?)
- Assign severity scores (0.0–1.0) based on magnitude and recency
- Suggest possible causes (search weight shift, query pattern change, data drift, etc.)
- Support multiple anomaly types: sudden_increase, sudden_decrease, trend_shift, emergence, decay
- Temporal analysis: compare recent window vs. historical baseline vs. previous anomalies
- Recency weighting (more recent anomalies ranked higher)
- Output: JSON with per-anomaly scores + aggregate statistics

### Out of Scope ✗
- Statistical significance testing (t-tests, p-values) — threshold-based only
- Causal inference (determining root cause) — only suggest possibilities
- Automated remediation (fixing detected anomalies)
- Prediction (forecasting future anomalies)
- Clustering similar anomalies (separate tool)
- Anomaly suppression (v2: anomaly filtering, annotation)

---

## Module Structure

```
tools/anomaly_scorer/
  __init__.py                    # exports main functions
  core.py                        # anomaly detection logic
  baselines.py                   # baseline computation and comparison
  severity_calculator.py         # scoring deviations by magnitude + recency
  cause_suggester.py             # heuristic cause suggestions
  cli.py                         # argparse CLI
  anomaly_schema.py              # dataclasses for JSON output
  README.md                       # usage docs + examples
  __main__.py                    # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

All functions accept/return JSON-serializable types (strings, dicts, lists).

#### 1. `detect_false_positive_rate_anomalies(grain_stats: dict, historical_baseline: dict, recent_window_duration_hours: int = 4) -> dict`

**Purpose:** Detect spikes/drops in false positive rates for specific grains.

**Input:**
- `grain_stats` (dict): Per-grain statistics from Dream Bucket, formatted as:
  ```json
  {
    "grain_42": {
      "fp_count": 12,
      "fp_rate": 0.31,
      "total_uses": 40,
      "most_confused_with": [137, 89],
      "window": "2026-07-14T10:00:00Z to 2026-07-14T14:00:00Z"
    },
    "grain_100": {
      "fp_count": 2,
      "fp_rate": 0.04,
      "total_uses": 50,
      "window": "2026-07-14T10:00:00Z to 2026-07-14T14:00:00Z"
    }
  }
  ```

- `historical_baseline` (dict): Per-grain baseline rates (from previous N days/weeks):
  ```json
  {
    "grain_42": {
      "mean_fp_rate": 0.06,
      "std_fp_rate": 0.02,
      "n_observations": 50,
      "period": "last_7_days"
    },
    "grain_100": {
      "mean_fp_rate": 0.04,
      "std_fp_rate": 0.01,
      "n_observations": 60
    }
  }
  ```

- `recent_window_duration_hours` (int): Duration of recent window (default: 4 hours for daytime anomaly detection)

**Output (JSON):**
```json
{
  "detection_params": {
    "anomaly_type": "false_positive_rate_spike",
    "recent_window_hours": 4,
    "baseline_period": "last_7_days",
    "severity_threshold": 0.4
  },
  "anomalies": [
    {
      "anomaly_id": "anom_grain_42_spike",
      "grain_id": 42,
      "anomaly_type": "sudden_increase_false_positives",
      "baseline_rate": 0.06,
      "observed_rate": 0.31,
      "deviation_magnitude": 5.17,
      "deviation_type": "sudden_increase",
      "severity": 0.78,
      "severity_factors": {
        "magnitude_ratio": 5.17,
        "above_std_deviations": 12.5,
        "recency_weight": 1.0,
        "sample_size_confidence": 0.95
      },
      "possible_causes": [
        "search_weight_shift",
        "query_pattern_change",
        "grain_confusion_emergence"
      ],
      "evidence": [
        "fp_rate_jumped_from_0.06_to_0.31",
        "12.5_standard_deviations_above_baseline",
        "most_confused_with_facts_137_89"
      ],
      "window": "2026-07-14T10:00:00Z to 2026-07-14T14:00:00Z",
      "recommendation": "Investigate grain_42's recent ternary deltas; check query patterns for shift"
    },
    {
      "anomaly_id": "anom_grain_100_stable",
      "grain_id": 100,
      "anomaly_type": "none",
      "baseline_rate": 0.04,
      "observed_rate": 0.04,
      "deviation_magnitude": 0.0,
      "severity": 0.0,
      "note": "No anomaly detected; within normal variation"
    }
  ],
  "aggregate_statistics": {
    "total_grains_analyzed": 2,
    "grains_with_anomalies": 1,
    "mean_severity": 0.78,
    "high_severity_count": 1
  }
}
```

**Behavior:**
- For each grain, compare observed_rate vs. baseline_rate (mean)
- Compute deviation magnitude: `(observed − baseline) / baseline` (ratio)
- Compute z-score: `(observed − baseline) / std_dev`
- Flag as anomaly if magnitude > 2.0 (e.g., 2x baseline) OR z-score > 3.0
- Assign severity: 0.4–1.0 based on magnitude ratio (2x=0.4, 5x=0.75, 10x+0.9)
- Apply recency weight: current hour anomalies score higher than 24h-old
- Suggest causes based on magnitude (small spike="transient noise", large="systematic change")

**Error handling:**
- `ValueError` if grain_stats format invalid
- `ValueError` if baseline missing for a grain (skip that grain, log warning)
- Handle division by zero (baseline_rate = 0 → treat as special case)

---

#### 2. `detect_confidence_degradation(violation_timeline: dict, historical_baseline: dict) -> dict`

**Purpose:** Detect when facts that were previously reliable now show increased violations.

**Input:**
- `violation_timeline` (dict): Per-fact violation data from Dream Bucket:
  ```json
  {
    "fact_42": {
      "total_violations": 23,
      "violation_rate": 0.15,
      "dissonance_types": {
        "high_confidence_low_coherence": 18,
        "context_switch_failure": 5
      },
      "timeline": [
        {"timestamp": "2026-07-14T10:00:00Z", "dissonance": 0.35},
        {"timestamp": "2026-07-14T12:00:00Z", "dissonance": 0.50},
        {"timestamp": "2026-07-14T14:00:00Z", "dissonance": 0.71}
      ]
    }
  }
  ```

- `historical_baseline` (dict): Per-fact baseline violation rates:
  ```json
  {
    "fact_42": {
      "mean_violation_rate": 0.04,
      "std_violation_rate": 0.02,
      "n_observations": 100,
      "period": "last_7_days",
      "reliability_label": "high"
    }
  }
  ```

**Output (JSON):**
```json
{
  "detection_params": {
    "anomaly_type": "confidence_degradation",
    "baseline_period": "last_7_days"
  },
  "anomalies": [
    {
      "anomaly_id": "anom_fact_42_degradation",
      "fact_id": 42,
      "anomaly_type": "confidence_degradation",
      "baseline_reliability": "high",
      "baseline_violation_rate": 0.04,
      "observed_violation_rate": 0.15,
      "violation_trend": "increasing",
      "trend_slope": 0.12,
      "severity": 0.65,
      "severity_factors": {
        "rate_increase_ratio": 3.75,
        "trend_direction": "increasing",
        "dissonance_types_involved": 2,
        "most_common_dissonance": "high_confidence_low_coherence"
      },
      "possible_causes": [
        "query_ambiguity_increase",
        "knowledge_base_drift",
        "context_confusion"
      ],
      "evidence": [
        "violation_rate_was_0.04_now_0.15",
        "violation_timeline_shows_increasing_trend",
        "recent_dissonance_spike_to_0.71"
      ],
      "recommendation": "Re-examine fact_42 with MTR layer; check for ternary delta drift"
    }
  ]
}
```

**Behavior:**
- Compare violation_rate vs. historical mean
- Compute trend from timeline (linear regression over timestamps)
- Flag as anomaly if violation_rate > 2x baseline OR trend is increasing with slope > threshold
- Assign severity based on rate increase + trend strength + dissonance type diversity
- Identify most common dissonance type (suggests the failure mode)
- Suggest causes matching dissonance pattern

**Error handling:**
- `ValueError` if timeline malformed
- `ValueError` if baseline missing (skip grain)
- Handle insufficient data (< 3 timeline points → can't compute trend)

---

#### 3. `detect_emerging_collisions(collision_index: dict, historical_collisions: dict, emergence_threshold: int = 5) -> dict`

**Purpose:** Identify newly emerging or rapidly growing collision pairs.

**Input:**
- `collision_index` (dict): Current collision pairs from Dream Bucket:
  ```json
  {
    "(42, 137)": {
      "collision_count": 47,
      "query_patterns": ["photosynthesis", "plant energy"],
      "avg_confidence_on_collision": 0.83,
      "first_observed": "2026-02-10T08:00:00Z",
      "last_observed": "2026-07-14T14:00:00Z"
    },
    "(42, 200)": {
      "collision_count": 2,
      "query_patterns": ["photosynthesis"],
      "avg_confidence_on_collision": 0.75,
      "first_observed": "2026-07-14T12:00:00Z",
      "last_observed": "2026-07-14T14:00:00Z"
    }
  }
  ```

- `historical_collisions` (dict): Collision pairs known from previous sleeps:
  ```json
  {
    "(42, 137)": {
      "total_all_time": 47,
      "baseline_rate_per_day": 2.1,
      "established_since": "2026-02-10T08:00:00Z"
    }
  }
  ```

- `emergence_threshold` (int): Collision count to flag as "emerging" (default: 5)

**Output (JSON):**
```json
{
  "detection_params": {
    "anomaly_type": "emerging_collisions",
    "emergence_threshold": 5
  },
  "anomalies": [
    {
      "anomaly_id": "anom_collision_42_200_emergence",
      "anomaly_type": "collision_emergence",
      "collision_pair": [42, 200],
      "collision_count": 2,
      "observation_window": "last_2_hours",
      "emergence_confidence": 0.55,
      "severity": 0.45,
      "severity_factors": {
        "collision_count_below_threshold": true,
        "recency_of_first_observation": "2_hours",
        "rate_acceleration": "unknown (too recent)",
        "shared_query_patterns": ["photosynthesis"]
      },
      "possible_causes": [
        "new_collision_pair_emerging",
        "query_pattern_drift",
        "grain_weight_rebalancing"
      ],
      "evidence": [
        "collision_pair_42_200_is_new_in_last_2_hours",
        "collision_count_2_approaching_threshold_5",
        "both_grains_involved_in_photosynthesis_queries"
      ],
      "recommendation": "Monitor collision_42_200 for rapid growth; may indicate emerging structural similarity"
    },
    {
      "anomaly_id": "anom_collision_42_137_stable",
      "anomaly_type": "none",
      "collision_pair": [42, 137],
      "collision_count": 47,
      "established_since": "2026-02-10",
      "note": "Established collision pair; no emergence anomaly"
    }
  ]
}
```

**Behavior:**
- Identify collision pairs in current index NOT in historical (emerging)
- For emerging pairs, count collisions; if < threshold, lower confidence (watch threshold)
- Compute rate acceleration if enough history (is this pair colliding faster recently?)
- Look for shared query patterns across pairs in collision cluster
- Assign severity based on: collision count (closer to threshold=higher), recency (newer=higher), pattern overlap (more=higher)

**Error handling:**
- `ValueError` if collision_index format invalid
- Handle missing historical baseline (treat as truly new collision)
- Skip if collision count < 1

---

#### 4. `detect_violation_trend_shifts(violation_timeline: dict, historical_trend: dict, window_days: int = 1) -> dict`

**Purpose:** Detect increasing/decreasing trends in violation rates over time.

**Input:**
- `violation_timeline` (dict): Same as detect_confidence_degradation input (with timeline array)
- `historical_trend` (dict): Previous trend statistics:
  ```json
  {
    "fact_42": {
      "mean_daily_violations": 1.2,
      "trend_direction": "stable",
      "last_7_day_slope": 0.01,
      "last_update": "2026-07-13T23:00:00Z"
    }
  }
  ```
- `window_days` (int): How many days back to analyze for trend (default: 1 day)

**Output (JSON):**
```json
{
  "detection_params": {
    "anomaly_type": "violation_trend_shift",
    "window_days": 1
  },
  "anomalies": [
    {
      "anomaly_id": "anom_fact_42_trend_shift",
      "fact_id": 42,
      "anomaly_type": "trend_shift",
      "previous_trend": "stable",
      "current_trend": "increasing",
      "slope_previous_day": 0.01,
      "slope_current_window": 0.35,
      "slope_change_ratio": 35.0,
      "severity": 0.72,
      "severity_factors": {
        "trend_reversal": true,
        "slope_acceleration_ratio": 35.0,
        "current_trend_strength": "strong"
      },
      "possible_causes": [
        "systematic_knowledge_base_change",
        "query_distribution_shift",
        "coherence_degradation"
      ],
      "evidence": [
        "trend_changed_from_stable_to_increasing",
        "slope_increased_35x_in_24_hours",
        "violations_climbing_steadily_since_2026_07_14T10_00"
      ],
      "recommendation": "Investigate what changed 24h ago; check MTR state updates and query pattern shifts"
    }
  ]
}
```

**Behavior:**
- Extract timeline array; compute linear regression over recent window
- Compare current slope vs. historical baseline slope
- Flag as anomaly if: slope reversal (was negative, now positive), or acceleration (current slope > 3x historical)
- Assign severity based on slope magnitude and reversal significance

**Error handling:**
- `ValueError` if timeline has < 3 points (can't compute trend)
- Handle missing historical trend (treat as unknown baseline)

---

#### 5. `score_anomaly_severity(anomaly_data: dict, recency_weight: float = 1.0) -> dict`

**Purpose:** Re-score anomaly severity with optional recency weighting (for late-run rescoring).

**Input:**
- `anomaly_data` (dict): Output from any detect_* function
- `recency_weight` (float): Weight for recency (1.0 = no extra weight; 2.0 = double weight to recent anomalies)

**Output (JSON):**
```json
{
  "rescored_anomalies": [
    {
      "anomaly_id": "anom_grain_42_spike",
      "original_severity": 0.78,
      "recency_adjusted_severity": 0.82,
      "timestamp": "2026-07-14T14:00:00Z",
      "age_hours": 0.5,
      "recency_factor": 1.05
    }
  ]
}
```

**Behavior:**
- Apply exponential recency decay: `age_minutes / 60` hours → recent anomalies boosted
- Recency_adjusted_severity = min(1.0, original_severity × recency_factor)

**Error handling:**
- `ValueError` if anomaly_data missing required fields

---

### CLI Interface (in `cli.py`)

```bash
# Detect false positive rate spikes
python -m tools.anomaly_scorer detect-fp-spikes \
  --grain-stats grain_stats.json \
  --historical-baseline baseline.json \
  --window-hours 4

# Detect confidence degradation
python -m tools.anomaly_scorer detect-confidence-degradation \
  --violation-timeline violations.json \
  --historical-baseline baseline.json

# Detect emerging collisions
python -m tools.anomaly_scorer detect-emerging-collisions \
  --collision-index collisions.json \
  --historical-collisions historical.json \
  --threshold 5

# Detect violation trends
python -m tools.anomaly_scorer detect-trend-shifts \
  --violation-timeline violations.json \
  --historical-trend trend_history.json \
  --window-days 1

# Score/re-score anomalies with recency
python -m tools.anomaly_scorer score-severity \
  --anomalies detected_anomalies.json \
  --recency-weight 1.5
```

**Output:** JSON to stdout (one object per command)

**Exit codes:**
- `0`: Success
- `1`: ValueError (invalid input/format)
- `2`: RuntimeError (I/O or processing error)

---

## Anomaly Types & Severity Scoring

### Anomaly Types

| Type | Trigger | Severity Range |
|------|---------|-----------------|
| `sudden_increase_false_positives` | FP rate > 2x baseline | 0.4–1.0 |
| `sudden_decrease_false_positives` | FP rate < 0.5x baseline | 0.3–0.8 |
| `confidence_degradation` | Violation rate > 2x baseline + increasing trend | 0.4–1.0 |
| `collision_emergence` | New collision pair, count > threshold | 0.3–0.9 |
| `collision_acceleration` | Established pair, recent rate 2x+ previous | 0.4–0.9 |
| `trend_shift` | Slope reversal or 3x+ acceleration | 0.5–1.0 |
| `violation_acceleration` | Violation timeline shows steep slope | 0.4–0.9 |

### Severity Calculation

```
Base severity from magnitude:
  - magnitude 2x–3x baseline   → 0.4
  - magnitude 3x–5x baseline   → 0.6
  - magnitude 5x–10x baseline  → 0.8
  - magnitude > 10x baseline   → 0.9
  - severity = min(1.0, 0.3 + (log10(magnitude) * 0.25))

Modifiers:
  + Recency: anomalies < 1h ago +0.1
  + Trend strength: if trending worse +0.1
  + Sample size confidence: if n < 5 observations -0.2
  + Persistence: if same anomaly detected previously +0.15

Final: clamp to [0.0, 1.0]
```

---

## Cause Suggestion Heuristics

| Observation | Suggested Causes |
|-------------|-----------------|
| FP rate spike + high magnitude | search_weight_shift, grain_confusion_emergence, query_ambiguity_increase |
| FP rate spike + low magnitude | transient_noise, sampling_variance |
| Confidence degradation + trending worse | knowledge_base_drift, query_distribution_shift, context_confusion |
| New collision pair | grain_structural_similarity_emergence, query_pattern_concentration |
| Established pair accelerating | search_reweighting, ternary_delta_change |
| Violation trend reversal | systematic_kb_change, coherence_degradation, epistemological_layer_shift |

---

## Integration Points

**Upstream (provides data):**
- Dream Bucket (false_positives.jsonl, collisions.jsonl, violations.jsonl)
- Sleep Stage 1 outputs (collision_index.json, false_positive_by_grain.json, violation_timeline.json)
- Historical baseline indices (from previous sleeps)

**Downstream (consumes output):**
- Sleep Stage 3: Hypothesis Generation (feeds collision_clusters.json + anomaly_timeline.json)
- Sleep Stage 4: Question Generation (uses anomalies to prioritize questions)
- Pattern Explainer (explains why anomalies matter)

---

## Data Flow Example

```
Sleep Stage 1 outputs:
  false_positive_by_grain.json: grain_42.fp_rate = 0.31 (last 4 hours)
  violation_timeline.json: fact_42.violations trending up
  collision_index.json: new pair (42, 200) with count = 2

Historical baseline (from last 7 days):
  grain_42.baseline_fp_rate = 0.06
  fact_42.baseline_violation_rate = 0.04
  collision (42, 200) = does not exist

↓ anomaly_scorer.detect_false_positive_rate_anomalies()

Output:
  - grain_42: 5.17x spike, severity 0.78 → "sudden_increase_false_positives"
  - Suggested causes: search_weight_shift, query_pattern_change

↓ anomaly_scorer.detect_confidence_degradation()

Output:
  - fact_42: violation_rate 3.75x baseline, trend increasing → severity 0.65

↓ anomaly_scorer.detect_emerging_collisions()

Output:
  - (42, 200): count=2, emerging, confidence=0.55 → "collision_emergence"

↓ Sleep Stage 2 summary:

anomaly_timeline.json:
  [
    {"anomaly_type": "sudden_increase_false_positives", "grain_id": 42, "severity": 0.78},
    {"anomaly_type": "confidence_degradation", "fact_id": 42, "severity": 0.65},
    {"anomaly_type": "collision_emergence", "collision_pair": [42, 200], "severity": 0.45}
  ]

↓ Sleep Stage 3: Hypothesis Generation

Generates hypotheses:
  - "grain_42's false positive rate spiked; possible search weight rebalancing"
  - "fact_42 reliability dropped; investigate MTR coherence"
  - "collision (42, 200) may represent emerging structural similarity"
```

---

## Testing Strategy

### Test Cases

1. **Simple FP rate spike:**
   - Baseline: 0.05, Observed: 0.15 (3x)
   - Expected: severity ~0.5–0.6, flag as `sudden_increase_false_positives`

2. **Confidence degradation with increasing trend:**
   - Baseline violation rate: 0.04, Observed: 0.15
   - Timeline shows: 0.05 → 0.08 → 0.15 (clear increase)
   - Expected: severity ~0.65, trend `increasing`, flag degradation

3. **Emerging collision (low count):**
   - Collision (42, 200) count = 2, threshold = 5
   - Expected: severity ~0.45, confidence ~0.55, flag `collision_emergence`, recommendation to monitor

4. **Established collision (stable):**
   - Collision (42, 137) count = 47, established 10 days ago
   - Expected: no anomaly, severity 0.0

5. **Trend shift (reversal):**
   - Previous slope: 0.01 (stable), Current slope: 0.35 (increasing)
   - Expected: severity ~0.72, flag `trend_shift`, cause = "systematic_kb_change"

6. **Recency weight boost:**
   - Original severity 0.78, age = 0.5 hours
   - Recency weight 1.5 applied
   - Expected: adjusted_severity = min(1.0, 0.78 × 1.05) ≈ 0.82

### Example Test File (TEST-anomaly_scorer_examples.json)

```json
{
  "test_cases": [
    {
      "name": "fp_rate_spike",
      "grain_id": 42,
      "baseline_rate": 0.05,
      "observed_rate": 0.15,
      "expected_output": {
        "anomaly_type": "sudden_increase_false_positives",
        "severity_min": 0.5,
        "severity_max": 0.65
      }
    },
    {
      "name": "confidence_degradation_with_trend",
      "fact_id": 42,
      "baseline_violation_rate": 0.04,
      "observed_violation_rate": 0.15,
      "timeline": [
        {"timestamp": "2026-07-14T10:00:00Z", "dissonance": 0.05},
        {"timestamp": "2026-07-14T12:00:00Z", "dissonance": 0.08},
        {"timestamp": "2026-07-14T14:00:00Z", "dissonance": 0.15}
      ],
      "expected_output": {
        "anomaly_type": "confidence_degradation",
        "trend": "increasing",
        "severity_min": 0.60,
        "severity_max": 0.70
      }
    }
  ]
}
```

---

## Non-Goals

- ❌ Statistical hypothesis testing (p-values, confidence intervals)
- ❌ Causal inference (determining root cause, not suggesting)
- ❌ Automated anomaly suppression (v2 feature)
- ❌ Anomaly clustering/grouping (separate tool)
- ❌ Forecasting (predicting future anomalies)

---

## Dependencies

| Package | Version | Purpose | Notes |
|---------|---------|---------|-------|
| stdlib | — | json, collections, math, statistics | No external deps |

**No external libraries needed. Pure Python stdlib.**

---

## Future Enhancements (Post-1.0)

1. **v1.1: Adaptive baselines** — Update historical baselines as data ages (exponential decay)
2. **v1.2: Anomaly persistence** — Track which anomalies recur across multiple sleeps (systemic vs. transient)
3. **v2.0: Causal scoring** — Use ablation analysis to narrow down root causes
4. **v2.0: Anomaly suppression** — Allow Sleep process to annotate known-benign anomalies
5. **v2.1: Multi-modal detection** — Combine multiple anomaly signals (e.g., FP spike + violation increase = high confidence)

---

**Last updated:** 2026-07-14  
**Author:** Isaac (Kitbash AI)  
**For:** tools/ ecosystem, Sleep Tier 2 introspection  
**Related:** SLEEP_METABOLISM_SPEC.md, DREAM_BUCKET_DESIGN.md, PATTERN_CONFIDENCE_SCORER_SPEC.md
