# SPEC: Pattern Confidence Scorer v1

**Module:** `tools/pattern_confidence_scorer/`  
**Status:** Ready for build  
**Dependencies:** stdlib (json, collections, math, statistics)  
**Priority:** High (feeds sleep Tier 2 pattern ranking; enables meta-learning on discovered patterns)

---

## Overview

Measure the reliability and predictive power of discovered patterns (tool sequences, collision chains, grain co-occurrences) by comparing them against ground-truth observations from the Dream Bucket. Emit confidence scores (precision, recall, F1, reliability) that help Sleep Tier 2 decide which patterns merit investigation or refinement.

**Design principle:** Deterministic scoring of patterns against outcomes. No statistical tests (v1); just count successes/failures and compute standard metrics. Flexible input: accept patterns + traces, or raw Dream Bucket observations, or both.

**Use case:** "Sleep Tier 2 discovered that tool_sequence [tokenizer → negation_detector → svo_extractor] appears 47 times. How reliable is it? Score it against my execution traces and tell me: precision, recall, false positive rate."

---

## Scope

### In Scope ✓
- Score individual patterns (sequences, collisions, grain chains) against execution traces or Dream Bucket observations
- Compute standard metrics: precision, recall, F1, true positive rate, false positive rate, specificity
- Measure pattern coverage (how many observations does this pattern explain?)
- Measure pattern predictiveness (if pattern fires, does predicted outcome occur?)
- Confidence intervals or reliability flags (e.g., "low sample size" warnings)
- Support multiple pattern sources: Sequence Pattern Miner output, collision clusters, procedural edges, grain co-occurrence rules
- Time-series confidence decay (optional: older observations weighted less)
- Output: JSON with per-pattern scores + aggregate statistics
- Batch scoring (accept multiple patterns, score all at once)

### Out of Scope ✗
- Statistical significance testing (p-values, hypothesis tests) — v1 is descriptive only
- Causal inference (pattern A causes outcome B) — can't determine causation from observations
- Ablation analysis (which elements of pattern are necessary?) — separate tool
- Pattern generation (create new patterns) — Sequence Pattern Miner does this
- Interactive visualization or REPL
- Hyperparameter tuning (fixed metrics for v1)

---

## Module Structure

