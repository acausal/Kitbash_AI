# SPEC: Log Parser v1

**Module:** `tools/log_parser/`  
**Status:** Ready for build  
**Dependencies:** stdlib (json, datetime)  
**Priority:** High (prepares traces for pattern mining; feeds Sequence Pattern Miner → Conditional Pattern Detector chain)

---

## Overview

Ingest raw execution traces (from dream bucket JSONL or raw text streams) and normalize them into structured trace objects suitable for pattern mining and sleep Tier 2 meta-learning.

**Design principle:** Simple streaming parser; no complex transformations. Input is JSONL traces from query orchestrator; output is normalized structured trace format with optional aggregation.

**Use case:** "Parse all execution traces from the last 24 hours, prepare them for sequence pattern mining to discover 'when query type X, tool sequence Y→Z→W always follows.'"

---

## Scope

### In Scope ✓
- Parse JSONL trace files (one JSON record per line)
- Parse individual JSON trace records (stdin or file)
- Normalize trace structure (ensure required fields present)
- Validate trace schema (correct types, non-empty chains)
- Extract and aggregate chain sequences (fact→fact→grain transitions)
- Optionally filter traces by time range, session, cartridge, or chain length
- Output: JSON array of normalized trace objects or newline-delimited JSON

### Out of Scope ✗
- Log rotation or compression
- Real-time streaming (one-shot batch processing)
- Log aggregation across multiple sources (single input file/stream)
- Statistical analysis of traces (separate tool)
- Natural language parsing of query text
- Trace deduplication or compression

---

## Module Structure

```
tools/log_parser/
  __init__.py                    # exports main functions
  core.py                        # implementation logic
  cli.py                         # argparse CLI
  log_schema.py                  # dataclasses for trace objects
  README.md                       # usage docs
  __main__.py                    # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

#### 1. `parse_jsonl_traces(jsonl_content: str) -> dict`

**Purpose:** Parse JSONL trace file (multi-line JSON, one record per line).

**Input:**
- `jsonl_content` (str): Raw JSONL string (may contain multiple records)

**Output (JSON):**
```json
{
  "parsing_report": {
    "total_lines": 100,
    "valid_traces": 95,
    "invalid_lines": 5,
    "errors": [
      {
        "line_number": 10,
        "error": "JSONDecodeError: ...",
        "line_content": "{incomplete json"
      }
    ]
  },
  "traces": [
    {
      "trace_id": "q_1_1721006445000",
      "query_id": "q_1_1721006445000",
      "chain_type": "intra_query",
      "session_id": "session_abc123",
      "timestamp": "2026-07-14T14:30:45Z",
      "chain": [
        {
          "position": 0,
          "element_id": "fact_123",
          "element_type": "fact",
          "traversal_type": "cartridge_lookup",
          "cartridge": "memories"
        },
        {
          "position": 1,
          "element_id": "grain_456",
          "element_type": "grain",
          "traversal_type": "grain_activation"
        }
      ],
      "chain_length": 2,
      "context": {
        "hat": "reasoning",
        "project": "general"
      }
    }
  ]
}
```

**Behavior:**
- Read line by line; skip empty lines
- Attempt to parse each line as JSON
- Catch and log parse errors (include line number and content for debugging)
- Normalize each valid trace (see **Trace Normalization** below)
- Return both parsing report (errors) and normalized traces

**Error handling:**
- Non-fatal: Invalid JSON on a line → log error, skip line, continue
- Fatal: No valid traces found → return empty traces array

---

#### 2. `parse_json_trace(json_str: str) -> dict`

**Purpose:** Parse and normalize a single JSON trace record.

**Input:**
- `json_str` (str): Single JSON trace object (may span multiple lines)

**Output (JSON):**
```json
{
  "trace_id": "q_1_1721006445000",
  "query_id": "q_1_1721006445000",
  "chain_type": "intra_query",
  "session_id": "session_abc123",
  "timestamp": "2026-07-14T14:30:45Z",
  "chain": [
    /* normalized chain steps */
  ],
  "chain_length": 2,
  "context": { /* ... */ }
}
```

**Behavior:**
- Parse JSON string
- Validate required fields (query_id, chain, chain_type)
- Normalize chain (ensure consistent position, element_type, traversal_type)
- Infer timestamp if missing (use current time)
- Return normalized trace

**Error handling:**
- `ValueError` if JSON parse fails
- `ValueError` if required fields missing (query_id, chain)
- `ValueError` if chain is empty

---

#### 3. `normalize_trace(raw_trace: dict) -> dict`

**Purpose:** Apply normalization rules to raw trace (internal helper, can be exported for testing).

**Normalization rules:**
1. Ensure trace has required fields: `query_id`, `chain`, `chain_type`
2. Default missing optional fields: `session_id` → None, `timestamp` → now, `context` → {}
3. Ensure chain is non-empty list
4. For each chain step:
   - Add `position` (index in chain)
   - Ensure `element_id` is present (either `fact_id`, `grain_id`, or explicit `element_id`)
   - Infer `element_type` (if missing, infer from presence of `fact_id` or `grain_id`)
   - Ensure `traversal_type` is present (or default to "unknown")
   - Add `cartridge` if inferable from context
5. Add synthetic fields: `trace_id` (if missing), `chain_length`
6. Validate types (query_id: str, chain: list, chain_length: int)

**Input/Output:**
```python
# Input
{
  "query_id": "q_1_1721006445000",
  "chain": [
    {"fact_id": 123},
    {"grain_id": 456, "traversal_type": "activation"}
  ],
  "chain_type": "intra_query"
}

