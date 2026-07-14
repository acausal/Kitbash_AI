# SPEC: Edge Weight Mutation Tool v1

**Version:** 1.0  
**Status:** Ready for implementation  
**Target:** Kitbash tool registry (standalone tool)  
**Depends:** stdlib `json`

---

## Purpose

Apply violation signals and confidence updates to procedural edge weights. Separates edge-update logic from sleep pipeline orchestration, making Dream Bucket signals reusable and testable.

**Use cases:**
- Apply violation signals from Stage 5 recalibration to edge graph
- Integrate Dream Bucket anomalies into topology
- Batch apply learned confidence adjustments
- Replay mutation history for debugging

---

## Interface

### Tool Call: Single Mutation

```
edge_mutate(
    edge_graph: dict,          # Procedural edge graph (nodes + edges)
    edge_id: str,              # Edge to modify (format: "node_a->node_b")
    delta: float,              # Weight change (range: -1.0 to +1.0)
    reason: str = None,        # Log reason for mutation (optional)
)
```

### Return Value

```json
{
  "status": "success",
  "operation": "single",
  "edge_id": "grain_123->grain_456",
  "old_weight": 0.65,
  "new_weight": 0.52,
  "delta": -0.13,
  "reason": "violation_observed",
  "graph_modified": true
}
```

### Tool Call: Batch Mutations

```
edge_mutate_batch(
    edge_graph: dict,          # Procedural edge graph
    mutations: list[dict],     # [{"edge_id": "...", "delta": ..., "reason": "..."}, ...]
    atomic: bool = true,       # All-or-nothing (default: true)
)
```

### Return Value

```json
{
  "status": "success",
  "operation": "batch",
  "mutations_applied": 3,
  "mutations_failed": 0,
  "mutations_total": 3,
  "graph_modified": true,
  "results": [
    {"edge_id": "a->b", "old_weight": 0.65, "new_weight": 0.58, "delta": -0.07, "status": "ok"},
    {"edge_id": "c->d", "old_weight": 0.42, "new_weight": 0.51, "delta": +0.09, "status": "ok"},
    {"edge_id": "e->f", "old_weight": 0.80, "new_weight": 0.75, "delta": -0.05, "status": "ok"}
  ]
}
```

### Error Cases

```json
{
  "status": "error",
  "reason": "Edge not found: 'grain_999->grain_000'",
  "edge_id": "grain_999->grain_000"
}
```

```json
{
  "status": "error",
  "reason": "Invalid delta: 1.5 (must be in range [-1.0, 1.0])",
  "delta": 1.5
}
```

```json
{
  "status": "error",
  "reason": "Batch atomic mode failed at mutation 2: edge_id 'c->d' not found. No changes applied.",
  "atomic": true,
  "failed_at": 2
}
```

---

## Semantics

### Edge Graph Structure

Input graph expected to have format (same as procedural_edge_graph.json):

```json
{
  "edges": {
    "grain_123->grain_456": {
      "weight": 0.65,
      "traversal_count": 42,
      "last_traversed": "2026-07-14T12:30:00Z",
      "confidence_mutable": true
    },
    ...
  },
  "nodes": {
    "grain_123": {"type": "grain", "cartridge": "physics"},
    "grain_456": {"type": "grain", "cartridge": "chemistry"},
    ...
  }
}
```

### Edge ID Format

Canonical format: `"node_a->node_b"` (ASCII `->`, no spaces). Direction matters.

### Weight Range

Weights are bounded to `[0.0, 1.0]`:
- `0.0`: Edge is inactive/unreliable
- `0.5`: Neutral
- `1.0`: Edge is strong/reliable

After applying `delta`, weight is **clamped** to this range:

```
new_weight = max(0.0, min(1.0, old_weight + delta))
```

Example: `old_weight=0.8 + delta=0.5` → `new_weight=1.0` (clamped)

### Delta Semantics

`delta` represents the **change in confidence**:
- `delta > 0`: Increase confidence (violation resolved, pattern confirmed)
- `delta < 0`: Decrease confidence (violation observed, pattern broken)
- `delta = 0`: No change

**Typical magnitudes:**
- `±0.1`: Small adjustment (minor signal)
- `±0.2`: Medium adjustment (moderate violation/success)
- `±0.5`: Large adjustment (strong signal)

### Mutation Reason

Optional `reason` string for audit/logging:
- `"violation_observed"`: Dream Bucket reported inconsistency
- `"success_pattern"`: Pattern succeeded; confidence increased
- `"anomaly_detected"`: Anomaly scorer flagged unexpected edge use
- `"hypothesis_test"`: Experimental hypothesis testing
- `"recalibration"`: Stage 5 systematic recalibration
- (or any other domain-specific reason)

### Atomic Mode (Batch)

