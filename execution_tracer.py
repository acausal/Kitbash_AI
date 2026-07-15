"""Execution trace collection for Kitbash (standalone, dependency-free).

Implements the TraceEvent / ExecutionTracer dataclasses from
docs/SPEC-WEBUI_AND_TRACE_VISIBILITY_v1.md. This module is PURE (stdlib only,
no repo imports) so it can be used by kitbash_cli.py to emit trace events as
NDJSON without coupling the CLI to the orchestrator internals.

Design note (see docs/DEVNOTE-WEBUI_AND_TRACE_VISIBILITY.md): the spec imagined
a server-side tracer wired into the orchestrator. The real architecture runs the
orchestrator inside the kitbash_cli subprocess, so the CLI is the trace collector
and emits events on stdout. This module is that collector's data model.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TraceEvent:
    """One step in the query execution pipeline."""
    step_name: str                       # "query_entry" | "mamba_context" | "engine_cascade" | "final_assembly"
    timestamp: str                       # ISO 8601
    input: Dict[str, Any]
    output: Dict[str, Any]
    duration_ms: int
    metadata: Dict[str, Any] = field(default_factory=dict)


# Canonical step names (kept here so emitters + consumers agree).
STEP_QUERY_ENTRY = "query_entry"
STEP_MAMBA_CONTEXT = "mamba_context"
STEP_ENGINE_CASCADE = "engine_cascade"
STEP_FINAL_ASSEMBLY = "final_assembly"


class ExecutionTracer:
    """Collect trace events during a single query execution."""

    def __init__(self) -> None:
        self._events: List[TraceEvent] = []

    def trace(
        self,
        step_name: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        duration_ms: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceEvent:
        """Record a trace event and return it."""
        event = TraceEvent(
            step_name=step_name,
            timestamp=datetime.now().isoformat(),
            input=input_data or {},
            output=output_data or {},
            duration_ms=int(duration_ms),
            metadata=metadata or {},
        )
        self._events.append(event)
        return event

    def events(self) -> List[TraceEvent]:
        """Return collected events in insertion order."""
        return list(self._events)

    def to_json(self) -> str:
        """Serialize all events as a JSON array string."""
        return json.dumps([asdict(e) for e in self._events], ensure_ascii=False, indent=2)

    def clear(self) -> None:
        """Clear events (for the next query)."""
        self._events = []


if __name__ == "__main__":
    # Smoke demo (stdout JSON, no side effects).
    t = ExecutionTracer()
    t.trace(STEP_QUERY_ENTRY, {"query": "x"}, {"query_len": 1}, 0)
    t.trace(STEP_FINAL_ASSEMBLY, {}, {"answer_len": 3}, 12)
    print(t.to_json())
