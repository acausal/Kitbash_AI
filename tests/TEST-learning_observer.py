#!/usr/bin/env python3
"""
TEST-learning_observer.py  (SPEC Step 2 / T3 acceptance)

Stub-based contract tests for LearningObserver. No torch required — the MTR
engine, state manager, and grain pipeline are lightweight stubs that mimic the
real call shapes. Each B-fix has a dedicated regression test.

Run:  python TEST-learning_observer.py
This is ad-hoc acceptance for T3 (NOT the permanent gate; that is T7).
"""

import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from learning_observer import LearningObserver, LearningReport


# --------------------------------------------------------------------------- #
# Stubs (mimic the real call shapes, no torch)
# --------------------------------------------------------------------------- #
@dataclass
class Ctx:
    hat: Any = None
    project_context: str = "demo_project"


class StubMTR:
    """mimics KitbashMTREngine.__call__ -> (logits, error_signal, new_state)."""
    d_model = 64
    d_state = 16

    def __init__(self):
        self.calls = 0

    def __call__(self, token_ids, state=None, kappa=1.0):
        self.calls += 1
        err = _Meanable([0.1])  # error_signal with .mean()
        return ([1, 2, 3], err, {"time": self.calls})


class _Meanable:
    def __init__(self, v):
        self.v = v

    def mean(self):
        return sum(self.v) / len(self.v)


class StubStateManager:
    def __init__(self):
        self.saved = []

    def save(self, mtr_state, d_model, d_state, session_id="default", metadata=None):
        self.saved.append((mtr_state, session_id, metadata))

    def load(self, device="cpu"):
        return ({"time": 99}, {})


class StubCartridge:
    def __init__(self):
        self.used = []

    def log_fact_usage(self, fact_id, success, mtr_error, context):
        self.used.append((fact_id, success, mtr_error, context))


class StubGrainRouter:
    def __init__(self):
        self.outcomes = []
        self.usages = []
        self.activated = []

    def log_grain_outcome(self, grain_id, mtr_error):
        self.outcomes.append((grain_id, mtr_error))

    def log_grain_usage(self, grain_id, success, mtr_error, context):
        self.usages.append((grain_id, success, mtr_error, context))

    def activate_grains(self, grain_ids):
        self.activated.extend(grain_ids)
        return {"loaded": len(grain_ids)}


class StubPipeline:
    def __init__(self):
        self.advance_calls = 0
        self.process_calls = 0

    def advance_phantom_cycle(self):
        self.advance_calls += 1

    def process_mtr_query(self, fact_ids, query_tokens, error_signal,
                          epistemic_snapshot, hat=None, dissonance_result=None):
        self.process_calls += 1
        return {"crystallization": {"crystallized_grains": [{"grain_id": "sg_test"}]}}


class StubDreamBucket:
    def __init__(self):
        self.records = []

    def append(self, log_type, record):
        self.records.append((log_type, record))
        return True


# --------------------------------------------------------------------------- #
# Test harness
# --------------------------------------------------------------------------- #
results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def make_observer(pipeline=None, dream=None, grain=None, mtr=None):
    return LearningObserver(
        mtr_engine=mtr or StubMTR(),
        state_manager=StubStateManager(),
        cartridge_engine=StubCartridge(),
        grain_router=grain or StubGrainRouter(),
        mtr_grain_pipeline=pipeline,
        l2_service=None,
        dream_bucket_writer=dream,
        crystallization_interval=51,
    )


def summarize():
    return sum(1 for _, ok, _ in results if ok), len(results)


# --------------------------------------------------------------------------- #
# B1: counter increments exactly once per query
# --------------------------------------------------------------------------- #
def test_B1():
    obs = make_observer()
    for _ in range(3):
        obs.observe("q1", "what is x?", Ctx(),
                    {"answered": True, "engine_name": "CARTRIDGE",
                     "confidence": 0.8, "fact_ids": {1}, "grain_ids": []})
    check("B1: query_count == 3 after 3 observe() calls (no double increment)",
          obs.query_count == 3, f"query_count={obs.query_count}")


# --------------------------------------------------------------------------- #
# B2: phantom cycle advances exactly once per query
# --------------------------------------------------------------------------- #
def test_B2():
    pipe = StubPipeline()
    obs = make_observer(pipeline=pipe)
    obs.observe("q1", "what is x?", Ctx(),
                {"answered": True, "engine_name": "CARTRIDGE",
                 "confidence": 0.8, "fact_ids": {1}, "grain_ids": ["sg_a"]})
    check("B2: advance_phantom_cycle called exactly ONCE per query",
          pipe.advance_calls == 1, f"advance_calls={pipe.advance_calls}")


