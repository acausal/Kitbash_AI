"""neighborhood_projection core: BFS projection over a procedural edge graph.

Isolation-first tool (see tools/README.md). Allowed imports: stdlib and Kitbash
core's structured_logger (read-only helper). No orchestrator/engine/redis imports.

Design: lightweight BFS with depth + strength filtering. All functions return
JSON-serializable dicts. Node metadata (node_type, cartridge) is DERIVED from the
edges (there is no separate node registry) — see _infer_node_metadata.
"""
from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional, Tuple

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("neighborhood_projection")
except Exception:  # structured_logger optional; never let logging break the tool
    _logger = None


# --------------------------------------------------------------------------- #
# Graph helpers
# --------------------------------------------------------------------------- #
def _validate_graph(edge_graph: dict) -> dict:
    """Return the edges dict or raise RuntimeError if the graph is malformed."""
    if not isinstance(edge_graph, dict) or "edges" not in edge_graph:
        raise RuntimeError("edge_graph malformed: missing 'edges' key")
    edges = edge_graph["edges"]
    if not isinstance(edges, dict):
        raise RuntimeError("edge_graph malformed: 'edges' must be a dict")
    return edges


def _edge_endpoints(edge: dict) -> Tuple[Optional[str], Optional[str]]:
    source = edge.get("source_fact_id") or edge.get("source_grain_id")
    target = edge.get("target_fact_id") or edge.get("target_grain_id")
    return source, target


def _all_nodes(edge_graph: dict) -> set:
    """Every node id that appears in edges or the cartridge_index."""
    nodes = set()
    for edge in edge_graph.get("edges", {}).values():
        s, t = _edge_endpoints(edge)
        if s:
            nodes.add(s)
        if t:
            nodes.add(t)
    for ids in (edge_graph.get("cartridge_index") or {}).values():
        nodes.update(ids or [])
    return nodes


def _infer_node_metadata(edge_graph: dict, node_id: str) -> dict:
    """Infer node_type and cartridge for a node from the edges it appears in.

    node_type: 'fact' if seen as *_fact_id, 'grain' if seen as *_grain_id
    (fact takes precedence on inconsistency), else 'unknown'.
    cartridge: most frequently observed source/target cartridge; ties broken
    alphabetically; None if never observed.
    """
    node_type = "unknown"
    cartridge_counts: Dict[str, int] = {}
    for edge in edge_graph.get("edges", {}).values():
        source = edge.get("source_fact_id") or edge.get("source_grain_id")
        target = edge.get("target_fact_id") or edge.get("target_grain_id")
        if source == node_id:
            if edge.get("source_fact_id"):
                node_type = "fact"
            elif edge.get("source_grain_id") and node_type != "fact":
                node_type = "grain"
            c = edge.get("source_cartridge")
            if c:
                cartridge_counts[c] = cartridge_counts.get(c, 0) + 1
        if target == node_id:
            if edge.get("target_fact_id"):
                node_type = "fact"
            elif edge.get("target_grain_id") and node_type != "fact":
                node_type = "grain"
            c = edge.get("target_cartridge")
            if c:
                cartridge_counts[c] = cartridge_counts.get(c, 0) + 1
    cartridge = None
    if cartridge_counts:
        # most frequent; ties broken alphabetically
        cartridge = min(sorted(cartridge_counts),
                        key=lambda k: -cartridge_counts[k])
    return {"node_type": node_type, "cartridge": cartridge}


def _adjacency(edges: dict, bidirectional: bool) -> Dict[str, List[Tuple[str, dict, str]]]:
    """Map node -> list of (neighbor, edge_dict, direction) tuples."""
    adj: Dict[str, List[Tuple[str, dict, str]]] = {}
    for edge in edges.values():
        s, t = _edge_endpoints(edge)
        if not s or not t:
            continue  # skip edges referencing non-existent nodes
        adj.setdefault(s, []).append((t, edge, "outgoing"))
        if bidirectional:
            adj.setdefault(t, []).append((s, edge, "incoming"))
    return adj


