# SPEC: Causal Credit Attribution v1

**Module:** `tools/causal_credit_attribution/`  
**Status:** Ready for spec  
**Dependencies:** stdlib (json, collections, itertools, statistics)  
**Priority:** High (learning-era feature; enables targeted improvement of weak links in successful chains)

---

## Overview

For a given successful execution trace, determine which tools/grains contributed most to the success. Attribute "credit" to each component based on their position in the chain, their historical correlation with success, and their causal role (as inferred from co-occurrence patterns).

**Design principle:** Deterministic attribution without true causal inference. Use heuristics: components closer to final outcome get higher credit; components with strong historical success correlation get higher credit; components appearing in discovered success patterns get higher credit. Emit per-component attribution scores and confidence levels.

**Use case:** "I ran [tokenizer → negation_detector → svo_extractor → json_filter] and succeeded. Which tools deserve credit? Should I invest in improving tokenizer or svo_extractor?"

---

## Scope

### In Scope ✓
- Attribute success credit to individual tools in a successful trace
- Attribute success credit to individual grains in a successful trace
- Use multiple attribution signals:
  - **Positional:** Components closer to outcome get higher credit
  - **Historical correlation:** Components with strong success pattern correlation get higher credit
  - **Pattern membership:** Components appearing in discovered success patterns get higher credit
  - **Input/output relationship:** Components that transform key intermediate results get higher credit
- Batch attribution: score all components in a trace
- Output: JSON with per-component attribution scores [0, 1] + total credit (should sum to ~1.0)
- Support mixed tool + grain traces
- Confidence levels: flag uncertain attributions (low evidence)

### Out of Scope ✗
- True causal inference (statistical causality, interventional tests, counterfactuals)
- Counterfactual reasoning ("what if I removed this tool?") — separate tool
- Predicting whether removing a component would hurt success
- Interactive visualization
- Ablation studies (removing components from trace to measure impact)

---

## Module Structure

