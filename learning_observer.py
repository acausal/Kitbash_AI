#!/usr/bin/env python3
"""
LearningObserver (SPEC Step 2 / T3)

Owns everything the donor did *after* answering: feedback logging, epistemic
snapshot, phantom pipeline, single phantom-cycle advance, grain activation on
crystallization, per-query trace logging, and a single counter increment.

Dependency-injected: the constructor takes already-built instances and builds
nothing itself (per SPEC §3.1). The MTR inference path is torch-guarded so the
contract tests run with STUB objects (no torch required).

B1-B6 fixes applied relative to the donor (query_orchestrator.py):
  B1  exactly ONE query_count increment, owned here (donor incremented twice).
  B2  advance_phantom_cycle() exactly ONCE per query (donor advanced twice).
      Cadence: PRE-query advance (so locking semantics stay consistent), per
      SPEC §3.1 "single phantom-cycle advance".
  B3  trace logging uses context.project_context (not context.project); the
      path is guarded so no AttributeError crashes a live trace.
  B4  per-query trace chain = ONLY this query's facts/grains (recent_/bounded
      deques kept separately for co-occurrence features, capped at 20).
  B5  confidence computed ONCE as 1.0 - error and used everywhere.
  B6  hat serialized as str(hat) (never the raw object) in trace context.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from collections import deque
from datetime import datetime
from pathlib import Path

# Torch is optional here: the observer only touches torch objects that are
# injected (mtr_engine, mtr_state). The contract tests use stub objects.
try:
    import torch
except Exception:  # pragma: no cover - allows stub-based tests without torch
    torch = None


@dataclass
class LearningReport:
    mtr_error: float = 0.0
    mtr_confidence: float = 0.0
    crystallization: Optional[dict] = None
    trace_logged: bool = False
    latency_ms: float = 0.0
    error: Optional[str] = None
    violation_emitted: bool = False          # a violation record was queued this query
    violation_error: Optional[str] = None    # emission attempted but failed (exception or backpressure)


class LearningObserver:
    """
    Post-answer learning pipeline. Construct with shared, already-built
    components (F2 coherence: these ARE the canonical instances).

    Args:
        mtr_engine: KitbashMTREngine (v6.1) or a stub with the same call shape.
        state_manager: MTRStateCheckpoint (save/load).
        cartridge_engine: the SHARED CartridgeInferenceEngine (F2).
        grain_router: the SHARED GrainRouter.
        mtr_grain_pipeline: MTRGrainUnifiedPipeline or None.
        l2_service: L2WorkingTheoryService or None (read-only audit; optional).
        dream_bucket_writer: DreamBucketWriter or None (trace + false-positive sink).
        crystallization_interval: queries between crystallization checks.
        device: torch device string.
    """

    def __init__(self,
                 mtr_engine: Any,
                 state_manager: Any,
                 cartridge_engine: Any,
                 grain_router: Any,
                 mtr_grain_pipeline: Any = None,
                 l2_service: Any = None,
                 dream_bucket_writer: Any = None,
                 crystallization_interval: int = 51,
                 device: str = "cpu"):
        self.mtr_engine = mtr_engine
        self.state_manager = state_manager
        self.cartridge_engine = cartridge_engine
        self.grain_router = grain_router
        self.mtr_grain_pipeline = mtr_grain_pipeline
        self.l2_service = l2_service
        self.dream_bucket_writer = dream_bucket_writer
        self.crystallization_interval = crystallization_interval
        self.device = device

        # Held MTR state (mutated by observe()). May be None until first inference.
        self.mtr_state = None
        # B1: ONE counter, owned here.
        self.query_count = 0

        # B4: separate bounded deques for co-occurrence/recency features.
        self._recent_facts: deque = deque(maxlen=20)
        self._recent_grains: deque = deque(maxlen=20)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def observe(self, query_id: str, user_query: str, context: Any,
                result_summary: Dict[str, Any]) -> LearningReport:
        """
        Run the post-answer learning pipeline for a single query.

        Args:
            query_id: stable id for this query.
            user_query: raw query text (for tokenization / concepts).
            context: object with .hat and .project_context attributes.
            result_summary: {
                answered: bool, engine_name, confidence,
                fact_ids: set, grain_ids: list,
            }

        Returns:
            LearningReport.
        """
        import time
        start = time.perf_counter()
        report = LearningReport()

        try:
            hat = getattr(context, "hat", None)
            project_context = getattr(context, "project_context", None) or "general"

            # --- tokenize ---
            tokens = self._simple_tokenize(user_query)
            fact_ids: Set[int] = set(result_summary.get("fact_ids", set()) or set())
            grain_ids: List[str] = list(result_summary.get("grain_ids", []) or [])
            # B4-style recency window: append THIS query's facts for the
            # violation-context chain (capped at 20 by the deque).
            if fact_ids:
                self._recent_facts.extend(fact_ids)

            # --- kappa from hat (epistemic rigidity) ---
            kappa = 1.0
            if hat is not None:
                try:
                    from mtr_grain_bridge import HatKappaMapper
                    kappa = HatKappaMapper.get_kappa(hat)
                except Exception:
                    kappa = 1.0

            # --- MTR inference (torch-guarded; stubs callable without torch) ---
            error_signal = None
            logits = None
            mtr_confidence = 0.0
            new_state = self.mtr_state
            if self.mtr_engine is not None:
                # Build token tensor only if torch is available AND engine wants one.
                token_ids = self._to_tensor(tokens, self.device)
                with self._no_grad():
                    out = self.mtr_engine(token_ids, state=self.mtr_state, kappa=kappa)
                # Normalize heterogeneous engine returns.
                if isinstance(out, tuple):
                    parts = list(out)
                    logits = parts[0]
                    error_signal = parts[1] if len(parts) > 1 else None
                    if len(parts) > 2:
                        new_state = parts[2]
                else:
                    logits = out
                self.mtr_state = new_state
                if error_signal is not None:
                    mtr_error = self._mean(error_signal)
                    # B5: confidence computed ONCE, used everywhere.
                    mtr_confidence = 1.0 - mtr_error
                    report.mtr_error = mtr_error
                    report.mtr_confidence = mtr_confidence
                    # --- dissonance detection (moved here from mtr()) ---
                    # Coherence dissonance = high MTR error signal (low model
                    # self-confidence in its own reasoning). Gate: mtr_error > 0.5.
                    if mtr_error > 0.5 and self.dream_bucket_writer is not None:
                        try:
                            from dream_bucket import log_consistency_violation
                            # Determinism (finding 4): smallest fact_id is
                            # reproducible across processes. result_summary
                            # carries no primary/answering fact today; if it
                            # ever does, prefer it over min() (leave as comment).
                            queued = log_consistency_violation(
                                writer=self.dream_bucket_writer,
                                source_layer="mtr",
                                returned_fact_id=min(fact_ids) if fact_ids else 0,
                                returned_confidence=mtr_confidence,
                                mtr_error_signal=mtr_error,
                                dissonance_type="high_confidence_low_coherence",
                                context={"recent_fact_ids": list(self._recent_facts)},
                            )
                            if queued:
                                report.violation_emitted = True
                            else:
                                report.violation_error = "writer.append returned False (queue backpressure)"
                        except Exception as e:
                            report.violation_error = f"{type(e).__name__}: {e}"

            # --- PHASE 4: feedback logging (B1 owned elsewhere; here only writes) ---
            if fact_ids:
                self._log_cartridge_feedback(fact_ids, mtr_confidence, project_context)
            if grain_ids:
                self._log_grain_feedback(grain_ids, mtr_confidence, project_context)

            # --- epistemic snapshot + phantom pipeline ---
            crystallization_report = None
            if self.mtr_grain_pipeline is not None:
                epistemic_snapshot = self._epistemic_snapshot(tokens, kappa)
                # B2: advance phantom cycle EXACTLY ONCE, pre-query.
                self.mtr_grain_pipeline.advance_phantom_cycle()
                pipeline_metadata = self.mtr_grain_pipeline.process_mtr_query(
                    fact_ids=fact_ids,
                    query_tokens=tokens,
                    error_signal=error_signal if error_signal is not None else _ZeroTensor(),
                    epistemic_snapshot=epistemic_snapshot,
                    hat=hat,
                    dissonance_result=None,
                )
                crystallization_report = (pipeline_metadata or {}).get("crystallization")
                # Activate newly crystallized grains into L3 cache.
                if crystallization_report and self.grain_router is not None:
                    newly = crystallization_report.get("crystallized_grains", [])
                    new_ids = [g.get("grain_id") for g in newly if g.get("grain_id")]
                    if new_ids:
                        self.grain_router.activate_grains(new_ids)
                if crystallization_report is not None:
                    report.crystallization = crystallization_report

            # --- per-query trace logging (B3/B4/B6) ---
            report.trace_logged = self._log_trace(
                query_id=query_id,
                user_query=user_query,
                fact_ids=fact_ids,
                grain_ids=grain_ids,
                confidence=mtr_confidence,
                hat=hat,
                project_context=project_context,
            )

            # --- B1: exactly ONE counter increment, owned here. ---
            self.query_count += 1

        except Exception as e:  # never break answering; report + re-raise-free
            report.error = str(e)
            report.latency_ms = (time.perf_counter() - start) * 1000.0
            return report

        report.latency_ms = (time.perf_counter() - start) * 1000.0
        return report

    def save_state(self, session_id: str = "default", metadata: Optional[Dict] = None) -> None:
        """Persist MTR state + query_count via the injected state_manager."""
        if self.mtr_state is None or self.state_manager is None:
            return
        meta = dict(metadata or {})
        meta["query_count"] = self.query_count
        self.state_manager.save(
            self.mtr_state,
            d_model=getattr(self.mtr_engine, "d_model", 0),
            d_state=getattr(self.mtr_engine, "d_state", 0),
            session_id=session_id,
            metadata=meta,
        )

    def load_state(self, device: str = None) -> None:
        if self.state_manager is None:
            return
        try:
            state, _ = self.state_manager.load(device or self.device)
            self.mtr_state = state
        except Exception:
            self.mtr_state = None

    # ------------------------------------------------------------------ #
    # Feedback helpers
    # ------------------------------------------------------------------ #
    def _log_cartridge_feedback(self, fact_ids: Set[int], mtr_confidence: float,
                                project_context: str) -> None:
        if self.cartridge_engine is None:
            return
        success = mtr_confidence >= 0.75
        mtr_error = 1.0 - mtr_confidence
        for fid in fact_ids:
            try:
                self.cartridge_engine.log_fact_usage(
                    fact_id=fid, success=success, mtr_error=mtr_error,
                    context=project_context,
                )
            except Exception:
                pass

    def _log_grain_feedback(self, grain_ids: List[str], mtr_confidence: float,
                            project_context: str) -> None:
        if self.grain_router is None:
            return
        success = mtr_confidence >= 0.75
        mtr_error = 1.0 - mtr_confidence
        for gid in grain_ids:
            try:
                self.grain_router.log_grain_outcome(gid, mtr_error)
                self.grain_router.log_grain_usage(gid, success, mtr_error, project_context)
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Trace logging (B3 / B4 / B6)
    # ------------------------------------------------------------------ #
    def _log_trace(self, query_id, user_query, fact_ids, grain_ids,
                   confidence, hat, project_context) -> bool:
        if self.dream_bucket_writer is None:
            return False
        # B6: serialize hat as string, never the raw object.
        hat_str = str(hat) if hat is not None else None
        # B4: per-query chain = ONLY this query's items (no unbounded history).
        chain = {
            "query_id": query_id,
            "chain_type": "intra_query",
            "fact_ids": sorted(fact_ids),
            "grain_ids": list(grain_ids),
            "confidence": confidence,
        }
        record = {
            # B3: correct attribute (project_context, not project).
            "project_context": project_context,
            "query_id": query_id,
            "query_text": user_query,
            "hat": hat_str,
            "confidence": confidence,
            "chain": chain,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        try:
            # B3: whole block guarded so a missing field never crashes answering.
            self.dream_bucket_writer.append("traces", record)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # Small utilities (torch-optional)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _simple_tokenize(text: str) -> List[int]:
        return [hash(w) % 49256 for w in text.lower().split()]

    def _to_tensor(self, tokens, device):
        if torch is None:
            return tokens  # stubs can accept a plain list
        return torch.tensor([tokens], dtype=torch.long, device=device)

    def _no_grad(self):
        if torch is not None:
            return torch.no_grad()
        # No-op context manager when torch absent.
        from contextlib import nullcontext
        return nullcontext()

    @staticmethod
    def _mean(x) -> float:
        # Prefer a native .mean() (torch tensors AND stub _Meanable) — this must
        # run regardless of whether torch is imported.
        if hasattr(x, "mean"):
            try:
                return float(x.mean())
            except Exception:
                pass
        try:
            return float(sum(x) / len(x))
        except Exception:
            return 0.0

    def _epistemic_snapshot(self, tokens, kappa):
        if self.mtr_engine is not None and hasattr(self.mtr_engine, "get_epistemic_snapshot"):
            try:
                token_ids = self._to_tensor(tokens, self.device)
                return self.mtr_engine.get_epistemic_snapshot(token_ids, self.mtr_state, kappa)
            except Exception:
                pass
        return {}


class _ZeroTensor:
    """Minimal stand-in so pipeline calls never crash when torch absent."""
    def mean(self, *a, **k):
        return 0.0
