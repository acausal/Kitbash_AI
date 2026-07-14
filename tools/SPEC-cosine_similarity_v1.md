# SPEC: Cosine Similarity v1

**Module:** `tools/cosine_similarity/`  
**Status:** Ready for build  
**Dependencies:** stdlib (json, math, collections)  
**Priority:** High (validates collision clusters; enables procedural edge extraction; lightweight grain embedding analysis)

---

## Overview

Compute cosine similarity between vectors to quantify semantic/structural similarity. Generate similarity matrices for collections of vectors; identify which items cluster together, which are distinct, and which have unexpected relationships. Primary use: validate collision cluster coherence, extract procedural edge weights from grain co-occurrence, analyze grain embedding space without neural models.

**Design principle:** Deterministic, pure-math similarity computation. No neural embeddings; works with any vector representation (TF-IDF term vectors, token counts, grain state vectors, query distributions). Output is both numerical (matrices) and interpretable (stats, comparisons).

**Use case:** "I have 10 grains' TF-IDF vectors. Which grains are similar (high cosine similarity)? Are they the ones in my collision cluster? What's the cluster's mean coherence? Can I extract procedural edge weights from pairwise similarities?"

---

## Scope

### In Scope ✓
- Compute cosine similarity between two vectors (single pair)
- Compute all-pairs similarity matrix for N vectors (N×N symmetric matrix)
- Accept vectors as: raw floats (lists), TF-IDF dicts (term→count), JSON arrays
- Normalize vectors before computing (handle unnormalized input)
- Compute aggregate statistics: mean, std, min, max, percentiles
- Identify high/low similarity pairs (top-K similar, top-K dissimilar)
- Validate vector dimensions (all same length)
- Output: JSON with similarity matrix + metadata + statistics
- Handle sparse vectors efficiently (skip zero entries)
- Support batching (multiple similarity matrices in one call)

### Out of Scope ✗
- Other distance metrics (Euclidean, Manhattan) — v1 is cosine only
- Dimensionality reduction (PCA, UMAP) — separate tool
- Clustering or grouping (k-means, hierarchical) — separate tool
- Neural embeddings or semantic understanding (just cosine math)
- Interpretation of what high/low similarity "means" (caller interprets)

---

## Module Structure

