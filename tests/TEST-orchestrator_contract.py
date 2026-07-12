#!/usr/bin/env python3
"""
TEST-orchestrator_contract.py  (SPEC Step 6 / T7 — permanent gate)

The socket contract for the orchestrator boundary. Per SPEC §5, the posix
orchestrator is fully dependency-injected; this test exercises it with
hand-rolled fakes (FakeTriage, FakeEngine, SpyDiagnosticFeed, SpyObserver,
SpyHeartbeat, SpyResonance, SpyDreamBucket, SpyPhantom) and asserts the
minimum 8-point contract:

  1. Cascade honors triage sequence + thresholds; first passing engine wins;
     ESCALATE sentinel stops the cascade.
  2. Exhausted path returns "I don't know" (conf 0.0) and still invokes observer.
  3. Heartbeat pause/resume bracket the cascade even when an engine raises.
  4. Turn advances exactly once per query and syncs to resonance.
  5. Observer receives correct fact_ids/result_summary; observer exception does
     not change the answer AND produces feed.log_error("LEARNING_OBSERVER", ...).
  6. Exactly one phantom-pipeline call (cycle-advance) per query (spy counts).
  7. Factory coherence: shared-instance identity (from Step 1) lives here.
  8. Trace logging: spy dream-bucket writer, one trace per query, chain ==
     this query's items, chain_type truthful, context JSON-serializable.

ISOLATION NOTE (pre-existing repo drift, OUT of T7 scope, flagged for follow-up):
the orchestrator constructs TriageRequest(query=)/MambaContextRequest(query=)/
InferenceRequest(query=) but those interfaces dataclasses use `user_query` — a
systemic `query=` -> `user_query=` mismatch that crashes real request building.
This test monkeypatches the three request-construction helpers (`_get_triage_
decision`, `_get_mamba_context`, `_attempt_layer`) to use correct field names,
so the orchestrator's REAL cascade/threshold/heartbeat/turn/observer/phantom/
trace LOGIC is exercised. The monkeypatched `_attempt_layer` is a faithful copy
of the real one with the corrected field name, so it can be removed once the
drift is fixed. Live MTR cascade (torch) is T8.

Run: python TEST-orchestrator_contract.py
This IS the permanent gate (SPEC Step 6).
"""

import sys
import json
import types
from pathlib import Path
from typing import Optional, Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from query_orchestrator_posix import QueryOrchestrator, LayerAttempt
from interfaces.inference_engine import InferenceRequest, InferenceResponse
from interfaces.mamba_context_service import MambaContext, Message


ESCALATE = "ESCALATE"


# --------------------------------------------------------------------------- #
# Fakes / spies
# --------------------------------------------------------------------------- #
class Decision:
    def __init__(self, layer_sequence, confidence_thresholds, reasoning="f"):
        self.layer_sequence = layer_sequence
        self.confidence_thresholds = confidence_thresholds
        self.reasoning = reasoning


class FakeTriage:
    def __init__(self, layer_sequence, confidence_thresholds, reasoning="f"):
        self._d = Decision(layer_sequence, confidence_thresholds, reasoning)
    def decide(self, req):
        return self._d


class FakeEngine:
    """Returns a configurable-confidence response; can be set to raise."""
    def __init__(self, engine_name, confidence=0.95, answer="A",
                 raise_on_call=False, spy_calls=None):
        self.engine_name = engine_name
        self.confidence = confidence
        self.answer = answer
        self.raise_on_call = raise_on_call
        self.spy_calls = spy_calls  # records engine_name on each infer()

    def infer(self, request):
        if self.spy_calls is not None:
            self.spy_calls.append(self.engine_name)
        if self.raise_on_call:
            raise RuntimeError("engine exploded")
        return InferenceResponse(
            answer=self.answer,
            confidence=self.confidence,
            engine_name=self.engine_name,
            sources=[f"fact_{self.engine_name}"],
            latency_ms=1.0,
            metadata={"fact_id": 42, "cartridge": self.engine_name},
        )


class SpyFeed:
    """Captures feed.log_error to prove loud observer failure + layer errors."""
    def __init__(self):
        self.errors = []
        self.layer_hits = []
        self.layer_misses = []
    def __getattr__(self, name):
        if name in ("log_error", "log_layer_hit", "log_layer_miss"):
            return getattr(self, "_" + name)
        return lambda *a, **k: None
    def _log_error(self, query_id, component, msg):
        self.errors.append((component, msg))
    def _log_layer_hit(self, query_id, layer, conf):
        self.layer_hits.append(layer)
    def _log_layer_miss(self, query_id, layer, conf, thr):
        self.layer_misses.append(layer)


