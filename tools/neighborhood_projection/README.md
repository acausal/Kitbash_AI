# neighborhood_projection

Local-neighborhood projection over a procedural edge graph (v1). Feeds the
post-1.0 sleep-pipeline Tier-2 context expansion and query-time debugging:
given seed node(s), returns reachable neighbors weighted by cumulative edge
strength (product of edge weights along the path). Lightweight BFS with depth +
strength filtering. Isolation-first tool (stdlib only + optional
`structured_logger`); read-only over an edge-graph snapshot.

## Library

```python
from tools.neighborhood_projection import (
    project_neighborhood, project_neighborhood_bidirectional,
    filter_neighborhood, rank_neighborhood_by_weight, explain_path,
)

nb = project_neighborhood(edge_graph, ["fact_123"], depth_limit=2, strength_threshold=0.0)
bi = project_neighborhood_bidirectional(edge_graph, ["fact_123"], depth_limit=2)
flt = filter_neighborhood(nb, min_strength=0.6, min_degree=1)
rank = rank_neighborhood_by_weight(nb, sort_order="descending")
path = explain_path(edge_graph, "fact_123", "fact_456")
```

Every function returns a **plain JSON-serializable dict**. Path weights are
**multiplicative** (favor short, high-confidence paths); a 0.0 edge breaks a path.

### Node metadata is DERIVED (no node registry)

The edge graph stores only edges + `cartridge_index` — there is no node table.
`node_type` and `cartridge` are inferred by scanning the edges a node appears in:

- **node_type**: `"fact"` if it appears as `*_fact_id`, `"grain"` if `*_grain_id`
  (fact wins on inconsistency), else `"unknown"`.
- **cartridge**: most frequently observed `source_cartridge`/`target_cartridge`;
  ties broken alphabetically; `null` if never observed.

## CLI

Multi-command; reads a JSON object from **stdin**, writes JSON to **stdout**:

```bash
echo '{"edge_graph": {...}, "seed_nodes": ["fact_123"], "depth_limit": 2, "strength_threshold": 0.0}' \
  | python -m tools.neighborhood_projection project_neighborhood
echo '{"edge_graph": {...}, "seed_nodes": ["fact_123"], "depth_limit": 2}' \
  | python -m tools.neighborhood_projection project_neighborhood_bidirectional
echo '{"neighborhood": {...}, "min_strength": 0.6, "min_degree": 1}' \
  | python -m tools.neighborhood_projection filter_neighborhood
echo '{"neighborhood": {...}, "sort_order": "descending"}' \
  | python -m tools.neighborhood_projection rank_neighborhood_by_weight
echo '{"edge_graph": {...}, "source_node": "fact_123", "target_node": "fact_456"}' \
  | python -m tools.neighborhood_projection explain_path
```

**Exit codes:** `0` success · `1` invalid input (`ValueError`/bad JSON) · `2` malformed graph (`RuntimeError`).

## Edge graph schema (input)

```json
{
  "edges": {
    "fact_123→fact_456": {
      "source_fact_id": "fact_123", "target_fact_id": "fact_456",
      "source_cartridge": "memories", "target_cartridge": "memories",
      "edge_type": "intra_cartridge", "edge_weight": 0.85,
      "traversal_count": 5, "last_traversed": "2026-07-14T18:30:45Z"
    }
  },
  "cartridge_index": {"memories": ["fact_123", "fact_456"]}
}
```

`explain_path` finds the shortest path within 5 hops; `source == target` yields a
trivial length-0 path. Edges referencing non-existent nodes are skipped.

## Requirements

- Pure stdlib (`json`, `collections`). No new deps.
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.neighborhood_projection ...`