```
tools/cosine_similarity/
  __init__.py                    # exports main functions
  core.py                        # cosine similarity computation
  vector_utils.py                # vector normalization, validation
  matrix_stats.py                # aggregate statistics, comparisons
  cli.py                         # argparse CLI
  similarity_schema.py           # dataclasses for JSON output
  README.md                       # usage docs + examples
  __main__.py                    # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

All functions accept/return JSON-serializable types (strings, dicts, lists, floats).

#### 1. `compute_similarity(vector_a: list, vector_b: list, normalize: bool = True) -> dict`

**Purpose:** Compute cosine similarity between two vectors.

**Input:**
- `vector_a` (list): First vector, e.g., `[0.5, 0.3, 0.1, 0.0, 0.1]` or TF-IDF dict `{"term1": 0.5, "term2": 0.3}`
- `vector_b` (list): Second vector (same format, same dimension)
- `normalize` (bool): If True, normalize vectors before computing (default: True)

**Output (JSON):**
```json
{
  "similarity_computation": {
    "vector_a_dimension": 5,
    "vector_b_dimension": 5,
    "normalized": true
  },
  "result": {
    "cosine_similarity": 0.856,
    "dot_product": 0.856,
    "magnitude_a": 1.0,
    "magnitude_b": 1.0,
    "interpretation": "high_similarity"
  }
}
```

**Behavior:**
- Compute dot product: `sum(a[i] * b[i])`
- Compute magnitudes: `sqrt(sum(a[i]^2))`, `sqrt(sum(b[i]^2))`
- If normalize=True: divide vectors by magnitudes (unit normalization)
- Cosine similarity: `dot_product / (magnitude_a * magnitude_b)`
- Range: [-1, 1] (typically [0, 1] for non-negative vectors; 1=identical direction, 0=orthogonal)
- Interpret result: < 0.3 = low similarity, 0.3–0.7 = medium, > 0.7 = high

**Error handling:**
- `ValueError` if vectors different dimension
- `ValueError` if vectors are zero (magnitude=0, undefined similarity)
- `ValueError` if vectors not numeric

---

#### 2. `compute_similarity_matrix(vectors: list, vector_ids: list = None, normalize: bool = True) -> dict`

**Purpose:** Compute all-pairs similarity matrix for N vectors.

**Input:**
- `vectors` (list): List of N vectors, e.g.:
  ```json
  [
    [0.5, 0.3, 0.1, 0.0, 0.1],
    [0.4, 0.2, 0.15, 0.05, 0.2],
    [0.1, 0.1, 0.8, 0.0, 0.0]
  ]
  ```
  OR TF-IDF dicts:
  ```json
  [
    {"photosynthesis": 0.5, "chloroplast": 0.3, "glucose": 0.1},
    {"photosynthesis": 0.4, "chloroplast": 0.2, "ATP": 0.15},
    {"respiration": 0.8, "ATP": 0.2}
  ]
  ```

- `vector_ids` (list, optional): Human-readable labels for vectors (default: ["v0", "v1", ..., "vN"])
  ```json
  ["grain_42", "grain_137", "grain_89"]
  ```

- `normalize` (bool): Normalize before computing (default: True)

**Output (JSON):**
```json
{
  "matrix_params": {
    "n_vectors": 3,
    "vector_dimension": 5,
    "normalized": true
  },
  "vector_ids": ["grain_42", "grain_137", "grain_89"],
  "similarity_matrix": [
    [1.0, 0.856, 0.120],
    [0.856, 1.0, 0.095],
    [0.120, 0.095, 1.0]
  ],
  "statistics": {
    "mean_similarity": 0.553,
    "std_similarity": 0.387,
    "min_similarity": 0.095,
    "max_similarity": 1.0,
    "percentiles": {
      "p25": 0.108,
      "p50": 0.553,
      "p75": 0.928
    }
  },
  "highest_similarity_pairs": [
    {"pair": ["grain_42", "grain_137"], "similarity": 0.856},
    {"pair": ["grain_42", "grain_89"], "similarity": 0.120}
  ],
  "lowest_similarity_pairs": [
    {"pair": ["grain_137", "grain_89"], "similarity": 0.095}
  ]
}
```

**Behavior:**
- Validate all vectors same dimension
- Compute N×N symmetric similarity matrix (only upper triangle computed, mirrored for output)
- Diagonal is always 1.0 (vector is identical to itself)
- Compute aggregate statistics (mean, std, percentiles) over off-diagonal elements
- Identify top K highest and lowest similarity pairs (default K=5)
- Interpret results: high mean similarity (>0.7) = coherent cluster, low (<0.3) = diverse set

**Error handling:**
- `ValueError` if vectors different dimensions
- `ValueError` if fewer than 2 vectors provided
- `ValueError` if vector_ids provided but length != N vectors

---

#### 3. `compute_vector_neighbors(query_vector: list, vectors: list, vector_ids: list = None, top_k: int = 5) -> dict`

**Purpose:** Find most similar vectors to a query vector (k-nearest neighbors by cosine similarity).

**Input:**
- `query_vector` (list): Query vector, e.g., `[0.5, 0.3, 0.1, 0.0, 0.1]`
- `vectors` (list): List of N candidate vectors
- `vector_ids` (list, optional): Labels for candidates
- `top_k` (int): Return top K most similar (default: 5)

**Output (JSON):**
```json
{
  "query_vector_id": "query_grain",
  "top_k": 5,
  "neighbors": [
    {
      "rank": 1,
      "vector_id": "grain_42",
      "similarity": 0.856,
      "interpretation": "high_similarity"
    },
    {
      "rank": 2,
      "vector_id": "grain_137",
      "similarity": 0.745,
      "interpretation": "high_similarity"
    },
    {
      "rank": 3,
      "vector_id": "grain_89",
      "similarity": 0.620,
      "interpretation": "medium_similarity"
    },
    {
      "rank": 4,
      "vector_id": "grain_200",
      "similarity": 0.310,
      "interpretation": "low_similarity"
    },
    {
      "rank": 5,
      "vector_id": "grain_50",
      "similarity": 0.095,
      "interpretation": "low_similarity"
    }
  ],
  "statistics": {
    "mean_neighbor_similarity": 0.525,
    "std_neighbor_similarity": 0.307,
    "query_vector_is_outlier": false
  }
}
```

**Behavior:**
- Compute similarity between query_vector and all vectors
- Sort by similarity descending
- Return top K with rank, ID, similarity, interpretation
- Flag if query_vector is an outlier (all neighbors have low similarity)

**Error handling:**
- `ValueError` if query_vector different dimension than candidates
- `ValueError` if top_k > N vectors

---

#### 4. `compare_vector_sets(vectors_a: list, vectors_b: list, vector_ids_a: list = None, vector_ids_b: list = None) -> dict`

**Purpose:** Compute cross-set similarity matrix (how similar are vectors in set A to vectors in set B?).

**Input:**
- `vectors_a` (list): First set of M vectors
- `vectors_b` (list): Second set of N vectors
- `vector_ids_a`, `vector_ids_b` (list, optional): Labels

**Output (JSON):**
```json
{
  "set_a": {"n_vectors": 3, "vector_ids": ["grain_42", "grain_137", "grain_89"]},
  "set_b": {"n_vectors": 2, "vector_ids": ["query_today", "query_yesterday"]},
  "cross_set_similarity_matrix": [
    [0.856, 0.720],
    [0.745, 0.680],
    [0.620, 0.510]
  ],
  "statistics": {
    "mean_cross_similarity": 0.688,
    "std_cross_similarity": 0.106,
    "max_similarity": 0.856,
    "min_similarity": 0.510
  },
  "closest_pairs": [
    {"from": "grain_42", "to": "query_today", "similarity": 0.856},
    {"from": "grain_42", "to": "query_yesterday", "similarity": 0.720}
  ]
}
```

**Behavior:**
- Compute M×N cross-set similarity matrix (not symmetric)
- Useful for: "which query is most similar to which grain?" or "has query distribution shifted between today and yesterday?"

**Error handling:**
- `ValueError` if vectors in A and B have different dimension

---

### CLI Interface (in `cli.py`)

```bash
# Single pair similarity
python -m tools.cosine_similarity compute-pair \
  --vector-a "[0.5, 0.3, 0.1, 0.0, 0.1]" \
  --vector-b "[0.4, 0.2, 0.15, 0.05, 0.2]"

