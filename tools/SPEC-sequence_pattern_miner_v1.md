# SPEC: Sequence Pattern Miner v1

**Module:** `tools/sequence_pattern_miner/`  
**Status:** Ready for build  
**Dependencies:** stdlib (json, collections, itertools)  
**Priority:** High (feeds sleep Tier 2 meta-learning; consumes Log Parser output directly)

---

## Overview

Mine recurring n-gram sequences from normalized execution traces. Discover patterns like "when query type X, tool sequence Y→Z→W always follows" by finding frequent element sequences in chains.

**Design principle:** Simple frequency counter over sequences; no statistical tests or significance thresholds (v1). Count and rank.

**Use case:** "Parse execution logs, find all sequences of length 2–4, show me which fact→fact→grain chains appear most often."

---

## Scope

### In Scope ✓
- Extract n-grams (sequences of length n) from chains
- Count frequency of each unique sequence
- Rank sequences by occurrence count
- Support variable n (n=1 unigrams, n=2 bigrams, n=3 trigrams, etc.)
- Optional: filter by minimum frequency threshold
- Optional: extract by element type (fact-only chains, grain-only chains, mixed)
- Output: JSON with sequence list, frequencies, rankings

### Out of Scope ✗
- Statistical significance testing (p-values, confidence intervals)
- Markov chain probabilities (separate tool)
- Smoothing or backoff strategies
- Fuzzy matching or similarity (exact sequence matching only)
- Multi-trace alignment or cross-trace patterns
- Visualization or rendering

---

## Module Structure

