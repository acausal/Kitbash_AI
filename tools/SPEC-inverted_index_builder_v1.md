# SPEC: Inverted Index Builder v1

**Module:** `tools/inverted_index_builder/`  
**Status:** Ready for spec  
**Dependencies:** stdlib (json, collections)  
**Priority:** Medium (supporting structure for fast Boolean/ranking queries; enables v2 optimization)

---

## Overview

Build an inverted index from a tokenized corpus: map each unique token to the list of documents containing it, along with frequency and position metadata. Pure, stateless construction: no persistent state, all data in-process. Emits JSON index suitable for downstream Boolean Search, TF-IDF ranking, or other retrieval operations.

**Design principle:** Deterministic index construction. Accept pre-tokenized corpus; emit inverted index in standard JSON format. No learning, no filtering at index time—that's configuration-driven. Index can be passed to downstream tools or serialized to disk by caller.

**Use case:** "I have 10K documents. Build me an inverted index so I can run fast Boolean searches or TF-IDF ranking without recomputing term frequencies each time."

---

## Scope

### In Scope ✓
- Build inverted index: token → [doc_ids containing token]
- Compute term frequencies (TF): per-document occurrence count
- Compute document frequencies (DF): how many docs contain each token
- Support positional indexing (optional): token → [(doc_id, positions in doc)]
- Configurable filtering: lowercase, stopwords, min/max term length
- Support batch indexing: multiple corpora
- Output: JSON index with metadata (vocabulary size, total docs, etc.)
- Detailed output: per-term statistics (DF, total frequency across corpus)

### Out of Scope ✗
- Query execution: Index is data structure only; search tools use it
- Ranking: Index doesn't compute TF-IDF; tools do that
- Persistence: Tool doesn't write to disk; caller handles serialization
- Incremental updates: Always rebuilds from scratch (v1)
- Compression or optimization: Raw index (v2 can add compression)

---

## Module Structure

