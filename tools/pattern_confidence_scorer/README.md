# pattern_confidence_scorer

Score discovered patterns (tool sequences, collision pairs, grain chains)
against execution traces or Dream Bucket observations to produce reliability
metrics (precision, recall, F1, TPR, FPR, specificity, support). Feeds Sleep
Tier 2 pattern ranking. Pure stdlib (`json`, `collections`, `math`,
`datetime`) — no new deps.

## Library

```python
from tools.pattern_confidence_scorer import (
    score_patterns_against_traces, score_patterns_against_dream_bucket,
    compare_pattern_reliability, decay_confidence_by_age,
)

res = score_patterns_against_traces(patterns, traces, pattern_type="sequence")
for s in res["pattern_scores"]:
    print(s["pattern_id"], s["metrics"], s["interpretation"])
```

Every function returns a **plain JSON-serializable dict**.

### Confusion matrix (per pattern vs. observations)
- `TP` = pattern fired AND outcome correct (success/correct)
- `FP` = pattern fired AND outcome incorrect (failure/false_positive)
- `TN` = pattern did NOT fire AND outcome correct
- `FN` = pattern did NOT fire AND outcome incorrect

### Metrics (standard textbook)
- `precision` = TP/(TP+FP)
- `recall` (= `true_positive_rate`) = TP/(TP+FN)
- `f1_score` = 2·P·R/(P+R)
- `false_positive_rate` = FP/(FP+TN)
- `specificity` = TN/(FP+TN) = 1 − FPR   (complements FPR, always)
- `support` = TP+FP

### Reliability / flags
- reliability: `high` (F1 ≥ 0.75), `medium` (0.5–0.75), `low` (< 0.5)
- `confidence_flag` (single, most severe): `high_false_positive_rate` (FPR > 0.3),
  `low_f1_score` (F1 < 0.5), `low_sample_size` (support < 20), else `none`.

### Pattern matching
- `sequence`: pattern is a **contiguous subsequence** of the trace sequence.
- `collision`: `collision_pair:[returned_id, correct_id]` matches a
  `false_positive` (exact IDs) or `collision_cluster` (both IDs in cluster).
- `grain_chain`: all pattern grains present in trace grain sequence, order
  preserved (subsequence).

### Functions
- `score_patterns_against_traces(patterns, traces, pattern_type="sequence")`
- `score_patterns_against_dream_bucket(patterns, dream_bucket_file, pattern_type="sequence")`
- `compare_pattern_reliability(patterns, traces_file=None, dream_bucket_file=None, pattern_type="sequence")`
- `decay_confidence_by_age(pattern_scores, decay_factor=0.99, reference_date=None)`

## ⚠ SPEC/test deviation (FPR & specificity)
The provided ground-truth file `TEST-pattern_confidence_scorer_examples.json`
contains **non-standard and internally inconsistent** FPR/specificity values
(e.g. case 1 expects `FPR=0.4`, `specificity=0.67` — which cannot both hold,
since standard FPR + specificity = 1). Reverse-engineering shows the reference
used `FPR = FP / total_successes` and `specificity = TN / total_failures`, which
are semantically wrong. **This tool implements the correct textbook metrics.**
All other fields (precision, recall, F1, TPR, support, TP/FP/TN/FN, reliability,
flags) match the JSON exactly. The JSON's FPR/specificity values are documented
here as known-bad references; verify against the other fields.

## Error taxonomy (exit codes)
`ValueError` → CLI 1 (bad pattern_type / empty traces / bad decay params) ·
`FileNotFoundError` / `OSError` / `RuntimeError` → CLI 2 (file IO / matching).

## CLI

```bash
python -m tools.pattern_confidence_scorer score-traces \
  --patterns patterns.json --traces traces.jsonl --pattern-type sequence
python -m tools.pattern_confidence_scorer score-dream-bucket \
  --patterns patterns.json --dream-bucket db.jsonl --pattern-type collision
python -m tools.pattern_confidence_scorer compare \
  --patterns patterns.json --traces traces.jsonl --dream-bucket db.jsonl
python -m tools.pattern_confidence_scorer decay \
  --scores scored.json --decay-factor 0.99 --reference-date 2026-07-14
```

Exit codes: `0` success · `1` `ValueError` · `2` `FileNotFoundError`/`OSError`/`RuntimeError`.

## Requirements
- Pure stdlib. Same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.
