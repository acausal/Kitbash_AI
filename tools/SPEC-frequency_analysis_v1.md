# SPEC: Frequency Analysis v1

**Module:** `tools/frequency_analysis/`  
**Status:** Ready for spec  
**Dependencies:** stdlib (json, collections, statistics, math)  
**Priority:** Medium (exploratory data analysis, corpus statistics, baseline feature extraction)

---

## Overview

Analyze token frequency distributions in a corpus. Pure, stateless analysis: compute term frequencies, document frequencies, statistical summaries (mean, median, std dev, quantiles). No learning, no persistent state. Deterministic output for reproducible corpus exploration.

**Design principle:** Simple statistical summary. Accept token stream or tokenized corpus; emit frequency distribution with per-token stats and corpus-level aggregates. No ranking, no filtering—just counts and statistics.

**Use case:** "I have 10K execution traces. Show me: which tools appear most/least frequently? What's the distribution of tool usage? Are there outlier frequencies? Give me percentiles and statistical summaries."

---

## Scope

### In Scope ✓
- Count token frequencies (unigrams)
- Compute document frequencies: how many documents contain each token
- Statistical summaries: mean, median, std dev, min, max, quantiles (25%, 50%, 75%, 90%, 99%)
- Token ranks and percentiles: which tokens are in top 10%, top 1%, etc.
- Vocabulary coverage: what % of tokens cover X% of corpus
- Frequency distribution visualization (JSON format): histogram bins
- Batch analysis: multiple corpora simultaneously
- Detailed output: per-token frequencies + corpus-level statistics

### Out of Scope ✗
- Zipf's law analysis or power-law fitting
- Entropy or information-theoretic measures (separate tool)
- Term weighting (TF-IDF, BM25): pure counts only
- Smoothing or adjustment for data issues
- Interactive visualization or plotting

---

## Module Structure

