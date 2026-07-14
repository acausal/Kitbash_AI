# SPEC: Historical AI Tools — Shared Contract v1

**Scope:** TF-IDF Ranker, Boolean Search, Inverted Index Builder, Markov Chain, Naive Bayes Classifier, Frequency Analysis  
**Status:** Contract definition (reference for all 6 tools)  
**Date:** 2026-07-14  
**Philosophy:** Stateless, deterministic, pure transformations. No hidden state, no persistent models. All computation happens in-process; input includes everything needed.

---

## Overview

Historical AI tools are deterministic ranking, classification, and analysis utilities for text and token streams. They implement classical NLP/IR techniques (TF-IDF, Boolean logic, Markov chains, naive Bayes) as composable Unix-style filters.

**Core principle:** Each tool is a pure function: `stdin (tokens/text + config) → stdout (results)`. No side effects, no persistent state, no training phases. If a tool needs pre-computed data (e.g., IDF scores, n-gram frequencies), that data is passed as JSON input, not loaded from disk.

**Why stateless?** Fits TOOL_PHILOSOPHY (reproducible, extractable, local-first). Same token stream + same config → same output, always. No hidden files, no serialized models, no cache invalidation headaches.

---

## Shared Interface Contract

### Input Format (stdin or file)

All Historical AI tools accept one of these input shapes:

#### Shape A: Token Stream + Configuration
```json
{
  "tokens": ["hello", "world", "example"],
  "config": {
    "tool_specific_param_1": "value",
    "tool_specific_param_2": 123
  }
}
```

#### Shape B: Text + Configuration
```json
{
  "text": "Hello world. This is an example.",
  "config": {
    "tokenization": "whitespace",
    "tool_specific_param": "value"
  }
}
```

#### Shape C: Corpus + Query + Configuration (for ranking tools)
```json
{
  "corpus": [
    {"id": "doc_1", "tokens": ["hello", "world"]},
    {"id": "doc_2", "tokens": ["example", "text"]}
  ],
  "query": ["hello", "example"],
  "config": {
    "ranking_algorithm": "tfidf",
    "top_k": 5
  }
}
```

#### Shape D: Pre-Computed State + Query (for tools needing external data)
```json
{
  "state": {
    "type": "inverted_index",
    "index": {
      "hello": ["doc_1", "doc_3"],
      "world": ["doc_1", "doc_2"]
    },
    "doc_count": 100
  },
  "query": ["hello", "world"],
  "config": {
    "matching_mode": "all_tokens"
  }
}
```

**Key rule:** No tool reads from disk (except via Filesystem Access v1 for explicit file I/O). All data needed for computation is in stdin JSON.

### Output Format (stdout)

All Historical AI tools emit:

```json
{
  "tool": "tool_name",
  "version": "v1",
  "run_id": "run_001",
  "timestamp": "2026-07-14T15:00:00Z",
  "input_summary": {
    "input_type": "token_stream",
    "token_count": 3
  },
  "results": [
    {
      "result_id": "result_001",
      "rank": 1,
      "value": 0.95,
      "details": {}
    }
  ],
  "metadata": {
    "computation_time_ms": 12,
    "config_used": {}
  }
}
```

**Results structure:**
- `result_id`: Unique identifier for this result (doc_id, token, n-gram, class, etc.)
- `rank`: Integer rank (1 = top result; ascending order expected)
- `value`: Score or probability [0, 1] (semantic meaning tool-specific)
- `details`: Tool-specific metadata (e.g., term frequency, feature contributions)

---

## Tokenization Contract

### Tokenizer Interop
Tools that need tokenization can:

**Option 1: Accept pre-tokenized input** (recommended)
- Expect `tokens` field in input JSON
- Skip tokenization entirely (pure computation)

**Option 2: Internal tokenization with configurable strategy**
- Accept `text` + `tokenization_config` in input
- Implement simple tokenizers (whitespace, regex, or call Tokenizer tool via subprocess)

**Recommendation for v1:** Use Option 1 (expect pre-tokenized). Tokenizer tool handles raw text → tokens upstream.

---

## Configuration Schema (Shared Across All Tools)

Every Historical AI tool accepts a `config` object with these optional fields:

```json
{
  "config": {
    "lowercase": true,
    "remove_stopwords": false,
    "stopword_list": ["the", "a", "an"],
    "min_token_length": 1,
    "top_k": 10,
    "threshold": 0.0,
    "verbose": false
  }
}
```

### Standard Config Fields

| Field | Type | Default | Used By | Purpose |
|-------|------|---------|---------|---------|
| `lowercase` | bool | true | All | Normalize tokens to lowercase |
| `remove_stopwords` | bool | false | All | Filter common words |
| `stopword_list` | array | standard English | All | Custom stopwords |
| `min_token_length` | int | 1 | All | Minimum token length to consider |
| `top_k` | int | 10 | Rankers | Return top K results |
| `threshold` | float | 0.0 | Classifiers/Rankers | Minimum score to include in results |
| `verbose` | bool | false | All | Include detailed computation info in `details` |

Tool-specific config fields are documented in each tool's spec (e.g., `tfidf_variant`, `boolean_mode`, `markov_order`).

---

## Error Semantics (All Tools)

### Exit Codes

- **Exit 0:** Success (results computed, even if empty)
- **Exit 1:** ValueError (invalid input format, missing required fields, malformed JSON)
- **Exit 2:** RuntimeError (I/O error, file not found, resource exhaustion)

### Error Output (to stderr)

```json
{
  "error_type": "ValueError",
  "error_message": "Missing required field: 'tokens' or 'text'",
  "error_code": 1,
  "timestamp": "2026-07-14T15:00:00Z"
}
```

