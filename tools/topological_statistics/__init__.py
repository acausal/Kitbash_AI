"""tools.topological_statistics — graph stats over node/edge graphs (see SPEC).

Public API: compute_degree_stats, compute_clustering_coefficients, compute_path_lengths,
compute_centrality (degree/closeness/betweenness/eigenvector), analyze_components.
Stateless, deterministic, stdlib-only.
"""
from __future__ import annotations

from .core import (
    compute_degree_stats, compute_clustering_coefficients, compute_path_lengths,
    compute_centrality, analyze_components,
)

__all__ = ["compute_degree_stats", "compute_clustering_coefficients",
           "compute_path_lengths", "compute_centrality", "analyze_components"]
