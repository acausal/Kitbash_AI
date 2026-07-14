# SPEC: Success Pattern Miner v1

**Module:** `tools/success_pattern_miner/`  
**Status:** Ready for spec  
**Dependencies:** stdlib (json, collections, itertools, statistics)  
**Priority:** High (inverse negative-signal infrastructure; enables positive feedback loop learning)

---

## Overview

Mirror of Sequence Pattern Miner, but for successful execution traces and positive outcomes. Discover recurring patterns in Dream Bucket success chains, tool sequences that led to correct results, and co-occurrence signatures of high-confidence grains.

**Design principle:** Deterministic pattern discovery from ground-truth success observations. Same interface as Sequence Pattern Miner, but filter input to success trajectories only. Count co-occurrences, measure frequency, emit patterns ranked by confidence and predictiveness.

**Use case:** "Show me the tool sequences I ran successfully 5+ times. Show me which grains fired together when outcomes were correct. Give me the topology of my wins."

---

## Scope

### In Scope ✓
- Discover recurring tool sequences in successful execution traces (outcome = "success" or error_signal < threshold)
- Discover recurring grain activation patterns during high-confidence decisions
- Count co-occurrences: which tools/grains appear together in successful chains?
- Filter by success criteria: outcome == "success" OR error_signal < 0.2 (configurable)
- Measure pattern frequency, support, and coverage (% of successes explained by pattern)
- Time-windowed discovery: patterns in last N traces, last N days
- Output: JSON array of patterns (same structure as Sequence Pattern Miner, field `pattern_type: "success_sequence"`)
- Batch discovery (accept full Dream Bucket trace logs, emit patterns)

### Out of Scope ✗
- Causal analysis (what made this sequence successful?) — Causal Credit Attribution does this
- Scoring/ranking by confidence — Positive Signal Scorer does this
- Prediction of future success — separate tool
- Interactive visualization
- Filtering by specific domain/cartridge/context — orchestrator layer controls filtering

---

## Module Structure

```
tools/success_pattern_miner/
  __init__.py                     # exports main functions
  core.py                         # pattern discovery logic
  pattern_extraction.py           # tool sequence + grain sequence extraction
  filtering.py                    # success criteria filtering
  cli.py                          # argparse CLI
  miner_schema.py                 # dataclasses for patterns and input/output
  README.md                        # usage + examples
  __main__.py                     # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

All functions accept/return JSON-serializable types.

#### 1. `mine_success_tool_sequences(traces: list, min_frequency: int = 3, success_threshold: float = 0.2, time_window_hours: int = None) -> dict`

**Purpose:** Discover recurring tool sequences in successful execution traces.

**Input:**
- `traces` (list): Execution traces with outcomes:
  ```json
  {
    "trace_id": "tr_12345",
    "sequence": ["tokenizer", "negation_detector", "svo_extractor"],
    "outcome": "success",
    "error_signal": 0.05,
    "timestamp": "2026-07-14T10:30:00Z"
  }
  ```
- `min_frequency` (int): Minimum occurrences to report pattern (default: 3)
- `success_threshold` (float): error_signal < this counts as success (default: 0.2)
- `time_window_hours` (int, optional): Only consider traces from last N hours

**Output:**
```json
{
  "discovery_run_id": "succ_disc_001",
  "timestamp": "2026-07-14T14:00:00Z",
  "input_traces_count": 1250,
  "success_traces_count": 847,
  "patterns": [
    {
      "pattern_id": "succ_seq_001",
      "sequence": ["tokenizer", "negation_detector", "svo_extractor"],
      "frequency": 47,
      "support": 0.056,
      "coverage": 0.187,
      "pattern_type": "success_sequence",
      "first_seen": "2026-07-10T08:15:00Z",
      "last_seen": "2026-07-14T13:45:00Z",
      "confidence_estimate": 0.92
    },
    {
      "pattern_id": "succ_seq_002",
      "sequence": ["text_search", "json_filter"],
      "frequency": 19,
      "support": 0.022,
      "coverage": 0.076,
      "pattern_type": "success_sequence",
      "first_seen": "2026-07-11T12:30:00Z",
      "last_seen": "2026-07-14T09:20:00Z",
      "confidence_estimate": 0.87
    }
  ],
  "metadata": {
    "min_frequency_threshold": 3,
    "success_criteria": {"error_signal_max": 0.2, "outcome_match": "success"},
    "time_window_hours": null
  }
}
```

#### 2. `mine_success_grain_patterns(traces: list, min_frequency: int = 3, success_threshold: float = 0.2) -> dict`

**Purpose:** Discover recurring grain activation patterns during successful decisions.

**Input:**
- `traces` (list): Execution traces including grain activations:
  ```json
  {
    "trace_id": "tr_12345",
    "grain_activations": [42, 137, 89],
    "outcome": "success",
    "error_signal": 0.08,
    "timestamp": "2026-07-14T10:30:00Z"
  }
  ```
- `min_frequency`, `success_threshold`: same as above

**Output:** Same structure as tool sequences, but `sequence` field contains grain IDs:
```json
{
  "patterns": [
    {
      "pattern_id": "succ_grain_001",
      "sequence": [42, 137, 89],
      "frequency": 23,
      "support": 0.027,
      "coverage": 0.091,
      "pattern_type": "success_grain_activation",
      "confidence_estimate": 0.85
    }
  ]
}
```

#### 3. `mine_mixed_success_patterns(traces: list, min_frequency: int = 3, success_threshold: float = 0.2) -> dict`

**Purpose:** Discover patterns that interleave tool sequences AND grain activations.

**Input:** Traces containing both `sequence` and `grain_activations` fields.

**Output:** Patterns with both fields populated:
```json
{
  "patterns": [
    {
      "pattern_id": "succ_mixed_001",
      "sequence": ["tokenizer", "negation_detector", "svo_extractor"],
      "grain_sequence": [42, 137],
      "frequency": 12,
      "support": 0.014,
      "coverage": 0.048,
      "pattern_type": "success_mixed",
      "confidence_estimate": 0.79
    }
  ]
}
```

---

## CLI Interface

```bash
# Discover tool sequences in successful traces
python -m tools.success_pattern_miner \
  --input traces.jsonl \
  --pattern-type sequences \
  --min-frequency 3 \
  --success-threshold 0.2 \
  --output patterns.json

