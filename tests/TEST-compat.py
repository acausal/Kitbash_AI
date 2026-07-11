#!/usr/bin/env python3
"""
TEST-compat.py  (SPEC Step 5 / T6 acceptance — compat shim + retired donor)

Verifies the donor's 10 importers are repointed to phase3e_compat and that the
compat facade preserves the donor API shape the importers consume:
  Phase3EOrchestrator(cartridges_dir=...) + QueryContext(query_text=...)
  process_query(ctx) -> QueryResult with .mtr_response/.mtr_confidence/
  .cartridge_facts/.grain_facts/.crystallization_report/.total_latency_ms
  + orch.mtr_state, .save_state, .get_stats, .cartridge_engine.get_stats, .close

The real factory needs torch (T8); we monkeypatch create_query_orchestrator
with a stub orchestrator matching the real interface. This verifies the SHIM
wiring (the T6 deliverable), not the live MTR cascade.

Run: python TEST-compat.py
Ad-hoc acceptance for T6 (NOT the permanent gate; that is T7).
"""

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import phase3e_compat as compat


# --------------------------------------------------------------------------- #
# Stub backing orchestrator (mirrors create_query_orchestrator's return shape)
# --------------------------------------------------------------------------- #
class _StubObserver:
    def __init__(self):
        self.mtr_state = {"time": 7, "W": None, "strength": 0.5, "copent_pos": 3}

    def save_state(self, session_id="default", metadata=None):
        self._saved = (session_id, metadata)

    def load_state(self, device=None):
        pass


class _StubEngine:
    def __init__(self):
        self.registry = types.SimpleNamespace(
            get_stats=lambda: {"cartridge_count": 4, "total_facts": 42}
        )

    def infer(self, request):
        return None


class _StubPosixResult:
    def __init__(self):
        self.answer = "stub MTR answer"
        self.confidence = 0.9
        self.engine_name = "CARTRIDGE"
        self.total_latency_ms = 12.5
        self.learning_report = {
            "mtr_error": 0.1, "mtr_confidence": 0.9,
            "crystallization": {"crystallized_grains": ["sg_x"]},
            "trace_logged": True, "latency_ms": 1.0, "error": None,
        }
        self.cartridge_facts = [{"fact_id": 42, "source": "cart_a", "confidence": 0.9}]


class _StubOrchestrator:
    def __init__(self):
        self.learning_observer = _StubObserver()
        self.engines = {"CARTRIDGE": _StubEngine()}
        self._closed = False

    def process_query(self, query_text, context=None):
        return _StubPosixResult()

    def close(self, session_id="default"):
        self._closed = True

    def get_metrics(self):
        return {"queries_total": 3, "queries_answered": 2}


# Monkeypatch the factory so we don't need torch.
compat.create_query_orchestrator = lambda **kw: _StubOrchestrator()


results = []
def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def main():
    # 1) donor-style construction
    orch = compat.Phase3EOrchestrator(cartridges_dir="./cartridges",
                                      enable_grain_system=True)
    check("Phase3EOrchestrator constructs from donor kwargs", isinstance(orch, compat.Phase3EOrchestrator))

    # 2) donor Context -> process_query -> donor-shaped QueryResult
    ctx = compat.QueryContext(query_text="What is ATP?",
                              session_id="run1", project_context="bio", hat="h")
    result = orch.process_query(ctx)
    check("process_query returns compat.QueryResult", isinstance(result, compat.QueryResult))
    check("result.mtr_response mapped from answer", result.mtr_response == "stub MTR answer", repr(result.mtr_response))
    check("result.mtr_confidence from learning_report", abs(result.mtr_confidence - 0.9) < 1e-9, repr(result.mtr_confidence))
    check("result.cartridge_facts populated", len(result.cartridge_facts) == 1 and result.cartridge_facts[0]["source"] == "cart_a")
    check("result.crystallization_report mapped", result.crystallization_report == {"crystallized_grains": ["sg_x"]})
    check("result.total_latency_ms mapped", abs(result.total_latency_ms - 12.5) < 1e-9)
    check("result.grain_facts defaults None", result.grain_facts is None)

    # 3) mtr_state accessor (donor reads time/W/strength/copent_pos)
    st = orch.mtr_state
    check("mtr_state exposes time", st.get("time") == 7)
    check("mtr_state exposes W/strength/copent_pos", "W" in st and "strength" in st and "copent_pos" in st)

    # 4) save_state / close delegate
    orch.save_state(session_id="run1", metadata={"k": 1})
    orch.close(session_id="run1")
    check("save_state+close delegate to backing orchestrator", orch._orch._closed is True)

    # 5) get_stats / cartridge_engine.get_stats delegate
    stats = orch.get_stats()
    check("get_stats delegates to backing orchestrator", stats["queries_total"] == 3)
    ces = orch.cartridge_engine.get_stats()
    check("cartridge_engine.get_stats delegates to registry", ces["total_facts"] == 42, repr(ces))

    # 6) the 10 importers are import-clean (no phase3e_orchestrator import)
    importers = ["diagnostic_phantoms.py", "debug_phantom_state.py", "debug_crystallization.py",
                 "quickcheck_with_diagnostics.py", "quickcheck_diagnostics.py", "test_integration.py",
                 "quickcheck.py", "test_phase3e.py", "test_long_run.py", "test_full_system.py"]
    bad = []
    for f in importers:
        txt = Path(f).read_text(encoding="utf-8")
        if "from phase3e_orchestrator import" in txt or "import phase3e_orchestrator" in txt:
            bad.append(f)
    check("all 10 importers repointed (no phase3e_orchestrator import)", not bad,
          ("still broken: " + ",".join(bad)) if bad else "10/10 clean")
    # and they now import from phase3e_compat
    compats = [f for f in importers if "from phase3e_compat import" in Path(f).read_text(encoding="utf-8")]
    check("all 10 importers now import from phase3e_compat", len(compats) == 10, f"{len(compats)}/10")

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("=" * 60)
    print(f"T6 compat shim: {passed}/{total} PASS")
    print("=" * 60)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
