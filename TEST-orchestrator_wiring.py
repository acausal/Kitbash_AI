#!/usr/bin/env python3
"""
TEST-orchestrator_wiring.py  (SPEC Step 3 / T4 acceptance)

Verifies the LearningObserver is correctly wired into the posix orchestrator:

  - orchestrator accepts learning_observer= and stores it
  - QueryResult.learning_report is populated (not None) after a query
  - the deprecated _record_phantom_hit stub is GONE (no double-recording):
    a stub shannon records ZERO phantom hits even on a winning response
  - observer failure is LOUD: a broken observer does not crash answering,
    but its error is recorded on the result + the diagnostic feed (no bare pass)

Runs with stub engines / stub observer (torch / redis NOT required).
Run:  python TEST-orchestrator_wiring.py
This is ad-hoc acceptance for T4 (NOT the permanent gate; that is T7).
"""

import sys
import types
from typing import Optional

sys.path.insert(0, ".")

from query_orchestrator_posix import QueryOrchestrator, QueryResult, LayerAttempt


# --------------------------------------------------------------------------- #
# Stubs
# --------------------------------------------------------------------------- #
class StubTriage:
    def decide(self, req):
        class D:
            layer_sequence = ["CARTRIDGE"]
            confidence_thresholds = {"CARTRIDGE": 0.70}
            reasoning = "stub"
        return D()


class StubResp:
    def __init__(self, answer, confidence, engine_name="CARTRIDGE", metadata=None):
        self.answer = answer
        self.confidence = confidence
        self.engine_name = engine_name
        self.metadata = metadata or {}


class StubEngine:
    def __init__(self, name):
        self.name = name

    def infer(self, request):
        # Always pass the CARTRIDGE threshold (0.70)
        return StubResp("stub answer", 0.9, self.name,
                        metadata={"fact_id": 42, "grain_id": "sg_x"})


class StubMamba:
    def get_context(self, req):
        return {}


class StubResonance:
    weights = {}

    def record_pattern(self, h, metadata=None):
        pass

    def reinforce_pattern(self, h):
        pass


class StubHeartbeat:
    turn_number = 0

    def pause(self, priority=None):
        pass

    def resume(self):
        pass

    def advance_turn(self):
        return 1


class StubShannon:
    """Detects any leftover phantom-hit recording (the removed stub)."""
    def __init__(self):
        self.phantom_hits = 0

    def record_phantom_hit(self, **kw):
        self.phantom_hits += 1


class RecordingObserver:
    """Mimics LearningObserver.observe() -> LearningReport-like object."""
    def __init__(self):
        self.calls = 0
        self.last_summary = None

    def observe(self, query_id, user_query, context, result_summary):
        self.calls += 1
        self.last_summary = result_summary
        return types.SimpleNamespace(
            mtr_error=0.1, mtr_confidence=0.9, crystallization=None,
            trace_logged=True, latency_ms=1.0, error=None,
        )


class BrokenObserver:
    """Proves loud failure isolation: raises, must not crash answering."""
    def observe(self, query_id, user_query, context, result_summary):
        raise RuntimeError("observer exploded")


class RecordingFeed:
    """Captures feed.log_error to prove the observer failure is LOUD."""
    def __init__(self):
        self.errors = []

    def __getattr__(self, name):
        # swallow all the other log_* calls
        return lambda *a, **k: None

    def log_error(self, query_id, component, msg):
        self.errors.append((component, msg))


# --------------------------------------------------------------------------- #
# Harness
# --------------------------------------------------------------------------- #
results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def build_orchestrator(observer=None, shannon=None):
    orch = QueryOrchestrator(
        triage_agent=StubTriage(),
        engines={"CARTRIDGE": StubEngine("CARTRIDGE")},
        mamba_service=StubMamba(),
        resonance=StubResonance(),
        heartbeat=StubHeartbeat(),
        shannon=shannon,
        learning_observer=observer,
    )
    # Isolate from unrelated repo drift:
    #  - orchestrator builds MambaContextRequest(query=...) / InferenceRequest(query=...)
    #    but those dataclasses have no `query` field (pre-existing, out of T4 scope).
    # Force a CARTRIDGE-winning cascade so the learning_summary assembly
    # (fact_id/grain_id) is exercised end-to-end.
    orch._get_mamba_context = lambda *a, **k: {}
    class _Dec:
        layer_sequence = ["CARTRIDGE"]
        confidence_thresholds = {"CARTRIDGE": 0.70}
        reasoning = "stub"
    orch._get_triage_decision = lambda *a, **k: _Dec()
    def _attempt_layer(self, layer_name, threshold, user_query, context, decision, query_id):
        resp = StubResp("stub answer", 0.9, "CARTRIDGE",
                        metadata={"fact_id": 42, "grain_id": "sg_x"})
        attempt = LayerAttempt(engine_name=layer_name, confidence=0.9,
                              threshold=threshold, passed=True, latency_ms=1.0)
        return attempt, resp
    orch._attempt_layer = _attempt_layer.__get__(orch, QueryOrchestrator)
    return orch


