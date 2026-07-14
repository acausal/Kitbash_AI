"""tools.edge_weight_mutation core (stdlib only).

Apply violation signals / confidence deltas to procedural edge weights.
Separates edge-update logic from sleep-pipeline orchestration. See
SPEC-edge_weight_mutation_v1.md.
"""
import datetime
from typing import Any, Dict, List


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _clamp(w: float) -> float:
    return round(max(0.0, min(1.0, w)), 6)


def edge_mutate(edge_graph: Dict[str, Any], edge_id: str, delta: float,
                reason: str = None) -> Dict[str, Any]:
    """Apply a single weight delta to one edge. Returns result/error dict."""
    if not (-1.0 <= delta <= 1.0):
        return {"status": "error",
                "reason": f"Invalid delta: {delta} (must be in range [-1.0, 1.0])",
                "delta": delta}
    edges = edge_graph.get("edges", {})
    if edge_id not in edges:
        return {"status": "error", "reason": f"Edge not found: '{edge_id}'", "edge_id": edge_id}
    edge = edges[edge_id]
    old_weight = edge.get("weight", 0.5)
    new_weight = _clamp(old_weight + delta)
    edge["weight"] = new_weight
    if reason:
        edge["last_mutation_reason"] = reason
    edge["last_mutated"] = _now()
    return {
        "status": "success", "operation": "single",
        "edge_id": edge_id, "old_weight": old_weight, "new_weight": new_weight,
        "delta": delta, "reason": reason, "graph_modified": True,
    }


def edge_mutate_batch(edge_graph: Dict[str, Any], mutations: List[Dict[str, Any]],
                      atomic: bool = True) -> Dict[str, Any]:
    """Apply multiple weight deltas. Atomic (default): all-or-nothing; on any
    failure, no changes applied and an error dict is returned. Non-atomic:
    apply individually, skipping failures."""
    edges = edge_graph.get("edges", {})
    # Validate all first (atomic mode only)
    if atomic:
        for i, m in enumerate(mutations):
            eid = m.get("edge_id")
            d = m.get("delta", 0)
            if eid not in edges:
                return {"status": "error",
                        "reason": f"Batch atomic mode failed at mutation {i}: edge_id '{eid}' not found. No changes applied.",
                        "atomic": True, "failed_at": i}
            if not (-1.0 <= d <= 1.0):
                return {"status": "error",
                        "reason": f"Batch atomic mode failed at mutation {i}: invalid delta {d}",
                        "atomic": True, "failed_at": i}
    results: List[Dict] = []
    failed = 0
    for m in mutations:
        eid = m.get("edge_id")
        d = m.get("delta", 0)
        reason = m.get("reason")
        if eid not in edges:
            if not atomic:
                failed += 1
                results.append({"edge_id": eid, "status": "failed", "reason": "edge not found"})
            continue
        edge = edges[eid]
        old_weight = edge.get("weight", 0.5)
        new_weight = _clamp(old_weight + d)
        edge["weight"] = new_weight
        if reason:
            edge["last_mutation_reason"] = reason
        edge["last_mutated"] = _now()
        results.append({"edge_id": eid, "old_weight": old_weight,
                        "new_weight": new_weight, "delta": d, "status": "ok"})
    return {
        "status": "success", "operation": "batch",
        "mutations_applied": len(results) - failed, "mutations_failed": failed,
        "mutations_total": len(mutations), "graph_modified": True, "results": results,
    }
