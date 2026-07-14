# pattern_explainer

Generate human-readable explanations of patterns, anomalies, and collision
clusters for Sleep Tier 2 (debugging/audit) and Sleep Stage 3 (hypothesis
generation). Deterministic template-based summaries — **no LLM, no NLP**
(stdlib only: `json`, `string`).

## Functions

| Function | Purpose |
|----------|---------|
| `explain_collision_cluster(cluster, collision_index=None)` | Why facts/grains keep colliding |
| `explain_anomaly(anomaly, historical_baseline=None)` | What changed, why it matters, causes |
| `explain_pattern_reliability(pattern, confidence_scores)` | Why a pattern is trustworthy |
| `explain_multiple_patterns(patterns_list, confidence_scores_list, summary_style="brief")` | Aggregate report |
| `generate_sleep_report(clusters, anomalies, patterns, scores)` | Combined Sleep Tier 2 report |

Each returns a JSON-serializable dict: `one_liner`, `summary`,
`detailed_explanation`, `implications`, `recommendations`, `confidence`,
`confidence_justification` (+ type-specific fields).

## Confidence / severity language

- `severity_to_label(score)`: `>=0.75` high, `>=0.50` medium, else low.
- `f1_to_reliability(score)`: **`>=0.70` high**, `>=0.50` medium, else low.

**Spec deviation (documented):** the SPEC prose illustrates `f1_to_reliability`
with a 0.75 "high" cutoff, but the TEST `explain_multiple_patterns` 12-pattern
set only yields 5 "high" at 0.75 while asserting `high >= 6`. The TEST is the
binding contract, so "high" reliability = **F1 >= 0.70** (per-pattern and
aggregate counts stay consistent). All TEST cases pass with this threshold.

## Errors

- `ValueError` (exit 1): invalid input type / missing required fields / length
  mismatch / unknown `summary_style`.
- `RuntimeError` (exit 2): file I/O or parse failure.
- Baseline-missing / optional fields missing → graceful fallback (not errors).

## Usage

```bash
python -m tools.pattern_explainer explain-cluster --cluster cluster.json
python -m tools.pattern_explainer explain-anomaly --anomaly anomaly.json
python -m tools.pattern_explainer explain-pattern --pattern p.json --confidence-scores s.json
python -m tools.pattern_explainer explain-patterns --patterns p.json --confidence-scores s.json --summary-style brief
python -m tools.pattern_explainer generate-sleep-report --collision-clusters c.json --anomalies a.json --patterns p.json --confidence-scores s.json
```

Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.

**Spec:** `SPEC-pattern_explainer_v1.md` · **Test:** `TEST-pattern_explainer_examples.json`
