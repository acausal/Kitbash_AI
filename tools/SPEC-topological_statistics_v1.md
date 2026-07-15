# SPEC: Topological Statistics v1

> Implemented 2026-07-14 in `tools/topological_statistics/`. Stdlib-only, stateless,
> deterministic, JSON I/O. Conforms to the Historical AI shared contract.

## Status
Implemented.

## Operations (five)
- **compute_degree_stats** — per-node degree + mean/max/min/distribution. O(E).
- **compute_clustering_coefficients** — local CC; mean. O(E^1.5)-ish.
- **compute_path_lengths** — all-pairs shortest-path (BFS hop-based) lengths; mean + diameter + distribution. O(N·E).
- **compute_centrality** — degree (normalized), closeness, betweenness (Brandes), eigenvector (power iteration).
- **analyze_components** — connected components, sizes, largest, isolated nodes. O(N+E).

## JSON input
`{"nodes":[{"id":...}], "edges":[{"source":..., "target":..., "weight":...}]}` (also accepts `nodes:[a,b]`).

## Graph defaults (locked)
| Decision | Default | Override | Note |
|----------|---------|----------|------|
| Directionality | Undirected | `--directed` | edge added both ways |
| Weighting | Weighted (1.0 fallback) | `--unweighted` | weights feed weighted degree; **path metrics are hop-based** |
| Cycles | Allowed | (n/a) | |
| Scale | Batch | none | no streaming |

## Complexity (as specified)
Degree O(E); clustering O(E^1.5); paths/betweenness O(N·E); components O(N+E).

## Error modes
empty graph, malformed edge → `ValueError` → exit 1.

## Use cases
Sleep Stage 2 anomaly detection (topological features), graph summarization.

## Non-goals / deferred
No visualization, ML, streaming, 100K+ approximations, weighted shortest paths, custom
distance metrics. Registry/sieve_hooks manifests deferred to post-1.0.
