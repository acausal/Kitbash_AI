# SPEC: Hypergraph Traversal v1

> Implemented 2026-07-14 in `tools/hypergraph_traversal/`. Stdlib-only, stateless,
> deterministic, JSON I/O. Conforms to the Historical AI shared contract.

## Status
Implemented.

## Operations (four)
- **find_neighbors** — BFS within `max_depth`; O(Ek). Returns `{node, depth}`.
- **find_paths** — all simple paths start→end up to `max_length`; O(E^length). No repeated nodes.
- **reachability_analysis** — BFS from start over all edges; O(NE). Flags full connectivity.
- **hyperedge_coverage** — hyperedges touching ≥1 target node + union of their nodes; O(E).

## JSON input
`{"nodes":[{"id":...}], "hyperedges":[{"id":..., "nodes":[...], "weight":..., "type":...}]}`.

## Graph defaults (locked)
| Decision | Default | Override | Note |
|----------|---------|----------|------|
| Directionality | Undirected | `--directed` | Hyperedge has no order → expands to undirected clique either way |
| Weighting | Weighted (1.0 fallback) | `--unweighted` | graceful |
| Cycles | Allowed | (n/a) | `find_paths` returns simple paths only |
| Scale | Batch | none | no streaming |

## Error modes
empty hypergraph, node not found, malformed hyperedge, invalid depth/length → `ValueError` → exit 1.

## Use cases
grain topology (3+ way relationships), epistemological-stack reachability, collision detection.

## Non-goals / deferred
No visualization, ML, streaming, custom formats beyond JSON. Registry/sieve_hooks
manifests deferred to post-1.0.