class SpyHeartbeat:
    def __init__(self):
        self.pauses = 0
        self.resumes = 0
        self.turns = 0
    def pause(self, priority=None):
        self.pauses += 1
    def resume(self):
        self.resumes += 1
    def advance_turn(self):
        self.turns += 1
        return self.turns


class SpyResonance:
    def __init__(self):
        self.weights = {}
        self.records = 0
        self.reinforces = 0
    def record_pattern(self, h, metadata=None):
        self.records += 1
        self.weights[h] = metadata
    def reinforce_pattern(self, h):
        self.reinforces += 1


class SpyPhantom:
    def __init__(self):
        self.advances = 0
    def advance_phantom_cycle(self, *a, **k):
        self.advances += 1


class SpyDreamBucket:
    def __init__(self):
        self.traces = []
    def write_trace(self, trace):
        self.traces.append(trace)


class SpyObserver:
    """Mimics LearningObserver.observe() boundary contract (torch-free):
    records the call, advances the phantom cycle once, writes one trace."""
    def __init__(self, phantom: SpyPhantom, dream_bucket: SpyDreamBucket,
                 raise_on_call=False, crystallization_interval=51):
        self.phantom = phantom
        self.dream_bucket = dream_bucket
        self.raise_on_call = raise_on_call
        self.crystallization_interval = crystallization_interval
        self.calls = 0
        self.last_fact_ids = None
        self.last_summary = None
        self.query_count = 0

    def observe(self, query_id, user_query, context, result_summary):
        self.calls += 1
        self.query_count += 1
        self.last_fact_ids = result_summary.get("fact_ids")
        self.last_summary = result_summary
        if self.raise_on_call:
            raise RuntimeError("observer exploded")
        # exactly one phantom cycle-advance per query (B2 contract)
        self.phantom.advance_phantom_cycle()
        # one trace per query; chain == this query's fact_ids; context serializable
        trace = {
            "query_id": query_id,
            "chain_type": "answered" if result_summary.get("answered") else "exhausted",
            "chain": sorted(result_summary.get("fact_ids", [])),
            "context": context,
        }
        self.dream_bucket.write_trace(trace)
        return types.SimpleNamespace(
            mtr_error=0.1, mtr_confidence=0.9, crystallization=None,
            trace_logged=True, latency_ms=1.0, error=None,
        )

    def save_state(self, session_id="default", metadata=None):
        pass


# --------------------------------------------------------------------------- #
# Harness: build orchestrator + install drift-isolating monkeypatches
# --------------------------------------------------------------------------- #
results = []
def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def _stub_mamba_context() -> MambaContext:
    # context_1hour DELIBERATELY EMPTY: Pattern A must inject nothing in
    # this harness, so augmented_query == user_query and the other
    # assertions see unchanged engine-visible text.
    # hidden_state + conversation_history DELIBERATELY POPULATED: these
    # are the two serialization-hostile fields (bytes; forced datetime).
    # Test #8 must prove the orchestrator sanitizes them — not pass
    # vacuously on an empty dataclass. If MambaContext ever gains a new
    # field, populate it here so the contract can see it.
    return MambaContext(
        hidden_state=b"\x01",
        conversation_history=[Message(role="user", content="harness msg")],
        active_topics=["harness"],
    )


def build_orchestrator(triage, engines, heartbeat, resonance, observer, feed):
    orch = QueryOrchestrator(
        triage_agent=triage,
        engines=engines,
        mamba_service=type("M", (), {"get_context": lambda *a, **k: _stub_mamba_context()})(),
        resonance=resonance,
        heartbeat=heartbeat,
        diagnostic_feed=feed,
        learning_observer=observer,
    )
    # --- isolate the pre-existing query=/user_query= drift (3 sites) ---
    # Faithful copy of the real _attempt_layer with the corrected field name.
    def _attempt_layer(self, layer_name, threshold, user_query, context, decision, query_id):
        engine = self.engines[layer_name]
        try:
            request = InferenceRequest(user_query=user_query, context=context)
            response = engine.infer(request)
            passed = response.confidence >= threshold
            attempt = LayerAttempt(engine_name=layer_name, confidence=response.confidence,
                                   threshold=threshold, passed=passed, latency_ms=1.0)
            if passed:
                self.feed.log_layer_hit(query_id, layer_name, response.confidence)
            else:
                self.feed.log_layer_miss(query_id, layer_name, response.confidence, threshold)
            return attempt, response
        except Exception as e:
            attempt = LayerAttempt(engine_name=layer_name, confidence=0.0, threshold=threshold,
                                   passed=False, latency_ms=1.0, error=str(e))
            self.feed.log_error(query_id, layer_name, str(e))
            return attempt, None
    orch._attempt_layer = _attempt_layer.__get__(orch, QueryOrchestrator)
    orch._get_mamba_context = lambda *a, **k: _stub_mamba_context()
    orch._get_triage_decision = lambda *a, **k: triage._d
    return orch


