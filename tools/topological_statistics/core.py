"""tools.topological_statistics — graph stats over node/edge graphs (see SPEC).

Five deterministic operations: compute_degree_stats, compute_clustering_coefficients,
compute_path_lengths, compute_centrality (degree/closeness/betweenness/eigenvector),
analyze_components. Stateless, stdlib-only, JSON I/O.

Graph defaults (locked): undirected by default (--directed opt-in); weighted with 1.0
fallback (--unweighted); cycles allowed; batch (single JSON in / single JSON out).
Shortest-path metrics are HOP-BASED (unweighted) for determinism + the O(N*E) bound;
edge weights are recorded (and used for weighted degree) but do not alter path metrics.

Shared boilerplate (config normalize, envelope, CLI/error) lives in
tools.historical_common. Envelope + shared config apply; exit 0/1/2.
"""
from __future__ import annotations

import math
from collections import deque

from tools.historical_common import envelope, normalize_config

_OPS = ("compute_degree_stats", "compute_clustering_coefficients",
        "compute_path_lengths", "compute_centrality", "analyze_components")


def _build(cfg, data):
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")
    nodes = data.get("nodes")
    edges = data.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("missing 'nodes'/'edges' lists")
    if not nodes:
        raise ValueError("empty graph (no nodes)")
    node_ids = [n.get("id") for n in nodes if isinstance(n, dict)]
    idset = set(node_ids)
    adj = {nid: {} for nid in node_ids}     # nid -> {neighbor: weight}
    default_w = 1.0
    for e in edges:
        a, b, w = _edge_endpoints(e, idset, default_w)
        adj[a][b] = adj[a].get(b, 0.0) + w
        adj[b][a] = adj[b].get(a, 0.0) + w
    return node_ids, adj


def _edge_endpoints(e, idset, default_w):
    if "source" in e and "target" in e:
        a, b = e["source"], e["target"]
    elif "nodes" in e and isinstance(e["nodes"], list) and len(e["nodes"]) == 2:
        a, b = e["nodes"][0], e["nodes"][1]
    else:
        raise ValueError(f"malformed edge {e!r}: needs source/target or nodes[2]")
    if a not in idset:
        raise ValueError(f"edge references unknown node {a!r}")
    if b not in idset:
        raise ValueError(f"edge references unknown node {b!r}")
    w = float(e.get("weight", default_w))
    return a, b, w


# ---- shortest paths (hop-based BFS, undirected) ----
def _bfs_distances(adj, src):
    dist = {src: 0}
    q = deque([src])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def compute_degree_stats(graph, config=None) -> dict:
    cfg = normalize_config(config)
    node_ids, adj = _build(cfg, graph)
    degrees = {n: len(adj[n]) for n in node_ids}
    vals = list(degrees.values())
    summary = {
        "node_count": len(node_ids),
        "edge_count": sum(vals) // 2,
        "mean_degree": round(sum(vals) / len(vals), 4) if vals else 0.0,
        "max_degree": max(vals) if vals else 0,
        "min_degree": min(vals) if vals else 0,
        "degree_distribution": _distribution(vals),
    }
    return {
        **envelope("topological_statistics"),
        "input_summary": {"operation": "compute_degree_stats", "node_count": len(node_ids)},
        "degrees": degrees,
        "summary": summary,
    }


def compute_clustering_coefficients(graph, config=None) -> dict:
    cfg = normalize_config(config)
    node_ids, adj = _build(cfg, graph)
    coeffs = {}
    for n in node_ids:
        neighbors = list(adj[n])
        k = len(neighbors)
        if k < 2:
            coeffs[n] = 0.0
            continue
        links = 0
        nset = set(neighbors)
        for u in neighbors:
            for v in adj[u]:
                if v in nset and v != u:
                    links += 1
        links //= 2
        coeffs[n] = round(links / (k * (k - 1) / 2), 4)
    vals = list(coeffs.values())
    return {
        **envelope("topological_statistics"),
        "input_summary": {"operation": "compute_clustering_coefficients", "node_count": len(node_ids)},
        "clustering_coefficients": coeffs,
        "summary": {"mean_clustering_coefficient": round(sum(vals) / len(vals), 4) if vals else 0.0},
    }


