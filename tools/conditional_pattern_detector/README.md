# conditional_pattern_detector

Detect association rules and shallow decision patterns in execution traces
(sleep Tier 2 meta-learning; consumes `log_parser` normalized traces). Stdlib
only (`json`, `collections`, `math`) — no new deps. Isolation-first.

## Library

```python
from tools.conditional_pattern_detector import (
    detect_conditional_patterns, detect_seeded_patterns,
    extract_decision_trees, filter_patterns, rank_patterns_by_metric,
)

# 1. Auto-discover conditions from trace structure, rank by confidence
report = detect_conditional_patterns(traces, min_support=2, min_confidence=0.5)
# 2. Targeted exploration with user-supplied seed conditions
report = detect_seeded_patterns(traces,
    [{"type":"chain_length","operator":">=","value":3}])
# 3. Shallow decision tree (binary target: does the chain contain a grain step?)
tree   = extract_decision_trees(traces, depth=2)
# 4. Post-filter rules
filt   = filter_patterns(rules, min_confidence=0.7, min_lift=1.2)
# 5. Re-rank by a different metric
ranked = rank_patterns_by_metric(rules, metric="lift")
```

Every function returns a **plain JSON-serializable dict**.

### Metrics
- **support** = count of traces matching the condition
- **confidence** = P(grain present | condition) `(matching ∩ grain) / matching`
- **lift** = confidence / baseline rate (baseline guard: if all traces contain
  grain, baseline = 1.0 → lift = 1.0, no division by zero)
- **inverse_confidence** = P(grain present | NOT condition)

### Decision-tree target (fixed for v1)
Per user decision 2026-07-14, the tree target is **`grain_present_in_chain`** —
a binary split on whether the chain contains a `grain` step. It is derivable
directly from `log_parser` output and not user-overridable in v1 (documented).

### Skipped types (post-1.0) — documented, not implemented
`log_parser` traces do not yet carry per-step `confidence`/`success` or
cartridge lists, so these are omitted and listed in the `skipped_types` key of
every report:
- **Conditions:** `cartridge_crossing`, `session_consistency`
- **Outcomes:** `success_rate`, `cartridge_distribution`

When `query_orchestrator` emits those fields and `log_parser` is extended,
these become computable (see README "Extensibility").

## CLI

Reads JSON from **stdin**, writes JSON to **stdout**:

```bash
echo '{"traces":[...]}' | python -m tools.conditional_pattern_detector detect_conditional_patterns --min_support 2 --min_confidence 0.5
echo '{"traces":[...],"seed_conditions":[{"type":"chain_length","operator":">=","value":3}]}' | python -m tools.conditional_pattern_detector detect_seeded_patterns
echo '{"traces":[...]}' | python -m tools.conditional_pattern_detector extract_decision_trees --depth 2
echo '{"patterns":[...]}' | python -m tools.conditional_pattern_detector filter_patterns --min_confidence 0.7 --min_lift 1.2
echo '{"patterns":[...]}' | python -m tools.conditional_pattern_detector rank_patterns_by_metric --metric lift
```

**Exit codes:** `0` success · `1` invalid input (`ValueError`) ·
`2` internal error (`RuntimeError`).

## Requirements

- Pure stdlib (`json`, `collections`, `math`). No new deps.
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.conditional_pattern_detector ...`
