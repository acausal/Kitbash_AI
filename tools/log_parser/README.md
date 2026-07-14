# log_parser

Ingest raw execution traces (JSONL from the query orchestrator / dream bucket, or
single JSON records) and normalize them into structured trace objects for pattern
mining (feeds the Sequence Pattern Miner → Conditional Pattern Detector chain).
Isolation-first tool (stdlib only + optional `structured_logger`); one-shot batch,
no streaming.

## Library

```python
from tools.log_parser import (
    parse_jsonl_traces, parse_json_trace, normalize_trace,
    filter_traces, aggregate_chains, extract_chain_steps,
)

parsed = parse_jsonl_traces(open("traces.jsonl").read())   # {parsing_report, traces}
one    = parse_json_trace('{"query_id":"q1","chain":[...],"chain_type":"intra_query"}')
norm   = normalize_trace({"query_id":"q1","chain":[{"fact_id":123}],"chain_type":"intra_query"})
flt    = filter_traces(parsed["traces"], {"min_chain_length": 2})
agg    = aggregate_chains(parsed["traces"])       # unique sequence frequencies
steps  = extract_chain_steps(parsed["traces"])    # consecutive transitions (n-gram)
```

Every function returns a **plain JSON-serializable dict**.

### Normalization rules

- **Required:** `query_id` (str), `chain` (non-empty list), `chain_type`. Missing → `ValueError`.
- **Defaults:** `session_id` → `null`, `timestamp` → now (ISO 8601 `Z`), `context` → `{}`, `trace_id` → `query_id`.
- **Chain steps:** `fact_id` → type `fact`, `grain_id` → type `grain` (fact wins if both present); explicit `element_id` keeps its `element_type` (or `unknown`); missing `traversal_type` → `unknown`. Steps with no id are **skipped** (logged). `element_id` is kept **raw**.
- **Timestamps:** validated via `datetime.fromisoformat` (accepts trailing `Z`); bad format → `ValueError`. Filter comparisons are string-based (ISO is sortable).

### Aggregation / transitions

Sequences and transitions use the **prefixed** form `"<type>_<id>"` (e.g. `"fact_123"`),
per the SPEC output examples. `aggregate_chains` counts unique full sequences;
`extract_chain_steps` counts consecutive pairs (chains of length 1 yield no steps).

## CLI

Reads JSON/JSONL from **stdin** (or `--input FILE`), writes JSON to **stdout**
(or `--output FILE`):

```bash
cat traces.jsonl | python -m tools.log_parser parse_jsonl_traces
echo '{"query_id":"q1","chain":[{"fact_id":123}],"chain_type":"intra_query"}' \
  | python -m tools.log_parser parse_json_trace
echo '{"traces":[...],"filters":{"min_chain_length":2}}' | python -m tools.log_parser filter_traces
echo '{"traces":[...]}' | python -m tools.log_parser aggregate_chains
echo '{"traces":[...]}' | python -m tools.log_parser extract_chain_steps
# chaining: parse -> filter -> aggregate
python -m tools.log_parser parse_jsonl_traces --input traces.jsonl \
  --filter '{"min_chain_length":2}' --aggregate
```

**Exit codes:** `0` success · `1` invalid input (`ValueError`/bad JSON) ·
`2` file not found · `3` internal / write error (`RuntimeError`/`OSError`).

## Requirements

- Pure stdlib (`json`, `datetime`). No new deps.
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.log_parser ...`