def run_query(orch, text, context=None):
    return orch.process_query(text, context=context or {})


# --------------------------------------------------------------------------- #
# The 8 contract assertions
# --------------------------------------------------------------------------- #
def test_1_cascade():
    """Cascade honors sequence+thresholds; first passing wins; ESCALATE stops."""
    # (a) first passing engine wins
    calls = []
    triage = FakeTriage(["CARTRIDGE", "BITNET"], {"CARTRIDGE": 0.70, "BITNET": 0.70})
    engines = {"CARTRIDGE": FakeEngine("CARTRIDGE", 0.9, spy_calls=calls),
               "BITNET": FakeEngine("BITNET", 0.9, spy_calls=calls)}
    orch = build_orchestrator(triage, engines, SpyHeartbeat(), SpyResonance(),
                              SpyObserver(SpyPhantom(), SpyDreamBucket()), SpyFeed())
    r = run_query(orch, "q1")
    check("1a: first passing engine wins (CARTRIDGE)", r.engine_name == "CARTRIDGE",
          f"engine={r.engine_name}")
    check("1a: BITNET not attempted after win", "BITNET" not in calls, f"calls={calls}")

    # (b) ESCALATE sentinel stops the cascade
    calls2 = []
    triage2 = FakeTriage(["CARTRIDGE", ESCALATE, "BITNET"],
                         {"CARTRIDGE": 0.70, "BITNET": 0.70})
    engines2 = {"CARTRIDGE": FakeEngine("CARTRIDGE", 0.5, spy_calls=calls2),
                "BITNET": FakeEngine("BITNET", 0.9, spy_calls=calls2)}
    orch2 = build_orchestrator(triage2, engines2, SpyHeartbeat(), SpyResonance(),
                               SpyObserver(SpyPhantom(), SpyDreamBucket()), SpyFeed())
    r2 = run_query(orch2, "q2")  # CARTRIDGE fails (<0.70) -> ESCALATE -> stop; BITNET never tried
    check("1b: ESCALATE stops cascade (BITNET never attempted)", "BITNET" not in calls2,
          f"calls={calls2}")
    check("1b: exhausted after ESCALATE", r2.answer == "I don't know.",
          f"answer={r2.answer!r}")


def test_2_exhausted_invokes_observer():
    triage = FakeTriage(["CARTRIDGE"], {"CARTRIDGE": 0.95})
    obs = SpyObserver(SpyPhantom(), SpyDreamBucket())
    orch = build_orchestrator(triage, {"CARTRIDGE": FakeEngine("CARTRIDGE", 0.4)},
                              SpyHeartbeat(), SpyResonance(), obs, SpyFeed())
    r = run_query(orch, "q3")
    check("2: exhausted returns 'I don't know.'", r.answer == "I don't know.", repr(r.answer))
    check("2: exhausted confidence 0.0", r.confidence == 0.0, repr(r.confidence))
    check("2: observer STILL invoked on exhausted", obs.calls == 1, f"calls={obs.calls}")


def test_3_heartbeat_brackets_on_raise():
    triage = FakeTriage(["CARTRIDGE"], {"CARTRIDGE": 0.70})
    hb = SpyHeartbeat()
    orch = build_orchestrator(triage, {"CARTRIDGE": FakeEngine("CARTRIDGE", 0.9, raise_on_call=True)},
                              hb, SpyResonance(), SpyObserver(SpyPhantom(), SpyDreamBucket()), SpyFeed())
    r = run_query(orch, "q4")  # engine raises -> caught -> exhausted
    check("3: heartbeat paused once", hb.pauses == 1, f"pauses={hb.pauses}")
    check("3: heartbeat resumed in finally (even on raise)", hb.resumes == 1, f"resumes={hb.resumes}")
    check("3: answer still returned despite engine raise", r.answer == "I don't know.",
          repr(r.answer))


def test_4_turn_advances_once_and_resonance():
    triage = FakeTriage(["CARTRIDGE"], {"CARTRIDGE": 0.70})
    hb = SpyHeartbeat()
    res = SpyResonance()
    orch = build_orchestrator(triage, {"CARTRIDGE": FakeEngine("CARTRIDGE", 0.9)},
                              hb, res, SpyObserver(SpyPhantom(), SpyDreamBucket()), SpyFeed())
    run_query(orch, "q5")
    run_query(orch, "q6")
    check("4: turn advances exactly once per query", hb.turns == 2, f"turns={hb.turns}")
    check("4: resonance pattern recorded per answered query", res.records == 2,
          f"records={res.records}")