# --------------------------------------------------------------------------- #
# B3: trace path executes without AttributeError (project_context, guarded)
# --------------------------------------------------------------------------- #
def test_B3():
    dream = StubDreamBucket()
    obs = make_observer(dream=dream)
    # Ctx has project_context (not project) -> must not crash.
    rep = obs.observe("q1", "what is x?", Ctx(project_context="projZ"),
                      {"answered": True, "engine_name": "CARTRIDGE",
                       "confidence": 0.8, "fact_ids": {1}, "grain_ids": []})
    traces = [r for (lt, r) in dream.records if lt == "traces"]
    check("B3: trace path executes, uses project_context (no AttributeError)",
          rep.trace_logged and traces and traces[0]["project_context"] == "projZ",
          f"trace_logged={rep.trace_logged}, project={traces[0]['project_context'] if traces else None}")


# --------------------------------------------------------------------------- #
# B4: chain length equals THIS query's items only (not unbounded history)
# --------------------------------------------------------------------------- #
def test_B4():
    dream = StubDreamBucket()
    obs = make_observer(dream=dream)
    obs.observe("q1", "query one", Ctx(),
                {"answered": True, "engine_name": "CARTRIDGE",
                 "confidence": 0.8, "fact_ids": {1, 2}, "grain_ids": ["sg_a"]})
    obs.observe("q2", "query two", Ctx(),
                {"answered": True, "engine_name": "CARTRIDGE",
                 "confidence": 0.8, "fact_ids": {3}, "grain_ids": ["sg_b"]})
    last = [r for (lt, r) in dream.records if lt == "traces"][-1]
    chain = last["chain"]
    ok = (sorted(chain["fact_ids"]) == [3]) and (chain["grain_ids"] == ["sg_b"]) \
        and chain["chain_type"] == "intra_query"
    check("B4: per-query chain = this query's items only (no accumulated history)",
          ok, f"chain={chain}")


# --------------------------------------------------------------------------- #
# B5: confidence == 1 - error (single definition)
# --------------------------------------------------------------------------- #
def test_B5():
    obs = make_observer()
    rep = obs.observe("q1", "what is x?", Ctx(),
                      {"answered": True, "engine_name": "CARTRIDGE",
                       "confidence": 0.8, "fact_ids": {1}, "grain_ids": []})
    # StubMTR returns error_signal mean 0.1 -> confidence must be 0.9
    ok = abs(rep.mtr_confidence - 0.9) < 1e-6
    check("B5: mtr_confidence == 1 - error (single definition, computed once)",
          ok, f"mtr_confidence={rep.mtr_confidence:.4f} (expected 0.9)")


# --------------------------------------------------------------------------- #
# B6: hat serialized as string (never raw object)
# --------------------------------------------------------------------------- #
class FakeHat:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return f"Hat({self.name})"


def test_B6():
    dream = StubDreamBucket()
    obs = make_observer(dream=dream)
    rep = obs.observe("q1", "what is x?", Ctx(hat=FakeHat("rigid")),
                      {"answered": True, "engine_name": "CARTRIDGE",
                       "confidence": 0.8, "fact_ids": {1}, "grain_ids": []})
    trace = [r for (lt, r) in dream.records if lt == "traces"][-1]
    hat_val = trace["hat"]
    ok = rep.trace_logged and isinstance(hat_val, str) and hat_val == "Hat(rigid)"
    check("B6: hat serialized as str(hat), never raw object",
          ok, f"hat={hat_val!r}")


# --------------------------------------------------------------------------- #
# Misses are observed too (SPEC §3.1): exhausted query still runs pipeline
# --------------------------------------------------------------------------- #
def test_miss_observed():
    pipe = StubPipeline()
    dream = StubDreamBucket()
    obs = make_observer(pipeline=pipe, dream=dream)
    rep = obs.observe("q1", "unknown thing?", Ctx(),
                      {"answered": False, "engine_name": None,
                       "confidence": 0.0, "fact_ids": set(), "grain_ids": []})
    traces = [r for (lt, r) in dream.records if lt == "traces"]
    # Pipeline ran (advance + process) AND a miss trace was logged.
    ok = pipe.advance_calls == 1 and pipe.process_calls == 1 and len(traces) == 1
    check("Miss observed: exhausted query still runs pipeline + logs trace",
          ok, f"advance={pipe.advance_calls}, process={pipe.process_calls}, traces={len(traces)}")


