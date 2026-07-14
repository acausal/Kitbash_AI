# sequence_pattern_miner

Mine recurring n-gram sequences from normalized execution traces (consumes
`log_parser` output). Discovers patterns like "when query type X, tool sequence
Y→Z→W follows" via exact frequency counting — no statistical tests (v1). Feeds
sleep Tier-2 meta-learning and the downstream Markov Chain tool. Isolation-first
(stdlib only + optional `structured_logger`).

## Library

```python
from tools.sequence_pattern_miner import (
    extract_ngrams, extract_ngrams_by_length, filter_sequences,
    rank_sequences_by_element_type, sequences_to_markov_transitions,
)

ng   = extract_ngrams(traces, n=2, min_frequency=1, chain_filter=None)
alln = extract_ngrams_by_length(traces, min_n=1, max_n=4, min_frequency=1)
flt  = filter_sequences(ng["sequences"], min_frequency=3, max_frequency=10)
byt  = rank_sequences_by_element_type(ng["sequences"])
mk   = sequences_to_markov_transitions(ng["sequences"])   # bigrams -> transitions
```

Every function returns a **plain JSON-serializable dict**. Elements use the
prefixed `"<type>_<id>"` form (e.g. `"fact_123"`), consistent with `log_parser`.

### Sequence extraction

- Sliding window of size `n` over each trace's chain (positions `[i:i+n]`).
- Frequency counted via `collections.Counter`; ranked descending, ties broken by
  sequence for determinism.
- `frequency_percent = occurrence_count / total_ngrams_extracted * 100`.
- `traces_containing` / `first_observed_trace` / `last_observed_trace` track
  which traces (by `trace_id`/`query_id`) contain each sequence, in first-seen order.

### `chain_filter` (trace-level, not element-level)

- `None` — all traces (default)
- `"fact_only"` — only traces where **all** chain steps are facts
- `"grain_only"` — only traces where **all** chain steps are grains
- `"mixed"` — only traces containing **both** fact and grain steps

Non-matching traces are skipped entirely.

### `sequence_type`

Homogeneous or 2-element sequences → joined types (`fact→fact`, `grain→fact`,
`fact→fact→fact`); 3+ elements with more than one type → `"mixed"`.

### Markov transitions

Bigrams only (length-2 sequences). For each source: `probability = count /
total_outgoing_from_source`; probabilities sum to 1.0 per state.

## CLI

Reads a JSON object from **stdin**, writes JSON to **stdout**. Typed flags
override payload keys:

```bash
echo '{"traces":[...]}' | python -m tools.sequence_pattern_miner extract_ngrams --n 2 --min_frequency 1
echo '{"traces":[...]}' | python -m tools.sequence_pattern_miner extract_ngrams_by_length --min_n 1 --max_n 4
echo '{"traces":[...]}' | python -m tools.sequence_pattern_miner extract_ngrams --n 2 --chain_filter fact_only
echo '{"sequences":[...]}' | python -m tools.sequence_pattern_miner filter_sequences --min_frequency 3 --max_frequency 10
echo '{"sequences":[...]}' | python -m tools.sequence_pattern_miner rank_sequences_by_element_type
echo '{"sequences":[...]}' | python -m tools.sequence_pattern_miner sequences_to_markov_transitions
```

**Exit codes:** `0` success · `1` invalid input (`ValueError`/bad JSON) ·
`2` internal error (`RuntimeError`, e.g. malformed trace structure).

## Behavior notes

- `n` larger than every chain → zero sequences (no error); `n < 1` → `ValueError`.
- Empty `traces` → zero sequences, no error.
- Trace missing `chain` field → `RuntimeError`; empty chain → skipped.

## Requirements

- Pure stdlib (`json`, `collections`, `itertools`). No new deps.
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.sequence_pattern_miner ...`