def test_wiring_present_and_report_surfaced():
    obs = RecordingObserver()
    shannon = StubShannon()
    orch = build_orchestrator(observer=obs, shannon=shannon)
    check("orchestrator stores learning_observer", orch.learning_observer is obs)

    result = orch.process_query("what is photosynthesis?")
    check("QueryResult.learning_report is populated (not None)",
          result.learning_report is not None,
          f"report={result.learning_report}")
    check("observer.observe() was called exactly once",
          obs.calls == 1, f"calls={obs.calls}")
    check("observer received answered=True summary",
          obs.last_summary.get("answered") is True,
          f"answered={obs.last_summary.get('answered') if obs.last_summary else None}")
    # Key anti-regression: _record_phantom_hit removed -> shannon gets ZERO hits
    check("no phantom double-record (stub shannon hit count == 0)",
          shannon.phantom_hits == 0, f"phantom_hits={shannon.phantom_hits}")
    check("_record_phantom_hit method removed from class",
          not hasattr(QueryOrchestrator, "_record_phantom_hit"))


def test_learning_report_none_when_no_observer():
    orch = build_orchestrator(observer=None)
    result = orch.process_query("hello?")
    check("learning_report is None when no observer supplied",
          result.learning_report is None, f"report={result.learning_report}")


def test_loud_failure_isolation():
    feed = RecordingFeed()
    orch = QueryOrchestrator(
        triage_agent=StubTriage(),
        engines={"CARTRIDGE": StubEngine("CARTRIDGE")},
        mamba_service=StubMamba(),
        resonance=StubResonance(),
        heartbeat=StubHeartbeat(),
        shannon=None,
        learning_observer=BrokenObserver(),
    )
    # monkeypatch feed to capture loud errors
    orch.feed = feed
    orch._get_mamba_context = lambda *a, **k: {}
    class _Dec:
        layer_sequence = ["CARTRIDGE"]
        confidence_thresholds = {"CARTRIDGE": 0.70}
        reasoning = "stub"
    orch._get_triage_decision = lambda *a, **k: _Dec()
    def _attempt_layer(self, layer_name, threshold, user_query, context, decision, query_id):
        resp = StubResp("stub answer", 0.9, "CARTRIDGE",
                        metadata={"fact_id": 42, "grain_id": "sg_x"})
        attempt = LayerAttempt(engine_name=layer_name, confidence=0.9,
                              threshold=threshold, passed=True, latency_ms=1.0)
        return attempt, resp
    orch._attempt_layer = _attempt_layer.__get__(orch, QueryOrchestrator)
    result = orch.process_query("trigger broken observer")
    # answering must still succeed
    check("answering succeeds despite broken observer",
          result.answer is not None and result.confidence > 0,
          f"answer={result.answer!r}")
    # but the failure is LOUD: recorded on result + feed (no bare pass)
    check("broken observer error surfaced on learning_report",
          isinstance(result.learning_report, dict)
          and "error" in result.learning_report,
          f"report={result.learning_report}")
    check("broken observer error LOUD in diagnostic feed",
          any(c == "LEARNING_OBSERVER" for c, _ in feed.errors),
          f"feed_errors={feed.errors}")


def main():
    test_wiring_present_and_report_surfaced()
    test_learning_report_none_when_no_observer()
    test_loud_failure_isolation()
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("=" * 60)
    print(f"T4 orchestrator wiring: {passed}/{total} PASS")
    print("=" * 60)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
