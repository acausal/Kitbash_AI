# SPEC: Pattern Explainer v1

**Module:** `tools/pattern_explainer/`  
**Status:** Ready for build  
**Dependencies:** stdlib (json, string.Template)  
**Priority:** High (completes Sleep Tier 2; feeds Sleep Stage 3 hypothesis generation; enables debugging/audit)

---

## Overview

Generate human-readable summaries and explanations of discovered patterns, anomalies, and collision clusters. Translate raw pattern metrics and anomaly scores into plain-language narratives that Sleep Tier 2 can use for hypothesis generation, and that users can review for debugging/auditing.

**Design principle:** Template-based explanation generation. No LLM; deterministic plain-text summaries from metrics. Structured output (explanation text + structured metadata) for downstream consumption.

**Use case:** "Anomaly Scorer found grain_42's FP rate spiked 5x. Pattern Explainer converts that into: 'Grain 42 (query router) showed a sudden increase in false positive rate from 6% to 31% in the last 4 hours. This grain is frequently confused with grains 137 and 89 (also query routers). Possible causes: search weight rebalancing or query pattern shift. Recommendation: investigate ternary delta drift.'"

---

## Scope

### In Scope ✓
- Explain collision clusters: why these facts/grains keep colliding
- Explain anomalies: what changed, why it matters, possible causes
- Explain patterns from Sequence Pattern Miner: what this tool chain does and when it succeeds
- Explain confidence scores: why a pattern is trustworthy or unreliable
- Multi-level summaries: one-liner, summary paragraph, detailed explanation
- Structured templates for different pattern/anomaly types
- Confidence calibration in explanations (don't claim certainty you don't have)
- Actionable recommendations (suggest investigation steps)
- Output: JSON with explanation text + structured metadata for downstream use

### Out of Scope ✗
- Causal inference (determining root cause) — explain observations, not causes
- LLM-based generation (deterministic templates only)
- Natural language processing (no NLP; pure template + variable substitution)
- Multi-language support (English-only v1)
- Visualization or rendering (plain text only)
- Narrative branching or conditional prose (simple templates)

---

## Module Structure