```
tools/inverted_index_builder/
  __init__.py                     # exports main functions
  core.py                         # index building logic
  index_operations.py             # query, merge, statistics on indexes
  cli.py                          # argparse CLI
  index_schema.py                 # dataclasses for input/output
  README.md                        # usage + examples
  __main__.py                     # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

#### 1. `build_inverted_index(corpus: list, config: dict = None) -> dict`

**Purpose:** Build inverted index from tokenized corpus.

**Input:**

- `corpus` (list): Documents with tokens:
  ```json
  [
    {
      "id": "doc_1",
      "tokens": ["machine", "learning", "algorithm"]
    },
    {
      "id": "doc_2",
      "tokens": ["deep", "learning", "neural", "network"]
    },
    {
      "id": "doc_3",
      "tokens": ["machine", "learning", "neural", "network"]
    }
  ]
  ```

- `config` (dict, optional):
  ```json
  {
    "lowercase": true,
    "remove_stopwords": false,
    "stopword_list": ["the", "a", "an"],
    "min_token_length": 1,
    "max_token_length": null,
    "positional": false,
    "verbose": false
  }
  ```

**Output:**

```json
{
  "tool": "inverted_index_builder",
  "version": "v1",
  "run_id": "invindex_001",
  "timestamp": "2026-07-14T15:20:00Z",
  "input_summary": {
    "corpus_size": 3,
    "total_tokens": 11,
    "avg_tokens_per_doc": 3.67
  },
  "index": {
    "vocabulary_size": 8,
    "total_documents": 3,
    "terms": {
      "machine": {
        "doc_frequency": 2,
        "total_frequency": 2,
        "documents": [
          {
            "doc_id": "doc_1",
            "term_frequency": 1,
            "positions": [0]
          },
          {
            "doc_id": "doc_3",
            "term_frequency": 1,
            "positions": [0]
          }
        ]
      },
      "learning": {
        "doc_frequency": 3,
        "total_frequency": 3,
        "documents": [
          {
            "doc_id": "doc_1",
            "term_frequency": 1,
            "positions": [1]
          },
          {
            "doc_id": "doc_2",
            "term_frequency": 1,
            "positions": [1]
          },
          {
            "doc_id": "doc_3",
            "term_frequency": 1,
            "positions": [1]
          }
        ]
      },
      "algorithm": {
        "doc_frequency": 1,
        "total_frequency": 1,
        "documents": [
          {
            "doc_id": "doc_1",
            "term_frequency": 1,
            "positions": [2]
          }
        ]
      },
      "deep": {
        "doc_frequency": 1,
        "total_frequency": 1,
        "documents": [
          {
            "doc_id": "doc_2",
            "term_frequency": 1,
            "positions": [0]
          }
        ]
      },
      "neural": {
        "doc_frequency": 2,
        "total_frequency": 2,
        "documents": [
          {
            "doc_id": "doc_2",
            "term_frequency": 1,
            "positions": [2]
          },
          {
            "doc_id": "doc_3",
            "term_frequency": 1,
            "positions": [2]
          }
        ]
      },
      "network": {
        "doc_frequency": 2,
        "total_frequency": 2,
        "documents": [
          {
            "doc_id": "doc_2",
            "term_frequency": 1,
            "positions": [3]
          },
          {
            "doc_id": "doc_3",
            "term_frequency": 1,
            "positions": [3]
          }
        ]
      }
    }
  },
  "metadata": {
    "computation_time_ms": 12,
    "config_used": {
      "lowercase": true,
      "remove_stopwords": false,
      "min_token_length": 1
    },
    "index_size_bytes_estimate": 2400
  }
}
```

#### 2. `query_index(index: dict, term: str, case_sensitive: bool = False) -> dict`

**Purpose:** Query built index to get documents containing a term.

**Input:**
```json
{
  "index": {... built index ...},
  "term": "learning",
  "case_sensitive": false
}
```

**Output:**
```json
{
  "query_term": "learning",
  "found": true,
  "doc_frequency": 3,
  "total_frequency": 3,
  "documents": [
    {
      "doc_id": "doc_1",
      "term_frequency": 1,
      "positions": [1]
    },
    {
      "doc_id": "doc_2",
      "term_frequency": 1,
      "positions": [1]
    },
    {
      "doc_id": "doc_3",
      "term_frequency": 1,
      "positions": [1]
    }
  ]
}
```

#### 3. `compute_idf(index: dict) -> dict`

**Purpose:** Compute IDF scores for all terms in index.

**Input:**
```json
{
  "index": {... built index ...}
}
```

**Output:**
```json
{
  "idf_scores": {
    "machine": 0.405,
    "learning": 0.0,
    "algorithm": 0.693,
    "deep": 0.693,
    "neural": 0.405,
    "network": 0.405
  },
  "total_documents": 3,
  "metadata": {
    "idf_formula": "log(N / df)",
    "computation_time_ms": 1
  }
}
```

---

## Index Format

### Standard Structure

```json
{
  "index": {
    "vocabulary_size": N,
    "total_documents": M,
    "terms": {
      "token": {
        "doc_frequency": int,
        "total_frequency": int,
        "documents": [
          {
            "doc_id": string,
            "term_frequency": int,
            "positions": [int, ...]  (if positional=true)
          }
        ]
      }
    }
  }
}
```

### Terminology

- **`doc_frequency`**: Number of documents containing this term
- **`total_frequency`**: Sum of term frequencies across all documents
- **`term_frequency`** (per document): Occurrence count in that specific document
- **`positions`** (optional): Array of 0-indexed positions in document where term appears

---

## Configuration Options

### Standard Config (Shared Contract)
- `lowercase` (bool, default true): Normalize tokens
- `remove_stopwords` (bool, default false): Filter stopwords
- `stopword_list` (array, default English): Custom stopwords
- `min_token_length` (int, default 1): Minimum token length
- `max_token_length` (int, default null): Maximum token length (null = unlimited)
- `verbose` (bool, default false): Include detailed stats

### Inverted Index Specific
- `positional` (bool, default false): Track token positions (increases output size)

---

## CLI Interface

```bash
# Basic index construction
python -m tools.inverted_index_builder \
  --input corpus.json \
  --output index.json

# With filtering
python -m tools.inverted_index_builder \
  --input corpus.json \
  --lowercase \
  --remove-stopwords \
  --min-token-length 2 \
  --output index.json

# Positional indexing
python -m tools.inverted_index_builder \
  --input corpus.json \
  --positional \
  --output index.json

# Query index
python -m tools.inverted_index_builder \
  --index index.json \
  --query-term learning

