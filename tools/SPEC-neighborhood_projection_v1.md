# SPEC: Neighborhood Projection v1

**Module:** `tools/neighborhood_projection/`  
**Status:** Ready for build  
**Dependencies:** stdlib (json, collections, heapq)  
**Priority:** High (feeds post-1.0 sleep pipeline Tier 2 context expansion; bridges exploratory + infrastructure)

---

## Overview

Given a seed node (or set of nodes) and a procedural edge graph, returns the local neighborhood of related nodes weighted by edge strength. Enables query-time context expansion using learned co-occurrence topology.

**Design principle:** Lightweight BFS/DFS with optional depth and strength filtering. Already embedded in sleep pipeline; exposing as standalone tool for query-time use and debugging.

**Use case:** "When I query about [fact X], what other facts does the system know are reliably co-accessed? Show me ranked by confidence."

---

## Scope

### In Scope ✓
- Query procedural edge graph given seed node ID(s)
- Return local neighborhood (all reachable nodes within depth limit)
- Weight neighbors by cumulative edge strength (path weight product)
- Optional strength threshold (drop weak paths)
- Optional depth limit (BFS/DFS with max hops)
- Aggregate edge metadata (traversal counts, timestamps, edge types)
- Output: JSON with neighborhood nodes, edges, and aggregated stats

### Out of Scope ✗
- Cycle detection or topological sorting
- Shortest path algorithms (dedicated pathfinding tool)
- Performance optimization for massive graphs (assume < 100k nodes)
- Semantic/embedding-based similarity (this is purely topological)
- Graph visualization or rendering
- Dynamic graph updates (read-only over procedural_edge_graph snapshot)

---

## Module Structure

