"""Dataclasses for tools.conditional_pattern_detector (see SPEC-conditional_pattern_detector_v1.md).

Mirror the JSON shapes. Core functions build plain dicts (composability); these
document the contract. Field `skipped_types` (post-1.0) records condition/outcome
types the detector omits because `log_parser` traces don't yet carry the needed
fields (per user decision 2026-07-14).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Condition:
    type: str  # "chain_length", "element_presence", "element_type_distribution", "element_count", "traversal_type_pattern"
    operator: Optional[str] = None  # ">=", "<", "=="
    value: Optional[Any] = None
    element_id: Optional[str] = None
    element_type: Optional[str] = None
    present: Optional[bool] = None
    dominant_type: Optional[str] = None


@dataclass
class Outcome:
    type: str  # "element_type_distribution", "element_type_sequence", "next_element_type", "traversal_type_dominance"
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PatternMetrics:
    support: int
    confidence: float
    lift: float
    inverse_confidence: float


@dataclass
class ConditionalPattern:
    rank: int
    condition: Condition
    outcome: Outcome
    metrics: PatternMetrics
    interpretation: Optional[str] = None


@dataclass
class DetectionReport:
    detection_params: Dict[str, Any]
    statistics: Dict[str, Any]
    rules: List[ConditionalPattern]
    condition_types_found: List[str]
    skipped_types: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class DecisionNode:
    condition: Condition
    info_gain: float
    traces_true: int
    traces_false: int
    children: Optional[Dict[str, "DecisionNode"]] = None
    outcome_distribution: Optional[Dict[str, int]] = None


@dataclass
class SeedResult:
    seed_condition: Condition
    traces_matching_condition: int
    outcomes: List[Dict[str, Any]] = field(default_factory=list)