# All-pairs matrix
python -m tools.cosine_similarity compute-matrix \
  --vectors vectors.json \
  --vector-ids ids.json

# k-nearest neighbors
python -m tools.cosine_similarity compute-neighbors \
  --query-vector "[0.5, 0.3, 0.1, 0.0, 0.1]" \
  --vectors vectors.json \
  --vector-ids ids.json \
  --top-k 5

# Cross-set comparison
python -m tools.cosine_similarity compare-sets \
  --vectors-a set_a.json \
  --vectors-b set_b.json \
  --ids-a ids_a.json \
  --ids-b ids_b.json
```

**Output:** JSON to stdout

**Exit codes:**
- `0`: Success
- `1`: ValueError (invalid input/format)
- `2`: RuntimeError (I/O or processing error)

---

## Interpretation Guide

### Similarity Score Thresholds

| Score Range | Interpretation | Use Case |
|-------------|-----------------|----------|
| 0.90–1.0 | Nearly identical | Same grain, different state? Data quality issue? |
| 0.75–0.90 | High similarity | Strong collision pair; grains should be disambiguated |
| 0.50–0.75 | Medium similarity | Related grains; moderate overlap in concept space |
| 0.25–0.50 | Low similarity | Weakly related; distinct roles |
| 0.0–0.25 | Very low similarity | Orthogonal; no conceptual overlap |

### Cluster Coherence Interpretation

| Mean Similarity | Interpretation | Action |
|-----------------|-----------------|--------|
| > 0.80 | Very high coherence | Cluster members are genuinely similar; may need fine-grained disambiguation |
| 0.60–0.80 | High coherence | Cluster is well-formed; members meaningfully related |
| 0.40–0.60 | Medium coherence | Cluster members related but diverse; may include false positives |
| < 0.40 | Low coherence | Cluster is fragmented; re-evaluate membership |

### Use Cases & Workflows

**1. Collision Cluster Validation (Sleep Tier 2):**
```
Input: grain vectors from collision cluster [42, 137, 89]
↓ compute_similarity_matrix()
Output: 3×3 matrix, mean_similarity = 0.62
→ "This cluster has medium coherence; members are related but not identical."
→ "Pair (42, 137) is most similar (0.86); consider ternary delta refinement."
```

**2. Procedural Edge Extraction (Stage 5):**
```
Input: execution trace with grains [tokenizer, negation_detector, svo_extractor, json_filter]
       + their state vectors at runtime
