"""tools.tfidf_ranker scoring helpers (stdlib only).

Secondary scoring utilities listed in the SPEC module layout: TF-IDF vector
construction for a single query and sparse-vector norms. Core ranking lives in
core.py.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence


def vector_norm(vec: Dict[str, float]) -> float:
    import math
    return math.sqrt(sum(v * v for v in vec.values()))


def query_vector(query_tokens: Sequence[str], idf: Dict[str, float],
                 variant: str = "standard") -> Dict[str, float]:
    """Build a TF-IDF query vector given a precomputed idf table.

    Mirrors core._tf_weight for 'standard'/'sublinear' (bm25 handled separately
    in core.rank_documents).
    """
    import math
    from collections import Counter
    tf = Counter(query_tokens)
    out = {}
    for t, f in tf.items():
        if variant == "sublinear":
            tw = 1.0 + math.log(f) if f > 0 else 0.0
        else:
            tw = float(f)
        out[t] = tw * idf.get(t, 0.0)
    return out


__all__ = ["vector_norm", "query_vector"]