### Fail-Loud Principle

- Never silently degrade (e.g., skip bad tokens, ignore missing config)
- Always emit error message to stderr
- Exit with appropriate code
- Let orchestrator decide how to handle

---

## CLI Interface (Consistent Across All Tools)

All Historical AI tools follow this CLI pattern:

```bash
# Read from stdin, write to stdout
python -m tools.TOOL_NAME < input.json > output.json

# Read from file, write to file
python -m tools.TOOL_NAME --input input.json --output output.json

# Verbose mode (include detailed computation info)
python -m tools.TOOL_NAME --input input.json --output output.json --verbose

# Custom config (override via CLI)
python -m tools.TOOL_NAME --input input.json --top-k 5 --lowercase --remove-stopwords

# Show help
python -m tools.TOOL_NAME --help
```

### Argparse Contract

Each tool implements:
- `--input` (optional, default stdin)
- `--output` (optional, default stdout)
- `--verbose` (optional, default false)
- Tool-specific flags (e.g., `--top-k`, `--tfidf-variant`, etc.)

---

## Performance & Resource Constraints

### Expected Limits (CPU-only, GTX 1060)

| Tool | Input Size | Latency Target |
|------|------------|-----------------|
| TF-IDF Ranker | 1000 docs, 100 tokens each | <100ms |
| Boolean Search | 1000 docs | <50ms |
| Inverted Index Builder | 1000 docs | <200ms |
| Markov Chain | 10K tokens | <100ms |
| Naive Bayes | 100 classes, 1000 features | <500ms |
| Frequency Analysis | 100K tokens | <1s |

### Resource Limits
- Max input JSON size: 100 MB
- Max token count: 1M
- Max doc count: 100K
- Memory ceiling: 2 GB (fail if exceeded)

---

## Testing Strategy (Shared)

Every Historical AI tool includes:

### TEST-{tool_name}_examples.json

Explicit test cases with expected outputs:
- 1–2 happy path cases (typical input, expected output)
- 1 edge case (empty input, single token, etc.)
- 1 error case (malformed JSON, missing required field)

Example structure:
```json
{
  "test_cases": [
    {
      "name": "simple_ranking",
      "input": {
        "corpus": [...],
        "query": [...],
        "config": {}
      },
      "expected_output": {
        "results": [...]
      }
    }
  ]
}
```

---

## Module Structure (All Tools)

Every Historical AI tool follows this layout:

```
tools/{tool_name}/
  __init__.py                  # exports main functions
  core.py                      # main algorithm logic
  cli.py                       # argparse CLI
  schema.py                    # dataclasses for input/output
  README.md                    # usage + algorithm explanation
  __main__.py                  # CLI entry point
```

---

## Composition Examples

### Example 1: Tokenizer → TF-IDF Ranker

```bash
cat raw_documents.txt | \
  python -m tools.tokenizer --lowercase --remove-stopwords | \
  python -m tools.tfidf_ranker --query "hello world" --top-k 5
```

### Example 2: Boolean Search on Pre-Tokenized Corpus

```bash
python -m tools.boolean_search \
  --input corpus_tokenized.json \
  --query-file query.json \
  --output results.json
```

### Example 3: Frequency Analysis with Stopwords

```bash
python -m tools.frequency_analysis \
  --input tokens.json \
  --remove-stopwords \
  --output freq_distribution.json
```

---

## Determinism & Reproducibility

### Guarantees

1. **Same input + same config → same output** (always)
2. **No randomness** (or explicitly seeded; documented in tool spec)
3. **No external dependencies** (network, files, system state)
4. **Computation time may vary slightly** (CPU load, caching), but output is identical

### Verification

To verify determinism:
```bash
# Run twice, compare outputs
python -m tools.tfidf_ranker --input test.json > out1.json
python -m tools.tfidf_ranker --input test.json > out2.json
diff out1.json out2.json  # Should be identical (except timestamp)
```

(Timestamps are acceptable differences; logic output must match exactly.)

---

## Dependencies & Constraints (All Tools)

- **Python:** 3.8+
- **Imports:** stdlib only (json, collections, math, statistics, re, datetime, etc.)
- **External libs:** None
- **Hardware:** CPU-only; no GPU required

---

## Related Tools & Integration

These Historical AI tools integrate into the larger toolkit:

- **Tokenizer v1:** Pre-processes raw text → tokens
- **Text Search v1:** Simple pattern matching (complementary)
- **JSON Query Filter v1:** Post-processes results
- **Log Parser v1:** Analyzes structured logs (can use Historical AI for pattern ranking)
- **Neighborhood Projection v1:** Uses these tools for graph topology inference

---

## Non-Goals

- **Streaming:** All tools are batch-oriented (v1)
- **Distributed computation:** Single-machine only
- **Training with persistence:** No model files; state always in-process
- **Incremental updates:** Always recompute from scratch (full corpus)
- **Real-time performance:** No hard latency guarantees, just targets

---

## Version & Evolution

**Version:** v1 (shared contract)  
**Status:** Stable (all 6 tools reference this; updates require consensus)  
**Post-1.0 extensions:**
- Streaming mode (incremental corpus updates)
- Parallel computation (multi-core usage)
- Persistent state (cached models, IDF tables)
- Advanced stemmers/lemmatizers

---

**Last updated:** 2026-07-14  
**For:** Historical AI batch (TF-IDF, Boolean Search, Inverted Index, Markov, Naive Bayes, Frequency Analysis)  
**Related:** TOOL_PHILOSOPHY.md, Shared tool design patterns