↓ compute_similarity_matrix()
Output: pairwise similarities
→ "tokenizer & negation_detector co-fire with similarity 0.95; strong procedural edge."
→ "svo_extractor & json_filter rarely co-fire (similarity 0.12); weak edge."
→ Extract procedural edges with similarity as weight
```

**3. Query Drift Detection (Downstream):**
```
Input: query term distribution today vs. 7 days ago
↓ compare_vector_sets() or compute_similarity()
Output: similarity = 0.71
→ "Query distribution has shifted moderately; possible cause for anomalies."
```

**4. Grain Embedding Space Exploration:**
```
Input: all grain TF-IDF vectors
↓ compute_similarity_matrix()
Output: full NxN similarity matrix
→ Identify grain clusters (high inter-similarity)
→ Identify outlier grains (low mean similarity to others)
→ Understand grain "neighborhoods" without neural embeddings
```

---

## Safety & Validation

**Filesystem:**
- Input from `workspace/` or `inbox/trusted/` (validated JSON)
- Output to `workspace/` or `outbox/` (use `tools/filesystem_access/`)

**Numerical stability:**
- Handle zero vectors gracefully (zero magnitude → undefined similarity, return NaN with warning)
- Handle very large/small numbers (use standard normalization, no rescaling)
- Sparse vectors optimized (skip zero entries in dot product)

**Reproducibility:**
- Same vectors → same similarity matrix, always
- No randomness; deterministic math
- Floating-point precision noted in output (similarity scores are float)

---

## Integration Points

**Upstream (provides vectors):**
- TF-IDF Ranker (term vectors)
- Grain state snapshots (grain embeddings)
- Query token distributions (for drift detection)
- Collision cluster member vectors

**Downstream (consumes output):**
- Sleep Tier 2: Collision cluster validation (coherence scores)
- Sleep Stage 5: Procedural edge extraction (similarity as weight)
- Grain embedding analysis (identification of grain neighborhoods)
- Anomaly detection (query drift signals)

---

## Data Flow Example

```
Sleep Tier 2 has collision cluster [42, 137, 89].
Extract grain vectors (TF-IDF or state-based): v42, v137, v89

↓ cosine_similarity.compute_similarity_matrix([v42, v137, v89])

Output:
  Matrix:
    [1.0,   0.86,  0.12]
    [0.86,  1.0,   0.10]
    [0.12,  0.10,  1.0]
  Mean similarity: 0.52
  Highest pair: (42, 137) = 0.86
  Lowest pair: (137, 89) = 0.10

↓ Sleep Tier 2 interpretation:

"Cluster coherence is medium (0.52). Grains 42 and 137 are strongly similar (0.86),
but 89 is weakly related (mean similarity 0.11 to others).
Recommendation: investigate whether grain 89 belongs in this cluster,
or if it's a distinct concept being conflated."

↓ Stage 5 (later):