# Output (normalized)
{
  "trace_id": "q_1_1721006445000",
  "query_id": "q_1_1721006445000",
  "chain_type": "intra_query",
  "session_id": null,
  "timestamp": "2026-07-14T14:30:45Z",
  "chain": [
    {
      "position": 0,
      "element_id": 123,
      "element_type": "fact",
      "traversal_type": "unknown"
    },
    {
      "position": 1,
      "element_id": 456,
      "element_type": "grain",
      "traversal_type": "activation"
    }
  ],
  "chain_length": 2,
  "context": {}
}
```

---

#### 4. `filter_traces(traces: list, filters: dict) -> dict`

**Purpose:** Filter normalized traces by criteria (time range, session, chain length, etc.).

**Input:**
- `traces` (list): Normalized trace objects (from `parse_jsonl_traces`)
- `filters` (dict): Filter criteria (all optional)
  - `min_timestamp` (str, ISO 8601): Only traces after this time
  - `max_timestamp` (str, ISO 8601): Only traces before this time
  - `session_ids` (list of str): Only traces from these sessions (if session_id matches)
  - `chain_type` (str): Only traces of this type ("intra_query", "inter_query", etc.)
  - `min_chain_length` (int): Only traces with chain_length >= this
  - `max_chain_length` (int): Only traces with chain_length <= this
  - `element_types` (list of str): Only traces containing at least one of these element types
  - `cartridges` (list of str): Only traces touching these cartridges

**Output (JSON):**
```json
{
  "filter_criteria": {
    "min_timestamp": "2026-07-14T00:00:00Z",
    "max_timestamp": "2026-07-14T23:59:59Z",
    "min_chain_length": 2
  },
  "total_traces_input": 100,
  "traces_after_filtering": 75,
  "filtered_out": 25,
  "traces": [
    /* filtered traces */
  ]
}
```

**Behavior:**
- Apply all filters (AND logic: trace must match ALL criteria to pass)
- Track how many traces were filtered out for reporting
- Return filtered trace list + report

**Error handling:**
- `ValueError` if filter criteria are invalid (e.g., min > max timestamp)

---

#### 5. `aggregate_chains(traces: list) -> dict`

**Purpose:** Extract and aggregate all chains as sequences for pattern mining.

**Input:**
- `traces` (list): Normalized trace objects

**Output (JSON):**
```json
{
  "total_traces": 100,
  "total_chains_extracted": 100,
  "unique_chain_sequences": 45,
  "sequence_frequency": [
    {
      "sequence": ["fact_123", "fact_456", "grain_789"],
      "sequence_type": "fact→fact→grain",
      "occurrence_count": 12,
      "frequency_percent": 12.0
    },
    {
      "sequence": ["grain_001", "fact_042"],
      "sequence_type": "grain→fact",
      "occurrence_count": 8,
      "frequency_percent": 8.0
    }
  ],
  "sequence_type_distribution": {
    "fact": 75,
    "grain": 20,
    "mixed": 5
  }
}
```

**Behavior:**
- Extract chain from each trace (sequence of element_ids)
- Count frequency of each unique sequence
- Infer sequence type (all facts, all grains, mixed)
- Sort by frequency (descending)
- Calculate statistics

---

#### 6. `extract_chain_steps(traces: list) -> dict`

**Purpose:** Break chains into individual transitions (fact→fact, grain→grain, fact→grain, etc.) for n-gram analysis.

**Input:**
- `traces` (list): Normalized trace objects

**Output (JSON):**
```json
{
  "total_traces": 100,
  "total_steps_extracted": 350,
  "unique_step_types": 5,
  "step_frequency": [
    {
      "from_element": "fact_123",
      "from_type": "fact",
      "to_element": "fact_456",
      "to_type": "fact",
      "transition_type": "fact→fact",
      "occurrence_count": 25,
      "frequency_percent": 7.14
    }
  ],
  "transition_type_distribution": {
    "fact→fact": 200,
    "grain→grain": 75,
    "fact→grain": 50,
    "grain→fact": 25
  }
}
```

**Behavior:**
- For each chain, extract consecutive pairs (step[i] → step[i+1])
- Track source element, target element, source type, target type
- Count frequency of each unique transition
- Categorize by transition type

---

### CLI Interface (in `cli.py`)

All commands read from stdin (JSON/JSONL) or file; output to stdout (JSON).

```bash
# Parse JSONL file
cat traces.jsonl | python -m tools.log_parser parse_jsonl_traces

