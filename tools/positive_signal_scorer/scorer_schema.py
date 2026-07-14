"""Dataclasses for tools.positive_signal_scorer (see SPEC-positive_signal_scorer_v1.md).

Mirror the JSON shapes. Core functions build plain dicts; dataclasses document
the contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DimensionScore:
    pattern_id: str
    score: float
    numerator: int = 0
    denominator: int = 0


@dataclass
class ScoredPattern:
    pattern_id: str
    pattern: List[Any]
    signal_strength: float
    rank: int
    signal_dimensions: Dict[str, float]
    sample_size: int
    sample_size_confidence: str
    success_rate_given_pattern: float
    coverage: float
    notes: str = ""


@dataclass
class ScoreResult:
    scoring_run_id: str
    timestamp: str
    patterns_scored: int
    patterns: List[ScoredPattern]
    metadata: Dict[str, Any]