```
tools/neighborhood_projection/
  __init__.py                    # exports main functions
  core.py                        # implementation logic
  cli.py                         # argparse CLI
  neighborhood_schema.py         # dataclasses for JSON output
  README.md                       # usage docs
  __main__.py                    # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

All functions accept/return JSON-serializable types (dicts, lists, strings).

#### 1. `project_neighborhood(edge_graph: dict, seed_nodes: list, depth_limit: int = 2, strength_threshold: float = 0.0) -> dict`

**Purpose:** Project local neighborhood around seed node(s).

**Input:**
- `edge_graph` (dict): Procedural edge graph structure (see **Graph Schema** below)
- `seed_nodes` (list of str): Node IDs to start projection from (e.g., `["fact_123", "fact_456"]`)
- `depth_limit` (int): Maximum hops from seed (default: 2)
- `strength_threshold` (float): Minimum cumulative path weight to include neighbor (default: 0.0, include all)

**Output (JSON):**
```json
{
  "seed_nodes": ["fact_123"],
  "depth_limit": 2,
  "strength_threshold": 0.0,
  "neighborhood": {
    "nodes": {
      "fact_123": {
        "node_id": "fact_123",
        "node_type": "fact",
        "cartridge": "memories",
        "is_seed": true
      },
      "fact_456": {
        "node_id": "fact_456",
        "node_type": "fact",
        "cartridge": "memories",
        "is_seed": false,
        "distance_from_seed": 1,
        "cumulative_path_weight": 0.85,
        "strongest_incoming_edge_weight": 0.85
      }
    },
    "edges": [
      {
        "source": "fact_123",
        "target": "fact_456",
        "edge_weight": 0.85,
        "edge_type": "intra_cartridge",
        "traversal_count": 5,
        "last_traversed": "2026-07-14T12:30:45Z"
      }
    ]
  },
  "aggregated_stats": {
    "total_nodes_in_neighborhood": 3,
    "total_edges_in_neighborhood": 2,
    "avg_edge_weight": 0.82,
    "depth_distribution": {
      "depth_0": 1,
      "depth_1": 2,
      "depth_2": 0
    },
    "edge_types": {
      "intra_cartridge": 2,
      "cross_cartridge": 0
    },
    "cartridges_touched": ["memories"]
  },
  "projection_params": {
    "depth_limit": 2,
    "strength_threshold": 0.0,
    "nodes_filtered_by_threshold": 0
  }
}
```

**Behavior:**
- BFS traversal from seed nodes
- Track cumulative path weight (product of edge weights along path)
- Stop at depth_limit
- Exclude neighbors with cumulative path weight < strength_threshold
- Return all reachable nodes + edges + aggregated statistics

**Error handling:**
- `ValueError` if seed_nodes is empty or contains invalid node IDs
- `ValueError` if strength_threshold is not in [0.0, 1.0]
- `ValueError` if depth_limit is negative
- `RuntimeError` if edge_graph is malformed (missing required fields)

---

#### 2. `project_neighborhood_bidirectional(edge_graph: dict, seed_nodes: list, depth_limit: int = 2, strength_threshold: float = 0.0) -> dict`

**Purpose:** Project neighborhood in both directions (incoming + outgoing edges).

**Input:**
- Same as `project_neighborhood`

**Output (JSON):**
```json
{
  "seed_nodes": ["fact_123"],
  "direction": "bidirectional",
  "neighborhood": {
    "nodes": { /* same structure */ },
    "edges": [
      {
        "source": "fact_123",
        "target": "fact_456",
        "direction": "outgoing",
        "edge_weight": 0.85,
        /* ... */
      },
      {
        "source": "fact_890",
        "target": "fact_123",
        "direction": "incoming",
        "edge_weight": 0.72,
        /* ... */
      }
    ]
  },
  "aggregated_stats": {
    "total_nodes": 4,
    "total_edges": 3,
    "incoming_edges": 1,
    "outgoing_edges": 2,
    /* ... rest of stats ... */
  }
}
```

**Behavior:**
- Traverse both incoming and outgoing edges from seed nodes
- Mark each edge with `"direction": "incoming"` or `"outgoing"`
- Otherwise identical to unidirectional projection

---

#### 3. `filter_neighborhood(neighborhood: dict, min_strength: float, min_degree: int = 1) -> dict`

**Purpose:** Filter neighborhood after projection (e.g., remove low-confidence or isolated nodes).

**Input:**
- `neighborhood` (dict): Output from `project_neighborhood`
- `min_strength` (float): Minimum cumulative path weight for nodes (0.0–1.0)
- `min_degree` (int): Minimum number of edges (incoming + outgoing) to keep node (default: 1)

**Output (JSON):**
Same structure as `project_neighborhood`, but with nodes/edges pruned.

**Behavior:**
- Remove nodes where `cumulative_path_weight < min_strength`
- Remove nodes where degree < min_degree
- Remove edges involving removed nodes
- Recalculate aggregated_stats

**Error handling:**
- `ValueError` if min_strength is not in [0.0, 1.0]
- `ValueError` if neighborhood structure is invalid

---

#### 4. `rank_neighborhood_by_weight(neighborhood: dict, sort_order: str = "descending") -> dict`

**Purpose:** Return neighborhood nodes ranked by cumulative path weight.

**Input:**
- `neighborhood` (dict): Output from `project_neighborhood`
- `sort_order` (str): `"ascending"` or `"descending"` (default: `"descending"`)

**Output (JSON):**
```json
{
  "ranked_nodes": [
    {
      "node_id": "fact_456",
      "cumulative_path_weight": 0.85,
      "distance_from_seed": 1,
      "rank": 1
    },
    {
      "node_id": "fact_789",
      "cumulative_path_weight": 0.72,
      "distance_from_seed": 2,
      "rank": 2
    }
  ],
  "original_seed_nodes": ["fact_123"]
}
```

---

#### 5. `explain_path(edge_graph: dict, source_node: str, target_node: str) -> dict`

**Purpose:** Trace a path from source to target in the edge graph (if one exists within reasonable bounds).

**Input:**
- `edge_graph` (dict): Procedural edge graph
- `source_node` (str): Starting node ID
- `target_node` (str): Target node ID

**Output (JSON):**
```json
{
  "source": "fact_123",
  "target": "fact_456",
  "path_found": true,
  "path": [
    {
      "node_id": "fact_123",
      "step": 0
    },
    {
      "node_id": "fact_789",
      "step": 1
    },
    {
      "node_id": "fact_456",
      "step": 2
    }
  ],
  "path_length": 2,
  "cumulative_weight": 0.72,
  "edges_traversed": [
    {
      "source": "fact_123",
      "target": "fact_789",
      "edge_weight": 0.85
    },
    {
      "source": "fact_789",
      "target": "fact_456",
      "edge_weight": 0.85
    }
  ]
}
```

**Behavior:**
- BFS to find shortest path from source to target (within depth 5 hops)
- Return path (nodes + edges) and cumulative weight
- If no path exists, return `"path_found": false`

**Error handling:**
- `ValueError` if source_node or target_node not in graph
- `RuntimeError` if edge_graph is malformed

---

### CLI Interface (in `cli.py`)

All commands read input from stdin (JSON) or CLI arguments; output to stdout (JSON).

```bash
# Project neighborhood around single seed
echo '{
  "edge_graph": { /* full edge graph JSON */ },
  "seed_nodes": ["fact_123"],
  "depth_limit": 2,
  "strength_threshold": 0.0
}' | python -m tools.neighborhood_projection project_neighborhood

