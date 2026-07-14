# SPEC: TF-IDF Ranker v1

**Module:** `tools/tfidf_ranker/`  
**Status:** Ready for spec  
**Dependencies:** stdlib (json, math, collections, statistics)  
**Priority:** Medium (classical IR; useful for corpus search, log analysis ranking)

---

## Overview

Rank documents by relevance to a query using classical TF-IDF (term frequency–inverse document frequency) scoring. Pure, stateless ranking: no training, no persistent models. All computation happens in-process from token streams.

**Design principle:** Standard TF-IDF vectorization (cosine similarity). Accept pre-tokenized corpus + query; emit ranked documents with per-term contribution details. Deterministic, no randomness, reference implementation.

**Use case:** "I have 500 tokenized documents. Rank them by relevance to the query 'machine learning optimization'. Show me the top 10 with score breakdowns."

---

## Scope

### In Scope ✓
- TF-IDF cosine similarity ranking
- Support multiple TF-IDF variants (standard, BM25-like weighting, sublinear TF)
- Pre-tokenized input (token arrays)
- Configurable query parameters: top_k, similarity threshold, lowercase, stopwords
- Output: ranked results with scores [0, 1] + per-term contributions
- Batch ranking: score one query against multiple documents
- Verbose mode: include detailed computation (term frequencies, IDF scores, vector norms)

### Out of Scope ✗
- Training/learning: TF-IDF tables computed on-the-fly from input corpus
- Persistent models: All data in-process; no model files
- Tokenization: Expect pre-tokenized input (Tokenizer tool handles raw text)
- Advanced stemming/lemmatization: Token comparison is exact match
- Relevance feedback or query expansion
- Phonetic matching or fuzzy matching

---

## Module Structure

```
tools/tfidf_ranker/
  __init__.py                     # exports main functions
  core.py                         # TF-IDF computation and ranking
  tfidf_variants.py               # standard, sublinear, BM25-like variants
  cli.py                          # argparse CLI
  ranker_schema.py                # dataclasses for input/output
  README.md                        # usage + algorithm explanation
  __main__.py                     # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

#### 1. `rank_documents(corpus: list, query: list, config: dict = None) -> dict`

**Purpose:** Rank documents by TF-IDF similarity to query.

**Input:**

- `corpus` (list): Documents, each with tokens:
  ```json
  [
    {
      "id": "doc_1",
      "tokens": ["machine", "learning", "optimization"]
    },
    {
      "id": "doc_2",
      "tokens": ["deep", "learning", "neural", "networks"]
    }
  ]
  ```

- `query` (list): Query tokens:
  ```json
  ["machine", "learning", "optimization"]
  ```

- `config` (dict, optional):
  ```json
  {
    "tfidf_variant": "standard",
    "top_k": 10,
    "threshold": 0.0,
    "lowercase": true,
    "remove_stopwords": false,
    "verbose": false
  }
  ```

**Output:**

```json
{
  "tool": "tfidf_ranker",
  "version": "v1",
  "run_id": "tfidf_rank_001",
  "timestamp": "2026-07-14T15:05:00Z",
  "input_summary": {
    "corpus_size": 2,
    "query_tokens": 3,
    "variant": "standard"
  },
  "results": [
    {
      "result_id": "doc_1",
      "rank": 1,
      "value": 0.87,
      "details": {
        "cosine_similarity": 0.87,
        "query_coverage": 1.0,
        "term_contributions": {
          "machine": 0.28,
          "learning": 0.35,
          "optimization": 0.24
        },
        "doc_length": 3,
        "query_length": 3
      }
    },
    {
      "result_id": "doc_2",
      "rank": 2,
      "value": 0.42,
      "details": {
        "cosine_similarity": 0.42,
        "query_coverage": 0.333,
        "term_contributions": {
          "learning": 0.42
        },
        "doc_length": 4,
        "query_length": 3
      }
    }
  ],
  "metadata": {
    "computation_time_ms": 8,
    "config_used": {
      "tfidf_variant": "standard",
      "top_k": 10,
      "threshold": 0.0
    }
  }
}
```

---

## TF-IDF Variants

### Variant 1: Standard (default)

**TF formula:** `tf(t, d) = count(t, d) / len(d)`  
**IDF formula:** `idf(t) = log(corpus_size / doc_freq(t))`  
**Similarity:** Cosine of TF-IDF vectors

```
score(query, doc) = cos(tfidf_vector(query), tfidf_vector(doc))
                  = sum(tf(t,q) * idf(t) * tf(t,d) * idf(t)) / (||q|| * ||d||)
```

### Variant 2: Sublinear TF

**TF formula:** `tf(t, d) = 1 + log(count(t, d))` (saturates at high frequencies)  
**IDF formula:** Same as standard  

Useful when documents have highly skewed term distributions.

### Variant 3: BM25-like (probabilistic)

**TF formula:** `tf_bm25(t, d) = (count(t,d) * (k1 + 1)) / (count(t,d) + k1 * (1 - b + b * (len(d) / avg_len)))`  
**IDF formula:** `idf(t) = log((corpus_size - doc_freq(t) + 0.5) / (doc_freq(t) + 0.5))`  
**Parameters:** k1 = 1.5, b = 0.75 (industry standard)

More robust to document length bias than standard TF-IDF.

---

## Configuration Options

### Standard Config (Shared Contract)
- `lowercase` (bool, default true): Normalize tokens
- `remove_stopwords` (bool, default false): Filter common words
- `stopword_list` (array, default English): Custom stopwords
- `min_token_length` (int, default 1): Minimum token length
- `top_k` (int, default 10): Return top K results
- `threshold` (float, default 0.0): Minimum similarity to include
- `verbose` (bool, default false): Include detailed term contributions

### TF-IDF Specific Config
- `tfidf_variant` (string, default "standard"): One of `["standard", "sublinear", "bm25"]`

---

## CLI Interface

```bash
# Basic ranking
python -m tools.tfidf_ranker \
  --input corpus.json \
  --query '["machine", "learning"]' \
  --output results.json

