"""Dataclasses for tools.neighborhood_projection (see SPEC-neighborhood_projection_v1.md).

These mirror the JSON output shapes. Core functions build plain dicts (per the
SPEC's composability requirement); dataclasses document the contract and can be
used by typed callers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class NeighborhoodNode:
    node_id: str
    node_type: str
    cartridge: Optional[str] = None
    is_seed: bool = False
    distance_from_seed: Optional[int] = None
    cumulative_path_weight: float = 1.0
    strongest_incoming_edge_weight: Optional[float] = None


@dataclass
class NeighborhoodEdge:
    source: str
    target: str
    edge_weight: float
    edge_type: str  # "intra_cartridge" or "cross_cartridge"
    traversal_count: int
    last_traversed: Optional[str] = None
    direction: Optional[str] = None  # "incoming"/"outgoing" for bidirectional


@dataclass
class AggregatedStats:
    total_nodes_in_neighborhood: int
    total_edges_in_neighborhood: int
    avg_edge_weight: float
    depth_distribution: Dict[str, int]
    edge_types: Dict[str, int]
    cartridges_touched: List[str]


@dataclass
class NeighborhoodResult:
    seed_nodes: List[str]
    depth_limit: int
    strength_threshold: float
    neighborhood: Dict[str, Any]  # nodes + edges
    aggregated_stats: AggregatedStats
    projection_params: Dict[str, Any]


@dataclass
class PathExplanation:
    source: str
    target: str
    path_found: bool
    path: List[Dict[str, Any]] = field(default_factory=list)
    path_length: int = 0
    cumulative_weight: float = 0.0
    edges_traversed: List[Dict[str, Any]] = field(default_factory=list)
