#!/usr/bin/env python3
"""
phase3e_compat.py  (SPEC Step 5 / T6 — compat shim)

Backwards-compatible facade over the reconciled orchestrator. Lets the donor's
10 importers keep working with ZERO structural changes: they edit only their
import line, from

    from phase3e_orchestrator import Phase3EOrchestrator, QueryContext

to

    from phase3e_compat import Phase3EOrchestrator, QueryContext

and everything else (Phase3EOrchestrator(cartridges_dir=...),
QueryContext(query_text=...), process_query(ctx), .mtr_response / .mtr_confidence
/ .cartridge_facts / .grain_facts / .crystallization_report / latency fields,
.mtr_state, .save_state, .get_stats, .print_summary, .close) keeps the donor
shape, backed by query_orchestrator_factory.create_query_orchestrator.

The real MTR/cascade needs torch (T8); this module is torch-free at import.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from query_orchestrator_factory import create_query_orchestrator


@dataclass
class QueryContext:
    """Donor-shaped query context."""
    query_text: str
    user_id: Optional[str] = None
    project_context: Optional[str] = None
    session_id: Optional[str] = None
    hat: Optional[Any] = None  # behavioral context for epistemic routing


@dataclass
class QueryResult:
    """Donor-shaped result — what the 10 importers read."""
    user_query: str
    mtr_response: str
    mtr_confidence: float
    cartridge_facts: list
    grain_facts: list = None
    total_latency_ms: float = 0.0
    mtr_latency_ms: float = 0.0
    cartridge_latency_ms: float = 0.0
    grain_latency_ms: float = 0.0
    crystallization_report: Optional[Dict] = None


class _CartridgeEngineProxy:
    """Best-effort shim for orch.cartridge_engine.get_stats() used by demos."""
    def __init__(self, orchestrator):
        self._orch = orchestrator

    def get_stats(self):
        engine = self._orch.engines.get("CARTRIDGE")
        registry = getattr(engine, "registry", None)
        if registry is not None and hasattr(registry, "get_stats"):
            return registry.get_stats()
        return {"cartridge_count": 0, "total_facts": 0}


class Phase3EOrchestrator:
    """Donor-shaped orchestrator backed by the reconciled factory."""

    def __init__(self, cartridges_dir: str = "./cartridges", vocab_size: int = 50257,
                 d_model: int = 256, d_state: int = 144, state_dir: str = "data/state",
                 grain_storage_dir: str = "./grains", device: str = "cpu",
                 enable_grain_system: bool = True, dream_bucket_dir: str = None,
                 **kwargs) -> None:
        # Forward donor kwargs straight to the factory (it accepts them all).
        self._orch = create_query_orchestrator(
            cartridges_dir=cartridges_dir,
            vocab_size=vocab_size,
            d_model=d_model,
            d_state=d_state,
            state_dir=state_dir,
            grain_storage_dir=grain_storage_dir,
            device=device,
            enable_grain_system=enable_grain_system,
            dream_bucket_dir=dream_bucket_dir or "data/subconscious/dream_bucket",
        )

    # ---- donor API surface ------------------------------------------------ #
    def process_query(self, context: QueryContext) -> QueryResult:
        posix_result = self._orch.process_query(
            context.query_text,
            context={
                "project_context": context.project_context,
                "session_id": context.session_id,
                "user_id": context.user_id,
                "hat": context.hat,
            },
        )
        lr = posix_result.learning_report or {}
        return QueryResult(
            user_query=context.query_text,
            mtr_response=posix_result.answer or "",
            mtr_confidence=lr.get("mtr_confidence", posix_result.confidence),
            cartridge_facts=posix_result.cartridge_facts,
            grain_facts=None,
            total_latency_ms=posix_result.total_latency_ms,
            mtr_latency_ms=0.0,
            cartridge_latency_ms=0.0,
            grain_latency_ms=0.0,
            crystallization_report=lr.get("crystallization"),
        )

    @property
    def mtr_state(self) -> Dict[str, Any]:
        """Donor-style MTR state accessor (time/W/strength/copent_pos)."""
        obs = getattr(self._orch, "learning_observer", None)
        if obs is not None and getattr(obs, "mtr_state", None):
            return obs.mtr_state
        return {}

    def save_state(self, session_id: str = "default", metadata: Optional[dict] = None) -> None:
        self._orch.close(session_id)

    def get_stats(self) -> Dict[str, Any]:
        return self._orch.get_metrics()

    @property
    def cartridge_engine(self):
        return _CartridgeEngineProxy(self._orch)

    def print_summary(self) -> None:
        m = self.get_stats()
        print("Phase 3E (compat) Summary")
        for k, v in m.items():
            print(f"  {k}: {v}")

    def close(self, session_id: str = "default") -> None:
        self._orch.close(session_id)