```
tools/frequency_analysis/
  __init__.py                     # exports main functions
  core.py                         # frequency computation and statistics
  distributions.py                # frequency distribution analysis
  cli.py                          # argparse CLI
  analysis_schema.py              # dataclasses for input/output
  README.md                        # usage + examples
  __main__.py                     # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

#### 1. `analyze_frequencies(tokens: list, config: dict = None) -> dict`

**Purpose:** Compute frequency statistics from token stream.

**Input:**

- `tokens` (list): Flat list of tokens:
  ```json
  ["machine", "learning", "machine", "algorithm", "learning", "learning"]
  ```

- `config` (dict, optional):
  ```json
  {
    "lowercase": true,
    "remove_stopwords": false,
    "stopword_list": ["the", "a"],
    "min_token_length": 1,
    "top_k": 20,
    "verbose": false
  }
  ```

**Output:**

```json
{
  "tool": "frequency_analysis",
  "version": "v1",
  "run_id": "freq_001",
  "timestamp": "2026-07-14T15:35:00Z",
  "input_summary": {
    "total_tokens": 6,
    "unique_tokens": 3,
    "avg_frequency": 2.0
  },
  "frequency_distribution": {
    "learning": {
      "frequency": 3,
      "rank": 1,
      "percentile": 100,
      "coverage_percent": 50.0
    },
    "machine": {
      "frequency": 2,
      "rank": 2,
      "percentile": 67,
      "coverage_percent": 33.3
    },
    "algorithm": {
      "frequency": 1,
      "rank": 3,
      "percentile": 33,
      "coverage_percent": 16.7
    }
  },
  "statistics": {
    "frequency_stats": {
      "mean": 2.0,
      "median": 2.0,
      "std_dev": 0.816,
      "min": 1,
      "max": 3,
      "sum": 6,
      "quantiles": {
        "q25": 1.5,
        "q50": 2.0,
        "q75": 2.5,
        "q90": 2.8,
        "q99": 2.98
      }
    },
    "token_stats": {
      "total_tokens": 6,
      "unique_tokens": 3,
      "type_token_ratio": 0.5,
      "gini_coefficient": 0.333
    }
  },
  "top_tokens": [
    {
      "token": "learning",
      "frequency": 3,
      "rank": 1,
      "percentile": 100
    },
    {
      "token": "machine",
      "frequency": 2,
      "rank": 2,
      "percentile": 67
    }
  ],
  "bottom_tokens": [
    {
      "token": "algorithm",
      "frequency": 1,
      "rank": 3,
      "percentile": 33
    }
  ],
  "metadata": {
    "computation_time_ms": 2,
    "config_used": {
      "lowercase": true,
      "remove_stopwords": false,
      "min_token_length": 1,
      "top_k": 20
    }
  }
}
```

#### 2. `analyze_corpus_frequencies(corpus: list, config: dict = None) -> dict`

**Purpose:** Analyze frequencies in tokenized corpus (document-level analysis).

**Input:**

- `corpus` (list): Documents with tokens:
  ```json
  [
    {"id": "doc_1", "tokens": ["machine", "learning"]},
    {"id": "doc_2", "tokens": ["learning", "algorithm"]},
    {"id": "doc_3", "tokens": ["machine", "learning"]}
  ]
  ```

- `config` (dict, optional): Same as above

**Output:**

```json
{
  "tool": "frequency_analysis",
  "version": "v1",
  "run_id": "freq_corpus_001",
  "timestamp": "2026-07-14T15:35:05Z",
  "input_summary": {
    "documents": 3,
    "total_tokens": 6,
    "unique_tokens": 3,
    "avg_doc_length": 2.0
  },
  "frequency_distribution": {
    "learning": {
      "total_frequency": 3,
      "document_frequency": 3,
      "avg_frequency_per_doc": 1.0,
      "rank": 1,
      "percentile": 100
    },
    "machine": {
      "total_frequency": 2,
      "document_frequency": 2,
      "avg_frequency_per_doc": 1.0,
      "rank": 2,
      "percentile": 67
    },
    "algorithm": {
      "total_frequency": 1,
      "document_frequency": 1,
      "avg_frequency_per_doc": 1.0,
      "rank": 3,
      "percentile": 33
    }
  },
  "statistics": {
    "token_frequency_stats": {
      "mean": 2.0,
      "median": 2.0,
      "std_dev": 0.816
    },
    "document_frequency_stats": {
      "mean": 2.0,
      "median": 2.0,
      "std_dev": 0.816
    },
    "document_length_stats": {
      "mean": 2.0,
      "median": 2.0,
      "std_dev": 0.0,
      "min": 2,
      "max": 2
    }
  }
}
```

#### 3. `compute_coverage(frequencies: dict, coverage_threshold: float = 0.8) -> dict`

**Purpose:** Analyze vocabulary coverage: what % of vocabulary needed to cover X% of corpus.

**Input:**

```json
{
  "frequencies": {"token1": 100, "token2": 50, "token3": 30, ...},
  "coverage_threshold": 0.8
}
```

**Output:**

```json
{
  "coverage_analysis": {
    "target_coverage": 0.8,
    "tokens_needed": 5,
    "total_unique_tokens": 1000,
    "coverage_achieved": 0.802,
    "coverage_percentages": {
      "80": 5,
      "90": 12,
      "95": 28,
      "99": 95
    }
  }
}
```

#### 4. `frequency_histogram(frequencies: dict, bin_edges: list = None) -> dict`

**Purpose:** Generate histogram of frequency distribution.

**Input:**

```json
{
  "frequencies": {"token1": 100, "token2": 50, ...},
  "bin_edges": [1, 10, 50, 100, 500, 1000]
}
```

**Output:**

```json
{
  "histogram": {
    "bins": [
      {"min": 1, "max": 10, "count": 250, "tokens_in_bin": ["token123", "token456", ...]},
      {"min": 10, "max": 50, "count": 120, "tokens_in_bin": [...]},
      {"min": 50, "max": 100, "count": 45, "tokens_in_bin": [...]}
    ],
    "total_tokens": 415
  }
}
```

---

## Key Statistical Measures

### Frequency Statistics

- **Mean:** Average frequency across all unique tokens
- **Median:** Middle value of frequency distribution
- **Std Dev:** Standard deviation of frequencies
- **Min/Max:** Lowest and highest frequencies
- **Quantiles:** 25th, 50th, 75th, 90th, 99th percentiles

### Token Statistics

- **Total Tokens:** Sum of all token occurrences (corpus size)
- **Unique Tokens:** Count of distinct tokens (vocabulary size)
- **Type-Token Ratio (TTR):** unique_tokens / total_tokens
  - Range: (0, 1]; higher = more diverse vocabulary
  - Lower = more repetitive corpus
- **Gini Coefficient:** Measure of inequality in frequency distribution
  - 0 = all tokens equally frequent
  - 1 = all occurrences in single token
  - Useful for detecting skewed distributions

### Document Statistics (Corpus Mode)

- **Document Frequency (DF):** How many docs contain token
- **Avg Frequency Per Doc:** total_frequency / document_frequency
- **Document Length Stats:** Mean/median/std of tokens per document

---

## Configuration & Parameters

### Standard Config (Shared Contract)
- `lowercase` (bool, default true): Normalize tokens
- `remove_stopwords` (bool, default false): Filter stopwords
- `stopword_list` (array, default English): Custom stopwords
- `min_token_length` (int, default 1): Minimum token length
- `verbose` (bool, default false): Include detailed stats

### Frequency Analysis Specific
- `top_k` (int, default 20): Return top K tokens
- `bottom_k` (int, default 5): Return bottom K tokens
- `include_percentiles` (bool, default true): Compute percentiles (slower for large vocabularies)

---

## CLI Interface

```bash
# Analyze token stream
python -m tools.frequency_analysis \
  --input tokens.json \
  --output analysis.json

# Analyze corpus (document-level)
python -m tools.frequency_analysis \
  --input corpus.json \
  --corpus \
  --output corpus_analysis.json

# Custom top_k
python -m tools.frequency_analysis \
  --input tokens.json \
  --top-k 50 \
  --output analysis.json

# Compute coverage
python -m tools.frequency_analysis \
  --input tokens.json \
  --compute-coverage \
  --coverage-threshold 0.9 \
  --output coverage.json

