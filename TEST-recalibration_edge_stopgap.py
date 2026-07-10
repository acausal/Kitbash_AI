#!/usr/bin/env python3
"""TEST-recalibration_edge_stopgap: AD-HOC verification of F2 Option-1 stopgap
in sleep_recalibration_service.py.

Verifies (against a TEMP dream-bucket dir, never the real one):
1. Real current-schema violations (no edge-targeting field) -> NO edge change,
   status reports the missing field + how many violations were affected.
2. Latent blanket-penalty is GONE: even a synthetic edge graph on disk is
   left completely untouched (no file rewrite, weights unchanged).
3. A violation carrying a targeting field (future schema) still no-ops
   (mapping unimplemented) — refuses to guess.
4. A stray procedural_edge_graph.json present on disk is NOT clobbered.

AD-HOC: this is the spec's Step-1 acceptance evidence, not the permanent
TEST-recalibration_contract.py (which is later, after the schema gaps unblock).
"""
import json
import tempfile
import shutil
from pathlib import Path

import sleep_recalibration_service as rs


def _make_violations(records):
    d = tempfile.mkdtemp(prefix="hermes_rec Stopgap_")
    live = Path(d) / "live"
    live.mkdir()
    (live / "violations.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n"
    )
    return d


def main():
    fails = []

    # ---- Case A: real current-schema violations ----
    recs = [
        {"dissonance_type": "type_a", "mtr_error_signal": 0.8,
         "returned_confidence": 0.9, "returned_fact_id": "f1",
         "session_id": "s1", "timestamp": "2026-07-10"},
        {"dissonance_type": "type_b", "mtr_error_signal": 0.5,
         "returned_confidence": 0.4, "returned_fact_id": "f2",
         "session_id": "s1", "timestamp": "2026-07-10"},
    ]
    bucket = _make_violations(recs)
    try:
        svc = rs.RecalibrationService(dream_bucket_dir=bucket)
        # plant a synthetic edge graph to prove it is NOT touched
        idx = Path(bucket) / "indices"
        idx.mkdir()
        graph = {"edges": {
            "e1": {"edge_weight": 0.5, "confidence_mutable": True},
            "e2": {"edge_weight": 0.7, "confidence_mutable": True},
        }}
        (idx / "procedural_edge_graph.json").write_text(json.dumps(graph))
        before = (idx / "procedural_edge_graph.json").read_text()

        report = svc.run_recalibration_cycle()

        after = (idx / "procedural_edge_graph.json").read_text()
        st = report["edge_recalibration_status"]
        unchanged = before == after
        noop = st and st["action"] == "no-op" and st["reason"] == "no_edge_targeting_field_in_violations"
        right_count = st["violations_seen"] == 2 and st["violations_targetable"] == 0
        edges_untouched = report["edges_updated"] == 0
        if unchanged and noop and right_count and edges_untouched:
            print(f"[PASS] A: current-schema violations -> no edge change, "
                  f"status={st['reason']}, seen={st['violations_seen']}, "
                  f"targetable={st['violations_targetable']}, missing={st['missing_fields']}")
        else:
            fails.append(f"A: unchanged={unchanged} noop={noop} count={right_count} "
                         f"edges_untouched={edges_untouched} -> {report}")
    finally:
        shutil.rmtree(bucket, ignore_errors=True)

    # ---- Case B: violation with a targeting field (future schema) ----
    recs2 = [{"dissonance_type": "x", "mtr_error_signal": 0.9,
              "returned_fact_id": "f3", "edge_key": "e9",
              "session_id": "s2", "timestamp": "2026-07-10"}]
    bucket2 = _make_violations(recs2)
    try:
        svc2 = rs.RecalibrationService(dream_bucket_dir=bucket2)
        idx2 = Path(bucket2) / "indices"
        idx2.mkdir()
        graph2 = {"edges": {"e9": {"edge_weight": 0.5}}}
        (idx2 / "procedural_edge_graph.json").write_text(json.dumps(graph2))
        before2 = (idx2 / "procedural_edge_graph.json").read_text()

        report2 = svc2.run_recalibration_cycle()

        after2 = (idx2 / "procedural_edge_graph.json").read_text()
        st2 = report2["edge_recalibration_status"]
        deferred = st2 and st2["action"] == "no-op" and st2["reason"] == "targeting_field_present_but_mapping_unimplemented"
        still_untouched = before2 == after2 and report2["edges_updated"] == 0
        if deferred and still_untouched:
            print(f"[PASS] B: targeting field present -> still no-op "
                  f"(mapping unimplemented), status={st2['reason']}, "
                  f"targetable={st2['violations_targetable']}")
        else:
            fails.append(f"B: deferred={deferred} untouched={still_untouched} -> {report2}")
    finally:
        shutil.rmtree(bucket2, ignore_errors=True)

    # ---- Case C: no violations file at all ----
    d3 = tempfile.mkdtemp(prefix="hermes_rec_none_")
    try:
        svc3 = rs.RecalibrationService(dream_bucket_dir=d3)
        report3 = svc3.run_recalibration_cycle()
        if report3["violations_processed"] == 0 and report3["edges_updated"] == 0:
            print("[PASS] C: no violations file -> clean early return, no edge change")
        else:
            fails.append(f"C: {report3}")
    finally:
        shutil.rmtree(d3, ignore_errors=True)

    if fails:
        print("\nFAILURES:")
        for f in fails:
            print(" ", f)
        raise SystemExit(1)
    print("\nALL STOPGAP CHECKS PASS — latent blanket-penalty neutralized, no heuristic invented.")


if __name__ == "__main__":
    main()