# --------------------------------------------------------------------------- #
# Core projection
# --------------------------------------------------------------------------- #
def _project(edge_graph: dict, seed_nodes: list, depth_limit: int,
             strength_threshold: float, bidirectional: bool) -> dict:
    edges = _validate_graph(edge_graph)
    if not isinstance(seed_nodes, list) or not seed_nodes:
        raise ValueError("seed_nodes must be a non-empty list")
    if not isinstance(depth_limit, int) or isinstance(depth_limit, bool) or depth_limit < 0:
        raise ValueError("depth_limit must be a non-negative integer")
    if not isinstance(strength_threshold, (int, float)) or isinstance(strength_threshold, bool) \
            or not (0.0 <= strength_threshold <= 1.0):
        raise ValueError("strength_threshold must be in [0.0, 1.0]")
    all_nodes = _all_nodes(edge_graph)
    for sn in seed_nodes:
        if sn not in all_nodes:
            raise ValueError(f"seed node not in graph: {sn!r}")

    adj = _adjacency(edges, bidirectional)
    # BFS: best[node] = (distance, cumulative_weight)
    best: Dict[str, Tuple[int, float]] = {sn: (0, 1.0) for sn in seed_nodes}
    queue = deque((sn, 0, 1.0) for sn in seed_nodes)
    while queue:
        node, dist, w = queue.popleft()
        if dist >= depth_limit:
            continue
        for nb, edge, _dir in adj.get(node, []):
            ew = float(edge.get("edge_weight", 0.0))
            nw = w * ew
            nd = dist + 1
            cur = best.get(nb)
            if cur is None or nd < cur[0] or (nd == cur[0] and nw > cur[1]):
                best[nb] = (nd, nw)
                queue.append((nb, nd, nw))

    # Apply strength threshold (seeds always kept)
    seeds = set(seed_nodes)
    filtered = 0
    members: Dict[str, Tuple[int, float]] = {}
    for node, (dist, w) in best.items():
        if node in seeds or w >= strength_threshold:
            members[node] = (dist, w)
        else:
            filtered += 1

    # Induced edges among members
    out_edges: List[dict] = []
    for edge in edges.values():
        s, t = _edge_endpoints(edge)
        if s in members and t in members:
            e = {
                "source": s,
                "target": t,
                "edge_weight": float(edge.get("edge_weight", 0.0)),
                "edge_type": edge.get("edge_type", "intra_cartridge"),
                "traversal_count": int(edge.get("traversal_count", 0)),
                "last_traversed": edge.get("last_traversed"),
            }
            if bidirectional:
                ds, dt = members[s][0], members[t][0]
                e["direction"] = "incoming" if ds > dt else "outgoing"
            out_edges.append(e)

    # strongest incoming edge weight per node
    strongest_in: Dict[str, float] = {}
    for e in out_edges:
        tgt = e["target"]
        strongest_in[tgt] = max(strongest_in.get(tgt, 0.0), e["edge_weight"])

    # Build node objects
    nodes_out: Dict[str, dict] = {}
    for node, (dist, w) in members.items():
        meta = _infer_node_metadata(edge_graph, node)
        obj = {
            "node_id": node,
            "node_type": meta["node_type"],
            "cartridge": meta["cartridge"],
            "is_seed": node in seeds,
        }
        if node not in seeds:
            obj["distance_from_seed"] = dist
            obj["cumulative_path_weight"] = w
            obj["strongest_incoming_edge_weight"] = strongest_in.get(node)
        nodes_out[node] = obj

    stats = _aggregate_stats(nodes_out, out_edges, depth_limit, bidirectional)
    result = {
        "seed_nodes": list(seed_nodes),
        "depth_limit": depth_limit,
        "strength_threshold": strength_threshold,
        "neighborhood": {"nodes": nodes_out, "edges": out_edges},
        "aggregated_stats": stats,
        "projection_params": {
            "depth_limit": depth_limit,
            "strength_threshold": strength_threshold,
            "nodes_filtered_by_threshold": filtered,
        },
    }
    if bidirectional:
        result["direction"] = "bidirectional"
    if _logger:
        _logger.log(event_type="projection_complete",
                    data={"seed_nodes": seed_nodes, "depth_limit": depth_limit,
                          "nodes_found": len(nodes_out), "edges_found": len(out_edges)})
    return result


def _aggregate_stats(nodes_out: dict, out_edges: list, depth_limit: int,
                     bidirectional: bool) -> dict:
    weights = [e["edge_weight"] for e in out_edges]
    avg_w = round(sum(weights) / len(weights), 4) if weights else 0.0
    depth_dist = {f"depth_{d}": 0 for d in range(depth_limit + 1)}
    for n in nodes_out.values():
        d = 0 if n.get("is_seed") else n.get("distance_from_seed", 0)
        depth_dist[f"depth_{d}"] = depth_dist.get(f"depth_{d}", 0) + 1
    edge_types = {"intra_cartridge": 0, "cross_cartridge": 0}
    for e in out_edges:
        et = e.get("edge_type", "intra_cartridge")
        edge_types[et] = edge_types.get(et, 0) + 1
    cartridges = sorted({n["cartridge"] for n in nodes_out.values() if n.get("cartridge")})
    stats = {
        "total_nodes_in_neighborhood": len(nodes_out),
        "total_edges_in_neighborhood": len(out_edges),
        "avg_edge_weight": avg_w,
        "depth_distribution": depth_dist,
        "edge_types": edge_types,
        "cartridges_touched": cartridges,
    }
    if bidirectional:
        stats["incoming_edges"] = sum(1 for e in out_edges if e.get("direction") == "incoming")
        stats["outgoing_edges"] = sum(1 for e in out_edges if e.get("direction") == "outgoing")
        stats["total_nodes"] = len(nodes_out)
        stats["total_edges"] = len(out_edges)
    return stats


def project_neighborhood(edge_graph: dict, seed_nodes: list, depth_limit: int = 2,
                         strength_threshold: float = 0.0) -> dict:
    return _project(edge_graph, seed_nodes, depth_limit, strength_threshold, False)


def project_neighborhood_bidirectional(edge_graph: dict, seed_nodes: list,
                                       depth_limit: int = 2,
                                       strength_threshold: float = 0.0) -> dict:
    return _project(edge_graph, seed_nodes, depth_limit, strength_threshold, True)


