# SPEC: Positive Signal Scorer v1

**Module:** `tools/positive_signal_scorer/`  
**Status:** Ready for spec  
**Dependencies:** stdlib (json, statistics, collections, math)  
**Priority:** High (inverse of Anomaly Scorer; enables positive feedback calibration for sleep learning)

---

## Overview

Score discovered success patterns by measuring their signal strength, reliability, and predictiveness. Complement to Pattern Confidence Scorer (which validates patterns against traces), this tool ranks patterns by how "good" they are—measuring consistency, coverage, temporal stability, and likelihood of producing desired outcomes.

**Design principle:** Deterministic scoring of success patterns without statistical testing. Compute multiple signal dimensions (frequency, consistency, outcome correlation, temporal drift); emit ranked list with per-pattern scores.

**Use case:** "I discovered 47 success patterns. Which ones are most reliable and worth learning from? Rank them by signal strength so I know which to prioritize."

---

## Scope

### In Scope ✓
- Score success patterns from Success Pattern Miner on multiple dimensions:
  - Frequency (how many times did this pattern appear?)
  - Support (% of successful traces containing this pattern)
  - Outcome correlation (if pattern fires, how likely is success?)
  - Consistency (low variance in outcomes across occurrences)
  - Temporal stability (pattern appears consistently over time, not just recently)
  - Recency bonus/penalty (optional: weight recent patterns slightly higher)
- Composite scoring: combine dimensions into single "signal strength" metric [0, 1]
- Per-dimension breakdowns: emit score for each dimension separately
- Batch scoring of multiple patterns
- Ranking: sort patterns by composite score
- Confidence intervals: flag low-sample-size patterns ("weak signal")

### Out of Scope ✗
- Statistical significance testing (p-values, hypothesis tests)
- Causal analysis (why is this pattern successful?) — Causal Credit Attribution does this
- Pattern generation or discovery — Success Pattern Miner does this
- Predicting whether a future pattern will succeed — separate predictive tool
- Interactive visualization or REPL
- Hyperparameter tuning (metrics fixed for v1)

---

## Module Structure

