"""Dataclasses mirroring tools.cosine_similarity JSON output (documentation)."""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class SimilarityResult:
    cosine_similarity: float
    dot_product: float
    magnitude_a: float
    magnitude_b: float
    interpretation: str


@dataclass
class PairwiseStats:
    mean_similarity: float
    std_similarity: float
    min_similarity: float
    max_similarity: float
    percentiles: Dict[str, float]


@dataclass
class SimilarityMatrix:
    n_vectors: int
    vector_dimension: int
    normalized: bool
    similarity_matrix: List[List[float]]
    statistics: PairwiseStats
    highest_similarity_pairs: List[Dict[str, Any]]
    lowest_similarity_pairs: List[Dict[str, Any]]


@dataclass
class Neighbor:
    rank: int
    vector_id: str
    similarity: float
    interpretation: str


@dataclass
class NeighborsResult:
    query_vector_id: str
    top_k: int
    neighbors: List[Neighbor]
    statistics: Dict[str, Any]