# With custom config
python -m tools.tfidf_ranker \
  --input corpus.json \
  --query '["machine", "learning"]' \
  --tfidf-variant bm25 \
  --top-k 5 \
  --threshold 0.2 \
  --lowercase \
  --remove-stopwords \
  --output results.json

# Verbose mode (include term contributions)
python -m tools.tfidf_ranker \
  --input corpus.json \
  --query '["machine", "learning"]' \
  --verbose \
  --output results.json

# From stdin/stdout
echo '{"corpus": [...], "query": [...]}' | python -m tools.tfidf_ranker
```

---

## Input/Output Formats

### Input (JSON)

**Shape A (Corpus + Query):**
```json
{
  "corpus": [
    {"id": "doc_1", "tokens": [...]},
    {"id": "doc_2", "tokens": [...]}
  ],
  "query": ["token1", "token2"],
  "config": {}
}
```

**Shape B (Corpus + Queries file):**
```json
{
  "corpus": [...],
  "query_file": "queries.jsonl"
}
```

### Output (JSON)

Standard Historical AI results format (see Shared Contract). Per-result details include:
- `cosine_similarity`: Raw score [0, 1]
- `query_coverage`: Fraction of query terms found in doc [0, 1]
- `term_contributions`: Per-term contribution to score
- `doc_length`, `query_length`: Token counts

---

## Algorithm Details

### Computation Steps

1. **Build vocabulary:** Extract unique tokens from corpus (respecting config filters)
2. **Compute document frequencies:** Count documents containing each token
3. **Compute IDF scores:** `idf(t) = log(N / df(t))` for each term
4. **Tokenize query:** Apply same filters as corpus (lowercase, stopwords, etc.)
5. **Compute TF-IDF vectors:**
   - For query: `tf(t, q) * idf(t)` for each term
   - For each doc: `tf(t, d) * idf(t)` for each term
6. **Normalize vectors:** L2 norm
7. **Compute cosine similarity:** `dot_product(query_vec, doc_vec) / (||query_vec|| * ||doc_vec||)`
8. **Sort & return:** Top-k by similarity

### Complexity

- **Time:** O(corpus_size * avg_doc_len + query_len * unique_terms) ≈ O(N) for typical inputs
- **Space:** O(vocabulary_size) for IDF table

---

## Edge Cases & Error Handling

1. **Empty query:** Return empty results (no error)
2. **Empty corpus:** Return empty results (no error)
3. **Query terms not in corpus:** Score 0 for those terms; compute partial similarity for matching terms
4. **Single-token corpus/query:** Compute similarity normally (no special case)
5. **Duplicate tokens in query:** Count each occurrence (e.g., `["learning", "learning"]` weights "learning" higher)
6. **Malformed JSON:** Exit 1 with ValueError
7. **Missing `corpus` or `query`:** Exit 1 with ValueError

---

## Testing Strategy

### Explicit Test Cases (TEST-tfidf_ranker_examples.json)

1. **Simple ranking (standard variant):**
   - Corpus: 3 docs, query: 2 tokens
   - Expected: Correct cosine similarity scores, ranked order

2. **Query coverage:**
   - Query: ["a", "b", "c"], Doc: ["a", "b"]
   - Expected: query_coverage = 0.667

3. **Variant comparison:**
   - Same input, run standard + BM25 variants
   - Expected: Different scores, same ranking order (usually)

4. **Empty query:**
   - Query: []
   - Expected: Empty results (exit 0)

5. **Stopword filtering:**
   - Query: ["the", "machine", "learning"]
   - Config: remove_stopwords = true
   - Expected: "the" ignored, only "machine" and "learning" contribute

6. **Threshold filtering:**
   - Config: threshold = 0.5
   - Expected: Only results with similarity >= 0.5 returned

---

## Performance Notes

- **Typical:** 1000 docs, 100 tokens each, 5-token query → <100ms
- **Scales:** Linear with corpus size for typical queries
- **Bottleneck:** IDF computation (can cache if needed, v2)

---

## Dependencies & Constraints

- **Python:** 3.8+
- **Imports:** json, math, collections, statistics, re
- **External libs:** None (stdlib only)
- **Resource limits:** Max 100K docs, 1M tokens total
- **Hardware:** CPU-only

---

## Related Tools

- **Tokenizer v1:** Pre-processes text → tokens (upstream)
- **Boolean Search v1:** Complementary exact-match ranking
- **Inverted Index Builder v1:** Can build supporting structure for faster ranking (v2)
- **Text Search v1:** Simple pattern matching (different algorithm)
- **Cosine Similarity v1:** General-purpose vector similarity (used internally)

---

## Non-Goals

- **Semantic similarity:** TF-IDF is syntactic, not semantic
- **Learning:** No training phase; IDF computed on-the-fly
- **Persistent models:** All state in-process
- **Phrase queries:** Only term-based ranking
- **Real-time incremental updates:** Full recomputation required

---

## Post-1.0 Extensions

1. **Inverted index caching:** Pre-compute IDF tables for known corpora
2. **Incremental corpus updates:** Add/remove docs without recomputing all IDF
3. **Phrase queries:** Support "term1 term2" as adjacent tokens
4. **Field-based TF-IDF:** Weight different fields (title vs. body) differently
5. **Query expansion:** Synonyms, related terms (separate tool)

---

**Last updated:** 2026-07-14  
**For:** Historical AI batch  
**Related:** Historical AI Shared Contract v1, TOOL_PHILOSOPHY.md