`atomic=true` (default): Either all mutations succeed, or none apply. If any mutation fails (edge not found, invalid delta), the entire batch is rolled back.

`atomic=false`: Apply mutations individually; if one fails, skip it and continue.

---

## Implementation Notes

### Single Mutation

```python
def edge_mutate(edge_graph: dict, edge_id: str, delta: float, reason: str = None) -> dict:
    # Validate delta
    if not -1.0 <= delta <= 1.0:
        return {
            "status": "error",
            "reason": f"Invalid delta: {delta} (must be in range [-1.0, 1.0])",
            "delta": delta
        }
    
    # Check edge exists
    if edge_id not in edge_graph.get("edges", {}):
        return {
            "status": "error",
            "reason": f"Edge not found: '{edge_id}'",
            "edge_id": edge_id
        }
    
    # Retrieve edge
    edge = edge_graph["edges"][edge_id]
    old_weight = edge.get("weight", 0.5)
    
    # Apply mutation (clamp to [0, 1])
    new_weight = max(0.0, min(1.0, old_weight + delta))
    
    # Update edge in place
    edge["weight"] = new_weight
    if reason:
        edge["last_mutation_reason"] = reason
    edge["last_mutated"] = datetime.utcnow().isoformat() + "Z"
    
    return {
        "status": "success",
        "operation": "single",
        "edge_id": edge_id,
        "old_weight": old_weight,
        "new_weight": new_weight,
        "delta": delta,
        "reason": reason,
        "graph_modified": True
    }
```

### Batch Mutation (Atomic)

```python
def edge_mutate_batch(edge_graph: dict, mutations: list, atomic: bool = True) -> dict:
    # Validate all mutations before applying (atomic pre-check)
    if atomic:
        for i, m in enumerate(mutations):
            if m.get("edge_id") not in edge_graph.get("edges", {}):
                return {
                    "status": "error",
                    "reason": f"Batch atomic mode failed at mutation {i}: edge_id '{m.get('edge_id')}' not found. No changes applied.",
                    "atomic": True,
                    "failed_at": i
                }
            delta = m.get("delta", 0)
            if not -1.0 <= delta <= 1.0:
                return {
                    "status": "error",
                    "reason": f"Batch atomic mode failed at mutation {i}: invalid delta {delta}",
                    "failed_at": i
                }
    
    # Apply mutations
    results = []
    failed = 0
    for m in mutations:
        edge_id = m.get("edge_id")
        delta = m.get("delta", 0)
        reason = m.get("reason")
        
        if edge_id not in edge_graph.get("edges", {}):
            if not atomic:
                failed += 1
                results.append({"edge_id": edge_id, "status": "failed", "reason": "edge not found"})
            continue
        
        edge = edge_graph["edges"][edge_id]
        old_weight = edge.get("weight", 0.5)
        new_weight = max(0.0, min(1.0, old_weight + delta))
        edge["weight"] = new_weight
        if reason:
            edge["last_mutation_reason"] = reason
        
        results.append({
            "edge_id": edge_id,
            "old_weight": old_weight,
            "new_weight": new_weight,
            "delta": delta,
            "status": "ok"
        })
    
    return {
        "status": "success",
        "operation": "batch",
        "mutations_applied": len(results) - failed,
        "mutations_failed": failed,
        "mutations_total": len(mutations),
        "graph_modified": True,
        "results": results
    }
```

---

## Data Structure

### Input Schema (Single)

```json
{
  "edge_graph": { ... },
  "edge_id": "grain_123->grain_456",
  "delta": -0.15,
  "reason": "violation_observed"
}
```

### Input Schema (Batch)

```json
{
  "edge_graph": { ... },
  "mutations": [
    {"edge_id": "a->b", "delta": -0.1, "reason": "anomaly_detected"},
    {"edge_id": "c->d", "delta": +0.2, "reason": "success_pattern"},
    {"edge_id": "e->f", "delta": -0.05}
  ],
  "atomic": true
}
```

### Output Schema (Success - Single)

```json
{
  "status": "success",
  "operation": "single",
  "edge_id": "grain_123->grain_456",
  "old_weight": 0.65,
  "new_weight": 0.50,
  "delta": -0.15,
  "reason": "violation_observed",
  "graph_modified": true
}
```

### Output Schema (Success - Batch)

```json
{
  "status": "success",
  "operation": "batch",
  "mutations_applied": 3,
  "mutations_failed": 0,
  "mutations_total": 3,
  "graph_modified": true,
  "results": [
    {"edge_id": "a->b", "old_weight": 0.5, "new_weight": 0.4, "delta": -0.1, "status": "ok"},
    {"edge_id": "c->d", "old_weight": 0.6, "new_weight": 0.8, "delta": +0.2, "status": "ok"},
    {"edge_id": "e->f", "old_weight": 0.75, "new_weight": 0.7, "delta": -0.05, "status": "ok"}
  ]
}
```

