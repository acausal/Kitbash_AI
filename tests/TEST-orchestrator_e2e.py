#!/usr/bin/env python3
"""
TEST-orchestrator_e2e.py  (SPEC Step 4/6 — T8 real-MTR end-to-end)

Runs the REAL factory (create_query_orchestrator) with the REAL torch-backed
MTR engine and the REAL repo components (no monkeypatching, no stubs). Proves
the full reconciled path actually works now that torch is installed:

  - factory builds an orchestrator with a live LearningObserver injected
  - real cascade answers a query (CARTRIDGE via real CartridgeEngine.query)
  - learning_report is populated (mtr_confidence, trace_logged)
  - MTR state counter advances across queries AND persists on close() AND
    resumes on a rebuilt orchestrator (SPEC Step 4 state lifecycle, for real)

Requires torch (installed in .venv). Skips cleanly if torch/engine absent so
the file stays importable in torch-free CI.

Run:  .venv\\Scripts\\activate && python TEST-orchestrator_e2e.py
"""
import sys
import os
import logging
from pathlib import Path

logging.basicConfig(level=logging.WARNING)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

results = []
def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def main():
    # --- torch availability gate ---
    try:
        import torch  # noqa
        from query_orchestrator_factory import create_query_orchestrator
        from MTR_v6_1 import KitbashMTREngine  # real engine present?
    except Exception as e:
        check("torch + MTR_v6_1 importable (T8 requires real MTR)", False,
              f"skipped: {e}")
        print("=" * 60)
        print("T8 e2e SKIPPED (torch/MTR not available)")
        print("=" * 60)
        return 0  # skip, don't fail the gate

    check("torch + MTR_v6_1 importable (T8 requires real MTR)", True)

    # Build the REAL orchestrator (no monkeypatch, no stubs).
    orch = create_query_orchestrator(cartridges_dir="./cartridges",
                                     enable_grain_system=False)
    check("factory builds orchestrator (real torch path)", orch is not None)
    check("LearningObserver injected by factory", orch.learning_observer is not None)

    # Real cascade answers a query.
    ctx = {"project_context": "test", "session_id": "t8e2e", "hat": "curious"}
    res = orch.process_query("What is ATP and why is it important?", context=ctx)
    check("real cascade produced an answer", bool(res.answer), repr(res.answer)[:60])
    check("answered query counted", orch.get_metrics()["queries_answered"] >= 1,
          f"answered={orch.get_metrics()['queries_answered']}")
    lr = res.learning_report or {}
    check("learning_report populated by real observer", bool(lr), repr(list(lr.keys())))
    check("learning_report.trace_logged True", lr.get("trace_logged") is True)
    check("learning_report has mtr_confidence", "mtr_confidence" in lr)

    # State counter advances across queries (SPEC Step 4, for real).
    t0 = (orch.learning_observer.mtr_state or {}).get("time", 0)
    orch.process_query("Second query about mitochondria.", context=ctx)
    orch.process_query("Third query about proteins.", context=ctx)
    t1 = (orch.learning_observer.mtr_state or {}).get("time", 0)
    check("MTR state counter advanced across 3 queries", t1 > t0,
          f"t0={t0} t1={t1}")

    # Persist on close(), then rebuild and confirm resume.
    orch.close(session_id="t8e2e")
    orch2 = create_query_orchestrator(cartridges_dir="./cartridges",
                                      enable_grain_system=False)
    t2 = (orch2.learning_observer.mtr_state or {}).get("time", 0)
    check("rebuilt orchestrator resumes counter from checkpoint", t2 >= t1,
          f"persisted={t1} resumed={t2}")

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("=" * 60)
    print(f"T8 real-MTR e2e: {passed}/{total} PASS")
    print("=" * 60)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