# Compute IDF scores
python -m tools.inverted_index_builder \
  --index index.json \
  --compute-idf

# Verbose mode
python -m tools.inverted_index_builder \
  --input corpus.json \
  --verbose \
  --output index.json
```

---

## Input/Output Formats

### Input (JSON)

**Shape A (Corpus + Config):**
```json
{
  "corpus": [
    {"id": "doc_1", "tokens": [...]},
    {"id": "doc_2", "tokens": [...]}
  ],
  "config": {
    "lowercase": true,
    "positional": false
  }
}
```

### Output (JSON)

Standard Historical AI results format. `index` field contains full inverted index with `terms` dictionary.

---

## Algorithm Details

### Index Construction

1. **Initialize:** Empty dict for terms
2. **For each document:**
   - For each token (0-indexed position):
     - Normalize (lowercase, filter stopwords, etc.)
     - If term not in index: create entry
     - Increment doc_frequency (if first occurrence in this doc)
     - Increment total_frequency
     - Record term_frequency and position (if positional)
3. **Emit:** Full index with metadata

### Complexity

- **Time:** O(corpus_size * avg_tokens_per_doc * token_processing_time) ≈ O(N)
- **Space:** O(vocabulary_size + total_occurrences) ≈ O(N)

---

## Edge Cases & Error Handling

1. **Empty corpus:** Return empty index with 0 vocabulary_size
2. **Empty token list in document:** Skip document (or count as present with 0 tokens)
3. **Duplicate tokens in document:** Count each occurrence separately
4. **Stopword-only document:** Document still indexed; positions may be empty if all stopwords removed
5. **Malformed input:** Exit 1 (ValueError)
6. **Query for non-existent term:** Return `found: false` with empty documents array

---

## Testing Strategy

### Explicit Test Cases (TEST-inverted_index_builder_examples.json)

1. **Simple corpus:**
   - 3 docs with known tokens
   - Expected: Correct doc_frequency, total_frequency, positions

2. **Term frequencies:**
   - Doc with repeated tokens: `["hello", "world", "hello"]`
   - Expected: term_frequency = 2 for "hello"

3. **Document frequency:**
   - Term appears in 2/3 docs
   - Expected: doc_frequency = 2

4. **Positional indexing:**
   - Same corpus with positional=true
   - Expected: positions array populated

5. **Stopword filtering:**
   - Corpus with stopwords + content words
   - Config: remove_stopwords=true
   - Expected: Stopwords excluded from index

6. **Query index:**
   - Build index, then query for a term
   - Expected: Correct documents returned

7. **IDF computation:**
   - Build index, compute IDF
   - Expected: IDF values decrease with higher doc_frequency

---

## Performance Notes

- **Typical:** 1000 docs, 100 tokens each → <100ms
- **Scales:** Linear with total token count
- **Bottleneck:** I/O (reading corpus)
- **Positional indexing overhead:** ~1.5x larger output, minimal time cost

---

## Dependencies & Constraints

- **Python:** 3.8+
- **Imports:** json, collections
- **External libs:** None (stdlib only)
- **Resource limits:** Max 100K docs, 1M total tokens
- **Hardware:** CPU-only

---

## Related Tools

- **TF-IDF Ranker v1:** Uses index output for fast ranking (v2)
- **Boolean Search v1:** Can use index for faster matching (v2)
- **Text Search v1:** Simpler pattern matching (no indexing)
- **Tokenizer v1:** Pre-processes text (upstream)

---

## Non-Goals

- **Query execution:** Index is data; search tools use it
- **Ranking:** TF-IDF and other tools compute scores
- **Persistence:** Tool doesn't write to disk; caller handles
- **Incremental updates:** Rebuild from scratch only (v1)
- **Compression:** Raw index (v2)

---

## Post-1.0 Extensions

1. **Incremental updates:** Add/remove documents without full rebuild
2. **Compression:** Use bit-packing, VByte encoding for smaller output
3. **Hierarchical indexes:** Support field-based indexing (title, body, etc.)
4. **Multi-language support:** Language-specific stopword lists, stemming
5. **Phrase indexing:** Track adjacent term pairs for phrase queries

---

**Last updated:** 2026-07-14  
**For:** Historical AI batch  
**Related:** Historical AI Shared Contract v1, TF-IDF Ranker v1, Boolean Search v1
