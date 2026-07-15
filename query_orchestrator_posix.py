"""
Kitbash_AI/query_orchestrator_posix.py

QueryOrchestrator - the single external entry point for user queries.

(Reconciled orchestrator per SPEC_ORCHESTRATOR_RECONCILIATION. Built by
query_orchestrator_factory.create_query_orchestrator(). Donor-style callers
use the phase3e_compat.py facade.)

Coordinates:
  1. Background work scheduling (via MetabolismScheduler)
  2. Mamba context retrieval (temporal windows)
  3. Triage routing decision (also routes background work)
  4. PAUSE background work (heartbeat.pause())
  5. Serial engine cascade (Complexity Sieve)
  6. RESUME background work (heartbeat.resume())
  7. Resonance pattern recording & Turn Sync
  8. Advance turn counter

Phase 3B MVP: GRAIN → CARTRIDGE only
Phase 4+: Add BITNET, LLM, specialists

Standardized for Phase 3B MVP.
"""

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from interfaces.triage_agent import TriageAgent, TriageRequest, TriageDecision
from interfaces.inference_engine import InferenceEngine, InferenceRequest, InferenceResponse
from interfaces.mamba_context_service import MambaContextService, MambaContextRequest
from resonance_weights import ResonanceWeightService
from heartbeat_service import HeartbeatService
from metabolism_scheduler import MetabolismScheduler
from learning_observer import LearningObserver

# Success Signal Integration (SPEC-SUCCESS_SIGNAL_INTEGRATION_v1):
# non-blocking Dream Bucket writer + coherence heuristic. Both degrade gracefully
# if unavailable so the answering path is never blocked.
try:
    from dream_bucket import DreamBucketWriter
    from query_completion_heuristic import CoherenceChecker, generate_trace_id
except ImportError:
    DreamBucketWriter = None
    CoherenceChecker = None
    generate_trace_id = None

# Phase 3B.3: Coupling Geometry Validation
try:
    from redis_coupling import CouplingValidator
except ImportError:
    CouplingValidator = None  # Graceful degradation if not available

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    """Final result returned to the caller."""
    query_id: str
    answer: Optional[str]
    confidence: float
    engine_name: str
    layer_results: List["LayerAttempt"]
    triage_reasoning: str
    triage_latency_ms: float
    total_latency_ms: float
    resonance_pattern_recorded: bool
    coupling_deltas: List[Dict[str, Any]] = field(default_factory=list)  # Phase 3B.3
    learning_report: Optional[dict] = None  # SPEC Step 3: LearningObserver output
    cartridge_facts: List[Dict[str, Any]] = field(default_factory=list)  # compat: winning fact
    mamba_injected: bool = False  # Pattern A: BitMamba context_1hour was prepended to the engine prompt


@dataclass
class LayerAttempt:
    """Record of a single engine attempt during cascade."""
    engine_name: str
    confidence: float
    threshold: float
    passed: bool
    latency_ms: float
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# No-op diagnostic feed
# ---------------------------------------------------------------------------

class _NoOpDiagnosticFeed:
    """Silent stand-in for DiagnosticFeed when Redis is unavailable."""
    def log_query_created(self, *a, **kw): pass
    def log_query_started(self, *a, **kw): pass
    def log_layer_attempt(self, *a, **kw): pass
    def log_layer_hit(self, *a, **kw): pass
    def log_layer_miss(self, *a, **kw): pass
    def log_escalation(self, *a, **kw): pass
    def log_error(self, *a, **kw): pass
    def log_query_completed(self, *a, **kw): pass
    def log_metric(self, *a, **kw): pass


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _serializable_mamba_context(mc) -> dict:
    """JSON-safe projection of MambaContext for the query context dict.

    The query context is a serializable-by-contract surface (T7 #8).
    - hidden_state (bytes) is EXCLUDED: engine plumbing, not context
      signal.
    - conversation_history Message timestamps (datetime, forced non-None
      by Message.__post_init__) are converted to ISO-8601 strings.
    Everything else passes through asdict() untouched. This dict is the
    Pattern B (routing-aware) entry point — rehydrate or read as needed.
    """
    if mc is None:
        return {}
    d = asdict(mc)
    d.pop("hidden_state", None)
    for m in d.get("conversation_history", []):
        ts = m.get("timestamp")
        if ts is not None and not isinstance(ts, str):
            m["timestamp"] = ts.isoformat()
    return d