```
tools/pattern_explainer/
  __init__.py                    # exports main functions
  core.py                        # explanation generation logic
  templates.py                   # explanation templates for each pattern type
  formatters.py                  # formatting helpers (numbers, lists, timestamps)
  confidence_language.py         # map confidence scores to prose (high/medium/low)
  cli.py                         # argparse CLI
  explainer_schema.py            # dataclasses for JSON output
  README.md                       # usage docs + examples
  __main__.py                    # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

All functions accept/return JSON-serializable types (strings, dicts, lists).

#### 1. `explain_collision_cluster(cluster: dict, collision_index: dict = None) -> dict`

**Purpose:** Generate human-readable explanation of why facts/grains in a cluster keep colliding.

**Input:**
- `cluster` (dict): Collision cluster from Sleep Stage 2, formatted as:
  ```json
  {
    "cluster_id": "bio_energy_transfer",
    "members": [42, 137, 89],
    "query_theme": "photosynthesis/respiration/ATP",
    "coherence": 0.87,
    "size": 3,
    "collision_density": 0.94,
    "pairwise_collisions": [
      {"pair": [42, 137], "count": 47},
      {"pair": [42, 89], "count": 23},
      {"pair": [137, 89], "count": 18}
    ]
  }
  ```

- `collision_index` (dict, optional): Raw collision index for additional context

**Output (JSON):**
```json
{
  "cluster_id": "bio_energy_transfer",
  "explanation_type": "collision_cluster",
  "one_liner": "Facts 42, 137, 89 (photosynthesis/ATP concepts) form a semantic collision cluster.",
  "summary": "Three facts related to energy transfer (photosynthesis, respiration, ATP) are frequently confused in query routing. Grains 42 and 137 collide most often (47 times), suggesting they are structurally similar in query space. This cluster may represent a region of high semantic ambiguity.",
  "detailed_explanation": "This collision cluster groups three related concepts: Fact 42 (photosynthesis), Fact 137 (cellular respiration), and Fact 89 (ATP synthesis). The cluster shows high coherence (0.87), indicating these facts are genuinely similar. Collision density is 0.94, meaning the cluster members collide frequently with each other.\n\nThe pairwise collision breakdown reveals:\n- Facts 42↔137: 47 collisions (most frequent pair; likely strongest semantic overlap)\n- Facts 42↔89: 23 collisions (moderate overlap)\n- Facts 137↔89: 18 collisions (lower overlap)\n\nThese facts may be isomorphic in query space—the same query could legitimately map to any of them. Alternatively, the system may be conflating related-but-distinct concepts due to insufficient ternary discrimination.",
  "implications": [
    "Query ambiguity: users asking about 'energy' may legitimately want any of these facts.",
    "Grain confusion: the grain routing system treats these facts as interchangeable.",
    "Opportunity: this cluster could benefit from disambiguation rules or refined ternary deltas."
  ],
  "recommendations": [
    "Review ternary delta values for grains 42, 137, 89; are they sufficiently distinct?",
    "Analyze collision queries: do they have common keywords indicating ambiguity?",
    "Consider creating a disambiguation rule that branches on 'photosynthesis' vs. 'respiration' vs. 'ATP'."
  ],
  "confidence": "high",
  "confidence_justification": "Cluster coherence 0.87 and collision density 0.94 indicate this is a real structural pattern, not noise."
}
```

**Behavior:**
- Map cluster members to human-readable labels (fact IDs + theme)
- Compute and explain coherence score (what does 0.87 mean?)
- Highlight pairwise collision patterns (which pair collides most?)
- Generate implications (what does this pattern mean for the system?)
- Suggest investigation steps (actionable recommendations)
- Calibrate confidence language based on coherence + density scores

**Error handling:**
- `ValueError` if cluster format invalid
- `KeyError` if required fields missing (cluster_id, members)
- Graceful fallback if optional fields (collision_index) missing

---

#### 2. `explain_anomaly(anomaly: dict, historical_baseline: dict = None) -> dict`

**Purpose:** Generate human-readable explanation of a detected anomaly.

**Input:**
- `anomaly` (dict): Anomaly from Anomaly Scorer, formatted as:
  ```json
  {
    "anomaly_id": "anom_grain_42_spike",
    "grain_id": 42,
    "anomaly_type": "sudden_increase_false_positives",
    "baseline_rate": 0.06,
    "observed_rate": 0.31,
    "deviation_magnitude": 5.17,
    "severity": 0.78,
    "possible_causes": ["search_weight_shift", "query_pattern_change"],
    "evidence": ["fp_rate_jumped_from_0.06_to_0.31", "12.5_standard_deviations_above_baseline"],
    "window": "2026-07-14T10:00:00Z to 2026-07-14T14:00:00Z",
    "recommendation": "Investigate grain_42's recent ternary deltas; check query patterns for shift"
  }
  ```

- `historical_baseline` (dict, optional): Baseline stats for context

**Output (JSON):**
```json
{
  "anomaly_id": "anom_grain_42_spike",
  "explanation_type": "anomaly",
  "severity_label": "high",
  "one_liner": "Grain 42 (query router) experienced a sudden spike in false positive rate (5.17x baseline).",
  "summary": "Grain 42's false positive rate jumped from 6% (historical baseline) to 31% in the last 4 hours. This 5.17x increase is substantial and falls outside normal variation (z-score 12.5). The grain is now misrouting 1 in 3 queries.",
  "detailed_explanation": "Over the last 4 hours (2026-07-14T10:00-14:00), Grain 42 (query routing component) showed a sharp increase in false positives—cases where the grain confidently returned an incorrect result.\n\nMetrics:\n- Historical baseline: 6% false positive rate (over last 7 days)\n- Observed rate: 31% (in the 4-hour window)\n- Deviation: 5.17x the baseline\n- Statistical significance: 12.5 standard deviations above mean\n\nThis shift is sudden and severe. It suggests a systematic change in either:\n1. Query patterns (users asking different types of questions), or\n2. Grain behavior (ternary deltas or search weights shifted), or\n3. Knowledge base (new facts added that confuse the routing logic)\n\nThe grain is frequently confused with Grains 137 and 89 (other routing components). This collision pattern may indicate the grain's discrimination ability has degraded.",
  "anomaly_type_explanation": "Sudden increases in false positive rates indicate a routing component has lost its ability to distinguish between similar queries. This usually signals either a configuration change, a shift in query distribution, or drift in the knowledge base.",
  "timeline": {
    "baseline_period": "last_7_days",
    "anomaly_observation_window": "2026-07-14T10:00-14:00Z",
    "age_at_detection": "current"
  },
  "possible_causes_expanded": [
    {
      "cause": "search_weight_shift",
      "explanation": "If search weights for Grain 42 were recently rebalanced, it may be over-triggering.",
      "investigation": "Check git history or config management for Grain 42 weight changes in the last 24 hours."
    },
    {
      "cause": "query_pattern_change",
      "explanation": "If queries are now using different keywords or phrasing, the grain may not match them correctly.",
      "investigation": "Analyze query logs from the last 4 hours; compare query distribution to historical norm."
    }
  ],
  "implications": [
    "User impact: 31% of queries routed to Grain 42 are returning incorrect results.",
    "Cascading effects: downstream facts will receive incorrect context.",
    "Signal in Dream Bucket: false positives are recorded; the system is aware of the problem."
  ],
  "recommendations": [
    "Immediate: monitor Grain 42 FP rate; if it continues above 20%, consider deprioritizing the grain temporarily.",
    "Investigation: compare query logs (last 4 hours) to baseline; look for keyword/pattern shifts.",
    "Investigation: review recent changes to Grain 42 config (weights, ternary deltas, search parameters).",
    "Investigation: check if any new facts were added that might confuse the routing logic.",
    "Hypothesis: Grain 42 and Grains 137/89 may need stronger ternary discrimination."
  ],
  "severity": 0.78,
  "severity_label": "high",
  "confidence": "high",
  "confidence_justification": "Magnitude (5.17x), statistical significance (z=12.5), and recency (within 4 hours) all confirm this is a real anomaly."
}
```

**Behavior:**
- Map anomaly_type to human-readable description (what does `sudden_increase_false_positives` mean?)
- Quantify severity in plain language ("high", "medium", "low"; map from 0–1 score)
- Expand possible_causes with explanations and investigation steps
- Identify implications (who cares? what breaks downstream?)
- Generate actionable recommendations (what should Sleep Tier 3 do?)
- Calibrate confidence language based on severity, statistical significance, and evidence count

**Error handling:**
- `ValueError` if anomaly format invalid
- `KeyError` if required fields missing
- Graceful fallback if optional fields missing

---

#### 3. `explain_pattern_reliability(pattern: dict, confidence_scores: dict) -> dict`

**Purpose:** Explain why a discovered pattern is trustworthy or unreliable.

**Input:**
- `pattern` (dict): Pattern from Sequence Pattern Miner or similar, formatted as:
  ```json
  {
    "pattern_id": "seq_001",
    "sequence": ["tokenizer", "negation_detector", "svo_extractor"],
    "frequency": 47,
    "min_frequency_threshold": 3
  }
  ```

- `confidence_scores` (dict): Output from Pattern Confidence Scorer, formatted as:
  ```json
  {
    "pattern_id": "seq_001",
    "pattern": ["tokenizer", "negation_detector", "svo_extractor"],
    "metrics": {
      "precision": 0.89,
      "recall": 0.76,
      "f1_score": 0.82,
      "support": 47
    },
    "interpretation": {
      "reliability": "high",
      "confidence_flag": "none"
    }
  }
  ```

**Output (JSON):**
```json
{
  "pattern_id": "seq_001",
  "explanation_type": "pattern_reliability",
  "one_liner": "Pattern [tokenizer → negation_detector → svo_extractor] is highly reliable (F1: 0.82).",
  "summary": "This tool sequence appears in 47 successful reasoning chains. When it fires, it succeeds 89% of the time (precision). It catches 76% of correct outcomes (recall). Overall reliability: high.",
  "detailed_explanation": "Pattern seq_001 represents a three-step tool sequence: tokenizer → negation_detector → svo_extractor. This sequence is a core component of the text processing pipeline.\n\nReliability metrics:\n- Precision: 0.89 (89% of times this pattern fires, the outcome is correct)\n- Recall: 0.76 (76% of correct outcomes involve this pattern firing)\n- F1 Score: 0.82 (harmonic mean; overall reliability is high)\n- Support: 47 observations (sufficient data for confidence)\n\nWhat this means:\n- When this sequence fires, you can trust the result (high precision).\n- This sequence covers most of the successful reasoning path (good recall).\n- The pattern is common and well-understood (47 occurrences).\n- No data quality issues detected (no confidence flags).",
  "reliability_breakdown": {
    "precision_explanation": "89% success rate when pattern fires. This is strong; the pattern rarely produces incorrect results.",
    "recall_explanation": "76% of successes involve this pattern. The pattern is important but not the only success mode.",
    "f1_explanation": "F1 score of 0.82 is above the 0.75 'high reliability' threshold. The pattern is trustworthy for both prediction and coverage."
  },
  "confidence_flags": [],
  "confidence_flag_explanations": [],
  "sample_size_assessment": "47 observations is sufficient for reliable scoring (well above n≥20 threshold).",
  "use_cases": [
    "High confidence: use this pattern for real-time reasoning (precision is high).",
    "Acceptable coverage: pattern covers 76% of success cases (good but not exhaustive).",
    "Learning target: this pattern is a good candidate for procedural edge extraction (stable and reliable)."
  ],
  "reliability_level": "high",
  "recommendation": "Sleep Tier 3 should prioritize this pattern for hypothesis generation and potential LoRA training.",
  "comparison_to_baseline": "This pattern's F1 score (0.82) is above the median (0.71); it's in the top quartile of patterns.",
  "confidence": "high",
  "confidence_justification": "High precision, good recall, sufficient sample size, and no quality flags all indicate this pattern is genuinely reliable."
}
```

**Behavior:**
- Interpret metrics in human terms (what does F1=0.82 mean for a user?)
- Map confidence levels to language (high/medium/low)
- Explain what flags mean (if any)
- Relate metrics to action (should Sleep pipeline use this? how?)
- Provide use case guidance (real-time vs. batch? training data?)
- Compare to baselines (is this pattern above/below average?)

**Error handling:**
- `ValueError` if pattern or confidence_scores format invalid
- `KeyError` if required fields missing
- Graceful fallback if optional comparison data missing

---

#### 4. `explain_multiple_patterns(patterns_list: list, confidence_scores_list: list, summary_style: str = "brief") -> dict`

**Purpose:** Generate summary explanation of multiple patterns (for Sleep report).

**Input:**
- `patterns_list` (list): Multiple patterns
- `confidence_scores_list` (list): Confidence scores for each
- `summary_style` (str): "brief" (one-liners), "summary" (paragraphs), "detailed" (full explanations)

**Output (JSON):**
```json
{
  "summary_type": "pattern_collection_brief",
  "total_patterns": 12,
  "high_reliability_patterns": 8,
  "medium_reliability_patterns": 3,
  "low_reliability_patterns": 1,
  "aggregate_summary": "Of 12 discovered patterns, 8 are highly reliable (F1>0.75), 3 are medium confidence, and 1 needs investigation. The pattern set is dominated by high-confidence sequences, suggesting the system has learned stable reasoning chains.",
  "pattern_summaries": [
    {
      "pattern_id": "seq_001",
      "one_liner": "Pattern [tokenizer → negation_detector → svo_extractor] is highly reliable (F1: 0.82).",
      "reliability": "high"
    },
    {
      "pattern_id": "seq_002",
      "one_liner": "Pattern [json_filter → text_search] is medium reliability (F1: 0.60); recommend collecting more data.",
      "reliability": "medium"
    }
  ],
  "top_patterns_by_reliability": [
    {"pattern_id": "seq_001", "f1": 0.89},
    {"pattern_id": "seq_005", "f1": 0.87},
    {"pattern_id": "seq_003", "f1": 0.84}
  ],
  "patterns_needing_attention": [
    {"pattern_id": "seq_012", "f1": 0.45, "issue": "low_f1_score"}
  ],
  "recommendations": [
    "Patterns seq_001, seq_005, seq_003 are solid; candidate for LoRA extraction.",
    "Pattern seq_002 needs more data; keep monitoring.",
    "Pattern seq_012 underperforms; investigate failure mode or remove from active reasoning."
  ]
}
```

**Behavior:**
- Aggregate multiple patterns into readable report
- Categorize by reliability level
- Identify best and worst performers
- Provide per-pattern and overall recommendations

**Error handling:**
- `ValueError` if patterns_list/scores_list length mismatch
- `ValueError` if summary_style unrecognized

---

### CLI Interface (in `cli.py`)

```bash
# Explain a collision cluster
python -m tools.pattern_explainer explain-cluster \
  --cluster cluster.json \
  --collision-index collisions.json

