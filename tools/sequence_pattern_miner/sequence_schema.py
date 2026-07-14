"""Dataclasses for tools.sequence_pattern_miner (see SPEC-sequence_pattern_miner_v1.md).

These mirror the JSON shapes. Core functions build plain dicts (per the SPEC's
composability requirement); dataclasses document the contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Sequence:
    rank: int
    sequence: List[str]  # list of prefixed element IDs
    sequence_type: str   # "fact→fact", "grain→grain", "mixed", etc.
    occurrence_count: int
    frequency_percent: float
    traces_containing: Optional[List[str]] = None
    first_observed_trace: Optional[str] = None
    last_observed_trace: Optional[str] = None


@dataclass
class ExtractionStats:
    total_chains_analyzed: int
    total_ngrams_extracted: int
    unique_sequences: int
    most_common_frequency: int
    least_common_frequency: int
    average_frequency: float


@dataclass
class ExtractionReport:
    extraction_params: Dict[str, Any]
    statistics: ExtractionStats
    sequences: List[Sequence]


@dataclass
class MarkovTransition:
    source_element: str
    target_element: str
    transition_count: int
    transition_probability: float
    frequency_percent: float


@dataclass
class MarkovState:
    state: str
    outgoing_transitions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarkovReport:
    transitions: Dict[str, Dict[str, Any]]
    state_count: int
    total_transitions: int
