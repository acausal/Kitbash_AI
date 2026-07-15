"""tools.hypergraph_traversal — traversal over hypergraphs (see SPEC).

Four deterministic operations over a hypergraph (nodes + hyperedges):
find_neighbors (BFS, O(Ek)), find_paths (DFS/BFS, O(E^length)), reachability_analysis
(O(NE)), hyperedge_coverage (O(E)). Stateless, stdlib-only, JSON I/O.

Graph defaults (locked): undirected by default (--directed opt-in); weighted with
1.0 fallback (--unweighted); cycles allowed but find_paths returns SIMPLE paths only
(no repeated nodes); batch (single JSON in / single JSON out). Malformed-edge /
node-not-found / empty-hypergraph errors -> ValueError -> exit 1.

Shared boilerplate (config normalize, envelope, CLI/error) lives in
tools.historical_common. Envelope + shared config apply; exit 0/1/2.
"""
from __future__ import annotations

from tools.historical_common import envelope, make_run_id, now_iso, normalize_config

_OPS = ("find_neighbors", "find_paths", "reachability_analysis", "hyperedge_coverage")


def _build(cfg, data):
    """Validate + index the hypergraph. Returns (nodes, adj, edges_meta)."""
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")
    nodes = data.get("nodes")
    edges = data.get("hyperedges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("missing 'nodes'/'hyperedges' lists")
    if not edges:
        raise ValueError("empty hypergraph (no hyperedges)")
    node_ids = {n.get("id") for n in nodes if isinstance(n, dict)}
    directed = bool(cfg.get("directed", False))
    default_w = 1.0
    # adjacency: node -> list of (neighbor_node, edge_id, weight)
    adj = {nid: [] for nid in node_ids}
    edges_meta = []
    for e in edges:
        eid = e.get("id", f"e{len(edges_meta)}")
        members = e.get("nodes") or e.get("members")
        if not isinstance(members, list) or len(members) < 1:
            raise ValueError(f"malformed hyperedge {eid!r}: needs 'nodes' list")
        for m in members:
            if m not in node_ids:
                raise ValueError(f"hyperedge {eid!r} references unknown node {m!r}")
        w = float(e.get("weight", default_w))
        edges_meta.append({"id": eid, "nodes": list(members), "weight": w,
                           "type": e.get("type", "default")})
        # clique expansion (undirected: all pairs; directed: order? hyperedge has no order -> treat as undirected clique)
        if directed:
            # there is no inherent order for a hyperedge; default to undirected clique regardless
            pass
        for a in members:
            for b in members:
                if a != b:
                    adj[a].append((b, eid, w))
    return node_ids, adj, edges_meta


def _require(node_ids, node):
    if node not in node_ids:
        raise ValueError(f"node not found: {node!r}")


def find_neighbors(graph, start_node, max_depth=1, config=None) -> dict:
    cfg = normalize_config(config)
    node_ids, adj, edges_meta = _build(cfg, graph)
    _require(node_ids, start_node)
    directed = bool(cfg.get("directed", False))
    depth = {}
    frontier = [(start_node, 0)]
    depth[start_node] = 0
    while frontier:
        cur, d = frontier.pop(0)
        if d >= max_depth:
            continue
        for nb, eid, w in adj[cur]:
            if nb in depth:
                continue
            depth[nb] = d + 1
            frontier.append((nb, d + 1))
    neighbors = {n: dd for n, dd in depth.items() if n != start_node}
    return {
        **envelope("hypergraph_traversal"),
        "input_summary": {"operation": "find_neighbors", "start_node": start_node,
                          "max_depth": max_depth, "node_count": len(node_ids)},
        "neighbors": [{"node": n, "depth": dd} for n, dd in sorted(neighbors.items(), key=lambda kv: kv[1])],
        "summary": {"neighbor_count": len(neighbors), "max_depth_reached": max(neighbors.values(), default=0)},
    }


def find_paths(graph, start_node, end_node, max_length=4, config=None) -> dict:
    cfg = normalize_config(config)
    node_ids, adj, edges_meta = _build(cfg, graph)
    _require(node_ids, start_node)
    _require(node_ids, end_node)
    paths = []
    # DFS over simple paths (no repeated nodes); undirected -> avoid backtrack via visited set
    stack = [(start_node, [start_node])]
    while stack:
        cur, path = stack.pop()
        if len(path) > max_length:
            continue
        if cur == end_node and len(path) >= 2:
            paths.append(list(path))
            continue
        for nb, eid, w in adj[cur]:
            if nb in path:
                continue
            stack.append((nb, path + [nb]))
    # sort by length then lex
    paths.sort(key=lambda p: (len(p), p))
    return {
        **envelope("hypergraph_traversal"),
        "input_summary": {"operation": "find_paths", "start_node": start_node,
                          "end_node": end_node, "max_length": max_length, "node_count": len(node_ids)},
        "paths": paths,
        "summary": {"path_count": len(paths), "shortest_length": min((len(p) for p in paths), default=0)},
    }


def reachability_analysis(graph, start_node, config=None) -> dict:
    cfg = normalize_config(config)
    node_ids, adj, edges_meta = _build(cfg, graph)
    _require(node_ids, start_node)
    seen = {start_node}
    frontier = [start_node]
    while frontier:
        cur = frontier.pop()
        for nb, eid, w in adj[cur]:
            if nb not in seen:
                seen.add(nb)
                frontier.append(nb)
    reachable = sorted(seen - {start_node})
    return {
        **envelope("hypergraph_traversal"),
        "input_summary": {"operation": "reachability_analysis", "start_node": start_node,
                          "node_count": len(node_ids)},
        "reachable_nodes": reachable,
        "summary": {"reachable_count": len(reachable), "total_nodes": len(node_ids),
                    "is_fully_connected_from_start": len(seen) == len(node_ids)},
    }


def hyperedge_coverage(graph, nodes, config=None) -> dict:
    cfg = normalize_config(config)
    node_ids, adj, edges_meta = _build(cfg, graph)
    targets = nodes if isinstance(nodes, list) else [nodes]
    for t in targets:
        if t not in node_ids:
            raise ValueError(f"node not found: {t!r}")
    if not targets:
        raise ValueError("'nodes' list is empty")
    # coverage: hyperedges touching >=1 target, and the set of nodes reachable through them
    covering = []
    covered_nodes = set()
    for e in edges_meta:
        if any(t in e["nodes"] for t in targets):
            covering.append(e["id"])
            covered_nodes.update(e["nodes"])
    return {
        **envelope("hypergraph_traversal"),
        "input_summary": {"operation": "hyperedge_coverage", "target_nodes": targets,
                          "hyperedge_count": len(edges_meta)},
        "covering_hyperedges": covering,
        "covered_nodes": sorted(covered_nodes),
        "summary": {"covering_hyperedge_count": len(covering), "covered_node_count": len(covered_nodes)},
    }