# Explain an anomaly
python -m tools.pattern_explainer explain-anomaly \
  --anomaly anomaly.json \
  --baseline baseline.json

# Explain pattern reliability
python -m tools.pattern_explainer explain-pattern \
  --pattern pattern.json \
  --confidence-scores scores.json

# Explain multiple patterns (summary report)
python -m tools.pattern_explainer explain-patterns \
  --patterns patterns.json \
  --confidence-scores scores.json \
  --summary-style brief

# Generate full Sleep Tier 2 report
python -m tools.pattern_explainer generate-sleep-report \
  --collision-clusters clusters.json \
  --anomalies anomalies.json \
  --patterns patterns.json \
  --confidence-scores scores.json
```

**Output:** JSON to stdout (one object per command)

**Exit codes:**
- `0`: Success
- `1`: ValueError (invalid input/format)
- `2`: RuntimeError (I/O or processing error)

---

## Templates & Formatting

### Template Categories (in `templates.py`)

```python
TEMPLATES = {
  # Collision cluster explanations
  "collision_cluster_one_liner": "Facts {members} ({theme}) form a semantic collision cluster.",
  "collision_cluster_summary": "...",
  "collision_cluster_detailed": "...",
  
  # Anomaly explanations
  "anomaly_sudden_increase_one_liner": "{entity} experienced a sudden {metric} spike ({magnitude}x baseline).",
  "anomaly_sudden_increase_summary": "...",
  "anomaly_sudden_increase_detailed": "...",
  
  # Pattern reliability
  "pattern_reliable_one_liner": "Pattern {pattern_id} is {reliability_label} ({f1_score}).",
  "pattern_reliable_summary": "...",
  
  # etc.
}
```

### Formatting Helpers (in `formatters.py`)

- `format_percentage(value)` → "89%" from 0.89
- `format_magnitude(ratio)` → "5.17x" from 5.17
- `format_confidence(score)` → "high" from 0.78
- `format_list(items)` → "Fact 42, 137, and 89" from [42, 137, 89]
- `format_timestamp(iso_str)` → "2026-07-14T10:00Z" → "2 hours ago"
- `format_entity_label(entity_id, entity_type)` → "Grain 42 (query router)" from (42, "grain")

### Confidence Language Mapping (in `confidence_language.py`)

```python
def severity_to_label(score: float) -> str:
  if score >= 0.75: return "high"
  if score >= 0.50: return "medium"
  return "low"

