"""tools.cosine_similarity core: deterministic cosine math (stdlib only).

Functions:
  compute_similarity(vector_a, vector_b, normalize=True)
  compute_similarity_matrix(vectors, vector_ids=None, normalize=True)
  compute_vector_neighbors(query_vector, vectors, vector_ids=None, top_k=5)
  compare_vector_sets(vectors_a, vectors_b, vector_ids_a=None, vector_ids_b=None)

No numpy; pure math. Vectors may be lists of floats or TF-IDF dicts.
"""
from typing import Dict, List, Optional, Union

from . import vector_utils as V
from . import matrix_stats as M


def interpret(sim: float) -> str:
    """Map a cosine similarity score to a coarse label (SPEC fn thresholds)."""
    if sim >= 0.7:
        return "high_similarity"
    if sim >= 0.3:
        return "medium_similarity"
    return "low_similarity"


def _prepare(a: Union[List[float], Dict[str, float]],
             b: Union[List[float], Dict[str, float]],
             normalize: bool):
    """Return aligned dense vectors (a, b) ready for dot/magnitude."""
    keys = V.union_keys([a, b])
    da = V.to_dense_union(a, keys)
    db = V.to_dense_union(b, keys)
    V.validate_numeric(da)
    V.validate_numeric(db)
    V.same_dimension(da, db)
    if normalize:
        da = V.normalize(da)
        db = V.normalize(db)
    return da, db


def compute_similarity(vector_a, vector_b, normalize: bool = True) -> dict:
    a, b = _prepare(vector_a, vector_b, normalize)
    ma = V.magnitude(a)
    mb = V.magnitude(b)
    if ma == 0.0 or mb == 0.0:
        raise ValueError("zero-magnitude vector: cosine similarity undefined")
    dot = V.dot_product(a, b)
    sim = dot / (ma * mb)
    # clamp to [-1, 1] for floating point safety
    sim = max(-1.0, min(1.0, sim))
    return {
        "similarity_computation": {
            "vector_a_dimension": len(a),
            "vector_b_dimension": len(b),
            "normalized": bool(normalize),
        },
        "result": {
            "cosine_similarity": round(sim, 6),
            "dot_product": round(dot, 6),
            "magnitude_a": round(ma, 6),
            "magnitude_b": round(mb, 6),
            "interpretation": interpret(sim),
        },
    }


def _ids(ids: Optional[List[str]], n: int) -> List[str]:
    if ids is not None:
        if len(ids) != n:
            raise ValueError("vector_ids length must match number of vectors")
        return list(ids)
    return [f"v{i}" for i in range(n)]


def compute_similarity_matrix(vectors: List, vector_ids: Optional[List[str]] = None,
                              normalize: bool = True) -> dict:
    if not isinstance(vectors, list) or len(vectors) < 2:
        raise ValueError("compute_similarity_matrix requires >= 2 vectors")
    dense = []
    keys = V.union_keys(vectors)
    for v in vectors:
        dv = V.to_dense_union(v, keys)
        V.validate_numeric(dv)
        dense.append(dv)
    V.same_dimension(*dense)
    ids = _ids(vector_ids, len(dense))
    n = len(dense)
    if normalize:
        dense = [V.normalize(v) for v in dense]

    matrix = [[1.0] * n for _ in range(n)]
    off_diag = []
    for i in range(n):
        mi = V.magnitude(dense[i])
        if mi == 0.0:
            raise ValueError("zero-magnitude vector in matrix: cosine undefined")
        for j in range(i + 1, n):
            mj = V.magnitude(dense[j])
            sim = V.dot_product(dense[i], dense[j]) / (mi * mj)
            sim = max(-1.0, min(1.0, sim))
            sim = round(sim, 6)
            matrix[i][j] = sim
            matrix[j][i] = sim
            off_diag.append(sim)

    stats = {
        "mean_similarity": round(M.mean(off_diag), 6),
        "std_similarity": round(M.std(off_diag), 6),
        "min_similarity": round(min(off_diag), 6) if off_diag else 1.0,
        "max_similarity": round(max(off_diag), 6) if off_diag else 1.0,
        "percentiles": M.percentiles(off_diag),
    }

    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append({"pair": [ids[i], ids[j]], "similarity": matrix[i][j]})
    pairs_sorted = sorted(pairs, key=lambda p: p["similarity"], reverse=True)
    highest = [dict(p, interpretation=interpret(p["similarity"])) for p in pairs_sorted[:5]]
    lowest = [dict(p, interpretation=interpret(p["similarity"]))
              for p in sorted(pairs, key=lambda p: p["similarity"])[:5]]

    return {
        "n_vectors": n,
        "matrix_params": {
            "n_vectors": n,
            "vector_dimension": len(dense[0]),
            "normalized": bool(normalize),
        },
        "vector_ids": ids,
        "similarity_matrix": matrix,
        "statistics": stats,
        "highest_similarity_pairs": highest,
        "lowest_similarity_pairs": lowest,
    }