# Parse single JSON trace
echo '{"query_id": "q_1", "chain": [...], "chain_type": "intra_query"}' \
  | python -m tools.log_parser parse_json_trace

# Filter traces by time range
echo '{"traces": [...], "filters": {"min_timestamp": "2026-07-14T00:00:00Z", "max_timestamp": "2026-07-14T23:59:59Z"}}' \
  | python -m tools.log_parser filter_traces

# Extract chain sequences
echo '{"traces": [...]}' | python -m tools.log_parser aggregate_chains

# Extract transitions for n-gram analysis
echo '{"traces": [...]}' | python -m tools.log_parser extract_chain_steps

# Parse JSONL from file + filter + aggregate in one step
python -m tools.log_parser parse_jsonl_traces --input traces.jsonl --filter '{"min_chain_length": 2}' --aggregate
```

**Exit codes:**
- `0` → success
- `1` → invalid input (ValueError)
- `2` → file not found (FileNotFoundError)
- `3` → internal error (RuntimeError)

---

### Schema (in `log_schema.py`)

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

@dataclass
class ChainStep:
    position: int
    element_id: str  # or fact_id / grain_id
    element_type: str  # "fact" or "grain"
    traversal_type: str
    cartridge: Optional[str] = None
    timestamp: Optional[str] = None
    weight: Optional[float] = None

@dataclass
class Trace:
    trace_id: str
    query_id: str
    chain_type: str  # "intra_query", "inter_query", etc.
    chain: List[ChainStep]
    session_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    chain_length: int = field(init=False)
    context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.chain_length = len(self.chain)

@dataclass
class ParseReport:
    total_lines: int
    valid_traces: int
    invalid_lines: int
    errors: List[Dict[str, Any]]  # line_number, error, line_content

@dataclass
class FilterReport:
    filter_criteria: Dict[str, Any]
    total_traces_input: int
    traces_after_filtering: int
    filtered_out: int

@dataclass
class AggregatedChainStats:
    total_traces: int
    unique_chain_sequences: int
    sequence_frequency: List[Dict[str, Any]]
    sequence_type_distribution: Dict[str, int]

@dataclass
class TransitionStats:
    total_traces: int
    total_steps_extracted: int
    unique_step_types: int
    step_frequency: List[Dict[str, Any]]
    transition_type_distribution: Dict[str, int]
```

---

## Input Format Specifications

### JSONL Trace Format (from query_orchestrator)

```jsonl
{"type":"trace","chain_type":"intra_query","query_id":"q_1_1721006445000","chain":[{"fact_id":123,"traversal_type":"cartridge_lookup","element_type":"fact"},{"grain_id":456,"traversal_type":"grain_activation","element_type":"grain"}],"chain_length":2,"session_id":"session_abc123","context":{"hat":"reasoning","project":"general"}}
{"type":"trace","chain_type":"intra_query","query_id":"q_2_1721006450000","chain":[{"fact_id":789,"traversal_type":"cartridge_lookup"}],"chain_length":1,"session_id":"session_abc123","context":{}}
```

**Fields:**
- `type` (str): Always "trace" (for filtering, if mixed with other log types)
- `query_id` (str): Unique query identifier
- `chain` (list): Sequence of element accesses
- `chain_type` (str): "intra_query" or "inter_query"
- `session_id` (str, optional): Session this query belongs to
- `context` (dict, optional): Additional metadata (hat, project, cartridge, etc.)

### Raw Trace Step Format

```json
{
  "fact_id": 123,              // or grain_id
  "element_type": "fact",      // optional; inferred from fact_id/grain_id
  "traversal_type": "cartridge_lookup",  // how it was accessed
  "timestamp": "2026-07-14T14:30:45Z",   // optional
  "weight": 0.85,              // optional; salience weight
  "cartridge": "memories"      // optional; which domain
}
```

---

## Error Handling

**Unified error taxonomy:**
- `FileNotFoundError` — input file not found
- `ValueError` — invalid JSON, missing required fields, invalid filter criteria, empty trace
- `RuntimeError` — internal parsing error (corrupted data structure)
- `IOError` — output write failure

