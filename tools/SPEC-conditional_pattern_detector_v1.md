# SPEC: Conditional Pattern Detector v1

**Module:** `tools/conditional_pattern_detector/`  
**Status:** Ready for build  
**Dependencies:** stdlib (json, collections, itertools)  
**Priority:** High (feeds sleep Tier 2 meta-learning; consumes Sequence Pattern Miner output directly)

---

## Overview

Detect association rules and decision patterns in execution traces. Discover relationships like "when grain_type='Z' and confidence < 0.6, tool_Y is called with frequency X" or "when query_length > 100, fact_lookup is skipped in N% of cases."

**Design principle:** Simple frequency-based rule discovery with confidence/support metrics (not statistical tests). Count co-occurrences; rank by strength.

**Use case:** "Analyze execution traces, find all patterns of the form 'when [condition], [outcome] follows,' ranked by confidence and support."

---

## Scope

### In Scope ✓
- Extract conditions and outcomes from trace sequences
- Conditions: grain properties, query characteristics, tool presence, confidence thresholds
- Outcomes: tool calls, traversal sequences, success/failure states
- Calculate confidence (P(outcome|condition)) and support (frequency)
- Calculate lift (how much more likely outcome is given condition)
- Optional: seed conditions (user provides known conditions to explore)
- Optional: minimum confidence/support thresholds for filtering
- Output: JSON with rules, metrics, ranked by strength

### Out of Scope ✗
- Statistical significance testing (chi-square, p-values)
- Causal inference (this is correlation, not causation)
- Constraint satisfaction or complex logical rules
- Temporal ordering (rules are atemporal; use Sequence Pattern Miner for ordering)
- Multi-step reasoning (one condition → one outcome; no chains)
- Optimization or pruning (return all rules that meet threshold)

---

## Module Structure

