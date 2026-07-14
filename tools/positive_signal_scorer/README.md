# positive_signal_scorer

Rank success patterns (from `success_pattern_miner`) by how trustworthy they
are — the inverse of `anomaly_scorer`. Computes 5 signal dimensions per pattern,
combines them into a composite `signal_strength` in [0,1], ranks descending, and
flags weak-sample patterns. Feeds sleep Tier-2 positive-feedback calibration.
Isolation-first (stdlib only + optional `structured_logger`).

## Library

```python
from tools.positive_signal_scorer import score_patterns, compute_signal_dimension

r = score_patterns(patterns, traces, weights=None)
#   r["patterns"]: [{pattern_id, pattern, signal_strength, rank,
#                     signal_dimensions{...}, sample_size, sample_size_confidence,
#                     success_rate_given_pattern, coverage, notes}, ...]

dim = compute_signal_dimension(patterns, traces, "outcome_correlation")
```

Every function returns a **plain JSON-serializable dict**.

### Signal dimensions (impl notes 1–4)
A pattern "fires" in a trace when its sequence is a **contiguous subsequence** of
`trace["sequence"]` (or `grain_sequence`).

- `frequency_score` = `min(frequency / median_frequency_across_patterns, 1.0)`
- `support_score` = pattern's own `support` field (clamped [0,1])
- `outcome_correlation_score` = `(pattern AND success) / (pattern fires)`
- `consistency_score` = `max(1.0 - cv(error_signals_of_firing_traces), 0.0)`
  (coefficient of variation = std/mean; low variance → high score)
- `temporal_stability_score` = `1.0 - (max_bucket_corr - min_bucket_corr)` over 3
  equal time buckets of firing traces (stable → high)

### Composite (weights from SPEC)
`signal_strength` = weighted sum of the 5 dimensions.
Default: `outcome_correlation 0.35, consistency 0.20, frequency 0.15,
support 0.15, temporal_stability 0.15` (auto-normalized if you override a subset).

### Confidence flag
`sample_size_confidence`: `very_high` (≥50), `adequate` (≥10), `low` (<10).

## CLI

Reads patterns + traces from `--patterns` / `--traces` files **or stdin**; writes
JSON to `--output` or stdout. Single-dimension mode via `--dimension`. Custom
weights via `--weights-<dim>` flags.

```bash
python -m tools.positive_signal_scorer --patterns patterns.json \
    --traces traces.jsonl --output scored.json
python -m tools.positive_signal_scorer --patterns patterns.json \
    --traces traces.jsonl --dimension outcome_correlation
python -m tools.positive_signal_scorer --patterns patterns.json \
    --traces traces.jsonl --weights-outcome-correlation 0.5 --output scored.json
```

**Exit codes:** `0` success · `1` invalid input (`ValueError`) · `2` I/O error.

## Notes / deviations
- Both `--patterns` and `--traces` may be JSON array **or JSONL** (one item/line).
- If neither file is given for a stream, that stream is read from stdin (patterns
  takes precedence; traces fall back to stdin if patterns came from a file).
- `sample_size` = pattern's `frequency` (falling back to firing-trace count).

## Requirements
- Pure stdlib (`json`, `statistics`, `collections`, `datetime`). No new deps.
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.positive_signal_scorer ...`