def compute_path_lengths(graph, config=None) -> dict:
    cfg = normalize_config(config)
    node_ids, adj = _build(cfg, graph)
    all_d = []
    for n in node_ids:
        d = _bfs_distances(adj, n)
        for m, dist in d.items():
            if m != n:
                all_d.append(dist)
    diam = max(all_d) if all_d else 0
    return {
        **envelope("topological_statistics"),
        "input_summary": {"operation": "compute_path_lengths", "node_count": len(node_ids)},
        "summary": {
            "node_count": len(node_ids),
            "pair_count": len(all_d),
            "mean_path_length": round(sum(all_d) / len(all_d), 4) if all_d else 0.0,
            "diameter": diam,
            "path_length_distribution": _distribution(all_d),
        },
    }


def compute_centrality(graph, config=None) -> dict:
    cfg = normalize_config(config)
    node_ids, adj = _build(cfg, graph)
    n = len(node_ids)
    idx = {nd: i for i, nd in enumerate(node_ids)}
    degrees = {nd: len(adj[nd]) for nd in node_ids}
    # closeness = (n-1) / sum(shortest dist to all others
    closeness = {}
    for nd in node_ids:
        d = _bfs_distances(adj, nd)
        others = [v for v in d.values() if v > 0]
        tot = sum(others)
        closeness[nd] = round((n - 1) / tot, 4) if tot else 0.0
    # betweenness (Brandes, unweighted)
    betweenness = {nd: 0.0 for nd in node_ids}
    for s in node_ids:
        pred = {v: [] for v in node_ids}
        dist = {v: -1 for v in node_ids}
        sigma = {v: 0 for v in node_ids}
        dist[s] = 0
        sigma[s] = 1
        q = deque([s])
        order = []
        while q:
            v = q.popleft()
            order.append(v)
            for w in adj[v]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    q.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta = {v: 0.0 for v in node_ids}
        for w in reversed(order):
            for v in pred[w]:
                if sigma[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != s:
                betweenness[w] += delta[w]
    # undirected: divide by 2
    betweenness = {v: round(bt / 2.0, 4) for v, bt in betweenness.items()}
    # eigenvector (power iteration on adjacency)
    eig = _eigenvector(adj, node_ids, idx, n)
    return {
        **envelope("topological_statistics"),
        "input_summary": {"operation": "compute_centrality", "node_count": n},
        "centrality": {
            "degree": {k: round(v / max(degrees.values()), 4) if degrees else 0.0 for k, v in degrees.items()},
            "closeness": closeness,
            "betweenness": betweenness,
            "eigenvector": {k: round(v, 4) for k, v in eig.items()},
        },
        "summary": {
            "most_central_by_degree": max(degrees, key=degrees.get) if degrees else None,
            "most_central_by_betweenness": max(betweenness, key=betweenness.get) if betweenness else None,
        },
    }


def _eigenvector(adj, node_ids, idx, n, max_iter=100, tol=1e-9):
    if n == 0:
        return {}
    x = {nd: 1.0 for nd in node_ids}
    for _ in range(max_iter):
        nx = {nd: sum(x[v] for v in adj[nd]) for nd in node_ids}
        norm = math.sqrt(sum(v * v for v in nx.values()))
        if norm == 0:
            return {nd: 0.0 for nd in node_ids}
        nx = {nd: v / norm for nd, v in nx.items()}
        diff = max(abs(nx[nd] - x[nd]) for nd in node_ids)
        x = nx
        if diff < tol:
            break
    return x


def analyze_components(graph, config=None) -> dict:
    cfg = normalize_config(config)
    node_ids, adj = _build(cfg, graph)
    seen = set()
    comps = []
    for nd in node_ids:
        if nd in seen:
            continue
        stack = [nd]
        comp = []
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            comp.append(u)
            for v in adj[u]:
                if v not in seen:
                    stack.append(v)
        comps.append(sorted(comp))
    comps.sort(key=lambda c: (-len(c), c[0]))
    return {
        **envelope("topological_statistics"),
        "input_summary": {"operation": "analyze_components", "node_count": len(node_ids)},
        "components": comps,
        "summary": {
            "component_count": len(comps),
            "largest_component_size": len(comps[0]) if comps else 0,
            "is_connected": len(comps) == 1,
            "isolated_nodes": [c[0] for c in comps if len(c) == 1],
        },
    }


def _distribution(vals):
    from collections import Counter
    c = Counter(vals)
    return {str(k): v for k, v in sorted(c.items())}