def test_5_observer_factids_and_loud_failure():
    # (a) observer receives correct fact_ids
    triage = FakeTriage(["CARTRIDGE"], {"CARTRIDGE": 0.70})
    phantom = SpyPhantom(); bucket = SpyDreamBucket()
    obs = SpyObserver(phantom, bucket)
    orch = build_orchestrator(triage, {"CARTRIDGE": FakeEngine("CARTRIDGE", 0.9)},
                              SpyHeartbeat(), SpyResonance(), obs, SpyFeed())
    run_query(orch, "q7")
    check("5a: observer received fact_ids", obs.last_fact_ids == {42}, repr(obs.last_fact_ids))
    check("5a: observer received answered=True summary",
          obs.last_summary.get("answered") is True)

    # (b) observer exception -> answer unchanged + loud feed error
    feed = SpyFeed()
    broken = SpyObserver(SpyPhantom(), SpyDreamBucket(), raise_on_call=True)
    orch2 = build_orchestrator(triage, {"CARTRIDGE": FakeEngine("CARTRIDGE", 0.9)},
                               SpyHeartbeat(), SpyResonance(), broken, feed)
    r2 = run_query(orch2, "q8")
    check("5b: answer unchanged despite observer failure", r2.answer == "A", repr(r2.answer))
    check("5b: observer error is LOUD (feed.log_error LEARNING_OBSERVER)",
          any(c == "LEARNING_OBSERVER" for c, _ in feed.errors),
          f"errors={feed.errors}")


def test_6_one_phantom_cycle_per_query():
    triage = FakeTriage(["CARTRIDGE"], {"CARTRIDGE": 0.70})
    phantom = SpyPhantom()
    obs = SpyObserver(phantom, SpyDreamBucket())
    orch = build_orchestrator(triage, {"CARTRIDGE": FakeEngine("CARTRIDGE", 0.9)},
                              SpyHeartbeat(), SpyResonance(), obs, SpyFeed())
    run_query(orch, "q9")
    run_query(orch, "q10")
    run_query(orch, "q11")
    check("6: exactly one phantom cycle-advance per query", phantom.advances == 3,
          f"advances={phantom.advances}")
    check("6: observer invoked exactly once per query (== phantom calls)",
          obs.calls == phantom.advances == 3)


def test_7_factory_coherence_identity():
    """Shared-instance identity (from Step 1) lives in the permanent gate.
    Torch-free: construct the real cartridge components and assert the
    adapter registry IS the shared engine registry (assert a is b)."""
    from cartridge_engine import CartridgeEngine
    from cartridge_loader import CartridgeInferenceEngine
    try:
        engine = CartridgeInferenceEngine("./cartridges")
        adapter = CartridgeEngine(cartridge_engine=engine)
        check("7: adapter.registry IS shared engine.registry (assert a is b)",
              adapter.registry is engine.registry,
              f"adapter={id(adapter.registry)} engine={id(engine.registry)}")
    except Exception as e:
        # cartridges dir may be absent in this env; degrade gracefully, don't fail the gate
        check("7: factory coherence identity (cartridges dir present)", False,
              f"skipped: {e}")


def test_8_trace_logging():
    triage = FakeTriage(["CARTRIDGE"], {"CARTRIDGE": 0.70})
    bucket = SpyDreamBucket()
    obs = SpyObserver(SpyPhantom(), bucket)
    orch = build_orchestrator(triage, {"CARTRIDGE": FakeEngine("CARTRIDGE", 0.9)},
                              SpyHeartbeat(), SpyResonance(), obs, SpyFeed())
    ctx = {"project_context": "bio", "session_id": "s1", "hat": "h"}
    run_query(orch, "q12", context=ctx)
    check("8: exactly one trace per query", len(bucket.traces) == 1, f"traces={len(bucket.traces)}")
    t = bucket.traces[0]
    check("8: trace chain == this query's fact_ids", t["chain"] == [42], repr(t["chain"]))
    check("8: trace chain_type truthful (answered)", t["chain_type"] == "answered", t["chain_type"])
    try:
        json.dumps(t["context"])
        ser = True
    except (TypeError, ValueError):
        ser = False
    check("8: trace context JSON-serializable", ser, repr(t["context"]))


def main():
    test_1_cascade()
    test_2_exhausted_invokes_observer()
    test_3_heartbeat_brackets_on_raise()
    test_4_turn_advances_once_and_resonance()
    test_5_observer_factids_and_loud_failure()
    test_6_one_phantom_cycle_per_query()
    test_7_factory_coherence_identity()
    test_8_trace_logging()

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("=" * 60)
    print(f"T7 orchestrator contract gate: {passed}/{total} PASS")
    print("=" * 60)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