```
tools/causal_credit_attribution/
  __init__.py                      # exports main functions
  core.py                          # attribution logic
  attribution_signals.py           # positional, historical, pattern-based signals
  heuristic_aggregation.py         # combine signals into final attribution
  cli.py                           # argparse CLI
  attribution_schema.py            # dataclasses for JSON output
  README.md                         # usage + examples
  __main__.py                      # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

All functions accept/return JSON-serializable types.

#### 1. `attribute_credit_to_tools(trace: dict, success_patterns: list = None, historical_traces: list = None, weights: dict = None) -> dict`

**Purpose:** Attribute success credit to each tool in a successful trace.

**Input:**
- `trace` (dict): A single successful execution trace:
  ```json
  {
    "trace_id": "tr_12345",
    "sequence": ["tokenizer", "negation_detector", "svo_extractor", "json_filter"],
    "outcome": "success",
    "error_signal": 0.05,
    "timestamp": "2026-07-14T10:30:00Z"
  }
  ```

- `success_patterns` (list, optional): Success patterns from Success Pattern Miner (for pattern-membership signal):
  ```json
  [
    {
      "pattern_id": "succ_seq_001",
      "sequence": ["tokenizer", "negation_detector", "svo_extractor"],
      "frequency": 47,
      "signal_strength": 0.87
    }
  ]
  ```

- `historical_traces` (list, optional): All historical execution traces (for historical-correlation signal):
  ```json
  [
    {"trace_id": "tr_00001", "sequence": [...], "outcome": "success", "error_signal": 0.02},
    {"trace_id": "tr_00002", "sequence": [...], "outcome": "success", "error_signal": 0.08}
  ]
  ```

- `weights` (dict, optional): Weights for attribution signals. Default:
  ```json
  {
    "positional": 0.30,
    "historical_correlation": 0.35,
    "pattern_membership": 0.25,
    "input_output_salience": 0.10
  }
  ```

**Output:**
```json
{
  "attribution_run_id": "attr_001",
  "timestamp": "2026-07-14T14:45:00Z",
  "trace_id": "tr_12345",
  "trace_sequence": ["tokenizer", "negation_detector", "svo_extractor", "json_filter"],
  "outcome": "success",
  "error_signal": 0.05,
  "total_credit_attributed": 1.0,
  "tool_attributions": [
    {
      "position": 0,
      "tool": "tokenizer",
      "credit_score": 0.18,
      "attribution_signals": {
        "positional_signal": 0.15,
        "historical_correlation_signal": 0.22,
        "pattern_membership_signal": 0.10,
        "input_output_salience_signal": 0.05
      },
      "appears_in_patterns": ["succ_seq_001"],
      "historical_success_rate": 0.89,
      "confidence": "high"
    },
    {
      "position": 1,
      "tool": "negation_detector",
      "credit_score": 0.25,
      "attribution_signals": {
        "positional_signal": 0.20,
        "historical_correlation_signal": 0.28,
        "pattern_membership_signal": 0.30,
        "input_output_salience_signal": 0.08
      },
      "appears_in_patterns": ["succ_seq_001"],
      "historical_success_rate": 0.92,
      "confidence": "high"
    },
    {
      "position": 2,
      "tool": "svo_extractor",
      "credit_score": 0.31,
      "attribution_signals": {
        "positional_signal": 0.25,
        "historical_correlation_signal": 0.32,
        "pattern_membership_signal": 0.35,
        "input_output_salience_signal": 0.12
      },
      "appears_in_patterns": ["succ_seq_001"],
      "historical_success_rate": 0.95,
      "confidence": "high"
    },
    {
      "position": 3,
      "tool": "json_filter",
      "credit_score": 0.26,
      "attribution_signals": {
        "positional_signal": 0.35,
        "historical_correlation_signal": 0.18,
        "pattern_membership_signal": 0.00,
        "input_output_salience_signal": 0.20
      },
      "appears_in_patterns": [],
      "historical_success_rate": 0.75,
      "confidence": "medium"
    }
  ],
  "metadata": {
    "weights": {
      "positional": 0.30,
      "historical_correlation": 0.35,
      "pattern_membership": 0.25,
      "input_output_salience": 0.10
    },
    "success_patterns_used": 1,
    "historical_traces_used": 1247
  }
}
```

#### 2. `attribute_credit_to_grains(trace: dict, grain_signal_scores: list = None, historical_traces: list = None, weights: dict = None) -> dict`

**Purpose:** Attribute success credit to each grain activation.

**Input:**
- `trace` (dict): Execution trace with grain activations:
  ```json
  {
    "trace_id": "tr_12345",
    "grain_activations": [42, 137, 89, 56],
    "outcome": "success",
    "error_signal": 0.05,
    "timestamp": "2026-07-14T10:30:00Z"
  }
  ```

- `grain_signal_scores` (list, optional): Pre-computed success signal for each grain:
  ```json
  [
    {"grain_id": 42, "success_signal_strength": 0.85},
    {"grain_id": 137, "success_signal_strength": 0.92}
  ]
  ```

- `historical_traces`, `weights`: Same as tool attribution

**Output:** Same structure as tool attribution, but `tool` field replaced with `grain_id` and grain-specific metrics.

#### 3. `batch_attribute_credit(traces: list, success_patterns: list = None, historical_traces: list = None, weights: dict = None) -> dict`

**Purpose:** Attribute credit for multiple traces in one batch.

**Input:**
- `traces` (list): Multiple execution traces
- Other parameters: same as above

**Output:**
```json
{
  "batch_attribution_run_id": "batch_attr_001",
  "timestamp": "2026-07-14T15:00:00Z",
  "traces_processed": 10,
  "attributions": [
    {attribution_run_id: "attr_001", ...},
    {attribution_run_id: "attr_002", ...}
  ],
  "aggregated_tool_credit": {
    "tokenizer": 0.18,
    "negation_detector": 0.25,
    "svo_extractor": 0.31,
    "json_filter": 0.26
  }
}
```

---

## Attribution Signals (Detailed)

### 1. Positional Signal
- **Definition:** Tools closer to outcome receive higher credit
- **Calculation:** 
  - Tool at position i (0-indexed) in sequence of length N
  - Score = `(N - i) / N` (last tool gets 1.0, first gets 1/N)
- **Intuition:** Components later in chain have more direct impact on final output
- **Range:** (0, 1]

### 2. Historical Correlation Signal
- **Definition:** Tools with strong historical success correlation get higher credit
- **Calculation:**
  - For each tool, compute success rate from historical_traces: `(traces where tool appears AND outcome=success) / (traces where tool appears)`
  - Score = `historical_success_rate`
- **Intuition:** Tools that have consistently led to success are more credible contributors
- **Range:** [0, 1]

### 3. Pattern Membership Signal
- **Definition:** Tools appearing in discovered success patterns get higher credit
- **Calculation:**
  - Count how many success patterns contain this tool (with this context/neighbors)
  - Score = `min(pattern_count / max_pattern_count, 1.0)` (normalized)
  - Bonus if pattern includes other tools in current trace (pattern is "active")
- **Intuition:** Tools that are part of known winning strategies deserve credit
- **Range:** [0, 1]

### 4. Input/Output Salience Signal
- **Definition:** Tools transforming key intermediate results get higher credit
- **Calculation:** (Heuristic; v1 is simple)
  - If tool's input was rare/high-error and output is common/low-error: high score
  - Estimate based on tool category (preprocessing tools lower, decision tools higher)
  - Default: all tools get base score 0.5
- **Intuition:** Tools fixing critical bottlenecks deserve more credit
- **Range:** [0, 1]

---

## Composite Attribution

**Per-tool credit** = weighted average of 4 signals:
```
credit_score = (
    positional_signal * weight["positional"] +
    historical_correlation_signal * weight["historical_correlation"] +
    pattern_membership_signal * weight["pattern_membership"] +
    input_output_salience_signal * weight["input_output_salience"]
)
```

Default weights (tuned for identifying weak links):
- `historical_correlation`: 0.35 (most important: proven track record)
- `positional`: 0.30 (second: proximity to outcome)
- `pattern_membership`: 0.25 (third: part of known winning strategy)
- `input_output_salience`: 0.10 (last: specialized heuristic)

**Total credit normalization:** `tool_credits = [c / sum(all_credits) for c in tool_credits]` (ensures total sums to ~1.0)

---

## CLI Interface

```bash
# Attribute credit for a single trace
python -m tools.causal_credit_attribution \
  --trace trace.json \
  --output attribution.json