---

## Testing

### Unit Test Examples

```python
def test_single_mutation_decrease():
    graph = {
        "edges": {"a->b": {"weight": 0.7}},
        "nodes": {}
    }
    result = edge_mutate(graph, "a->b", -0.2)
    assert result["status"] == "success"
    assert result["new_weight"] == 0.5
    assert graph["edges"]["a->b"]["weight"] == 0.5

def test_single_mutation_increase():
    graph = {"edges": {"a->b": {"weight": 0.6}}, "nodes": {}}
    result = edge_mutate(graph, "a->b", +0.3)
    assert result["new_weight"] == 0.9

def test_weight_clamping_upper():
    graph = {"edges": {"a->b": {"weight": 0.9}}, "nodes": {}}
    result = edge_mutate(graph, "a->b", +0.5)
    assert result["new_weight"] == 1.0  # Clamped

def test_weight_clamping_lower():
    graph = {"edges": {"a->b": {"weight": 0.1}}, "nodes": {}}
    result = edge_mutate(graph, "a->b", -0.3)
    assert result["new_weight"] == 0.0  # Clamped

def test_edge_not_found():
    graph = {"edges": {}, "nodes": {}}
    result = edge_mutate(graph, "x->y", -0.1)
    assert result["status"] == "error"
    assert "not found" in result["reason"]

def test_invalid_delta():
    graph = {"edges": {"a->b": {"weight": 0.5}}, "nodes": {}}
    result = edge_mutate(graph, "a->b", 1.5)
    assert result["status"] == "error"
    assert "Invalid delta" in result["reason"]

def test_batch_atomic_success():
    graph = {
        "edges": {
            "a->b": {"weight": 0.5},
            "c->d": {"weight": 0.6}
        },
        "nodes": {}
    }
    mutations = [
        {"edge_id": "a->b", "delta": -0.1},
        {"edge_id": "c->d", "delta": +0.2}
    ]
    result = edge_mutate_batch(graph, mutations, atomic=True)
    assert result["status"] == "success"
    assert result["mutations_applied"] == 2
    assert graph["edges"]["a->b"]["weight"] == 0.4
    assert graph["edges"]["c->d"]["weight"] == 0.8

def test_batch_atomic_rollback():
    graph = {
        "edges": {"a->b": {"weight": 0.5}},
        "nodes": {}
    }
    mutations = [
        {"edge_id": "a->b", "delta": -0.1},
        {"edge_id": "x->y", "delta": +0.2}  # Doesn't exist
    ]
    result = edge_mutate_batch(graph, mutations, atomic=True)
    assert result["status"] == "error"
    assert result["atomic"] == True
    assert graph["edges"]["a->b"]["weight"] == 0.5  # Unchanged (rolled back)

def test_batch_non_atomic_partial():
    graph = {
        "edges": {"a->b": {"weight": 0.5}},
        "nodes": {}
    }
    mutations = [
        {"edge_id": "a->b", "delta": -0.1},
        {"edge_id": "x->y", "delta": +0.2}  # Doesn't exist
    ]
    result = edge_mutate_batch(graph, mutations, atomic=False)
    assert result["status"] == "success"
    assert result["mutations_applied"] == 1
    assert result["mutations_failed"] == 1
    assert graph["edges"]["a->b"]["weight"] == 0.4  # Applied
```

---

## CLI

```bash
# Single mutation
python -m tools.edge_mutation mutate \
  edge_graph.json \
  grain_123->grain_456 \
  -0.15 \
  --reason violation_observed
# Output: JSON with new weight

# Batch mutation
python -m tools.edge_mutation mutate-batch \
  edge_graph.json \
  mutations.json \
  --atomic
# Output: JSON with results

# Example mutations.json
[
  {"edge_id": "a->b", "delta": -0.1, "reason": "anomaly_detected"},
  {"edge_id": "c->d", "delta": +0.2, "reason": "success_pattern"}
]
```

---

## Non-Goals

- **Automatic weight learning:** Tool only applies deltas; learning is elsewhere (sleep pipeline)
- **Edge creation/deletion:** Only mutates existing edges. Add/remove via graph modification tool
- **Conflict resolution:** No merge logic. Last writer wins (atomic batches prevent interleaving)
- **Validation against data:** No checks that mutations are "correct" or evidence-based

---

## Related Components

- **Sleep Procedural Edge Extractor** — builds initial edge graph
- **Anomaly Scorer** — flags edges with anomalies (input to mutations)
- **Dream Bucket** — violation signals (input to mutations)
- **Stage 5 Recalibration** — computes mutation deltas from signals
- **Neighborhood Projection** — queries mutated edges for context