```
tools/sequence_pattern_miner/
  __init__.py                    # exports main functions
  core.py                        # implementation logic
  cli.py                         # argparse CLI
  sequence_schema.py             # dataclasses for JSON output
  README.md                       # usage docs
  __main__.py                    # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

#### 1. `extract_ngrams(traces: list, n: int = 2, min_frequency: int = 1, chain_filter: str = None) -> dict`

**Purpose:** Extract n-grams from all chains in traces and rank by frequency.

**Input:**
- `traces` (list): Normalized trace objects (from Log Parser)
- `n` (int): Sequence length (default: 2 for bigrams)
- `min_frequency` (int): Only return sequences occurring ≥ n times (default: 1)
- `chain_filter` (str, optional): Filter chains by type: `"fact_only"`, `"grain_only"`, `"mixed"` (default: None = all)

**Output (JSON):**
```json
{
  "extraction_params": {
    "n": 2,
    "min_frequency": 1,
    "chain_filter": null,
    "total_traces": 100
  },
  "statistics": {
    "total_chains_analyzed": 100,
    "total_ngrams_extracted": 285,
    "unique_sequences": 45,
    "most_common_frequency": 12,
    "least_common_frequency": 1,
    "average_frequency": 6.3
  },
  "sequences": [
    {
      "rank": 1,
      "sequence": ["fact_123", "fact_456"],
      "sequence_type": "fact→fact",
      "occurrence_count": 12,
      "frequency_percent": 4.21,
      "traces_containing": ["q_1_xxx", "q_3_xxx", "q_5_xxx"],
      "first_observed_trace": "q_1_xxx",
      "last_observed_trace": "q_45_xxx"
    },
    {
      "rank": 2,
      "sequence": ["grain_789", "fact_042"],
      "sequence_type": "grain→fact",
      "occurrence_count": 8,
      "frequency_percent": 2.81,
      "traces_containing": ["q_2_xxx", "q_7_xxx"],
      "first_observed_trace": "q_2_xxx",
      "last_observed_trace": "q_44_xxx"
    }
  ]
}
```

**Behavior:**
- For each trace, extract all n-grams from its chain (sliding window of size n)
- Count frequency of each unique sequence
- Infer sequence_type from element types (fact→fact, grain→grain, mixed, etc.)
- Filter sequences by min_frequency
- Sort by occurrence count (descending)
- Rank and calculate frequency percentages
- Track which traces contain each sequence

**Error handling:**
- `ValueError` if n < 1 or n > max_chain_length
- `ValueError` if min_frequency < 1
- `ValueError` if chain_filter not in ["fact_only", "grain_only", "mixed"]
- `RuntimeError` if trace structure is invalid

---

#### 2. `extract_ngrams_by_length(traces: list, min_n: int = 1, max_n: int = 4, min_frequency: int = 1) -> dict`

**Purpose:** Extract n-grams across multiple sequence lengths (1 to 4) in one call.

**Input:**
- `traces` (list): Normalized trace objects
- `min_n` (int): Minimum sequence length (default: 1)
- `max_n` (int): Maximum sequence length (default: 4)
- `min_frequency` (int): Minimum occurrence count (default: 1)

**Output (JSON):**
```json
{
  "extraction_params": {
    "min_n": 1,
    "max_n": 4,
    "min_frequency": 1,
    "total_traces": 100
  },
  "sequences_by_length": {
    "n=1": {
      "total_unigrams": 100,
      "unique_unigrams": 25,
      "sequences": [
        {
          "rank": 1,
          "sequence": ["fact_123"],
          "occurrence_count": 50,
          "frequency_percent": 50.0
        }
      ]
    },
    "n=2": {
      "total_bigrams": 200,
      "unique_bigrams": 45,
      "sequences": [
        /* bigrams sorted by frequency */
      ]
    },
    "n=3": { /* trigrams */ },
    "n=4": { /* 4-grams */ }
  },
  "summary": {
    "total_sequences_extracted": 545,
    "total_unique_sequences": 115,
    "most_common_sequence": ["fact_123", "fact_456"],
    "most_common_frequency": 12
  }
}
```

**Behavior:**
- Call `extract_ngrams()` for each n from min_n to max_n
- Aggregate results by sequence length
- Return summary of all lengths

---

#### 3. `filter_sequences(sequences: list, min_frequency: int, max_frequency: int = None) -> dict`

**Purpose:** Post-filter a sequence list by frequency bounds.

**Input:**
- `sequences` (list): Sequence objects (from `extract_ngrams`)
- `min_frequency` (int): Keep sequences with occurrence_count ≥ this
- `max_frequency` (int, optional): Keep sequences with occurrence_count ≤ this

**Output (JSON):**
```json
{
  "filter_criteria": {
    "min_frequency": 3,
    "max_frequency": 10
  },
  "total_sequences_input": 45,
  "sequences_after_filtering": 12,
  "filtered_out": 33,
  "sequences": [
    /* filtered sequence list, re-ranked */
  ]
}
```

---

#### 4. `rank_sequences_by_element_type(sequences: list) -> dict`

**Purpose:** Group and rank sequences by element type pattern (fact→fact, grain→grain, mixed).

**Input:**
- `sequences` (list): Sequence objects

**Output (JSON):**
```json
{
  "sequences_by_type": {
    "fact→fact": {
      "count": 20,
      "top_sequences": [
        {
          "rank": 1,
          "sequence": ["fact_123", "fact_456"],
          "occurrence_count": 12
        }
      ]
    },
    "grain→grain": {
      "count": 8,
      "top_sequences": []
    },
    "fact→grain": {
      "count": 10,
      "top_sequences": []
    },
    "grain→fact": {
      "count": 5,
      "top_sequences": []
    },
    "mixed": {
      "count": 2,
      "top_sequences": []
    }
  },
  "summary": {
    "total_sequences": 45,
    "type_distribution": {
      "fact→fact": 44.4,
      "grain→grain": 17.8,
      /* ... */
    }
  }
}
```

---

#### 5. `sequences_to_markov_transitions(sequences: list) -> dict`

**Purpose:** Convert sequences to Markov transition format (preparatory for Markov Chain tool).

**Input:**
- `sequences` (list): Sequence objects (typically n=2)

**Output (JSON):**
```json
{
  "transitions": {
    "fact_123": {
      "fact_456": {
        "transition_count": 12,
        "transition_probability": 0.6,
        "frequency_percent": 60.0
      },
      "grain_789": {
        "transition_count": 8,
        "transition_probability": 0.4,
        "frequency_percent": 40.0
      }
    },
    "grain_789": {
      "fact_042": {
        "transition_count": 8,
        "transition_probability": 1.0,
        "frequency_percent": 100.0
      }
    }
  },
  "state_count": 3,
  "total_transitions": 28
}
```

**Behavior:**
- Convert bigrams (source, target) to state → next_state mapping
- Calculate transition probabilities (count / total_outgoing_from_source)
- Group by source element

---

### CLI Interface (in `cli.py`)

```bash
# Extract bigrams
echo '{"traces": [...]}' | python -m tools.sequence_pattern_miner extract_ngrams --n 2 --min_frequency 1

