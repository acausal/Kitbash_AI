#!/usr/bin/env python3
"""
TEST-mutation2_l2_wiring.py — SPEC_MUTATION_2_L2_WIRING.md verification (Phase A
prerequisite for the End-to-End Chat Milestone).

Asserts the canonical factory (create_query_orchestrator) now produces a real,
non-None L2WorkingTheoryService and hands it to LearningObserver, and that the
service is functional (read-only audit call works). Runs a real process_query()
through the canonical path (mock Mamba, GRAIN/CARTRIDGE, no BitNet) to confirm
the pipe is connected and the observer carries the live L2 instance.

HONEST SCOPE NOTE (per spec "wiring only"): LearningObserver.observe() stores
self.l2_service but does NOT currently invoke it. So a query does NOT yet produce
L2 audit output from within observe(). This test verifies WIRING (factory -> non-None
instance -> observer receives it -> service is functional), and explicitly reports
the observe()-does-not-call-it gap as a finding, not a test failure. Invocation
belongs to Mutation 3 / Phase 5B (L2 enrichment), which this spec puts out of scope.

Run: python TEST-mutation2_l2_wiring.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from query_orchestrator_factory import create_query_orchestrator
from l2_working_theory_service import L2WorkingTheoryService

FAILS = []


def check(name, cond, detail=""):
    if cond:
        print(f"[PASS] {name}")
    else:
        print(f"[FAIL] {name}  {detail}")
        FAILS.append(name)


def main():
    print("=== Mutation 2 wiring: build canonical orchestrator (Phase A config) ===")
    try:
        orch = create_query_orchestrator(
            enable_grain_system=True,
            enable_bitnet=False,   # Phase A: mock Mamba + GRAIN/CARTRIDGE, no BitNet
            verbose=False,
        )
    except Exception as e:
        print(f"[FAIL] orchestrator construction raised: {type(e).__name__}: {e}")
        FAILS.append("orchestrator_construction")
        raise SystemExit(1)

    # 1. observer present + holds a real L2 instance
    obs = getattr(orch, "learning_observer", None)
    check("LearningObserver present on orchestrator", obs is not None)
    if obs is not None:
        l2 = getattr(obs, "l2_service", None)
        check("observer.l2_service is NOT None (was hardcoded None before Mutation 2)",
              l2 is not None, f"got {l2!r}")
        check("observer.l2_service is a real L2WorkingTheoryService",
              isinstance(l2, L2WorkingTheoryService), f"type={type(l2)}")

        # 2. the service is functional (read-only audit call)
        try:
            snap = l2.get_working_theory_snapshot(top_phantoms=5, top_edges=5)
            check("L2WorkingTheoryService.get_working_theory_snapshot() returns data (functional)",
                  isinstance(snap, dict), f"returned {type(snap)}")
            print(f"      snapshot keys: {list(snap.keys())[:8]}")
        except Exception as e:
            check("L2WorkingTheoryService functional call", False, f"{type(e).__name__}: {e}")

        # 3. observe() stores l2_service — confirm it is the SAME live instance
        #    (wiring integrity: factory -> observer holds real instance)
        check("observer holds the live L2 instance (not a stub/None)",
              l2 is not None and isinstance(l2, L2WorkingTheoryService))

    # 4. real query through canonical path (mock components, no BitNet)
    print("\n=== real process_query() through canonical path ===")
    try:
        result = orch.process_query("What is ATP and why is it important?")
        check("process_query() returned without crash", result is not None)
        # observer still carries the live L2 instance after a query
        if obs is not None:
            check("observer.l2_service still live after query",
                  getattr(obs, "l2_service", None) is not None)
        print(f"      result type: {type(result).__name__}")
        if isinstance(result, dict):
            print(f"      result keys: {list(result.keys())[:10]}")
    except Exception as e:
        # fail-loud: a crash is a finding, not a silent pass
        check("process_query() ran", False, f"{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # 5. EXPLICIT FINDING (not a failure): observe() does not invoke l2_service
    print("\n=== FINDING (scope-adjacent, not a test failure) ===")
    obs_src = None
    try:
        import inspect
        src = inspect.getsource(obs.observe)
        invokes = "self.l2_service." in src or "l2_service(" in src
        print(f"      LearningObserver.observe() invokes l2_service: {invokes}")
        if not invokes:
            print("      -> observer STORES l2_service but does NOT call it in observe().")
            print("         A query therefore does not yet produce L2 audit output from within")
            print("         observe(). Wiring is complete (factory->observer->functional instance);")
            print("         INVOCATION belongs to Mutation 3 / Phase 5B (L2 enrichment, out of scope here).")
    except Exception as e:
        print(f"      (could not inspect observe(): {e})")

    print("\n=== Mutation 2 wiring verdict ===")
    if FAILS:
        print(f"FAILURES: {FAILS}")
        raise SystemExit(1)
    print("WIRING VERIFIED: factory produces real L2WorkingTheoryService, observer receives it,")
    print("service is functional. (observe()-invocation gap noted above as out-of-scope finding.)")


if __name__ == "__main__":
    main()
