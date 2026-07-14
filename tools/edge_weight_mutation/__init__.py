"""tools.edge_weight_mutation package.

Library:
    from tools.edge_weight_mutation import edge_mutate, edge_mutate_batch
    edge_mutate(graph, "a->b", -0.2)              # -> {"status":"success","new_weight":...,...}
    edge_mutate_batch(graph, [{"edge_id":"a->b","delta":-0.1}, ...], atomic=True)

CLI:
    python -m tools.edge_weight_mutation mutate graph.json a->b -0.15 --reason violation_observed
    python -m tools.edge_weight_mutation mutate-batch graph.json muts.json --no-atomic

Applies confidence deltas to procedural edge weights (clamped to [0,1]).
Batch atomic (default) rolls back on any failure. In-place graph mutation.
Errors returned as dicts, never raised. Pure stdlib.
"""
from .core import edge_mutate, edge_mutate_batch

__all__ = ["edge_mutate", "edge_mutate_batch"]
