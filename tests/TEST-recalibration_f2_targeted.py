"""
TEST-recalibration_f2_targeted.py — F2 EDGE-TARGETING CONTRACT (RED by design)

TDD spec for Mutation 5 / F2 edge recalibration. Encodes the acceptance
from SPEC_AXIOM_RECALIBRATION.md §2.3 + the approved
PROPOSAL_VIOLATION_SCHEMA.md:

    Given a violation with recent_fact_ids=[f1, f2], F2's
    _update_edge_weights resolves to edges INCIDENT on f1/f2 and
    ONLY modifies those edges. An unrelated edge Y is UNCHANGED.

EDGE KEYS = fact_id -> fact_id (verified in sleep_procedural_edge_extractor.py:
edge key f"{src_fact}->{tgt_fact}", carrying source_fact_id /
target_fact_id). So recent_fact_ids resolves directly.

STATUS: EXPECTED RED until next turn implements the field->edge-key mapping
inside _update_edge_weights. The current method is the guarded
no-op (returns 0 updates, status
'targeting_field_present_but_mapping_unimplemented'). This test is
the contract that next turn must turn green. It is intentionally a
failing test — do NOT "fix" it by weakening the assertions; implement
the mapping instead.

Run: python tests/TEST-recalibration_f2_targeted.py
Exit 0 = PASS (mapping implemented); exit 1 = still RED (TDD).
"""
import sys, os, json
from typing import Dict, Any

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from sleep_recalibration_service import RecalibrationService


def _build_graph() -> Dict[str, Any]:
    """3 edges: two incident on facts 1/2, one unrelated (Y = 9->10)."""
    return {
        "metadata": {"total_edges": 3},
        "edges": {
            "1->3": {"source_fact_id": 1, "target_fact_id": 3,
                      "edge_weight": 0.50, "confidence_mutable": True},
            "2->4": {"source_fact_id": 2, "target_fact_id": 4,
                      "edge_weight": 0.50, "confidence_mutable": True},
            "9->10": {"source_fact_id": 9, "target_fact_id": 10,
                       "edge_weight": 0.50, "confidence_mutable": True},
        },
    }


def _snapshot(g: Dict[str, Any]) -> Dict[str, float]:
    return {k: v["edge_weight"] for k, v in g["edges"].items()}


def _check(cond: bool, msg: str):
    if cond:
        print(f"  ✓ {msg}")
    else:
        print(f"  ✗ FAIL: {msg}")
        raise AssertionError(msg)


def main():
    svc = RecalibrationService()  # paths set, no disk I/O in _update_edge_weights
    graph = _build_graph()
    before = _snapshot(graph)

    violation = {
        "dissonance_type": "high_confidence_low_coherence",
        "mtr_error_signal": 0.9,
        "returned_confidence": 0.1,
        "context": {"recent_fact_ids": [1, 2]},  # the unlocked schema field
    }
    updates = {e: -0.2 for e in graph["edges"]}  # candidate penalty per edge

    updated_count, status = svc._update_edge_weights(updates, [violation])
    after = _snapshot(graph)

    print(f"  updated_count={updated_count}")
    print(f"  status={json.dumps(status) if isinstance(status, dict) else status}")

    # TARGETED behavior (the contract):
    _check(abs(after["1->3"] - before["1->3"]) > 1e-9,
            "edge 1->3 (incident on f1) CHANGED")
    _check(abs(after["2->4"] - before["2->4"]) > 1e-9,
            "edge 2->4 (incident on f2) CHANGED")
    _check(abs(after["9->10"] - before["9->10"]) < 1e-9,
            "unrelated edge 9->10 (Y) UNCHANGED")
    _check(updated_count == 2,
            f"exactly 2 edges updated (got {updated_count})")
    print("RESULT: F2 edge-targeting contract SATISFIED")


if __name__ == "__main__":
    try:
        main()
        print("\nPASS: F2 edge-targeting GREEN")
        sys.exit(0)
    except AssertionError as e:
        print(f"\nRED (expected until F2 mapping implemented): {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
