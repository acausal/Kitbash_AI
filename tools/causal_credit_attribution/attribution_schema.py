"""Dataclasses for tools.causal_credit_attribution (see SPEC). Mirror JSON shapes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ToolAttribution:
    position: int
    tool: str
    credit_score: float
    attribution_signals: Dict[str, float]
    appears_in_patterns: List[str]
    historical_success_rate: float
    confidence: str


@dataclass
class GrainAttribution:
    position: int
    grain_id: int
    credit_score: float
    attribution_signals: Dict[str, float]
    appears_in_patterns: List[str]
    historical_success_rate: float
    confidence: str


@dataclass
class AttributionResult:
    attribution_run_id: str
    timestamp: str
    trace_id: str
    trace_sequence: List[Any]
    outcome: str
    error_signal: float
    total_credit_attributed: float
    tool_attributions: List[ToolAttribution]
    metadata: Dict[str, Any]
