"""L5 user-model observation logger (observation-only, non-acting).

Roadmap Phase D2 (L5 user model, observation-only). This module records, per
query, the session signals the live orchestrator already exposes, plus any
hat/topic/session_id the caller chooses to pass via `context` (forward-
compatible: empty/None when absent, never fabricated). It does NOT act on or
modify anything — it only observes and persists.

Grounded audit (2026-07-15):
- The LIVE orchestrator (query_orchestrator_posix.py) exposes at the hook:
  query text, winning engine name, confidence, total latency, triage
  layer_sequence, and any session_id in `context`. It does NOT compute a 'hat'
  or 'topic' itself (those only existed in the retired attic/query_orchestrator.py,
  and Mamba — the L4/L5 source — is off in this deployment). So we record what
  is real and accept hat/topic/session_id from `context` if provided.
- The recorder is the single source of truth for "what L5 saw". Analysis
  (temporal patterns, engine distribution, hat/topic distribution) is done by
  `summarize()` over the persisted JSONL — also non-acting.

Pure stdlib. No torch / no orchestrator import, so it can be unit-tested in
isolation. Wire into process_query as an optional, fully-guarded observer.

Usage (wiring, done in query_orchestrator_posix.py):
    self._l5_logger = L5ObservationLogger("data/l5_observations.jsonl") or None
    ...
    if self._l5_logger is not None:
        try:
            self._l5_logger.observe(query_id, user_query, context, decision,
                                    winning_response, total_latency)
        except Exception as e:
            logger.debug(f"L5 observation failed (non-blocking): {e}")
"""
from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class L5ObservationLogger:
    """Append-only observer for L5 / session-state signals.

    Each `observe()` call writes one JSON line. The record captures the live
    signals plus any forward-compatible context fields (hat/topic/session_id).
    """

    def __init__(self, log_path: str) -> None:
        self.log_path = log_path
        self._turn = 0

    def observe(
        self,
        query_id: str,
        user_query: str,
        context: Optional[Dict[str, Any]],
        decision: Any,
        winning_response: Any,
        total_latency_ms: float,
    ) -> Dict[str, Any]:
        """Record one observation. Returns the record (also appended to disk)."""
        context = context or {}
        self._turn += 1

        winning_engine = None
        confidence = None
        if winning_response is not None:
            winning_engine = getattr(winning_response, "engine_name", None)
            confidence = getattr(winning_response, "confidence", None)

        layer_sequence = None
        if decision is not None:
            layer_sequence = getattr(decision, "layer_sequence", None)

        record = {
            "type": "l5_observation",
            "query_id": query_id,
            "timestamp": _now_iso(),
            "turn": self._turn,
            "query": user_query,
            "winning_engine": winning_engine,
            "confidence": confidence,
            "total_latency_ms": total_latency_ms,
            "layer_sequence": list(layer_sequence) if layer_sequence is not None else None,
            # Forward-compatible: only present if the caller supplies them.
            "hat": context.get("hat"),
            "topic": context.get("topic"),
            "session_id": context.get("session_id"),
        }

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def flush(self) -> None:
        """No buffered state; retained for API symmetry with other loggers."""
        return None

    @classmethod
    def summarize(cls, log_path: str) -> Dict[str, Any]:
        """Non-acting analysis over persisted observations.

        Reports distributions that answer 'temporal patterns / engine mix /
        hat & topic mix' without modifying anything. Fields absent in all
        records (e.g. hat when never supplied) report empty distributions.
        """
        records: List[Dict[str, Any]] = []
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
        except FileNotFoundError:
            return {"observations": 0, "note": "no log file"}

        if not records:
            return {"observations": 0}

        engine_dist = Counter(r.get("winning_engine") for r in records)
        hat_dist = Counter(r.get("hat") for r in records if r.get("hat") is not None)
        topic_dist = Counter(r.get("topic") for r in records if r.get("topic") is not None)
        session_dist = Counter(r.get("session_id") for r in records if r.get("session_id") is not None)
        # Temporal: bucket by hour-of-day (UTC) from timestamp.
        hour_dist = Counter()
        for r in records:
            try:
                ts = datetime.fromisoformat(r["timestamp"])
                hour_dist[ts.hour] += 1
            except Exception:
                pass
        confs = [r["confidence"] for r in records if isinstance(r.get("confidence"), (int, float))]
        avg_conf = sum(confs) / len(confs) if confs else None

        return {
            "observations": len(records),
            "turns": max((r.get("turn", 0) for r in records), default=0),
            "engine_distribution": dict(engine_dist),
            "hat_distribution": dict(hat_dist),
            "topic_distribution": dict(topic_dist),
            "session_distribution": dict(session_dist),
            "hour_of_day_distribution": dict(hour_dist),
            "avg_confidence": round(avg_conf, 4) if avg_conf is not None else None,
        }
