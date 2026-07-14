"""tools.cosine_similarity package.

Library:
    from tools.cosine_similarity import (
        compute_similarity, compute_similarity_matrix,
        compute_vector_neighbors, compare_vector_sets,
    )

CLI:
    python -m tools.cosine_similarity compute-pair --vector-a "[0.5,0.3,0.1]" --vector-b "[0.4,0.2,0.15]"
    python -m tools.cosine_similarity compute-matrix --vectors vectors.json --vector-ids ids.json
    python -m tools.cosine_similarity compute-neighbors --query-vector q.json --vectors v.json --top-k 5
    python -m tools.cosine_similarity compare-sets --vectors-a a.json --vectors-b b.json

Stdlib only (json, math). Exit codes: 0 success, 1 ValueError, 2 RuntimeError.
"""
from .core import (
    compute_similarity,
    compute_similarity_matrix,
    compute_vector_neighbors,
    compare_vector_sets,
    interpret,
)
from .vector_utils import to_dense, normalize, magnitude, dot_product

__all__ = [
    "compute_similarity",
    "compute_similarity_matrix",
    "compute_vector_neighbors",
    "compare_vector_sets",
    "interpret",
    "to_dense",
    "normalize",
    "magnitude",
    "dot_product",
]