```
tools/pattern_confidence_scorer/
  __init__.py                    # exports main functions
  core.py                        # scoring logic
  metrics.py                     # precision, recall, F1, etc.
  pattern_matching.py            # match patterns against observations
  cli.py                         # argparse CLI
  scorer_schema.py               # dataclasses for JSON output
  README.md                       # usage docs + examples
  __main__.py                    # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

All functions accept/return JSON-serializable types (strings, dicts, lists).

#### 1. `score_patterns_against_traces(patterns: list, traces: list, pattern_type: str = "sequence") -> dict`

**Purpose:** Score discovered patterns against execution traces with known outcomes.

**Input:**
- `patterns` (list): Pattern objects from Sequence Pattern Miner, each containing:
  ```json
  {
    "pattern_id": "seq_001",
    "sequence": ["tokenizer", "negation_detector", "svo_extractor"],
    "frequency": 47,
    "min_frequency_threshold": 3
  }
  ```
  OR (for collision patterns):
  ```json
  {
    "pattern_id": "coll_001",
    "collision_pair": [42, 137],
    "collision_count": 23,
    "avg_query_distance": 0.12
  }
  ```

- `traces` (list): Execution traces with outcomes, each containing:
  ```json
  {
    "trace_id": "tr_12345",
    "sequence": ["tokenizer", "negation_detector", "svo_extractor", "json_filter"],
    "outcome": "success",
    "timestamp": "2026-07-14T10:30:00Z",
    "error_signal": 0.0
  }
  ```
  OR (for collision observations):
  ```json
  {
    "trace_id": "tr_12346",
    "returned_id": 42,
    "correct_id": 137,
    "returned_confidence": 0.87,
    "outcome": "false_positive",
    "timestamp": "2026-07-14T10:31:00Z"
  }
  ```

- `pattern_type` (str): Type of pattern being scored: `"sequence"`, `"collision"`, `"grain_chain"` (default: `"sequence"`)

**Output (JSON):**
```json
{
  "scoring_params": {
    "pattern_type": "sequence",
    "total_patterns_scored": 12,
    "total_traces_used": 250,
    "timestamp_generated": "2026-07-14T14:30:00Z"
  },
  "pattern_scores": [
    {
      "pattern_id": "seq_001",
      "pattern": ["tokenizer", "negation_detector", "svo_extractor"],
      "pattern_frequency_in_data": 47,
      "metrics": {
        "precision": 0.89,
        "recall": 0.76,
        "f1_score": 0.82,
        "true_positive_rate": 0.76,
        "false_positive_rate": 0.11,
        "specificity": 0.98,
        "support": 47
      },
      "interpretation": {
        "reliability": "high",
        "confidence_flag": "none",
        "sample_size_note": "n=47 (sufficient)"
      },
      "details": {
        "true_positives": 36,
        "false_positives": 4,
        "true_negatives": 195,
        "false_negatives": 11,
        "total_observations": 246
      }
    },
    {
      "pattern_id": "seq_002",
      "pattern": ["json_filter", "text_search"],
      "pattern_frequency_in_data": 8,
      "metrics": {
        "precision": 0.75,
        "recall": 0.50,
        "f1_score": 0.60,
        "true_positive_rate": 0.50,
        "false_positive_rate": 0.25,
        "specificity": 0.90,
        "support": 8
      },
      "interpretation": {
        "reliability": "medium",
        "confidence_flag": "low_sample_size",
        "sample_size_note": "n=8 (recommend n≥20 for reliable scoring)"
      },
      "details": {
        "true_positives": 4,
        "false_positives": 1,
        "true_negatives": 181,
        "false_negatives": 4,
        "total_observations": 190
      }
    }
  ],
  "aggregate_statistics": {
    "mean_precision": 0.82,
    "mean_recall": 0.63,
    "mean_f1": 0.71,
    "patterns_with_high_confidence": 8,
    "patterns_with_low_sample_size": 4,
    "patterns_with_low_reliability": 0
  }
}
```

**Behavior:**
- Match each pattern against all traces (substring/sequence matching for sequences; ID matching for collisions)
- Count true positives (pattern fires, outcome is success/correct)
- Count false positives (pattern fires, outcome is failure/incorrect)
- Count true negatives (pattern doesn't fire, outcome is correct)
- Count false negatives (pattern doesn't fire, outcome fails anyway)
- Compute precision, recall, F1, TPR, FPR, specificity
- Flag low sample size (n < 20) with confidence_flag: `"low_sample_size"`
- Flag high FP rate (> 0.3) with confidence_flag: `"high_false_positive_rate"`
- Assign reliability level: "high" (F1 ≥ 0.75), "medium" (0.5–0.75), "low" (< 0.5)

**Error handling:**
- `ValueError` if pattern_type not recognized
- `ValueError` if traces list is empty
- `RuntimeError` if pattern matching fails

---

#### 2. `score_patterns_against_dream_bucket(patterns: list, dream_bucket_file: str, pattern_type: str = "sequence") -> dict`

**Purpose:** Score patterns against raw Dream Bucket observations (false positives, collisions, violations).

**Input:**
- `patterns` (list): Pattern objects (same format as above)
- `dream_bucket_file` (str): Path to Dream Bucket JSONL file (one observation per line)
  ```jsonl
  {"type": "false_positive", "returned_id": 42, "correct_id": 137, "returned_confidence": 0.87, "error_signal": 0.31, "timestamp": "2026-07-14T10:30:00Z"}
  {"type": "collision_cluster", "pivot_id": 42, "collision_ids": [137, 89], "collision_count": 47, "timestamp": "2026-07-14T10:31:00Z"}
  {"type": "consistency_violation", "returned_fact_id": 42, "mtr_error_signal": 0.71, "timestamp": "2026-07-14T10:32:00Z"}
  ```
- `pattern_type` (str): Type of pattern (default: `"sequence"`)

**Output (JSON):**
```json
{
  "scoring_params": {
    "pattern_type": "sequence",
    "total_patterns_scored": 12,
    "total_observations_used": 523,
    "observation_types": ["false_positive", "collision_cluster", "consistency_violation"],
    "timestamp_generated": "2026-07-14T14:30:00Z"
  },
  "pattern_scores": [
    {
      "pattern_id": "seq_001",
      "pattern": ["tokenizer", "negation_detector", "svo_extractor"],
      "observation_count": 47,
      "metrics": {
        "precision": 0.89,
        "recall": 0.76,
        "f1_score": 0.82,
        "false_positive_rate": 0.11,
        "observation_support": 47
      },
      "interpretation": {
        "reliability": "high",
        "confidence_flag": "none"
      }
    }
  ],
  "aggregate_statistics": {
    "mean_precision": 0.82,
    "mean_recall": 0.63,
    "patterns_explaining_observations": 11,
    "unexplained_observations": 12
  }
}
```

**Behavior:**
- Parse Dream Bucket JSONL; extract relevant observations for pattern type
- For sequence patterns: match against observation sequences
- For collision patterns: match against collision_cluster observations
- Compute same metrics as `score_patterns_against_traces()`
- Report how many observations each pattern explains
- Flag unexplained observations (anomalies not covered by any pattern)

**Error handling:**
- `FileNotFoundError` if dream_bucket_file not found
- `ValueError` if JSONL is malformed
- `IOError` if file not readable

---

#### 3. `compare_pattern_reliability(patterns: list, traces_file: str = None, dream_bucket_file: str = None) -> dict`

**Purpose:** Score patterns against both traces AND Dream Bucket; compare results.

**Input:**
- `patterns` (list): Pattern objects
- `traces_file` (str, optional): Path to traces JSONL
- `dream_bucket_file` (str, optional): Path to Dream Bucket JSONL

**Output (JSON):**
```json
{
  "comparison": {
    "scoring_methods": ["traces", "dream_bucket"],
    "timestamp_generated": "2026-07-14T14:30:00Z"
  },
  "scores_from_traces": { /* same as score_patterns_against_traces() output */ },
  "scores_from_dream_bucket": { /* same as score_patterns_against_dream_bucket() output */ },
  "agreement_analysis": {
    "patterns_with_consistent_scores": 10,
    "patterns_with_divergent_scores": 2,
    "mean_score_divergence": 0.08,
    "note": "High agreement (95%) suggests robust scoring across data sources"
  }
}
```

**Behavior:**
- If both files provided: score against each, compare results
- If only one provided: fall back to that method
- Compute divergence (difference in F1, precision, etc.) for each pattern
- Flag patterns with large divergence (possible data quality issues)

**Error handling:**
- `ValueError` if neither file provided
- Graceful fallback if one file missing

---

#### 4. `decay_confidence_by_age(pattern_scores: dict, decay_factor: float = 0.99, reference_date: str = None) -> dict`

**Purpose:** (Optional) Adjust pattern confidence scores based on age. Older observations get lower weight.

**Input:**
- `pattern_scores` (dict): Output from `score_patterns_against_traces()` or similar
- `decay_factor` (float): Exponential decay rate per day (default: 0.99 = 1% decay/day)
- `reference_date` (str): ISO 8601 date to use as "now" (default: current date)

**Output (JSON):**
```json
{
  "decay_params": {
    "decay_factor": 0.99,
    "reference_date": "2026-07-14",
    "oldest_observation_age_days": 30
  },
  "decayed_pattern_scores": [
    {
      "pattern_id": "seq_001",
      "original_f1": 0.82,
      "decayed_f1": 0.80,
      "age_weight": 0.74,
      "observation_dates": {
        "newest": "2026-07-14",
        "oldest": "2026-06-14"
      }
    }
  ]
}
```

**Behavior:**
- Extract timestamps from observations in pattern_scores
- Calculate age of each observation (reference_date - observation date)
- Apply decay: `new_score = old_score * (decay_factor ^ age_days)`
- Re-compute aggregate metrics with decay-weighted observations

**Error handling:**
- `ValueError` if decay_factor not 0–1
- `ValueError` if reference_date not valid ISO 8601

---

### CLI Interface (in `cli.py`)

```bash
# Score patterns against traces
python -m tools.pattern_confidence_scorer score-traces \
  --patterns patterns.json \
  --traces traces.jsonl \
  --pattern-type sequence