# Project bidirectional neighborhood
echo '{
  "edge_graph": { /* ... */ },
  "seed_nodes": ["fact_123"],
  "depth_limit": 2
}' | python -m tools.neighborhood_projection project_neighborhood_bidirectional

# Filter neighborhood
echo '{
  "neighborhood": { /* from project_neighborhood */ },
  "min_strength": 0.6,
  "min_degree": 1
}' | python -m tools.neighborhood_projection filter_neighborhood

# Rank by weight
echo '{
  "neighborhood": { /* from project_neighborhood */ },
  "sort_order": "descending"
}' | python -m tools.neighborhood_projection rank_neighborhood_by_weight

# Explain path between nodes
echo '{
  "edge_graph": { /* ... */ },
  "source_node": "fact_123",
  "target_node": "fact_456"
}' | python -m tools.neighborhood_projection explain_path
```

**Exit codes:**
- `0` → success
- `1` → invalid input (ValueError)
- `2` → internal error (RuntimeError)

---

### Schema (in `neighborhood_schema.py`)

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

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
    direction: Optional[str] = None  # "incoming" or "outgoing" for bidirectional

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
```

---

## Procedural Edge Graph Schema

The tool expects the edge_graph input to have this structure (from sleep pipeline):

```json
{
  "metadata": {
    "created_at": "2026-07-14T12:30:45Z",
    "stages_applied": ["1.5", "2.5"],
    "total_edges": 100,
    "intra_cartridge_edges": 80,
    "cross_cartridge_edges": 20,
    "last_updated": "2026-07-14T18:30:45Z"
  },
  "edges": {
    "fact_123→fact_456": {
      "source_fact_id": "fact_123",
      "target_fact_id": "fact_456",
      "source_cartridge": "memories",
      "target_cartridge": "memories",
      "edge_type": "intra_cartridge",
      "edge_weight": 0.85,
      "traversal_count": 5,
      "confidence_mutable": true,
      "first_traversed": "2026-07-10T10:00:00Z",
      "last_traversed": "2026-07-14T18:30:45Z"
    },
    /* ... more edges ... */
  },
  "cartridge_index": {
    "memories": ["fact_123", "fact_456", "fact_789"],
    "knowledge": ["fact_001", "fact_002"]
  }
}
```

**Key fields:**
- `edges`: Dict mapping `"source→target"` to edge objects
- `edge_weight` (float, 0.0–1.0): Confidence/strength of relationship
- `edge_type` (str): `"intra_cartridge"` or `"cross_cartridge"`
- `traversal_count` (int): How many times this edge was traversed
- `source_cartridge` / `target_cartridge` (str): Domain membership

---

## Error Handling

**Unified error taxonomy:**
- `FileNotFoundError` — not applicable (no file I/O)
- `ValueError` — invalid inputs (empty seed_nodes, invalid thresholds, unrecognized nodes, malformed neighborhood)
- `RuntimeError` — graph structure errors (missing required fields, broken edges)
- `IOError` — not applicable (no file I/O)

**Logging:**
- Use `structured_logger.get_event_logger("neighborhood_projection")`
- Log events: `projection_started`, `projection_complete`, `projection_failed`
- Metadata: seed_nodes, depth_limit, nodes_found, edges_found, execution_time_ms

---

## Test Cases