```
tools/conditional_pattern_detector/
  __init__.py                    # exports main functions
  core.py                        # implementation logic
  cli.py                         # argparse CLI
  pattern_schema.py              # dataclasses for JSON output
  README.md                       # usage docs
  __main__.py                    # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

#### 1. `detect_conditional_patterns(traces: list, min_support: int = 2, min_confidence: float = 0.5) -> dict`

**Purpose:** Discover all conditional patterns in traces (auto-generated conditions from trace structure).

**Input:**
- `traces` (list): Normalized trace objects (from Log Parser)
- `min_support` (int): Minimum occurrence count for a rule (default: 2)
- `min_confidence` (float): Minimum confidence P(outcome|condition) (default: 0.5)

**Output (JSON):**
```json
{
  "detection_params": {
    "min_support": 2,
    "min_confidence": 0.5,
    "total_traces_analyzed": 100,
    "traces_with_extractable_conditions": 95
  },
  "statistics": {
    "total_rules_found": 42,
    "rules_after_filtering": 28,
    "avg_confidence": 0.72,
    "avg_support": 4.3,
    "avg_lift": 1.45
  },
  "rules": [
    {
      "rank": 1,
      "condition": {
        "type": "chain_length",
        "operator": ">=",
        "value": 3
      },
      "outcome": {
        "type": "element_type_distribution",
        "fact_count_percent": 60,
        "grain_count_percent": 40
      },
      "metrics": {
        "support": 15,
        "confidence": 0.87,
        "lift": 1.74,
        "inverse_confidence": 0.33
      },
      "interpretation": "When chain length >= 3, fact:grain ratio is 60:40 in 87% of cases (vs 50% baseline)"
    },
    {
      "rank": 2,
      "condition": {
        "type": "element_presence",
        "element_id": "grain_789",
        "present": true
      },
      "outcome": {
        "type": "element_type_sequence",
        "sequence": ["grain_789", "fact_*"],
        "sequence_frequency_percent": 75
      },
      "metrics": {
        "support": 12,
        "confidence": 0.75,
        "lift": 1.5,
        "inverse_confidence": 0.5
      }
    }
  ],
  "condition_types_found": [
    "chain_length",
    "element_presence",
    "element_type_distribution",
    "session_id_consistency",
    "traversal_type_pattern"
  ]
}
```

**Behavior:**
- Auto-generate conditions from trace structure: chain_length, element counts, presence of specific elements, cartridge boundaries
- For each condition, find matching traces
- For each matching trace, extract outcomes (e.g., element distribution, next-element patterns)
- Calculate: support (count), confidence (matching_with_outcome / matching_total), lift (confidence / baseline_outcome_rate)
- Filter by min_support and min_confidence
- Rank by confidence descending (or lift)
- Include `inverse_confidence` (P(outcome|NOT condition)) for comparison

---

#### 2. `detect_seeded_patterns(traces: list, seed_conditions: list, min_support: int = 2) -> dict`

**Purpose:** Find patterns for user-specified conditions (targeted exploration).

**Input:**
- `traces` (list): Normalized trace objects
- `seed_conditions` (list of dict): User-provided conditions to explore
  ```python
  [
    {"type": "chain_length", "operator": ">=", "value": 3},
    {"type": "element_presence", "element_id": "grain_456", "present": true},
    {"type": "session_id", "value": "session_abc123"}
  ]
  ```
- `min_support` (int): Minimum occurrence count

**Output (JSON):**
```json
{
  "seeded_params": {
    "seed_conditions_provided": 3,
    "min_support": 2,
    "total_traces_analyzed": 100
  },
  "results": [
    {
      "seed_condition": {
        "type": "chain_length",
        "operator": ">=",
        "value": 3
      },
      "traces_matching_condition": 45,
      "outcomes": [
        {
          "outcome": {
            "type": "element_type_distribution",
            "fact_percent": 60
          },
          "support": 35,
          "confidence": 0.78,
          "lift": 1.56
        }
      ]
    }
  ]
}
```

**Behavior:**
- For each seed condition, find matching traces
- Extract outcomes from matching traces
- Calculate metrics (support, confidence, lift)
- Return ranked outcomes per seed condition

**Error handling:**
- `ValueError` if seed_condition format is invalid
- `ValueError` if condition type not recognized

---

#### 3. `extract_decision_trees(traces: list, depth: int = 2) -> dict`

**Purpose:** Build shallow decision tree from conditions (which condition distinguishes traces best?).

**Input:**
- `traces` (list): Normalized trace objects
- `depth` (int): Tree depth (default: 2; limit to avoid explosion)

**Output (JSON):**
```json
{
  "tree_params": {
    "depth": 2,
    "total_traces": 100
  },
  "decision_tree": {
    "root": {
      "condition": {
        "type": "chain_length",
        "operator": "<",
        "value": 3
      },
      "info_gain": 0.45,
      "traces_true": 40,
      "traces_false": 60,
      "children": {
        "true": {
          "condition": {
            "type": "element_presence",
            "element_id": "grain_789",
            "present": true
          },
          "traces_true": 30,
          "traces_false": 10,
          "outcome_distribution": {
            "success": 25,
            "failure": 5
          }
        },
        "false": {
          "condition": {
            "type": "session_id",
            "distinct_sessions": 15
          },
          "outcome_distribution": {
            "success": 45,
            "failure": 15
          }
        }
      }
    }
  }
}
```

**Behavior:**
- Recursively split traces by information gain (entropy reduction)
- At each node, pick condition that best separates traces
- Stop at depth_limit
- Return tree structure + outcome distributions at leaves

---

#### 4. `filter_patterns(patterns: list, min_confidence: float, min_lift: float = 1.0) -> dict`

**Purpose:** Post-filter rules by confidence and lift thresholds.

**Input:**
- `patterns` (list): Pattern objects (from `detect_conditional_patterns`)
- `min_confidence` (float): Minimum confidence
- `min_lift` (float): Minimum lift (default: 1.0 = no effect)

**Output (JSON):**
```json
{
  "filter_criteria": {
    "min_confidence": 0.7,
    "min_lift": 1.2
  },
  "total_patterns_input": 42,
  "patterns_after_filtering": 15,
  "filtered_out": 27,
  "patterns": [
    /* filtered and re-ranked */
  ]
}
```

---

#### 5. `rank_patterns_by_metric(patterns: list, metric: str = "confidence") -> dict`

**Purpose:** Re-rank patterns by different metrics (confidence, lift, support).

**Input:**
- `patterns` (list): Pattern objects
- `metric` (str): One of `"confidence"`, `"lift"`, `"support"` (default: `"confidence"`)

**Output (JSON):**
```json
{
  "metric": "lift",
  "ranked_patterns": [
    {
      "rank": 1,
      "condition": { /* ... */ },
      "outcome": { /* ... */ },
      "metrics": {
        "support": 25,
        "confidence": 0.92,
        "lift": 1.84
      }
    }
  ]
}
```

---

### CLI Interface (in `cli.py`)

```bash
# Auto-detect patterns with default thresholds
echo '{"traces": [...]}' | python -m tools.conditional_pattern_detector detect_conditional_patterns --min_support 2 --min_confidence 0.5

