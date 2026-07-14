# cosine_similarity

Compute cosine similarity between vectors (lists or TF-IDF dicts) to quantify
semantic/structural similarity. Validates collision-cluster coherence, extracts
procedural edge weights, analyzes grain embedding space — no neural models.
Pure stdlib (`json`, `math`, `collections`).

## Functions

| Function | Purpose |
|----------|---------|
| `compute_similarity(a, b, normalize=True)` | Single pair cosine similarity |
| `compute_similarity_matrix(vectors, vector_ids=None, normalize=True)` | N×N symmetric matrix + stats |
| `compute_vector_neighbors(query, vectors, vector_ids=None, top_k=5)` | k-NN by cosine |
| `compare_vector_sets(a, b, vector_ids_a=None, vector_ids_b=None)` | M×N cross-set matrix |

All return JSON-serializable dicts. Statistics (mean/std/min/max/percentiles) are
computed over **off-diagonal** elements only. Diagonal is always 1.0.

## Interpretation (per SPEC)

- `>= 0.9` very_high · `>= 0.7` high · `>= 0.3` medium · `>= 0.0` low · else very_low
- Outlier flag (k-NN): `max neighbor similarity < 0.6` (TEST `knn_find_neighbors_low_similarity_all` asserts outlier at mean 0.5).

## Errors

- `ValueError` (exit 1): mismatched dimensions, non-numeric, zero-magnitude (undefined), <2 vectors, `vector_ids` length mismatch, `top_k > N`.
- `RuntimeError` (exit 2): file I/O or parse failure.

## Usage

```bash
python -m tools.cosine_similarity compute-pair --vector-a "[0.5,0.3,0.1,0,0.1]" --vector-b "[0.4,0.2,0.15,0.05,0.2]"
python -m tools.cosine_similarity compute-matrix --vectors vectors.json --vector-ids ids.json
python -m tools.cosine_similarity compute-neighbors --query-vector q.json --vectors v.json --top-k 5
python -m tools.cosine_similarity compare-sets --vectors-a a.json --vectors-b b.json
```

Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.

**Spec:** `SPEC-cosine_similarity_v1.md` · **Test:** `TEST-cosine_similarity_examples.json`