```
tools/positive_signal_scorer/
  __init__.py                      # exports main functions
  core.py                          # scoring logic
  signal_dimensions.py             # frequency, support, outcome_correlation, consistency, temporal_stability
  composite_scoring.py             # combine dimensions into signal strength
  cli.py                           # argparse CLI
  scorer_schema.py                 # dataclasses for JSON output
  README.md                         # usage + examples
  __main__.py                      # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

All functions accept/return JSON-serializable types.

#### 1. `score_patterns(patterns: list, execution_traces: list, weights: dict = None) -> dict`

**Purpose:** Score success patterns on multiple signal dimensions.

**Input:**
- `patterns` (list): Success patterns from Success Pattern Miner:
  ```json
  [
    {
      "pattern_id": "succ_seq_001",
      "sequence": ["tokenizer", "negation_detector", "svo_extractor"],
      "frequency": 47,
      "support": 0.056,
      "coverage": 0.187
    }
  ]
  ```

- `execution_traces` (list): Execution traces for ground truth:
  ```json
  [
    {
      "trace_id": "tr_12345",
      "sequence": ["tokenizer", "negation_detector", "svo_extractor"],
      "outcome": "success",
      "error_signal": 0.05,
      "timestamp": "2026-07-14T10:30:00Z"
    }
  ]
  ```

- `weights` (dict, optional): Weights for each signal dimension. Default:
  ```json
  {
    "frequency": 0.15,
    "support": 0.15,
    "outcome_correlation": 0.35,
    "consistency": 0.20,
    "temporal_stability": 0.15
  }
  ```
  (all weights sum to 1.0)

**Output:**
```json
{
  "scoring_run_id": "pos_score_001",
  "timestamp": "2026-07-14T14:30:00Z",
  "patterns_scored": 12,
  "patterns": [
    {
      "pattern_id": "succ_seq_001",
      "pattern": ["tokenizer", "negation_detector", "svo_extractor"],
      "signal_strength": 0.87,
      "rank": 1,
      "signal_dimensions": {
        "frequency_score": 0.94,
        "support_score": 0.78,
        "outcome_correlation_score": 0.92,
        "consistency_score": 0.81,
        "temporal_stability_score": 0.85
      },
      "sample_size": 47,
      "sample_size_confidence": "adequate",
      "success_rate_given_pattern": 0.93,
      "coverage": 0.187,
      "notes": "Strong pattern; appears consistently across time period"
    },
    {
      "pattern_id": "succ_seq_002",
      "pattern": ["text_search", "json_filter"],
      "signal_strength": 0.71,
      "rank": 2,
      "signal_dimensions": {
        "frequency_score": 0.63,
        "support_score": 0.55,
        "outcome_correlation_score": 0.88,
        "consistency_score": 0.65,
        "temporal_stability_score": 0.72
      },
      "sample_size": 19,
      "sample_size_confidence": "low",
      "success_rate_given_pattern": 0.89,
      "coverage": 0.076,
      "notes": "Good signal but low sample size; monitor for confirmation"
    }
  ],
  "metadata": {
    "weights": {
      "frequency": 0.15,
      "support": 0.15,
      "outcome_correlation": 0.35,
      "consistency": 0.20,
      "temporal_stability": 0.15
    },
    "min_sample_size_for_adequate_confidence": 10
  }
}
```

#### 2. `compute_signal_dimension(patterns: list, traces: list, dimension: str) -> dict`

**Purpose:** Compute a single signal dimension across patterns (useful for debugging/analysis).

**Input:**
- `patterns` (list): Pattern list (same as above)
- `traces` (list): Execution traces
- `dimension` (str): One of `["frequency", "support", "outcome_correlation", "consistency", "temporal_stability"]`

**Output:**
```json
{
  "dimension": "outcome_correlation",
  "definition": "If pattern fires, how likely is success? Computed as: (traces where pattern AND success) / (traces where pattern fires)",
  "pattern_scores": [
    {
      "pattern_id": "succ_seq_001",
      "pattern": ["tokenizer", "negation_detector", "svo_extractor"],
      "score": 0.92,
      "numerator": 43,
      "denominator": 47
    }
  ]
}
```

---

## Signal Dimensions (Detailed)

### 1. Frequency Score
- **Definition:** How often does this pattern appear?
- **Calculation:** `min(frequency / median_frequency_across_patterns, 1.0)`
- **Range:** [0, 1]
- **Intuition:** Patterns appearing more frequently are more "proven" (more data)

### 2. Support Score
- **Definition:** What % of successful traces does this pattern appear in?
- **Calculation:** `support` (already provided in pattern)
- **Range:** [0, 1]
- **Intuition:** Patterns covering more successes are more generally useful

### 3. Outcome Correlation Score
- **Definition:** Given the pattern fires, what's the success rate?
- **Calculation:** `(traces where pattern AND success) / (traces where pattern fires)`
- **Range:** [0, 1]
- **Intuition:** High score = pattern strongly predicts success
- **Implementation:** Match pattern as contiguous subsequence in each trace

### 4. Consistency Score
- **Definition:** How stable is outcome across occurrences? (low variance = high consistency)
- **Calculation:** 
  - For each trace where pattern fires, record `error_signal`
  - Compute coefficient of variation (std_dev / mean) of error_signals
  - Score = `max(1.0 - cv, 0.0)` (clamped to [0, 1])
- **Range:** [0, 1]
- **Intuition:** High score = pattern reliably produces same outcome; low score = outcome varies wildly

### 5. Temporal Stability Score
- **Definition:** Does pattern success rate drift over time? (stable = high score)
- **Calculation:**
  - Partition traces into 3 equal time buckets (early, mid, late)
  - Compute outcome_correlation for each bucket
  - Score = `1.0 - (max_bucket_score - min_bucket_score)` (clamped to [0, 1])
- **Range:** [0, 1]
- **Intuition:** High score = pattern works consistently across time; low score = performance degraded/improved recently (potential drift or learning)

---

## Composite Scoring

**Signal Strength** = weighted average of all 5 dimensions:
```
signal_strength = (
    frequency_score * weight["frequency"] +
    support_score * weight["support"] +
    outcome_correlation_score * weight["outcome_correlation"] +
    consistency_score * weight["consistency"] +
    temporal_stability_score * weight["temporal_stability"]
)
```

Default weights (tuned for Kitbash learning loop):
- `outcome_correlation`: 0.35 (most important: does pattern predict success?)
- `consistency`: 0.20 (second most: is outcome stable?)
- `frequency`: 0.15 (third: how much evidence?)
- `support`: 0.15 (third: coverage of successes?)
- `temporal_stability`: 0.15 (last: is pattern still valid?)

**Confidence Level:**
- `adequate`: sample_size >= 10
- `low`: sample_size < 10
- `very_high`: sample_size >= 50

---

## CLI Interface

```bash
# Score all patterns with default weights
python -m tools.positive_signal_scorer \
  --patterns patterns.json \
  --traces traces.jsonl \
  --output scored_patterns.json