# Extract all n-grams (unigrams through 4-grams)
echo '{"traces": [...]}' | python -m tools.sequence_pattern_miner extract_ngrams_by_length --min_n 1 --max_n 4

# Extract fact-only chains
echo '{"traces": [...]}' | python -m tools.sequence_pattern_miner extract_ngrams --n 2 --chain_filter fact_only

# Filter sequences
echo '{"sequences": [...]}' | python -m tools.sequence_pattern_miner filter_sequences --min_frequency 3 --max_frequency 10

# Rank by element type
echo '{"sequences": [...]}' | python -m tools.sequence_pattern_miner rank_sequences_by_element_type

# Convert to Markov transitions
echo '{"sequences": [...]}' | python -m tools.sequence_pattern_miner sequences_to_markov_transitions
```

**Exit codes:**
- `0` → success
- `1` → invalid input (ValueError)
- `2` → internal error (RuntimeError)

---

### Schema (in `sequence_schema.py`)

```python
from dataclasses import dataclass
from typing import List, Dict, Optional, Any

@dataclass
class Sequence:
    rank: int
    sequence: List[str]  # list of element IDs
    sequence_type: str   # "fact→fact", "grain→grain", "mixed", etc.
    occurrence_count: int
    frequency_percent: float
    traces_containing: Optional[List[str]] = None
    first_observed_trace: Optional[str] = None
    last_observed_trace: Optional[str] = None

@dataclass
class ExtractionStats:
    total_chains_analyzed: int
    total_ngrams_extracted: int
    unique_sequences: int
    most_common_frequency: int
    least_common_frequency: int
    average_frequency: float

@dataclass
class ExtractionReport:
    extraction_params: Dict[str, Any]
    statistics: ExtractionStats
    sequences: List[Sequence]

@dataclass
class MarkovTransition:
    source_element: str
    target_element: str
    transition_count: int
    transition_probability: float
    frequency_percent: float

@dataclass
class MarkovState:
    state: str
    outgoing_transitions: Dict[str, MarkovTransition]

@dataclass
class MarkovReport:
    transitions: Dict[str, Dict[str, MarkovTransition]]
    state_count: int
    total_transitions: int
