"""tools.neighborhood_projection package.

Library (functions return JSON-serializable dicts):
    from tools.neighborhood_projection import (
        project_neighborhood, project_neighborhood_bidirectional,
        filter_neighborhood, rank_neighborhood_by_weight, explain_path,
    )
"""
from .core import (
    explain_path,
    filter_neighborhood,
    project_neighborhood,
    project_neighborhood_bidirectional,
    rank_neighborhood_by_weight,
)
from .neighborhood_schema import (
    AggregatedStats,
    NeighborhoodEdge,
    NeighborhoodNode,
    NeighborhoodResult,
    PathExplanation,
)

__all__ = [
    "project_neighborhood", "project_neighborhood_bidirectional",
    "filter_neighborhood", "rank_neighborhood_by_weight", "explain_path",
    "NeighborhoodNode", "NeighborhoodEdge", "AggregatedStats",
    "NeighborhoodResult", "PathExplanation",
]