# Score with custom weights
python -m tools.positive_signal_scorer \
  --patterns patterns.json \
  --traces traces.jsonl \
  --weights-frequency 0.1 \
  --weights-outcome-correlation 0.4 \
  --weights-consistency 0.2 \
  --weights-support 0.2 \
  --weights-temporal-stability 0.1 \
  --output scored_patterns.json

# Compute single dimension
python -m tools.positive_signal_scorer \
  --patterns patterns.json \
  --traces traces.jsonl \
  --dimension outcome_correlation \
  --output dimension_scores.json
```

---

## Input/Output Formats

### Input
- `patterns`: JSON array or JSONL from Success Pattern Miner
- `traces`: JSONL or JSON array of execution traces
- Each trace must have: `trace_id`, `sequence` (or `grain_sequence`), `outcome`, `error_signal`, `timestamp`

### Output
- JSON object with `patterns` array, each containing per-dimension scores and composite `signal_strength`

---

## Implementation Notes

1. **Pattern matching:** Find pattern as contiguous subsequence in trace.sequence
2. **Outcome correlation:** Count (pattern AND success) / (pattern fires)
3. **Consistency:** Use coefficient of variation (std / mean) of error_signals for traces where pattern fires
4. **Temporal stability:** Partition by timestamp into 3 buckets; compare outcome_correlation per bucket
5. **Ranking:** Sort patterns by signal_strength descending; emit rank 1, 2, 3, etc.
6. **Confidence flag:** If sample_size < 10, emit `sample_size_confidence: "low"`
7. **Error handling:** Fail-loud on malformed JSON, missing required fields

---

## Error Semantics

- Exit 0: Success (patterns scored)
- Exit 1: ValueError (invalid input, missing fields)
- Exit 2: RuntimeError (I/O error, file not found)

---

## Testing Strategy

### Explicit Test Cases (in `TEST-positive_signal_scorer_examples.json`)

1. **High-signal pattern:** 50 traces, pattern appears 40 times with 39 successes → high outcome_correlation, high signal_strength
2. **Low-consistency pattern:** 20 traces, pattern appears 15 times but error_signal varies wildly → low consistency_score
3. **Temporal drift:** Pattern works well in early traces but fails in recent traces → low temporal_stability_score
4. **Low-sample-size flag:** Pattern appears only 5 times → confidence = "low"
5. **Custom weights:** Score with outcome_correlation weight = 0.5 → should dominate final score
6. **Single dimension:** Compute outcome_correlation only → detailed breakdown
7. **Empty patterns:** 0 patterns input → empty output (no error)

---

## Dependencies & Constraints

- **Python:** 3.8+
- **Imports:** json, statistics, collections, math, datetime
- **External libs:** None (stdlib only)
- **Resource limits:** Should handle 100+ patterns + 10K traces in <10 seconds
- **Hardware:** CPU-only

---

## Related Tools

- **Success Pattern Miner v1:** Discovers patterns (this tool ranks them)
- **Pattern Confidence Scorer v1:** Validates patterns against outcomes (different approach)
- **Anomaly Scorer v1:** Inverse (scores failure/anomaly patterns)
- **Causal Credit Attribution v1:** Explains why patterns are successful (separate tool)

---

## Non-Goals

- **Causality:** Scoring ≠ causation; Causal Credit Attribution handles attribution
- **Prediction:** This tool ranks discovered patterns; doesn't predict future patterns
- **Real-time streaming:** Batch processing only (v1)
- **Statistical testing:** No p-values, confidence intervals beyond "adequate / low" flags

---

**Last updated:** 2026-07-14  
**For:** Kitbash sleep pipeline (Tier 2 positive signal learning)  
**Related:** TOOL_PHILOSOPHY.md, Success Pattern Miner v1 spec, Anomaly Scorer v1 spec