# Discover grain patterns
python -m tools.success_pattern_miner \
  --input traces.jsonl \
  --pattern-type grains \
  --output patterns.json

# Discover mixed patterns with time window
python -m tools.success_pattern_miner \
  --input traces.jsonl \
  --pattern-type mixed \
  --time-window-hours 24 \
  --output patterns.json
```

---

## Input/Output Formats

### Input (stdin or file)
- JSONL (one trace per line) or JSON array of traces
- Each trace must have: `trace_id`, `outcome`, `error_signal`, `timestamp`
- Must have either `sequence` or `grain_activations` (or both)

### Output (stdout or file)
- JSON object with `patterns` array
- Each pattern includes: `pattern_id`, `sequence` (or `grain_sequence`), `frequency`, `support`, `coverage`, `pattern_type`, `confidence_estimate`

---

## Implementation Notes

1. **Success filtering:** Filter input traces where `outcome == "success"` OR `error_signal < success_threshold` before mining
2. **Pattern extraction:** Use itertools to find contiguous n-grams of length 2–6 in tool/grain sequences
3. **Frequency counting:** Use collections.Counter; track (pattern → count)
4. **Support calculation:** `frequency / total_success_traces`
5. **Coverage calculation:** `traces_containing_pattern / total_success_traces`
6. **Confidence estimate:** Heuristic based on frequency + coverage (e.g., `(frequency / min_frequency) * (coverage / 0.5)`, clamped to [0, 1])
7. **Time-window filtering:** Parse `timestamp` as ISO 8601; filter traces where `now - timestamp < time_window_hours`
8. **Error handling:** Fail-loud on malformed JSON, missing required fields, empty pattern output

---

## Error Semantics

- Exit 0: Success (patterns discovered or explicitly empty)
- Exit 1: ValueError (invalid input format, missing required fields)
- Exit 2: RuntimeError (I/O error, file not found)

---

## Testing Strategy

### Explicit Test Cases (in `TEST-success_pattern_miner_examples.json`)

1. **Simple sequences:** 5 traces with repeated [tool_a, tool_b, tool_c] sequence, min_frequency=2 → finds pattern
2. **Grain activations:** 5 traces with repeated [grain_42, grain_137] during success → finds pattern
3. **Mixed patterns:** 5 traces with both tools and grains → mixed pattern discovered
4. **Time window:** 10 traces, 5 old (>24h) + 5 new → respects time-window-hours
5. **Low frequency filtering:** 100 traces, 1 pattern appears 2 times → filtered out if min_frequency=3
6. **Empty input:** 0 traces → empty patterns array (no error)
7. **Malformed JSON:** Invalid JSON → exit 1 with error message

---

## Dependencies & Constraints

- **Python:** 3.8+
- **Imports:** json, collections, itertools, statistics, datetime
- **External libs:** None (stdlib only)
- **Resource limits:** Should handle 10K+ traces in <10 seconds on GTX 1060
- **Hardware:** CPU-only

---

## Related Tools

- **Sequence Pattern Miner v1:** Discovers patterns from ALL traces (not success-filtered)
- **Positive Signal Scorer v1:** Ranks/scores success patterns by confidence
- **Causal Credit Attribution v1:** Attributes success to specific causal factors
- **Anomaly Scorer v1:** Inverse (finds anomalies = low-confidence patterns)

---

## Non-Goals

- **Prediction:** This tool discovers what happened; it doesn't predict future success
- **Causality:** Finding patterns ≠ causation; Causal Credit Attribution handles that
- **Interactive visualization:** Output is JSON only; downstream tools visualize
- **Real-time streaming:** Batch processing only (v1)

---

**Last updated:** 2026-07-14  
**For:** Kitbash sleep pipeline (Tier 2 positive feedback learning)  
**Related:** TOOL_PHILOSOPHY.md, Sequence Pattern Miner v1 spec
