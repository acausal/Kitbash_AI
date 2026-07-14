# success_pattern_miner

Mine recurring **success** patterns from execution traces — the inverse of
`anomaly_scorer`/`sequence_pattern_miner`. Filter input to successful traces
(`outcome == "success"` OR `error_signal < success_threshold`), then discover
frequent tool sequences, grain activation patterns, and mixed co-occurrence.
Feeds sleep Tier-2 positive-feedback learning. Isolation-first (stdlib only +
optional `structured_logger`).

## Library

```python
from tools.success_pattern_miner import (
    mine_success_tool_sequences, mine_success_grain_patterns,
    mine_mixed_success_patterns,
)

# tool sequences in successful traces
r = mine_success_tool_sequences(traces, min_frequency=3, success_threshold=0.2)
#   r["patterns"]: [{pattern_id, sequence, frequency, support, coverage,
#                     pattern_type:"success_sequence", confidence_estimate, ...}]

# grain activation patterns during success
g = mine_success_grain_patterns(traces, min_frequency=3)

# mixed tool + grain co-occurrence
m = mine_mixed_success_patterns(traces, min_frequency=3)
```

Every function returns a **plain JSON-serializable dict**.

### Success filtering (impl note 1)
A trace is a success iff `outcome == "success"` OR `error_signal < success_threshold`.
Non-success traces are dropped before mining.

### Pattern extraction (impl note 2)
Sliding n-grams of length **2–6** over `sequence` (tools, str list) or
`grain_activations` (int list). Counted with `collections.Counter`, ranked
descending (ties broken by sequence for determinism).

### Metrics (impl notes 4–6)
- `support = frequency / success_traces_count`
- `coverage = traces_containing_pattern / success_traces_count`
- `confidence_estimate = clamp((frequency / min_frequency) * (coverage / 0.5), 0..1)`

## CLI

Reads traces from `--input` (file) or **stdin**; dispatches on `--pattern-type`;
writes JSON to `--output` or stdout. Accepts JSON array **or JSONL** (one trace
per line).

```bash
python -m tools.success_pattern_miner --input traces.jsonl \
    --pattern-type sequences --min-frequency 3 --success-threshold 0.2 \
    --output patterns.json

python -m tools.success_pattern_miner --input traces.jsonl \
    --pattern-type grains --output patterns.json

python -m tools.success_pattern_miner --input traces.jsonl \
    --pattern-type mixed --time-window-hours 24 --output patterns.json
```

**Exit codes:** `0` success · `1` invalid input (`ValueError`, bad JSON/format) ·
`2` I/O error (file not found).

## Input trace schema

```json
{"trace_id":"tr_1","sequence":["tokenizer","negation_detector"],
 "grain_activations":[42,137],"outcome":"success","error_signal":0.05,
 "timestamp":"2026-07-14T10:30:00Z"}
```

Required: `trace_id`/`query_id`, `timestamp`, and at least one of
`sequence`/`grain_activations`. `outcome` and `error_signal` drive success.

## Behavior notes

- Empty traces → empty `patterns`, no error.
- Time window drops success traces older than `time_window_hours` (and any trace
  with an unparseable timestamp when a window is set).
- Fail-loud (`ValueError`) on missing required fields or non-numeric `error_signal`.

## Divergence from sequence_pattern_miner

`sequence_pattern_miner` consumes the *normalized* `log_parser` shape (a `chain`
of `{element_type, element_id}` dicts). This tool uses the **success_pattern_miner
SPEC's own simpler schema** (`sequence`/`grain_activations` lists directly), per
that SPEC's authoritative contract. They share philosophy (n-gram counting) but
not input shape.

## Requirements

- Pure stdlib (`json`, `collections`, `datetime`). No new deps.
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.success_pattern_miner ...`