class QueryOrchestrator:
    """
    Main coordinator for user-facing queries.
    
    Phase 3B MVP: Cascades through GRAIN → CARTRIDGE
    Phase 4+: Will add BITNET, LLM, specialists
    """

    FALLBACK_THRESHOLDS: Dict[str, float] = {
        "GRAIN":     0.90,
        "CARTRIDGE": 0.70,
        # Phase 4+:
        # "BITNET":    0.75,
        # "SPECIALIST": 0.65,
        # "LLM":       0.0,
    }

    ESCALATE_SENTINEL = "ESCALATE"

    def __init__(
        self,
        triage_agent: TriageAgent,
        engines: Dict[str, InferenceEngine],
        mamba_service: MambaContextService,
        resonance: ResonanceWeightService,
        heartbeat: Optional[HeartbeatService] = None,
        metabolism_scheduler: Optional[MetabolismScheduler] = None,
        shannon=None,
        diagnostic_feed=None,
        redis_client=None,  # Phase 3B.3: For coupling validation
        learning_observer: Optional[LearningObserver] = None,  # SPEC Step 3
    ) -> None:
        self.triage_agent = triage_agent
        self.engines = engines
        self.mamba_service = mamba_service
        self.resonance = resonance
        self.shannon = shannon
        self.learning_observer = learning_observer  # SPEC Step 3 (may be None)

        # Week 3 Metabolism components
        self.heartbeat = heartbeat or HeartbeatService(initial_turn=0)
        self.metabolism_scheduler = metabolism_scheduler

        # Phase 3B.3: Coupling validation
        self.coupling_validator = None
        if redis_client and CouplingValidator:
            try:
                self.coupling_validator = CouplingValidator(redis_client)
            except Exception as e:
                logger.warning(f"Could not initialize coupling validator: {e}")

        self.feed = self._init_feed(diagnostic_feed)

        # Success Signal Integration: lazily-held non-blocking Dream Bucket
        # writer for success_traces. None if dream_bucket unavailable.
        self._success_writer = None
        if DreamBucketWriter is not None:
            try:
                self._success_writer = DreamBucketWriter("dream_bucket")
            except Exception as e:
                logger.warning(f"Could not init success-trace writer: {e}")

        self._metrics: Dict[str, Any] = {
            "queries_total": 0,
            "queries_answered": 0,
            "queries_exhausted": 0,
            "layer_hits": {},
            "layer_attempts": {},
            "triage_latencies_ms": [],
            "total_latencies_ms": [],
            "heartbeat_pauses": 0,
            "metabolism_cycles_run": 0,
        }

    def process_query(
        self,
        user_query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> QueryResult:
        """
        Process a user query through the full orchestration pipeline.
        """
        query_id = str(uuid.uuid4())
        total_start = time.perf_counter()
        context = context or {}

        self.feed.log_query_created(query_id, user_query)
        self.feed.log_query_started(query_id)

        # PHASE 1: Metabolism check
        if self.metabolism_scheduler:
            try:
                # Sync turn to scheduler before checking if work is due
                self.metabolism_scheduler.current_turn = self.heartbeat.turn_number
                bg_status = self.metabolism_scheduler.step()
                if bg_status.get("executed"):
                    self._metrics["metabolism_cycles_run"] += 1
            except Exception as e:
                logger.warning(f"Metabolism scheduler failed: {e}")
                self.feed.log_error(query_id, "METABOLISM_SCHEDULER", str(e))

        # PHASE 2: Context retrieval
        mamba_context = self._get_mamba_context(user_query, context)
        context["mamba_context"] = _serializable_mamba_context(mamba_context)

        # Pattern A (consume Mamba downstream): prepend the BitMamba-generated
        # recent context to the ENGINE prompt only. Triage/routing/resonance/
        # learning keep the raw query. Empty when Mamba is disabled or returns
        # nothing, so behavior is unchanged in that case.
        mamba_text = ""
        if mamba_context is not None:
            mamba_text = (mamba_context.context_1hour or {}).get("generated", "") or ""
        augmented_query = (
            f"[Recent context]\n{mamba_text}\n\n{user_query}"
            if mamba_text else user_query
        )

        # PHASE 3: Triage
        triage_start = time.perf_counter()
        decision = self._get_triage_decision(user_query, context, query_id)
        triage_latency = (time.perf_counter() - triage_start) * 1000

        # PHASE 4: PAUSE background work
        if self.heartbeat:
            try:
                self.heartbeat.pause()
                self._metrics["heartbeat_pauses"] += 1
            except Exception as e:
                logger.warning(f"Heartbeat pause failed: {e}")
                self.feed.log_error(query_id, "HEARTBEAT_PAUSE", str(e))

        try:
            # PHASE 5: Engine cascade
            layer_results: List[LayerAttempt] = []
            winning_response: Optional[InferenceResponse] = None

            for layer_name in decision.layer_sequence:
                if layer_name == self.ESCALATE_SENTINEL:
                    break

                if layer_name not in self.engines:
                    logger.warning(f"Layer {layer_name} missing from engines.")
                    continue

                threshold = decision.confidence_thresholds.get(
                    layer_name, self.FALLBACK_THRESHOLDS.get(layer_name, 0.5)
                )

                attempt, response = self._attempt_layer(
                    layer_name, threshold, augmented_query, context, decision, query_id
                )
                layer_results.append(attempt)
                self._record_layer_metric(layer_name, attempt)

                # Phase 3B.3: Coupling validation after layer processes
                if self.coupling_validator:
                    try:
                        # Validate this layer against appropriate previous layers
                        if "L2" in layer_name:
                            self.coupling_validator.validate_and_record(query_id, "L1", "L2")
                        elif "L4" in layer_name:
                            self.coupling_validator.validate_and_record(query_id, "L2", "L4")
                            self.coupling_validator.validate_and_record(query_id, "L4", "L3")
                            self.coupling_validator.validate_and_record(query_id, "L4", "L5")
                    except Exception as e:
                        logger.debug(f"Coupling validation failed: {e}")
                        # Graceful degradation - continue query processing

                if attempt.passed:
                    winning_response = response
                    break

            # PHASE 6: Finalize response
            total_latency = (time.perf_counter() - total_start) * 1000
            pattern_recorded = False

            if winning_response and winning_response.answer:
                answer = winning_response.answer
                confidence = winning_response.confidence
                engine_name = winning_response.engine_name

                # Enrich cartridge_facts from winning response metadata so the
                # compat shim (and donor-style callers) can read fact provenance.
                _md = getattr(winning_response, "metadata", {}) or {}
                _cid = _md.get("fact_id")
                _csrc = _md.get("source") or _md.get("cartridge")
                cartridge_facts = (
                    [{"fact_id": _cid, "source": _csrc, "confidence": confidence}]
                    if _cid is not None else []
                )

                # Record pattern to resonance
                pattern_hash = self._hash_query(user_query)
                if pattern_hash in self.resonance.weights:
                    self.resonance.reinforce_pattern(pattern_hash)
                else:
                    self.resonance.record_pattern(
                        pattern_hash,
                        metadata={
                            "query": user_query[:200],
                            "engine": engine_name,
                            "query_id": query_id,
                        },
                    )
                pattern_recorded = True

                self.feed.log_query_completed(query_id, engine_name, confidence, total_latency)
                self._metrics["queries_answered"] += 1
            else:
                answer = "I don't know."
                confidence = 0.0
                engine_name = "NONE"
                cartridge_facts = []
                self.feed.log_query_completed(query_id, "NONE", 0.0, total_latency)
                self._metrics["queries_exhausted"] += 1

            self._metrics["queries_total"] += 1
            self._metrics["triage_latencies_ms"].append(triage_latency)
            self._metrics["total_latencies_ms"].append(total_latency)

            # Success Signal Integration (SPEC-SUCCESS_SIGNAL_INTEGRATION_v1):
            # post-answer, non-blocking coherence check. A clean answered query
            # carries violations_count=0 (user decision A); grains/facts are
            # pulled from the winning response's metadata. Fully guarded so a
            # logging failure never breaks answering.
            if (self._success_writer is not None
                    and CoherenceChecker is not None
                    and winning_response is not None
                    and getattr(winning_response, "answer", None)):
                try:
                    checker = CoherenceChecker()
                    result = checker.check(
                        violations_count=0,
                        top_grain_confidence=confidence,
                        response_length=len(answer.split()),
                        parse_errors=[],
                        query=user_query,
                    )
                    if result.passed:
                        _md = getattr(winning_response, "metadata", {}) or {}
                        _facts = [_md["fact_id"]] if _md.get("fact_id") is not None else []
                        _grains = (
                            _md["grain_id"] if isinstance(_md.get("grain_id"), list)
                            else ([_md["grain_id"]] if _md.get("grain_id") is not None else [])
                        )
                        from dream_bucket import log_success
                        log_success(
                            self._success_writer,
                            response=answer,
                            grains=_grains,
                            facts=_facts,
                            metadata={
                                "query_id": query_id,
                                "engine_name": engine_name,
                                "coherence_check": result.to_dict(),
                                "trace_id": generate_trace_id() if generate_trace_id else None,
                            },
                            session_id=session_id,
                        )
                except Exception as e:
                    logger.warning(f"Success-signal logging failed (non-blocking): {e}")

            # SPEC Step 3: post-answer learning. Failure isolation with LOUD
            # telemetry — learning must never break answering, but a dead
            # observer must scream into the feed + logs every query (never a
            # bare pass, which is how F1 stayed invisible).
            learning_report = None
            if self.learning_observer:
                try:
                    fact_ids = set()
                    grain_ids = []
                    if winning_response is not None:
                        # InferenceResponse exposes fact_id / grain_id on metadata
                        md = getattr(winning_response, "metadata", {}) or {}
                        fid = md.get("fact_id")
                        if fid is not None:
                            fact_ids.add(fid)
                        gid = md.get("grain_id") or md.get("grain_ids")
                        if gid:
                            grain_ids.extend(gid if isinstance(gid, list) else [gid])
                    result_summary = {
                        "answered": winning_response is not None
                        and bool(getattr(winning_response, "answer", None)),
                        "engine_name": engine_name,
                        "confidence": confidence,
                        "fact_ids": fact_ids,
                        "grain_ids": grain_ids,
                    }
                    learning_report = self.learning_observer.observe(
                        query_id, user_query, context, result_summary
                    ).__dict__
                    if learning_report.get("violation_error"):
                        self.feed.log_error(
                            query_id, "LEARNING_OBSERVER",
                            f"violation emission failed: {learning_report['violation_error']}",
                        )
                except Exception as e:
                    learning_report = {"error": str(e)}
                    self.feed.log_error(query_id, "LEARNING_OBSERVER", str(e))
                    logger.error(f"Learning observer failed: {e}")

            # SPEC Step 4: periodic checkpointing — flush observer (learning)
            # state every crystallization interval so learning survives restarts.
            if (self.learning_observer
                    and self.learning_observer.query_count > 0
                    and self.learning_observer.query_count
                    % self.learning_observer.crystallization_interval == 0):
                try:
                    self.learning_observer.save_state(session_id or "default")
                except Exception as e:
                    logger.debug(f"Periodic checkpoint failed: {e}")

            # Phase 3B.3: Collect coupling deltas
            coupling_deltas = []
            if self.coupling_validator:
                try:
                    coupling_deltas = self.coupling_validator.get_deltas_for_query(query_id)
                except Exception as e:
                    logger.debug(f"Could not retrieve coupling deltas: {e}")

            return QueryResult(
                query_id=query_id,
                answer=answer,
                confidence=confidence,
                engine_name=engine_name,
                layer_results=layer_results,
                triage_reasoning=decision.reasoning,
                triage_latency_ms=triage_latency,
                total_latency_ms=total_latency,
                resonance_pattern_recorded=pattern_recorded,
                coupling_deltas=coupling_deltas,  # Phase 3B.3
                learning_report=learning_report,  # SPEC Step 3
                cartridge_facts=cartridge_facts,  # compat: winning fact provenance
                mamba_injected=bool(mamba_text),  # Pattern A: context was prepended
            )

        finally:
            # PHASE 7 & 8: Resume & Advance Clock
            if self.heartbeat:
                try:
                    self.heartbeat.resume()
                    # Advance the master clock
                    new_turn = self.heartbeat.advance_turn()
                    
                    # Sync turn across stateful services
                    if hasattr(self.resonance, 'current_turn'):
                        self.resonance.current_turn = new_turn
                    if hasattr(self.triage_agent, 'current_turn'):
                        self.triage_agent.current_turn = new_turn
                        
                except Exception as e:
                    logger.warning(f"Turn advancement failed: {e}")

    def close(self, session_id: str = "default") -> None:
        """Shutdown hook (SPEC Step 4): flush observer (learning) state to disk.

        Safe to call multiple times; no-ops when no observer is wired.
        """
        if self.learning_observer is not None:
            try:
                self.learning_observer.save_state(session_id)
            except Exception as e:
                logger.warning(f"Observer save on close failed: {e}")
            # Flush the async dream-bucket trace queue so queued traces are
            # persisted before the process exits (daemon writer thread would
            # otherwise be killed with the interpreter, losing the records).
            writer = getattr(self.learning_observer, "dream_bucket_writer", None)
            if writer is not None and hasattr(writer, "close"):
                try:
                    writer.close()
                except Exception as e:
                    logger.warning(f"DreamBucket flush on close failed: {e}")
        # Flush the success-signal writer (success_traces) the same way.
        if self._success_writer is not None and hasattr(self._success_writer, "close"):
            try:
                self._success_writer.close()
            except Exception as e:
                logger.warning(f"Success-trace flush on close failed: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Return session-level performance metrics."""
        lats = self._metrics["total_latencies_ms"]
        
        def percentile(data, p):
            if not data: return 0.0
            sorted_data = sorted(data)
            return sorted_data[min(int(len(sorted_data) * p / 100), len(sorted_data) - 1)]
        
        return {
            "queries_total": self._metrics["queries_total"],
            "queries_answered": self._metrics["queries_answered"],
            "queries_exhausted": self._metrics["queries_exhausted"],
            "success_rate": (
                self._metrics["queries_answered"] / self._metrics["queries_total"]
                if self._metrics["queries_total"] > 0 else 0.0
            ),
            "latency_p50_ms": percentile(lats, 50),
            "latency_p95_ms": percentile(lats, 95),
            "latency_p99_ms": percentile(lats, 99),
            "avg_latency_ms": sum(lats) / len(lats) if lats else 0.0,
            "heartbeat_pauses": self._metrics["heartbeat_pauses"],
            "metabolism_cycles": self._metrics["metabolism_cycles_run"],
        }

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _init_feed(self, diagnostic_feed):
        """Initialize diagnostic feed (or no-op if unavailable)."""
        if diagnostic_feed:
            return diagnostic_feed
        return _NoOpDiagnosticFeed()

    def _get_mamba_context(self, user_query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve mamba context for query."""
        try:
            request = MambaContextRequest(
                user_id=context.get("user_id"),
                session_id=context.get("session_id"),
                user_query=user_query,
            )
            return self.mamba_service.get_context(request)
        except Exception as e:
            logger.warning(f"Mamba context retrieval failed: {e}")
            return {}

    def _get_triage_decision(
        self,
        user_query: str,
        context: Dict[str, Any],
        query_id: str,
    ) -> TriageDecision:
        """Get triage decision for layer sequence."""
        try:
            request = TriageRequest(
                user_query=user_query,
                context=context,
                metadata={"query_id": query_id},
            )
            return self.triage_agent.route(request)
        except Exception as e:
            logger.warning(f"Triage decision failed: {e}")
            # Fallback: Try GRAIN only
            return TriageDecision(
                layer_sequence=["GRAIN"],
                confidence_thresholds={"GRAIN": 0.90},
                reasoning=f"Fallback to GRAIN due to triage error: {e}",
            )

    def _attempt_layer(
        self,
        layer_name: str,
        threshold: float,
        user_query: str,
        context: Dict[str, Any],
        decision: TriageDecision,
        query_id: str,
    ) -> tuple:
        """Attempt a single inference layer."""
        engine = self.engines[layer_name]
        attempt_start = time.perf_counter()

        try:
            request = InferenceRequest(
                user_query=user_query,
                context=context,
            )
            response = engine.query(request)
            latency = (time.perf_counter() - attempt_start) * 1000

            passed = response.confidence >= threshold
            
            attempt = LayerAttempt(
                engine_name=layer_name,
                confidence=response.confidence,
                threshold=threshold,
                passed=passed,
                latency_ms=latency,
            )

            if passed:
                self.feed.log_layer_hit(query_id, layer_name, response.confidence)
            else:
                self.feed.log_layer_miss(query_id, layer_name, response.confidence, threshold)

            return attempt, response

        except Exception as e:
            latency = (time.perf_counter() - attempt_start) * 1000
            logger.warning(f"Layer {layer_name} failed: {e}")
            
            attempt = LayerAttempt(
                engine_name=layer_name,
                confidence=0.0,
                threshold=threshold,
                passed=False,
                latency_ms=latency,
                error=str(e),
            )
            
            self.feed.log_error(query_id, layer_name, str(e))
            return attempt, None

    def _record_layer_metric(self, layer_name: str, attempt: LayerAttempt) -> None:
        """Record metrics for layer attempt."""
        if layer_name not in self._metrics["layer_attempts"]:
            self._metrics["layer_attempts"][layer_name] = 0
        self._metrics["layer_attempts"][layer_name] += 1

        if attempt.passed:
            if layer_name not in self._metrics["layer_hits"]:
                self._metrics["layer_hits"][layer_name] = 0
            self._metrics["layer_hits"][layer_name] += 1

    def _hash_query(self, user_query: str) -> str:
        """Hash query for resonance pattern matching."""
        return hashlib.sha256(user_query.encode()).hexdigest()[:16]
