# edge_weight_mutation

Apply violation signals and confidence updates to procedural edge weights.
Separates edge-update logic from sleep-pipeline orchestration. `tools.edge_weight_mutation`.

## Interface

```python
edge_mutate(graph, "grain_123->grain_456", -0.13, reason="violation_observed")
# {"status":"success","old_weight":0.65,"new_weight":0.52,"delta":-0.13,...}

edge_mutate_batch(graph, [{"edge_id":"a->b","delta":-0.1}, {"edge_id":"c->d","delta":0.2}], atomic=True)
# {"status":"success","mutations_applied":2,"mutations_failed":0,...}
```

| Function | Purpose |
|----------|---------|
| `edge_mutate(graph, edge_id, delta, reason=None)` | Single delta; return result/error dict |
| `edge_mutate_batch(graph, mutations, atomic=True)` | Batch; atomic rolls back on any failure |

Weights clamped to `[0,1]`. Delta ∈ `[-1,1]` (else error). Unknown edge →
error. Batch atomic (default): all-or-nothing, no partial apply; non-atomic
skips failures. In-place graph mutation. Errors returned as dicts, never raised.

## CLI

```bash
python -m tools.edge_weight_mutation mutate graph.json a->b -0.15 --reason violation_observed
python -m tools.edge_weight_mutation mutate-batch graph.json muts.json --no-atomic
```

Writes the mutated graph back to the graph file. JSON to stdout, summary to
stderr. Exit 0 = success, 1 = error. Pure stdlib; same `PYTHONPATH= ` prefix
rule in the Kitbash `.venv`.

**Spec:** `SPEC-edge_weight_mutation_v1.md` · **Test:** `TEST-edge_weight_mutation_examples.json`