**Logging:**
- Use `structured_logger.get_event_logger("log_parser")`
- Events: `parsing_started`, `parsing_complete`, `parsing_failed`, `filtering_started`, `aggregation_complete`
- Metadata: traces_read, traces_output, errors_logged, execution_time_ms

---

## Test Cases

### Happy Path
1. Parse single JSONL trace → normalized with all fields
2. Parse multi-line JSONL (3 traces) → all normalized correctly
3. Parse trace with minimal fields (only query_id, chain) → defaults applied
4. Parse trace with full context → all context preserved
5. Filter by time range → correct traces included/excluded
6. Filter by chain_length (min=2) → only traces with length ≥2
7. Filter by session_id → only traces from specified session
8. Aggregate chains → correct frequency counts
9. Extract transitions → correct pair counts and types
10. Mixed chain (fact→grain→fact) → correct transition sequence

### Edge Cases
11. Empty JSONL file → zero traces, no errors
12. JSONL with empty lines (blank lines between records) → skipped gracefully
13. Trace with chain of length 1 (no transitions) → parsed, but no steps in extract_chain_steps
14. Trace with null session_id → preserved as None
15. Missing element_type in chain step → inferred from fact_id/grain_id
16. Missing traversal_type → defaults to "unknown"
17. Chain step with both fact_id and grain_id (ambiguous) → fact_id takes precedence
18. Trace with Unicode in context → preserved correctly
19. Very large chain (1000+ elements) → parsed without truncation
20. Filter with no matches → returns empty traces array

### Error Cases
21. Invalid JSON in JSONL line → error logged, line skipped, parsing continues
22. Missing query_id in trace → `ValueError`
23. Missing chain (empty or null) → `ValueError`
24. Invalid timestamp format → `ValueError`
25. Invalid filter criteria (min > max chain_length) → `ValueError`
26. Malformed chain step (no element_id, no fact/grain_id) → logged as warning, skip step
27. Invalid element_type → preserved but flagged in output
28. File not found (--input flag) → `FileNotFoundError`
29. Duplicate query_ids in different traces → allowed (no enforced uniqueness)
30. Invalid session_id format (very long string) → accepted as-is

### CLI Behavior
31. CLI exit code 0 on success
32. CLI exit code 1 on ValueError (bad input)
33. CLI exit code 2 on FileNotFoundError
34. CLI exit code 3 on RuntimeError
35. CLI with --input file → reads from file instead of stdin
36. CLI with --output file → writes to file instead of stdout
37. CLI with --filter and --aggregate → chains them (parse → filter → aggregate)

---

## Non-Goals (Explicitly Out of Scope)

- Real-time streaming (batch processing only)
- Log rotation or compression
- Distributed log aggregation
- Complex SQL-like queries
- Trace deduplication
- Statistical significance testing
- Anomaly detection in logs
- Automatic trace schema inference (schema is fixed/documented)

---

## Implementation Notes

### Normalization Strategy
- Lenient parsing (ignore unknown fields, don't fail on missing optional fields)
- Strict validation (fail on missing required fields)
- Consistent defaults (timestamp: now, session_id: None, context: {})
- Idempotent (parsing twice yields same result)

### Timestamp Handling
- Accept ISO 8601 strings; parse via datetime.fromisoformat()
- If missing, default to datetime.utcnow().isoformat() + 'Z'
- Store all timestamps in ISO 8601 format
- Comparisons (for filtering) via string comparison (ISO strings are sortable)

### Chain Step Inference
- If `fact_id` present → element_type = "fact", element_id = fact_id
- If `grain_id` present → element_type = "grain", element_id = grain_id
- If `element_id` present and type missing → infer from context or error
- If both fact_id and grain_id present → fact_id takes precedence, log warning

### Sequence Aggregation
- Use dict to track {sequence: count}; iterate over dict to build output
- For very large traces, sequence representation could be lossy (truncate?)
- Consider: store sequences as "fact_123→fact_456→grain_789" (string) or list (list)
- Recommend: list (more composable with downstream tools)

---

## Success Criteria

- ✅ All 37 test cases pass (manually verified with terminal output)
- ✅ CLI exit codes correct (0, 1, 2, 3)
- ✅ JSONL parsing handles mixed valid/invalid lines gracefully
- ✅ Normalization produces consistent structure (all traces have same keys)
- ✅ Filtering logic applies AND semantics (all criteria must match)
- ✅ Chain aggregation counts match manual verification
- ✅ Transition extraction correctly pairs consecutive elements
- ✅ Timestamps in ISO 8601 format (sortable, parseable)
- ✅ Errors logged via structured_logger with context
- ✅ README documents all functions, filter criteria, and examples

---

**Last updated:** 2026-07-14  
**Prepared by:** Claude  
**Status:** Ready for Hermes build