# Attribute using success patterns and historical data
python -m tools.causal_credit_attribution \
  --trace trace.json \
  --patterns patterns.json \
  --historical traces.jsonl \
  --output attribution.json

# Batch attribution
python -m tools.causal_credit_attribution \
  --traces traces.jsonl \
  --patterns patterns.json \
  --historical all_traces.jsonl \
  --batch \
  --output batch_attributions.json

# Custom weights
python -m tools.causal_credit_attribution \
  --trace trace.json \
  --weights-positional 0.25 \
  --weights-historical 0.40 \
  --weights-pattern 0.25 \
  --weights-salience 0.10 \
  --output attribution.json
```

---

## Input/Output Formats

### Input
- `trace`: JSON object with `trace_id`, `sequence` (or `grain_activations`), `outcome`, `error_signal`, `timestamp`
- `success_patterns`: JSON array from Success Pattern Miner
- `historical_traces`: JSONL or JSON array of all execution traces

### Output
- JSON object with per-tool/grain attribution scores, signals, and metadata

---

## Implementation Notes

1. **Positional calculation:** `(len(sequence) - position_index) / len(sequence)`
2. **Historical correlation:** Filter historical_traces by tool name; count successes
3. **Pattern membership:** Find which patterns in success_patterns contain this tool in sequence order
4. **Input/output salience:** v1 uses base heuristic (0.5 for all tools); can be refined later
5. **Normalization:** After computing all scores, normalize so total credit = 1.0
6. **Confidence:** `high` if >= 2 signals available and historical_traces > 100; `medium` otherwise; `low` if < 10 traces
7. **Error handling:** Fail-loud on malformed input, missing required fields

---

## Error Semantics

- Exit 0: Success (credit attributed)
- Exit 1: ValueError (invalid trace format, missing fields)
- Exit 2: RuntimeError (I/O error, file not found)

---

## Testing Strategy

### Explicit Test Cases (in `TEST-causal_credit_attribution_examples.json`)

1. **Simple chain:** 4-tool sequence; later tools should get higher positional credit
2. **Pattern membership:** Tool appearing in 3 discovered patterns should get high pattern_membership_signal
3. **Historical correlation:** Tool with 95% success rate should get high historical_correlation_signal
4. **Weak link:** Tool with 60% historical success rate should get lower credit
5. **Batch attribution:** 5 traces → aggregated tool_credit should show most-credited tools
6. **Grain attribution:** Trace with grain activations → credit attributed to grains
7. **No patterns/history:** Attribution with only positional signal → should still compute reasonable scores

---

## Dependencies & Constraints

- **Python:** 3.8+
- **Imports:** json, collections, itertools, statistics
- **External libs:** None (stdlib only)
- **Resource limits:** Should handle single 20-tool trace in <1 second; 1000 traces in <30 seconds
- **Hardware:** CPU-only

---

## Related Tools

- **Success Pattern Miner v1:** Discovers patterns (this tool uses them)
- **Positive Signal Scorer v1:** Ranks patterns (this tool attributes credit within traces)
- **Anomaly Scorer v1:** Inverse (scores failure; could support failure attribution in v2)
- **Pattern Confidence Scorer v1:** Validates patterns (different tool)

---

## Non-Goals

- **True causality:** This is heuristic-based attribution, not causal inference
- **Interventional experiments:** No counterfactual reasoning ("what if I removed this?")
- **Prediction:** Tool doesn't predict what happens if you change the trace
- **Real-time streaming:** Batch processing only (v1)

---

## Post-1.0 Extensions

1. **Failure attribution:** Version 2 could attribute failure to weak links (inverse of this)
2. **Counterfactual reasoning:** "If I removed this tool, would success rate drop?"
3. **Input/output salience v2:** Learn salience from actual intermediate outputs, not heuristics
4. **Grain interaction attribution:** Measure credit for grain *pairs* in mixed traces

---

**Last updated:** 2026-07-14  
**For:** Kitbash sleep pipeline (Tier 2 learning-era feature)  
**Related:** TOOL_PHILOSOPHY.md, Success Pattern Miner v1, Positive Signal Scorer v1