```

---

## Error Handling

**Unified error taxonomy:**
- `FileNotFoundError` — not applicable
- `ValueError` — invalid n, invalid min_frequency, invalid chain_filter, empty traces
- `RuntimeError` — malformed trace structure
- `IOError` — not applicable

**Logging:**
- Use `structured_logger.get_event_logger("sequence_pattern_miner")`
- Events: `extraction_started`, `extraction_complete`, `extraction_failed`, `filtering_complete`
- Metadata: traces_analyzed, ngrams_extracted, unique_sequences, execution_time_ms

---

## Test Cases

### Happy Path
1. Extract bigrams from simple traces → correct frequency counts
2. Extract trigrams → correct 3-element sequences
3. Extract unigrams → single elements ranked
4. Extract with min_frequency=2 → only sequences appearing 2+ times
5. Fact-only chain filter → ignores grain elements
6. Grain-only chain filter → ignores fact elements
7. Extract across multiple lengths (n=1 to 4) → correct breakdown
8. Rank by element type → correct type classification
9. Convert bigrams to Markov → correct transitions and probabilities
10. Sequence appears in multiple traces → traces_containing list correct

### Edge Cases
11. Empty traces list → zero sequences, no error
12. Single-element chain → unigrams only (no bigrams)
13. All traces have identical chain → single sequence with 100% frequency
14. Traces with very different sequence patterns → diverse unique_sequences count
15. n equals chain length → single sequence per trace (no overlap)
16. n > max_chain_length → zero sequences (no ngrams possible)
17. min_frequency equals max occurrence → only one sequence passes filter
18. Multiple sequences with same frequency → ranked consistently (by first occurrence or alphabetically)
19. Mixed element type chains (fact→grain→fact→grain) → sequence_type marked as "mixed"
20. Element IDs are very long strings → handled correctly in output

### Error Cases
21. n < 1 → `ValueError`
22. n = 0 → `ValueError`
23. min_frequency < 1 → `ValueError`
24. min_frequency > max_frequency → `ValueError` (if both provided to filter)
25. Invalid chain_filter (not fact_only, grain_only, mixed, or None) → `ValueError`
26. Traces list is None or not a list → `ValueError`
27. Trace without chain field → `RuntimeError`
28. Trace with empty chain → parsed but skipped (no ngrams possible)
29. Sequence list is empty to filter → returns empty filtered list
30. max_n < min_n in extract_ngrams_by_length → `ValueError`

### CLI Behavior
31. CLI exit code 0 on success
32. CLI exit code 1 on ValueError
33. CLI exit code 2 on RuntimeError
34. CLI with --n and --chain_filter together → both applied
35. CLI reads valid JSON from stdin and outputs valid JSON

---

## Non-Goals (Explicitly Out of Scope)

- Statistical significance testing
- Entropy or information-theoretic measures
- Markov chain probability generation (that's a separate tool)
- Fuzzy or approximate sequence matching
- Smoothing or backoff strategies
- Multi-trace alignment
- Visualization or rendering
- Streaming/real-time pattern mining

---

## Implementation Notes

### Sequence Extraction
- Use sliding window: for chain of length n, extract positions [0:n], [1:n+1], ..., [len-n:len]
- Store sequences as tuples (hashable) for counting; convert to lists for JSON output
- Use `collections.Counter` to count frequency

### Sequence Type Inference
- Check element types in sequence: all "fact" → "fact→fact", all "grain" → "grain→grain", mixed → "mixed"
- Format: join types with "→" (e.g., "fact→grain→fact")

### Frequency Calculation
- Frequency % = (occurrence_count / total_ngrams_extracted) * 100
- total_ngrams_extracted = sum of all occurrence_counts

### Markov Transition Probability
- For each source element, count outgoing transitions
- Probability = outgoing_count / total_outgoing_from_source
- Example: if fact_123 → fact_456 happens 12 times and fact_123 → grain_789 happens 8 times, then:
  - P(fact_456 | fact_123) = 12/20 = 0.6
  - P(grain_789 | fact_123) = 8/20 = 0.4

### Performance
- Assume traces < 10k; linear iteration acceptable
- Counter operations are O(1) average case
- No special optimization needed for v1

---

## Success Criteria

- ✅ All 35 test cases pass (manually verified with terminal output)
- ✅ CLI exit codes correct (0, 1, 2)
- ✅ Frequency counts match manual verification
- ✅ Sequence types correctly inferred
- ✅ Markov probabilities sum to 1.0 per state
- ✅ Filtering logic correct (AND semantics with min/max)
- ✅ Extract-by-length returns correct breakdown
- ✅ Errors logged via structured_logger with context
- ✅ README documents all functions, examples, and edge cases

---

**Last updated:** 2026-07-14  
**Prepared by:** Claude  
**Status:** Ready for Hermes build