def f1_to_reliability(score: float) -> str:
  if score >= 0.75: return "high"
  if score >= 0.50: return "medium"
  return "low"
```

---

## Integration Points

**Upstream (provides data):**
- Anomaly Scorer (anomaly_timeline.json)
- Pattern Confidence Scorer (confidence scores)
- Sequence Pattern Miner (patterns)
- Sleep Stage 2 outputs (collision_clusters.json)

**Downstream (consumes output):**
- Sleep Stage 3: Hypothesis Generation (feeds explanations into hypothesis text)
- Sleep Stage 4: Question Generation (uses explanations for context)
- User audit/debugging (human-readable reports)

---

## Data Flow Example

```
Sleep Stage 2 outputs:
  anomaly_timeline.json: grain_42 FP spike, severity 0.78
  collision_clusters.json: bio_energy cluster with facts 42, 137, 89
  
  ↓ Pattern Explainer

explain_anomaly(grain_42_spike):
  "Grain 42 (query router) experienced a sudden spike in false positive 
   rate (5.17x baseline, severity high). Over 4 hours, FP rate jumped from 
   6% to 31%. Possible causes: search weight shift, query pattern change. 
   Recommendation: investigate ternary deltas."

explain_collision_cluster(bio_energy):
  "Three facts related to energy transfer (photosynthesis, respiration, ATP) 
   form a semantic collision cluster. Facts 42 and 137 collide frequently 
   (47 times), indicating they are structurally similar in query space."

  ↓ Sleep Stage 3: Hypothesis Generation

  Generates hypothesis:
  "Grain 42's false positive rate spiked. This grain is frequently confused 
   with grains 137 and 89 (part of bio_energy collision cluster). Hypothesis: 
   search weight rebalancing or query pattern shift caused the grain to 
   over-trigger."