# Explore seeded conditions
echo '{
  "traces": [...],
  "seed_conditions": [
    {"type": "chain_length", "operator": ">=", "value": 3}
  ]
}' | python -m tools.conditional_pattern_detector detect_seeded_patterns

# Build decision tree
echo '{"traces": [...]}' | python -m tools.conditional_pattern_detector extract_decision_trees --depth 2

# Filter patterns
echo '{"patterns": [...]}' | python -m tools.conditional_pattern_detector filter_patterns --min_confidence 0.7 --min_lift 1.2

# Rank by different metric
echo '{"patterns": [...]}' | python -m tools.conditional_pattern_detector rank_patterns_by_metric --metric lift
```

**Exit codes:**
- `0` → success
- `1` → invalid input (ValueError)
- `2` → internal error (RuntimeError)

---

### Schema (in `pattern_schema.py`)

```python
from dataclasses import dataclass
from typing import List, Dict, Optional, Any

@dataclass
class Condition:
    type: str  # "chain_length", "element_presence", "session_id", etc.
    operator: Optional[str] = None  # ">=", "<=", "==", etc.
    value: Optional[Any] = None

@dataclass
class Outcome:
    type: str  # "element_type_distribution", "element_sequence", etc.
    data: Dict[str, Any]  # outcome-specific data

@dataclass
class PatternMetrics:
    support: int  # count of matching traces
    confidence: float  # P(outcome|condition)
    lift: float  # confidence / baseline_outcome_rate
    inverse_confidence: float  # P(outcome|NOT condition)

@dataclass
class ConditionalPattern:
    rank: int
    condition: Condition
    outcome: Outcome
    metrics: PatternMetrics
    interpretation: Optional[str] = None

@dataclass
class DetectionReport:
    detection_params: Dict[str, Any]
    statistics: Dict[str, Any]
    rules: List[ConditionalPattern]
    condition_types_found: List[str]

@dataclass
class DecisionNode:
    condition: Condition
    info_gain: float
    traces_true: int
    traces_false: int
    children: Optional[Dict[str, 'DecisionNode']] = None
    outcome_distribution: Optional[Dict[str, int]] = None