# Score patterns against Dream Bucket
python -m tools.pattern_confidence_scorer score-dream-bucket \
  --patterns patterns.json \
  --dream-bucket dream_bucket.jsonl \
  --pattern-type collision

# Compare both sources
python -m tools.pattern_confidence_scorer compare \
  --patterns patterns.json \
  --traces traces.jsonl \
  --dream-bucket dream_bucket.jsonl

# Apply decay
python -m tools.pattern_confidence_scorer decay \
  --scores scored_patterns.json \
  --decay-factor 0.99 \
  --reference-date 2026-07-14
```

**Output:** JSON to stdout (one object per command)

**Exit codes:**
- `0`: Success
- `1`: ValueError (invalid input/format)
- `2`: RuntimeError (I/O or processing error)

---

## Metrics Definitions

### Precision
**Formula:** TP / (TP + FP)  
**Meaning:** Of all times pattern fired, how often was outcome correct?  
**Interpretation:** High precision = few false alarms; pattern is trustworthy when it fires.

### Recall
**Formula:** TP / (TP + FN)  
**Meaning:** Of all correct outcomes, how often did pattern fire?  
**Interpretation:** High recall = pattern catches most successes; good coverage.

### F1 Score
**Formula:** 2 × (Precision × Recall) / (Precision + Recall)  
**Meaning:** Harmonic mean of precision and recall.  
**Interpretation:** Balanced measure of overall reliability; good summary metric.

### True Positive Rate (Sensitivity)
**Formula:** TP / (TP + FN)  
**Meaning:** Same as recall; probability of pattern firing given outcome is correct.

### False Positive Rate
**Formula:** FP / (FP + TN)  
**Meaning:** Of all incorrect outcomes, how often did pattern incorrectly fire?  
**Interpretation:** Low FPR = pattern doesn't fire on garbage; safe to trust.

### Specificity
**Formula:** TN / (TN + FP)  
**Meaning:** Of all incorrect outcomes, how often does pattern correctly NOT fire?  
**Interpretation:** High specificity = pattern avoids false alarms.

### Support
**Formula:** TP + FP  
**Meaning:** Total number of observations where pattern fired.  
**Interpretation:** Sample size; use to assess reliability confidence.

---

## Confidence Flags

Patterns are flagged if they don't meet minimum reliability thresholds:

| Flag | Condition | Action |
|------|-----------|--------|
| `low_sample_size` | Support < 20 | Include in results; mark unreliable |
| `high_false_positive_rate` | FPR > 0.3 | Include in results; warn on use |
| `high_false_negative_rate` | FNR > 0.4 | Include in results; pattern has poor coverage |
| `low_f1_score` | F1 < 0.5 | Mark as "low" reliability |
| `data_quality_issue` | Divergence > 0.25 between sources | Flag for investigation |

**Recommendation:** Sleep Tier 2 should skip patterns with `low_sample_size` flag (n < 20) until more data accumulates.

---

## Pattern Matching Strategy

### For Sequence Patterns
**Exact match:** Pattern sequence must appear as contiguous subsequence in trace sequence.

Example:
- Pattern: `[tokenizer, negation_detector, svo_extractor]`
- Trace: `[tokenizer, negation_detector, svo_extractor, json_filter, text_search]`
- Match: YES (pattern is prefix of trace)

- Trace: `[tokenizer, svo_extractor, negation_detector, json_filter]`
- Match: NO (order differs)

### For Collision Patterns
**ID match:** Pattern (returned_id, correct_id) pair must appear in collision observations.

Example:
- Pattern: `collision_pair: [42, 137]`
- Observation: `returned_id: 42, correct_id: 137`
- Match: YES

### For Grain Chains
**Grain presence match:** All grains in pattern must fire in trace execution.

Example:
- Pattern: `[grain_42, grain_137]`
- Trace grain sequence: `[grain_100, grain_42, grain_50, grain_137]`
- Match: YES (both grains present, order preserved)

---

## Safety & Validation

**Filesystem:**
- Read patterns from `workspace/` or `inbox/trusted/` only
- Read traces/Dream Bucket from `workspace/` only
- Write results to `workspace/` or `outbox/` (use `tools/filesystem_access/`)

**Error handling:**
- Fail-loud on invalid input (don't silently degrade)
- Validate pattern structure before scoring
- Log all scoring operations to audit trail

**Reproducibility:**
- Same patterns + traces → same scores, always
- No randomness; deterministic metrics

---

## Integration Points

**Upstream (provides patterns):**
- Sequence Pattern Miner (tool sequences, n-grams)
- Conditional Pattern Detector (contextual patterns)
- Sleep Tier 2 pattern extraction (collision clusters, procedural edges)

**Upstream (provides observations):**
- Dream Bucket (false positives, collisions, violations)
- Execution trace logs (success/failure outcomes)

**Downstream (consumes scores):**
- Sleep Tier 2 (pattern ranking, meta-learning decisions)
- Anomaly Scorer (detect unreliable patterns)
- Pattern Explainer (explain why patterns are trustworthy)

---

## Data Flow Example

```
Sequence Pattern Miner discovers:
  Pattern 1: [tokenizer → negation_detector → svo_extractor]
  Pattern 2: [json_filter → text_search]
  
