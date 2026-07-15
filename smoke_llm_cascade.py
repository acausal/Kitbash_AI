"""Smoke harness: run the Kitbash cascade through a LOCAL LLM (llama.cpp)
instead of BitNet, to test "what we have so far" with a small model.

This is a TEST SCAFFOLD (proposal Option A / ~3.1). It does NOT modify
the orchestrator or triage routing permanently — it builds the real
orchestrator via the factory (enable_llm=True) and overrides ONLY the
triage decision with a stub sequence that includes "LLM", so the live
cascade runs: GRAIN -> LLM -> CARTRIDGE -> ESCALATE.

Wiring the LLM into the real triage (_insert_bitnet equivalent) is the
separate Step-4 ticket; this harness is for live experimentation.

Usage:
    # server down (verifies fail-loud + construction):
    PYTHONPATH= .venv/Scripts/python.exe smoke_llm_cascade.py
    # server up (you stand up llama-server on :8081 with your model):
    KITBASH_LLM_URL=http://127.0.0.1:8081 \
        PYTHONPATH= .venv/Scripts/python.exe smoke_llm_cascade.py

The harness reports each query's winning engine + answer, and degrades
gracefully if the LLM server is unreachable (prints the RuntimeError
instead of crashing) so you can see the fail-loud path.
"""
from __future__ import annotations
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from interfaces.triage_agent import TriageDecision, TriageRequest
from query_orchestrator_factory import create_query_orchestrator


class _LLMStubTriage:
    """Override only the routing decision: put LLM in the cascade.

    Mirrors the shape the real RuleBasedTriageAgent would emit once the
    LLM slot is wired (proposal Step 4). Confidence threshold for LLM is
    low (0.50) so it actually fires on normal traffic — your call per
    proposal ~5.3 on the final cascade position/threshold.
    """
    def __init__(self, sequence, thresholds):
        self._seq = sequence
        self._thr = thresholds

    def route(self, request: TriageRequest) -> TriageDecision:
        return TriageDecision(
            layer_sequence=self._seq,
            confidence_thresholds=self._thr,
            reasoning="smoke-harness stub: LLM in cascade (not BitNet)",
        )


QUERIES = [
    "What is ATP synthase?",
    "How does photosynthesis work?",
    "What is the difference between mitosis and meiosis?",
    "Explain what a black hole is.",
    "Why is the sky blue?",
    "What is DNA made of?",
    "How do vaccines work?",
    "What is the speed of light?",
    "Describe the water cycle.",
    "What is the function of the mitochondria?",
]


def main():
    print("=" * 70)
    print("KITBASH -> LOCAL LLM (llama.cpp) SMOKE CASCADE")
    print("=" * 70)

    orch = create_query_orchestrator(
        enable_bitnet=False,   # no BitNet at all
        enable_llm=True,      # llama.cpp engine registered as "LLM"
        enable_grain_system=False,
        verbose=False,
    )
    print(f"Engines registered: {list(orch.engines.keys())}")
    llm = orch.engines.get("LLM")
    if llm is None:
        print("FATAL: LLM engine not registered (enable_llm=True required)")
        sys.exit(1)
    print(f"LLM server reachable now? {llm.is_available()}")

    # Override routing: GRAIN -> LLM -> CARTRIDGE -> ESCALATE
    orch.triage_agent = _LLMStubTriage(
        sequence=["GRAIN", "LLM", "CARTRIDGE", "ESCALATE"],
        thresholds={"GRAIN": 0.90, "LLM": 0.50, "CARTRIDGE": 0.70},
    )

    print("-" * 70)
    for i, q in enumerate(QUERIES, 1):
        print(f"\n[{i}/{len(QUERIES)}] Q: {q}")
        try:
            result = orch.process_query(q)
            if not result.answer:
                print("  -> NO ANSWER (cascade exhausted / all layers missed)")
            else:
                print(f"  ENGINE: {result.engine_name}  conf={result.confidence:.2f}  "
                      f"lat={result.total_latency_ms:.0f}ms")
                ans = (result.answer or "").strip().replace("\n", " ")
                print(f"  ANSWER: {ans[:300]}")
        except Exception as e:
            print(f"  -> ERROR: {type(e).__name__}: {e}")
    print("\n" + "=" * 70)
    print("SMOKE CASCADE COMPLETE")


if __name__ == "__main__":
    main()
