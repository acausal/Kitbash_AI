# hypergraph_traversal

Traversal over hypergraphs (Historical AI batch). Four deterministic operations,
stdlib-only, stateless, JSON I/O. See `SPEC-hypergraph_traversal_v1.md`.

## Library

```python
from tools.hypergraph_traversal import find_neighbors, find_paths, reachability_analysis, hyperedge_coverage
hg = {"nodes":[{"id":"A"},{"id":"B"},{"id":"C"}],
      "hyperedges":[{"id":"e1","nodes":["A","B"],"weight":1.0},
                    {"id":"e2","nodes":["B","C"]}]}
find_neighbors(hg, "A", max_depth=1)            # B (depth 1)
find_paths(hg, "A", "C", max_length=4)          # [["A","B","C"]]
reachability_analysis(hg, "A")                  # ["B","C"]
hyperedge_coverage(hg, ["A"])                    # covering ["e1"], covered ["A","B"]
```

Operations:
- `find_neighbors(graph, start_node, max_depth=1)` — BFS reach within `max_depth`; returns `{node, depth}`.
- `find_paths(graph, start_node, end_node, max_length=4)` — all **simple** paths (no repeated nodes), sorted by length then lex.
- `reachability_analysis(graph, start_node)` — every node reachable via BFS; `is_fully_connected_from_start`.
- `hyperedge_coverage(graph, nodes)` — hyperedges touching ≥1 target node + the union of their nodes.

## Graph Assumptions (locked defaults)
- **Undirected** by default (`--directed` opt-in). A hyperedge has no inherent order, so it expands to an undirected clique regardless.
- **Weighted** with `1.0` fallback when `weight` omitted (`--unweighted` forces `1.0`).
- **Cycles allowed**, but `find_paths` returns only **simple paths** (no node repetition).
- **Batch** only (single JSON in → single JSON out); no streaming.

## Error modes (→ stderr JSON, exit 1)
empty hypergraph (no hyperedges), node not found, malformed hyperedge (missing/no `nodes` list or unknown node reference), invalid depth/length.

## CLI

```bash
echo '{"nodes":[...],"hyperedges":[...]}' | python -m tools.hypergraph_traversal --neighbors --start A --max-depth 2
python -m tools.hypergraph_traversal --paths --start A --end C --max-length 4 --input hg.json
python -m tools.hypergraph_traversal --reachability --start A
python -m tools.hypergraph_traversal --coverage --nodes A,B
```

Shared boilerplate (config normalize, envelope, CLI/error) lives in
`tools/historical_common.py`. Envelope + shared config apply; exit 0/1/2.

## Post-1.0
This tool will be registered with `ToolRegistry` (see `SPEC_TOOL_REGISTRY_INFRASTRUCTURE.md`)
for grain-topology / causal-chain exploration in Sleep Stage 3. For now, invoked
directly by tests or the sleep pipeline.