# --------------------------------------------------------------------------- #
# Fail-loud stubs (gate must trip: error_signal mean > 0.5)
# --------------------------------------------------------------------------- #
class StubMTRHighError:
    """Mimics KitbashMTREngine.__call__ -> (logits, error_signal, new_state)
    with error_signal mean > 0.5 so the dissonance gate (mtr_error > 0.5) trips."""
    d_model = 64
    d_state = 16

    def __init__(self):
        self.calls = 0

    def __call__(self, token_ids, state=None, kappa=1.0):
        self.calls += 1
        err = _Meanable([0.6])  # error_signal mean 0.6 -> gate trips
        return ([1, 2, 3], err, {"time": self.calls})


class RaisingDreamBucket:
    """append() raises ONLY for the violations log_type — exercises the
    fail-loud exception path while leaving trace logging (a separate append)
    able to run, matching the spec's 'trace path still ran' requirement."""
    def __init__(self):
        self.records = []

    def append(self, log_type, record):
        if log_type == "violations":
            raise RuntimeError("simulated queue failure")
        self.records.append((log_type, record))
        return True


class BackpressureDreamBucket:
    """append() returns False — exercises the fail-loud backpressure path."""
    def __init__(self):
        self.records = []

    def append(self, log_type, record):
        return False


class CapturingDreamBucket:
    """append() records the emitted record so tests can inspect it."""
    def __init__(self):
        self.records = []

    def append(self, log_type, record):
        self.records.append((log_type, record))
        return True


# --------------------------------------------------------------------------- #
# Fail-loud / determinism (SPEC_OBSERVER_FAIL_LOUD.md, Step 4)
# --------------------------------------------------------------------------- #
def test_fail_loud_exception():
    """Writer.append raises -> violation_error set, report.error None,
    trace path still ran, observe() does not raise."""
    dream = RaisingDreamBucket()
    obs = make_observer(dream=dream, mtr=StubMTRHighError())
    rep = None
    try:
        rep = obs.observe("q1", "what is x?", Ctx(),
                          {"answered": True, "engine_name": "CARTRIDGE",
                           "confidence": 0.8, "fact_ids": {1}, "grain_ids": []})
    except Exception as e:
        check("Fail-loud on exception: observe() did NOT raise",
              False, f"raised {type(e).__name__}: {e}")
        return
    ok = (rep.violation_error is not None
          and rep.error is None
          and rep.trace_logged is True
          and not rep.violation_emitted)
    check("Fail-loud on exception: violation_error set, error=None, trace ran, no raise",
          ok, f"violation_error={rep.violation_error!r}, error={rep.error}, "
              f"trace_logged={rep.trace_logged}, emitted={rep.violation_emitted}")


def test_fail_loud_backpressure():
    """Writer.append returns False -> violation_error mentions backpressure,
    violation_emitted is False."""
    dream = BackpressureDreamBucket()
    obs = make_observer(dream=dream, mtr=StubMTRHighError())
    rep = obs.observe("q1", "what is x?", Ctx(),
                      {"answered": True, "engine_name": "CARTRIDGE",
                       "confidence": 0.8, "fact_ids": {1}, "grain_ids": []})
    ok = (rep.violation_error is not None
          and "backpressure" in rep.violation_error
          and rep.violation_emitted is False)
    check("Fail-loud on backpressure: violation_error mentions backpressure, emitted False",
          ok, f"violation_error={rep.violation_error!r}, emitted={rep.violation_emitted}")


def test_determinism_fact_attribution():
    """result_summary fact_ids={9,3,5} -> emitted record returned_fact_id == 3
    (min()), deterministic across runs. violation_emitted True."""
    dream = CapturingDreamBucket()
    obs = make_observer(dream=dream, mtr=StubMTRHighError())
    rep = obs.observe("q1", "what is x?", Ctx(),
                      {"answered": True, "engine_name": "CARTRIDGE",
                       "confidence": 0.8, "fact_ids": {9, 3, 5}, "grain_ids": []})
    violations = [r for (lt, r) in dream.records if lt == "violations"]
    ok = (len(violations) == 1
          and violations[0].get("returned_fact_id") == 3
          and rep.violation_emitted is True)
    check("Determinism: returned_fact_id == min(fact_ids) == 3 (reproducible)",
          ok, f"emitted_fact_id={violations[0].get('returned_fact_id') if violations else None}, "
              f"violation_emitted={rep.violation_emitted}")


# --------------------------------------------------------------------------- #
def main():
    test_B1()
    test_B2()
    test_B3()
    test_B4()
    test_B5()
    test_B6()
    test_miss_observed()
    test_fail_loud_exception()
    test_fail_loud_backpressure()
    test_determinism_fact_attribution()
    passed, total = summarize()
    print("=" * 60)
    print(f"T3 LearningObserver: {passed}/{total} PASS")
    print("=" * 60)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