```

---

## Condition Types (Auto-Detected)

Conditions that `detect_conditional_patterns` can auto-generate:

1. **chain_length** — Chain has N or more elements
   ```json
   {"type": "chain_length", "operator": ">=", "value": 3}
   ```

2. **element_presence** — Specific element (fact/grain) appears in chain
   ```json
   {"type": "element_presence", "element_id": "fact_123", "present": true}
   ```

3. **element_type_distribution** — Percentage of facts vs. grains
   ```json
   {"type": "element_type_distribution", "fact_percent": 60}
   ```

4. **element_count** — Number of specific element type
   ```json
   {"type": "element_count", "element_type": "fact", "operator": ">=", "value": 3}
   ```

5. **session_consistency** — All steps in same session
   ```json
   {"type": "session_consistency", "consistent": true}
   ```

6. **cartridge_crossing** — Chain crosses cartridge boundaries
   ```json
   {"type": "cartridge_crossing", "crosses_boundary": true}
   ```

7. **traversal_type_pattern** — Dominant traversal type (e.g., mostly "cartridge_lookup")
   ```json
   {"type": "traversal_type_pattern", "dominant_type": "cartridge_lookup"}
   ```

---

## Outcome Types (Auto-Detected)

Outcomes that can be inferred from matching traces:

1. **element_type_distribution** — Fact:grain ratio in matching traces
2. **element_type_sequence** — Common multi-step patterns
3. **next_element_type** — What element type typically follows
4. **success_rate** — (If outcomes labeled) success frequency
5. **cartridge_distribution** — Which cartridges appear together
6. **traversal_type_dominance** — Which traversal type dominates

---

## Error Handling

**Unified error taxonomy:**
- `FileNotFoundError` — not applicable
- `ValueError` — invalid trace structure, invalid seed condition format, invalid metric name
- `RuntimeError` — internal rule discovery failure
- `IOError` — not applicable

**Logging:**
- Use `structured_logger.get_event_logger("conditional_pattern_detector")`
- Events: `detection_started`, `detection_complete`, `detection_failed`, `filtering_complete`
- Metadata: traces_analyzed, patterns_found, patterns_after_filtering, execution_time_ms

---

## Test Cases

### Happy Path
1. Simple chain_length condition → rules generated with correct support/confidence
2. Element presence condition → traces with element matched correctly
3. Multiple outcomes for single condition → all ranked by confidence
4. Seeded conditions → rules generated for user-specified conditions
5. Decision tree depth=1 → single root split
6. Decision tree depth=2 → root + two child nodes
7. Filter by min_confidence → rules below threshold removed
8. Filter by min_lift → rules with lift < threshold removed
9. Rank by lift → different order than confidence-ranked
10. Rank by support → frequency-based ranking

### Edge Cases
11. Empty traces → zero patterns, no error
12. All traces identical → single pattern (condition matches all)
13. All traces diverse → many unique patterns
14. Single condition matches one trace → support=1 (allowed if min_support=1)
15. Outcome appears in all traces regardless of condition → lift=1.0 (no discriminative power)
16. Condition never occurs in traces → no patterns generated (filtered out)
17. Multiple seed conditions → results for each condition separately
18. Seed condition matches zero traces → support=0, confidence=N/A
19. Decision tree depth=0 → just root node with outcome distribution
20. Decision tree with all traces at leaf → no further splits

### Error Cases
21. Invalid seed condition format (missing type) → `ValueError`
22. Invalid condition type (not recognized) → `ValueError`
23. Invalid metric name (not confidence/lift/support) → `ValueError`
24. min_confidence not in [0.0, 1.0] → `ValueError`
25. min_lift < 0.0 → `ValueError`
26. min_support < 1 → `ValueError`
27. Traces with missing chain → `RuntimeError` or skip (document choice)
28. Trace with empty chain → skip (no conditions possible)
29. Filter with no matches → empty patterns array
30. Depth > 10 for decision tree → `ValueError` (prevent explosion)

### CLI Behavior
31. CLI exit code 0 on success
32. CLI exit code 1 on ValueError
33. CLI exit code 2 on RuntimeError
34. CLI reads valid JSON from stdin
35. CLI with multiple filters (--min_confidence --min_lift) → both applied

---

## Non-Goals (Explicitly Out of Scope)

- Statistical significance testing (chi-square, Fisher's exact test)
- Causal inference (intervention analysis, counterfactuals)
- Temporal ordering (use Sequence Pattern Miner for that)
- Constraint satisfaction or rule optimization
- Pruning or redundancy elimination
- Visualization or graphing

---

## Implementation Notes

### Information Gain Calculation (for Decision Trees)

```
info_gain = entropy(parent) - (weighted avg of entropy(children))

entropy(traces) = -Σ P(outcome_i) * log2(P(outcome_i))
```

Keep it simple; don't overthink. Gini index alternative if cleaner.

### Confidence Calculation

```
confidence(outcome | condition) = 
  count(traces with condition AND outcome) / count(traces with condition)
```

### Lift Calculation

```
lift = confidence(outcome | condition) / baseline_rate(outcome)

baseline_rate(outcome) = count(traces with outcome) / total_traces
```

Lift > 1 means condition makes outcome more likely.
Lift < 1 means condition makes outcome less likely.
Lift = 1 means no relationship.

### Auto-Condition Generation Strategy

Start simple:
1. Extract chain_length from each trace
2. Extract element_presence for the top N most-common elements
3. Extract element_type_distribution (fact %, grain %)
4. Limit to conditions appearing in ≥ min_support traces (avoid combinatorial explosion)

Don't over-generate; quality over quantity.

---

## Success Criteria

- ✅ All 35 test cases pass (manually verified with terminal output)
- ✅ CLI exit codes correct (0, 1, 2)
- ✅ Support/confidence/lift calculated correctly
- ✅ Conditions auto-generated match trace structure
- ✅ Seeded conditions correctly applied
- ✅ Decision tree splits by information gain
- ✅ Filtering logic correct (AND semantics)
- ✅ Ranking by different metrics produces different orders
- ✅ Errors logged via structured_logger with context
- ✅ README documents all functions, condition types, outcome types, examples

---

**Last updated:** 2026-07-14  
**Prepared by:** Claude  
**Status:** Ready for Hermes build
