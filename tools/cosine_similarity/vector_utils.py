"""Vector utilities for tools.cosine_similarity (stdlib only)."""
import math
from typing import List, Union, Dict, Any


def to_dense(vec: Union[List[float], Dict[str, float]]) -> List[float]:
    """Normalize input to a dense list of floats.

    Lists pass through (validated). Dicts (TF-IDF term->weight) are expanded
    against the union of all keys supplied by the caller (see to_dense_union).
    """
    if isinstance(vec, dict):
        return [float(v) for v in vec.values()]
    if not isinstance(vec, (list, tuple)):
        raise ValueError("vector must be a list or dict")
    return [float(x) for x in vec]


def union_keys(vecs: List[Union[List[float], Dict[str, float]]]) -> List[str]:
    """Union of dict keys across vectors (for TF-IDF alignment)."""
    keys = set()
    for v in vecs:
        if isinstance(v, dict):
            keys.update(v.keys())
    return sorted(keys)


def to_dense_union(vec: Union[List[float], Dict[str, float]],
                   keys: List[str]) -> List[float]:
    """Expand one vector to a dense list aligned to `keys` (dicts -> weights)."""
    if isinstance(vec, dict):
        return [float(vec.get(k, 0.0)) for k in keys]
    return to_dense(vec)


def validate_numeric(vec: List[float]) -> None:
    for x in vec:
        if not isinstance(x, (int, float)) or isinstance(x, bool):
            raise ValueError(f"vector contains non-numeric value: {x!r}")


def magnitude(vec: List[float]) -> float:
    return math.sqrt(sum(x * x for x in vec))


def dot_product(a: List[float], b: List[float]) -> float:
    # sparse-friendly: zero terms contribute nothing
    return sum(x * y for x, y in zip(a, b))


def normalize(vec: List[float]) -> List[float]:
    m = magnitude(vec)
    if m == 0.0:
        raise ValueError("cannot normalize zero-magnitude vector")
    return [x / m for x in vec]


def same_dimension(*vecs: List[float]) -> None:
    dims = {len(v) for v in vecs}
    if len(dims) > 1:
        raise ValueError(f"vectors have mismatched dimensions: {sorted(dims)}")