Extract grain state vectors from successful reasoning traces.
For each tool sequence, compute similarity between grains that fired.
High similarity (>0.7) → strong procedural edge.
Low similarity (<0.3) → weak edge or sequential independence.
Build procedural edge graph with similarity as edge weight.
```

---

## Testing Strategy

### Test Cases

1. **Identical vectors:**
   - Vectors: `[1, 0, 0]` vs `[1, 0, 0]`
   - Expected: similarity = 1.0

2. **Orthogonal vectors:**
   - Vectors: `[1, 0, 0]` vs `[0, 1, 0]`
   - Expected: similarity = 0.0

3. **Parallel vectors (different magnitude):**
   - Vectors: `[2, 0, 0]` vs `[1, 0, 0]`
   - Expected: similarity = 1.0 (after normalization)

4. **All-pairs matrix (3 vectors):**
   - Vectors: `[[1,0,0], [0.7,0.3,0], [0.5,0.5,0]]`
   - Expected: 3×3 symmetric matrix, diagonal all 1.0, mean_similarity > 0.5

5. **k-nearest neighbors:**
   - Query: `[1, 0, 0]`, candidates: `[[1,0,0], [0,1,0], [0.7,0.3,0], [0,0,1]]`
   - Expected: top_1 = [1,0,0] (similarity 1.0), top_2 = [0.7,0.3,0] (similarity 0.7)

6. **Cross-set similarity:**
   - Set A: `[[1,0], [0,1]]`, Set B: `[[0.7,0.3], [0,1]]`
   - Expected: 2×2 matrix with high similarity between (A1,B0) and (A2,B1)

7. **Zero vector handling:**
   - Vector: `[0, 0, 0]` vs any vector
   - Expected: error or NaN with warning (magnitude undefined)

8. **Low coherence cluster:**
   - Vectors: `[[1,0,0], [0,1,0], [0,0,1]]` (orthogonal)
   - Expected: mean_similarity = 0.0, all pairs except diagonal = 0.0

### Example Test File (TEST-cosine_similarity_examples.json)

```json
{
  "test_cases": [
    {
      "name": "identical_vectors",
      "function": "compute_similarity",
      "input": {
        "vector_a": [1, 0, 0],
        "vector_b": [1, 0, 0]
      },
      "expected": {
        "cosine_similarity": 1.0
      }
    },
    {
      "name": "orthogonal_vectors",
      "function": "compute_similarity",
      "input": {
        "vector_a": [1, 0, 0],
        "vector_b": [0, 1, 0]
      },
      "expected": {
        "cosine_similarity": 0.0
      }
    },
    {
      "name": "high_coherence_cluster_3_vectors",
      "function": "compute_similarity_matrix",
      "input": {
        "vectors": [
          [0.5, 0.3, 0.1, 0.1],
          [0.4, 0.35, 0.15, 0.1],
          [0.45, 0.28, 0.12, 0.15]
        ],
        "vector_ids": ["grain_42", "grain_137", "grain_89"]
      },
      "expected": {
        "n_vectors": 3,
        "statistics": {
          "mean_similarity_min": 0.70,
          "max_similarity_min": 0.90
        }
      }
    },
    {
      "name": "knn_find_neighbors",
      "function": "compute_vector_neighbors",
      "input": {
        "query_vector": [1, 0, 0, 0],
        "vectors": [
          [1, 0, 0, 0],
          [0.7, 0.3, 0, 0],
          [0, 1, 0, 0],
          [0, 0, 1, 0],
          [0, 0, 0, 1]
        ],
        "vector_ids": ["v0", "v1", "v2", "v3", "v4"],
        "top_k": 3
      },
      "expected": {
        "neighbors_count": 3,
        "rank_1_id": "v0",
        "rank_1_similarity": 1.0,
        "rank_2_id": "v1",
        "rank_2_similarity_approx": 0.7
      }
    }
  ]
}
```

---

## Non-Goals

- ❌ Other distance metrics (Euclidean, Manhattan, Hamming)
- ❌ Dimensionality reduction (PCA, UMAP, t-SNE)
- ❌ Clustering algorithms (k-means, hierarchical clustering)
- ❌ Neural embeddings or semantic interpretation
- ❌ Visualization or rendering

---

## Dependencies

| Package | Version | Purpose | Notes |
|---------|---------|---------|-------|
| stdlib | — | json, math, collections | No external deps |

**No external libraries needed. Pure Python stdlib.**

---

## Future Enhancements (Post-1.0)

1. **v1.1: Sparse vector support** — Optimize for high-dimensional sparse vectors (stop words, etc.)
2. **v1.2: Batch normalization** — Pre-normalize large vector collections for efficiency
3. **v2.0: Other metrics** — Euclidean distance, Manhattan, Jaccard similarity
4. **v2.0: Dimensionality reduction** — PCA-based analysis of high-D vector spaces
5. **v2.1: Clustering wrapper** — Use cosine similarity matrix as input to k-means/hierarchical

---

**Last updated:** 2026-07-14  
**Author:** Isaac (Kitbash AI)  
**For:** tools/ ecosystem, Sleep Tier 2 validation, Stage 5 procedural edge extraction  
**Related:** PATTERN_CONFIDENCE_SCORER_SPEC.md, ANOMALY_SCORER_SPEC.md, SLEEP_METABOLISM_SPEC.md
