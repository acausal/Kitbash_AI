# frequency_analysis

Token frequency statistics for a corpus (Historical AI batch). Stateless,
deterministic, stdlib-only. See SPEC-frequency_analysis_v1.md and the shared
Historical AI contract (SPEC-historical_ai_shared_contract_v1.md).

## Library

```python
from tools.frequency_analysis import analyze_frequencies, analyze_corpus_frequencies
r = analyze_frequencies(["a","a","b","c","c","c"], {"lowercase": True})
#   r["frequency_distribution"]: per-token {frequency, rank, percentile, coverage_percent}
#   r["statistics"]: mean/median/std_dev/quantiles, type_token_ratio, gini_coefficient
#   r["top_tokens"] / r["bottom_tokens"]
cr = analyze_corpus_frequencies([{"id":"d1","tokens":[...]}, ...], config)
```

Also: `compute_coverage(frequencies, threshold)` and
`frequency_histogram(frequencies, bin_edges)`.

## CLI

```bash
echo '{"tokens":["a","a","b","c","c","c"]}' | python -m tools.frequency_analysis
python -m tools.frequency_analysis --input corpus.json --corpus --output freq.json
python -m tools.frequency_analysis --input freqs.json --compute-coverage --coverage-threshold 0.9
python -m tools.frequency_analysis --input freqs.json --histogram
```

Each tool in the Historical AI batch shares the same envelope and config
(`lowercase`, `remove_stopwords`, `stopword_list`, `min_token_length`, `top_k`,
`threshold`, `verbose`); exit 0/1/2 with JSON error on stderr.

## Notes
- Shared boilerplate (config normalize, stopwords, envelope, CLI/error) lives in
  `tools/historical_common.py` (not a tool itself).
- `run_id`/`timestamp` differ per run; logic output is fully deterministic.