def compute_vector_neighbors(query_vector, vectors: List, vector_ids: Optional[List[str]] = None,
                             top_k: int = 5) -> dict:
    if not isinstance(vectors, list) or len(vectors) == 0:
        raise ValueError("vectors must be a non-empty list")
    if top_k > len(vectors):
        raise ValueError("top_k cannot exceed number of candidate vectors")
    keys = V.union_keys([query_vector] + vectors)
    q = V.to_dense_union(query_vector, keys)
    V.validate_numeric(q)
    if V.magnitude(q) == 0.0:
        raise ValueError("zero-magnitude query vector: cosine undefined")
    qn = V.normalize(q)
    cands = []
    ids = _ids(vector_ids, len(vectors))
    for idx, v in enumerate(vectors):
        dv = V.to_dense_union(v, keys)
        V.validate_numeric(dv)
        cnorm = V.normalize(dv)
        sim = V.dot_product(qn, cnorm)
        sim = max(-1.0, min(1.0, sim))
        cands.append((ids[idx], round(sim, 6)))
    cands.sort(key=lambda t: t[1], reverse=True)
    top = cands[:top_k]
    neighbors = [{
        "rank": i + 1,
        "vector_id": vid,
        "similarity": sim,
        "interpretation": interpret(sim),
    } for i, (vid, sim) in enumerate(top)]
    sims = [s for _, s in top]
    max_sim = max(sims) if sims else 0.0
    return {
        "query_vector_id": "query_grain",
        "top_k": top_k,
        "neighbors": neighbors,
        "statistics": {
            "mean_neighbor_similarity": round(M.mean(sims), 6),
            "std_neighbor_similarity": round(M.std(sims), 6),
            "query_vector_is_outlier": bool(max_sim < 0.6),
        },
    }


def compare_vector_sets(vectors_a: List, vectors_b: List,
                        vector_ids_a: Optional[List[str]] = None,
                        vector_ids_b: Optional[List[str]] = None) -> dict:
    if not vectors_a or not vectors_b:
        raise ValueError("both sets must be non-empty")
    keys = V.union_keys(vectors_a + vectors_b)
    da = [V.to_dense_union(v, keys) for v in vectors_a]
    db = [V.to_dense_union(v, keys) for v in vectors_b]
    for v in da + db:
        V.validate_numeric(v)
    V.same_dimension(*(da + db))
    ida = _ids(vector_ids_a, len(da))
    idb = _ids(vector_ids_b, len(db))
    na = [V.normalize(v) for v in da]
    nb = [V.normalize(v) for v in db]
    cross = []
    for i in range(len(na)):
        mi = V.magnitude(na[i])
        if mi == 0.0:
            raise ValueError("zero-magnitude vector in set A: cosine undefined")
        row = []
        for j in range(len(nb)):
            mj = V.magnitude(nb[j])
            if mj == 0.0:
                raise ValueError("zero-magnitude vector in set B: cosine undefined")
            sim = V.dot_product(na[i], nb[j]) / (mi * mj)
            sim = max(-1.0, min(1.0, sim))
            row.append(round(sim, 6))
        cross.append(row)
    flat = [x for row in cross for x in row]
    closest = []
    for i in range(len(na)):
        for j in range(len(nb)):
            closest.append({"from": ida[i], "to": idb[j], "similarity": cross[i][j]})
    closest = sorted(closest, key=lambda p: p["similarity"], reverse=True)[:5]
    return {
        "set_a": {"n_vectors": len(da), "vector_ids": ida},
        "set_b": {"n_vectors": len(db), "vector_ids": idb},
        "cross_set_similarity_matrix": cross,
        "statistics": {
            "mean_cross_similarity": round(M.mean(flat), 6),
            "std_cross_similarity": round(M.std(flat), 6),
            "max_similarity": round(max(flat), 6) if flat else 0.0,
            "min_similarity": round(min(flat), 6) if flat else 0.0,
        },
        "closest_pairs": closest,
    }