```

---

## Testing Strategy

### Test Cases

1. **Collision cluster explanation (high coherence):**
   - Input: cluster with members=[42,137,89], coherence=0.87, collisions=47
   - Expected: one_liner and summary explain semantic similarity, recommendations for disambiguation

2. **Anomaly explanation (high severity spike):**
   - Input: anomaly grain_42, baseline=0.06, observed=0.31, severity=0.78
   - Expected: detailed explanation of 5.17x spike, possible causes, investigation steps

3. **Pattern reliability explanation (high F1):**
   - Input: pattern F1=0.82, precision=0.89, recall=0.76, support=47
   - Expected: explanation calibrated to high reliability; use case suggestions

4. **Low-confidence pattern:**
   - Input: pattern F1=0.45, support=8, confidence_flag="low_sample_size"
   - Expected: cautious language; explanation of unreliability; recommendation to collect more data

5. **Multiple patterns summary:**
   - Input: 12 patterns with mixed F1 scores
   - Expected: brief aggregation, top/bottom performers, overall assessment

### Example Test File (TEST-pattern_explainer_examples.json)

```json
{
  "test_cases": [
    {
      "name": "collision_cluster_high_coherence",
      "input": {
        "cluster_id": "bio_energy_transfer",
        "members": [42, 137, 89],
        "query_theme": "photosynthesis/respiration/ATP",
        "coherence": 0.87,
        "size": 3,
        "collision_density": 0.94
      },
      "expected_output": {
        "explanation_type": "collision_cluster",
        "one_liner_includes": "semantic collision cluster",
        "confidence": "high"
      }
    },
    {
      "name": "anomaly_high_severity_spike",
      "input": {
        "anomaly_type": "sudden_increase_false_positives",
        "grain_id": 42,
        "baseline_rate": 0.06,
        "observed_rate": 0.31,
        "severity": 0.78
      },
      "expected_output": {
        "severity_label": "high",
        "one_liner_includes": "sudden spike",
        "recommendations_count_min": 3
      }
    }
  ]
}
```

---

## Non-Goals

- ❌ LLM-based generation (deterministic templates only)
- ❌ Natural language generation beyond templates
- ❌ Multi-language support (English-only v1)
- ❌ Causal inference (explain observations, not causes)
- ❌ Visualization or rendering

---

## Dependencies

| Package | Version | Purpose | Notes |
|---------|---------|---------|-------|
| stdlib | — | json, string.Template | No external deps |

**No external libraries needed. Pure Python stdlib.**

---

## Future Enhancements (Post-1.0)

1. **v1.1: Custom entity labels** — User can define entity names (grain_42 → "Query Router A")
2. **v1.2: Explanation depth levels** — Control verbosity per output (one-liner vs. detailed)
3. **v2.0: Multi-language** — Template expansion to other languages
4. **v2.0: Narrative chains** — Link explanations (e.g., "This collision cluster causes the anomaly in Pattern X")

---

**Last updated:** 2026-07-14  
**Author:** Isaac (Kitbash AI)  
**For:** tools/ ecosystem, Sleep Tier 2 introspection  
**Related:** SLEEP_METABOLISM_SPEC.md, ANOMALY_SCORER_SPEC.md, PATTERN_CONFIDENCE_SCORER_SPEC.md