### Happy Path
1. Single seed node, depth 1 → returns direct neighbors only
2. Single seed node, depth 2 → returns 1-hop and 2-hop neighbors
3. Multiple seed nodes → returns neighborhood around all seeds (union)
4. Strength threshold 0.5 → excludes paths with cumulative weight < 0.5
5. Bidirectional projection → includes both incoming and outgoing edges
6. Filter by min_strength 0.6 → removes low-confidence nodes
7. Filter by min_degree 2 → keeps only nodes with ≥2 edges
8. Rank by weight (descending) → highest confidence nodes first
9. Rank by weight (ascending) → lowest confidence nodes first
10. Path exists (A→B→C) → returns path with correct edges and cumulative weight
11. Path with multiple routes → returns shortest path (fewest hops)

### Edge Cases
12. Single node graph (no edges) → projection returns just seed node
13. Disconnected graph (seed has no neighbors) → returns only seed node
14. Depth 0 (only seed) → returns only seed node, no neighbors
15. Strength threshold 0.0 (include all) → no nodes filtered
16. Strength threshold 1.0 (only direct edge 1.0) → only adjacent 1.0-weight edges
17. Node appears at multiple depths → uses shortest distance in output
18. Bidirectional with asymmetric edges → correctly marks direction
19. No path exists between two nodes → `"path_found": false`
20. Path to self (source == target) → returns trivial path of length 0

### Error Cases
21. Empty seed_nodes list → `ValueError`
22. Seed node not in graph → `ValueError` (or silent if allow-missing-seeds flag)
23. Invalid strength_threshold (< 0.0 or > 1.0) → `ValueError`
24. Invalid depth_limit (negative) → `ValueError`
25. Malformed edge_graph (missing "edges" key) → `RuntimeError`
26. Edge references non-existent node → handled gracefully (skip edge or warn)
27. Invalid sort_order → `ValueError`
28. Empty neighborhood dict to filter → returns empty output

### CLI Behavior
29. CLI exit code 0 on success
30. CLI exit code 1 on ValueError (bad input)
31. CLI exit code 2 on RuntimeError (bad graph)
32. CLI reads valid JSON from stdin and outputs valid JSON
33. CLI with invalid JSON input → `ValueError` (JSON parse failure)

---

## Implementation Notes

### BFS Traversal
- Use standard BFS queue (collections.deque)
- Track visited nodes to avoid revisiting
- Maintain distance_from_seed and cumulative_path_weight for each node
- Stop when depth_limit reached

### Path Weight Calculation
- Cumulative weight = product of edge weights along path (multiplicative)
- If any edge weight is 0.0, cumulative weight becomes 0.0 (strong break)
- Alternative: sum of edge weights (additive) — choose multiplicative to favor short, high-confidence paths

### Bidirectional Traversal
- Maintain two separate edge lists: incoming, outgoing
- For each edge in graph, check both directions
- Mark direction on edge object for clarity in output

### Performance
- Assume graph < 100k nodes; linear-time BFS acceptable
- No fancy indexing; iterate edges list for each neighbor lookup
- Cache result if depth_limit and strength_threshold are stable (optional, post-v1)

### Cartridge Indexing
- Use `cartridge_index` from edge_graph to detect cartridge boundaries
- Helpful for filtering neighborhood by domain ("give me only neighbors in cartridge X")
- Optional feature; can add in v2 if needed

---

## Success Criteria

- ✅ All 33 test cases pass (manually verified with terminal output)
- ✅ CLI exit codes correct (0, 1, 2)
- ✅ JSON output validated against schema (fields present, types correct)
- ✅ BFS traversal logic correct (respects depth_limit, applies strength_threshold)
- ✅ Bidirectional mode correctly marks edge directions
- ✅ Path explanation algorithm finds shortest path
- ✅ Aggregated stats accurately reflect neighborhood (correct counts, distributions)
- ✅ Error messages clear and actionable
- ✅ Errors logged via structured_logger
- ✅ README documents all functions, examples, and edge cases

---

## Non-Goals (Explicitly Out of Scope)

- Cycle detection or topological sorting
- Shortest-path optimization (Dijkstra, A*)
- Graph visualization or rendering
- Semantic similarity (this is purely learned co-occurrence topology)
- Dynamic graph updates (snapshot-based, read-only)
- Massive graph optimization (assumes < 100k nodes)
- Constraint satisfaction or complex queries
- Multi-hop reasoning (keeps paths simple, leaves reasoning to orchestrator)

---

**Last updated:** 2026-07-14  
**Prepared by:** Claude  
**Status:** Ready for Hermes build