# Generate histogram
python -m tools.frequency_analysis \
  --input tokens.json \
  --histogram \
  --output histogram.json

# With stopwords
python -m tools.frequency_analysis \
  --input tokens.json \
  --remove-stopwords \
  --output analysis.json

# Verbose mode
python -m tools.frequency_analysis \
  --input tokens.json \
  --verbose \
  --output analysis.json
```

---

## Input/Output Formats

### Input (JSON)

**Shape A (Token Stream):**
```json
{
  "tokens": ["token1", "token2", "token1", ...],
  "config": {}
}
```

**Shape B (Corpus):**
```json
{
  "corpus": [
    {"id": "doc_1", "tokens": [...]},
    {"id": "doc_2", "tokens": [...]}
  ],
  "config": {}
}
```

### Output (JSON)

Standard Historical AI results format. Includes `frequency_distribution` (per-token details) and `statistics` (corpus-level summaries).

---

## Algorithm Details

### Frequency Computation

1. **Normalize tokens:** Apply config (lowercase, stopwords, min_length)
2. **Count occurrences:** Use collections.Counter
3. **Sort by frequency:** Descending order
4. **Compute ranks:** 1 = most frequent
5. **Compute percentiles:** (rank / total_unique_tokens) * 100

### Statistical Computation

1. **Collect all frequencies:** [f₁, f₂, ..., fₙ] for n unique tokens
2. **Mean:** Σ(fᵢ) / n
3. **Median:** Sorted middle value
4. **Std Dev:** sqrt(Σ((fᵢ - mean)²) / n)
5. **Quantiles:** Linear interpolation on sorted frequencies
6. **Gini:** Σ(2*i*fᵢ) / (n * Σ(fᵢ)) - (n+1)/n [where i is rank]

### Complexity

- **Time:** O(tokens + unique_tokens * log(unique_tokens)) for sorting
- **Space:** O(vocabulary_size)

---

## Edge Cases & Error Handling

1. **Empty token list:** Return empty distribution, zero statistics
2. **Single unique token:** All tokens identical; std_dev = 0, Gini = 1
3. **Single token occurrence:** Frequency = 1 for all
4. **Stopword-heavy corpus:** If all removed, return empty; no error
5. **Malformed input:** Exit 1 (ValueError)

---

## Testing Strategy

### Explicit Test Cases (TEST-frequency_analysis_examples.json)

1. **Simple distribution:**
   - 6 tokens: 3 of "a", 2 of "b", 1 of "c"
   - Expected: Correct frequencies, ranks, percentiles

2. **Uniform distribution:**
   - 9 tokens: 3 unique, 3 each
   - Expected: Mean=3, std_dev=0, Gini≈0.33

3. **Skewed distribution:**
   - 100 tokens: 1 token appears 90 times, others 1 time each
   - Expected: High std_dev, Gini≈0.9

4. **Coverage analysis:**
   - Compute % of vocabulary needed for 80%, 90%, 95% coverage
   - Expected: Monotonic increase

5. **Histogram:**
   - Generate bins, count tokens per bin
   - Expected: Correct bin assignments, total = corpus size

6. **Corpus mode:**
   - 3 docs with known tokens
   - Expected: Document frequencies, per-doc stats

7. **Single token:**
   - All tokens identical
   - Expected: 1 unique token, frequency = total_tokens

---

## Performance Notes

- **Typical:** 100K tokens, 10K unique → <50ms
- **Scales:** Linear with total token count
- **Percentile computation:** O(unique_tokens * log(unique_tokens)) for sorting; can be slow for 100K+ vocabulary
- **Gini coefficient:** O(unique_tokens); typically fast

---

## Dependencies & Constraints

- **Python:** 3.8+
- **Imports:** json, collections, statistics, math, itertools
- **External libs:** None (stdlib only)
- **Resource limits:** Max 1M tokens, 500K unique tokens
- **Hardware:** CPU-only

---

## Related Tools

- **Tokenizer v1:** Pre-processes text (upstream)
- **Inverted Index Builder v1:** Uses frequency counts
- **TF-IDF Ranker v1:** Uses document/term frequencies
- **Markov Chain v1:** Analyzes token sequence patterns
- **Naive Bayes Classifier v1:** Uses token frequencies for classification

---

## Non-Goals

- **Zipf's law or power-law analysis:** Statistical modeling beyond basic stats
- **Entropy or information theory:** Separate tool
- **Semantic analysis:** Pure frequency counts only
- **Language-specific insights:** No linguistic analysis
- **Visualization:** JSON output only; external tools visualize

---

## Post-1.0 Extensions

1. **Streaming mode:** Analyze token stream without loading all into memory
2. **Time-windowed analysis:** Frequency over time windows
3. **Comparative analysis:** Compare frequency distributions across multiple corpora
4. **Dispersion metrics:** How concentrated vs. spread are token occurrences across documents?
5. **Collocations:** Frequency of token pairs (bigrams, trigrams)

---

**Last updated:** 2026-07-14  
**For:** Historical AI batch  
**Related:** Historical AI Shared Contract v1, Inverted Index Builder v1, TF-IDF Ranker v1