↓

Dream Bucket contains (over 250 queries):
  47 times Pattern 1 fired + success
  4 times Pattern 1 fired + failure
  8 times Pattern 2 fired + success
  2 times Pattern 2 fired + failure
  200 times neither pattern fired (mixed outcomes)
  
↓ score_patterns_against_dream_bucket()

Pattern Confidence Scorer outputs:
  Pattern 1:
    - Precision: 47/(47+4) = 0.92
    - Recall: (depends on total successes)
    - F1: ~0.85
    - Reliability: HIGH ✓
    
  Pattern 2:
    - Precision: 8/(8+2) = 0.80
    - Recall: (lower)
    - F1: ~0.60
    - Reliability: MEDIUM
    - Flag: low_sample_size (n=10 < 20)
    
↓

Sleep Tier 2 reads scores:
  - Trust Pattern 1 for this domain
  - Deprioritize Pattern 2 until more data
  - Explore why Pattern 2 underperforms
```

---

## Testing Strategy

### Test Cases

1. **Simple sequence scoring:**
   - Pattern: `[A, B]`
   - Traces: 10 fires (8 success, 2 failure), 40 no-fires (25 success, 15 failure)
   - Expected: Precision ~0.80, Recall ~0.24, F1 ~0.37

2. **Collision pattern scoring:**
   - Pattern: `(fact_42, fact_137)`
   - Dream Bucket: 23 collisions, 150 non-collisions
   - Expected: Precision, recall based on co-occurrence frequency

3. **Low sample size flag:**
   - Pattern: rare sequence, only 5 observations
   - Expected: `confidence_flag: "low_sample_size"`

4. **High false positive rate:**
   - Pattern: fires 50 times, but only 10 successes
   - Expected: `confidence_flag: "high_false_positive_rate"`, FPR ~0.88

5. **Decay by age:**
   - Pattern with observations from 30 days ago
   - Decay factor 0.99: score decays by ~30%
   - Expected: `decayed_f1` < `original_f1`

### Example Test File (TEST-pattern_confidence_scorer_examples.json)

```json
{
  "test_cases": [
    {
      "name": "simple_sequence",
      "pattern": {"pattern_id": "p1", "sequence": ["A", "B"], "frequency": 10},
      "traces": [
        {"trace_id": "t1", "sequence": ["A", "B", "C"], "outcome": "success"},
        {"trace_id": "t2", "sequence": ["A", "B", "D"], "outcome": "success"},
        {"trace_id": "t3", "sequence": ["A", "B", "E"], "outcome": "failure"},
        {"trace_id": "t4", "sequence": ["X", "Y", "Z"], "outcome": "success"}
      ],
      "expected_metrics": {
        "precision": 0.67,
        "recall": 0.4
      }
    }
  ]
}
```

---

## Non-Goals

- ❌ Statistical significance testing (p-values, confidence intervals)
- ❌ Causal inference (does pattern cause outcome?)
- ❌ Pattern generation (create new patterns)
- ❌ Interactive model exploration (REPL, visualization)
- ❌ Hyperparameter optimization (fixed metrics for v1)

---

## Dependencies

| Package | Version | Purpose | Notes |
|---------|---------|---------|-------|
| stdlib | — | json, collections, math, statistics | No external deps |

**No external libraries needed. Pure Python.**

---

## Future Enhancements (Post-1.0)

1. **v1.1: Confidence intervals** — Compute 95% CI for each metric (bootstrap resampling)
2. **v1.2: Bayesian prior** — Incorporate prior expectations about pattern reliability
3. **v2.0: Causal scoring** — Ablation analysis to measure causal contribution of pattern elements
4. **v2.0: Online scoring** — Score patterns incrementally as new traces arrive (no batch processing)

---

**Last updated:** 2026-07-14  
**Author:** Isaac (Kitbash AI)  
**For:** tools/ ecosystem, Sleep Tier 2  
**Related:** SLEEP_METABOLISM_SPEC.md, DREAM_BUCKET_DESIGN.md, TOOLS_PIPELINE_REMAINING.md
