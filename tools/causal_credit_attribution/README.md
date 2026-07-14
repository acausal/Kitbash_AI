# causal_credit_attribution

Attribute success credit to tools (or grains) in a successful trace — the
"who earned this win" tool feeding sleep Tier-2 learning-era improvement. The
user built the SPEC *before* the CWL episode-dependency work so its inputs can
absorb the brief's custom fields retroactively. Inverse of nothing (it's
positive-only); pairs with `success_pattern_miner` + `positive_signal_scorer`.

## Library

```python
from tools.causal_credit_attribution import (
    attribute_credit_to_tools, attribute_credit_to_grains, batch_attribute_credit)

r = attribute_credit_to_tools(trace, success_patterns, historical_traces, weights)
#   r["tool_attributions"]: [{position, tool, credit_score, attribution_signals{...},
#                             appears_in_patterns, historical_success_rate, confidence}, ...]
#   r["total_credit_attributed"] ~ 1.0
g = attribute_credit_to_grains(trace, grain_signal_scores, historical_traces, weights)
b = batch_attribute_credit(traces, success_patterns, historical_traces, weights)
#   b["aggregated_tool_credit"]: {tool: summed credit}
```

### 4 signals per component
- `positional` = `(N - i) / N` (later in chain → higher)
- `historical_correlation` = success rate of this component across `historical_traces`
- `pattern_membership` = `min(count_in_patterns / max_count, 1.0)` + 0.1 if the
  pattern is active in the current trace
- `input_output_salience` = v1 base heuristic **0.5**; elevated by the CWL brief's
  custom fields when present (see below)

Composite `credit_score` = weighted avg of the 4 signals; then **normalized to sum
1.0** so `total_credit_attributed ≈ 1.0`. Defaults: `historical_correlation 0.35,
positional 0.30, pattern_membership 0.25, input_output_salience 0.10`.

### Positional signal — SPEC erratum
The SPEC's formula line says `(N - i) / N`, but its own prose ("last tool gets
1.0, first gets 1/N") and worked API example (positional rises 0.15→0.20→0.25→0.35
down the chain) contradict it. Implemented as **`(i + 1) / N`** (later = higher),
matching the stated intent. Flagged in `attribution_signals.py`.
The brief (`BRIEF-CWL_EPISODE_DEPENDENCY_INTEGRATION.md`) proposes a `work_type`
(`exploratory`/`action`/`neutral`) + `depends_on_results` field per tool. When you
add them later, pass `tool_metadata={tool: {"work_type": ..., "depends_on_results":
bool}}` to `attribute_credit_to_tools` — `input_output_salience` will then use
`action`→0.8, `neutral`→0.6, `exploratory`→0.5, +0.1 if `depends_on_results`. Absent
→ base 0.5. No code change needed when the fields arrive.

## CLI

```bash
python -m tools.causal_credit_attribution --trace trace.json --output attr.json
python -m tools.causal_credit_attribution --trace trace.json \
    --patterns patterns.json --historical traces.jsonl --tool-metadata meta.json --output attr.json
python -m tools.causal_credit_attribution --traces traces.jsonl --batch --output batch.json
python -m tools.causal_credit_attribution --trace trace.json --grain --output attr_grains.json
```

`--patterns`/`--historical`/`--tool-metadata` are file paths **or** stdin. Custom
weights via `--weights-positional`, `--weights-historical-correlation`,
`--weights-pattern-membership`, `--weights-input-output-salience`.

Exit: `0` success · `1` invalid input · `2` I/O error.

## Confidence flag
`high` (historical_traces > 100 and ≥2 signal sources) · `medium` · `low`
(historical_traces < 10).

## Notes / deviations
- Signals are computed against the *whole* trace sequence; pattern membership uses
  the pattern's `sequence` (or `grain_sequence`).
- `attribute_credit_to_grains` uses `grain_activations` and reads
  `grain_signal_scores` as a fallback for historical success rate.
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH`:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.causal_credit_attribution ...`

## Requirements
- Pure stdlib (`json`, `collections`, `itertools`, `statistics`). No new deps.
