# topological_statistics

Graph statistics over node/edge graphs (Historical AI batch). Five deterministic
operations, stdlib-only, stateless, JSON I/O. See `SPEC-topological_statistics_v1.md`.

## Library

```python
from tools.topological_statistics import (
    compute_degree_stats, compute_clustering_coefficients, compute_path_lengths,
    compute_centrality, analyze_components,
)
g = {"nodes":[{"id":"A"},{"id":"B"},{"id":"C"},{"id":"D"}],
     "edges":[{"source":"A","target":"B"},{"source":"B","target":"C"},
              {"source":"C","target":"D"},{"source":"D","target":"A"}]}
compute_degree_stats(g)              # degrees; mean 2.0
compute_clustering_coefficients(g)   # 0.0 (cycle of 4 has no triangles)
compute_path_lengths(g)              # diameter 2
compute_centrality(g)                # degree/closeness/betweenness/eigenvector
analyze_components(g)                # 1 component (connected)
```

Operations:
- `compute_degree_stats` — per-node degree + mean/max/min/distribution. O(E).
- `compute_clustering_coefficients` — local CC (triangles / k(k−1)); mean. O(E^1.5)-ish.
- `compute_path_lengths` — all-pairs shortest-path (BFS, hop-based) lengths; mean + diameter + distribution. O(N·E).
- `compute_centrality` — degree (normalized), closeness, betweenness (Brandes), eigenvector (power iteration).
- `analyze_components` — connected components, sizes, largest, isolated nodes. O(N+E).

## Graph Assumptions (locked defaults)
- **Undirected** by default (`--directed` opt-in).
- **Weighted** with `1.0` fallback (`--unweighted`); weights feed weighted degree but **path metrics are hop-based** (unweighted) for determinism + the O(N·E) bound. Weighted shortest paths deferred.
- **Cycles allowed**; **batch** only (single JSON in → single JSON out).

## Error modes (→ stderr JSON, exit 1)
empty graph (no nodes), malformed edge (missing source/target or nodes[2], or unknown node reference).

## CLI

```bash
echo '{"nodes":[...],"edges":[...]}' | python -m tools.topological_statistics --degree
python -m tools.topological_statistics --centrality --input g.json
```

Shared boilerplate (config normalize, envelope, CLI/error) lives in
`tools/historical_common.py`. Envelope + shared config apply; exit 0/1/2.

## Post-1.0
This tool will be registered with `ToolRegistry` (see `SPEC_TOOL_REGISTRY_INFRASTRUCTURE.md`)
for Sleep Stage 2 anomaly detection. For now, invoked directly by tests or the pipeline.