# --------------------------------------------------------------------------- #
# Post-projection operations
# --------------------------------------------------------------------------- #
def _inner(neighborhood: dict) -> dict:
    """Accept either a full projection result or the inner {nodes,edges}."""
    if not isinstance(neighborhood, dict):
        raise ValueError("neighborhood must be a dict")
    if "neighborhood" in neighborhood and isinstance(neighborhood["neighborhood"], dict):
        return neighborhood["neighborhood"]
    return neighborhood


def filter_neighborhood(neighborhood: dict, min_strength: float,
                        min_degree: int = 1) -> dict:
    if not isinstance(min_strength, (int, float)) or isinstance(min_strength, bool) \
            or not (0.0 <= min_strength <= 1.0):
        raise ValueError("min_strength must be in [0.0, 1.0]")
    inner = _inner(neighborhood)
    nodes = inner.get("nodes", {})
    edges = inner.get("edges", [])
    if not nodes:
        return {"neighborhood": {"nodes": {}, "edges": []},
                "aggregated_stats": _aggregate_stats({}, [], 0, False)}

    # degree from current edges
    degree: Dict[str, int] = {}
    for e in edges:
        degree[e["source"]] = degree.get(e["source"], 0) + 1
        degree[e["target"]] = degree.get(e["target"], 0) + 1

    kept = {}
    for nid, n in nodes.items():
        w = n.get("cumulative_path_weight", 1.0)
        if w < min_strength:
            continue
        if degree.get(nid, 0) < min_degree:
            continue
        kept[nid] = n
    kept_edges = [e for e in edges if e["source"] in kept and e["target"] in kept]
    return {
        "neighborhood": {"nodes": kept, "edges": kept_edges},
        "aggregated_stats": _aggregate_stats(kept, kept_edges, 0, False),
    }


def rank_neighborhood_by_weight(neighborhood: dict,
                                sort_order: str = "descending") -> dict:
    if sort_order not in ("ascending", "descending"):
        raise ValueError("sort_order must be 'ascending' or 'descending'")
    if isinstance(neighborhood, dict) and "seed_nodes" in neighborhood:
        seeds = neighborhood["seed_nodes"]
    else:
        seeds = []
    inner = _inner(neighborhood)
    nodes = inner.get("nodes", {})
    ranked = [n for n in nodes.values() if not n.get("is_seed")]
    ranked.sort(key=lambda n: n.get("cumulative_path_weight", 0.0),
                reverse=(sort_order == "descending"))
    out = []
    for i, n in enumerate(ranked, start=1):
        out.append({
            "node_id": n["node_id"],
            "cumulative_path_weight": n.get("cumulative_path_weight", 0.0),
            "distance_from_seed": n.get("distance_from_seed"),
            "rank": i,
        })
    return {"ranked_nodes": out, "original_seed_nodes": list(seeds)}


def explain_path(edge_graph: dict, source_node: str, target_node: str) -> dict:
    edges = _validate_graph(edge_graph)
    all_nodes = _all_nodes(edge_graph)
    if source_node not in all_nodes:
        raise ValueError(f"source_node not in graph: {source_node!r}")
    if target_node not in all_nodes:
        raise ValueError(f"target_node not in graph: {target_node!r}")

    if source_node == target_node:
        return {
            "source": source_node, "target": target_node, "path_found": True,
            "path": [{"node_id": source_node, "step": 0}],
            "path_length": 0, "cumulative_weight": 1.0, "edges_traversed": [],
        }

    adj = _adjacency(edges, bidirectional=False)
    # BFS shortest path within 5 hops, tracking predecessor + edge used
    prev: Dict[str, Tuple[str, dict]] = {}
    visited = {source_node}
    queue = deque([(source_node, 0)])
    found = False
    while queue:
        node, dist = queue.popleft()
        if dist >= 5:
            continue
        for nb, edge, _dir in adj.get(node, []):
            if nb in visited:
                continue
            visited.add(nb)
            prev[nb] = (node, edge)
            if nb == target_node:
                found = True
                queue.clear()
                break
            queue.append((nb, dist + 1))

    if not found:
        return {"source": source_node, "target": target_node, "path_found": False,
                "path": [], "path_length": 0, "cumulative_weight": 0.0,
                "edges_traversed": []}

    # reconstruct
    chain = []
    node = target_node
    while node != source_node:
        p, edge = prev[node]
        chain.append((p, node, edge))
        node = p
    chain.reverse()
    path_nodes = [{"node_id": source_node, "step": 0}]
    edges_traversed = []
    cumulative = 1.0
    for i, (s, t, edge) in enumerate(chain, start=1):
        path_nodes.append({"node_id": t, "step": i})
        ew = float(edge.get("edge_weight", 0.0))
        cumulative *= ew
        edges_traversed.append({"source": s, "target": t, "edge_weight": ew})
    return {
        "source": source_node, "target": target_node, "path_found": True,
        "path": path_nodes, "path_length": len(chain),
        "cumulative_weight": round(cumulative, 6), "edges_traversed": edges_traversed,
    }
